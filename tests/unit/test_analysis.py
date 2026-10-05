from __future__ import annotations

import pytest

from pejip.ai.client import AIClient, AIError
from pejip.analysis import (
    EvidenceMatching,
    JobAnalysis,
    analyze_job,
    ground_analysis,
    ground_matching,
    quote_in,
)
from pejip.config import SearchConfig
from pejip.profile import CareerProfile
from pejip.store import Store
from tests import factories as f
from tests.conftest import NOW, FakeMessages, response


def test_quote_in_ignores_case_and_whitespace() -> None:
    assert quote_in("lead   TECHNOLOGY\noperations", f.POSTING_TEXT)
    assert not quote_in("run sales", f.POSTING_TEXT)
    assert not quote_in("   ", f.POSTING_TEXT)


def test_ground_analysis_drops_unsupported_and_duplicate_items() -> None:
    data = f.analysis(
        [
            f.requirement("R1"),
            f.requirement("R1", quote="Own portfolio governance"),
            f.requirement("R2", quote="Own portfolio governance"),
            f.requirement("R3", quote="Manage a budget above $30M"),
            f.requirement("R4", quote="Invented requirement"),
        ],
        positive_scope_signals=[{"quote": "executive team"}, {"quote": "board of directors"}],
        negative_signals=[
            {"code": "OTHER", "quote": "large organization"},
            {"code": "QUOTA_CARRYING", "quote": "carry a quota"},
        ],
    )
    grounded, dropped = ground_analysis(JobAnalysis.model_validate(data), f.POSTING_TEXT)
    assert [r.id for r in grounded.requirements] == ["R1", "R2", "R3"]
    assert dropped == 2
    assert [s.quote for s in grounded.positive_scope_signals] == ["executive team"]
    assert [s.code for s in grounded.negative_signals] == ["OTHER"]


def test_ground_analysis_rejects_mostly_invented_output() -> None:
    data = f.analysis(
        [f.requirement("R1", quote="made up"), f.requirement("R2", quote="also made up")]
    )
    with pytest.raises(AIError, match="not grounded"):
        ground_analysis(JobAnalysis.model_validate(data), f.POSTING_TEXT)


def test_ground_analysis_accepts_no_requirements() -> None:
    grounded, dropped = ground_analysis(JobAnalysis.model_validate(f.analysis([])), f.POSTING_TEXT)
    assert grounded.requirements == [] and dropped == 0


def test_ground_matching(profile: CareerProfile) -> None:
    analysis = JobAnalysis.model_validate(
        f.analysis(
            [f.requirement("R1"), f.requirement("R2"), f.requirement("R3"), f.requirement("R4")]
        )
    )
    matching = EvidenceMatching.model_validate(
        f.matching(
            [
                f.match("R1", "STRONG_MATCH", ["E1", "E99"]),
                f.match("R1", "NO_MATCH", []),
                f.match("R2", "GOOD_MATCH", ["E99"]),
                f.match("R3", "NO_MATCH", []),
                f.match("R9", "STRONG_MATCH", ["E1"]),
            ],
            direction_evidence=["E2", "E77"],
        )
    )
    grounded = ground_matching(matching, analysis, profile)
    result = {m.requirement_id: (m.match_strength, m.evidence_ids) for m in grounded.matches}
    assert result == {
        "R1": ("STRONG_MATCH", ["E1"]),
        "R2": ("UNKNOWN", []),
        "R3": ("NO_MATCH", []),
        "R4": ("UNKNOWN", []),
    }
    assert grounded.career_direction_evidence_ids == ["E2"]


def test_analyze_job_runs_both_prompts(
    config: SearchConfig, store: Store, profile: CareerProfile
) -> None:
    fake = FakeMessages(response(f.analysis()), response(f.matching()))
    ai = AIClient(config.ai, store, messages=fake, clock=lambda: NOW)
    outcome = analyze_job(
        ai, profile, title="VP Ops", company="Co", location="SF", description=f.POSTING_TEXT
    )
    assert outcome.matching.matches[0].match_strength == "STRONG_MATCH"
    assert outcome.dropped_requirements == 0
    assert set(outcome.provenance) == {"analysis", "matching"}
    analysis_request, matching_request = fake.calls
    assert "<posting>" in analysis_request["messages"][0]["content"]
    matching_input = matching_request["messages"][0]["content"]
    assert "R1 [ROLE_RESPONSIBILITY, REQUIRED, CORE]" in matching_input
    assert profile.name not in matching_input
