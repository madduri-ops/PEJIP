"""Load network inputs from local files for a run (design doc 0014).

Until the portal stores imports, a run reads the candidate's LinkedIn export from
``PEJIP_CONNECTIONS`` and their decisions from ``PEJIP_NETWORK_DECISIONS``. Both
files live outside the repository; neither holds anything PEJIP invents.

The decisions file is YAML::

    companies:              # employer name as imported -> tracked company, or null
      Company X Cloud: Company X
      Northstar: null       # a separate company: leave unmatched
    titles:                 # an unclear title, judged against a role level
      - {company: Company A, position: "Principal, Technology Strategy",
         role_level: VP, matured: true}
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from pejip.config import SearchConfig
from pejip.network.companies import CompanyDirectory
from pejip.network.linkedin import ImportPreview, parse_export
from pejip.network.matching import NetworkIndex, TitleDecision
from pejip.profile import Seniority


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TitleDecisionEntry(_Strict):
    company: str
    position: str
    role_level: Seniority
    matured: bool


class NetworkDecisions(_Strict):
    companies: dict[str, str | None] = Field(default_factory=dict)
    titles: list[TitleDecisionEntry] = Field(default_factory=list)


def load_decisions(path: Path | None) -> NetworkDecisions:
    """The candidate's decisions; a named file that is missing is an error, not empty."""
    if path is None:
        return NetworkDecisions()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return NetworkDecisions.model_validate(data)


def tracked_companies(config: SearchConfig) -> list[str]:
    """Every company PEJIP searches: board sources and job-alert companies."""
    names = [s.company for s in config.sources]
    if config.inbox is not None:
        names += [c.company for c in config.inbox.companies]
    return list(dict.fromkeys(names))


def directory_for(config: SearchConfig, decisions: NetworkDecisions) -> CompanyDirectory:
    aliases = config.network.company_aliases if config.network is not None else {}
    return CompanyDirectory.build(tracked_companies(config), aliases, decisions.companies)


def read_export(path: Path) -> ImportPreview:
    """Parse an export file; its modified time stands for the import date."""
    imported_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return parse_export(path.read_bytes(), imported_at)


def load_index(
    config: SearchConfig, connections_path: Path, decisions_path: Path | None
) -> tuple[ImportPreview, NetworkIndex]:
    decisions = load_decisions(decisions_path)
    preview = read_export(connections_path)
    titles = [TitleDecision(**t.model_dump()) for t in decisions.titles]
    index = NetworkIndex.build(preview.connections, directory_for(config, decisions), titles)
    return preview, index
