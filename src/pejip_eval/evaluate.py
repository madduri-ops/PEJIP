"""Run a scorer over the golden set and measure it (spec 9.43, 17.33)."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from .golden import Case, Context, GoldenSet
from .scorer import EvalInput, Prediction, Scorer

# Every metric is a rate in [0, 1] where higher is better, so one ratchet rule
# ("never below the baseline") covers all of them.
METRICS = (
    "scored_rate",
    "fit_in_range",
    "confidence_match",
    "priority_match",
    "positive_reason_recall",
    "concern_recall",
    "pairwise_order",
    "citation_validity",
    "network_invariance",
)

# Network probes swap the case's network for this one; Fit must not move (spec 9.8).
PROBE_CONNECTIONS = 15
PROBE_STRONG = 6

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


@dataclass
class CaseResult:
    case_id: str
    prediction: Prediction | None
    error: str | None = None
    fit_in_range: bool = False
    confidence_match: bool = False
    priority_match: bool = False
    missing_reasons: tuple[str, ...] = ()
    missing_concerns: tuple[str, ...] = ()
    bad_citations: tuple[str, ...] = ()
    citations_valid: bool = False
    probe_fit: float | None = None
    network_invariant: bool | None = None

    def failures(self) -> list[str]:
        if self.prediction is None:
            return [f"unranked: {self.error}"]
        out = []
        if not self.fit_in_range:
            out.append(f"fit {self.prediction.fit:g} out of range")
        if not self.confidence_match:
            out.append(f"confidence {self.prediction.confidence}")
        if not self.priority_match:
            out.append(f"priority {self.prediction.priority}")
        if self.missing_reasons:
            out.append("missing reasons " + ",".join(self.missing_reasons))
        if self.missing_concerns:
            out.append("missing concerns " + ",".join(self.missing_concerns))
        if not self.citations_valid:
            out.append("citations missing or not in posting")
        if self.network_invariant is False:
            out.append(f"fit moved to {self.probe_fit:g} when network changed")
        return out


@dataclass
class Report:
    golden_set_version: str
    metrics: dict[str, float]
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "golden_set_version": self.golden_set_version,
            "metrics": self.metrics,
            "cases": [
                {
                    "case_id": r.case_id,
                    "prediction": dataclasses.asdict(r.prediction)
                    if r.prediction
                    else None,
                    "failures": r.failures(),
                }
                for r in self.cases
            ],
        }


def _call(scorer: Scorer, item: EvalInput) -> tuple[Prediction | None, str | None]:
    # Policy 12: a failed ranking is shown as unranked, never as a made-up result.
    try:
        prediction = scorer(item)
    except Exception as exc:  # noqa: BLE001 - any scorer failure counts as unranked
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(prediction, Prediction):
        return None, f"scorer returned {type(prediction).__name__}, not Prediction"
    return prediction, None


def _judge(case: Case, prediction: Prediction) -> CaseResult:
    exp = case.expected
    posting = _norm(" ".join((case.job.title, case.job.description)))
    bad = tuple(
        c for c in prediction.citations if not c.strip() or _norm(c) not in posting
    )
    return CaseResult(
        case_id=case.id,
        prediction=prediction,
        fit_in_range=exp.fit_min <= prediction.fit <= exp.fit_max,
        confidence_match=prediction.confidence in exp.confidence,
        priority_match=prediction.priority in exp.priority,
        missing_reasons=tuple(
            r for r in exp.positive_reasons if r not in prediction.positive_reasons
        ),
        missing_concerns=tuple(c for c in exp.concerns if c not in prediction.concerns),
        bad_citations=bad,
        citations_valid=bool(prediction.citations) and not bad,
    )


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 4) if total else 1.0


def evaluate(
    golden: GoldenSet, scorer: Scorer, *, fit_tolerance: float = 0.0
) -> Report:
    results: list[CaseResult] = []
    for case in golden.cases:
        item = EvalInput(case.id, case.job, case.context, golden.profile)
        prediction, error = _call(scorer, item)
        if prediction is None:
            results.append(CaseResult(case.id, None, error=error))
            continue
        result = _judge(case, prediction)
        if case.invariance_probe:
            probe, _ = _call(
                scorer,
                dataclasses.replace(
                    item, context=Context(PROBE_CONNECTIONS, PROBE_STRONG)
                ),
            )
            result.probe_fit = probe.fit if probe else None
            result.network_invariant = (
                probe is not None and abs(probe.fit - prediction.fit) <= fit_tolerance
            )
        results.append(result)

    by_id = {case.id: case for case in golden.cases}
    scored = [r for r in results if r.prediction is not None]
    expected_reasons = sum(
        len(by_id[r.case_id].expected.positive_reasons) for r in results
    )
    expected_concerns = sum(len(by_id[r.case_id].expected.concerns) for r in results)
    found_reasons = sum(
        len(by_id[r.case_id].expected.positive_reasons) - len(r.missing_reasons)
        for r in scored
    )
    found_concerns = sum(
        len(by_id[r.case_id].expected.concerns) - len(r.missing_concerns)
        for r in scored
    )

    # Ranking quality: for every pair whose labelled Fit ranges do not overlap, the
    # scorer must order them the same way. An unranked case loses all its pairs.
    pairs = ordered = 0
    for a, b in combinations(results, 2):
        ea, eb = by_id[a.case_id].expected, by_id[b.case_id].expected
        if ea.fit_max < eb.fit_min:
            low, high = a, b
        elif eb.fit_max < ea.fit_min:
            low, high = b, a
        else:
            continue
        pairs += 1
        if (
            low.prediction
            and high.prediction
            and low.prediction.fit < high.prediction.fit
        ):
            ordered += 1

    probes = [r for r in results if by_id[r.case_id].invariance_probe]
    metrics = {
        "scored_rate": _rate(len(scored), len(results)),
        "fit_in_range": _rate(sum(r.fit_in_range for r in results), len(results)),
        "confidence_match": _rate(
            sum(r.confidence_match for r in results), len(results)
        ),
        "priority_match": _rate(sum(r.priority_match for r in results), len(results)),
        "positive_reason_recall": _rate(found_reasons, expected_reasons),
        "concern_recall": _rate(found_concerns, expected_concerns),
        "pairwise_order": _rate(ordered, pairs),
        "citation_validity": _rate(
            sum(r.citations_valid for r in results), len(results)
        ),
        "network_invariance": _rate(
            sum(bool(r.network_invariant) for r in probes), len(probes)
        ),
    }
    return Report(golden_set_version=golden.version, metrics=metrics, cases=results)
