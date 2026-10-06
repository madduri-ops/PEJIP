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
from pejip.explain import build_explanation, network_points, verify_citations
from pejip.logs import run_id_var
from pejip.models import Posting
from pejip.network.matching import NetworkIndex, NetworkSignal
from pejip.profile import CareerProfile
from pejip.scoring import JobFacts, score_job
from pejip.sources.ashby import fetch_ashby
from pejip.sources.email_alerts import S3Inbox, parse_alert
from pejip.sources.greenhouse import fetch_greenhouse
from pejip.sources.http import FetchError, PoliteClient
from pejip.sources.lever import fetch_lever
from pejip.store import AnalysisRecord, RecommendationRecord, Store, is_current

log = logging.getLogger(__name__)

Fetcher = Callable[[PoliteClient, SourceConfig], list[Posting]]
FETCHERS: dict[str, Fetcher] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


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
    network: NetworkIndex | None = None
    unranked_reason: str = "ranking is not set up"
    # The Claude Code routine analyses new roles after the run (design doc 0015),
    # so their waiting is expected, not worth a digest note.
    routine: bool = False
    _analysed: int = 0
    _budget_error: str | None = None
    _new_recommendations_only: bool = False

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
        elif self.ai is None and not self.routine:
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

        # Roles left for the routine are expected to be unranked now, not a fault.
        waiting = self.routine and self.profile is not None
        status = _status(sources, items, unranked_expected=waiting)
        unranked = sum(i.recommendation is None for i in items)
        notes += _network_notes(self.network)
        if budget_hit:
            notes.append("The monthly AI spend cap was reached; remaining roles are unranked.")
        summary = {
            "sources": [vars(s) for s in sources],
            "candidates": len(seen),
            "analysed": analysed,
            "unranked": unranked,
            # Kept so `pejip digest` can rank this run's roles again later (design 0015).
            "seen": [list(pair) for pair in seen],
            "notes": notes,
        }
        self.store.finish_run(run_id, status, summary, self.clock())
        log.info(
            "run_finished",
            extra={"status": status, **{k: v for k, v in summary.items() if k not in _UNLOGGED}},
        )
        return Digest(run_id, now, status, sources, items, notes)

    def digest_from(self, run: dict[str, Any]) -> Digest:
        """The digest of an earlier run, ranked again with the analyses stored since.

        The ranking routine (design doc 0015) analyses a run's new roles after the run
        ends; this scores them, without fetching anything or starting a new run.
        """
        now = self.clock()
        summary = run["summary"]
        # Runs stored before design 0015 have no "seen" or "notes".
        sources = [SourceResult(**s) for s in summary.get("sources", [])]
        self._analysed = 0
        self._budget_error = None
        # Roles the run already scored are scored again without a second
        # recommendation row; a role two sources reported is listed once.
        self._new_recommendations_only = True
        items = []
        for job_id, discovery in dict(map(tuple, summary.get("seen", []))).items():
            job = self.store.find_job(job_id)
            if job is not None:
                items.append(self._rank(job, discovery, now))
        status = _status(sources, items)
        log.info(
            "digest_built",
            extra={
                "status": status,
                "roles": len(items),
                "unranked": sum(i.recommendation is None for i in items),
            },
        )
        return Digest(run["id"], now, status, sources, items, list(summary.get("notes", [])))

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
        ignored = 0
        try:
            for key in inbox.message_keys():
                alert = parse_alert(inbox.read(key), companies)
                result.fetched += len(alert.postings)
                for posting in alert.postings:
                    if is_candidate(posting, self.config.taxonomy, self.config.geography):
                        result.candidates += 1
                        upsert = self.store.upsert_job(posting, now)
                        seen.append((upsert.job_id, upsert.discovery))
                if alert.confirm_links:
                    notes.append(_confirm_note(alert.sender, alert.subject, alert.confirm_links))
                elif not alert.postings:
                    ignored += 1
                inbox.delete(key)
        except FetchError as exc:
            result.status, result.error = "FAILED", str(exc)
            log.warning("source_failed", extra={"source": result.name})
        if ignored:
            # A count only: these may be Babu's personal emails (policy section 10).
            counted = "1 other email had no roles and was deleted"
            if ignored > 1:
                counted = f"{ignored} other emails had no roles and were deleted"
            notes.append(f"Job-alert inbox: {counted}.")
        if result.status == "FAILED":
            return result
        log.info(
            "source_fetched",
            extra={
                "source": result.name,
                "fetched": result.fetched,
                "candidates": result.candidates,
                "ignored_emails": ignored,
            },
        )
        return result

    def _rank(self, job: dict[str, Any], discovery: str, now: datetime) -> DigestItem:
        profile = self.profile
        if profile is None:
            return DigestItem(job, discovery, None, self.unranked_reason)
        latest = self.store.latest_analysis(job["id"])
        if latest is None or not is_current(latest, job):
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

    def _recorded(self, job_id: int, analysis_id: int, scoring_version: str) -> bool:
        """In ``digest_from``: the run already stored this exact recommendation."""
        if not self._new_recommendations_only:
            return False
        latest = self.store.latest_recommendation(job_id)
        return (
            latest is not None
            and latest["analysis_id"] == analysis_id
            and latest["scoring_version"] == scoring_version
        )

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
        signal: NetworkSignal | None = None
        if self.network is not None:
            signal = self.network.signal(job["company"], analysis.inferred_seniority, job["title"])
        facts = JobFacts(
            posted_at=job["posted_at"],
            first_seen_at=job["first_seen_at"],
            comp_min=job["comp_min"],
            comp_max=job["comp_max"],
            location_preference=geo.preference,
            as_of=now,
            network=signal.facts() if signal is not None else None,
        )
        rec = score_job(analysis, matching, profile, facts, self.config.scoring)
        explanation = build_explanation(analysis, matching, rec, job, signal)
        # A strong role where Babu knows nobody directly gets a warm-path prompt.
        strong = rec.fit is not None and rec.fit >= self.config.scoring.strong_match_fit
        explanation["who_you_know"] = network_points(signal, job["company"], warm_path=strong)
        verify_citations(explanation, job, profile, signal)
        detail = {**rec.to_dict(), "explanation": explanation}
        if not self._recorded(job["id"], analysis_row["id"], rec.scoring_version):
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


