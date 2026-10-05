import logging
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pejip.cost import (
    ALERT_PERCENTS,
    BudgetExceededError,
    CostGuard,
    PriceTable,
    SqliteLedger,
    UnknownModelError,
)

RATES = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
# $1 per million input or output tokens keeps the arithmetic readable:
# 1,000,000 tokens = $1.
PRICES = PriceTable.from_dict(
    {
        "version": "t",
        "models": {
            "m": dict.fromkeys(
                ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read"), "1"
            )
        },
    }
)
M = 1_000_000


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 31, 23, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class RecordingMetrics:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def usage(output_millions: float) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=0, output_tokens=int(output_millions * M))


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def metrics() -> RecordingMetrics:
    return RecordingMetrics()


@pytest.fixture
def guard(tmp_path: Path, clock: Clock, metrics: RecordingMetrics) -> CostGuard:
    return CostGuard(
        SqliteLedger(tmp_path / "spend.db"), cap_usd=10, prices=PRICES, metrics=metrics, clock=clock
    )


def test_policy_defaults() -> None:
    assert ALERT_PERCENTS == (50, 60, 70, 80, 90, 100)
    guard = CostGuard(SqliteLedger(":memory:"))
    assert guard.cap_usd == Decimal(100)


def test_cap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        CostGuard(SqliteLedger(":memory:"), cap_usd=0)


def test_settled_call_records_actual_cost(guard: CostGuard, metrics: RecordingMetrics) -> None:
    with guard.reserve(
        feature="ranking", model="m", input_tokens=M, max_output_tokens=2 * M
    ) as call:
        assert call.reserved_usd == Decimal(3)
        assert guard.month_to_date_usd() == Decimal(3)
        assert call.settle({"input_tokens": M, "output_tokens": M // 2}) == Decimal("1.5")
    assert guard.month_to_date_usd() == Decimal("1.5")
    [line] = guard.breakdown()
    assert (line.feature, line.model, line.calls) == ("ranking", "m", 1)
    assert metrics.calls == [
        {
            "month_to_date_usd": Decimal("1.5"),
            "feature": "ranking",
            "model": "m",
            "call_usd": Decimal("1.5"),
        }
    ]


def test_call_that_would_pass_the_cap_is_refused_before_it_is_made(
    guard: CostGuard, caplog: pytest.LogCaptureFixture
) -> None:
    with guard.reserve(
        feature="ranking", model="m", input_tokens=0, max_output_tokens=9 * M
    ) as call:
        call.settle(usage(9))
    with (
        caplog.at_level(logging.WARNING, logger="pejip.cost"),
        pytest.raises(BudgetExceededError) as refused,
    ):
        guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=2 * M)
    assert refused.value.spent_usd == Decimal(9)
    assert refused.value.requested_usd == Decimal(2)
    assert refused.value.cap_usd == Decimal(10)
    assert refused.value.month == "2026-10"
    assert "cap reached" in str(refused.value)
    assert [r.message for r in caplog.records if r.message == "ai_call_refused"] == [
        "ai_call_refused"
    ]
    # A call that still fits goes through.
    guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=M).release()


def test_essential_call_is_recorded_but_not_refused(guard: CostGuard) -> None:
    with guard.reserve(
        feature="ranking", model="m", input_tokens=0, max_output_tokens=12 * M, essential=True
    ) as call:
        call.settle(usage(11))
    assert guard.month_to_date_usd() == Decimal(11)
    with pytest.raises(BudgetExceededError):
        guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=1)


def test_cap_resets_at_the_start_of_the_month(guard: CostGuard, clock: Clock) -> None:
    with guard.reserve(
        feature="ranking", model="m", input_tokens=0, max_output_tokens=10 * M
    ) as call:
        call.settle(usage(10))
    with pytest.raises(BudgetExceededError):
        guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=1)
    clock.now += timedelta(hours=1)  # 2026-11-01 00:00 UTC
    assert guard.month() == "2026-11"
    assert guard.month_to_date_usd() == 0
    guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=M).release()


def test_month_is_taken_in_utc(guard: CostGuard, clock: Clock) -> None:
    clock.now = datetime(2026, 10, 31, 20, 0, tzinfo=timezone(timedelta(hours=-8)))
    assert guard.month() == "2026-11"


def test_released_call_costs_nothing(guard: CostGuard, metrics: RecordingMetrics) -> None:
    with guard.reserve(feature="ranking", model="m", input_tokens=M, max_output_tokens=M) as call:
        call.release()
    assert guard.month_to_date_usd() == 0
    assert metrics.calls == []


