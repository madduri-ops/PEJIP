"""Deterministic discovery filter: taxonomy titles and geography (spec 3, 4).

This runs before any AI call, so only plausibly senior roles in scope cost money.
Final relevance is decided later by matching and scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pejip.config import GeographyConfig, TaxonomyConfig
from pejip.models import Posting

_TITLE_VARIANTS = [
    (re.compile(r"\bs\.?v\.?p\.?(?=\W|$)"), "senior vice president"),
    (re.compile(r"\be\.?v\.?p\.?(?=\W|$)"), "executive vice president"),
    (re.compile(r"\bv\.?p\.?(?=\W|$)"), "vice president"),
    (re.compile(r"\bsr\.?(?=\W|$)"), "senior"),
    (re.compile(r"\bdir\.?(?=\W|$)"), "director"),
]
_US_MARKERS = ("united states", "usa", "u.s.", " us", "us ", "(us)", "us-", "-us", "north america")
_NON_US_MARKERS = (
    "canada",
    "uk",
    "united kingdom",
    "london",
    "ireland",
    "dublin",
    "germany",
    "india",
    "emea",
    "apac",
    "europe",
    "latam",
    "mexico",
    "brazil",
    "japan",
    "singapore",
    "australia",
)


def normalize_title(title: str) -> str:
    """Lower-case a title and expand VP / Sr. style variants (spec 3.3)."""
    text = title.lower()
    for pattern, replacement in _TITLE_VARIANTS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def _has_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text) is not None


def title_matches(title: str, taxonomy: TaxonomyConfig) -> bool:
    normalized = normalize_title(title)
    if any(_has_term(normalized, p) for p in taxonomy.excluded_title_patterns):
        return False
    if not any(_has_term(normalized, p) for p in taxonomy.seniority_patterns):
        return False
    return any(_has_term(normalized, t) for t in taxonomy.role_terms)


@dataclass(frozen=True)
class GeoMatch:
    scope: str | None
    preference: str  # PREFERRED, ACCEPTABLE, UNDESIRABLE, INELIGIBLE or UNKNOWN


def classify_location(location: str, geography: GeographyConfig) -> GeoMatch:
    """Place a posting's location in a configured scope (spec 4.2, 4.3, 4.7)."""
    text = f" {location.lower()} "
    if not location.strip():
        return GeoMatch(None, "UNKNOWN")
    for name, scope in geography.scopes.items():
        if any(_has_term(text, place) for place in scope.places):
            return GeoMatch(name, scope.preference)
    remote_scope = geography.scopes.get("US_REMOTE")
    if remote_scope is not None and "remote" in text:
        non_us = any(_has_term(text, m) for m in _NON_US_MARKERS)
        us = any(m in text for m in _US_MARKERS)
        if us or not non_us:
            return GeoMatch("US_REMOTE", remote_scope.preference)
    return GeoMatch(None, "INELIGIBLE" if geography.hard_filter else "UNDESIRABLE")


def is_candidate(posting: Posting, taxonomy: TaxonomyConfig, geography: GeographyConfig) -> bool:
    """Should this posting go on to analysis?"""
    if not title_matches(posting.title, taxonomy):
        return False
    return classify_location(posting.location, geography).preference != "INELIGIBLE"
