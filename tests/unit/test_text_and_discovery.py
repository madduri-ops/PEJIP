from __future__ import annotations

import pytest

from pejip.config import GeographyConfig, GeoScope, SearchConfig
from pejip.discovery import (
    BELOW_PAY,
    JOB_ALERT,
    OUT_OF_SCOPE,
    PAY,
    SENIOR_TITLE,
    UNCLEAR_NO_PAY,
    classify_location,
    is_candidate,
    normalize_title,
    screen,
    title_matches,
)
from pejip.models import Compensation, Posting
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


FLOOR = 260_000.0


def _pay(low: float | None, high: float | None) -> Compensation:
    return Compensation(low, high, "USD")


@pytest.mark.parametrize(
    ("title", "pay", "origin", "basis"),
    [
        # A senior title is enough, with or without pay.
        ("Director, Technical Program Management", None, None, SENIOR_TITLE),
        # The title is one signal, not a gate (Babu, 2026-10-06): an unclear title
        # is kept when posted pay reaches the profile minimum.
        ("Lead Portfolio Program Manager", _pay(200_000, 300_000), None, PAY),
        ("Principal Program Manager", _pay(270_000, None), None, PAY),
        ("Assistant Vice President, Operations", _pay(250_000, 280_000), None, PAY),
        # Posted pay below the minimum rules a role out, whatever its title.
        ("Lead Portfolio Program Manager", _pay(150_000, 220_000), None, BELOW_PAY),
        ("Vice President, Technology", _pay(180_000, 240_000), None, BELOW_PAY),
        ("Director, Program Management", _pay(None, 200_000), "job_alert_email", BELOW_PAY),
        ("Lead Portfolio Program Manager", _pay(None, None), None, UNCLEAR_NO_PAY),
        ("Lead Portfolio Program Manager", None, None, UNCLEAR_NO_PAY),
        # Babu chose his job-alert searches, so an alert's role is kept on its title's area.
        ("Lead Portfolio Program Manager", None, "job_alert_email", JOB_ALERT),
        ("Associate Director, Program Management", None, "job_alert_email", UNCLEAR_NO_PAY),
        # A role outside the role families is out whatever it pays.
        ("Recruiter", _pay(300_000, 400_000), "job_alert_email", OUT_OF_SCOPE),
    ],
)
def test_screen_reads_title_then_pay(
    config: SearchConfig,
    title: str,
    pay: Compensation | None,
    origin: str | None,
    basis: str,
) -> None:
    extra = {"origin": origin} if origin else {}
    posting = Posting(
        "lever", "a:1", "Co", title, "Oakland", "d", "u", compensation=pay, extra=extra
    )
    assert screen(posting, config.taxonomy, config.geography, FLOOR) == basis


def test_screen_without_a_pay_floor_or_outside_the_area(config: SearchConfig) -> None:
    paid = Posting(
        "lever", "a:1", "Co", "Lead Program Manager", "Oakland", "d", "u", compensation=_pay(1, 9e9)
    )
    assert screen(paid, config.taxonomy, config.geography) == UNCLEAR_NO_PAY
    london = Posting("lever", "a:1", "Co", "VP Engineering", "London", "d", "u")
    assert screen(london, config.taxonomy, config.geography, FLOOR) == OUT_OF_SCOPE


def test_inline_tags_do_not_break_lines() -> None:
    assert html_to_text("<p>Lead <b>global</b> ops</p>") == "Lead global ops"
