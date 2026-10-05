"""The AI cost guard: every Claude call reserves budget here before it is made.

Usage::

    guard = CostGuard(SqliteLedger(path), metrics=CloudWatchSpendMetrics(cloudwatch))
    with guard.reserve(
        feature="ranking", model=MODEL, input_tokens=est, max_output_tokens=2048
    ) as call:
        response = client.messages.create(model=MODEL, max_tokens=2048, ...)
        call.settle(response.usage)

``reserve`` raises ``BudgetExceededError`` before the API is called when the month's
spend plus the call's worst-case cost would pass the cap (policy section 13).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Protocol

from .ledger import CapReachedError, Ledger, SpendLine, SpendRequest
from .pricing import PriceTable, TokenUsage, nanos_to_usd, usd_to_nanos

DEFAULT_CAP_USD = Decimal(100)
# Policy section 13: alert at 50% of the cap and every 10% after.
ALERT_PERCENTS: tuple[int, ...] = (50, 60, 70, 80, 90, 100)

# Feature names end up in the ledger, logs and metric dimensions, so they are
# restricted to short identifiers that can't carry personal data.
_FEATURE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

_BAD_CAP = "cap_usd must be positive"
_BAD_FEATURE = f"feature must match {_FEATURE.pattern}"
_BAD_TOKENS = "token counts must not be negative"
_CLOSED = "reservation already settled or released"

log = logging.getLogger("pejip.cost")


class BudgetExceededError(Exception):
    """The call would take this month's AI spend past the cap."""

    def __init__(
        self, *, month: str, spent_usd: Decimal, requested_usd: Decimal, cap_usd: Decimal
    ) -> None:
        super().__init__(
            f"AI spend cap reached for {month}: spent ${spent_usd:.2f} of ${cap_usd:.2f},"
            f" call needs up to ${requested_usd:.4f}"
        )
        self.month = month
        self.spent_usd = spent_usd
        self.requested_usd = requested_usd
        self.cap_usd = cap_usd


