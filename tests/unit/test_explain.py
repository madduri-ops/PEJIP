from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from pejip.analysis import EvidenceMatching, JobAnalysis
from pejip.config import SearchConfig
from pejip.explain import (
    UnsupportedClaimError,
    build_explanation,
    network_points,
    verify_citations,
)
from pejip.network.companies import CompanyDirectory
from pejip.network.linkedin import parse_export
from pejip.network.matching import NetworkIndex, NetworkSignal, TitleDecision
from pejip.profile import CareerProfile
from pejip.scoring import JobFacts, score_job
from tests import factories as f
from tests.conftest import NOW
from tests.linkedin import export, row

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


def signal_for(role_level: str, *rows: str) -> NetworkSignal:
    directory = CompanyDirectory.build(["Co"])
    people = parse_export(export(*rows), NOW).connections if rows else ()
    return NetworkIndex.build(people, directory).signal("Co", role_level)


def test_who_you_know_names_matured_connections_and_asks_about_unclear_titles(
    profile: CareerProfile,
) -> None:
    signal = signal_for(
        "VP",
        row("Avery", company="Co", position="SVP Technology"),
        row("Casey", company="Co", position="Principal, Technology Strategy"),
        row("Devon", company="Co", position="Director"),
        row("Emery", company="Co", position="Engineer"),
    )
    points = network_points(signal, "Co")
    assert [p["text"] for p in points] == [
        "Matured connection: Avery Example, SVP Technology",
        "Your call: Casey Example, Principal, Technology Strategy. This title has no clear"
        " level. Is it comparable to VP or more senior?",
        "2 other first-degree connections below VP level.",
        "As of your LinkedIn import on October 5, 2026; people may have moved since.",
    ]
    assert points[0]["citations"] == [
        {"type": "network", "connection_id": signal.matches[0].connection.connection_id}
    ]
    verify_citations({"who_you_know": points}, job(), profile, signal)
    with pytest.raises(UnsupportedClaimError):
        verify_citations({"who_you_know": points}, job(), profile)


def test_who_you_know_wording_for_decided_single_and_absent_connections() -> None:
    directory = CompanyDirectory.build(["Co"])
    people = parse_export(
        export(
            row("Casey", company="Co", position="Partner"),
            row("Devon", company="Co", position="Director"),
        ),
        NOW,
    ).connections
    decided = NetworkIndex.build(
        people, directory, [TitleDecision("Co", "Partner", "VP", matured=True)]
    ).signal("Co", "VP")
    texts = [p["text"] for p in network_points(decided, "Co")]
    assert texts[:2] == [
        "Matured connection: Casey Example, Partner (your call)",
        "1 other first-degree connection below VP level.",
    ]
    nobody = network_points(signal_for("VP"), "Co")
    assert [p["text"] for p in nobody] == [
        "No first-degree connections at Co. As of your LinkedIn import on an unknown date;"
        " people may have moved since."
    ]
    assert network_points(None, "Co")[0]["text"] == "Network data has not been imported yet."
    warm = network_points(signal_for("VP"), "Co & Sons", warm_path=True)
    assert warm[1]["text"] == (
        "Strong fit: check LinkedIn for someone who can introduce you (second-degree"
        " connections at Co & Sons): https://www.linkedin.com/search/results/people/"
        "?keywords=Co+%26+Sons&network=%5B%22S%22%5D"
    )
    assert warm[1]["citations"] == []
    # Someone known directly is the better path, so no second-degree prompt.
    assert network_points(decided, "Co", warm_path=True) == network_points(decided, "Co")


def test_an_unclear_role_level_is_asked_about_plainly() -> None:
    directory = CompanyDirectory.build(["Co"])
    people = parse_export(export(row(company="Co", position="VP")), NOW).connections
    signal = NetworkIndex.build(people, directory).signal("Co", "UNKNOWN", "Partner")
    assert network_points(signal, "Co")[0]["text"] == (
        "Your call: Avery Example, VP. This role's level is unclear. Is this person at its"
        " level or more senior?"
    )


def test_people_past_the_first_four_are_counted_not_dropped() -> None:
    names = ["Ari", "Bo", "Cy", "Di", "Ed", "Fy"]
    rows = [row(n, company="Co", position="SVP") for n in names]
    rows += [row(f"P{n}", company="Co", position="Partner") for n in names[:5]]
    texts = [p["text"] for p in network_points(signal_for("VP", *rows), "Co")]
    assert "2 more matured connections." in texts
    assert "1 more title needs your call." in texts
    assert sum(t.startswith("Matured connection") for t in texts) == 4
    rows = [row(n, company="Co", position="SVP") for n in names[:5]]
    rows += [row(f"P{n}", company="Co", position="Partner") for n in names]
    texts = [p["text"] for p in network_points(signal_for("VP", *rows), "Co")]
    assert "1 more matured connection." in texts
    assert "2 more titles need your call." in texts
