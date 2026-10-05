"""A working folder where a Claude Code session does the model step of ranking.

The ranking routine (design doc 0015) runs as a Claude Code session on Babu's
plan instead of calling the API. It gets the same two steps the API path runs in
``pejip.analysis.analyze_job``: job analysis, then evidence matching on the
grounded requirements. Each step has the same system prompt, input and output
schema as the API call. The session writes each answer as a JSON file. This module
lays out the folder, says which step comes next, and checks every answer with the
API path's own validation before it counts.

Layout::

    <work>/profile.json             the career profile (never committed)
    <work>/roles/<id>/role.json     one posting
    <work>/roles/<id>/step.md       the next step's instructions, written by next_step
    <work>/roles/<id>/job_analysis.json
    <work>/roles/<id>/evidence_matching.json
    <work>/roles/<id>/skipped.txt   why the session gave up on this role
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from pejip.ai.client import AIError, strict_schema
from pejip.ai.prompts import load_prompt
from pejip.analysis import (
    EvidenceMatching,
    JobAnalysis,
    PostingText,
    analysis_input,
    ground_analysis,
    ground_matching,
    matching_input,
)
from pejip.profile import CareerProfile

PROFILE_FILE = "profile.json"
ROLES_DIR = "roles"
ROLE_FILE = "role.json"
STEP_FILE = "step.md"
SKIPPED_FILE = "skipped.txt"
ANALYSIS_FILE = "job_analysis.json"
MATCHING_FILE = "evidence_matching.json"

# Role ids become folder names, so only plain ids are accepted.
_ROLE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class WorkbenchError(ValueError):
    """The working folder is not usable as asked."""


class BadRoleIdError(WorkbenchError):
    def __init__(self, role_id: str) -> None:
        super().__init__(f"role id {role_id!r} must be 1-64 letters, digits, - or _")


class UnknownRoleError(WorkbenchError):
    def __init__(self, role_id: str) -> None:
        super().__init__(f"no role {role_id!r} in this working folder")


class RefusedAnswerError(WorkbenchError):
    """An answer file failed the API path's validation; the message says why."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"{filename}: {reason}")


@dataclass(frozen=True)
class Role:
    """One posting to analyse. ``content_hash`` ties the answer to this version."""

    id: str
    posting: PostingText
    content_hash: str = ""


@dataclass(frozen=True)
class Outcome:
    """A role's validated answers, grounded exactly as the API path grounds them."""

    role: Role
    analysis: JobAnalysis
    matching: EvidenceMatching
    dropped_requirements: int


@dataclass(frozen=True)
class Step:
    """What the session must do next for one role."""

    role_id: str
    feature: str  # job_analysis or evidence_matching
    instructions: Path
    output: Path
    problem: str | None  # why an answer already written was refused


def _role_dir(work: Path, role_id: str) -> Path:
    if not _ROLE_ID.fullmatch(role_id):
        raise BadRoleIdError(role_id)
    return work / ROLES_DIR / role_id


def prepare(work: Path, profile: CareerProfile, roles: list[Role]) -> None:
    """Lay out a fresh working folder for ``roles``."""
    work.mkdir(parents=True, exist_ok=True)
    (work / PROFILE_FILE).write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    for role in roles:
        folder = _role_dir(work, role.id)
        folder.mkdir(parents=True, exist_ok=False)
        data = {"id": role.id, "content_hash": role.content_hash, **vars(role.posting)}
        (folder / ROLE_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_profile(work: Path) -> CareerProfile:
    return CareerProfile.model_validate_json((work / PROFILE_FILE).read_text(encoding="utf-8"))


def load_roles(work: Path) -> list[Role]:
    roles = []
    for path in sorted((work / ROLES_DIR).glob(f"*/{ROLE_FILE}")):
        data = json.loads(path.read_text(encoding="utf-8"))
        posting = PostingText(data["title"], data["company"], data["location"], data["description"])
        roles.append(Role(data["id"], posting, data["content_hash"]))
    return roles


def skip(work: Path, role_id: str, reason: str) -> None:
    """Give up on a role; it stays unranked and is offered again next time."""
    folder = _role_dir(work, role_id)
    if not (folder / ROLE_FILE).exists():
        raise UnknownRoleError(role_id)
    (folder / SKIPPED_FILE).write_text(reason.strip() + "\n", encoding="utf-8")


def _read_answer[T: BaseModel](path: Path, schema: type[T]) -> T:
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'top level'}: {e['msg']}"
            for e in exc.errors()[:10]
        )
        raise RefusedAnswerError(path.name, f"does not match the schema: {errors}") from exc


