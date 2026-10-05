"""Unit tests for the web portal pages (design doc 0011). All data is synthetic."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from pejip import portal
from pejip.config import SearchConfig, load_config
from pejip.portal import render, views
from pejip.portal.data import (
    Citation,
    Company,
    Connection,
    FitComponent,
    HistoryEvent,
    Opportunity,
    Point,
    SearchRun,
    Signal,
    SourceStatus,
)
from pejip.portal.sample import (
    SampleData,
    sample_companies,
    sample_opportunities,
    sample_runs,
)
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
        self,
        items: list[Opportunity],
        run: SearchRun | None,
        sample: bool = False,
        runs: list[SearchRun] | None = None,
        companies: list[Company] | None = None,
    ) -> None:
        self.items = items
        self.run = run
        self.is_sample = sample
        self.runs = runs if runs is not None else ([run] if run else [])
        self.company_list = companies or []

    def latest_run(self) -> SearchRun | None:
        return self.run

    def recent_runs(self) -> list[SearchRun]:
        return list(self.runs)

    def companies(self) -> list[Company]:
        return list(self.company_list)

    def opportunities(self) -> list[Opportunity]:
        return list(self.items)


def _role(number: int = 1, **changes: object) -> Opportunity:
    base = Opportunity(
        location_scope="BAY_AREA",
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
    data = SampleData(lambda: NOW)
    return FakeData(
        sample_opportunities(NOW),
        data.latest_run(),
        True,
        data.recent_runs(),
        data.companies(),
    )


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


def test_opportunity_detail_shows_company_source_and_history() -> None:
    html = _get(_sample(), "/opportunities/1").text

    assert "Company intelligence" in html
    assert 'href="/opportunities?view=all&amp;company=Company%20A">All roles at Company A' in html
    assert "Enterprise Software · AI Platforms" in html
    assert "Enterprise AI investment" in html
    assert "Open roles you match" in html
    assert "Source and verification" in html
    assert "Company A careers site" in html
    assert "R100001" in html
    assert "First discovered by the daily search" in html
    assert "Scored: fit 94, priority Immediate" in html


def test_opportunity_detail_without_company_profile_or_history() -> None:
    html = _get(FakeData([_role()], None), "/opportunities/1").text

    assert "PEJIP has no company profile for this employer yet." in html
    assert "Not verified yet" in html
    assert "No changes recorded yet." in html


def test_opportunity_detail_lists_history_oldest_first() -> None:
    company = Company(
        name="Company A",
        industry=None,
        target=True,
        watching=True,
        monitoring="HIGH",
        relevance="STRATEGICALLY_RELEVANT",
        job_source="Careers site feed",
    )
    role = _role(
        history=(
            HistoryEvent(NOW - timedelta(hours=1), "Second <event>"),
            HistoryEvent(NOW - timedelta(hours=2), "First event"),
        ),
        verified_on="Company A careers site",
        requisition="R1",
        last_verified_at=NOW - timedelta(hours=1),
    )
    html = _get(FakeData([role, _role(2)], None, companies=[company]), "/opportunities/1").text

    assert html.index("First event") < html.index("Second &lt;event&gt;")
    assert "Watching" in html
    assert '<span class="lbl">Open roles you match</span><span class="v">2</span>' in html
    assert "No relevant signals in the last 90 days." in html


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
    listing = list_opportunities(items, Filters(view="immediate"), NOW)
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
            "scope": "US_REMOTE",
            "age": "7",
            "network": "none",
            "pay": "unpublished",
        }
    )

    assert (f.view, f.priority, f.min_fit, f.confidence, f.work_model) == (
        "remote",
        "HIGH",
        90,
        "LOW",
        "Onsite",
    )
    assert (f.scope, f.max_age_days, f.network, f.pay) == ("US_REMOTE", 7, "none", "unpublished")
    assert Filters.from_query({"age": "5", "scope": "MARS"}) == Filters()
    assert Filters(network="none").any_set
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
        (Filters(scope="BAY_AREA"), True),
        (Filters(scope="US_REMOTE"), False),
        (Filters(max_age_days=1), True),
        (Filters(network="unknown"), True),
        (Filters(network="connected"), False),
        (Filters(pay="published"), True),
        (Filters(pay="unpublished"), False),
    ],
)
def test_filters_keep(filters: Filters, kept: bool) -> None:
    assert filters.keep(_role(), NOW) is kept


def test_views_match_their_roles() -> None:
    items = sample_opportunities(NOW)
    counts = list_opportunities(items, Filters(view="all"), NOW).counts

    assert counts == {
        "attention": 3,
        "new": 5,
        "high-fit": 4,
        "immediate": 1,
        "watched": 2,
        "network": 2,
        "remote": 3,
        "bay-area": 5,
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


# ── Search Health ────────────────────────────────────────────────────────────
def _run(hours_ago: int, status: str = "SUCCESS", *sources: SourceStatus) -> SearchRun:
    return SearchRun(
        started_at=NOW - timedelta(hours=hours_ago),
        status=status,
        sources_searched=sum(s.status == "OK" for s in sources),
        sources_total=len(sources),
        new=1,
        changed=0,
        expired=0,
        next_run_at=None,
        sources=sources,
    )


def test_search_health_shows_latest_sources_and_history() -> None:
    page = _get(_sample(), "/search-health")

    assert page.status_code == 200
    html = page.text
    assert "<title>PEJIP · Search Health</title>" in html
    assert 'class="nl on" href="/search-health" aria-current="page"' in html
    assert "Sources in the latest search · 14" in html
    assert "Company A careers site" in html
    assert "Recent searches · 5" in html
    # The older partial run is in the history; the clean latest run has no failures.
    assert '<span class="pill p-warn">PARTIAL</span>' in html
    assert "Sources that failed" not in html
    assert "Sample data until the database is connected" in html


def test_search_health_explains_a_failed_source_without_raw_errors() -> None:
    ok, failed = SourceStatus("Board A", "OK", 5, 1), SourceStatus("Board B", "FAILED", 0, 0)
    never = SourceStatus("Board C", "FAILED", 0, 0)
    runs = [
        _run(1, "PARTIAL", ok, failed, never),
        _run(5, "PARTIAL", ok, replace(failed, status="FAILED"), never),
        _run(9, "SUCCESS", ok, replace(failed, status="OK")),
    ]
    html = _get(FakeData([], runs[0], runs=runs), "/search-health").text

    assert "Sources that failed · 2" in html
    assert "Results from this source may be incomplete." in html
    assert "Today 3:00 AM" in html  # Board B last worked nine hours ago
    assert "None in recent runs" in html  # Board C never worked
    # Failed sources are listed first in the sources table.
    assert html.index("<td>Board B</td>") < html.index("<td>Board A</td>")


def test_search_health_before_any_run_and_without_source_detail() -> None:
    assert (
        "No search has run yet. The first scheduled search"
        in _get(FakeData([], None), "/search-health").text
    )
    bare = _run(2)
    html = _get(FakeData([], bare), "/search-health").text
    assert "This run did not record its sources." in html


def test_search_health_pills_for_unexpected_statuses() -> None:
    assert render._source_pill("SKIPPED") == '<span class="pill p-warn">Skipped</span>'
    assert render._run_pill("FAILED") == '<span class="pill p-fail">FAILED</span>'


def test_navigation_links_live_pages_and_marks_the_rest_soon() -> None:
    html = _get(_sample(), "/").text

    assert '<a class="nl" href="/search-health">Search Health</a>' in html
    assert '<a href="/search-health">Details</a>' in html
    assert '<a class="nl" href="/companies">Companies</a>' in html
    assert '<a class="nl" href="/watchlist">Watchlist</a>' in html
    assert '<a class="nl" href="/settings">Settings</a>' in html
    for label in ("Connections",):
        assert f'<span class="nl off">{label}<span class="soon">Soon</span></span>' in html


def test_sample_runs_have_one_partial_run_with_a_failed_source() -> None:
    runs = sample_runs(NOW)

    assert [r.status for r in runs].count("PARTIAL") == 1
    assert runs[0].status == "SUCCESS"
    assert runs[0].started_at > runs[-1].started_at
    partial = next(r for r in runs if r.status == "PARTIAL")
    assert [s.name for s in partial.sources if s.status == "FAILED"] == ["Job discovery source B"]
    assert partial.sources_searched == partial.sources_total - 1


# ── Companies ────────────────────────────────────────────────────────────────
def _company(name: str = "Company A", **changes: object) -> Company:
    base = Company(
        name,
        "Enterprise Software",
        target=True,
        watching=False,
        monitoring="NORMAL",
        relevance="NO_CURRENT_MATCH",
        job_source="Careers site feed",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_companies_page_shows_targets_and_discovered() -> None:
    page = _get(_sample(), "/companies")

    assert page.status_code == 200
    html = page.text
    assert "<title>PEJIP · Companies</title>" in html
    assert 'class="nl on" href="/companies" aria-current="page"' in html
    assert "Target companies · 7" in html
    assert "Discovered in searches · 5" in html
    assert 'Top match: <a href="/opportunities/1">VP Technology Transformation</a>' in html
    assert "No suitable opening currently." in html
    assert "Why this company remains relevant" in html
    assert "Role family outside your targets" in html
    assert 'href="/opportunities?view=all&amp;company=Company%20A"' in html
    assert "Strategically relevant" in html
    # High monitoring and urgent roles come first.
    assert html.index("<h3>Company A</h3>") < html.index("<h3>Company D</h3>")


@pytest.mark.parametrize(
    ("view", "heading"),
    [
        ("matching", "Target companies · 4"),
        ("watching", "Target companies · 4"),
        ("relevant", "Target companies · 1"),
        ("no-match", "Target companies · 2"),
        ("low", "Target companies · 0"),
        ("bogus", "Target companies · 7"),
    ],
)
def test_company_views(view: str, heading: str) -> None:
    html = _get(_sample(), f"/companies?view={view}").text

    assert heading in html


def test_company_without_signals_connections_or_industry() -> None:
    quiet = _company(connections=None, industry=None, coverage_note="no alert in 9 days")
    html = _get(FakeData([], None, companies=[quiet]), "/companies").text

    assert "No relevant signals in the last 90 days." in html
    assert '<div class="fit">Unknown</div><div class="fitl">Connections</div>' in html
    assert "no alert in 9 days" in html
    assert "Industry unknown" not in html  # targets show no industry line at all


def test_company_with_one_unscored_match_and_a_discovered_one() -> None:
    signal = Signal("AI expansion", "Press release", NOW - timedelta(days=2))
    companies = [
        _company(signals=(signal,), connections=4),
        _company("Company Z", target=False, industry=None, relevance="LOW_RELEVANCE"),
    ]
    roles = [_role(1, fit=None, priority="MEDIUM")]
    html = _get(FakeData(roles, None, companies=companies), "/companies").text

    assert "Matching job</div>" in html
    assert "Fit Unknown · Medium" in html
    assert "AI expansion" in html
    assert "Press release · 2d ago" in html
    assert "Industry unknown" in html
    assert "Low relevance" in html


def test_companies_page_with_no_companies() -> None:
    html = _get(FakeData([], None), "/companies").text

    assert "No target company is in this view." in html
    assert "Discovered in searches" not in html


def test_company_rows_sort_and_state() -> None:
    rows = views.company_rows(
        [
            _company("B", monitoring="HIGH"),
            _company("A", monitoring="ODD"),
            _company("C", monitoring="HIGH"),
        ],
        [_role(1, company="C", priority="IMMEDIATE"), _role(2, company="C", priority="LOW")],
    )

    assert [r.company.name for r in rows] == ["C", "B", "A"]
    assert rows[0].state == "MATCHING_JOBS"
    assert len(rows[0].jobs) == 1  # low-priority roles do not count as matches
    assert rows[1].state == "NO_CURRENT_MATCH"
    assert render._company_state("SOMETHING_NEW") == '<span class="pill p-med">Something new</span>'


def test_sample_companies_cover_every_state() -> None:
    rows = views.company_rows(sample_companies(NOW), sample_opportunities(NOW))

    assert {r.state for r in rows} == {
        "MATCHING_JOBS",
        "STRATEGICALLY_RELEVANT",
        "NO_CURRENT_MATCH",
        "LOW_RELEVANCE",
    }


# ── Watchlist ────────────────────────────────────────────────────────────────
def test_watchlist_shows_changes_then_everything_watched() -> None:
    page = _get(_sample(), "/watchlist")

    assert page.status_code == 200
    html = page.text
    assert "<title>PEJIP · Watchlist</title>" in html
    assert 'class="nl on" href="/watchlist" aria-current="page"' in html
    assert "Watched job changed · Onsite to Remote" in html
    # Company A is watched and posted a new Immediate role.
    assert html.index("New roles at watched companies") < html.index("VP Technology Transformation")
    assert "Enterprise AI investment" in html
    assert "Watched jobs · 2" in html
    assert "Watched companies · 4" in html
    assert "It never changes the Fit of its jobs." in html


def test_watchlist_when_nothing_is_watched() -> None:
    html = _get(FakeData([_role()], None, companies=[_company()]), "/watchlist").text

    assert "No watched job changed since the last search." in html
    assert "No new role at a watched company." in html
    assert "No new signal at a watched company this week." in html
    assert "You are not watching any job yet." in html
    assert "You are not watching any company yet." in html


def test_watchlist_details() -> None:
    old = Signal("Old news", "News report", NOW - timedelta(days=20))
    fresh = Signal("Fresh news", "Press release", NOW - timedelta(days=1))
    companies = [
        _company("Company A", watching=True, signals=(old, fresh)),
        _company("Company B", watching=True, signals=(old,)),
        _company("Company C", watching=True),
    ]
    roles = [
        _role(1, watched=True, discovery="MATERIALLY_CHANGED", fit=None, priority="HIGH"),
        _role(2, company="Company B", discovery="PREVIOUSLY_SEEN", priority="MEDIUM"),
    ]
    w = views.watchlist(companies, roles, NOW)

    assert [s.text for _r, s in w.new_signals] == ["Fresh news"]
    assert w.new_at_watched == []  # neither role is a new posting
    html = render.watchlist_body(w, NOW)
    assert "Watched job changed · posting changed" in html
    assert '<span class="tfit">Unknown</span>' in html
    assert "1 · 1 high-priority" in html
    assert "None in 90 days" in html
    assert "Old news · 20d ago" in html


def test_watched_job_without_change_note_in_table() -> None:
    w = views.watchlist([], [_role(1, watched=True, discovery="PREVIOUSLY_SEEN")], NOW)

    assert w.changed_jobs == []
    assert "<td>No change</td>" in render.watchlist_body(w, NOW)


# ── Settings ─────────────────────────────────────────────────────────────────
CONFIG = load_config(Path("config/search.yaml"))


def _get_settings(config: SearchConfig | None) -> str:
    app = FastAPI()
    app.include_router(portal.router(FakeData([], None), clock=lambda: NOW, config=config))

    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/settings")

    page = asyncio.run(call())
    assert page.status_code == 200
    return page.text


def test_settings_shows_the_real_search_setup() -> None:
    html = _get_settings(CONFIG)

    assert "<title>PEJIP · Settings</title>" in html
    assert 'class="nl on" href="/settings" aria-current="page"' in html
    assert '<span class="chip">vice president</span>' in html
    assert '<span class="chip">intern</span>' in html
    assert "San Francisco Bay Area" in html
    assert "Any remote role in the US" in html
    assert "Roles outside every location are hidden." in html
    assert "<h3>Anthropic</h3>" in html
    assert "Public Greenhouse job board" in html
    assert "alerts@inbox.job-search.zephyr-mcg.com" in html
    assert "Job board alerts" in html  # LinkedIn
    assert "Careers site alerts" in html
    assert f"Scoring version {CONFIG.scoring.version}." in html
    assert "Priority 85+, Fit 85+" in html
    assert "90 days, then deleted" in html


def test_settings_variants() -> None:
    config = CONFIG.model_copy(
        update={
            "inbox": None,
            "geography": CONFIG.geography.model_copy(
                update={
                    "hard_filter": False,
                    "scopes": {"SEATTLE": CONFIG.geography.scopes["US_REMOTE"]},
                }
            ),
            "sources": [CONFIG.sources[0].model_copy(update={"adapter": "lever"})],
        }
    )
    html = _get_settings(config)

    assert "Job-alert emails are not set up." in html
    assert "Roles outside these locations are kept, with lower priority." in html
    assert "<td>Seattle</td>" in html
    assert "Public Lever job board" in html


def test_settings_without_configuration() -> None:
    assert "The search configuration is not available" in _get_settings(None)


def test_new_filters_on_roles() -> None:
    old = _role(1, posted_at=NOW - timedelta(days=10), first_seen_at=NOW - timedelta(days=9))
    connected = _role(2, connections=(Connection("Person A", "VP", "STRONG"),))
    alone = _role(3, connections=(), compensation=None)

    assert not Filters(max_age_days=7).keep(old, NOW)
    assert Filters(max_age_days=30).keep(old, NOW)
    assert Filters(network="connected").keep(connected, NOW)
    assert Filters(network="none").keep(alone, NOW)
    assert not Filters(network="none").keep(connected, NOW)
    assert Filters(pay="unpublished").keep(alone, NOW)


def test_opportunities_page_bay_area_view_and_new_filters_in_the_form() -> None:
    html = _get(
        _sample(),
        "/opportunities?view=bay-area&scope=BAY_AREA&age=3&network=connected&pay=published",
    ).text

    assert 'class="btn sel" aria-current="page" href="/opportunities?view=bay-area"' in html
    assert '<option value="BAY_AREA" selected>San Francisco Bay Area</option>' in html
    assert '<option value="3" selected>Last 3 days</option>' in html
    assert '<option value="connected" selected>Has connections</option>' in html
    assert '<option value="published" selected>Pay published</option>' in html
