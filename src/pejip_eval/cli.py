"""Command line: ``python -m pejip_eval {validate,run,ratchet}``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .baseline import (
    DEFAULT_BASELINE,
    ratchet,
    read_baseline,
    regressions,
    write_baseline,
)
from .evaluate import Report, evaluate
from .golden import DEFAULT_GOLDEN_DIR, GoldenSetError, load_golden_set
from .scorer import ScorerLoadError, load_scorer


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pejip_eval", description=__doc__)
    parser.add_argument(
        "--golden", type=Path, default=DEFAULT_GOLDEN_DIR, help="golden set directory"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check the golden set is well formed")

    for name, text in (
        ("run", "score the golden set and fail below the baseline"),
        ("ratchet", "score the golden set and raise the baseline where it improved"),
    ):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--scorer", required=True, help="package.module:callable")
        cmd.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        cmd.add_argument("--report", type=Path, help="write a JSON report here")
        cmd.add_argument(
            "--fit-tolerance",
            type=float,
            default=0.0,
            help="allowed Fit drift in network probes",
        )
    return parser


def _print_report(report: Report) -> None:
    print(f"golden set {report.golden_set_version}")
    for name, value in report.metrics.items():
        print(f"  {name:<24} {value:.4f}")
    for result in report.cases:
        failures = result.failures()
        if failures:
            print(f"  {result.case_id}: " + "; ".join(failures))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        golden = load_golden_set(args.golden)
    except GoldenSetError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"golden set {golden.version}: {len(golden.cases)} cases OK")
        return 0

    try:
        scorer = load_scorer(args.scorer)
        baseline = read_baseline(args.baseline)
    except (ScorerLoadError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    report = evaluate(golden, scorer, fit_tolerance=args.fit_tolerance)
    _print_report(report)
    if args.report:
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    if args.command == "ratchet":
        updated, changed = ratchet(report, baseline, args.scorer)
        if changed:
            write_baseline(args.baseline, updated)
            print(f"baseline raised in {args.baseline}")
        else:
            print("baseline unchanged")
        return 0

    found = regressions(report, baseline)
    for regression in found:
        print(f"REGRESSION {regression}", file=sys.stderr)
    return 1 if found else 0
