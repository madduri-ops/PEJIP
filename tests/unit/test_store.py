from __future__ import annotations

import json
from datetime import timedelta

from pejip.models import Compensation, Posting
from pejip.store import AnalysisRecord, RecommendationRecord, Store, _aware
from tests.conftest import NOW


def posting(description: str = "Body", comp: Compensation | None = None) -> Posting:
    return Posting(
        "greenhouse",
        "b:1",
        "Co",
        "VP Ops",
        "Oakland",
        description,
        "https://e/1",
        NOW,
        comp,
        "HYBRID",
    )


def test_upsert_classifies_new_seen_and_changed(store: Store) -> None:
    first = store.upsert_job(posting(comp=Compensation(1.0, 2.0, "USD")), NOW)
    assert first.discovery == "NEW_POSTING"
    again = store.upsert_job(posting(), NOW + timedelta(hours=1))
    assert (again.job_id, again.discovery) == (first.job_id, "PREVIOUSLY_SEEN")
    changed = store.upsert_job(posting("New body"), NOW + timedelta(hours=2))
    assert changed.discovery == "MATERIALLY_CHANGED"
    job = store.get_job(first.job_id)
    assert job["description"] == "New body"
    assert job["first_seen_at"] == NOW
    assert job["last_seen_at"] == NOW + timedelta(hours=2)
    assert job["posted_at"].tzinfo is not None
    assert job["comp_min"] is None  # the latest observation had no pay


def test_analyses_and_recommendations(store: Store) -> None:
    job_id = store.upsert_job(posting(), NOW).job_id
    assert store.latest_analysis(job_id) is None
    assert store.latest_recommendation(job_id) is None
    store.add_analysis(AnalysisRecord(job_id, "h", "FAILED", None, "boom", {}, NOW))
    second = store.add_analysis(
        AnalysisRecord(job_id, "h", "OK", {"a": 1}, None, {"model": "m"}, NOW)
    )
    latest = store.latest_analysis(job_id)
    assert latest is not None
    assert (latest["id"], latest["status"]) == (second, "OK")
    store.add_recommendation(
        RecommendationRecord(job_id, second, 90.0, "HIGH", "HIGH", {"x": 1}, "fit-1", NOW)
    )
    rec = store.latest_recommendation(job_id)
    assert rec is not None
    assert rec["fit"] == 90.0


def test_runs_are_recorded(store: Store) -> None:
    store.start_run("r1", NOW)
    store.finish_run("r1", "SUCCESS", {"n": 1}, NOW)
    exported = json.loads(store.export_all())
    assert exported["runs"][0]["status"] == "SUCCESS"


def test_purge_removes_expired_rows_only(store: Store) -> None:
    old = NOW - timedelta(days=120)
    old_job = store.upsert_job(posting(), old).job_id
    store.add_analysis(AnalysisRecord(old_job, "h", "OK", {}, None, {}, old))
    store.start_run("old", old)
    fresh = Posting("lever", "c:2", "Co", "VP", "SF", "d", "u")
    fresh_id = store.upsert_job(fresh, NOW).job_id
    stale_analysis = store.add_analysis(AnalysisRecord(fresh_id, "h", "OK", {}, None, {}, old))
    store.add_recommendation(
        RecommendationRecord(fresh_id, stale_analysis, 1.0, "LOW", "LOW", {}, "v", old)
    )
    store.add_analysis(AnalysisRecord(fresh_id, "h", "OK", {}, None, {}, NOW))

    deleted = store.purge_expired(NOW, 90)

    assert deleted == 5
    data = json.loads(store.export_all())
    assert [j["id"] for j in data["jobs"]] == [fresh_id]
    assert len(data["analyses"]) == 1
    assert data["runs"] == data["recommendations"] == []


def test_purge_keeps_an_old_analysis_that_backs_a_recent_ranking(store: Store) -> None:
    old = NOW - timedelta(days=120)
    job_id = store.upsert_job(posting(), NOW).job_id
    reused = store.add_analysis(AnalysisRecord(job_id, "h", "OK", {}, None, {}, old))
    store.add_recommendation(
        RecommendationRecord(job_id, reused, 80.0, "HIGH", "HIGH", {}, "v", NOW)
    )

    assert store.purge_expired(NOW, 90) == 0
    assert store.latest_analysis(job_id) is not None
    assert store.latest_recommendation(job_id) is not None


def test_delete_all(store: Store) -> None:
    job_id = store.upsert_job(posting(), NOW).job_id
    store.add_analysis(AnalysisRecord(job_id, "h", "OK", {}, None, {}, NOW))
    store.delete_all()
    assert all(rows == [] for rows in json.loads(store.export_all()).values())


def test_aware_keeps_existing_timezones() -> None:
    assert _aware(NOW) is NOW
    assert _aware(None) is None
    assert _aware(NOW.replace(tzinfo=None)) == NOW


def test_decisions_keep_the_score_seen_and_the_latest_wins(store: Store) -> None:
    ranked = store.upsert_job(posting(), NOW).job_id
    analysis = store.add_analysis(AnalysisRecord(ranked, "h", "OK", {}, None, {}, NOW))
    store.add_recommendation(
        RecommendationRecord(ranked, analysis, 88.0, "HIGH", "HIGH", {}, "v", NOW)
    )
    unranked = store.upsert_job(Posting("lever", "c:2", "Co", "VP", "SF", "d", "u"), NOW).job_id
    cleared = store.upsert_job(Posting("lever", "c:3", "Co", "VP", "SF", "d", "u"), NOW).job_id

    store.add_decision(ranked, "WATCH", NOW)
    store.add_decision(ranked, "ALREADY_APPLIED", NOW)
    store.add_decision(unranked, "NOT_INTERESTED", NOW)
    store.add_decision(cleared, "INTERESTED", NOW)
    store.add_decision(cleared, None, NOW)

    assert store.latest_decisions() == {ranked: "ALREADY_APPLIED", unranked: "NOT_INTERESTED"}
    rows = json.loads(store.export_all())["decisions"]
    assert len(rows) == 5
    assert (rows[0]["fit"], rows[0]["priority"], rows[0]["recommendation_id"]) == (
        88.0,
        "HIGH",
        1,
    )
    assert rows[2]["fit"] is rows[2]["recommendation_id"] is None


def test_purge_removes_old_decisions_and_those_of_expired_jobs(store: Store) -> None:
    old = NOW - timedelta(days=120)
    expired = store.upsert_job(posting(), old).job_id
    current = store.upsert_job(Posting("lever", "c:2", "Co", "VP", "SF", "d", "u"), NOW).job_id
    store.add_decision(expired, "WATCH", NOW)
    store.add_decision(current, "WATCH", old)
    store.add_decision(current, "INTERESTED", NOW)

    assert store.purge_expired(NOW, 90) == 3  # two decisions and the expired job
    assert store.latest_decisions() == {current: "INTERESTED"}
