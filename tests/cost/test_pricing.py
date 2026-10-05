from decimal import Decimal
from types import SimpleNamespace

import pytest

from pejip.cost.pricing import (
    PriceTable,
    TokenUsage,
    UnknownModelError,
    nanos_to_usd,
    usd_to_nanos,
)


@pytest.fixture
def prices() -> PriceTable:
    return PriceTable.from_dict(
        {
            "version": "test",
            "web_search_usd_per_request": "0.01",
            "models": {
                "m": {"input": "4", "output": "20", "cache_write_5m": "5", "cache_write_1h": "8", "cache_read": "0.20"},
            },
        }
    )


def test_shipped_table_loads_and_prices_the_default_model() -> None:
    table = PriceTable.load()
    assert table.version
    assert "claude-opus-5-5" in table.models
    assert table.price("claude-opus-5-5").output == Decimal("20.00")


def test_every_shipped_model_has_every_rate() -> None:
    table = PriceTable.load()
    for model in table.models:
        price = table.price(model)
        assert price.output > price.input > price.cache_read > 0
        assert price.cache_write_1h > price.cache_write_5m > price.input


def test_unknown_model_is_refused(prices: PriceTable) -> None:
    with pytest.raises(UnknownModelError):
        prices.price("not-a-model")


def test_cost_of_one_million_tokens_each(prices: PriceTable) -> None:
    usage = TokenUsage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_write_5m_tokens=1_000_000,
        cache_write_1h_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        web_search_requests=3,
    )
    assert nanos_to_usd(prices.cost_nanos("m", usage)) == Decimal("37.23")


def test_fractions_of_a_nano_dollar_round_up(prices: PriceTable) -> None:
    # One cache-read token costs 0.2 micro-dollars = 200 nano-dollars exactly;
    # one token at a rate that leaves a remainder must round up, not down.
    odd = PriceTable.from_dict(
        {"version": "t", "models": {"m": {k: "0.0000001" for k in ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")}}}
    )
    assert odd.cost_nanos("m", TokenUsage(input_tokens=1)) == 1
    assert prices.cost_nanos("m", TokenUsage(cache_read_tokens=1)) == 200


def test_worst_case_prices_input_at_the_one_hour_write_rate(prices: PriceTable) -> None:
    nanos = prices.worst_case_nanos("m", input_tokens=1_000_000, max_output_tokens=500_000)
    assert nanos_to_usd(nanos) == Decimal(8 + 10)


def test_usage_from_sdk_object_with_ttl_breakdown() -> None:
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=20,
        cache_creation_input_tokens=7,
        cache_creation=SimpleNamespace(ephemeral_5m_input_tokens=3, ephemeral_1h_input_tokens=4),
        cache_read_input_tokens=5,
        server_tool_use=SimpleNamespace(web_search_requests=2),
    )
    assert TokenUsage.from_api(usage) == TokenUsage(10, 20, 3, 4, 5, 2)


def test_usage_without_breakdown_charges_writes_at_one_hour_rate() -> None:
    usage = {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 7, "cache_read_input_tokens": None}
    tokens = TokenUsage.from_api(usage)
    assert tokens == TokenUsage(input_tokens=10, output_tokens=20, cache_write_1h_tokens=7)
    assert tokens.cache_write_tokens == 7


def test_usage_from_none_is_empty() -> None:
    assert TokenUsage.from_api(None) == TokenUsage()


def test_usd_round_trip() -> None:
    assert usd_to_nanos("100") == 100_000_000_000
    assert nanos_to_usd(1) == Decimal("1E-9")
