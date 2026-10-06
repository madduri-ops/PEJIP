"""The portal's view of one account's database (design doc 0013).

:class:`StoreData` turns what the search runs store (jobs, recommendations with
their explanations, and run summaries) into the :mod:`pejip.portal.data` records
the pages show. Nothing here writes: when the account has no database yet, the
pages show that no search has run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pejip.config import SearchConfig
from pejip.discovery import classify_location
from pejip.portal.data import (
    Citation,
    Company,
    Connection,
    FitComponent,
    HistoryEvent,
    Network,
    Opportunity,
    Point,
    SearchRun,
    SourceStatus,
)
from pejip.portal.views import PACIFIC_STANDARD, to_pacific
from pejip.store import Store

# Runs shown on Search Health, and how far back a role still counts as open: one
# seen by any search in the last week, so a source that failed today does not
# hide yesterday's roles.
RECENT_RUNS = 10
ACTIVE_FOR = timedelta(days=7)

# When `pejip run` starts, in Pacific time on weekdays (infra variable
# run_schedule, "cron(0 5,10,15 ? * MON-FRI *)").
SEARCH_HOURS = (5, 10, 15)
WEEKDAYS = range(5)

WORK_MODELS = {"REMOTE": "Remote", "HYBRID": "Hybrid", "ONSITE": "Onsite"}

# The "Who you know" lines `pejip.explain.network_points` writes for named people.
MATURED_PREFIX = "Matured connection: "
YOUR_CALL_PREFIX = "Your call: "
NOT_IMPORTED = "Network data has not been imported yet."
NO_CONNECTIONS = "No first-degree connections at "


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _slot(date: date, hour: int) -> datetime:
    """``hour`` o'clock Pacific time on ``date``, in UTC (never near a 2 AM change)."""
    naive = datetime(date.year, date.month, date.day, hour, tzinfo=UTC)
    daylight = naive - (PACIFIC_STANDARD + timedelta(hours=1))
    return daylight if to_pacific(daylight).hour == hour else naive - PACIFIC_STANDARD


def next_search(now: datetime) -> datetime:
    """The next scheduled search after ``now``."""
    today = to_pacific(now).date()
    for days in range(8):
        day = today + timedelta(days=days)
        if day.weekday() in WEEKDAYS:
            for hour in SEARCH_HOURS:
                if (slot := _slot(day, hour)) > now:
                    return slot
    msg = "a week always has a weekday"  # pragma: no cover
    raise AssertionError(msg)  # pragma: no cover


def _money(value: float) -> str:
    return f"${value / 1000:,.0f}K" if value >= 1000 else f"${value:,.0f}"  # noqa: PLR2004


def compensation(job: dict[str, Any]) -> str | None:
    """The published pay range, as the pages show it."""
    low, high = job["comp_min"], job["comp_max"]
    if low is None and high is None:
        return None
    currency = job["comp_currency"]
    suffix = f" {currency}" if currency and currency != "USD" else ""
    if low is not None and high is not None and low != high:
        return f"{_money(low)} to {_money(high)}{suffix}"
    return f"{_money(low if low is not None else high)}{suffix}"


def _citation(raw: dict[str, Any]) -> Citation | None:
    kind = raw.get("type")
    if kind == "posting":
        return Citation("posting", str(raw.get("quote", "")))
    if kind == "profile":
        return Citation("profile", str(raw.get("evidence_id", "")))
    if kind == "job_field":
        return Citation("job_field", str(raw.get("field", "")))
    return None  # network citations name people; "Who you know" shows them instead


def points(raw: Iterable[dict[str, Any]]) -> tuple[Point, ...]:
    """Explanation points with the citations a page can show."""
    return tuple(
        Point(
            str(p["text"]),
            tuple(c for c in map(_citation, p.get("citations", [])) if c is not None),
        )
        for p in raw
    )


def connections(raw: list[dict[str, Any]] | None) -> tuple[Connection, ...] | None:
    """The named people in a stored "Who you know" section.

    None when the section is missing or says no import was read; empty when the
    import has nobody at the company. Strength is not recorded yet.
    """
    if not raw or raw[0]["text"] == NOT_IMPORTED:
        return None
    people: list[Connection] = []
    for p in raw:
        text = str(p["text"])
        for prefix, status in ((MATURED_PREFIX, "MATURED"), (YOUR_CALL_PREFIX, "YOUR_CALL")):
            if text.startswith(prefix):
                name, _, role = text.removeprefix(prefix).partition(", ")
                role = role.split(". ")[0].removesuffix(" (your call)")
                people.append(Connection(name, role, "UNKNOWN", status))
    return tuple(people)


