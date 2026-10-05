"""Persistence for jobs, analyses, recommendations, AI spend and search runs.

SQLAlchemy Core keeps the schema portable: SQLite for local runs and tests,
PostgreSQL (spec 14.5) when the service is deployed. Everything here is kept for
``retention_days`` (policy section 10) and can be exported or deleted on request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
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

ai_usage = Table(
    "ai_usage",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("feature", String(64), nullable=False),
    Column("model", String(64), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost_usd", Float, nullable=False),
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


@dataclass(frozen=True)
class UpsertResult:
    job_id: int
    discovery: str  # NEW_POSTING, PREVIOUSLY_SEEN or MATERIALLY_CHANGED


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Store:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url)
        metadata.create_all(self.engine)

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

    def get_job(self, job_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
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

    def add_analysis(
        self,
        job_id: int,
        content_hash: str,
        status: str,
        payload: dict[str, Any] | None,
        error: str | None,
        provenance: dict[str, Any],
        now: datetime,
    ) -> int:
        with self.engine.begin() as conn:
            analysis_id = conn.execute(
                insert(analyses)
                .values(
                    job_id=job_id,
                    content_hash=content_hash,
                    status=status,
                    payload=payload,
                    error=error,
                    provenance=provenance,
                    created_at=now,
                )
                .returning(analyses.c.id)
            ).scalar_one()
        return int(analysis_id)

    def add_recommendation(
        self,
        job_id: int,
        analysis_id: int,
        fit: float | None,
        confidence: str,
        priority: str,
        detail: dict[str, Any],
        scoring_version: str,
        now: datetime,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(recommendations).values(
                    job_id=job_id,
                    analysis_id=analysis_id,
                    fit=fit,
                    confidence=confidence,
                    priority=priority,
                    detail=detail,
                    scoring_version=scoring_version,
                    created_at=now,
                )
            )

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

    # AI spend -------------------------------------------------------------

    def record_ai_usage(
        self,
        feature: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        now: datetime,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(ai_usage).values(
                    at=now,
                    feature=feature,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                )
            )

    def month_spend(self, now: datetime) -> float:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with self.engine.connect() as conn:
            total = conn.execute(
                select(func.coalesce(func.sum(ai_usage.c.cost_usd), 0.0)).where(
                    ai_usage.c.at >= start
                )
            ).scalar_one()
        return float(total)

    # Runs -----------------------------------------------------------------

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

    # Retention, export and deletion (policy section 10) -------------------

    def purge_expired(self, now: datetime, retention_days: int) -> int:
        """Delete everything older than the retention window. Returns rows deleted."""
        cutoff = now - timedelta(days=retention_days)
        deleted = 0
        with self.engine.begin() as conn:
            stale_jobs = select(jobs.c.id).where(jobs.c.last_seen_at < cutoff)
            for table in (recommendations, analyses):
                deleted += conn.execute(
                    delete(table).where(
                        (table.c.created_at < cutoff) | table.c.job_id.in_(stale_jobs)
                    )
                ).rowcount
            deleted += conn.execute(delete(jobs).where(jobs.c.last_seen_at < cutoff)).rowcount
            deleted += conn.execute(delete(ai_usage).where(ai_usage.c.at < cutoff)).rowcount
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
