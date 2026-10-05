from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from pejip.analysis import EvidenceMatching, JobAnalysis
from pejip.config import SearchConfig
from pejip.explain import UnsupportedClaimError, build_explanation, verify_citations
from pejip.profile import CareerProfile
from pejip.scoring import JobFacts, score_job
from tests import factories as f
from tests.conftest import NOW

DESCRIPTION = (
    "Lead technology operations. Own portfolio governance. Manage a budget above $30M. "
    "Healthcare experience required. Carry a quota. Hands-on coding. Board reporting. Extra item."
)


def job(**overrides: Any) -> dict[str, Any]:
    data = {
        "title": "VP Ops",
        "company": "Co",
        "location": "Oakland, CA",
        "description": DESCRIPTION,
        "posted_at": NOW - timedelta(days=0),
        "first_seen_at": NOW,
        "comp_min": 300000.0,
        "comp_max": 400000.0,
    }
    data.update(overrides)
    return data


def build(
    profile: CareerProfile,
    config: SearchConfig,
    matches: list[dict[str, Any]],
    location_fit: str = "PREFERRED",
    **job_overrides: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    quotes = [
        "Lead technology operations",
        "Own portfolio governance",
        "Manage a budget above $30M",
        "Healthcare experience required",
        "Board reporting",
        "Extra item",
    ]
    importance = ["CORE", "CORE", "IMPORTANT", "IMPORTANT", "SUPPORTING", "CORE"]
    reqs = [
        f.requirement(f"R{i}", quote=q, importance=imp)
        for i, (q, imp) in enumerate(zip(quotes, importance, strict=True), 1)
    ]
    analysis = JobAnalysis.model_validate(
        f.analysis(
            reqs,
            negative_signals=[{"code": "QUOTA_CARRYING", "quote": "Carry a quota"}],
            missing_information=["TEAM_SIZE", "REPORTING_LINE"],
        )
    )
    matching = EvidenceMatching.model_validate(f.matching(matches))
    j = job(**job_overrides)
    facts = JobFacts(
        j["posted_at"], j["first_seen_at"], j["comp_min"], j["comp_max"], location_fit, NOW
    )
    rec = score_job(analysis, matching, profile, facts, config.scoring)
    return build_explanation(analysis, matching, rec, j), j


MATCHES = [
    f.match("R1", "STRONG_MATCH", ["E1"]),
    f.match("R2", "GOOD_MATCH", ["E4"]),
    f.match("R3", "UNKNOWN", []),
    f.match("R4", "NO_MATCH", []),
    f.match("R5", "WEAK_MATCH", ["E7"]),
    f.match("R6", "STRONG_MATCH", ["E2"]),
]


def test_explanation_sections_cite_their_evidence(
    profile: CareerProfile, config: SearchConfig
) -> None:
    explanation, j = build(profile, config, MATCHES)
    fits = [p["text"] for p in explanation["why_it_fits"]]
    assert fits == [
        "Strong match: Requirement R1",
        "Good match: Requirement R2",
        "Strong match: Requirement R6",
    ]
    assert explanation["why_it_fits"][0]["citations"] == [
        {"type": "posting", "quote": "Lead technology operations"},
        {"type": "profile", "evidence_id": "E1"},
    ]
    concerns = [p["text"] for p in explanation["concerns"]]
    assert concerns == [
        "Not enough profile evidence to judge: Requirement R3",
        "Gap: Requirement R4",
        "Possible negative fit (quota_carrying)",
        "The posting does not state: team size, reporting line",
    ]
    now = [p["text"] for p in explanation["why_now"]]
    assert now == [
        "Posted today",
        "Preferred location: Oakland, CA",
        "Stated pay meets your preference",
    ]
    assert explanation["who_you_know"][0]["citations"] == []
    verify_citations(explanation, j, profile)


def test_points_are_capped(profile: CareerProfile, config: SearchConfig) -> None:
    matches = [f.match(f"R{i}", "STRONG_MATCH", ["E1"]) for i in range(1, 7)]
    explanation, _ = build(profile, config, matches)
    assert len(explanation["why_it_fits"]) == 4
    gaps = [f.match(f"R{i}", "NO_MATCH", []) for i in range(1, 7)]
    explanation, _ = build(profile, config, gaps)
    assert sum(p["text"].startswith("Gap") for p in explanation["concerns"]) == 4


def test_pay_and_first_seen_wording(profile: CareerProfile, config: SearchConfig) -> None:
    explanation, j = build(
        profile,
        config,
        MATCHES,
        posted_at=None,
        first_seen_at=NOW - timedelta(days=3),
        comp_min=200000.0,
        comp_max=None,
    )
    assert explanation["why_now"][0]["text"] == "First seen 3 days ago"
    assert explanation["concerns"][-1]["text"] == "Stated pay is below your minimum"
    assert explanation["concerns"][-1]["citations"] == [{"type": "job_field", "field": "comp_min"}]
    verify_citations(explanation, j, profile)
    explanation, j = build(profile, config, MATCHES, comp_min=None, comp_max=300000.0)
    assert explanation["concerns"][-1]["text"] == "Stated pay is below your preferred level"
    explanation, j = build(profile, config, MATCHES, comp_min=360000.0, comp_max=None)
    assert explanation["why_now"][-1]["citations"] == [{"type": "job_field", "field": "comp_min"}]


@pytest.mark.parametrize(
    "citation",
    [
        {"type": "posting", "quote": "not in the posting"},
        {"type": "profile", "evidence_id": "E404"},
        {"type": "job_field", "field": "comp_min"},
        {"type": "job_field", "field": "secret_field"},
        {"type": "web", "url": "https://example.com"},
    ],
)
def test_unresolvable_citations_fail(profile: CareerProfile, citation: dict[str, str]) -> None:
    explanation = {"why_it_fits": [{"text": "claim", "citations": [citation]}]}
    with pytest.raises(UnsupportedClaimError):
        verify_citations(explanation, job(comp_min=None), profile)


def test_unknown_pay_adds_no_pay_point(profile: CareerProfile, config: SearchConfig) -> None:
    explanation, j = build(profile, config, MATCHES, comp_min=None, comp_max=None)
    assert [p["text"] for p in explanation["why_now"]] == [
        "Posted today",
        "Preferred location: Oakland, CA",
    ]
    verify_citations(explanation, j, profile)


@pytest.mark.parametrize(
    ("location_fit", "expected"),
    [("ACCEPTABLE", "Acceptable location: Oakland, CA"), ("UNKNOWN", None)],
)
def test_location_points(
    profile: CareerProfile, config: SearchConfig, location_fit: str, expected: str | None
) -> None:
    explanation, _ = build(profile, config, MATCHES, location_fit=location_fit)
    texts = [p["text"] for p in explanation["why_now"]]
    assert (expected in texts) if expected else not any("location" in t for t in texts)
