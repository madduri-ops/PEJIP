"""Where AI spend is recorded.

The ledger holds one row per call: feature, model, token counts and cost. It never
holds prompts, responses or anything else that could carry personal data.

Amounts are integer nano-dollars. A call is first *reserved* at its worst-case
cost, then *settled* at its actual cost or *released* if nothing was billed. Open
reservations count towards the month's spend, so concurrent workers can't
overshoot the cap together, and a crashed worker's reservation keeps counting
(spend is overstated, never understated).
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .pricing import TokenUsage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_spend (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    month TEXT NOT NULL,
    feature TEXT NOT NULL,
    model TEXT NOT NULL,
    essential INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'released')),
    reserved_nanos INTEGER NOT NULL,
    cost_nanos INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_write_tokens INTEGER,
    cache_read_tokens INTEGER,
    web_search_requests INTEGER
);
CREATE INDEX IF NOT EXISTS ai_spend_month ON ai_spend (month, status);
"""

# Open reservations count at their reserved amount, settled calls at their cost.
_SPENT = """
SELECT COALESCE(SUM(CASE status WHEN 'reserved' THEN reserved_nanos ELSE cost_nanos END), 0)
FROM ai_spend WHERE month = ? AND status != 'released'
"""


class CapReachedError(Exception):
    """Raised by a ledger when a reservation would take spend past the cap."""

    def __init__(self, spent_nanos: int, requested_nanos: int, cap_nanos: int) -> None:
        super().__init__(spent_nanos, requested_nanos, cap_nanos)
        self.spent_nanos = spent_nanos
        self.requested_nanos = requested_nanos
        self.cap_nanos = cap_nanos


@dataclass(frozen=True)
class SpendRequest:
    """A call asking to reserve budget: who is calling, and its worst-case cost."""

    month: str
    at: datetime
    feature: str
    model: str
    amount_nanos: int
    essential: bool = False


@dataclass(frozen=True)
class SpendLine:
    """Settled spend for one feature and model in a month."""

    feature: str
    model: str
    calls: int
    cost_nanos: int


class Ledger(Protocol):
    def reserve(self, request: SpendRequest, *, cap_nanos: int | None) -> int:
        """Record a reservation and return its id, atomically refusing it with
        ``CapReachedError`` if it would take the month past ``cap_nanos``."""
        ...  # pragma: no cover

    def settle(
        self, reservation_id: int, *, cost_nanos: int, usage: TokenUsage
    ) -> None: ...  # pragma: no cover

    def release(self, reservation_id: int) -> None: ...  # pragma: no cover

    def spent(self, month: str) -> int: ...  # pragma: no cover

    def breakdown(self, month: str) -> list[SpendLine]: ...  # pragma: no cover


class SqliteLedger:
    """Ledger in a SQLite file. Safe across threads and across processes that
    share the file: reservations take SQLite's write lock while they check the cap.

    Keep the file on persistent storage; a ledger that resets mid-month resets
    the cap with it.
    """

    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(
            str(path), isolation_level=None, check_same_thread=False, timeout=30
        )
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def reserve(self, request: SpendRequest, *, cap_nanos: int | None) -> int:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                spent = self._conn.execute(_SPENT, (request.month,)).fetchone()[0]
                _check_cap(spent, request.amount_nanos, cap_nanos)
                cursor = self._conn.execute(
                    "INSERT INTO ai_spend"
                    " (created_at, month, feature, model, essential, status, reserved_nanos)"
                    " VALUES (?, ?, ?, ?, ?, 'reserved', ?)",
                    (
                        request.at.isoformat(),
                        request.month,
                        request.feature,
                        request.model,
                        int(request.essential),
                        request.amount_nanos,
                    ),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            return int(cursor.lastrowid)  # type: ignore[arg-type]

    def settle(self, reservation_id: int, *, cost_nanos: int, usage: TokenUsage) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE ai_spend SET status = 'settled', cost_nanos = ?,"
                " input_tokens = ?, output_tokens = ?, cache_write_tokens = ?,"
                " cache_read_tokens = ?, web_search_requests = ?"
                " WHERE id = ? AND status = 'reserved'",
                (
                    cost_nanos,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_write_tokens,
                    usage.cache_read_tokens,
                    usage.web_search_requests,
                    reservation_id,
                ),
            )

    def release(self, reservation_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE ai_spend SET status = 'released', cost_nanos = 0"
                " WHERE id = ? AND status = 'reserved'",
                (reservation_id,),
            )

    def spent(self, month: str) -> int:
        with self._lock:
            return int(self._conn.execute(_SPENT, (month,)).fetchone()[0])

    def breakdown(self, month: str) -> list[SpendLine]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT feature, model, COUNT(*), SUM(cost_nanos) FROM ai_spend"
                " WHERE month = ? AND status = 'settled'"
                " GROUP BY feature, model ORDER BY feature, model",
                (month,),
            ).fetchall()
        return [SpendLine(feature, model, calls, cost) for feature, model, calls, cost in rows]


def _check_cap(spent_nanos: int, requested_nanos: int, cap_nanos: int | None) -> None:
    if cap_nanos is not None and spent_nanos + requested_nanos > cap_nanos:
        raise CapReachedError(spent_nanos, requested_nanos, cap_nanos)