# Run summary fields kept in the database but left out of the run_finished log line.
_UNLOGGED = frozenset({"sources", "seen", "notes"})


def _status(
    sources: list[SourceResult], items: list[DigestItem], *, unranked_expected: bool = False
) -> str:
    failed_sources = sum(s.status == "FAILED" for s in sources)
    unranked = 0 if unranked_expected else sum(i.recommendation is None for i in items)
    if sources and failed_sources == len(sources):
        status = "FAILED"
    elif failed_sources or unranked:
        status = "PARTIAL"
    else:
        status = "SUCCESS"
    return status


def _network_notes(index: NetworkIndex | None) -> list[str]:
    """Digest lines on the connections snapshot (spec 8.19) and names to review."""
    if index is None:
        return []
    when = f"{index.imported_at:%B %-d, %Y}" if index.imported_at else "never"
    notes = [f"LinkedIn connections last refreshed: {when}."]
    if index.unresolved:
        names = "; ".join(
            f"{raw} ({index.held_back[raw]}, could be {' or '.join(res.candidates)})"
            for raw, res in sorted(index.unresolved.items())
        )
        notes.append(
            "Employer names to review before their connections count (add them to your"
            f" network decisions file): {names}."
        )
    return notes


def _confirm_note(sender: str, subject: str, confirm_links: list[str]) -> str:
    """A digest line for a job site's sign-up check, so Babu can finish signing up."""
    note = f"Job-alert inbox: {sender or 'a job site'} asks you to confirm an alert "
    note += f'("{subject or "no subject"}"). Open: ' + ", ".join(confirm_links)
    return note
