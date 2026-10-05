"""Ranking, saved views, filters and time display for the portal (spec 12.6, 12.7).

Pure functions over :class:`pejip.portal.data.Opportunity`, so they are tested
without a server and stay the same whichever data source is plugged in.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from pejip.portal.data import PRIORITY_ORDER, Company, Opportunity

HIGH_FIT = 85
# Bands the default views show; LOW and below appear only in "All active".
SHOWN_BANDS = frozenset({"IMMEDIATE", "HIGH", "MEDIUM"})


def _has_strong_connection(o: Opportunity) -> bool:
    return any(c.strength == "STRONG" for c in o.connections or ())


@dataclass(frozen=True)
class View:
    key: str
    label: str
    matches: Callable[[Opportunity], bool]


VIEWS = (
    View("attention", "Requires attention", lambda o: o.priority in ("IMMEDIATE", "HIGH")),
    View("new", "New postings", lambda o: o.discovery == "NEW_POSTING"),
    View("high-fit", "High fit", lambda o: (o.fit or 0) >= HIGH_FIT),
    View("immediate", "Immediate priority", lambda o: o.priority == "IMMEDIATE"),
    View("watched", "Watched", lambda o: o.watched),
    View("network", "Strong network", _has_strong_connection),
    View("remote", "Remote", lambda o: o.work_model == "Remote"),
    View("changed", "Recently changed", lambda o: o.discovery == "MATERIALLY_CHANGED"),
    View("all", "All active", lambda _o: True),
)
VIEW_BY_KEY = {v.key: v for v in VIEWS}
DEFAULT_VIEW = "attention"

PRIORITY_CHOICES = ("IMMEDIATE", "HIGH", "MEDIUM", "LOW")
CONFIDENCE_CHOICES = ("HIGH", "MEDIUM", "LOW")
FIT_CHOICES = (90, 80, 70)
WORK_MODEL_CHOICES = ("Remote", "Hybrid", "Onsite")
MAX_COMPANY_FILTER = 100


@dataclass(frozen=True)
class Filters:
    """Filters from the query string. Unknown values are ignored, never echoed raw."""

    view: str = DEFAULT_VIEW
    priority: str = ""
    min_fit: int = 0
    confidence: str = ""
    company: str = ""
    work_model: str = ""

    @classmethod
    def from_query(cls, query: Mapping[str, str]) -> Filters:
        def pick(name: str, allowed: tuple[str, ...]) -> str:
            value = query.get(name, "")
            return value if value in allowed else ""

        fit = query.get("fit", "")
        return cls(
            view=query.get("view", "") if query.get("view", "") in VIEW_BY_KEY else DEFAULT_VIEW,
            priority=pick("priority", PRIORITY_CHOICES),
            min_fit=int(fit) if fit in {str(f) for f in FIT_CHOICES} else 0,
            confidence=pick("confidence", CONFIDENCE_CHOICES),
            company=query.get("company", "").strip()[:MAX_COMPANY_FILTER],
            work_model=pick("work_model", WORK_MODEL_CHOICES),
        )

    @property
    def any_set(self) -> bool:
        """True when a filter beyond the view is applied."""
        return any((self.priority, self.min_fit, self.confidence, self.company, self.work_model))

    def keep(self, o: Opportunity) -> bool:
        """True when ``o`` passes every filter (the view is applied separately)."""
        return (
            (not self.priority or o.priority == self.priority)
            and (o.fit or 0) >= self.min_fit
            and (not self.confidence or o.confidence == self.confidence)
            and (not self.company or self.company.lower() in o.company.lower())
            and (not self.work_model or o.work_model == self.work_model)
        )


def _seen(o: Opportunity) -> datetime:
    return o.posted_at or o.first_seen_at


def rank(items: list[Opportunity]) -> list[Opportunity]:
    """Priority, then Fit (unknown last), then freshness (spec 12.6)."""
    return sorted(
        items,
        key=lambda o: (
            PRIORITY_ORDER.index(o.priority)
            if o.priority in PRIORITY_ORDER
            else len(PRIORITY_ORDER),
            -(o.fit if o.fit is not None else -1),
            -_seen(o).timestamp(),
        ),
    )


@dataclass(frozen=True)
class Listing:
    """What the Opportunities page shows for one request."""

    view: View
    in_view: list[Opportunity]
    others: list[Opportunity]
    counts: dict[str, int]


def list_opportunities(items: list[Opportunity], filters: Filters) -> Listing:
    """Split the ranked, filtered roles into the chosen view and the rest."""
    view = VIEW_BY_KEY[filters.view]
    kept = [o for o in rank(items) if filters.keep(o)]
    shown = kept if view.key == "all" else [o for o in kept if o.priority in SHOWN_BANDS]
    in_view = [o for o in kept if view.matches(o)]
    others = [o for o in shown if o not in in_view]
    counts = {v.key: sum(v.matches(o) for o in kept) for v in VIEWS}
    return Listing(view, in_view, others, counts)


# ── Companies (spec 12.18 to 12.21) ──────────────────────────────────────────
MONITORING_ORDER = ("HIGH", "NORMAL", "LOW")


@dataclass(frozen=True)
class CompanyRow:
    """A company with its matching roles, ranked, and the state the page shows."""

    company: Company
    jobs: list[Opportunity]

    @property
    def state(self) -> str:
        return "MATCHING_JOBS" if self.jobs else self.company.relevance

    @property
    def high_priority(self) -> int:
        return sum(o.priority in ("IMMEDIATE", "HIGH") for o in self.jobs)


@dataclass(frozen=True)
class CompanyView:
    key: str
    label: str
    matches: Callable[[CompanyRow], bool]


COMPANY_VIEWS = (
    CompanyView("all", "All", lambda _r: True),
    CompanyView("matching", "Matching jobs", lambda r: r.state == "MATCHING_JOBS"),
    CompanyView("watching", "Watching", lambda r: r.company.watching),
    CompanyView(
        "relevant", "Strategically relevant", lambda r: r.state == "STRATEGICALLY_RELEVANT"
    ),
    CompanyView("no-match", "No current match", lambda r: r.state == "NO_CURRENT_MATCH"),
    CompanyView("low", "Low relevance", lambda r: r.state == "LOW_RELEVANCE"),
)
COMPANY_VIEW_BY_KEY = {v.key: v for v in COMPANY_VIEWS}


@dataclass(frozen=True)
class CompanyListing:
    view: CompanyView
    targets: list[CompanyRow]
    discovered: list[CompanyRow]
    counts: dict[str, int]


def company_rows(companies: list[Company], items: list[Opportunity]) -> list[CompanyRow]:
    """Each company with its shown roles; monitoring priority, then urgent roles first."""
    ranked = rank(items)
    rows = [
        CompanyRow(c, [o for o in ranked if o.company == c.name and o.priority in SHOWN_BANDS])
        for c in companies
    ]
    return sorted(
        rows,
        key=lambda r: (
            MONITORING_ORDER.index(r.company.monitoring)
            if r.company.monitoring in MONITORING_ORDER
            else len(MONITORING_ORDER),
            -r.high_priority,
            -len(r.jobs),
            r.company.name.lower(),
        ),
    )


def list_companies(
    companies: list[Company], items: list[Opportunity], view_key: str
) -> CompanyListing:
    """Targets and discovered companies in the chosen view; unknown views show all."""
    view = COMPANY_VIEW_BY_KEY.get(view_key, COMPANY_VIEWS[0])
    rows = company_rows(companies, items)
    shown = [r for r in rows if view.matches(r)]
    counts = {v.key: sum(v.matches(r) for r in rows) for v in COMPANY_VIEWS}
    return CompanyListing(
        view,
        [r for r in shown if r.company.target],
        [r for r in shown if not r.company.target],
        counts,
    )


# ── Time display ─────────────────────────────────────────────────────────────
# Babu is in Pacific time. The container image has no time zone database, so US
# daylight saving rules (second Sunday of March to first Sunday of November, at
# 2 AM local) are applied here.
PACIFIC_STANDARD = timedelta(hours=-8)
MARCH, NOVEMBER, SUNDAY = 3, 11, 6


def _nth_sunday(year: int, month: int, n: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=UTC)
    offset = (SUNDAY - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


PST = timezone(PACIFIC_STANDARD, "PST")
PDT = timezone(PACIFIC_STANDARD + timedelta(hours=1), "PDT")


def to_pacific(moment: datetime) -> datetime:
    """``moment`` in Pacific time, with a PST or PDT zone."""
    utc = moment.astimezone(UTC)
    # DST starts at 2 AM PST (10:00 UTC) and ends at 2 AM PDT (09:00 UTC).
    start = _nth_sunday(utc.year, MARCH, 2) + timedelta(hours=10)
    end = _nth_sunday(utc.year, NOVEMBER, 1) + timedelta(hours=9)
    return utc.astimezone(PDT if start <= utc < end else PST)


def _clock(local: datetime) -> str:
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"  # noqa: PLR2004


def when(moment: datetime | None, now: datetime) -> str:
    """ "Today 12:00 PM", "Yesterday 5:00 PM" or "Oct 2, 9:15 AM" in Pacific time."""
    if moment is None:
        return "Unknown"
    local = to_pacific(moment)
    today = to_pacific(now)
    days = (today.date() - local.date()).days
    if days == 0:
        return f"Today {_clock(local)}"
    if days == 1:
        return f"Yesterday {_clock(local)}"
    if days == -1:
        return f"Tomorrow {_clock(local)}"
    return f"{local:%b} {local.day}, {_clock(local)}"


def age(moment: datetime | None, now: datetime) -> str:
    """How long ago, coarsely: "just now", "4h ago", "2d ago"."""
    if moment is None:
        return "Unknown"
    hours = int((now - moment).total_seconds() // 3600)
    if hours < 1:
        return "just now"
    if hours < 24:  # noqa: PLR2004
        return f"{hours}h ago"
    return f"{hours // 24}d ago"
