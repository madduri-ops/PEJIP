"""The portal reading an account's own database (pejip.portal.stored)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pejip.config import AlertCompany, SearchConfig
from pejip.explain import network_points
from pejip.models import Compensation, Posting
from pejip.network.companies import CompanyDirectory
from pejip.network.linkedin import parse_export
from pejip.network.matching import NetworkIndex
from pejip.portal.data import Citation, Connection
from pejip.portal.stored import (
    StoreData,
    _aware,
    compensation,
    connections,
    next_search,
    points,
)
from pejip.store import AnalysisRecord, RecommendationRecord, Store
from tests.conftest import NOW
from tests.linkedin import export, row

EXPLANATION = {
    "why_it_fits": [
        {
            "text": "Strong match: operations leadership",
            "citations": [
                {"type": "posting", "quote": "lead operations"},
                {"type": "profile", "evidence_id": "ev-1"},
            ],
        }
    ],
    "concerns": [
        {"text": "Posted a while ago", "citations": [{"type": "job_field", "field": "posted_at"}]}
    ],
    "why_now": [{"text": "Hiring now", "citations": [{"type": "network", "connection_id": "c1"}]}],
    "who_you_know": [
        {"text": "Matured connection: Avery Example, SVP Technology", "citations": []},
        {"text": "1 other first-degree connection below VP level.", "citations": []},
    ],
}


def _posting(number: int, **changes: Any) -> Posting:
    fields: dict[str, Any] = {
        "source": "greenhouse",
        "source_job_id": f"b:{number}",
        "company": "Co",
        "title": f"VP Ops {number}",
        "location": "Oakland, CA",
        "description": "Lead operations.",
        "url": f"https://example.com/{number}",
        "posted_at": NOW - timedelta(days=1),
        "compensation": Compensation(300_000.0, 400_000.0, "USD"),
        "work_model_hint": "HYBRID",
    }
    return Posting(**{**fields, **changes})


def _rank(store: Store, job_id: int, at: datetime) -> None:
    analysis = store.add_analysis(AnalysisRecord(job_id, "h", "OK", {}, None, {}, at))
    store.add_recommendation(
        RecommendationRecord(
            job_id=job_id,
            analysis_id=analysis,
            fit=91.4,
            confidence="HIGH",
            priority="IMMEDIATE",
            detail={
                "components": [
                    {"name": "LEADERSHIP", "value": 0.9, "weight": 1, "evidence_ids": []}
                ],
                "explanation": EXPLANATION,
            },
            scoring_version="v",
            created_at=at,
        )
    )


def _run(store: Store, run_id: str, at: datetime, seen: list[list[Any]], **summary: Any) -> None:
    store.start_run(run_id, at)
    store.finish_run(
        run_id,
        "PARTIAL",
        {
            "sources": [
                {"name": "Co careers", "status": "OK", "fetched": 4, "candidates": 2},
                {"name": "Alerts", "status": "FAILED"},
            ],
            "seen": seen,
            **summary,
        },
        at + timedelta(minutes=5),
    )


def test_an_account_without_a_database_shows_no_search_yet(config: SearchConfig) -> None:
    data = StoreData(None, config, clock=lambda: NOW)

    assert not data.is_sample
    assert data.latest_run() is None
    assert data.recent_runs() == []
    assert data.opportunities() == []
    assert data.network() is None


def test_roles_runs_and_explanations_come_from_the_database(
    store: Store, config: SearchConfig
) -> None:
    ranked = store.upsert_job(_posting(1), NOW - timedelta(days=2))
    store.upsert_job(
        _posting(1, description="Lead operations, now global."), NOW - timedelta(hours=3)
    )
    unranked = store.upsert_job(
        _posting(2, compensation=None, work_model_hint=None, location=""), NOW - timedelta(hours=3)
    )
    old = store.upsert_job(_posting(3), NOW - timedelta(days=20))
    _rank(store, ranked.job_id, NOW - timedelta(hours=2))
    _run(store, "old", NOW - timedelta(days=20), [[old.job_id, "NEW_POSTING"]])
    _run(store, "yesterday", NOW - timedelta(days=1), [[ranked.job_id, "NEW_POSTING"]])
    _run(
        store,
        "today",
        NOW - timedelta(hours=3),
        [
            [ranked.job_id, "MATERIALLY_CHANGED"],
            [unranked.job_id, "NEW_POSTING"],
            [999, "NEW_POSTING"],
        ],
    )
    data = StoreData(store, config, clock=lambda: NOW)

    runs = data.recent_runs()
    assert [r.started_at for r in runs] == [
        NOW - timedelta(hours=3),
        NOW - timedelta(days=1),
        NOW - timedelta(days=20),
    ]
    latest = data.latest_run()
    assert latest is not None
    assert (latest.status, latest.sources_searched, latest.sources_total) == ("PARTIAL", 1, 2)
    assert (latest.new, latest.changed, latest.expired) == (2, 1, 0)
    assert latest.next_run_at == next_search(NOW)
    assert latest.sources[1].fetched == 0
    assert runs[1].next_run_at is None

    by_id = {o.id: o for o in data.opportunities()}
    assert set(by_id) == {ranked.job_id, unranked.job_id}  # the 20-day-old role is gone
    role = by_id[ranked.job_id]
    assert (role.fit, role.confidence, role.priority) == (91.4, "HIGH", "IMMEDIATE")
    assert role.discovery == "MATERIALLY_CHANGED"
    assert role.change_note is not None
    assert role.work_model == "Hybrid"
    assert role.compensation == "$300K to $400K"
    assert role.location_scope == "BAY_AREA"
    assert role.components[0].name == "LEADERSHIP"
    assert role.why_it_fits[0].citations == (
        Citation("posting", "lead operations"),
        Citation("profile", "ev-1"),
    )
    assert role.concerns[0].citations == (Citation("job_field", "posted_at"),)
    assert role.why_now[0].citations == ()
    assert role.connections == (
        Connection("Avery Example", "SVP Technology", "UNKNOWN", "MATURED"),
    )
    assert (role.verified_on, role.requisition) == ("Greenhouse", "b:1")
    assert [h.text for h in role.history] == [
        "First discovered by a search",
        "The posting changed materially",
        "Scored: fit 91, priority Immediate",
    ]

    bare = by_id[unranked.job_id]
    assert (bare.fit, bare.confidence, bare.priority) == (None, "UNKNOWN", "UNRANKED")
    assert bare.location == "Location not stated"
    assert bare.location_scope is None
    assert (bare.work_model, bare.compensation, bare.connections) == (None, None, None)
    assert [h.text for h in bare.history] == ["First discovered by a search"]


def test_a_score_without_a_fit_and_no_search_setup(store: Store) -> None:
    job = store.upsert_job(_posting(1), NOW)
    analysis = store.add_analysis(AnalysisRecord(job.job_id, "h", "OK", {}, None, {}, NOW))
    store.add_recommendation(
        RecommendationRecord(job.job_id, analysis, None, "LOW", "UNRANKED", {}, "v", NOW)
    )
    _run(store, "r", NOW, [[job.job_id, "NEW_POSTING"]], notes=[])
    data = StoreData(store, None, clock=lambda: NOW)

    (role,) = data.opportunities()
    assert role.location_scope is None
    assert role.history[-1].text == "Scored: fit unknown, priority Unranked"
    assert role.connections is None
    assert data.companies() == []


def test_companies_come_from_the_search_setup(config: SearchConfig) -> None:
    companies = StoreData(None, config).companies()

    boards = {s.company for s in config.sources}
    assert boards <= {c.name for c in companies}
    assert len({c.name for c in companies}) == len(companies)
    assert all(c.target and not c.watching for c in companies)
    assert config.inbox is not None
    boards_only = [a.company for a in config.inbox.companies if a.job_board]
    assert not set(boards_only) & {c.name for c in companies}


def test_companies_with_their_own_job_alerts(config: SearchConfig) -> None:
    assert config.inbox is not None
    alert = AlertCompany(company="Contoso", link_patterns=["contoso.example/jobs"])
    inbox = config.inbox.model_copy(update={"companies": [*config.inbox.companies, alert]})
    setup = config.model_copy(update={"inbox": inbox})

    (contoso,) = [c for c in StoreData(None, setup).companies() if c.name == "Contoso"]
    assert contoso.job_source == "Job alerts"


def test_companies_without_job_alerts(config: SearchConfig) -> None:
    setup = config.model_copy(update={"inbox": None})

    assert {c.job_source for c in StoreData(None, setup).companies()} == {"Careers site feed"}


def test_who_you_know_reads_what_the_explanation_wrote() -> None:
    directory = CompanyDirectory.build(["Co"])
    people = parse_export(
        export(
            row("Avery", company="Co", position="SVP Technology"),
            row("Casey", company="Co", position="Principal, Technology Strategy"),
            row("Devon", company="Co", position="Director"),
        ),
        NOW,
    ).connections
    signal = NetworkIndex.build(people, directory).signal("Co", "VP")

    assert connections(network_points(signal, "Co")) == (
        Connection("Avery Example", "SVP Technology", "UNKNOWN", "MATURED"),
        Connection("Casey Example", "Principal, Technology Strategy", "UNKNOWN", "YOUR_CALL"),
    )
    nobody = NetworkIndex.build((), directory).signal("Co", "VP")
    assert connections(network_points(nobody, "Co")) == ()
    assert connections(network_points(None, "Co")) is None
    assert connections(None) is None
    assert connections(
        [{"text": "Matured connection: Ann Lee, VP Ops (your call)", "citations": []}]
    ) == (Connection("Ann Lee", "VP Ops", "UNKNOWN", "MATURED"),)


def test_points_without_citations() -> None:
    assert points([{"text": "Plain"}])[0].citations == ()


def test_compensation_text() -> None:
    def pay(low: float | None, high: float | None, currency: str | None = "USD") -> str | None:
        return compensation({"comp_min": low, "comp_max": high, "comp_currency": currency})

    assert pay(None, None) is None
    assert pay(250_000, 250_000) == "$250K"
    assert pay(None, 180_000) == "$180K"
    assert pay(200_000, None, "CAD") == "$200K CAD"
    assert pay(95, 120, None) == "$95 to $120"


def test_next_search_is_the_next_weekday_slot_in_pacific_time() -> None:
    # Monday 2026-10-05 at 04:00 PDT (11:00 UTC): the 05:00 search is next.
    assert next_search(datetime(2026, 10, 5, 11, tzinfo=UTC)) == datetime(
        2026, 10, 5, 12, tzinfo=UTC
    )
    # Friday at 16:00 PDT: next is Monday 05:00 PDT.
    assert next_search(datetime(2026, 10, 9, 23, tzinfo=UTC)) == datetime(
        2026, 10, 12, 12, tzinfo=UTC
    )
    # In winter (PST) the same 05:00 search is 13:00 UTC.
    assert next_search(datetime(2026, 12, 1, 12, tzinfo=UTC)) == datetime(
        2026, 12, 1, 13, tzinfo=UTC
    )


def test_stored_times_are_utc() -> None:
    assert _aware(None) is None
    assert _aware(NOW) is NOW
    assert _aware(NOW.replace(tzinfo=None)) == NOW


def test_decisions_are_recorded_and_shown(store: Store, config: SearchConfig) -> None:
    watched = store.upsert_job(_posting(1), NOW)
    other = store.upsert_job(_posting(2), NOW)
    _run(store, "r", NOW, [[watched.job_id, "NEW_POSTING"], [other.job_id, "NEW_POSTING"]])
    data = StoreData(store, config, clock=lambda: NOW)

    assert data.decide(watched.job_id, "WATCH")
    assert not data.decide(999, "WATCH")
    assert not StoreData(None, config).decide(watched.job_id, "WATCH")

    by_id = {o.id: o for o in data.opportunities()}
    assert (by_id[watched.job_id].decision, by_id[watched.job_id].watched) == ("WATCH", True)
    assert (by_id[other.job_id].decision, by_id[other.job_id].watched) == (None, False)
    assert data.decide(watched.job_id, None)
    assert {o.decision for o in data.opportunities()} == {None}
