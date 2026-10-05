"""Commands the ranking routine's Claude Code session runs (design doc 0015).

``python -m pejip.routine next --work DIR`` names the next step and writes its
instructions. The session follows them, writes the answer file, and runs ``next``
again until it prints ``DONE``. ``skip`` gives up on a role that keeps failing.

The golden set runs through the same steps, so the routine's answers are measured
before they rank real roles (policy section 12)::

    python -m pejip.routine eval-prepare --work /tmp/eval
    python -m pejip.routine next --work /tmp/eval        # repeat until DONE
    python -m pejip.routine eval-record --work /tmp/eval --out /tmp/eval/recordings \\
        --model "<model the session runs on>"
    PEJIP_EVAL_RECORDINGS=/tmp/eval/recordings python -m pejip.evaluation run \\
        --scorer pejip.golden_eval:replay_scorer

The working folder holds personal data in production, so it must live outside the
repository and is never committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pejip import golden_eval, workbench
from pejip.evaluation.golden import DEFAULT_GOLDEN_DIR, load_golden_set


def _say(text: str) -> None:
    sys.stdout.write(text + "\n")


def _cmd_next(work: Path) -> int:
    step = workbench.next_step(work)
    if step is None:
        _say("DONE: every role has valid answers or was skipped.")
        return 0
    if step.problem:
        _say(f"REDO role {step.role_id} {step.feature}: {step.problem}")
    else:
        _say(f"STEP role {step.role_id} {step.feature}")
    _say(f"Read {step.instructions} and write your JSON answer to {step.output}.")
    return 0


def _cmd_skip(work: Path, role_id: str, reason: str) -> int:
    workbench.skip(work, role_id, reason)
    _say(f"Skipped role {role_id}.")
    return 0


def _cmd_eval_prepare(work: Path, golden_dir: Path) -> int:
    golden = load_golden_set(golden_dir)
    roles = [workbench.Role(case.id, golden_eval.posting_text(case.job)) for case in golden.cases]
    workbench.prepare(work, golden_eval.career_profile(golden.profile), roles)
    _say(f"Prepared {len(roles)} golden cases in {work}.")
    return 0


def _cmd_eval_record(work: Path, out: Path, model: str, golden_dir: Path) -> int:
    done, missing = workbench.outcomes(work)
    out.mkdir(parents=True, exist_ok=True)
    version = golden_eval.golden_set_version(golden_dir)
    for outcome in done:
        recording = {
            "golden_set_version": version,
            "provenance": {"ranker": "routine", "model": model},
            **workbench.payload(outcome),
        }
        path = golden_eval.recording_path(outcome.role.id, out)
        path.write_text(json.dumps(recording, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _say(f"Recorded {len(done)} cases in {out}.")
    if missing:
        _say("No valid answers for: " + ", ".join(missing))
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pejip.routine", description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="working folder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("next", help="name the next step and write its instructions")
    skip = sub.add_parser("skip", help="give up on a role that keeps failing")
    skip.add_argument("role")
    skip.add_argument("reason")
    prepare = sub.add_parser("eval-prepare", help="lay out the golden set as roles")
    prepare.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_DIR)
    record = sub.add_parser("eval-record", help="write answers as eval recordings")
    record.add_argument("--out", type=Path, required=True)
    record.add_argument("--model", required=True, help="the model the session ran on")
    record.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "next":
            return _cmd_next(args.work)
        if args.command == "skip":
            return _cmd_skip(args.work, args.role, args.reason)
        if args.command == "eval-prepare":
            return _cmd_eval_prepare(args.work, args.golden)
        return _cmd_eval_record(args.work, args.out, args.model, args.golden)
    except workbench.WorkbenchError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
