"""Illustrative portal data, shown until the persistent database lands.

Everything here is invented (policy section 10): companies are "Company A" and so
on, people are "Person A", and numbers follow the spec's examples. Times are
relative to the clock, so the sample always looks current. Every page shows the
sample-data banner while this source is in use.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pejip.portal.data import (
    Citation,
    Company,
    Connection,
    FitComponent,
    Opportunity,
    Point,
    SearchRun,
    Signal,
    SourceStatus,
)


def _components(*values: float | None) -> tuple[FitComponent, ...]:
    names = (
        "ROLE_RESPONSIBILITY",
        "SENIORITY_SCOPE",
        "CAPABILITY",
        "LEADERSHIP",
        "CAREER_DIRECTION",
        "DOMAIN_INDUSTRY",
    )
    return tuple(FitComponent(n, v) for n, v in zip(names, values, strict=True))


def _quote(text: str) -> Citation:
    return Citation("posting", text)


def _evidence(text: str) -> Citation:
    return Citation("profile", text)


def _field(name: str) -> Citation:
    return Citation("job_field", name)


DESCRIPTION = (
    "{company} is looking for a {title} to lead enterprise-wide technology "
    "modernization across all business units.\n\n"
    "Own the multi-year transformation portfolio and its governance.\n"
    "Lead a global organization of program and operations leaders.\n"
    "Partner with the executive team on operating model and investment priorities."
)


def _scope(location: str) -> str | None:
    if location == "United States":
        return "US_REMOTE"
    return "BAY_AREA" if location.endswith(", CA") or "Bay Area" in location else None


def _opportunity(  # noqa: PLR0913 - one row of sample data per call
    now: datetime,
    *,
    number: int,
    title: str,
    company: str,
    location: str,
    work_model: str | None,
    compensation: str | None,
    posted_hours: float | None,
    seen_hours: float,
    fit: float | None,
    confidence: str,
    priority: str,
    components: tuple[FitComponent, ...] = (),
    why_it_fits: tuple[Point, ...] = (),
    concerns: tuple[Point, ...] = (),
    why_now: tuple[Point, ...] = (),
    connections: tuple[Connection, ...] | None = None,
    watched: bool = False,
    discovery: str = "NEW_POSTING",
    change_note: str | None = None,
) -> Opportunity:
    return Opportunity(
        id=number,
        title=title,
        company=company,
        location=location,
        work_model=work_model,
        compensation=compensation,
        posted_at=None if posted_hours is None else now - timedelta(hours=posted_hours),
        first_seen_at=now - timedelta(hours=seen_hours),
        fit=fit,
        confidence=confidence,
        priority=priority,
        discovery=discovery,
        source="greenhouse",
        url=f"https://example.com/careers/{number}",
        description=DESCRIPTION.format(company=company, title=title),
        components=components,
        why_it_fits=why_it_fits,
        concerns=concerns,
        why_now=why_now,
        connections=connections,
        watched=watched,
        change_note=change_note,
        location_scope=_scope(location),
    )


def sample_opportunities(now: datetime) -> list[Opportunity]:
    """The sample roles, matching the portal mocks."""
    return [
        _opportunity(
            now,
            number=1,
            title="VP Technology Transformation",
            company="Company A",
            location="San Francisco Bay Area",
            work_model="Hybrid",
            compensation="$320K + bonus + equity",
            posted_hours=4,
            seen_hours=3,
            fit=94,
            confidence="HIGH",
            priority="IMMEDIATE",
            components=_components(0.96, 0.94, 0.95, 0.96, 0.93, 0.82),
            why_it_fits=(
                Point(
                    "Strong match: enterprise transformation leadership",
                    (
                        _quote("Lead enterprise-wide technology modernization"),
                        _evidence("Sample achievement: led a multi-year modernization program"),
                    ),
                ),
                Point(
                    "Strong match: large-scale portfolio governance",
                    (_quote("Own the multi-year transformation portfolio and its governance"),),
                ),
                Point(
                    "Good match: executive stakeholder management",
                    (_quote("Partner with the executive team"),),
                ),
            ),
            concerns=(
                Point(
                    "Gap: prefers financial-services experience",
                    (_quote("Financial-services experience strongly preferred"),),
                ),
                Point("The posting does not state: reporting line"),
            ),
            why_now=(
                Point("Posted today", (_field("posted_at"),)),
                Point("Preferred location: San Francisco Bay Area", (_field("location"),)),
                Point("Stated pay meets your preference", (_field("comp_max"),)),
            ),
            connections=(
                Connection("Person A", "Technology organization · Director", "STRONG"),
                Connection("Person B", "Executive leadership · SVP", "MEDIUM"),
                Connection("Person C", "Talent / recruiting · Recruiter", "UNKNOWN"),
            ),
        ),
        _opportunity(
            now,
            number=2,
            title="VP Technology Operations",
            company="Company B",
            location="San Jose, CA",
            work_model="Hybrid",
            compensation="$300K + bonus + equity",
            posted_hours=26,
            seen_hours=7,
            fit=92,
            confidence="HIGH",
            priority="HIGH",
            components=_components(0.94, 0.92, 0.93, 0.9, 0.9, None),
            why_it_fits=(
                Point(
                    "Strong match: technology operations at global scale",
                    (_quote("Lead a global organization of program and operations leaders"),),
                ),
            ),
            concerns=(Point("The posting does not state: reporting line"),),
            why_now=(
                Point("Posted 1 day ago", (_field("posted_at"),)),
                Point("Preferred location: San Jose, CA", (_field("location"),)),
            ),
            connections=(
                Connection("Person D", "Operations · VP", "STRONG"),
                Connection("Person E", "Engineering · Senior Director", "MEDIUM"),
                Connection("Person F", "Finance · Director", "UNKNOWN"),
                Connection("Person G", "Product · Partner", "UNKNOWN"),
            ),
        ),
        _opportunity(
            now,
            number=3,
            title="Head of AI Platform Programs",
            company="Company C",
            location="United States",
            work_model="Remote",
            compensation=None,
            posted_hours=50,
            seen_hours=48,
            fit=88,
            confidence="MEDIUM",
            priority="HIGH",
            components=_components(0.9, 0.78, 0.92, 0.88, 0.9, None),
            why_it_fits=(
                Point(
                    "Strong match: AI transformation and program portfolio leadership",
                    (_quote("Own the multi-year transformation portfolio"),),
                ),
            ),
            concerns=(Point("The posting does not state: compensation, team size"),),
            why_now=(Point("Posted 2 days ago", (_field("posted_at"),)),),
            connections=(),
            watched=True,
            discovery="MATERIALLY_CHANGED",
            change_note="Onsite to Remote",
        ),
        _opportunity(
            now,
            number=4,
            title="Senior Director, Enterprise Program Management",
            company="Company D",
            location="Sunnyvale, CA",
            work_model="Onsite",
            compensation="$280K + bonus",
            posted_hours=30,
            seen_hours=28,
            fit=86,
            confidence="HIGH",
            priority="MEDIUM",
            components=_components(0.9, 0.75, 0.9, 0.85, 0.8, None),
            concerns=(Point("Possible negative fit (onsite five days a week)"),),
            why_now=(Point("Posted 1 day ago", (_field("posted_at"),)),),
            connections=(
                Connection("Person H", "Program office · Director", "MEDIUM"),
                Connection("Person I", "Engineering · VP", "UNKNOWN"),
            ),
        ),
        _opportunity(
            now,
            number=5,
            title="VP Developer Productivity",
            company="Company E",
            location="United States",
            work_model="Remote",
            compensation="$290K + equity",
            posted_hours=60,
            seen_hours=55,
            fit=81,
            confidence="MEDIUM",
            priority="MEDIUM",
            components=_components(0.85, 0.9, 0.7, 0.85, 0.75, None),
            concerns=(Point("Possible negative fit (hands_on_coding)"),),
            why_now=(Point("Posted 2 days ago", (_field("posted_at"),)),),
            connections=(Connection("Person J", "Engineering · SVP", "UNKNOWN"),),
            watched=True,
        ),
        _opportunity(
            now,
            number=6,
            title="Head of Technology Strategy and Operations",
            company="Company F",
            location="Palo Alto, CA",
            work_model="Hybrid",
            compensation=None,
            posted_hours=None,
            seen_hours=70,
            fit=79,
            confidence="MEDIUM",
            priority="MEDIUM",
            components=_components(0.82, 0.8, 0.8, 0.78, 0.75, None),
            concerns=(Point("The posting does not state: compensation, reporting line"),),
            why_now=(Point("First seen 2 days ago", (_field("first_seen_at"),)),),
            discovery="MATERIALLY_CHANGED",
            change_note="Compensation range removed",
        ),
        _opportunity(
            now,
            number=7,
            title="VP Security Governance and Risk",
            company="Company G",
            location="Santa Clara, CA",
            work_model="Hybrid",
            compensation="$310K + bonus",
            posted_hours=80,
            seen_hours=75,
            fit=77,
            confidence="HIGH",
            priority="MEDIUM",
            components=_components(0.75, 0.9, 0.7, 0.85, 0.6, None),
            concerns=(Point("Gap: domain shift toward security"),),
            why_now=(Point("Posted 3 days ago", (_field("posted_at"),)),),
            discovery="PREVIOUSLY_SEEN",
        ),
        _opportunity(
            now,
            number=8,
            title="Senior Director, Cloud Transformation",
            company="Company H",
            location="United States",
            work_model="Remote",
            compensation="$250K + bonus",
            posted_hours=150,
            seen_hours=140,
            fit=74,
            confidence="MEDIUM",
            priority="LOW",
            components=_components(0.8, 0.6, 0.8, 0.7, 0.6, None),
            concerns=(Point("Stated pay is below your preferred level", (_field("comp_max"),)),),
            why_now=(Point("Posted 6 days ago", (_field("posted_at"),)),),
            discovery="PREVIOUSLY_SEEN",
        ),
        _opportunity(
            now,
            number=9,
            title="Chief of Staff to the CTO",
            company="Company I",
            location="New York, NY",
            work_model=None,
            compensation=None,
            posted_hours=None,
            seen_hours=20,
            fit=None,
            confidence="LOW",
            priority="UNRANKED",
            concerns=(Point("The posting does not state: work model, compensation"),),
        ),
    ]


ALERTS = "Job-alert emails"
PARTIAL_COVERAGE = "coverage may be incomplete"


def sample_companies(now: datetime) -> list[Company]:
    """Target and discovered companies, matching the Companies mock."""
    day = timedelta(days=1)

    def signal(text: str, source: str, days_ago: float) -> Signal:
        return Signal(text, source, now - days_ago * day)

    return [
        Company(
            "Company A",
            "Enterprise Software · AI Platforms",
            target=True,
            watching=True,
            monitoring="HIGH",
            relevance="NO_CURRENT_MATCH",
            job_source="Careers site feed",
            signals=(
                signal("Enterprise AI investment", "Company announcement", 6),
                signal("Technology modernization program", "Earnings call", 21),
                signal("New technology leadership", "Press release", 14),
            ),
            connections=3,
        ),
        Company(
            "Company B",
            "Technology · AI Infrastructure",
            target=True,
            watching=True,
            monitoring="HIGH",
            relevance="NO_CURRENT_MATCH",
            job_source=ALERTS,
            coverage_note=PARTIAL_COVERAGE,
            signals=(
                signal("AI expansion", "Company announcement", 4),
                signal("Platform modernization", "Engineering blog", 7),
            ),
            connections=7,
        ),
        Company(
            "Company C",
            "Semiconductors · Memory and Storage",
            target=True,
            watching=True,
            monitoring="NORMAL",
            relevance="NO_CURRENT_MATCH",
            job_source=ALERTS,
            coverage_note=PARTIAL_COVERAGE,
            signals=(signal("Significant AI investment", "Investor presentation", 21),),
            connections=0,
        ),
        Company(
            "Company D",
            "Cloud and Productivity Software",
            target=True,
            watching=False,
            monitoring="NORMAL",
            relevance="NO_CURRENT_MATCH",
            job_source=ALERTS,
            coverage_note=PARTIAL_COVERAGE,
            signals=(signal("Recent acquisition", "Company announcement", 30),),
            connections=12,
        ),
        Company(
            "Company J",
            "Consumer Internet · AI Research",
            target=True,
            watching=True,
            monitoring="HIGH",
            relevance="NO_CURRENT_MATCH",
            job_source=ALERTS,
            coverage_note=PARTIAL_COVERAGE,
            signals=(
                signal("Enterprise transformation underway", "News report", 30),
                signal("New Bay Area office opening", "Company announcement", 14),
            ),
            connections=5,
        ),
        Company(
            "Company K",
            "AI Research Lab",
            target=True,
            watching=False,
            monitoring="NORMAL",
            relevance="STRATEGICALLY_RELEVANT",
            job_source=ALERTS,
            coverage_note=PARTIAL_COVERAGE,
            signals=(signal("Enterprise product launch", "Company announcement", 7),),
            connections=2,
        ),
        Company(
            "Company L",
            "Social Media · Advertising Platforms",
            target=True,
            watching=False,
            monitoring="LOW",
            relevance="NO_CURRENT_MATCH",
            job_source=ALERTS,
            coverage_note="no alert received in 9 days",
        ),
        *(
            Company(
                f"Company {letter}",
                None,
                target=False,
                watching=False,
                monitoring="LOW",
                relevance="NO_CURRENT_MATCH",
                job_source="Careers site feed",
            )
            for letter in "EFG"
        ),
        Company(
            "Company H",
            "Financial Services · Payments",
            target=False,
            watching=False,
            monitoring="LOW",
            relevance="LOW_RELEVANCE",
            job_source="Careers site feed",
            low_reason="Role family outside your targets",
        ),
        Company(
            "Company I",
            None,
            target=False,
            watching=False,
            monitoring="LOW",
            relevance="NO_CURRENT_MATCH",
            job_source="Careers site feed",
        ),
    ]


SAMPLE_SOURCES = (
    *(f"Company {letter} careers site" for letter in "ABCDEFGHIJKL"),
    "Job-alert inbox",
    "Job discovery source B",
)
FAILING_SOURCE = "Job discovery source B"


def _sources(failed: str | None = None) -> tuple[SourceStatus, ...]:
    return tuple(
        SourceStatus(
            name,
            "FAILED" if name == failed else "OK",
            0 if name == failed else 4 + 3 * (i % 5),
            0 if name == failed else i % 3,
        )
        for i, name in enumerate(SAMPLE_SOURCES)
    )


def sample_runs(now: datetime) -> list[SearchRun]:
    """Recent runs, newest first: two clean runs, a partial one, then clean again."""
    hour = timedelta(hours=1)
    # (hours ago, status, failed source, new, changed, expired)
    history = (
        (1, "SUCCESS", None, 7, 3, 2),
        (6, "SUCCESS", None, 4, 1, 0),
        (20, "PARTIAL", FAILING_SOURCE, 5, 2, 1),
        (25, "SUCCESS", None, 3, 0, 2),
        (30, "SUCCESS", None, 6, 1, 0),
    )
    total = len(SAMPLE_SOURCES)
    return [
        SearchRun(
            started_at=now - ago * hour,
            status=status,
            sources_searched=total - (failed is not None),
            sources_total=total,
            new=new,
            changed=changed,
            expired=expired,
            next_run_at=now + 4 * hour if ago == 1 else None,
            sources=_sources(failed),
        )
        for ago, status, failed, new, changed, expired in history
    ]


class SampleData:
    """A :class:`pejip.portal.data.PortalData` serving the sample roles."""

    is_sample = True

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def latest_run(self) -> SearchRun | None:
        return self.recent_runs()[0]

    def recent_runs(self) -> list[SearchRun]:
        return sample_runs(self._clock())

    def opportunities(self) -> list[Opportunity]:
        return sample_opportunities(self._clock())

    def companies(self) -> list[Company]:
        return sample_companies(self._clock())
