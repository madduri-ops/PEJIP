"""Shared fixtures. All data here is synthetic (policy section 10)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pejip.config import SearchConfig, load_config
from pejip.profile import CareerProfile, load_profile
from pejip.store import Store

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def config() -> SearchConfig:
    return load_config(ROOT / "config" / "search.yaml")


@pytest.fixture
def profile() -> CareerProfile:
    return load_profile(ROOT / "examples" / "profile.example.yaml")


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(f"sqlite:///{tmp_path / 'test.db'}")


def response(
    payload: Any,
    *,
    model: str = "claude-opus-5-5",
    stop_reason: str = "end_turn",
    usage: tuple[int, int] = (1000, 500),
    text: bool = True,
) -> SimpleNamespace:
    """A stand-in for an Anthropic Messages API response."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text:
        content.append(SimpleNamespace(type="text", text=body))
    tokens = SimpleNamespace(
        input_tokens=usage[0],
        output_tokens=usage[1],
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    return SimpleNamespace(content=content, model=model, usage=tokens, stop_reason=stop_reason)


class FakeMessages:
    """Replays queued responses (or exceptions) and records each request."""

    def __init__(self, *responses: Any) -> None:
        self.queue: list[Any] = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.responder: Callable[[dict[str, Any]], Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.responder(kwargs) if self.responder else self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
