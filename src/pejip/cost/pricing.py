"""Claude API prices, loaded from the versioned pricing.json next to this file.

Costs are computed in integer nano-dollars (1e-9 USD) so the ledger can sum them
exactly. A model missing from the table is refused rather than guessed at.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from importlib import resources
from typing import Any

NANOS_PER_USD = 1_000_000_000
_TOKENS_PER_MILLION = 1_000_000


class UnknownModelError(KeyError):
    """The model has no entry in the pricing table, so its cost can't be bounded."""


@dataclass(frozen=True)
class ModelPrice:
    """Prices for one model, in USD per million tokens."""

    input: Decimal
    output: Decimal
    cache_write_5m: Decimal
    cache_write_1h: Decimal
    cache_read: Decimal


@dataclass(frozen=True)
class TokenUsage:
    """Token counts for one call, as reported by the API's usage object."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_read_tokens: int = 0
    web_search_requests: int = 0

    @property
    def cache_write_tokens(self) -> int:
        return self.cache_write_5m_tokens + self.cache_write_1h_tokens

    @classmethod
    def from_api(cls, usage: Any) -> TokenUsage:
        """Read an Anthropic SDK ``Usage`` object (or the equivalent dict).

        When the response doesn't break cache writes down by duration, they are
        all charged at the dearer 1-hour rate so spend is never undercounted.
        """
        cache_creation = _field(usage, "cache_creation")
        total_writes = _int(_field(usage, "cache_creation_input_tokens"))
        if cache_creation is None:
            write_5m, write_1h = 0, total_writes
        else:
            write_5m = _int(_field(cache_creation, "ephemeral_5m_input_tokens"))
            write_1h = _int(_field(cache_creation, "ephemeral_1h_input_tokens"))
        server_tools = _field(usage, "server_tool_use")
        return cls(
            input_tokens=_int(_field(usage, "input_tokens")),
            output_tokens=_int(_field(usage, "output_tokens")),
            cache_write_5m_tokens=write_5m,
            cache_write_1h_tokens=write_1h,
            cache_read_tokens=_int(_field(usage, "cache_read_input_tokens")),
            web_search_requests=_int(_field(server_tools, "web_search_requests")),
        )


class PriceTable:
    """Looks up model prices and turns token counts into nano-dollar costs."""

    def __init__(
        self,
        models: Mapping[str, ModelPrice],
        *,
        version: str,
        web_search_usd_per_request: Decimal = Decimal(0),
    ) -> None:
        self._models = dict(models)
        self.version = version
        self._web_search = web_search_usd_per_request

    @classmethod
    def load(cls) -> PriceTable:
        """Load the pricing table shipped with the package."""
        raw = resources.files(__package__).joinpath("pricing.json").read_text()
        return cls.from_dict(json.loads(raw))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PriceTable:
        models = {
            name: ModelPrice(**{key: Decimal(value) for key, value in prices.items()})
            for name, prices in data["models"].items()
        }
        return cls(
            models,
            version=data["version"],
            web_search_usd_per_request=Decimal(data.get("web_search_usd_per_request", "0")),
        )

    @property
    def models(self) -> frozenset[str]:
        return frozenset(self._models)

    def price(self, model: str) -> ModelPrice:
        try:
            return self._models[model]
        except KeyError:
            raise UnknownModelError(model) from None

    def cost_nanos(self, model: str, usage: TokenUsage) -> int:
        """Actual cost of a finished call."""
        p = self.price(model)
        usd = (
            usage.input_tokens * p.input
            + usage.output_tokens * p.output
            + usage.cache_write_5m_tokens * p.cache_write_5m
            + usage.cache_write_1h_tokens * p.cache_write_1h
            + usage.cache_read_tokens * p.cache_read
        ) / _TOKENS_PER_MILLION + usage.web_search_requests * self._web_search
        return _to_nanos(usd)

    def worst_case_nanos(self, model: str, *, input_tokens: int, max_output_tokens: int) -> int:
        """Upper bound for a call before it is made.

        Input is priced at the 1-hour cache write rate, the dearest way an input
        token can be billed, and output at ``max_output_tokens``.
        """
        p = self.price(model)
        usd = (input_tokens * p.cache_write_1h + max_output_tokens * p.output) / _TOKENS_PER_MILLION
        return _to_nanos(usd)


def nanos_to_usd(nanos: int) -> Decimal:
    return Decimal(nanos) / NANOS_PER_USD


def usd_to_nanos(usd: Decimal | int | str) -> int:
    return _to_nanos(Decimal(usd))


def _to_nanos(usd: Decimal) -> int:
    # Round up: a fraction of a nano-dollar still counts against the cap.
    return int((usd * NANOS_PER_USD).to_integral_value(rounding="ROUND_CEILING"))


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _int(value: Any) -> int:
    return int(value) if value else 0
