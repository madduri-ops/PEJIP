"""Load network inputs from local files for a run (design doc 0014).

Until the portal stores imports, a run reads the candidate's LinkedIn export from
``PEJIP_CONNECTIONS`` and their decisions from ``PEJIP_NETWORK_DECISIONS``. On AWS
both are uploaded instead to ``network/`` in the encrypted bucket named by
``PEJIP_NETWORK_BUCKET``, where they expire after 90 days. Neither is in the
repository, and neither holds anything PEJIP invents.

The decisions file is YAML::

    companies:              # employer name as imported -> tracked company, or null
      Company X Cloud: Company X
      Northstar: null       # a separate company: leave unmatched
    titles:                 # an unclear title, judged against a role level
      - {company: Company A, position: "Principal, Technology Strategy",
         role_level: VP, matured: true}
"""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from pejip.config import SearchConfig
from pejip.network.companies import CompanyDirectory
from pejip.network.linkedin import MAX_EXPORT_BYTES, ExportError, ImportPreview, parse_export
from pejip.network.matching import NetworkIndex, TitleDecision
from pejip.profile import Seniority
from pejip.sources.email_alerts import S3Client

NETWORK_PREFIX = "network/"
CONNECTIONS_KEY = f"{NETWORK_PREFIX}Connections.csv"
DECISIONS_KEY = f"{NETWORK_PREFIX}network-decisions.yaml"


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
    return _parse_decisions(path.read_bytes())


def _parse_decisions(data: bytes) -> NetworkDecisions:
    return NetworkDecisions.model_validate(yaml.safe_load(data) or {})


def tracked_companies(config: SearchConfig) -> list[str]:
    """Every company PEJIP searches: board sources and job-alert companies."""
    names = [s.company for s in config.sources]
    if config.inbox is not None:
        # A job board such as LinkedIn lists other employers' roles; it is not one.
        names += [c.company for c in config.inbox.companies if not c.job_board]
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
    return _index(config, read_export(connections_path), load_decisions(decisions_path))


def load_index_s3(client: S3Client, bucket: str, config: SearchConfig) -> NetworkIndex | None:
    """The index from the uploaded export, or None when none has been uploaded.

    The prefix is listed first because without a broader s3:ListBucket grant, a
    missing object reads as access denied rather than as absent.
    """
    listed = client.list_objects_v2(Bucket=bucket, Prefix=NETWORK_PREFIX)
    keys = {item["Key"] for item in listed.get("Contents", [])}
    if CONNECTIONS_KEY not in keys:
        return None
    export = client.get_object(Bucket=bucket, Key=CONNECTIONS_KEY)
    with closing(export["Body"]) as body:
        if export["ContentLength"] > MAX_EXPORT_BYTES:
            raise ExportError("too_large")
        preview = parse_export(body.read(), export["LastModified"])
    decisions = NetworkDecisions()
    if DECISIONS_KEY in keys:
        uploaded = client.get_object(Bucket=bucket, Key=DECISIONS_KEY)
        with closing(uploaded["Body"]) as body:
            decisions = _parse_decisions(body.read())
    return _index(config, preview, decisions)[1]


def _index(
    config: SearchConfig, preview: ImportPreview, decisions: NetworkDecisions
) -> tuple[ImportPreview, NetworkIndex]:
    titles = [TitleDecision(**t.model_dump()) for t in decisions.titles]
    index = NetworkIndex.build(preview.connections, directory_for(config, decisions), titles)
    return preview, index
