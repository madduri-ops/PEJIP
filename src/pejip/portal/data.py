"""What the portal pages show, and the interface they read it through.

The pages never touch the database directly. They read a :class:`PortalData`, so the
source can change without touching a page: :class:`pejip.portal.sample.SampleData`
today, a store-backed reader once the persistent database lands.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Priority bands in the order the portal ranks them (spec 9.25).
PRIORITY_ORDER = ("IMMEDIATE", "HIGH", "MEDIUM", "LOW", "UNRANKED", "EXCLUDED")


@dataclass(frozen=True)
class Citation:
    """Where an explanation point comes from (``pejip.explain`` citations).

    ``kind`` is ``posting`` (``text`` quotes the job posting), ``profile`` (``text``
    is a career-profile evidence item) or ``job_field`` (``text`` names a stored
    job field such as the posting date).
    """

    kind: str
    text: str


@dataclass(frozen=True)
class Point:
    """One explanation line and the evidence it cites (spec 9.29)."""

    text: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class Connection:
    """Someone Babu knows at the hiring company. ``strength`` may be UNKNOWN."""

    name: str
    role: str
    strength: str


@dataclass(frozen=True)
class FitComponent:
    """One Fit input (``scoring.Component``): value 0 to 1, or None when unknown."""

    name: str
    value: float | None


@dataclass(frozen=True)
class Opportunity:
    """A ranked role with its explanation, as the pages show it."""

    id: int
    title: str
    company: str
    location: str
    work_model: str | None
    compensation: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    fit: float | None
    confidence: str
    priority: str
    discovery: str  # NEW_POSTING, MATERIALLY_CHANGED or PREVIOUSLY_SEEN
    source: str
    url: str
    description: str
    components: tuple[FitComponent, ...] = ()
    why_it_fits: tuple[Point, ...] = ()
    concerns: tuple[Point, ...] = ()
    why_now: tuple[Point, ...] = ()
    # None until a LinkedIn connections export has been imported.
    connections: tuple[Connection, ...] | None = None
    watched: bool = False
    change_note: str | None = None


@dataclass(frozen=True)
class SourceStatus:
    """How one source did in a run (``pejip.digest.SourceResult``).

    ``status`` is OK or FAILED. Low-level errors stay in the logs; the portal shows
    only the impact (spec 12.31).
    """

    name: str
    status: str
    fetched: int
    candidates: int


@dataclass(frozen=True)
class SearchRun:
    """One search run: the status line on every page and the Search Health page."""

    started_at: datetime
    status: str  # SUCCESS, PARTIAL or FAILED
    sources_searched: int
    sources_total: int
    new: int
    changed: int
    expired: int
    next_run_at: datetime | None
    sources: tuple[SourceStatus, ...] = ()


@dataclass(frozen=True)
class Signal:
    """A company development worth knowing, with where it came from (spec 12.19)."""

    text: str
    source: str
    seen_at: datetime


@dataclass(frozen=True)
class Company:
    """A company PEJIP tracks: a target Babu chose, or one discovered in searches.

    Whether it has matching jobs comes from the opportunities, not from here;
    ``relevance`` (STRATEGICALLY_RELEVANT, NO_CURRENT_MATCH or LOW_RELEVANCE) is
    what the portal shows when it has none (spec 12.18, 12.21).
    """

    name: str
    industry: str | None
    target: bool
    watching: bool
    monitoring: str  # HIGH, NORMAL or LOW
    relevance: str
    job_source: str
    coverage_note: str | None = None
    signals: tuple[Signal, ...] = ()
    # None until a LinkedIn connections export maps people to this company.
    connections: int | None = None
    low_reason: str | None = None


class PortalData(Protocol):
    """Read-only source of everything the portal shows."""

    @property
    def is_sample(self) -> bool:
        """True when the data is illustrative; every page then says so."""

    def latest_run(self) -> SearchRun | None:
        """The most recent search run, or None before the first one."""

    def recent_runs(self) -> list[SearchRun]:
        """Recent search runs, newest first; empty before the first one."""

    def opportunities(self) -> list[Opportunity]:
        """Every active opportunity, in any order."""

    def companies(self) -> list[Company]:
        """Target companies and companies discovered in searches, in any order."""
