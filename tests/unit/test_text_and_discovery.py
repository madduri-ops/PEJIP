from __future__ import annotations

import pytest

from pejip.config import GeographyConfig, GeoScope, SearchConfig
from pejip.discovery import classify_location, is_candidate, normalize_title, title_matches
from pejip.models import Posting
from pejip.sources.text import extract_salary_range, html_to_text


def test_html_to_text_handles_escaped_markup_and_lists() -> None:
    escaped = (
        "&lt;p&gt;Lead&amp;nbsp;ops&lt;/p&gt;"
        "&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;li&gt;Two&lt;/li&gt;&lt;/ul&gt;"
    )
    assert html_to_text(escaped) == "Lead ops\n\n- One\n\n- Two"
    assert html_to_text("<div>A</div><br><div>B</div>") == "A\n\nB"
    assert html_to_text("plain   text") == "plain text"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pay: $250,000 - $300,000 per year", (250000.0, 300000.0)),
        ("Range $280k\N{EN DASH}$340k plus equity", (280000.0, 340000.0)),
        ("$310.5K to $350K", (310500.0, 350000.0)),
        ("Stipend $10,000 - $20,000, salary $200,000 - $260,000", (200000.0, 260000.0)),
        ("$300,000 - $200,000", None),
        ("No pay stated", None),
    ],
)
def test_extract_salary_range(text: str, expected: tuple[float, float] | None) -> None:
    assert extract_salary_range(text) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("VP, Technology Operations", "vice president, technology operations"),
        ("V.P. Product Ops", "vice president product ops"),
        ("SVP Engineering", "senior vice president engineering"),
        ("EVP, Strategy", "executive vice president, strategy"),
        ("Sr. Director   Programs", "senior director programs"),
        ("Sr Dir. Platform", "senior director platform"),
        ("SRE Manager", "sre manager"),
    ],
)
def test_normalize_title(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("VP, Technology Operations", True),
        ("Sr. Director, Strategic Programs", True),
        ("Head of AI Transformation", True),
        ("Assistant Vice President, Operations", False),
        ("Associate Director, Programs", False),
        # Plain Director counts (a Meta role from a LinkedIn alert was once dropped here).
        ("Director, Technical Program Management \N{EM DASH} Meta Business AI", True),
        ("Dir. Engineering Productivity", True),
        ("Assistant Director, Operations", False),
        ("Director of Sales", False),
        ("Senior Software Engineer, Platform", False),
        ("VP of Sales", False),
        ("Head of Maintenance", False),
    ],
)
def test_title_matches(config: SearchConfig, title: str, expected: bool) -> None:
    assert title_matches(title, config.taxonomy) is expected


@pytest.mark.parametrize(
    ("location", "scope", "preference"),
    [
        ("", None, "UNKNOWN"),
        ("San Francisco, CA", "BAY_AREA", "PREFERRED"),
        ("Hybrid - Palo Alto", "BAY_AREA", "PREFERRED"),
        ("Remote - United States", "US_REMOTE", "ACCEPTABLE"),
        ("Remote (US)", "US_REMOTE", "ACCEPTABLE"),
        ("Remote", "US_REMOTE", "ACCEPTABLE"),
        ("Remote - Canada", None, "INELIGIBLE"),
        ("New York, NY", None, "INELIGIBLE"),
    ],
)
def test_classify_location(
    config: SearchConfig, location: str, scope: str | None, preference: str
) -> None:
    match = classify_location(location, config.geography)
    assert (match.scope, match.preference) == (scope, preference)


def test_classify_location_without_hard_filter_or_remote_scope() -> None:
    geography = GeographyConfig(
        hard_filter=False,
        scopes={"BAY_AREA": GeoScope(preference="PREFERRED", places=["oakland"])},
    )
    assert classify_location("Remote", geography).preference == "UNDESIRABLE"
    assert classify_location("Oakland, CA", geography).scope == "BAY_AREA"


def test_is_candidate(config: SearchConfig) -> None:
    def posting(title: str, location: str) -> Posting:
        return Posting("lever", "a:1", "Co", title, location, "d", "u")

    assert is_candidate(
        posting("VP Engineering Operations", "Oakland"), config.taxonomy, config.geography
    )
    assert not is_candidate(
        posting("VP Engineering Operations", "London"), config.taxonomy, config.geography
    )
    assert not is_candidate(posting("Recruiter", "Oakland"), config.taxonomy, config.geography)


def test_inline_tags_do_not_break_lines() -> None:
    assert html_to_text("<p>Lead <b>global</b> ops</p>") == "Lead global ops"
