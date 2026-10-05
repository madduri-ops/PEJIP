"""Coverage gate and ratchet (docs/BUILD_POLICY.md section 1).

Reads a combined `coverage json` report and fails when line coverage is below 100%
or branch coverage is below the committed baseline (never below the 95% policy floor).
With --base-baseline, it also fails when the committed baseline is lower than the
base branch's, so the baseline can only go up. With --update, it raises the baseline
to the measured values.
"""

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

POLICY_LINE = 100.0
POLICY_BRANCH = 95.0


def _percent(covered: int, total: int) -> float:
    """Coverage as a percentage, floored to two decimals so rounding never passes a gate."""
    if total == 0:
        return 100.0
    return math.floor(covered * 10000 / total) / 100


def measure(report: dict[str, Any]) -> dict[str, float]:
    """Line and branch percentages from a `coverage json` report."""
    totals = report["totals"]
    return {
        "line": _percent(totals["covered_lines"], totals["num_statements"]),
        "branch": _percent(totals["covered_branches"], totals["num_branches"]),
    }


def check(
    measured: dict[str, float],
    baseline: dict[str, float],
    base_baseline: dict[str, float] | None = None,
) -> list[str]:
    """Return the gate failures; an empty list means the gate passes."""
    failures = []
    for metric, floor in (("line", POLICY_LINE), ("branch", POLICY_BRANCH)):
        required = max(floor, baseline[metric])
        if measured[metric] < required:
            failures.append(f"{metric} coverage {measured[metric]:.2f}% is below {required:.2f}%")
        if base_baseline is not None and baseline[metric] < base_baseline[metric]:
            failures.append(
                f"{metric} baseline lowered from {base_baseline[metric]:.2f}% "
                f"to {baseline[metric]:.2f}%; the ratchet never goes down"
            )
    return failures


def improved(measured: dict[str, float], baseline: dict[str, float]) -> bool:
    return any(measured[metric] > baseline[metric] for metric in ("line", "branch"))


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("coverage.json"))
    parser.add_argument("--baseline", type=Path, default=Path(".coverage-baseline.json"))
    parser.add_argument("--base-baseline", type=Path, help="baseline file from the base branch")
    parser.add_argument("--update", action="store_true", help="raise the baseline to measured")
    args = parser.parse_args(argv)

    measured = measure(_load(args.report))
    baseline = _load(args.baseline)
    base_baseline = _load(args.base_baseline) if args.base_baseline else None
    print(
        f"Measured: line {measured['line']:.2f}%, branch {measured['branch']:.2f}%. "
        f"Baseline: line {baseline['line']:.2f}%, branch {baseline['branch']:.2f}%."
    )

    failures = check(measured, baseline, base_baseline)
    for failure in failures:
        print(f"::error::{failure}")
    if failures:
        return 1

    if improved(measured, baseline):
        if args.update:
            raised = {metric: max(measured[metric], baseline[metric]) for metric in measured}
            args.baseline.write_text(json.dumps(raised, indent=2) + "\n", encoding="utf-8")
            print(f"Raised the baseline in {args.baseline}.")
        else:
            print(
                "::notice::Coverage is above the baseline. Raise it in this PR with "
                "`python -m ci.coverage_gate --update` and commit .coverage-baseline.json."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
