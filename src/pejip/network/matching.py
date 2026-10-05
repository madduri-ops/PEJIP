"""Matured connections for a role (spec 8.22 to 8.26, design doc 0014).

A **matured connection** is a first-degree connection who, as of the last import,
works at the hiring company in a position comparable to the role's level or more
senior. Each connection at the company gets one status for a role:

- ``MATURED``: the title's level is at or above the role's level.
- ``NOT_MATURED``: the title's level is below it.
- ``YOUR_CALL``: the title has no clear level, or the role's own level is unknown
  (from neither the analysis nor its title). The candidate decides; PEJIP does not
  guess, and the connection does not count as matured until they say so.

Decisions are keyed by company, title and role level, never by person, so one answer
covers everyone with that title and is asked again when a re-import changes the title.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from pejip.network.companies import RESOLVED, CompanyDirectory, Resolution
from pejip.network.linkedin import Connection
from pejip.network.seniority import UNCLEAR, is_comparable_or_senior, normalize_title, title_level
from pejip.scoring import SENIORITY_RANK, NetworkFacts

MATURED = "MATURED"
NOT_MATURED = "NOT_MATURED"
YOUR_CALL = "YOUR_CALL"


@dataclass(frozen=True)
class TitleDecision:
    """The candidate's answer for one unclear title at one company for one role level."""

    company: str
    position: str
    role_level: str
    matured: bool


def decision_key(company: str, position: str, role_level: str) -> tuple[str, str, str]:
    return (company, normalize_title(position), role_level)


@dataclass(frozen=True)
class ConnectionMatch:
    connection: Connection
    level: str
    status: str
    decided: bool = False


@dataclass(frozen=True)
class NetworkSignal:
    """Who the candidate knows at one hiring company, judged against one role."""

    company: str | None
    role_level: str
    imported_at: datetime | None
    matches: tuple[ConnectionMatch, ...] = ()

    def by_status(self, status: str) -> list[ConnectionMatch]:
        return [m for m in self.matches if m.status == status]

    def facts(self) -> NetworkFacts:
        return NetworkFacts(
            first_degree=len(self.matches),
            matured=len(self.by_status(MATURED)),
            your_call=len(self.by_status(YOUR_CALL)),
        )


@dataclass
class NetworkIndex:
    """Connections from one import, grouped by the tracked company they resolved to.

    Connections whose employer is ambiguous or unmatched are kept out of every
    company's group, so nobody is linked to the wrong company (spec 8.21).
    """

    directory: CompanyDirectory
    imported_at: datetime | None
    by_company: dict[str, list[Connection]] = field(default_factory=dict)
    unresolved: dict[str, Resolution] = field(default_factory=dict)
    held_back: Counter[str] = field(default_factory=Counter)
    decisions: Mapping[tuple[str, str, str], bool] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        connections: Iterable[Connection],
        directory: CompanyDirectory,
        decisions: Iterable[TitleDecision] = (),
    ) -> NetworkIndex:
        answers: dict[tuple[str, str, str], bool] = {}
        for d in decisions:
            # The file may spell the company another way ("scale ai", an alias).
            resolved = directory.resolve(d.company)
            company = resolved.company if resolved.status == RESOLVED else None
            answers[decision_key(company or d.company, d.position, d.role_level)] = d.matured
        index = cls(directory, None, decisions=answers)
        for conn in connections:
            if index.imported_at is None or conn.imported_at > index.imported_at:
                index.imported_at = conn.imported_at
            if not conn.company_raw:
                continue
            resolution = directory.resolve(conn.company_raw)
            if resolution.status == RESOLVED and resolution.company is not None:
                index.by_company.setdefault(resolution.company, []).append(conn)
            elif resolution.candidates:
                # Ambiguous: held back until the candidate says which company it is.
                index.unresolved[conn.company_raw] = resolution
                index.held_back[conn.company_raw] += 1
        return index

    def signal(self, job_company: str, role_level: str, role_title: str = "") -> NetworkSignal:
        """Judge every connection at the job's company against the role's level.

        When the analysis left the role's level unknown, the role title is read the
        same way as a connection's; if that is unclear too, every connection there
        is the candidate's call.
        """
        if role_level not in SENIORITY_RANK:
            role_level = title_level(role_title)
        resolution = self.directory.resolve(job_company)
        company = resolution.company if resolution.status == RESOLVED else None
        matches: list[ConnectionMatch] = []
        for conn in self.by_company.get(company or "", []):
            level = title_level(conn.position_raw)
            key = decision_key(company or "", conn.position_raw, role_level)
            if role_level == UNCLEAR:
                matches.append(ConnectionMatch(conn, level, YOUR_CALL))
            elif level == UNCLEAR and key in self.decisions:
                status = MATURED if self.decisions[key] else NOT_MATURED
                matches.append(ConnectionMatch(conn, level, status, decided=True))
            elif level == UNCLEAR:
                matches.append(ConnectionMatch(conn, level, YOUR_CALL))
            elif is_comparable_or_senior(level, role_level):
                matches.append(ConnectionMatch(conn, level, MATURED))
            else:
                matches.append(ConnectionMatch(conn, level, NOT_MATURED))
        order = {MATURED: 0, YOUR_CALL: 1, NOT_MATURED: 2}
        matches.sort(key=lambda m: (order[m.status], m.connection.name))
        return NetworkSignal(company, role_level, self.imported_at, tuple(matches))
