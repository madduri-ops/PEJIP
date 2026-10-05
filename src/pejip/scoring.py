"""Deterministic Fit, Confidence and Priority (spec 9.5 to 9.31, 14.35).

AI supplies structured judgements; this module owns every number. Fit uses only
career evidence. Freshness, compensation and location affect Priority only, and
unknown inputs are left out of an average rather than counted as negative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from pejip.analysis import EvidenceMatching, JobAnalysis, Requirement, RequirementMatch
from pejip.config import ScoringConfig
from pejip.profile import CareerProfile

STRENGTH_VALUE = {
    "STRONG_MATCH": 1.0,
    "GOOD_MATCH": 0.8,
    "PARTIAL_MATCH": 0.5,
    "WEAK_MATCH": 0.25,
    "NO_MATCH": 0.0,
}
IMPORTANCE_WEIGHT = {"CORE": 3.0, "IMPORTANT": 2.0, "SUPPORTING": 1.0, "MINOR": 0.5}
CLASSIFICATION_WEIGHT = {"REQUIRED": 1.0, "PREFERRED": 0.6, "CONTEXTUAL": 0.4, "INFERRED": 0.4}
SENIORITY_RANK = {
    "C_LEVEL": 6,
    "SVP": 5,
    "VP": 4,
    "HEAD_OF": 4,
    "SENIOR_DIRECTOR": 3,
    "DIRECTOR": 2,
    "BELOW_DIRECTOR": 1,
}
DIRECTION_VALUE = {"ADVANCES": 1.0, "ALIGNED": 0.8, "LATERAL": 0.5, "AWAY": 0.1}
# Priority freshness by posting age: (maximum age in days, value).
FRESH_POSTING_DAYS = 2
FRESHNESS_STEPS = ((FRESH_POSTING_DAYS, 1.0), (7, 0.7), (30, 0.4))
STALE_FRESHNESS = 0.2
# Below this share of Fit weight with known values, confidence drops.
MIN_KNOWN_FIT_WEIGHT = 0.5
LOCATION_VALUE = {"PREFERRED": 1.0, "ACCEPTABLE": 0.7, "UNDESIRABLE": 0.2}
COMPENSATION_VALUE = {
    "STRONG": 1.0,
    "ACCEPTABLE": 0.8,
    "BELOW_PREFERENCE": 0.4,
    "BELOW_MINIMUM": 0.0,
}
COMPONENT_REASON = {
    "ROLE_RESPONSIBILITY": "STRONG_ROLE_MATCH",
    "CAPABILITY": "STRONG_CAPABILITY_MATCH",
    "LEADERSHIP": "LEADERSHIP_MATCH",
    "SENIORITY_SCOPE": "EXECUTIVE_SCOPE_MATCH",
    "CAREER_DIRECTION": "CAREER_DIRECTION_MATCH",
}
NEGATIVE_REASON = {
    "QUOTA_CARRYING": "SALES_QUOTA_CONCERN",
    "SALES_HEAVY": "SALES_HEAVY_CONCERN",
    "HANDS_ON_CODING": "HANDS_ON_CONCERN",
    "INDIVIDUAL_CONTRIBUTOR": "INDIVIDUAL_CONTRIBUTOR_CONCERN",
    "OTHER": "NEGATIVE_SIGNAL",
}
BAND_BELOW = {"IMMEDIATE": "HIGH", "HIGH": "MEDIUM", "MEDIUM": "LOW"}
STRONG_COMPONENT = 0.8
WEAK_COMPONENT = 0.4


@dataclass(frozen=True)
class Component:
    name: str
    value: float | None
    weight: float
    evidence_ids: list[str]


@dataclass(frozen=True)
class NetworkFacts:
    """Who the candidate knows at the hiring company (spec 9.22, design doc 0014).

    Counts of first-degree connections there, of those that are matured for this
    role, and of those whose level waits on the candidate's call. Priority only.
    """

    first_degree: int
    matured: int
    your_call: int


@dataclass(frozen=True)
class JobFacts:
    """Stored facts about the posting that Priority uses (not career evidence).

    ``as_of`` is the moment the role is scored; posting age is measured from it.
    """

    posted_at: datetime | None
    first_seen_at: datetime
    comp_min: float | None
    comp_max: float | None
    location_preference: str  # PREFERRED, ACCEPTABLE, UNDESIRABLE or UNKNOWN
    as_of: datetime
    network: NetworkFacts | None = None


@dataclass(frozen=True)
class Recommendation:
    fit: float | None
    components: list[Component]
    negative_penalty: float
    confidence: str
    confidence_score: float
    uncertainty_factors: list[str]
    priority: str
    priority_score: float | None
    age_days: int
    compensation_fit: str
    location_fit: str
    reason_codes: list[str] = field(default_factory=list)
    scoring_version: str = ""
    network_boost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _weighted_strength(
    pairs: list[tuple[Requirement, RequirementMatch]],
) -> tuple[float | None, list[str]]:
    """Importance-weighted mean match strength; UNKNOWN matches are left out."""
    total = weight_sum = 0.0
    evidence: list[str] = []
    for req, match in pairs:
        value = STRENGTH_VALUE.get(match.match_strength)
        if value is None:
            continue
        weight = IMPORTANCE_WEIGHT[req.importance] * CLASSIFICATION_WEIGHT[req.classification]
        total += value * weight
        weight_sum += weight
        evidence.extend(e for e in match.evidence_ids if e not in evidence)
    if weight_sum == 0:
        return None, evidence
    return total / weight_sum, evidence


def _seniority_value(analysis: JobAnalysis, profile: CareerProfile) -> float | None:
    rank = SENIORITY_RANK.get(analysis.inferred_seniority)
    if rank is None:
        return None
    targets = [SENIORITY_RANK[t] for t in profile.target_seniority if t in SENIORITY_RANK]
    if not targets or min(targets) <= rank <= max(targets):
        return 1.0
    if rank > max(targets):
        return 0.7
    return max(0.0, 1.0 - 0.5 * (min(targets) - rank))


def fit_components(
    analysis: JobAnalysis, matching: EvidenceMatching, profile: CareerProfile, cfg: ScoringConfig
) -> list[Component]:
    match_by_id = {m.requirement_id: m for m in matching.matches}
    components: list[Component] = []
    for name, weight in cfg.fit_weights.items():
        pairs = [
            (r, match_by_id[r.id])
            for r in analysis.requirements
            if r.category == name and r.id in match_by_id
        ]
        value, evidence = _weighted_strength(pairs)
        if name == "SENIORITY_SCOPE":
            # Meeting a role's stated scope does not make a junior role a fit, so
            # the inferred level caps what the scope requirements can contribute.
            level = _seniority_value(analysis, profile)
            parts = [v for v in (value, level) if v is not None]
            value = min(parts) if parts else None
        elif name == "CAREER_DIRECTION":
            value = DIRECTION_VALUE.get(matching.career_direction)
            evidence = list(matching.career_direction_evidence_ids)
        components.append(Component(name, value, weight, evidence))
    return components


def compensation_fit(facts: JobFacts, profile: CareerProfile) -> str:
    pref = profile.compensation
    top = facts.comp_max if facts.comp_max is not None else facts.comp_min
    if top is None or (pref.minimum is None and pref.preferred is None):
        return "UNKNOWN"
    if pref.minimum is not None and top < pref.minimum:
        return "BELOW_MINIMUM"
    if pref.preferred is not None and top < pref.preferred:
        return "BELOW_PREFERENCE"
    if pref.preferred is not None:
        return "STRONG"
    return "ACCEPTABLE"


def _freshness(age_days: int) -> float:
    for max_age, value in FRESHNESS_STEPS:
        if age_days <= max_age:
            return value
    return STALE_FRESHNESS


def _confidence(
    analysis: JobAnalysis, matching: EvidenceMatching, components: list[Component]
) -> tuple[float, list[str]]:
    score = 1.0
    factors: list[str] = []
    if analysis.missing_information:
        score -= min(0.3, 0.1 * len(analysis.missing_information))
        factors.append("POSTING_MISSING_" + "_".join(sorted(analysis.missing_information)))
    if matching.matches:
        unknown = sum(m.match_strength == "UNKNOWN" for m in matching.matches)
        share = unknown / len(matching.matches)
        if share:
            score -= 0.4 * share
            factors.append("PROFILE_EVIDENCE_UNKNOWN")
    else:
        score -= 0.4
        factors.append("NO_REQUIREMENTS_EXTRACTED")
    score -= {"HIGH": 0.0, "MEDIUM": 0.1, "LOW": 0.2}[analysis.analysis_confidence]
    if analysis.analysis_confidence != "HIGH":
        factors.append(f"ANALYSIS_CONFIDENCE_{analysis.analysis_confidence}")
    if analysis.ambiguities:
        score -= min(0.15, 0.05 * len(analysis.ambiguities))
        factors.append("AMBIGUOUS_POSTING")
    total_weight = sum(c.weight for c in components)
    known_weight = sum(c.weight for c in components if c.value is not None)
    if total_weight and known_weight / total_weight < MIN_KNOWN_FIT_WEIGHT:
        score -= 0.2
        factors.append("MOST_FIT_COMPONENTS_UNKNOWN")
    return max(0.0, round(score, 3)), factors


def _network_boost(network: NetworkFacts | None, cfg: ScoringConfig) -> tuple[float, list[str]]:
    """Priority points and reasons from the network; it never touches Fit (spec 8.25)."""
    if network is None:
        return 0.0, []
    boost, reasons = 0.0, []
    if network.matured:
        boost = cfg.network_priority_boost.get("MATURED", 0.0)
        reasons.append("MATURED_CONNECTION")
    elif network.first_degree:
        boost = cfg.network_priority_boost.get("CONNECTED", 0.0)
        reasons.append("FIRST_DEGREE_CONNECTIONS")
    if network.your_call:
        reasons.append("NETWORK_DECISION_NEEDED")
    return boost, reasons


def _band(score: float, thresholds: dict[str, float]) -> str:
    for band in ("IMMEDIATE", "HIGH", "MEDIUM"):
        if score >= thresholds[band]:
            return band
    return "LOW"


def score_job(
    analysis: JobAnalysis,
    matching: EvidenceMatching,
    profile: CareerProfile,
    facts: JobFacts,
    cfg: ScoringConfig,
) -> Recommendation:
    components = fit_components(analysis, matching, profile, cfg)
    known = [c for c in components if c.value is not None]
    negatives = sorted({s.code for s in analysis.negative_signals})
    match_by_id = {m.requirement_id: m for m in matching.matches}
    core_gaps = [
        r.id
        for r in analysis.requirements
        if r.importance == "CORE"
        and r.classification == "REQUIRED"
        and r.id in match_by_id
        and match_by_id[r.id].match_strength == "NO_MATCH"
    ]
    penalty = cfg.negative_signal_penalty * len(negatives) + cfg.core_gap_penalty * len(core_gaps)
    fit: float | None = None
    if known:
        raw = sum(c.weight * (c.value or 0.0) for c in known) / sum(c.weight for c in known)
        fit = round(max(0.0, raw * 100 - penalty), 1)

    confidence_score, factors = _confidence(analysis, matching, components)
    th = cfg.confidence_thresholds
    confidence = (
        "HIGH"
        if confidence_score >= th["HIGH"]
        else "MEDIUM"
        if confidence_score >= th["MEDIUM"]
        else "LOW"
    )

    reference = facts.posted_at or facts.first_seen_at
    age_days = max(0, (facts.as_of - reference).days)
    comp = compensation_fit(facts, profile)
    location = facts.location_preference
    reasons = [
        COMPONENT_REASON[c.name]
        for c in known
        if c.name in COMPONENT_REASON and (c.value or 0) >= STRONG_COMPONENT
    ]
    reasons += [f"{c.name}_GAP" for c in known if (c.value or 0) <= WEAK_COMPONENT]
    reasons += [NEGATIVE_REASON[code] for code in negatives]
    if core_gaps:
        reasons.append("CORE_REQUIREMENT_GAP")

    boost, network_reasons = _network_boost(facts.network, cfg)
    reasons += network_reasons

    priority_score: float | None = None
    priority = "UNRANKED"
    hard_excluded = comp == "BELOW_MINIMUM" and profile.compensation.minimum_is_hard_filter
    if fit is not None and not hard_excluded:
        inputs = {
            "FIT": fit / 100,
            "FRESHNESS": _freshness(age_days),
            "COMPENSATION": COMPENSATION_VALUE.get(comp),
            "LOCATION": LOCATION_VALUE.get(location),
        }
        used = {k: v for k, v in inputs.items() if v is not None}
        weights = {k: cfg.priority_weights[k] for k in used}
        weighted = 100 * sum(used[k] * weights[k] for k in used) / sum(weights.values())
        priority_score = round(min(100.0, weighted + boost), 1)
        priority = _band(priority_score, cfg.priority_thresholds)
        # Freshness or location alone must not lift a middling Fit into a top band.
        while priority in cfg.priority_min_fit and fit < cfg.priority_min_fit[priority]:
            priority = BAND_BELOW[priority]
        if priority == "IMMEDIATE" and (
            age_days > cfg.immediate_max_age_days or confidence == "LOW"
        ):
            priority = "HIGH"
        if confidence == "LOW" and priority == "HIGH":
            priority = "MEDIUM"
    elif hard_excluded:
        priority = "EXCLUDED"

    if age_days <= FRESH_POSTING_DAYS:
        reasons.append("FRESH_POSTING")
    if comp in ("BELOW_PREFERENCE", "BELOW_MINIMUM"):
        reasons.append("COMPENSATION_CONCERN")
    if location == "PREFERRED":
        reasons.append("PREFERRED_LOCATION")
    elif location == "UNDESIRABLE":
        reasons.append("LOCATION_CONCERN")

    return Recommendation(
        fit=fit,
        components=components,
        negative_penalty=penalty,
        confidence=confidence,
        confidence_score=confidence_score,
        uncertainty_factors=factors,
        priority=priority,
        priority_score=priority_score,
        age_days=age_days,
        compensation_fit=comp,
        location_fit=location,
        reason_codes=reasons,
        scoring_version=cfg.version,
        network_boost=boost if priority_score is not None else 0.0,
    )
