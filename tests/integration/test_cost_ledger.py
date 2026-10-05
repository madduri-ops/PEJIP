import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pejip.cost.ledger import CapReachedError, SpendLine, SpendRequest, SqliteLedger
from pejip.cost.pricing import TokenUsage

AT = datetime(2026, 10, 5, tzinfo=UTC)


def reserve(
    ledger: SqliteLedger,
    amount: int,
    *,
    cap: int | None = 1000,
    month: str = "2026-10",
    feature: str = "ranking",
) -> int:
    return ledger.reserve(SpendRequest(month, AT, feature, "m", amount), cap_nanos=cap)


def test_reservations_count_until_settled_or_released(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    first = reserve(ledger, 300)
    second = reserve(ledger, 200)
    assert ledger.spent("2026-10") == 500
    ledger.settle(first, cost_nanos=50, usage=TokenUsage(input_tokens=1))
    assert ledger.spent("2026-10") == 250
    ledger.release(second)
    assert ledger.spent("2026-10") == 50
    ledger.close()


def test_settle_and_release_only_touch_open_reservations(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    rid = reserve(ledger, 300)
    ledger.settle(rid, cost_nanos=40, usage=TokenUsage())
    ledger.release(rid)
    ledger.settle(rid, cost_nanos=999, usage=TokenUsage())
    assert ledger.spent("2026-10") == 40


def test_cap_is_checked_atomically_and_nothing_is_written_on_refusal(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    reserve(ledger, 900)
    with pytest.raises(CapReachedError) as refused:
        reserve(ledger, 101)
    assert (refused.value.spent_nanos, refused.value.requested_nanos, refused.value.cap_nanos) == (
        900,
        101,
        1000,
    )
    reserve(ledger, 100)
    assert ledger.spent("2026-10") == 1000


def test_no_cap_means_no_refusal(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    reserve(ledger, 5000, cap=None)
    assert ledger.spent("2026-10") == 5000


def test_months_are_separate(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    reserve(ledger, 900, month="2026-09")
    reserve(ledger, 900, month="2026-10")
    assert ledger.spent("2026-09") == ledger.spent("2026-10") == 900


def test_breakdown_groups_settled_spend(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    for feature, cost in (("ranking", 10), ("ranking", 20), ("digest", 5)):
        ledger.settle(reserve(ledger, 50, feature=feature), cost_nanos=cost, usage=TokenUsage())
    reserve(ledger, 50)  # open reservations aren't in the breakdown
    assert ledger.breakdown("2026-10") == [
        SpendLine("digest", "m", 1, 5),
        SpendLine("ranking", "m", 2, 30),
    ]


def test_spend_survives_reopening_the_file(tmp_path: Path) -> None:
    path = tmp_path / "spend.db"
    first = SqliteLedger(path)
    first.settle(reserve(first, 50), cost_nanos=30, usage=TokenUsage())
    first.close()
    assert SqliteLedger(path).spent("2026-10") == 30


def test_two_connections_cannot_overshoot_the_cap_together(tmp_path: Path) -> None:
    path = tmp_path / "spend.db"
    ledgers = [SqliteLedger(path) for _ in range(4)]
    accepted: list[int] = []
    lock = threading.Lock()

    def worker(ledger: SqliteLedger) -> None:
        for _ in range(10):
            try:
                reserve(ledger, 60)
            except CapReachedError:
                continue
            with lock:
                accepted.append(1)

    threads = [threading.Thread(target=worker, args=(ledger,)) for ledger in ledgers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(accepted) == 16  # 16 * 60 = 960 <= 1000 < 17 * 60
    assert ledgers[0].spent("2026-10") == 960


def test_unexpected_error_rolls_back(tmp_path: Path) -> None:
    ledger = SqliteLedger(tmp_path / "spend.db")
    with pytest.raises(sqlite3.IntegrityError):
        ledger.reserve(SpendRequest("2026-10", AT, "ranking", "m", None), cap_nanos=None)  # type: ignore[arg-type]
    assert ledger.spent("2026-10") == 0
    reserve(ledger, 10)
    assert ledger.spent("2026-10") == 10
