"""Evidence-backed explanations (spec 9.29 to 9.33, policy section 12).

Explanations are built from the already-validated analysis, matches and scores, so
the text never reaches beyond the evidence. Every point carries citations, and
:func:`verify_citations` checks that each one resolves to stored data: a posting
quote that appears in the stored posting, a profile evidence id that exists, or a
stored job field.
"""

from __future__ import annotations

from typing import Any

from pejip.analysis import EvidenceMatching, JobAnalysis, quote_in
from pejip.profile import CareerProfile
from pejip.scoring import Recommendation

POSITIVE = ("STRONG_MATCH", "GOOD_MATCH")
IMPORTANCE_ORDER = {"CORE": 0, "IMPORTANT": 1, "SUPPORTING": 2, "MINOR": 3}
MAX_POINTS = 4
JOB_FIELDS = frozenset({"posted_at", "first_seen_at", "location", "comp_min", "comp_max"})
MISSING_TEXT = {
    "COMPENSATION": "compensation",
    "ORG_SCOPE": "organizational scope",
    "TEAM_SIZE": "team size",
    "BUDGET": "budget responsibility",
    "REPORTING_LINE": "reporting line",
    "WORK_MODEL": "work model",
    "LOCATION": "location",
}


class UnsupportedClaim(Exception):
    """An explanation point cites something that is not in stored data."""


def _point(text: str, citations: list[dict[str, str]]) -> dict[str, Any]:
    return {"text": text, "citations": citations}


def _posting(quote: str) -> dict[str, str]:
    return {"type": "posting", "quote": quote}


def _evidence(evidence_id: str) -> dict[str, str]:
    return {"type": "profile", "evidence_id": evidence_id}


def _job_field(name: str) -> dict[str, str]:
    return {"type": "job_field", "field": name}


def build_explanation(
    analysis: JobAnalysis,
    matching: EvidenceMatching,
    rec: Recommendation,
    job: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    reqs = sorted(analysis.requirements, key=lambda r: IMPORTANCE_ORDER[r.importance])
    match_by_id = {m.requirement_id: m for m in matching.matches}

    fits: list[dict[str, Any]] = []
    concerns: list[dict[str, Any]] = []
    for req in reqs:
        match = match_by_id[req.id]
        if match.match_strength in POSITIVE and len(fits) < MAX_POINTS:
            label = "Strong" if match.match_strength == "STRONG_MATCH" else "Good"
            fits.append(
                _point(
                    f"{label} match: {req.text}",
                    [_posting(req.quote)] + [_evidence(e) for e in match.evidence_ids],
                )
            )
        elif req.importance in ("CORE", "IMPORTANT") and len(concerns) < MAX_POINTS:
            if match.match_strength in ("NO_MATCH", "WEAK_MATCH"):
                concerns.append(
                    _point(
                        f"Gap: {req.text}",
                        [_posting(req.quote)] + [_evidence(e) for e in match.evidence_ids],
                    )
                )
            elif match.match_strength == "UNKNOWN":
                concerns.append(
                    _point(
                        f"Not enough profile evidence to judge: {req.text}",
                        [_posting(req.quote)],
                    )
                )
    for signal in analysis.negative_signals:
        concerns.append(
            _point(f"Possible negative fit ({signal.code.lower()})", [_posting(signal.quote)])
        )
    if analysis.missing_information:
        missing = ", ".join(MISSING_TEXT[m] for m in analysis.missing_information)
        concerns.append(_point(f"The posting does not state: {missing}", []))
    if rec.compensation_fit in ("BELOW_PREFERENCE", "BELOW_MINIMUM"):
        concerns.append(
            _point(
                "Stated pay is below your "
                + ("minimum" if rec.compensation_fit == "BELOW_MINIMUM" else "preferred level"),
                [_job_field("comp_max" if job.get("comp_max") is not None else "comp_min")],
            )
        )

    now_points: list[dict[str, Any]] = []
    when = "posted_at" if job.get("posted_at") else "first_seen_at"
    verb = "Posted" if when == "posted_at" else "First seen"
    age = "today" if rec.age_days == 0 else f"{rec.age_days} days ago"
    now_points.append(_point(f"{verb} {age}", [_job_field(when)]))
    if rec.location_fit in ("PREFERRED", "ACCEPTABLE"):
        word = "Preferred" if rec.location_fit == "PREFERRED" else "Acceptable"
        now_points.append(_point(f"{word} location: {job['location']}", [_job_field("location")]))
    if rec.compensation_fit in ("STRONG", "ACCEPTABLE"):
        field = "comp_max" if job.get("comp_max") is not None else "comp_min"
        now_points.append(_point("Stated pay meets your preference", [_job_field(field)]))

    return {
        "why_it_fits": fits,
        "concerns": concerns,
        "why_now": now_points,
        "who_you_know": [_point("Network data has not been imported yet.", [])],
    }


def verify_citations(
    explanation: dict[str, list[dict[str, Any]]], job: dict[str, Any], profile: CareerProfile
) -> None:
    """Raise :class:`UnsupportedClaim` if any citation does not resolve."""
    evidence_ids = set(profile.evidence_by_id())
    posting_text = "\n".join([job["title"], job["company"], job["location"], job["description"]])
    for section in explanation.values():
        for point in section:
            for cite in point["citations"]:
                kind = cite["type"]
                if kind == "posting" and quote_in(cite["quote"], posting_text):
                    continue
                if kind == "profile" and cite["evidence_id"] in evidence_ids:
                    continue
                if (
                    kind == "job_field"
                    and cite["field"] in JOB_FIELDS
                    and job.get(cite["field"]) is not None
                ):
                    continue
                raise UnsupportedClaim(f"unresolved citation {cite!r} for {point['text']!r}")
