from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from pejip.ai import client as client_module
from pejip.ai.client import AIClient, AIError, strict_schema
from pejip.ai.prompts import Prompt
from pejip.claude_auth import ClaudeAuthError
from pejip.config import SearchConfig
from pejip.cost import BudgetExceededError, CostGuard, SqliteLedger
from tests.conftest import NOW, FakeMessages, response

PROMPT = Prompt("TEST", 3, "Do the thing.")
API_URL = "https://api.anthropic.com/v1/messages"


class Inner(BaseModel):
    value: int = 1


class Output(BaseModel):
    name: str
    inner: Inner
    items: list[Inner]


def make(config: SearchConfig, guard: CostGuard, fake: FakeMessages) -> AIClient:
    return AIClient(config.ai, guard, messages=fake, clock=lambda: NOW)


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
    assert inner["required"] == ["value"]
    assert inner["additionalProperties"] is False
    assert "title" not in schema


def test_structured_call_settles_spend_and_records_provenance(
    config: SearchConfig, guard: CostGuard
) -> None:
    fake = FakeMessages(response(GOOD, usage=(1_000_000, 100_000)))
    result = make(config, guard, fake).structured(
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
    assert request["output_config"]["effort"] == "medium"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "fallbacks" not in request
    # $4 per million input tokens plus $20 per million output tokens.
    assert guard.month_to_date_usd() == Decimal(6)
    [line] = guard.breakdown()
    assert (line.feature, line.model) == ("test", "claude-opus-5-5")


def test_malformed_output_is_retried_once(config: SearchConfig, guard: CostGuard) -> None:
    fake = FakeMessages(response("not json"), response(GOOD))
    assert call(make(config, guard, fake)).name == "x"
    assert len(fake.calls) == 2


def test_repeated_bad_output_raises(config: SearchConfig, guard: CostGuard) -> None:
    fake = FakeMessages(response({"name": "x"}), response(GOOD, text=False))
    with pytest.raises(AIError, match="no text block"):
        call(make(config, guard, fake))
    fake = FakeMessages(response({"name": "x"}), response({"name": "y"}))
    with pytest.raises(AIError, match="malformed output"):
        call(make(config, guard, fake))


def test_refusal_and_truncation_are_errors(config: SearchConfig, guard: CostGuard) -> None:
    for reason in ("refusal", "max_tokens"):
        fake = FakeMessages(response(GOOD, stop_reason=reason))
        with pytest.raises(AIError, match=reason):
            call(make(config, guard, fake))
    assert guard.month_to_date_usd() > 0  # the failed calls were still billed


def test_api_rejection_releases_the_reservation(config: SearchConfig, guard: CostGuard) -> None:
    rejected = httpx2.Response(400, request=httpx2.Request("POST", API_URL))
    fake = FakeMessages(anthropic.BadRequestError("credit too low", response=rejected, body=None))
    with pytest.raises(AIError, match="BadRequestError 400: credit too low"):
        call(make(config, guard, fake))
    assert guard.month_to_date_usd() == 0


def test_lost_response_keeps_the_worst_case_on_the_books(
    config: SearchConfig, guard: CostGuard
) -> None:
    fake = FakeMessages(anthropic.APIConnectionError(request=httpx2.Request("POST", API_URL)))
    with pytest.raises(AIError, match="APIConnectionError"):
        call(make(config, guard, fake))
    # Up to 16,000 output tokens at $20 per million, plus the input estimate.
    assert guard.month_to_date_usd() > Decimal("0.32")


def test_budget_cap_blocks_calls_before_the_api(config: SearchConfig, tmp_path: Path) -> None:
    guard = CostGuard(SqliteLedger(tmp_path / "spend.db"), cap_usd="0.10", clock=lambda: NOW)
    fake = FakeMessages(response(GOOD))
    with pytest.raises(BudgetExceededError):
        call(make(config, guard, fake))
    assert fake.calls == []


def test_spend_alerts_come_from_the_guard(
    config: SearchConfig, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    guard = CostGuard(SqliteLedger(tmp_path / "spend.db"), cap_usd=10, clock=lambda: NOW)
    fake = FakeMessages(response(GOOD, usage=(0, 300_000)))  # $6
    with caplog.at_level(logging.WARNING):
        call(make(config, guard, fake))
    alerts = [r for r in caplog.records if r.msg == "ai_spend_threshold_crossed"]
    assert [r.__dict__["percent"] for r in alerts] == [50, 60]


def test_default_messages_client(
    config: SearchConfig, guard: CostGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    client = AIClient(config.ai, guard)
    assert client._messages is not None


def test_default_messages_client_uses_federation(
    config: SearchConfig, guard: CostGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PEJIP_CLAUDE_IDENTITY", "github-actions")
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "00000000-0000-4000-8000-000000000000")
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_test")
    monkeypatch.setenv("ANTHROPIC_SERVICE_ACCOUNT_ID", "svac_test")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://example.invalid/token")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token-not-real")
    client = AIClient(config.ai, guard)
    assert client._messages is not None


def test_default_messages_client_refuses_a_leftover_key(
    config: SearchConfig, guard: CostGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("PEJIP_CLAUDE_IDENTITY", "github-actions")
    with pytest.raises(ClaudeAuthError):
        AIClient(config.ai, guard)


def test_default_messages_client_federates_from_aws_with_a_regional_sts_client(
    config: SearchConfig, guard: CostGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PEJIP_CLAUDE_IDENTITY", "aws-sts")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("ANTHROPIC_ORGANIZATION_ID", "00000000-0000-4000-8000-000000000000")
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_test")
    monkeypatch.setenv("ANTHROPIC_SERVICE_ACCOUNT_ID", "svac_test")
    built: list[Any] = []
    real = client_module._sts_client

    def spy() -> Any:
        built.append(real())
        return built[-1]

    monkeypatch.setattr(client_module, "_sts_client", spy)
    client = AIClient(config.ai, guard)
    assert client._messages is not None
    assert built[0].meta.region_name == "us-west-2"
    assert callable(built[0].get_web_identity_token)
