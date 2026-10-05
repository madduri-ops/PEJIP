"""Coverage gate and ratchet (docs/BUILD_POLICY.md section 1).

Reads coverage.json and coverage-baseline.json. Fails when line coverage is below
100%, branch coverage is below 95%, either drops below the committed baseline, or
either rises above it without the baseline being raised in the same change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LINE_FLOOR = 100.0
BRANCH_FLOOR = 95.0


def percentages(report: dict[str, dict[str, float]]) -> tuple[float, float]:
    totals = report["totals"]
    line = 100.0 * totals["covered_lines"] / max(totals["num_statements"], 1)
    branch = 100.0 * totals["covered_branches"] / max(totals["num_branches"], 1)
    return round(line, 2), round(branch, 2)


def check(line: float, branch: float, baseline: dict[str, float]) -> list[str]:
    errors = []
    if line < LINE_FLOOR:
        errors.append(f"line coverage {line}% is below the {LINE_FLOOR}% floor")
    if branch < BRANCH_FLOOR:
        errors.append(f"branch coverage {branch}% is below the {BRANCH_FLOOR}% floor")
    for name, value in (("line", line), ("branch", branch)):
        if value < baseline[name]:
            errors.append(f"{name} coverage {value}% dropped below the baseline {baseline[name]}%")
        elif value > baseline[name]:
            errors.append(
                f"{name} coverage rose to {value}%: raise coverage-baseline.json to lock it in"
            )
    return errors


def main(report_path: str = "coverage.json", baseline_path: str = "coverage-baseline.json") -> int:
    report = json.loads(Path(report_path).read_text())
    baseline = json.loads(Path(baseline_path).read_text())
    line, branch = percentages(report)
    print(f"line {line}%  branch {branch}%  (baseline {baseline})")
    errors = check(line, branch, baseline)
    for error in errors:
        print(f"::error::{error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