def test_leaving_without_settling_books_the_worst_case(guard: CostGuard) -> None:
    with (
        pytest.raises(TimeoutError),
        guard.reserve(feature="ranking", model="m", input_tokens=M, max_output_tokens=M),
    ):
        raise TimeoutError
    assert guard.month_to_date_usd() == Decimal(2)
    assert guard.breakdown()[0].cost_nanos == 2_000_000_000


def test_reservation_closes_once(guard: CostGuard) -> None:
    call = guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=1)
    call.release()
    for action in (call.release, call.settle_at_reserved, lambda: call.settle(usage(0))):
        with pytest.raises(RuntimeError, match="already settled"):
            action()


@pytest.mark.parametrize(
    "feature", ["", "Ranking", "has space", "x" * 65, "role for jane@example.com"]
)
def test_feature_names_must_be_plain_identifiers(guard: CostGuard, feature: str) -> None:
    with pytest.raises(ValueError, match="feature must match"):
        guard.reserve(feature=feature, model="m", input_tokens=0, max_output_tokens=1)


def test_negative_token_counts_are_rejected(guard: CostGuard) -> None:
    with pytest.raises(ValueError, match="negative"):
        guard.reserve(feature="ranking", model="m", input_tokens=-1, max_output_tokens=1)


def test_unknown_model_is_refused_before_anything_is_reserved(guard: CostGuard) -> None:
    with pytest.raises(UnknownModelError):
        guard.reserve(feature="ranking", model="mystery", input_tokens=1, max_output_tokens=1)
    assert guard.month_to_date_usd() == 0


def test_threshold_logged_once_per_crossing(
    guard: CostGuard, caplog: pytest.LogCaptureFixture
) -> None:
    def spend(millions: float) -> None:
        with guard.reserve(
            feature="ranking", model="m", input_tokens=0, max_output_tokens=int(millions * M)
        ) as call:
            call.settle(usage(millions))

    with caplog.at_level(logging.WARNING, logger="pejip.cost"):
        spend(4.9)  # 49%: nothing
        spend(0.1)  # exactly 50%
        spend(2.5)  # 75%: crosses 60 and 70
        spend(0.1)  # 76%: nothing new
        spend(2.4)  # 100%: crosses 80, 90 and 100
    crossed = [r.percent for r in caplog.records if r.message == "ai_spend_threshold_crossed"]  # type: ignore[attr-defined]
    assert crossed == [50, 60, 70, 80, 90, 100]
    assert caplog.records[0].month_to_date_usd == "5"  # type: ignore[attr-defined]


def test_metrics_failure_is_logged_and_does_not_break_the_call(
    tmp_path: Path, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    class Broken:
        def publish(self, **_kwargs: Any) -> None:
            raise ConnectionError

    guard = CostGuard(
        SqliteLedger(tmp_path / "s.db"), cap_usd=10, prices=PRICES, metrics=Broken(), clock=clock
    )
    with (
        caplog.at_level(logging.ERROR, logger="pejip.cost"),
        guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=M) as call,
    ):
        assert call.settle(usage(1)) == Decimal(1)
    assert [r.message for r in caplog.records] == ["ai_spend_metrics_failed"]


def test_works_without_metrics(tmp_path: Path, clock: Clock) -> None:
    guard = CostGuard(SqliteLedger(tmp_path / "s.db"), cap_usd=10, prices=PRICES, clock=clock)
    with guard.reserve(feature="ranking", model="m", input_tokens=0, max_output_tokens=M) as call:
        call.settle(usage(1))
    assert guard.month_to_date_usd() == Decimal(1)


def test_default_clock_is_utc() -> None:
    guard = CostGuard(SqliteLedger(":memory:"), prices=PRICES)
    assert guard.month() == datetime.now(UTC).strftime("%Y-%m")


def test_spend_records_hold_no_prompt_or_response_text(tmp_path: Path, clock: Clock) -> None:
    path = tmp_path / "spend.db"
    guard = CostGuard(SqliteLedger(path), cap_usd=10, prices=PRICES, clock=clock)
    with guard.reserve(feature="ranking", model="m", input_tokens=10, max_output_tokens=10) as call:
        call.settle(
            {"input_tokens": 10, "output_tokens": 10, "content": "Jane Doe, VP Engineering"}
        )
    assert b"Jane" not in path.read_bytes()
