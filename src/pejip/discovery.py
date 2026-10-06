"""Deterministic discovery filter: role family, level and geography (spec 3, 4).

This runs before any AI call, so only plausibly senior roles in scope cost money.
Final relevance is decided later by matching and scoring.

A title is one signal of level, not a gate (Babu, 2026-10-06): levels differ by
company, so a Meta Director can match a Yahoo VP. A role in one of the role
families is kept when its title reads as senior, when it came from one of Babu's
own job alerts (he chose those searches), or when its posted pay reaches his
minimum. Posted pay below his minimum rules a role out whatever its title. An
unclear title with no posted pay from a careers board is held back too, and the
run counts both so none is dropped silently.
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
    """A title that reads as senior and names one of the role families."""
    return _senior_title(normalize_title(title), taxonomy) and role_family_matches(title, taxonomy)


def role_family_matches(title: str, taxonomy: TaxonomyConfig) -> bool:
    normalized = normalize_title(title)
    return any(_has_term(normalized, t) for t in taxonomy.role_terms)


def _senior_title(normalized: str, taxonomy: TaxonomyConfig) -> bool:
    if any(_has_term(normalized, p) for p in taxonomy.excluded_title_patterns):
        return False
    return any(_has_term(normalized, p) for p in taxonomy.seniority_patterns)


# Why a posting goes on to ranking, or why it does not.
SENIOR_TITLE = "SENIOR_TITLE"
JOB_ALERT = "JOB_ALERT"
PAY = "PAY"
UNCLEAR_NO_PAY = "UNCLEAR_NO_PAY"
BELOW_PAY = "BELOW_PAY"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
KEPT = frozenset({SENIOR_TITLE, JOB_ALERT, PAY})


def screen(
    posting: Posting,
    taxonomy: TaxonomyConfig,
    geography: GeographyConfig,
    pay_floor: float | None = None,
) -> str:
    """Whether a posting goes on to ranking (a value in ``KEPT``) and on what basis.

    ``pay_floor`` is the profile's minimum pay. Posted pay below it rules a role
    out whatever its title (Babu, 2026-10-06); posted pay at or above it keeps a
    role whose title alone is unclear.
    """
    ineligible = classify_location(posting.location, geography).preference == "INELIGIBLE"
    if ineligible or not role_family_matches(posting.title, taxonomy):
        return OUT_OF_SCOPE
    pay = posting.compensation
    top = None if pay is None else (pay.maximum if pay.maximum is not None else pay.minimum)
    if top is not None and pay_floor is not None and top < pay_floor:
        return BELOW_PAY
    normalized = normalize_title(posting.title)
    excluded = any(_has_term(normalized, p) for p in taxonomy.excluded_title_patterns)
    if _senior_title(normalized, taxonomy):
        return SENIOR_TITLE
    if not excluded and posting.extra.get("origin") == "job_alert_email":
        return JOB_ALERT
    if top is None or pay_floor is None:
        return UNCLEAR_NO_PAY
    return PAY


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


def is_candidate(
    posting: Posting,
    taxonomy: TaxonomyConfig,
    geography: GeographyConfig,
    pay_floor: float | None = None,
) -> bool:
    """Should this posting go on to analysis?"""
    return screen(posting, taxonomy, geography, pay_floor) in KEPT