class StoreData:
    """A :class:`pejip.portal.data.PortalData` reading one account's database."""

    is_sample = False

    def __init__(
        self,
        store: Store | None,
        config: SearchConfig | None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._clock = clock or (lambda: datetime.now(UTC))

    def _runs(self) -> list[dict[str, Any]]:
        return self._store.recent_runs(RECENT_RUNS) if self._store else []

    def latest_run(self) -> SearchRun | None:
        runs = self.recent_runs()
        return runs[0] if runs else None

    def recent_runs(self) -> list[SearchRun]:
        now = self._clock()
        return [self._run(row, now if i == 0 else None) for i, row in enumerate(self._runs())]

    @staticmethod
    def _run(row: dict[str, Any], now: datetime | None) -> SearchRun:
        summary = row["summary"] or {}
        sources = tuple(
            SourceStatus(s["name"], s["status"], s.get("fetched", 0), s.get("candidates", 0))
            for s in summary.get("sources", [])
        )
        seen = [discovery for _, discovery in summary.get("seen", [])]
        return SearchRun(
            started_at=row["started_at"],
            status=row["status"],
            sources_searched=sum(s.status == "OK" for s in sources),
            sources_total=len(sources),
            new=seen.count("NEW_POSTING"),
            changed=seen.count("MATERIALLY_CHANGED"),
            expired=0,
            next_run_at=next_search(now) if now else None,
            sources=sources,
        )

    def opportunities(self) -> list[Opportunity]:
        if self._store is None:
            return []
        now = self._clock()
        discovery: dict[int, str] = {}
        for run in reversed(self._runs()):  # oldest first, so the newest run wins
            if run["started_at"] >= now - ACTIVE_FOR:
                discovery.update({int(j): d for j, d in run["summary"].get("seen", [])})
        decided = self._store.latest_decisions()
        # One read for the jobs and one for their scores, not two per role.
        found = self._store.find_jobs(list(discovery))
        recs = self._store.latest_recommendations(list(found))
        return [
            self._opportunity(found[job_id], how, recs.get(job_id), decided.get(job_id))
            for job_id, how in discovery.items()
            if job_id in found
        ]

    def decide(self, opportunity_id: int, decision: str | None) -> bool:
        """Record Babu's decision; False when the account has no such role."""
        if self._store is None or self._store.find_job(opportunity_id) is None:
            return False
        self._store.add_decision(opportunity_id, decision, self._clock())
        return True

    def _opportunity(
        self,
        job: dict[str, Any],
        discovery: str,
        rec: dict[str, Any] | None,
        decision: str | None,
    ) -> Opportunity:
        detail = rec["detail"] if rec else {}
        explanation = detail.get("explanation", {})
        scope = (
            classify_location(job["location"], self._config.geography).scope
            if self._config
            else None
        )
        history = [HistoryEvent(job["first_seen_at"], "First discovered by a search")]
        if discovery == "MATERIALLY_CHANGED":
            history.append(HistoryEvent(job["last_seen_at"], "The posting changed materially"))
        if rec:
            fit = "unknown" if rec["fit"] is None else f"{rec['fit']:.0f}"
            history.append(
                HistoryEvent(
                    _aware(rec["created_at"]) or job["last_seen_at"],
                    f"Scored: fit {fit}, priority {str(rec['priority']).title()}",
                )
            )
        return Opportunity(
            id=job["id"],
            title=job["title"],
            company=job["company"],
            location=job["location"] or "Location not stated",
            work_model=WORK_MODELS.get(str(job["work_model_hint"]).upper()),
            compensation=compensation(job),
            posted_at=job["posted_at"],
            first_seen_at=job["first_seen_at"],
            fit=rec["fit"] if rec else None,
            confidence=rec["confidence"] if rec else "UNKNOWN",
            priority=rec["priority"] if rec else "UNRANKED",
            discovery=discovery,
            source=job["source"],
            url=job["url"],
            description=job["description"],
            components=tuple(
                FitComponent(c["name"], c["value"]) for c in detail.get("components", [])
            ),
            why_it_fits=points(explanation.get("why_it_fits", [])),
            concerns=points(explanation.get("concerns", [])),
            why_now=points(explanation.get("why_now", [])),
            connections=connections(explanation.get("who_you_know")),
            change_note=(
                "The posting changed materially since it was last seen."
                if discovery == "MATERIALLY_CHANGED"
                else None
            ),
            location_scope=scope,
            verified_on=job["source"].capitalize(),
            requisition=job["source_job_id"],
            last_verified_at=job["last_seen_at"],
            history=tuple(history),
            decision=decision,
            watched=decision == "WATCH",
        )

    def companies(self) -> list[Company]:
        """Tracked companies from the search setup: careers boards and job alerts."""
        if self._config is None:
            return []
        found: dict[str, Company] = {}
        for source in self._config.sources:
            found.setdefault(source.company, self._company(source.company, "Careers site feed"))
        if self._config.inbox is not None:
            for alert in self._config.inbox.companies:
                if not alert.job_board:
                    found.setdefault(alert.company, self._company(alert.company, "Job alerts"))
        return list(found.values())

    @staticmethod
    def _company(name: str, job_source: str) -> Company:
        return Company(
            name=name,
            industry=None,
            target=True,
            watching=False,
            monitoring="NORMAL",
            relevance="NO_CURRENT_MATCH",
            job_source=job_source,
        )

    def network(self) -> Network | None:
        # The LinkedIn import is read by the search run, not stored for the portal yet.
        return None
