"""Builders for synthetic analysis and matching payloads."""

from __future__ import annotations

from typing import Any


def requirement(
    rid: str = "R1",
    *,
    category: str = "ROLE_RESPONSIBILITY",
    classification: str = "REQUIRED",
    importance: str = "CORE",
    quote: str = "Lead technology operations",
) -> dict[str, Any]:
    return {
        "id": rid,
        "text": f"Requirement {rid}",
        "category": category,
        "classification": classification,
        "importance": importance,
        "quote": quote,
    }


def analysis(requirements: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "normalized_title": "vice president technology operations",
        "role_family": "Technology Operations",
        "inferred_seniority": "VP",
        "inferred_scope": "ENTERPRISE",
        "work_model": "UNKNOWN",
        "requirements": requirements if requirements is not None else [requirement()],
        "positive_scope_signals": [],
        "negative_signals": [],
        "ambiguities": [],
        "missing_information": [],
        "analysis_confidence": "HIGH",
    }
    data.update(overrides)
    return data


def match(
    rid: str = "R1", strength: str = "STRONG_MATCH", evidence: list[str] | None = None
) -> dict[str, Any]:
    return {
        "requirement_id": rid,
        "match_strength": strength,
        "evidence_ids": ["E1"] if evidence is None else evidence,
        "rationale": "Synthetic rationale.",
    }


def matching(
    matches: list[dict[str, Any]] | None = None,
    direction: str = "ADVANCES",
    direction_evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "matches": matches if matches is not None else [match()],
        "career_direction": direction,
        "career_direction_evidence_ids": ["E1"]
        if direction_evidence is None
        else direction_evidence,
    }


POSTING_TEXT = (
    "Lead technology operations for a large organization.\n"
    "Own portfolio governance with the executive team.\n"
    "Manage a budget above $30M."
)
