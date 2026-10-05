from __future__ import annotations

import dataclasses
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from pejip.analysis import EvidenceMatching, JobAnalysis
from pejip.config import ScoringConfig, SearchConfig
from pejip.profile import CareerProfile
from pejip.scoring import (
    JobFacts,
    NetworkFacts,
    Recommendation,
    compensation_fit,
    score_job,
)
from tests import factories as f
from tests.conftest import NOW


def facts(
    age_days: int = 1,
    comp: tuple[float | None, float | None] = (None, None),
    location: str = "PREFERRED",
    posted: bool = True,
) -> JobFacts:
    return JobFacts(
        posted_at=NOW - timedelta(days=age_days) if posted else None,
        first_seen_at=NOW - timedelta(days=age_days),
        comp_min=comp[0],
        comp_max=comp[1],
        location_preference=location,
        as_of=NOW,
    )


def all_categories(
    strength: str = "STRONG_MATCH", importance: str = "CORE"
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cats = ["ROLE_RESPONSIBILITY", "SENIORITY_SCOPE", "CAPABILITY", "LEADERSHIP", "DOMAIN_INDUSTRY"]
    reqs = [
        f.requirement(f"R{i}", category=c, importance=importance) for i, c in enumerate(cats, 1)
    ]
    matches = [
        f.match(f"R{i}", strength, [] if strength in ("NO_MATCH", "UNKNOWN") else ["E1"])
        for i in range(1, 6)
    ]
    return reqs, matches


def score(
    profile: CareerProfile,
    cfg: ScoringConfig,
    analysis: dict[str, Any] | None = None,
    matching: dict[str, Any] | None = None,
    job: JobFacts | None = None,
) -> Recommendation:
    reqs, matches = all_categories()
    return score_job(
        JobAnalysis.model_validate(analysis or f.analysis(reqs)),
        EvidenceMatching.model_validate(matching or f.matching(matches)),
        profile,
        job or facts(),
        cfg,
    )


def test_excellent_fresh_match_is_immediate(profile: CareerProfile, config: SearchConfig) -> None:
    rec = score(profile, config.scoring, job=facts(comp=(None, 400000)))
    assert rec.fit == 100.0
    assert rec.confidence == "HIGH"
    assert rec.priority == "IMMEDIATE"
    assert rec.compensation_fit == "STRONG"
    assert {
        "STRONG_ROLE_MATCH",
        "EXECUTIVE_SCOPE_MATCH",
        "FRESH_POSTING",
        "PREFERRED_LOCATION",
    } <= set(rec.reason_codes)
    assert rec.to_dict()["scoring_version"] == "fit-2"


def test_unknown_matches_do_not_lower_fit_but_lower_confidence(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs, matches = all_categories()
    matches[2] = f.match("R3", "UNKNOWN", [])
    matches[4] = f.match("R5", "UNKNOWN", [])
    rec = score(profile, config.scoring, f.analysis(reqs), f.matching(matches))
    assert rec.fit == 100.0
    assert "PROFILE_EVIDENCE_UNKNOWN" in rec.uncertainty_factors
    assert rec.confidence_score < 1.0


def test_fit_is_unranked_when_nothing_is_known(
    profile: CareerProfile, config: SearchConfig
) -> None:
    analysis = f.analysis([], inferred_seniority="UNKNOWN")
    rec = score(profile, config.scoring, analysis, f.matching([], direction="UNKNOWN"))
    assert rec.fit is None
    assert rec.priority == "UNRANKED"
    assert rec.priority_score is None
    assert {"NO_REQUIREMENTS_EXTRACTED", "MOST_FIT_COMPONENTS_UNKNOWN"} <= set(
        rec.uncertainty_factors
    )
    assert rec.confidence == "LOW"


@pytest.mark.parametrize(
    ("seniority", "targets", "expected"),
    [
        ("VP", ["VP", "HEAD_OF"], 1.0),
        ("C_LEVEL", ["VP"], 0.7),
        ("DIRECTOR", ["VP"], 0.0),
        ("SENIOR_DIRECTOR", ["VP"], 0.5),
        ("VP", ["UNKNOWN"], 1.0),
    ],
)
def test_seniority_component(
    profile: CareerProfile,
    config: SearchConfig,
    seniority: str,
    targets: list[str],
    expected: float,
) -> None:
    custom = profile.model_copy(update={"target_seniority": targets})
    analysis = f.analysis([], inferred_seniority=seniority)
    rec = score(custom, config.scoring, analysis, f.matching([]))
    component = next(c for c in rec.components if c.name == "SENIORITY_SCOPE")
    assert component.value == pytest.approx(expected)


def test_inferred_level_caps_scope_requirements(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs = [f.requirement("R1", category="SENIORITY_SCOPE")]
    rec = score(
        profile,
        config.scoring,
        f.analysis(reqs, inferred_seniority="BELOW_DIRECTOR"),
        f.matching([f.match("R1")]),
    )
    component = next(c for c in rec.components if c.name == "SENIORITY_SCOPE")
    assert component.value == 0.0
    assert "SENIORITY_SCOPE_GAP" in rec.reason_codes


def test_negative_signals_and_core_gaps_reduce_fit(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs, matches = all_categories()
    matches[0] = f.match("R1", "NO_MATCH", [])
    analysis = f.analysis(
        reqs,
        negative_signals=[
            {"code": "QUOTA_CARRYING", "quote": "q"},
            {"code": "QUOTA_CARRYING", "quote": "q2"},
            {"code": "HANDS_ON_CODING", "quote": "c"},
        ],
    )
    rec = score(profile, config.scoring, analysis, f.matching(matches))
    assert rec.negative_penalty == 2 * 8 + 10
    assert {
        "SALES_QUOTA_CONCERN",
        "HANDS_ON_CONCERN",
        "CORE_REQUIREMENT_GAP",
        "ROLE_RESPONSIBILITY_GAP",
    } <= set(rec.reason_codes)


def test_weights_follow_importance_and_classification(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs = [
        f.requirement("R1", category="CAPABILITY", importance="CORE"),
        f.requirement("R2", category="CAPABILITY", importance="MINOR", classification="PREFERRED"),
    ]
    matches = [f.match("R1", "STRONG_MATCH"), f.match("R2", "NO_MATCH", [])]
    rec = score(profile, config.scoring, f.analysis(reqs), f.matching(matches))
    capability = next(c for c in rec.components if c.name == "CAPABILITY")
    assert capability.value == pytest.approx(3 / (3 + 0.3))


@pytest.mark.parametrize(
    ("comp", "minimum", "preferred", "expected"),
    [
        ((None, None), 280000, 350000, "UNKNOWN"),
        ((200000, None), None, None, "UNKNOWN"),
        ((200000, 250000), 280000, 350000, "BELOW_MINIMUM"),
        ((300000, None), 280000, 350000, "BELOW_PREFERENCE"),
        ((300000, 380000), 280000, 350000, "STRONG"),
        ((300000, 380000), 280000, None, "ACCEPTABLE"),
        ((None, 300000), None, 350000, "BELOW_PREFERENCE"),
    ],
)
def test_compensation_fit(
    profile: CareerProfile,
    comp: tuple[float | None, float | None],
    minimum: float | None,
    preferred: float | None,
    expected: str,
) -> None:
    custom = profile.model_copy(
        update={
            "compensation": profile.compensation.model_copy(
                update={"minimum": minimum, "preferred": preferred}
            )
        }
    )
    assert compensation_fit(facts(comp=comp), custom) == expected


def test_hard_compensation_minimum_excludes(profile: CareerProfile, config: SearchConfig) -> None:
    custom = profile.model_copy(
        update={
            "compensation": profile.compensation.model_copy(update={"minimum_is_hard_filter": True})
        }
    )
    rec = score(custom, config.scoring, job=facts(comp=(150000, 200000)))
    assert rec.priority == "EXCLUDED"
    assert "COMPENSATION_CONCERN" in rec.reason_codes


@pytest.mark.parametrize(
    ("age", "band"), [(1, "IMMEDIATE"), (5, "HIGH"), (20, "HIGH"), (60, "HIGH")]
)
def test_freshness_affects_priority_not_fit(
    profile: CareerProfile, config: SearchConfig, age: int, band: str
) -> None:
    rec = score(profile, config.scoring, job=facts(age_days=age))
    assert rec.fit == 100.0
    assert rec.priority == band
    assert rec.age_days == age


def test_first_seen_is_used_when_posting_date_is_unknown(
    profile: CareerProfile, config: SearchConfig
) -> None:
    rec = score(profile, config.scoring, job=facts(age_days=4, posted=False))
    assert rec.age_days == 4


def test_low_confidence_caps_priority(profile: CareerProfile, config: SearchConfig) -> None:
    reqs, matches = all_categories()
    analysis = f.analysis(
        reqs,
        analysis_confidence="LOW",
        ambiguities=["a", "b", "c", "d"],
        missing_information=["COMPENSATION", "ORG_SCOPE", "TEAM_SIZE", "BUDGET"],
    )
    rec = score(profile, config.scoring, analysis, f.matching(matches))
    assert rec.confidence == "LOW"
    assert rec.priority == "MEDIUM"
    assert "AMBIGUOUS_POSTING" in rec.uncertainty_factors


def test_medium_confidence_band(profile: CareerProfile, config: SearchConfig) -> None:
    reqs, matches = all_categories()
    analysis = f.analysis(
        reqs, analysis_confidence="MEDIUM", missing_information=["COMPENSATION", "BUDGET"]
    )
    rec = score(profile, config.scoring, analysis, f.matching(matches))
    assert rec.confidence == "MEDIUM"
    assert "ANALYSIS_CONFIDENCE_MEDIUM" in rec.uncertainty_factors


def test_middling_fit_cannot_reach_top_bands(profile: CareerProfile, config: SearchConfig) -> None:
    reqs, matches = all_categories("GOOD_MATCH")
    rec = score(profile, config.scoring, f.analysis(reqs), f.matching(matches, direction="LATERAL"))
    assert rec.fit is not None
    assert rec.fit < 85
    assert rec.priority in ("HIGH", "MEDIUM")
    weak_reqs, weak = all_categories("WEAK_MATCH")
    rec = score(profile, config.scoring, f.analysis(weak_reqs), f.matching(weak, direction="AWAY"))
    assert rec.priority == "LOW"


@pytest.mark.parametrize(
    ("location", "reason"),
    [("UNDESIRABLE", "LOCATION_CONCERN"), ("ACCEPTABLE", None), ("UNKNOWN", None)],
)
def test_location_reasons(
    profile: CareerProfile, config: SearchConfig, location: str, reason: str | None
) -> None:
    rec = score(profile, config.scoring, job=facts(location=location))
    assert rec.location_fit == location
    if reason:
        assert reason in rec.reason_codes
    assert "PREFERRED_LOCATION" not in rec.reason_codes


def networked(network: NetworkFacts | None, **kwargs: Any) -> JobFacts:
    return dataclasses.replace(facts(**kwargs), network=network)


def test_a_matured_connection_raises_priority_but_never_fit(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs, matches = all_categories("GOOD_MATCH")
    args = (f.analysis(reqs), f.matching(matches))
    alone = score(profile, config.scoring, *args, job=networked(None, age_days=10))
    known = score(profile, config.scoring, *args, job=networked(NetworkFacts(4, 1, 0), age_days=10))
    assert known.fit == alone.fit
    assert alone.priority_score is not None
    assert known.priority_score == round(alone.priority_score + 10, 1)
    assert known.network_boost == 10
    assert "MATURED_CONNECTION" in known.reason_codes
    assert alone.network_boost == 0


def test_connections_without_a_matured_one_add_a_little(
    profile: CareerProfile, config: SearchConfig
) -> None:
    rec = score(profile, config.scoring, job=networked(NetworkFacts(3, 0, 1)))
    assert rec.network_boost == 3
    assert {"FIRST_DEGREE_CONNECTIONS", "NETWORK_DECISION_NEEDED"} <= set(rec.reason_codes)
    assert "MATURED_CONNECTION" not in rec.reason_codes
    none = score(profile, config.scoring, job=networked(NetworkFacts(0, 0, 0)))
    assert none.network_boost == 0
    assert not {"FIRST_DEGREE_CONNECTIONS", "MATURED_CONNECTION"} & set(none.reason_codes)


def test_priority_score_is_capped_at_100(profile: CareerProfile, config: SearchConfig) -> None:
    rec = score(profile, config.scoring, job=networked(NetworkFacts(1, 1, 0), comp=(None, 400000)))
    assert rec.priority_score == 100.0


def test_a_strong_network_cannot_lift_a_weak_fit_to_the_top(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs, weak = all_categories("WEAK_MATCH")
    rec = score(
        profile,
        config.scoring,
        f.analysis(reqs),
        f.matching(weak, direction="AWAY"),
        job=networked(NetworkFacts(12, 12, 0)),
    )
    assert rec.fit is not None
    assert rec.fit < 60
    assert rec.priority in ("MEDIUM", "LOW")


def test_no_boost_is_recorded_for_an_unranked_role(
    profile: CareerProfile, config: SearchConfig
) -> None:
    rec = score(
        profile,
        config.scoring,
        f.analysis([], inferred_seniority="UNKNOWN"),
        f.matching([], direction="UNKNOWN"),
        job=networked(NetworkFacts(1, 1, 0)),
    )
    assert rec.priority == "UNRANKED"
    assert rec.network_boost == 0.0


def test_network_boost_config_is_optional_and_bounded(config: SearchConfig) -> None:
    data = config.scoring.model_dump()
    del data["network_priority_boost"]
    assert ScoringConfig.model_validate(data).network_priority_boost == {}
    for bad in ({"MATURED": -1}, {"MATURED": 50}, {"OTHER": 1}):
        with pytest.raises(ValidationError):
            ScoringConfig.model_validate({**data, "network_priority_boost": bad})


def test_a_role_below_the_network_minimum_fit_gains_no_priority(
    profile: CareerProfile, config: SearchConfig
) -> None:
    reqs, weak = all_categories("PARTIAL_MATCH")
    args = (f.analysis(reqs), f.matching(weak, direction="LATERAL"))
    alone = score(profile, config.scoring, *args, job=networked(None))
    known = score(profile, config.scoring, *args, job=networked(NetworkFacts(12, 5, 0)))
    assert alone.fit is not None
    assert alone.fit < config.scoring.network_min_fit
    assert known.network_boost == 0.0
    assert known.priority_score == alone.priority_score
    assert "MATURED_CONNECTION" in known.reason_codes
