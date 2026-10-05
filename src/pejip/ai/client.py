"""The single AI client: spend tracking, the monthly cap and failure handling.

Policy section 13: every AI call goes through here. Spend is recorded per feature
and model, calls are refused once the month's spend reaches the cap, and crossing
50% and each further 10% of the cap logs a ``ai_spend_threshold`` alert event.
Policy section 12: output is schema-validated before anyone uses it, and a model
error, refusal or malformed output raises :class:`AIError` instead of guessing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from pejip.ai.prompts import Prompt
from pejip.config import AIConfig
from pejip.store import Store

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
SCHEMA_ATTEMPTS = 2

T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    """The model call failed or returned unusable output."""


class AIBudgetExceeded(AIError):
    """This month's AI spend has reached the configured cap."""


class MessagesAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class AIResult(Generic[T]):
    output: T
    model: str
    prompt_id: str
    prompt_version: int
    schema_version: str
    generated_at: datetime

    def provenance(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "model": self.model,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "generated_at": self.generated_at.isoformat(),
        }


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema for structured outputs: every property required, no extras."""
    schema = model.model_json_schema()

    def tighten(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            node.pop("title", None)
            for value in node.values():
                tighten(value)
        elif isinstance(node, list):
            for value in node:
                tighten(value)

    tighten(schema)
    return schema


class AIClient:
    def __init__(
        self,
        config: AIConfig,
        store: Store,
        messages: MessagesAPI | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._config = config
        self._store = store
        self._messages = messages or anthropic.Anthropic(max_retries=2).beta.messages
        self._clock = clock

    def cost_usd(self, model: str, usage: Any) -> float:
        prices = self._config.pricing.get(model)
        if prices is None:
            in_price = max(p.input for p in self._config.pricing.values())
            out_price = max(p.output for p in self._config.pricing.values())
        else:
            in_price, out_price = prices.input, prices.output
        cache_write = getattr(usage, "cache_creation_input_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        dollars: float = (
            usage.input_tokens * in_price
            + cache_write * in_price * 1.25
            + cache_read * in_price * 0.1
            + usage.output_tokens * out_price
        )
        return dollars / 1_000_000

    def structured(
        self,
        *,
        feature: str,
        prompt: Prompt,
        content: str,
        schema: type[T],
        schema_version: str,
    ) -> AIResult[T]:
        """Run ``prompt`` on ``content`` and return output validated against ``schema``."""
        last_error = "no attempt made"
        for _ in range(SCHEMA_ATTEMPTS):
            response = self._call(feature, prompt, content, schema)
            text = next((b.text for b in response.content if b.type == "text"), None)
            if text is None:
                last_error = "response had no text block"
                continue
            try:
                output = schema.model_validate(json.loads(text))
            except (ValueError, ValidationError) as exc:
                last_error = f"malformed output: {type(exc).__name__}"
                log.warning("ai_malformed_output", extra={"feature": feature})
                continue
            return AIResult(
                output=output,
                model=str(response.model),
                prompt_id=prompt.id,
                prompt_version=prompt.version,
                schema_version=schema_version,
                generated_at=self._clock(),
            )
        raise AIError(last_error)

    def _call(self, feature: str, prompt: Prompt, content: str, schema: type[BaseModel]) -> Any:
        now = self._clock()
        before = self._store.month_spend(now)
        if before >= self._config.monthly_cap_usd:
            raise AIBudgetExceeded(f"monthly AI cap of ${self._config.monthly_cap_usd:.2f} reached")
        try:
            response = self._messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                system=prompt.text,
                messages=[{"role": "user", "content": content}],
                output_config={
                    "effort": self._config.effort,
                    "format": {"type": "json_schema", "schema": strict_schema(schema)},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            raise AIError(f"model call failed: {type(exc).__name__}") from exc
        model = str(response.model)
        cost = self.cost_usd(model, response.usage)
        self._store.record_ai_usage(
            feature, model, response.usage.input_tokens, response.usage.output_tokens, cost, now
        )
        self._alert_thresholds(before, before + cost)
        if response.stop_reason != "end_turn":
            raise AIError(f"model stopped with {response.stop_reason}")
        return response

    def _alert_thresholds(self, before: float, after: float) -> None:
        cap = self._config.monthly_cap_usd
        for pct in sorted(self._config.alert_thresholds_percent):
            level = cap * pct / 100
            if before < level <= after:
                log.warning(
                    "ai_spend_threshold",
                    extra={"percent": pct, "spend_usd": round(after, 2), "cap_usd": cap},
                )
