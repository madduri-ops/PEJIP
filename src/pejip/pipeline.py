"""One search run: fetch, filter, store, analyse, score, explain, digest (spec 14.22).

Failures are isolated (spec 14.45): a failed source does not stop the others, and a
failed analysis leaves that job unranked rather than guessing a result.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pejip.ai.client import AIClient, AIError
from pejip.analysis import EvidenceMatching, JobAnalysis, PostingText, analyze_job
from pejip.config import AlertCompany, SearchConfig, SourceConfig
from pejip.cost import BudgetExceededError
from pejip.digest import Digest, DigestItem, SourceResult
from pejip.discovery import classify_location, is_candidate
from pejip.explain import build_explanation, verify_citations
from pejip.logs import run_id_var
from pejip.models import Posting
from pejip.profile import CareerProfile
from pejip.scoring import JobFacts, score_job
from pejip.sources.email_alerts import S3Inbox, parse_alert
from pejip.sources.greenhouse import fetch_greenhouse
from pejip.sources.http import FetchError, PoliteClient
from pejip.sources.lever import fetch_lever
from pejip.store import AnalysisRecord, RecommendationRecord, Store

log = logging.getLogger(__name__)

Fetcher = Callable[[PoliteClient, SourceConfig], list[Posting]]
FETCHERS: dict[str, Fetcher] = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}


@dataclass
class Pipeline:
    config: SearchConfig
    # Ranking needs both the career profile and Claude. When either is missing the
    # run still finds and stores roles and lists them unranked, saying why.
    profile: CareerProfile | None
    store: Store
    ai: AIClient | None
    http: PoliteClient
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    inbox: S3Inbox | None = None
    unranked_reason: str = "ranking is not set up"
    _analysed: int = 0
    _budget_error: str | None = None

    def run(self) -> Digest:
        run_id = str(uuid.uuid4())
        token = run_id_var.set(run_id)
        try:
            return self._run(run_id)
        finally:
            run_id_var.reset(token)

    def _run(self, run_id: str) -> Digest:
        now = self.clock()
        self.store.start_run(run_id, now)
        purged = self.store.purge_expired(now, self.config.retention_days)
        log.info("run_started", extra={"purged_rows": purged})

        sources: list[SourceResult] = []
        seen: list[tuple[int, str]] = []
        for source in self.config.sources:
            result = SourceResult(f"{source.company} ({source.adapter})", "OK")
            sources.append(result)
            try:
                postings = FETCHERS[source.adapter](self.http, source)
            except FetchError as exc:
                result.status, result.error = "FAILED", str(exc)
                log.warning("source_failed", extra={"source": result.name})
                continue
            result.fetched = len(postings)
            for posting in postings:
                if is_candidate(posting, self.config.taxonomy, self.config.geography):
                    result.candidates += 1
                    upsert = self.store.upsert_job(posting, now)
                    seen.append((upsert.job_id, upsert.discovery))
            log.info(
                "source_fetched",
                extra={
                    "source": result.name,
                    "fetched": result.fetched,
                    "candidates": result.candidates,
                },
            )

        notes: list[str] = []
        if self.profile is None:
            notes.append(f"Roles are unranked because {self.unranked_reason}.")
        elif self.ai is None:
            notes.append(f"New and changed roles are unranked because {self.unranked_reason}.")
        if self.inbox is not None and self.config.inbox is not None:
            companies = self.config.inbox.companies
            sources.append(self._read_inbox(self.inbox, companies, now, seen, notes))

        items: list[DigestItem] = []
        self._analysed = 0
        self._budget_error = None
        for job_id, discovery in seen:
            items.append(self._rank(self.store.get_job(job_id), discovery, now))
        analysed, budget_hit = self._analysed, self._budget_error is not None

        failed_sources = sum(s.status == "FAILED" for s in sources)
        unranked = sum(i.recommendation is None for i in items)
        if sources and failed_sources == len(sources):
            status = "FAILED"
        elif failed_sources or unranked:
            status = "PARTIAL"
        else:
            status = "SUCCESS"
        if budget_hit:
            notes.append("The monthly AI spend cap was reached; remaining roles are unranked.")
        summary = {
            "sources": [vars(s) for s in sources],
            "candidates": len(seen),
            "analysed": analysed,
            "unranked": unranked,
        }
        self.store.finish_run(run_id, status, summary, self.clock())
        log.info(
            "run_finished",
            extra={"status": status, **{k: v for k, v in summary.items() if k != "sources"}},
        )
        return Digest(run_id, now, status, sources, items, notes)

    def _read_inbox(
        self,
        inbox: S3Inbox,
        companies: list[AlertCompany],
        now: datetime,
        seen: list[tuple[int, str]],
        notes: list[str],
    ) -> SourceResult:
        """Turn new job-alert emails into roles, then delete them (design doc 0010)."""
        result = SourceResult("Job-alert inbox (email)", "OK")
        try:
            for key in inbox.message_keys():
                alert = parse_alert(inbox.read(key), companies)
                result.fetched += len(alert.postings)
                for posting in alert.postings:
                    if is_candidate(posting, self.config.taxonomy, self.config.geography):
                        result.candidates += 1
                        upsert = self.store.upsert_job(posting, now)
                        seen.append((upsert.job_id, upsert.discovery))
                if not alert.postings:
                    notes.append(_unread_note(alert.sender, alert.subject, alert.confirm_links))
                inbox.delete(key)
        except FetchError as exc:
            result.status, result.error = "FAILED", str(exc)
            log.warning("source_failed", extra={"source": result.name})
            return result
        log.info(
            "source_fetched",
            extra={
                "source": result.name,
                "fetched": result.fetched,
                "candidates": result.candidates,
            },
        )
        return result

    def _rank(self, job: dict[str, Any], discovery: str, now: datetime) -> DigestItem:
        profile = self.profile
        if profile is None:
            return DigestItem(job, discovery, None, self.unranked_reason)
        latest = self.store.latest_analysis(job["id"])
        if (
            latest is None
            or latest["status"] != "OK"
            or latest["content_hash"] != job["content_hash"]
        ):
            latest, failure = self._analyse_if_allowed(profile, job, now)
            if latest is None:
                return DigestItem(job, discovery, None, failure)
        return DigestItem(job, discovery, self._recommend(profile, job, latest, now))

    def _analyse_if_allowed(
        self, profile: CareerProfile, job: dict[str, Any], now: datetime
    ) -> tuple[dict[str, Any] | None, str]:
        """A fresh analysis, or None and why there is none."""
        # A role analysed before, and unchanged since, is still scored without
        # Claude; only new and changed roles need it.
        if self.ai is None:
            return None, self.unranked_reason
        if self._budget_error is not None:
            return None, self._budget_error
        if self._analysed >= self.config.ai.max_jobs_per_run:
            return None, "deferred to the next run"
        self._analysed += 1
        try:
            return self._analyse(self.ai, profile, job, now), "analysis failed"
        except BudgetExceededError as exc:
            self._budget_error = str(exc)
            return None, self._budget_error

    def _analyse(
        self, ai: AIClient, profile: CareerProfile, job: dict[str, Any], now: datetime
    ) -> dict[str, Any] | None:
        job_id, content_hash = job["id"], job["content_hash"]
        try:
            outcome = analyze_job(ai, profile, PostingText.from_job(job))
        except AIError as exc:
            log.warning("analysis_failed", extra={"job_id": job_id, "error": str(exc)})
            self.store.add_analysis(
                AnalysisRecord(job_id, content_hash, "FAILED", None, str(exc), {}, now)
            )
            return None
        payload = {
            "analysis": outcome.analysis.model_dump(),
            "matching": outcome.matching.model_dump(),
            "dropped_requirements": outcome.dropped_requirements,
        }
        analysis_id = self.store.add_analysis(
            AnalysisRecord(job_id, content_hash, "OK", payload, None, outcome.provenance, now)
        )
        return {"id": analysis_id, "status": "OK", "payload": payload}

    def _recommend(
        self,
        profile: CareerProfile,
        job: dict[str, Any],
        analysis_row: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        payload = analysis_row["payload"]
        analysis = JobAnalysis.model_validate(payload["analysis"])
        matching = EvidenceMatching.model_validate(payload["matching"])
        geo = classify_location(job["location"], self.config.geography)
        facts = JobFacts(
            posted_at=job["posted_at"],
            first_seen_at=job["first_seen_at"],
            comp_min=job["comp_min"],
            comp_max=job["comp_max"],
            location_preference=geo.preference,
            as_of=now,
        )
        rec = score_job(analysis, matching, profile, facts, self.config.scoring)
        explanation = build_explanation(analysis, matching, rec, job)
        verify_citations(explanation, job, profile)
        detail = {**rec.to_dict(), "explanation": explanation}
        self.store.add_recommendation(
            RecommendationRecord(
                job_id=job["id"],
                analysis_id=analysis_row["id"],
                fit=rec.fit,
                confidence=rec.confidence,
                priority=rec.priority,
                detail=detail,
                scoring_version=rec.scoring_version,
                created_at=now,
            )
        )
        return {
            "fit": rec.fit,
            "confidence": rec.confidence,
            "priority": rec.priority,
            "detail": detail,
        }


def _unread_note(sender: str, subject: str, confirm_links: list[str]) -> str:
    """A digest line for an inbox email that listed no roles, such as a sign-up check."""
    note = f"Job-alert inbox: an email from {sender or 'an unknown sender'} "
    note += f'("{subject or "no subject"}") listed no roles.'
    if confirm_links:
        note += " To confirm the alert, open: " + ", ".join(confirm_links)
    return note
