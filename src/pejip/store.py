"""Persistence for jobs, analyses, recommendations, AI spend and search runs.

SQLAlchemy Core keeps the schema portable: SQLite for local runs and tests,
PostgreSQL (spec 14.5) when the service is deployed. Everything here is kept for
``retention_days`` (policy section 10) and can be exported or deleted on request.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)

from pejip import retention
from pejip.models import Posting

metadata = MetaData()

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("fingerprint", String(64), nullable=False, unique=True),
    Column("source", String(32), nullable=False),
    Column("source_job_id", String(255), nullable=False),
    Column("company", String(255), nullable=False),
    Column("title", String(500), nullable=False),
    Column("location", String(500), nullable=False),
    Column("description", Text, nullable=False),
    Column("url", String(2000), nullable=False),
    Column("posted_at", DateTime(timezone=True)),
    Column("comp_min", Float),
    Column("comp_max", Float),
    Column("comp_currency", String(8)),
    Column("work_model_hint", String(16)),
    Column("content_hash", String(64), nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
)

analyses = Table(
    "analyses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("status", String(16), nullable=False),  # OK or FAILED
    Column("payload", JSON),
    Column("error", Text),
    Column("provenance", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

recommendations = Table(
    "recommendations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("analysis_id", ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
    Column("fit", Float),
    Column("confidence", String(8), nullable=False),
    Column("priority", String(16), nullable=False),
    Column("detail", JSON, nullable=False),
    Column("scoring_version", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# Babu's decisions about roles from the portal (spec 10.4): every click is kept,
# the latest one per job is current, and None clears it. The score he saw is kept
# with it, so later learning knows what the decision was about.
decisions = Table(
    "decisions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("decision", String(32)),
    Column("recommendation_id", Integer),
    Column("fit", Float),
    Column("priority", String(16)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# The search settings an account saved on the portal (design doc 0017): one row,
# replaced on each save and removed by a reset. They are kept until changed, not
# purged after 90 days, so a quiet quarter never silently undoes them; export and
# delete-all cover them like every other table.
search_settings = Table(
    "search_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("settings", JSON, nullable=False),
    Column("saved_at", DateTime(timezone=True), nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(16), nullable=False),
    Column("summary", JSON, nullable=False),
)

# Pages and runs look up a job's analyses, scores and decisions by job; without
# these each lookup read the whole table (design doc 0013).
Index("ix_analyses_job_id", analyses.c.job_id)
Index("ix_recommendations_job_id", recommendations.c.job_id)
Index("ix_decisions_job_id", decisions.c.job_id)

# SQLite caps the parameters in one statement; batched lookups go in chunks.
_CHUNK = 500


def _chunks(ids: list[int]) -> list[list[int]]:
    return [ids[i : i + _CHUNK] for i in range(0, len(ids), _CHUNK)]


@dataclass(frozen=True)
class UpsertResult:
    job_id: int
    discovery: str  # NEW_POSTING, PREVIOUSLY_SEEN or MATERIALLY_CHANGED


@dataclass(frozen=True)
class AnalysisRecord:
    """One stored analysis attempt; ``payload`` is None when it failed."""

    job_id: int
    content_hash: str
    status: str
    payload: dict[str, Any] | None
    error: str | None
    provenance: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class RecommendationRecord:
    job_id: int
    analysis_id: int
    fit: float | None
    confidence: str
    priority: str
    detail: dict[str, Any]
    scoring_version: str
    created_at: datetime


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Store:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url)
        metadata.create_all(self.engine)
        # create_all skips the indexes of tables that already exist.
        for table in metadata.sorted_tables:
            for index in table.indexes:
                index.create(self.engine, checkfirst=True)

    # Jobs -----------------------------------------------------------------

    def upsert_job(self, posting: Posting, now: datetime) -> UpsertResult:
        comp = posting.compensation
        values: dict[str, Any] = {
            "source": posting.source,
            "source_job_id": posting.source_job_id,
            "company": posting.company,
            "title": posting.title,
            "location": posting.location,
            "description": posting.description,
            "url": posting.url,
            "posted_at": posting.posted_at,
            "comp_min": comp.minimum if comp else None,
            "comp_max": comp.maximum if comp else None,
            "comp_currency": comp.currency if comp else None,
            "work_model_hint": posting.work_model_hint,
            "content_hash": posting.content_hash,
            "last_seen_at": now,
        }
        with self.engine.begin() as conn:
            row = conn.execute(
                select(jobs.c.id, jobs.c.content_hash).where(
                    jobs.c.fingerprint == posting.fingerprint
                )
            ).first()
            if row is None:
                job_id = conn.execute(
                    insert(jobs)
                    .values(fingerprint=posting.fingerprint, first_seen_at=now, **values)
                    .returning(jobs.c.id)
                ).scalar_one()
                return UpsertResult(int(job_id), "NEW_POSTING")
            conn.execute(update(jobs).where(jobs.c.id == row.id).values(**values))
            changed = row.content_hash != posting.content_hash
            return UpsertResult(row.id, "MATERIALLY_CHANGED" if changed else "PREVIOUSLY_SEEN")

    def find_job(self, job_id: int) -> dict[str, Any] | None:
        """The job, or None when it does not exist (or was purged)."""
        with self.engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
        return None if row is None else self._job(row)

    def find_jobs(self, job_ids: list[int]) -> dict[int, dict[str, Any]]:
        """The jobs that still exist among ``job_ids``, by id, in one read per chunk."""
        found: dict[int, dict[str, Any]] = {}
        with self.engine.connect() as conn:
            for chunk in _chunks(job_ids):
                for row in conn.execute(select(jobs).where(jobs.c.id.in_(chunk))).mappings():
                    found[row["id"]] = self._job(row)
        return found

    def get_job(self, job_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
        return self._job(row)

    @staticmethod
    def _job(row: Any) -> dict[str, Any]:
        job = dict(row)
        for key in ("posted_at", "first_seen_at", "last_seen_at"):
            job[key] = _aware(job[key])
        return job

    # Analyses and recommendations ------------------------------------------

    def latest_analysis(self, job_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(analyses)
                    .where(analyses.c.job_id == job_id)
                    .order_by(analyses.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def add_analysis(self, record: AnalysisRecord) -> int:
        with self.engine.begin() as conn:
            analysis_id = conn.execute(
                insert(analyses).values(asdict(record)).returning(analyses.c.id)
            ).scalar_one()
        return int(analysis_id)

    def add_recommendation(self, record: RecommendationRecord) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(recommendations).values(asdict(record)))

    def latest_recommendation(self, job_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(recommendations)
                    .where(recommendations.c.job_id == job_id)
                    .order_by(recommendations.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def latest_recommendations(self, job_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Each job's latest recommendation, by job id; unscored jobs are left out."""
        found: dict[int, dict[str, Any]] = {}
        with self.engine.connect() as conn:
            for chunk in _chunks(job_ids):
                latest = (
                    select(func.max(recommendations.c.id))
                    .where(recommendations.c.job_id.in_(chunk))
                    .group_by(recommendations.c.job_id)
                )
                rows = conn.execute(select(recommendations).where(recommendations.c.id.in_(latest)))
                found.update({row["job_id"]: dict(row) for row in rows.mappings()})
        return found

    # Decisions ------------------------------------------------------------

    def add_decision(self, job_id: int, decision: str | None, now: datetime) -> None:
        """Record Babu's decision about a job with the score he saw (None clears it)."""
        rec = self.latest_recommendation(job_id)
        with self.engine.begin() as conn:
            conn.execute(
                decisions.insert().values(
                    job_id=job_id,
                    decision=decision,
                    recommendation_id=rec["id"] if rec else None,
                    fit=rec["fit"] if rec else None,
                    priority=rec["priority"] if rec else None,
                    created_at=now,
                )
            )

    def latest_decisions(self) -> dict[int, str]:
        """Each job's current decision; cleared and undecided jobs are left out."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(decisions.c.job_id, decisions.c.decision).order_by(decisions.c.id)
            ).all()
        current: dict[int, str | None] = dict(rows)  # in order, so the latest wins
        return {job_id: d for job_id, d in current.items() if d is not None}

    # Search settings --------------------------------------------------------

    def save_search_settings(self, settings: dict[str, Any] | None, now: datetime) -> None:
        """Keep ``settings`` as the account's search settings; None goes back to the defaults."""
        with self.engine.begin() as conn:
            conn.execute(delete(search_settings))
            if settings is not None:
                conn.execute(insert(search_settings).values(settings=settings, saved_at=now))

    def saved_search_settings(self) -> tuple[dict[str, Any], datetime] | None:
        """The saved search settings and when they were saved, or None."""
        with self.engine.connect() as conn:
            row = conn.execute(select(search_settings)).mappings().first()
        if row is None:
            return None
        saved_at: datetime = row["saved_at"]
        return row["settings"], saved_at.replace(tzinfo=saved_at.tzinfo or UTC)

    def needs_analysis(self, job: dict[str, Any]) -> bool:
        """True when the posting has no successful analysis of its current text."""
        return not is_current(self.latest_analysis(job["id"]), job)

    def analyses_since(self, since: datetime, ranker: str) -> int:
        """How many successful analyses ``ranker`` stored at or after ``since``."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(analyses.c.provenance).where(
                    (analyses.c.created_at >= since) & (analyses.c.status == "OK")
                )
            ).scalars()
            return sum(1 for provenance in rows if provenance.get("ranker") == ranker)

    # Runs -----------------------------------------------------------------

    def latest_run(self) -> dict[str, Any] | None:
        """The most recent finished run, or None before the first one."""
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(runs)
                    .where(runs.c.finished_at.is_not(None))
                    .order_by(runs.c.started_at.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        run = dict(row)
        run["started_at"] = _aware(run["started_at"])
        run["finished_at"] = _aware(run["finished_at"])
        return run

    def recent_runs(self, limit: int) -> list[dict[str, Any]]:
        """The most recent finished runs, newest first."""
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(runs)
                    .where(runs.c.finished_at.is_not(None))
                    .order_by(runs.c.started_at.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            {
                **row,
                "started_at": _aware(row["started_at"]),
                "finished_at": _aware(row["finished_at"]),
            }
            for row in rows
        ]

    def start_run(self, run_id: str, now: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(runs).values(id=run_id, started_at=now, status="RUNNING", summary={})
            )

    def finish_run(self, run_id: str, status: str, summary: dict[str, Any], now: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(status=status, summary=summary, finished_at=now)
            )

    def mark_digest_sent(self, run_id: str, now: datetime) -> None:
        """Record in the run's summary that its digest went out (design doc 0015)."""
        with self.engine.begin() as conn:
            summary = conn.execute(select(runs.c.summary).where(runs.c.id == run_id)).scalar_one()
            summary = {**summary, "digest_sent_at": now.isoformat()}
            conn.execute(update(runs).where(runs.c.id == run_id).values(summary=summary))

    # Retention, export and deletion (policy section 10) -------------------

    def purge_expired(self, now: datetime, retention_days: int) -> int:
        """Delete everything older than the retention window. Returns rows deleted."""
        cutoff = retention.cutoff(now, retention_days)
        deleted = 0
        with self.engine.begin() as conn:
            stale_jobs = select(jobs.c.id).where(jobs.c.last_seen_at < cutoff)
            deleted += conn.execute(
                delete(decisions).where(
                    (decisions.c.created_at < cutoff) | decisions.c.job_id.in_(stale_jobs)
                )
            ).rowcount
            deleted += conn.execute(
                delete(recommendations).where(
                    (recommendations.c.created_at < cutoff)
                    | recommendations.c.job_id.in_(stale_jobs)
                )
            ).rowcount
            # An analysis is reused while the posting is unchanged, so an old one can
            # still back rankings made inside the window; it goes with its job instead.
            in_use = select(recommendations.c.analysis_id)
            deleted += conn.execute(
                delete(analyses).where(
                    ((analyses.c.created_at < cutoff) & analyses.c.id.not_in(in_use))
                    | analyses.c.job_id.in_(stale_jobs)
                )
            ).rowcount
            deleted += conn.execute(delete(jobs).where(jobs.c.last_seen_at < cutoff)).rowcount
            deleted += conn.execute(delete(runs).where(runs.c.started_at < cutoff)).rowcount
        return deleted

    def export_all(self) -> str:
        """Every stored row, as JSON."""
        out: dict[str, list[dict[str, Any]]] = {}
        with self.engine.connect() as conn:
            for table in metadata.sorted_tables:
                out[table.name] = [dict(r) for r in conn.execute(select(table)).mappings()]
        return json.dumps(out, default=str, indent=2, sort_keys=True)

    def delete_all(self) -> None:
        with self.engine.begin() as conn:
            for table in reversed(metadata.sorted_tables):
                conn.execute(delete(table))


def is_current(analysis: dict[str, Any] | None, job: dict[str, Any]) -> bool:
    """True when ``analysis`` is a successful analysis of the job's current text."""
    return (
        analysis is not None
        and analysis["status"] == "OK"
        and analysis["content_hash"] == job["content_hash"]
    )
