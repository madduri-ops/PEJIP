"""Unit tests for the web portal pages (design doc 0011). All data is synthetic."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from pejip import portal
from pejip.portal import render
from pejip.portal.data import Citation, Connection, FitComponent, Opportunity, Point, SearchRun
from pejip.portal.sample import SampleData, sample_opportunities
from pejip.portal.views import (
    DEFAULT_VIEW,
    Filters,
    age,
    list_opportunities,
    rank,
    to_pacific,
    when,
)

NOW = datetime(2026, 10, 5, 19, 0, tzinfo=UTC)  # 12:00 PM PDT


class FakeData:
    """A PortalData with whatever roles and run a test needs."""

    def __init__(
        self, items: list[Opportunity], run: SearchRun | None, sample: bool = False
    ) -> None:
        self.items = items
        self.run = run
        self.is_sample = sample

    def latest_run(self) -> SearchRun | None:
        return self.run

    def opportunities(self) -> list[Opportunity]:
        return list(self.items)


def _role(number: int = 1, **changes: object) -> Opportunity:
    base = Opportunity(
        id=number,
        title=f"VP Role {number}",
        company="Company A",
        location="San Jose, CA",
        work_model="Hybrid",
        compensation="$300K",
        posted_at=NOW - timedelta(hours=3),
        first_seen_at=NOW - timedelta(hours=2),
        fit=90,
        confidence="HIGH",
        priority="HIGH",
        discovery="NEW_POSTING",
        source="greenhouse",
        url="https://example.com/jobs/1",
        description="First line.\n\nSecond line.",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _get(data: FakeData, path: str) -> httpx.Response:
    app = FastAPI()
    app.include_router(portal.router(data, clock=lambda: NOW))

    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(call())


def _sample() -> FakeData:
    return FakeData(sample_opportunities(NOW), SampleData(lambda: NOW).latest_run(), True)


# ── Pages ────────────────────────────────────────────────────────────────────
def test_home_shows_attention_new_changes_and_health() -> None:
    page = _get(_sample(), "/")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    html = page.text
    assert "<title>PEJIP · Home</title>" in html
    assert '<div class="brand">Personal Executive Job Intelligence Platform</div>' in html
    assert "Sample data until the database is connected" in html
    assert "VP Technology Transformation" in html
    assert "Onsite to Remote" in html
    assert "14 of 14 searched" in html
    assert "Last search: Today 11:00 AM" in html
    # Unranked roles never appear among strong matches.
    assert "Chief of Staff to the CTO" not in html


def test_home_with_no_data_says_so() -> None:
    html = _get(FakeData([], None), "/").text

    assert "Nothing needs your attention right now." in html
    assert "No other new postings" in html
    assert "No role changed" in html
    assert "No search has run yet" in html
    assert "Sample data" not in html


def test_opportunities_default_view_and_others_table() -> None:
    html = _get(_sample(), "/opportunities").text

    assert "Requires attention · 3" in html
    assert "Other active opportunities · 4" in html
    assert 'class="btn sel" aria-current="page" href="/opportunities?view=attention"' in html
    assert "Low-priority and unranked roles appear only in" in html


def test_opportunities_all_view_includes_low_and_unranked() -> None:
    html = _get(_sample(), "/opportunities?view=all").text

    assert "All active · 9" in html
    assert "Chief of Staff to the CTO" in html
    assert "Low-priority and unranked" not in html


def test_opportunities_filters_are_applied_and_kept_in_the_form() -> None:
    html = _get(_sample(), "/opportunities?view=all&work_model=Remote&fit=80&company=company").text

    assert "All active · 2" in html
    assert '<option value="Remote" selected>' in html
    assert '<option value="80" selected>' in html
    assert 'value="company"' in html


def test_opportunities_empty_view_explains_why() -> None:
    filtered = _get(_sample(), "/opportunities?view=immediate&company=nobody").text
    unfiltered = _get(FakeData([], None), "/opportunities?view=watched").text

    assert "No opportunity matches this view and these filters." in filtered
    assert "No opportunity is in this view right now." in unfiltered


def test_opportunities_ignores_unknown_query_values() -> None:
    html = _get(_sample(), "/opportunities?view=bogus&priority=<b>&fit=55").text

    assert "Requires attention · 3" in html
    assert "<b>" not in html


def test_opportunity_detail_shows_cited_explanation() -> None:
    html = _get(_sample(), "/opportunities/1").text

    assert '<div class="crumb"><a href="/opportunities">Opportunities</a></div>' in html
    assert "Fit analysis · 94" in html
    assert "Real gap" in html
    assert "Missing information" in html
    assert "Job evidence" in html
    assert "Profile evidence" in html
    assert "Employer posting date" in html
    assert "Person A" in html
    assert 'rel="noopener noreferrer"' in html


def test_opportunity_detail_with_unknowns() -> None:
    html = _get(_sample(), "/opportunities/9").text

    assert "Fit analysis · Unknown" in html
    assert "Not scored yet." in html
    assert "No strong reasons found." in html
    assert "Nothing urgent." in html
    assert "Who you know · Unknown" in html
    assert "have not been imported yet" in html


def test_opportunity_detail_variants() -> None:
    role = _role(
        posted_at=None,
        work_model=None,
        compensation=None,
        url="javascript:alert(1)",
        components=(FitComponent("CAPABILITY", None), FitComponent("LEADERSHIP", 0.5)),
        concerns=(
            Point("Not enough profile evidence to judge: budget"),
            Point("Possible negative fit (sales_heavy)", (Citation("job_field", "custom"),)),
        ),
        connections=(),
        why_now=(Point("A point with no citation"),),
    )
    html = _get(FakeData([role], None), "/opportunities/1").text

    assert '<div class="gap"><span class="t">A point with no citation</span></div>' in html
    assert "javascript:" not in html
    assert "No link to the original posting" in html
    assert '<span class="pill k-unk">Unknown</span>' in html
    assert '<span class="pill k-pref">Concern</span>' in html
    assert "custom" in html
    assert 'class="v lo"' in html
    assert "No first-degree connections at this company." in html
    assert "Concerns and gaps · 2" in html


def test_opportunity_detail_without_concerns() -> None:
    html = _get(FakeData([_role()], None), "/opportunities/1").text

    assert "No concerns found." in html


def test_unknown_opportunity_is_not_found() -> None:
    response = _get(_sample(), "/opportunities/99")

    assert response.status_code == 404
    assert "no longer active" in response.text


def test_stylesheet_is_served() -> None:
    response = _get(_sample(), "/portal.css")

    assert response.headers["content-type"].startswith("text/css")
    assert ".nav" in response.text


def test_every_value_from_the_data_is_escaped() -> None:
    hostile = "<script>alert(1)</script>"
    role = _role(
        title=hostile,
        company=hostile,
        why_it_fits=(Point(hostile, (Citation("posting", hostile),)),),
        connections=(Connection(hostile, hostile, "STRONG"),),
    )
    for path in ("/", "/opportunities", "/opportunities/1"):
        assert "<script>" not in _get(FakeData([role], None), path).text


# ── Building blocks ──────────────────────────────────────────────────────────
def test_cards_show_unknowns_and_flags() -> None:
    role = _role(
        fit=None,
        compensation=None,
        posted_at=None,
        work_model=None,
        connections=None,
        watched=True,
        discovery="PREVIOUSLY_SEEN",
    )
    html = render.card(role, NOW)

    assert '<div class="unk">Unknown</div>' in html
    assert "Compensation: Not published" in html
    assert "Network: Unknown" in html
    assert "WATCHING" in html
    assert "PREVIOUSLY SEEN" not in html
    assert "Posted" not in html
    assert render.mini_card(role, NOW).count("Hybrid") == 0


def test_connection_counts() -> None:
    one = (Connection("Person A", "VP", "STRONG"),)

    assert "1 connection<" in render.card(_role(connections=one), NOW)
    assert "No connections" in render.card(_role(connections=()), NOW)


def test_card_without_explanation_has_no_why_block() -> None:
    assert 'class="why' not in render.card(_role(), NOW)


def test_table_shows_unknown_fit_and_missing_pay() -> None:
    items = [_role(1, priority="MEDIUM"), _role(2, fit=None, compensation=None, work_model=None)]
    listing = list_opportunities(items, Filters(view="immediate"))
    html = render.opportunities_body(listing, Filters(view="immediate"), NOW)

    assert '<span class="tfit">Unknown</span>' in html
    assert '<td class="unk">Not published</td>' in html
    assert "None noted" in html


def test_run_line_variants() -> None:
    run = SearchRun(NOW, "PARTIAL", 3, 4, 1, 0, 0, None)

    assert 'class="partial"' in render.run_line(run, NOW)
    assert "Not scheduled" in render.run_line(run, NOW)
    assert "Not scheduled" in render.health_card(run, NOW)
    failed = render.run_line(replace(run, status="FAILED"), NOW)
    assert '<span class="fail">FAILED</span>' in failed


# ── Ranking, views and filters ───────────────────────────────────────────────
def test_rank_orders_priority_then_fit_then_freshness() -> None:
    older = _role(1, fit=80, posted_at=NOW - timedelta(days=3))
    newer = _role(2, fit=80, posted_at=None, first_seen_at=NOW)
    better = _role(3, fit=95)
    unknown = _role(4, fit=None)
    immediate = _role(5, priority="IMMEDIATE", fit=70)
    odd = _role(6, priority="SOMETHING_NEW")

    ranked = rank([odd, unknown, older, newer, better, immediate])

    assert [o.id for o in ranked] == [5, 3, 2, 1, 4, 6]


def test_filters_from_query() -> None:
    f = Filters.from_query(
        {
            "view": "remote",
            "priority": "HIGH",
            "fit": "90",
            "confidence": "LOW",
            "company": "  " + "x" * 200,
            "work_model": "Onsite",
        }
    )

    assert (f.view, f.priority, f.min_fit, f.confidence, f.work_model) == (
        "remote",
        "HIGH",
        90,
        "LOW",
        "Onsite",
    )
    assert len(f.company) == 100
    assert f.any_set
    assert Filters.from_query({}) == Filters()
    assert Filters().view == DEFAULT_VIEW
    assert not Filters().any_set


@pytest.mark.parametrize(
    ("filters", "kept"),
    [
        (Filters(priority="HIGH"), True),
        (Filters(priority="LOW"), False),
        (Filters(min_fit=95), False),
        (Filters(confidence="HIGH"), True),
        (Filters(confidence="LOW"), False),
        (Filters(company="pany a"), True),
        (Filters(company="Company B"), False),
        (Filters(work_model="Hybrid"), True),
        (Filters(work_model="Remote"), False),
    ],
)
def test_filters_keep(filters: Filters, kept: bool) -> None:
    assert filters.keep(_role()) is kept


def test_views_match_their_roles() -> None:
    items = sample_opportunities(NOW)
    counts = list_opportunities(items, Filters(view="all")).counts

    assert counts == {
        "attention": 3,
        "new": 5,
        "high-fit": 4,
        "immediate": 1,
        "watched": 2,
        "network": 2,
        "remote": 3,
        "changed": 2,
        "all": 9,
    }


# ── Time display ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("moment", "local"),
    [
        (datetime(2026, 7, 1, 19, 0, tzinfo=UTC), "2026-07-01 12:00 PDT"),
        (datetime(2026, 12, 1, 20, 0, tzinfo=UTC), "2026-12-01 12:00 PST"),
        # Daylight saving starts 2026-03-08 at 10:00 UTC and ends 2026-11-01 at 09:00 UTC.
        (datetime(2026, 3, 8, 9, 59, tzinfo=UTC), "2026-03-08 01:59 PST"),
        (datetime(2026, 3, 8, 10, 0, tzinfo=UTC), "2026-03-08 03:00 PDT"),
        (datetime(2026, 11, 1, 8, 59, tzinfo=UTC), "2026-11-01 01:59 PDT"),
        (datetime(2026, 11, 1, 9, 0, tzinfo=UTC), "2026-11-01 01:00 PST"),
    ],
)
def test_to_pacific(moment: datetime, local: str) -> None:
    assert f"{to_pacific(moment):%Y-%m-%d %H:%M %Z}" == local


def test_when() -> None:
    assert when(None, NOW) == "Unknown"
    assert when(NOW, NOW) == "Today 12:00 PM"
    assert when(NOW - timedelta(hours=12), NOW) == "Today 12:00 AM"
    assert when(NOW - timedelta(days=1, hours=3), NOW) == "Yesterday 9:00 AM"
    assert when(NOW + timedelta(days=1), NOW) == "Tomorrow 12:00 PM"
    assert when(NOW - timedelta(days=3, minutes=-5), NOW) == "Oct 2, 12:05 PM"


def test_age() -> None:
    assert age(None, NOW) == "Unknown"
    assert age(NOW - timedelta(minutes=30), NOW) == "just now"
    assert age(NOW - timedelta(hours=5), NOW) == "5h ago"
    assert age(NOW - timedelta(days=2, hours=1), NOW) == "2d ago"


# ── Sample data ──────────────────────────────────────────────────────────────
def test_sample_data_is_marked_and_current() -> None:
    data = SampleData()
    run = data.latest_run()

    assert data.is_sample
    assert run is not None
    assert run.next_run_at is not None
    assert run.started_at < datetime.now(UTC) < run.next_run_at
    assert len(data.opportunities()) == 9
    assert {o.company for o in data.opportunities()} <= {f"Company {c}" for c in "ABCDEFGHI"}
