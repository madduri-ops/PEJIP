from __future__ import annotations

import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from pejip.ai.client import (
    FALLBACK_BETA,
    AIBudgetExceeded,
    AIClient,
    AIError,
    strict_schema,
)
from pejip.ai.prompts import Prompt
from pejip.config import SearchConfig
from pejip.store import Store
from tests.conftest import NOW, FakeMessages, response

PROMPT = Prompt("TEST", 3, "Do the thing.")


class Inner(BaseModel):
    value: int = 1


class Output(BaseModel):
    name: str
    inner: Inner
    items: list[Inner]


def make(config: SearchConfig, store: Store, fake: FakeMessages) -> AIClient:
    return AIClient(config.ai, store, messages=fake, clock=lambda: NOW)


def call(client: AIClient) -> Output:
    result = client.structured(
        feature="test", prompt=PROMPT, content="input", schema=Output, schema_version="s1"
    )
    assert result.provenance()["prompt_version"] == 3
    return result.output


GOOD = {"name": "x", "inner": {"value": 2}, "items": []}


def test_strict_schema_requires_every_property_and_forbids_extras() -> None:
    schema = strict_schema(Output)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["name", "inner", "items"]
    inner = schema["$defs"]["Inner"]
    assert inner["required"] == ["value"] and inner["additionalProperties"] is False
    assert "title" not in schema


def test_structured_call_records_spend_and_provenance(config: SearchConfig, store: Store) -> None:
    fake = FakeMessages(response(GOOD, input_tokens=1_000_000, output_tokens=100_000))
    client = make(config, store, fake)
    result = client.structured(
        feature="test", prompt=PROMPT, content="input", schema=Output, schema_version="s1"
    )
    assert result.output.inner.value == 2
    assert result.provenance() == {
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "prompt_id": "TEST",
        "prompt_version": 3,
        "schema_version": "s1",
        "generated_at": NOW.isoformat(),
    }
    request = fake.calls[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == "Do the thing."
    assert request["betas"] == [FALLBACK_BETA] and request["fallbacks"] == "default"
    assert request["output_config"]["effort"] == "medium"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert store.month_spend(NOW) == pytest.approx(4.0 + 2.0)


def test_cost_uses_cache_rates_and_charges_unknown_models_the_top_price(
    config: SearchConfig, store: Store
) -> None:
    client = make(config, store, FakeMessages())
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=0,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert client.cost_usd("claude-opus-5-5", usage) == pytest.approx(4 + 5 + 0.4)
    plain = SimpleNamespace(input_tokens=0, output_tokens=1_000_000)
    assert client.cost_usd("some-new-model", plain) == pytest.approx(50.0)


def test_malformed_output_is_retried_once(config: SearchConfig, store: Store) -> None:
    fake = FakeMessages(response("not json"), response(GOOD))
    assert call(make(config, store, fake)).name == "x"
    assert len(fake.calls) == 2


def test_repeated_bad_output_raises(config: SearchConfig, store: Store) -> None:
    fake = FakeMessages(response({"name": "x"}), response(GOOD, text=False))
    with pytest.raises(AIError, match="no text block"):
        call(make(config, store, fake))
    fake = FakeMessages(response({"name": "x"}), response({"name": "y"}))
    with pytest.raises(AIError, match="malformed output"):
        call(make(config, store, fake))


def test_refusal_and_truncation_are_errors(config: SearchConfig, store: Store) -> None:
    for reason in ("refusal", "max_tokens"):
        fake = FakeMessages(response(GOOD, stop_reason=reason))
        with pytest.raises(AIError, match=reason):
            call(make(config, store, fake))
    assert store.month_spend(NOW) > 0  # the failed calls were still billed and recorded


def test_api_errors_are_wrapped(config: SearchConfig, store: Store) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake = FakeMessages(anthropic.APIConnectionError(request=request))
    with pytest.raises(AIError, match="APIConnectionError"):
        call(make(config, store, fake))


def test_budget_cap_blocks_calls(config: SearchConfig, store: Store) -> None:
    store.record_ai_usage("other", "m", 0, 0, 100.0, NOW)
    fake = FakeMessages(response(GOOD))
    with pytest.raises(AIBudgetExceeded):
        call(make(config, store, fake))
    assert fake.calls == []


def test_threshold_alerts(
    config: SearchConfig, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    store.record_ai_usage("other", "m", 0, 0, 45.0, NOW)
    fake = FakeMessages(response(GOOD, input_tokens=0, output_tokens=1_000_000))  # $20
    with caplog.at_level(logging.WARNING):
        call(make(config, store, fake))
    alerts = [r for r in caplog.records if r.msg == "ai_spend_threshold"]
    assert [r.__dict__["percent"] for r in alerts] == [50, 60]


def test_default_messages_client(
    config: SearchConfig, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    client = AIClient(config.ai, store)
    assert client._messages is not None
