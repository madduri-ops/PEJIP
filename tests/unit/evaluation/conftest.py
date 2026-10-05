from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pejip.evaluation.golden import DEFAULT_GOLDEN_DIR, GoldenSet, load_golden_set
from pejip.evaluation.scorer import EvalInput, Prediction, Scorer


@pytest.fixture(scope="session")
def golden() -> GoldenSet:
    return load_golden_set()


@pytest.fixture
def golden_copy(tmp_path: Path) -> Path:
    """A writable copy of the real golden set, for tests that break it on purpose."""
    target = tmp_path / "golden"
    shutil.copytree(DEFAULT_GOLDEN_DIR, target)
    return target


def oracle_for(golden: GoldenSet) -> Scorer:
    """A scorer that answers straight from the labels: the best possible result."""
    by_id = {case.id: case for case in golden.cases}

    def score(item: EvalInput) -> Prediction:
        exp = by_id[item.case_id].expected
        return Prediction(
            fit=(exp.fit_min + exp.fit_max) / 2,
            confidence=exp.confidence[0],
            priority=exp.priority[0],
            positive_reasons=exp.positive_reasons,
            concerns=exp.concerns,
            citations=(item.job.title,),
        )

    return score


@pytest.fixture
def oracle(golden: GoldenSet) -> Scorer:
    return oracle_for(golden)
