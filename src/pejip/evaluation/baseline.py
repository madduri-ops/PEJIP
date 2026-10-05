"""The committed evaluation baseline and its ratchet (policy section 12).

Like the coverage baseline, the evaluation baseline only goes up: a run fails when
any metric is below its baseline value, and ``ratchet`` raises each metric to the
best value seen without ever lowering one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluate import METRICS, Report

DEFAULT_BASELINE = Path(__file__).resolve().parents[3] / "eval" / "baseline.json"


@dataclass(frozen=True)
class Regression:
    metric: str
    baseline: float
    actual: float

    def __str__(self) -> str:
        return f"{self.metric}: {self.actual:.4f} is below the baseline {self.baseline:.4f}"


class BaselineError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"{path}: 'metrics' must list exactly {', '.join(METRICS)}")


def read_baseline(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    metrics = data.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(METRICS):
        raise BaselineError(path)
    return data


# The rules a live model run must hold on every run. The other metrics move from
# run to run with the model's answers, so live runs report them and the replay of
# committed recordings gates them (see eval/README.md).
INVARIANTS = ("scored_rate", "citation_validity", "network_invariance")


def regressions(
    report: Report, baseline: dict[str, Any], metrics: tuple[str, ...] = METRICS
) -> list[Regression]:
    return [
        Regression(name, float(baseline["metrics"][name]), report.metrics[name])
        for name in metrics
        if report.metrics[name] < float(baseline["metrics"][name])
    ]


def ratchet(report: Report, baseline: dict[str, Any], scorer: str) -> tuple[dict[str, Any], bool]:
    """Return the raised baseline and whether anything went up."""
    old = baseline["metrics"]
    new = {name: max(float(old[name]), report.metrics[name]) for name in METRICS}
    changed = new != {name: float(old[name]) for name in METRICS}
    updated = {
        **baseline,
        "golden_set_version": report.golden_set_version,
        "scorer": scorer,
        "metrics": new,
    }
    return updated, changed


def write_baseline(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
