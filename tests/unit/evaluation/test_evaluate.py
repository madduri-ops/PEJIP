from __future__ import annotations

import dataclasses
import threading

import pytest

from pejip.evaluation.evaluate import METRICS, evaluate
from pejip.evaluation.golden import GoldenSet
from pejip.evaluation.scorer import EvalInput, Prediction, Scorer


def test_oracle_scores_perfectly(golden: GoldenSet, oracle: Scorer) -> None:
    report = evaluate(golden, oracle)
    assert set(report.metrics) == set(METRICS)
    assert all(value == 1.0 for value in report.metrics.values()), report.metrics
    assert all(not r.failures() for r in report.cases)
    assert report.to_dict()["cases"][0]["failures"] == []


def test_labels_are_never_passed_to_the_scorer(golden: GoldenSet, oracle: Scorer) -> None:
    seen: list[EvalInput] = []

    def spy(item: EvalInput) -> Prediction:
        seen.append(item)
        return oracle(item)

    evaluate(golden, spy)
    assert {f.name for f in dataclasses.fields(seen[0])} == {
        "case_id",
        "job",
        "context",
        "profile",
    }
    probes = sum(case.invariance_probe for case in golden.cases)
    assert len(seen) == len(golden.cases) + probes


def test_failures_count_as_unranked(golden: GoldenSet) -> None:
    def broken(item: EvalInput) -> Prediction:
        if item.case_id == "G01":
            raise TimeoutError
        return "not a prediction"  # type: ignore[return-value]

    report = evaluate(golden, broken)
    assert report.metrics["scored_rate"] == 0.0
    assert report.metrics["pairwise_order"] == 0.0
    assert report.metrics["positive_reason_recall"] == 0.0
    by_id = {r.case_id: r for r in report.cases}
    assert by_id["G01"].failures() == ["unranked: TimeoutError: "]
    assert by_id["G02"].failures() == ["unranked: scorer returned str, not Prediction"]
    assert report.to_dict()["cases"][0]["prediction"] is None


def test_network_leaking_into_fit_is_caught(golden: GoldenSet, oracle: Scorer) -> None:
    def leaky(item: EvalInput) -> Prediction:
        base = oracle(item)
        return dataclasses.replace(base, fit=min(100.0, base.fit + item.context.connections))

    report = evaluate(golden, leaky)
    assert report.metrics["network_invariance"] < 1.0
    g02 = next(r for r in report.cases if r.case_id == "G02")
    assert "fit moved to" in " ".join(g02.failures())
    assert evaluate(golden, leaky, fit_tolerance=100).metrics["network_invariance"] == 1.0


def test_probe_failure_is_not_invariant(golden: GoldenSet, oracle: Scorer) -> None:
    def flaky_probe(item: EvalInput) -> Prediction:
        if item.context.connections == 15:
            raise RuntimeError("boom")
        return oracle(item)

    report = evaluate(golden, flaky_probe)
    assert report.metrics["network_invariance"] == 0.0


def test_wrong_answers_are_reported(golden: GoldenSet) -> None:
    def wrong(item: EvalInput) -> Prediction:
        return Prediction(
            fit=101 - len(item.job.description) % 100,
            confidence="LOW",
            priority="IMMEDIATE",
            citations=("words the posting never says", " "),
        )

    report = evaluate(golden, wrong)
    assert report.metrics["citation_validity"] == 0.0
    assert report.metrics["positive_reason_recall"] == 0.0
    assert report.metrics["concern_recall"] == 0.0
    g03 = next(r for r in report.cases if r.case_id == "G03")
    failures = " ".join(g03.failures())
    for text in (
        "out of range",
        "confidence LOW",
        "priority IMMEDIATE",
        "missing reasons",
        "missing concerns",
        "citations",
    ):
        assert text in failures


def test_inverted_ranking_scores_zero_pairwise(golden: GoldenSet, oracle: Scorer) -> None:
    def inverted(item: EvalInput) -> Prediction:
        return dataclasses.replace(oracle(item), fit=100 - oracle(item).fit)

    assert evaluate(golden, inverted).metrics["pairwise_order"] == 0.0


@pytest.mark.parametrize(
    "citation",
    [
        "VICE PRESIDENT, enterprise   technology transformation",
        "own a $90M\ntransformation portfolio",
    ],
)
def test_citations_match_case_and_whitespace_insensitively(
    golden: GoldenSet, citation: str, oracle: Scorer
) -> None:
    def cites(item: EvalInput) -> Prediction:
        return dataclasses.replace(oracle(item), citations=(citation,))

    g01 = next(r for r in evaluate(golden, cites).cases if r.case_id == "G01")
    assert g01.citations_valid


def test_empty_denominators_count_as_perfect(golden: GoldenSet, oracle: Scorer) -> None:
    empty = dataclasses.replace(golden, cases=())
    report = evaluate(empty, oracle)
    assert all(value == 1.0 for value in report.metrics.values())


def test_workers_score_cases_at_once_in_golden_set_order(golden: GoldenSet, oracle: Scorer) -> None:
    # Every first call waits until four are in flight, so this only finishes if
    # four cases really are scored at the same time.
    started = threading.Barrier(4, timeout=10)
    first_calls: set[str] = set()
    lock = threading.Lock()

    def slow(item: EvalInput) -> Prediction:
        with lock:
            first = item.case_id not in first_calls
            first_calls.add(item.case_id)
        if first and len(first_calls) <= 4:
            started.wait()
        return oracle(item)

    report = evaluate(golden, slow, workers=4)
    assert [r.case_id for r in report.cases] == [c.id for c in golden.cases]
    assert report.metrics == evaluate(golden, oracle).metrics
