"""The contract a ranking scorer meets to be evaluated against the golden set."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from .golden import Context, Job


@dataclass(frozen=True)
class EvalInput:
    """Everything a scorer may see for one golden case. Labels are never passed in."""

    case_id: str
    job: Job
    context: Context
    profile: dict[str, Any]


@dataclass(frozen=True)
class Prediction:
    """A scorer's answer for one case (spec 9.29-9.34).

    ``fit`` is 0-100. ``confidence`` and ``priority`` use the manifest vocabularies,
    with priority ``EXCLUDED`` when a hard filter removes the role. ``citations`` are
    the exact posting snippets the explanation relies on (policy section 12); each
    must appear in the posting text.
    """

    fit: float
    confidence: str
    priority: str
    positive_reasons: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    citations: tuple[str, ...] = field(default_factory=tuple)


Scorer = Callable[[EvalInput], Prediction]


class ScorerLoadError(ValueError):
    def __init__(self, spec: str, reason: str) -> None:
        super().__init__(f"cannot load scorer {spec!r}: {reason}")


def load_scorer(spec: str) -> Scorer:
    """Import a scorer from ``package.module:attribute``."""
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ScorerLoadError(spec, "expected 'package.module:attribute'")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ScorerLoadError(spec, str(exc)) from exc
    scorer = getattr(module, attr, None)
    if not callable(scorer):
        raise ScorerLoadError(spec, "not callable")
    return cast(Scorer, scorer)
