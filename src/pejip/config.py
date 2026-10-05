"""Search, scoring and AI configuration loaded from YAML (spec 3.8, 4.8, 9.7)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from pejip.retention import RETENTION_DAYS

Adapter = Literal["greenhouse", "lever"]
Preference = Literal["PREFERRED", "ACCEPTABLE", "UNDESIRABLE"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceConfig(_Strict):
    adapter: Adapter
    company: str
    board: str
    api_base: str | None = None


class FetchConfig(_Strict):
    user_agent: str
    min_interval_seconds: float = Field(ge=0)
    max_retries: int = Field(ge=0)
    backoff_base_seconds: float = Field(ge=0)
    timeout_seconds: float = Field(gt=0)


class TaxonomyConfig(_Strict):
    seniority_patterns: list[str]
    excluded_title_patterns: list[str]
    role_terms: list[str]


class GeoScope(_Strict):
    preference: Preference
    places: list[str]


class GeographyConfig(_Strict):
    hard_filter: bool
    scopes: dict[str, GeoScope]


class AIConfig(_Strict):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]
    max_tokens: int = Field(gt=0)
    max_jobs_per_run: int = Field(ge=0)


class ScoringConfig(_Strict):
    version: str
    fit_weights: dict[str, float]
    negative_signal_penalty: float = Field(ge=0)
    core_gap_penalty: float = Field(ge=0)
    confidence_thresholds: dict[str, float]
    priority_weights: dict[str, float]
    priority_thresholds: dict[str, float]
    priority_min_fit: dict[str, float]
    immediate_max_age_days: int = Field(ge=0)
    strong_match_fit: float
    # Priority points a role gains from the network (design doc 0011). Never negative,
    # so having no connections never lowers a role.
    network_priority_boost: dict[
        Literal["MATURED", "CONNECTED"], Annotated[float, Field(ge=0, le=25)]
    ] = Field(default_factory=dict)


class AlertCompany(_Strict):
    """A company whose job-alert emails PEJIP reads (design doc 0010).

    ``link_patterns`` are ``host/path-prefix`` strings; a link in an alert becomes a
    role only when it points at one of them (subdomains of the host match too).
    """

    company: str
    link_patterns: list[str] = Field(min_length=1)


class InboxConfig(_Strict):
    companies: list[AlertCompany]


class NetworkConfig(_Strict):
    """Other names a tracked company goes by in LinkedIn employer fields (spec 13.3)."""

    company_aliases: dict[str, list[str]] = Field(default_factory=dict)


class SearchConfig(_Strict):
    sources: list[SourceConfig]
    fetch: FetchConfig
    taxonomy: TaxonomyConfig
    geography: GeographyConfig
    ai: AIConfig
    scoring: ScoringConfig
    retention_days: int = Field(ge=1, le=RETENTION_DAYS)
    inbox: InboxConfig | None = None
    network: NetworkConfig | None = None


def load_config(path: Path) -> SearchConfig:
    """Load and validate the search configuration file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SearchConfig.model_validate(data)


@dataclass(frozen=True)
class Settings:
    """Runtime locations, taken from the environment."""

    config_path: Path
    profile_path: Path
    database_url: str
    output_dir: Path
    ai_ledger_path: Path
    inbox_bucket: str | None = None
    aws_region: str | None = None
    connections_path: Path | None = None
    network_decisions_path: Path | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = dict(os.environ) if env is None else env
        return cls(
            config_path=Path(e.get("PEJIP_CONFIG", "config/search.yaml")),
            profile_path=Path(e.get("PEJIP_PROFILE", "profile.yaml")),
            database_url=e.get("PEJIP_DATABASE_URL", "sqlite:///pejip.db"),
            output_dir=Path(e.get("PEJIP_OUTPUT_DIR", "output")),
            ai_ledger_path=Path(e.get("PEJIP_AI_LEDGER", "pejip-ai-spend.db")),
            # The job-alert inbox is read only where a bucket is named (in AWS).
            inbox_bucket=e.get("PEJIP_INBOX_BUCKET") or None,
            aws_region=e.get("AWS_REGION") or None,
            # A LinkedIn Connections export and the candidate's network decisions, both
            # kept outside the repository (design doc 0011).
            connections_path=_optional_path(e.get("PEJIP_CONNECTIONS")),
            network_decisions_path=_optional_path(e.get("PEJIP_NETWORK_DECISIONS")),
        )


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None
