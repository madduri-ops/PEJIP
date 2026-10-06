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

In production the session first runs ``fetch`` to get the waiting roles from PEJIP
and finally ``submit`` to post the answers back, which also tells PEJIP to email
the digest now rather than at its scheduled time. Both read ``PEJIP_RANKING_URL``
(PEJIP's address) and ``PEJIP_RANKING_KEY`` (the routine's key) from the
environment.

The working folder holds personal data in production, so it must live outside the
repository and is never committed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from pejip import golden_eval, workbench
from pejip.analysis import PostingText
from pejip.evaluation.golden import DEFAULT_GOLDEN_DIR, load_golden_set
from pejip.ranking_api import MAX_RESULTS, RANKING_PREFIX, MatchingProfile, Queue

PROMPTS_FILE = "prompts.json"
TIMEOUT_SECONDS = 60
# Tests swap in a mock transport; production uses the network.
TRANSPORT: httpx.BaseTransport | None = None


class SettingMissingError(workbench.WorkbenchError):
    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is not set")


class ExchangeError(workbench.WorkbenchError):
    """PEJIP refused the request or could not be reached."""

    def __init__(self, cause: str) -> None:
        super().__init__(f"PEJIP did not accept the request: {cause}")


def _client() -> httpx.Client:
    url, key = os.environ.get("PEJIP_RANKING_URL", ""), os.environ.get("PEJIP_RANKING_KEY", "")
    for name, value in (("PEJIP_RANKING_URL", url), ("PEJIP_RANKING_KEY", key)):
        if not value:
            raise SettingMissingError(name)
    return httpx.Client(
        base_url=url.rstrip("/") + RANKING_PREFIX,
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT_SECONDS,
        transport=TRANSPORT,
    )


def _exchange(method: str, path: str, body: object = None) -> httpx.Response:
    try:
        with _client() as client:
            response = client.request(method, path, json=body)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExchangeError(str(exc)) from exc
    return response


def _say(text: str) -> None:
    sys.stdout.write(text + "\n")


def _cmd_next(work: Path, role_id: str | None) -> int:
    step = workbench.next_step(work, role_id)
    if step is None:
        which = "this role has" if role_id else "every role has"
        _say(f"DONE: {which} valid answers or was skipped.")
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


def _cmd_fetch(work: Path) -> int:
    queue = Queue.model_validate(_exchange("GET", "queue").json())
    profile = MatchingProfile.model_validate(queue.profile.model_dump()).career_profile()
    roles = [
        workbench.Role(
            str(role.job_id),
            PostingText(role.title, role.company, role.location, role.description),
            role.content_hash,
        )
        for role in queue.roles
    ]
    workbench.prepare(work, profile, roles)
    (work / PROMPTS_FILE).write_text(json.dumps(queue.prompts), encoding="utf-8")
    _say(f"Fetched {len(roles)} roles into {work}.")
    return 0


def _cmd_submit(work: Path, model: str) -> int:
    done, missing = workbench.outcomes(work)
    prompts = json.loads((work / PROMPTS_FILE).read_text(encoding="utf-8"))
    results = [
        {
            "job_id": int(outcome.role.id),
            "content_hash": outcome.role.content_hash,
            "analysis": outcome.analysis.model_dump(),
            "matching": outcome.matching.model_dump(),
        }
        for outcome in done
    ]
    accepted, rejected = 0, []
    for start in range(0, len(results), MAX_RESULTS):
        body = {"model": model, "prompts": prompts, "results": results[start : start + MAX_RESULTS]}
        reply = _exchange("POST", "analyses", body).json()
        accepted += reply["accepted"]
        rejected += reply["rejected"]
    _say(f"PEJIP accepted {accepted} of {len(results)} answers.")
    for item in rejected:
        _say(f"Refused role {item['job_id']}: {item['reason']}")
    if missing:
        _say("Not answered (offered again next time): " + ", ".join(missing))
    _exchange("POST", "done", {})
    _say("Asked PEJIP to email the digest now.")
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
    sub.add_parser("fetch", help="get the waiting roles from PEJIP")
    submit = sub.add_parser("submit", help="post the answers back and have PEJIP email the digest")
    submit.add_argument("--model", required=True, help="the model the session ran on")
    step = sub.add_parser("next", help="name the next step and write its instructions")
    step.add_argument("--role", help="only this role")
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


def _dispatch(args: argparse.Namespace) -> int:
    commands = {
        "fetch": lambda: _cmd_fetch(args.work),
        "submit": lambda: _cmd_submit(args.work, args.model),
        "next": lambda: _cmd_next(args.work, args.role),
        "skip": lambda: _cmd_skip(args.work, args.role, args.reason),
        "eval-prepare": lambda: _cmd_eval_prepare(args.work, args.golden),
        "eval-record": lambda: _cmd_eval_record(args.work, args.out, args.model, args.golden),
    }
    return commands[args.command]()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except workbench.WorkbenchError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