def _analysis(folder: Path, role: Role) -> tuple[JobAnalysis, int]:
    answer = _read_answer(folder / ANALYSIS_FILE, JobAnalysis)
    try:
        return ground_analysis(answer, analysis_input(role.posting))
    except AIError as exc:
        reason = f"{exc}. Every quote must be copied exactly from the posting."
        raise RefusedAnswerError(ANALYSIS_FILE, reason) from exc


def _outcome(work: Path, role: Role, profile: CareerProfile) -> Outcome:
    folder = _role_dir(work, role.id)
    analysis, dropped = _analysis(folder, role)
    matching = _read_answer(folder / MATCHING_FILE, EvidenceMatching)
    return Outcome(role, analysis, ground_matching(matching, analysis, profile), dropped)


def _instructions(feature: str, prompt_id: str, content: str, schema: type[BaseModel]) -> str:
    prompt = load_prompt(prompt_id)
    return (
        f"# {feature} (prompt {prompt.id} v{prompt.version})\n\n"
        "Follow the system prompt below exactly, as if it were your instructions, and "
        "answer the input with one JSON object that matches the schema. Write only that "
        "JSON to the output file: no Markdown fence, no comments.\n\n"
        f"## System prompt\n\n{prompt.text}\n\n"
        f"## Input\n\n{content}\n\n"
        f"## Output schema\n\n```json\n{json.dumps(strict_schema(schema), indent=2)}\n```\n"
    )


def _step(folder: Path, role_id: str, feature: str, text: str, problem: str | None) -> Step:
    output = folder / (ANALYSIS_FILE if feature == "job_analysis" else MATCHING_FILE)
    if problem:
        text += f"\n## Your previous answer was refused\n\n{problem}\n"
    instructions = folder / STEP_FILE
    instructions.write_text(text, encoding="utf-8")
    return Step(role_id, feature, instructions, output, problem)


def next_step(work: Path) -> Step | None:
    """The first step still to do, with its instructions written; None when all are done.

    An answer already written is checked first. If it fails validation, the same
    step comes back with the reason, so the session can correct it.
    """
    profile = load_profile(work)
    for role in load_roles(work):
        folder = _role_dir(work, role.id)
        if (folder / SKIPPED_FILE).exists():
            continue
        posting = analysis_input(role.posting)
        if not (folder / ANALYSIS_FILE).exists():
            text = _instructions("job_analysis", "JOB_ANALYSIS", posting, JobAnalysis)
            return _step(folder, role.id, "job_analysis", text, None)
        try:
            analysis, _ = _analysis(folder, role)
        except WorkbenchError as exc:
            text = _instructions("job_analysis", "JOB_ANALYSIS", posting, JobAnalysis)
            return _step(folder, role.id, "job_analysis", text, str(exc))
        content = matching_input(profile, analysis)
        text = _instructions("evidence_matching", "EVIDENCE_MATCHING", content, EvidenceMatching)
        if not (folder / MATCHING_FILE).exists():
            return _step(folder, role.id, "evidence_matching", text, None)
        try:
            _read_answer(folder / MATCHING_FILE, EvidenceMatching)
        except WorkbenchError as exc:
            return _step(folder, role.id, "evidence_matching", text, str(exc))
    return None


def outcomes(work: Path) -> tuple[list[Outcome], list[str]]:
    """Every finished role's validated answers, and the ids of roles without one."""
    profile = load_profile(work)
    done: list[Outcome] = []
    missing: list[str] = []
    for role in load_roles(work):
        try:
            done.append(_outcome(work, role, profile))
        except (OSError, WorkbenchError):
            missing.append(role.id)
    return done, missing


def payload(outcome: Outcome) -> dict[str, Any]:
    """The answers in the shape the pipeline stores and the eval recordings use."""
    return {
        "analysis": outcome.analysis.model_dump(),
        "matching": outcome.matching.model_dump(),
        "dropped_requirements": outcome.dropped_requirements,
    }
