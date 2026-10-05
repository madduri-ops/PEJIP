"""The single AI client: the spend cap, structured output and failure handling.

Policy section 13: every model call reserves its worst-case cost with the
:class:`~pejip.cost.CostGuard` first, which refuses the call with
:class:`~pejip.cost.BudgetExceededError` when it would pass the monthly cap, then
settles the actual usage and raises the spend alerts.
Policy section 12: output is schema-validated before anyone uses it, and a model
error, refusal or malformed output raises :class:`AIError` instead of guessing.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import anthropic
from pydantic import BaseModel, ValidationError

from pejip import claude_auth
from pejip.ai.prompts import Prompt
from pejip.config import AIConfig
from pejip.cost import CostGuard

log = logging.getLogger(__name__)

SCHEMA_ATTEMPTS = 2
# A deliberately high estimate of tokens per character of request text, so the
# reservation errs above the real input cost (English runs nearer 0.25).
INPUT_TOKENS_PER_CHAR = 0.5


class AIError(Exception):
    """The model call failed or returned unusable output."""


class ModelCallError(AIError):
    """The API rejected or failed the request."""

    def __init__(self, cause: Exception) -> None:
        detail = type(cause).__name__
        if isinstance(cause, anthropic.APIStatusError):
            # The API's own explanation (a bad parameter, an exhausted credit
            # balance); it describes the request, never the posting or profile.
            detail += f" {cause.status_code}: {cause.message}"
        super().__init__(f"model call failed: {detail}")


class IncompleteOutputError(AIError):
    """The model stopped before finishing its answer."""

    def __init__(self, stop_reason: object) -> None:
        super().__init__(f"model stopped with {stop_reason}")


class MessagesAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class AIResult[T: BaseModel]:
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


def _sts_client() -> claude_auth.StsClient:
    """A regional STS client (GetWebIdentityToken has no global endpoint)."""
    import boto3  # noqa: PLC0415  (only runs on AWS, with PEJIP_CLAUDE_IDENTITY=aws-sts)

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        msg = "AWS_REGION is not set; STS needs a regional endpoint"
        raise claude_auth.ClaudeAuthError(msg)
    return cast(claude_auth.StsClient, boto3.client("sts", region_name=region))


def _credentials() -> anthropic.WorkloadIdentityCredentials | None:
    # Keyless in CI and on ECS (ADR-0004); a developer's own login when
    # PEJIP_CLAUDE_IDENTITY is unset.
    on_aws = os.environ.get(claude_auth.IDENTITY_SOURCE_ENV) == claude_auth.AWS_STS
    kwargs = claude_auth.federation_credentials(os.environ, sts=_sts_client() if on_aws else None)
    return anthropic.WorkloadIdentityCredentials(**kwargs) if kwargs else None


class AIClient:
    def __init__(
        self,
        config: AIConfig,
        guard: CostGuard,
        messages: MessagesAPI | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._config = config
        self._guard = guard
        self._messages = (
            messages or anthropic.Anthropic(max_retries=2, credentials=_credentials()).messages
        )
        self._clock = clock

    def structured[T: BaseModel](
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
        json_schema = strict_schema(schema)
        request_chars = len(prompt.text) + len(content) + len(json.dumps(json_schema))
        with self._guard.reserve(
            feature=feature,
            model=self._config.model,
            input_tokens=int(request_chars * INPUT_TOKENS_PER_CHAR),
            max_output_tokens=self._config.max_tokens,
        ) as call:
            try:
                response = self._messages.create(
                    model=self._config.model,
                    max_tokens=self._config.max_tokens,
                    system=prompt.text,
                    messages=[{"role": "user", "content": content}],
                    output_config={
                        "effort": self._config.effort,
                        "format": {"type": "json_schema", "schema": json_schema},
                    },
                )
            except anthropic.APIStatusError as exc:
                # The API answered with an error, so nothing was billed.
                call.release()
                raise ModelCallError(exc) from exc
            except anthropic.APIError as exc:
                # No answer (timeout, connection lost): it may have been billed,
                # so the guard keeps the worst-case amount on the books.
                raise ModelCallError(exc) from exc
            call.settle(response.usage)
        if response.stop_reason != "end_turn":
            raise IncompleteOutputError(response.stop_reason)
        return response
