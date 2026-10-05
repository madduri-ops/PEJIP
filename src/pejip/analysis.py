"""Structured job analysis and requirement-to-evidence matching (spec 9.1 to 9.4).

AI interprets; the validation here makes sure what it returns is grounded before
scoring sees it (spec 14.43): requirement and signal quotes must appear in the
posting, requirement ids must be known, and evidence ids must exist in the profile.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from pejip.ai.client import AIClient, AIError
from pejip.ai.prompts import load_prompt
from pejip.profile import CareerProfile, Seniority

ANALYSIS_SCHEMA_VERSION = "job-analysis-1"
MATCHING_SCHEMA_VERSION = "evidence-matching-1"
MIN_GROUNDED_SHARE = 0.5

Category = Literal[
    "ROLE_RESPONSIBILITY", "SENIORITY_SCOPE", "CAPABILITY", "LEADERSHIP", "DOMAIN_INDUSTRY"
]
Classification = Literal["REQUIRED", "PREFERRED", "CONTEXTUAL", "INFERRED"]
Importance = Literal["CORE", "IMPORTANT", "SUPPORTING", "MINOR"]
Scope = Literal["ENTERPRISE", "MULTI_BUSINESS_UNIT", "BUSINESS_UNIT", "FUNCTION", "TEAM", "UNKNOWN"]
WorkModel = Literal["REMOTE", "HYBRID", "ONSITE", "FLEXIBLE", "UNKNOWN"]
NegativeCode = Literal[
    "QUOTA_CARRYING", "SALES_HEAVY", "HANDS_ON_CODING", "INDIVIDUAL_CONTRIBUTOR", "OTHER"
]
MissingInfo = Literal[
    "COMPENSATION", "ORG_SCOPE", "TEAM_SIZE", "BUDGET", "REPORTING_LINE", "WORK_MODEL", "LOCATION"
]
Level = Literal["HIGH", "MEDIUM", "LOW"]


class UngroundedAnalysisError(AIError):
    """Most extracted requirements quote text that is not in the posting."""

    def __init__(self) -> None:
        super().__init__("most requirements were not grounded in the posting")


Strength = Literal[
    "STRONG_MATCH", "GOOD_MATCH", "PARTIAL_MATCH", "WEAK_MATCH", "NO_MATCH", "UNKNOWN"
]
Direction = Literal["ADVANCES", "ALIGNED", "LATERAL", "AWAY", "UNKNOWN"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Requirement(_Strict):
    id: str
    text: str
    category: Category
    classification: Classification
    importance: Importance
    quote: str


class ScopeSignal(_Strict):
    quote: str


class NegativeSignal(_Strict):
    code: NegativeCode
    quote: str


class JobAnalysis(_Strict):
    normalized_title: str
    role_family: str
    inferred_seniority: Seniority
    inferred_scope: Scope
    work_model: WorkModel
    requirements: list[Requirement]
    positive_scope_signals: list[ScopeSignal]
    negative_signals: list[NegativeSignal]
    ambiguities: list[str]
    missing_information: list[MissingInfo]
    analysis_confidence: Level


class RequirementMatch(_Strict):
    requirement_id: str
    match_strength: Strength
    evidence_ids: list[str]
    rationale: str


class EvidenceMatching(_Strict):
    matches: list[RequirementMatch]
    career_direction: Direction
    career_direction_evidence_ids: list[str]


@dataclass(frozen=True)
class AnalysisOutcome:
    analysis: JobAnalysis
    matching: EvidenceMatching
    provenance: dict[str, object]
    dropped_requirements: int


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in(quote: str, posting_text: str) -> bool:
    """Is ``quote`` a verbatim (whitespace- and case-insensitive) passage of the posting?"""
    q = _squash(quote)
    return bool(q) and q in _squash(posting_text)


def ground_analysis(analysis: JobAnalysis, posting_text: str) -> tuple[JobAnalysis, int]:
    """Drop requirements and signals whose quotes are not in the posting."""
    seen: set[str] = set()
    kept: list[Requirement] = []
    for req in analysis.requirements:
        if req.id not in seen and quote_in(req.quote, posting_text):
            kept.append(req)
            seen.add(req.id)
    dropped = len(analysis.requirements) - len(kept)
    if analysis.requirements and len(kept) / len(analysis.requirements) < MIN_GROUNDED_SHARE:
        raise UngroundedAnalysisError
    grounded = analysis.model_copy(
        update={
            "requirements": kept,
            "positive_scope_signals": [
                s for s in analysis.positive_scope_signals if quote_in(s.quote, posting_text)
            ],
            "negative_signals": [
                s for s in analysis.negative_signals if quote_in(s.quote, posting_text)
            ],
        }
    )
    return grounded, dropped


def ground_matching(
    matching: EvidenceMatching, analysis: JobAnalysis, profile: CareerProfile
) -> EvidenceMatching:
    """Keep one match per known requirement; unsupported matches become UNKNOWN."""
    known_evidence = set(profile.evidence_by_id())
    by_req: dict[str, RequirementMatch] = {}
    for match in matching.matches:
        if match.requirement_id in by_req:
            continue
        evidence = [e for e in match.evidence_ids if e in known_evidence]
        strength = match.match_strength
        if strength not in ("NO_MATCH", "UNKNOWN") and not evidence:
            strength = "UNKNOWN"
        by_req[match.requirement_id] = match.model_copy(
            update={"evidence_ids": evidence, "match_strength": strength}
        )
    matches = [
        by_req.get(req.id)
        or RequirementMatch(
            requirement_id=req.id,
            match_strength="UNKNOWN",
            evidence_ids=[],
            rationale="No assessment returned.",
        )
        for req in analysis.requirements
    ]
    direction_evidence = [e for e in matching.career_direction_evidence_ids if e in known_evidence]
    return matching.model_copy(
        update={"matches": matches, "career_direction_evidence_ids": direction_evidence}
    )


def _posting_message(title: str, company: str, location: str, description: str) -> str:
    return (
        f"<posting>\nTitle: {title}\nCompany: {company}\nLocation: {location}\n\n"
        f"{description}\n</posting>"
    )


@dataclass(frozen=True)
class PostingText:
    """The parts of a stored posting the model reads."""

    title: str
    company: str
    location: str
    description: str

    @classmethod
    def from_job(cls, job: Mapping[str, Any]) -> PostingText:
        return cls(job["title"], job["company"], job["location"], job["description"])


def analysis_input(posting: PostingText) -> str:
    """What the job analysis step reads: the posting, marked up as the prompt expects."""
    return _posting_message(posting.title, posting.company, posting.location, posting.description)


def matching_input(profile: CareerProfile, analysis: JobAnalysis) -> str:
    """What the evidence matching step reads: the profile and the grounded requirements."""
    requirements = "\n".join(
        f"- {r.id} [{r.category}, {r.classification}, {r.importance}]: {r.text}"
        for r in analysis.requirements
    )
    return (
        f"<career_profile>\n{profile.ai_view()}</career_profile>\n\n"
        f"<job>\nTitle: {analysis.normalized_title}\nRequirements:\n{requirements}\n</job>"
    )


def analyze_job(ai: AIClient, profile: CareerProfile, posting: PostingText) -> AnalysisOutcome:
    """Run job analysis then evidence matching, validating each step."""
    posting_text = analysis_input(posting)
    analysed = ai.structured(
        feature="job_analysis",
        prompt=load_prompt("JOB_ANALYSIS"),
        content=posting_text,
        schema=JobAnalysis,
        schema_version=ANALYSIS_SCHEMA_VERSION,
    )
    analysis, dropped = ground_analysis(analysed.output, posting_text)
    matched = ai.structured(
        feature="evidence_matching",
        prompt=load_prompt("EVIDENCE_MATCHING"),
        content=matching_input(profile, analysis),
        schema=EvidenceMatching,
        schema_version=MATCHING_SCHEMA_VERSION,
    )
    matching = ground_matching(matched.output, analysis, profile)
    return AnalysisOutcome(
        analysis=analysis,
        matching=matching,
        provenance={"analysis": analysed.provenance(), "matching": matched.provenance()},
        dropped_requirements=dropped,
    )