class SpendMetrics(Protocol):
    def publish(
        self,
        *,
        month_to_date_usd: Decimal,
        feature: str,
        model: str,
        call_usd: Decimal,
    ) -> None: ...  # pragma: no cover


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CostGuard:
    """Enforces the monthly AI spend cap and reports spend as it happens."""

    def __init__(
        self,
        ledger: Ledger,
        *,
        cap_usd: Decimal | int | str = DEFAULT_CAP_USD,
        prices: PriceTable | None = None,
        metrics: SpendMetrics | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._cap_nanos = usd_to_nanos(cap_usd)
        if self._cap_nanos <= 0:
            raise ValueError(_BAD_CAP)
        self._ledger = ledger
        self._prices = prices or PriceTable.load()
        self._metrics = metrics
        self._clock = clock

    @property
    def cap_usd(self) -> Decimal:
        return nanos_to_usd(self._cap_nanos)

    def month(self) -> str:
        """The current budget month, ``YYYY-MM`` in UTC."""
        return self._clock().astimezone(UTC).strftime("%Y-%m")

    def month_to_date_usd(self) -> Decimal:
        """Spend this month, counting calls still in flight at their worst case."""
        return nanos_to_usd(self._ledger.spent(self.month()))

    def breakdown(self) -> list[SpendLine]:
        """This month's settled spend per feature and model."""
        return self._ledger.breakdown(self.month())

    def reserve(
        self,
        *,
        feature: str,
        model: str,
        input_tokens: int,
        max_output_tokens: int,
        essential: bool = False,
    ) -> Reservation:
        """Reserve the worst-case cost of a call, or raise ``BudgetExceededError``.

        ``input_tokens`` is the caller's estimate of the prompt size (a high
        estimate is safer; ``messages.count_tokens`` gives an exact one).
        ``essential`` calls are recorded but not refused at the cap; nothing
        should set it without a reason written next to the call.
        """
        if not _FEATURE.match(feature):
            raise ValueError(_BAD_FEATURE)
        if input_tokens < 0 or max_output_tokens < 0:
            raise ValueError(_BAD_TOKENS)
        amount = self._prices.worst_case_nanos(
            model, input_tokens=input_tokens, max_output_tokens=max_output_tokens
        )
        now = self._clock()
        month = now.astimezone(UTC).strftime("%Y-%m")
        request = SpendRequest(month, now, feature, model, amount, essential)
        try:
            reservation_id = self._ledger.reserve(
                request, cap_nanos=None if essential else self._cap_nanos
            )
        except CapReachedError as exc:
            log.warning(
                "ai_call_refused",
                extra={
                    "event": "ai_call_refused",
                    "feature": feature,
                    "model": model,
                    "month": month,
                },
            )
            raise BudgetExceededError(
                month=month,
                spent_usd=nanos_to_usd(exc.spent_nanos),
                requested_usd=nanos_to_usd(exc.requested_nanos),
                cap_usd=self.cap_usd,
            ) from None
        return Reservation(self, reservation_id, request)

    def _settle(self, reservation: Reservation, usage: TokenUsage, cost_nanos: int) -> None:
        before = self._ledger.spent(reservation.month)
        self._ledger.settle(reservation.id, cost_nanos=cost_nanos, usage=usage)
        after = self._ledger.spent(reservation.month)
        # Reserved amounts already counted in `before`, so compare against what
        # spend would have been without this call's reservation.
        self._report(
            reservation,
            previous=before - reservation.reserved_nanos,
            current=after,
            cost_nanos=cost_nanos,
        )

    def _report(
        self, reservation: Reservation, *, previous: int, current: int, cost_nanos: int
    ) -> None:
        for percent in ALERT_PERCENTS:
            threshold = self._cap_nanos * percent // 100
            if previous < threshold <= current:
                log.warning(
                    "ai_spend_threshold_crossed",
                    extra={
                        "event": "ai_spend_threshold_crossed",
                        "percent": percent,
                        "month": reservation.month,
                        "month_to_date_usd": str(nanos_to_usd(current)),
                        "cap_usd": str(self.cap_usd),
                    },
                )
        if self._metrics is None:
            return
        try:
            self._metrics.publish(
                month_to_date_usd=nanos_to_usd(current),
                feature=reservation.feature,
                model=reservation.model,
                call_usd=nanos_to_usd(cost_nanos),
            )
        except Exception:
            # A metrics outage must not stop the pipeline, but it does silence
            # the email alerts, so it is logged as an error.
            log.exception("ai_spend_metrics_failed", extra={"event": "ai_spend_metrics_failed"})


class Reservation:
    """A reserved call. Settle it with the response's usage, or release it if
    the API rejected the request and nothing was billed.

    Leaving the ``with`` block without either keeps the worst-case amount on the
    books, since a call that failed part way may still have been billed.
    """

    def __init__(self, guard: CostGuard, reservation_id: int, request: SpendRequest) -> None:
        self._guard = guard
        self.id = reservation_id
        self.month = request.month
        self.feature = request.feature
        self.model = request.model
        self.reserved_nanos = request.amount_nanos
        self._closed = False

    @property
    def reserved_usd(self) -> Decimal:
        return nanos_to_usd(self.reserved_nanos)

    def settle(self, usage: Any) -> Decimal:
        """Record the actual cost from the API's ``usage`` and return it in USD."""
        self._check_open()
        tokens = TokenUsage.from_api(usage)
        cost = self._guard._prices.cost_nanos(self.model, tokens)
        self._closed = True
        self._guard._settle(self, tokens, cost)
        return nanos_to_usd(cost)

    def release(self) -> None:
        """Drop the reservation: the request failed and nothing was billed."""
        self._check_open()
        self._closed = True
        self._guard._ledger.release(self.id)

    def __enter__(self) -> Reservation:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._closed:
            self.settle_at_reserved()

    def settle_at_reserved(self) -> None:
        """Book the worst-case amount as the cost, when the real usage is unknown."""
        self._check_open()
        self._closed = True
        self._guard._settle(self, TokenUsage(), self.reserved_nanos)

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError(_CLOSED)
