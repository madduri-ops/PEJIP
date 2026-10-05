"""The ranking routine's working folder (design doc 0015). Synthetic data only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pejip import workbench
from pejip.analysis import PostingText, analysis_input
from pejip.profile import CareerProfile
from tests import factories

POSTING = PostingText(
    "VP Technology Operations",
    "Example Co",
    "Remote, US",
    "Lead technology operations for a large organization.",
)


@pytest.fixture
def work(tmp_path: Path, profile: CareerProfile) -> Path:
    folder = tmp_path / "work"
    workbench.prepare(
        folder,
        profile,
        [workbench.Role("1", POSTING, "hash-1"), workbench.Role("2", POSTING, "hash-2")],
    )
    return folder


def _answer(work: Path, role: str, name: str, data: object) -> None:
    text = data if isinstance(data, str) else json.dumps(data)
    (work / "roles" / role / name).write_text(text, encoding="utf-8")


def _finish(work: Path, role: str) -> None:
    _answer(work, role, workbench.ANALYSIS_FILE, factories.analysis())
    _answer(work, role, workbench.MATCHING_FILE, factories.matching())


def test_prepare_lays_out_the_profile_and_roles(work: Path, profile: CareerProfile) -> None:
    assert workbench.load_profile(work) == profile
    roles = workbench.load_roles(work)
    assert [(r.id, r.content_hash, r.posting) for r in roles] == [
        ("1", "hash-1", POSTING),
        ("2", "hash-2", POSTING),
    ]


@pytest.mark.parametrize("role_id", ["../escape", "a b", "", "x" * 65])
def test_role_ids_must_be_plain(tmp_path: Path, profile: CareerProfile, role_id: str) -> None:
    with pytest.raises(workbench.BadRoleIdError):
        workbench.prepare(tmp_path, profile, [workbench.Role(role_id, POSTING)])


def test_first_step_is_job_analysis_with_the_api_paths_input(work: Path) -> None:
    step = workbench.next_step(work)
    assert step is not None
    assert (step.role_id, step.feature, step.problem) == ("1", "job_analysis", None)
    assert step.output == work / "roles" / "1" / workbench.ANALYSIS_FILE
    text = step.instructions.read_text(encoding="utf-8")
    assert "prompt JOB_ANALYSIS v1" in text
    assert analysis_input(POSTING) in text
    assert '"normalized_title"' in text  # the schema


def test_matching_follows_a_valid_analysis(work: Path, profile: CareerProfile) -> None:
    _answer(work, "1", workbench.ANALYSIS_FILE, factories.analysis())
    step = workbench.next_step(work)
    assert step is not None
    assert (step.role_id, step.feature, step.problem) == ("1", "evidence_matching", None)
    text = step.instructions.read_text(encoding="utf-8")
    assert "<career_profile>" in text
    assert profile.headline in text
    assert "R1 [ROLE_RESPONSIBILITY, REQUIRED, CORE]" in text


def test_an_answer_that_breaks_the_schema_is_sent_back(work: Path) -> None:
    _answer(work, "1", workbench.ANALYSIS_FILE, {"normalized_title": "x"})
    step = workbench.next_step(work)
    assert step is not None
    assert step.feature == "job_analysis"
    assert step.problem is not None
    assert "does not match the schema" in step.problem
    assert "Your previous answer was refused" in step.instructions.read_text(encoding="utf-8")


def test_an_answer_that_is_not_json_is_sent_back(work: Path) -> None:
    _answer(work, "1", workbench.ANALYSIS_FILE, "```json\n{}\n```")
    step = workbench.next_step(work)
    assert step is not None
    assert step.problem is not None


def test_quotes_not_in_the_posting_are_sent_back(work: Path) -> None:
    ungrounded = factories.analysis([factories.requirement(quote="Not in the posting")])
    _answer(work, "1", workbench.ANALYSIS_FILE, ungrounded)
    step = workbench.next_step(work)
    assert step is not None
    assert step.feature == "job_analysis"
    assert step.problem is not None
    assert "copied exactly from the posting" in step.problem


def test_a_bad_matching_answer_is_sent_back(work: Path) -> None:
    _answer(work, "1", workbench.ANALYSIS_FILE, factories.analysis())
    _answer(work, "1", workbench.MATCHING_FILE, {"matches": "no"})
    step = workbench.next_step(work)
    assert step is not None
    assert step.feature == "evidence_matching"
    assert step.problem is not None


def test_done_when_every_role_is_answered_or_skipped(work: Path) -> None:
    _finish(work, "1")
    step = workbench.next_step(work)
    assert step is not None
    assert step.role_id == "2"
    workbench.skip(work, "2", "the posting is empty  ")
    assert workbench.next_step(work) is None
    assert (work / "roles" / "2" / workbench.SKIPPED_FILE).read_text() == "the posting is empty\n"


def test_skipping_an_unknown_role_is_refused(work: Path) -> None:
    with pytest.raises(workbench.UnknownRoleError):
        workbench.skip(work, "9", "why")


def test_outcomes_are_grounded_like_the_api_path(work: Path) -> None:
    requirements = [
        factories.requirement("R1"),
        factories.requirement("R2", quote="Lead technology operations"),
        factories.requirement("R3", quote="Not in the posting"),
    ]
    _answer(work, "1", workbench.ANALYSIS_FILE, factories.analysis(requirements))
    _answer(
        work,
        "1",
        workbench.MATCHING_FILE,
        factories.matching([factories.match("R1", evidence=["E1", "E999"])]),
    )
    _answer(work, "2", workbench.ANALYSIS_FILE, factories.analysis())
    done, missing = workbench.outcomes(work)
    assert missing == ["2"]
    [outcome] = done
    assert outcome.role.id == "1"
    assert outcome.dropped_requirements == 1
    assert [r.id for r in outcome.analysis.requirements] == ["R1", "R2"]
    assert outcome.matching.matches[0].evidence_ids == ["E1"]
    assert outcome.matching.matches[1].match_strength == "UNKNOWN"
    stored = workbench.payload(outcome)
    assert set(stored) == {"analysis", "matching", "dropped_requirements"}
    assert stored["dropped_requirements"] == 1
