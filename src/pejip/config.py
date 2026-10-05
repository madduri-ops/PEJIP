"""Search, scoring and AI configuration loaded from YAML (spec 3.8, 4.8, 9.7)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    # Priority points a role gains from the network (design doc 0014). Never negative,
    # so having no connections never lowers a role.
    network_priority_boost: dict[
        Literal["MATURED", "CONNECTED"], Annotated[float, Field(ge=0, le=25)]
    ] = Field(default_factory=dict)
    # Below this Fit the network adds no Priority: a weak match stays weak (spec 8.26).
    network_min_fit: float = Field(default=0, ge=0, le=100)


class InvalidPatternError(ValueError):
    def __init__(self, cause: re.error) -> None:
        super().__init__(f"job_id_pattern is not a valid regular expression: {cause}")


class AlertCompany(_Strict):
    """A company whose job-alert emails PEJIP reads (design doc 0010).

    ``link_patterns`` are ``host/path-prefix`` strings; a link in an alert becomes a
    role only when it points at one of them (subdomains of the host match too).

    A ``job_board`` (such as LinkedIn) lists many employers' roles: the employer
    and location are read from the text after each link, and ``company`` names
    the board. ``job_id_pattern`` is a regular expression for the part of a link
    that identifies the role, so the same role keeps one id across alerts.
    """

    company: str
    link_patterns: list[str] = Field(min_length=1)
    job_board: bool = False
    job_id_pattern: str | None = None

    @field_validator("job_id_pattern")
    @classmethod
    def _compiles(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as exc:
                raise InvalidPatternError(exc) from exc
        return value


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


class PrivateCompanies(_Strict):
    """Babu's own target companies, kept out of the public repository (ADR-0009).

    They are added to the boards, alert companies and aliases in the committed
    configuration, which holds only companies searched for testing.
    """

    sources: list[SourceConfig] = Field(default_factory=list)
    inbox_companies: list[AlertCompany] = Field(default_factory=list)
    company_aliases: dict[str, list[str]] = Field(default_factory=dict)


def parse_private_companies(text: str) -> PrivateCompanies:
    return PrivateCompanies.model_validate(yaml.safe_load(text) or {})


def with_private_companies(config: SearchConfig, private: PrivateCompanies) -> SearchConfig:
    """The configuration with Babu's private companies added to the committed ones."""
    alerts = [*(config.inbox.companies if config.inbox else []), *private.inbox_companies]
    aliases = config.network.company_aliases if config.network else {}
    return SearchConfig.model_validate(
        {
            **config.model_dump(),
            "sources": [*config.sources, *private.sources],
            "inbox": InboxConfig(companies=alerts) if alerts else None,
            "network": NetworkConfig(company_aliases={**aliases, **private.company_aliases}),
        }
    )


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _flag(env: dict[str, str], name: str, *, default: bool) -> bool:
    """A boolean setting; an unrecognised value fails instead of guessing."""
    value = env.get(name, "").strip().lower()
    if not value:
        return default
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    msg = f"{name} must be one of {sorted(_TRUE | _FALSE)}, got {value!r}"
    raise ValueError(msg)


RANKERS = ("api", "routine")


def _choice(env: dict[str, str], name: str, choices: tuple[str, ...]) -> str:
    """One of ``choices``, the first when unset; anything else fails."""
    value = env.get(name, "").strip().lower() or choices[0]
    if value not in choices:
        msg = f"{name} must be one of {list(choices)}, got {value!r}"
        raise ValueError(msg)
    return value


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
    network_bucket: str | None = None
    companies_path: Path | None = None
    companies_parameter: str | None = None
    profile_parameter: str | None = None
    digest_topic_arn: str | None = None
    ai_enabled: bool = True
    ranker: str = "api"
    ranking_key_parameter: str | None = None

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
            # kept outside the repository (design doc 0014).
            connections_path=_optional_path(e.get("PEJIP_CONNECTIONS")),
            network_decisions_path=_optional_path(e.get("PEJIP_NETWORK_DECISIONS")),
            # On AWS they are uploaded to network/ in this bucket instead.
            network_bucket=e.get("PEJIP_NETWORK_BUCKET") or None,
            # Babu's target companies, kept out of the public repository (ADR-0009):
            # a local file, or on AWS an encrypted SSM parameter.
            companies_path=_optional_path(e.get("PEJIP_COMPANIES")),
            companies_parameter=e.get("PEJIP_COMPANIES_PARAMETER") or None,
            # In AWS the profile is an encrypted SSM parameter, not a file.
            profile_parameter=e.get("PEJIP_PROFILE_PARAMETER") or None,
            # Where `pejip run` emails the digest (an SNS topic), when set.
            digest_topic_arn=e.get("PEJIP_DIGEST_TOPIC_ARN") or None,
            # Off until the workload can sign in to Claude; roles are then unranked.
            ai_enabled=_flag(e, "PEJIP_AI_ENABLED", default=True),
            # Who does the model step: the API, or the Claude Code routine (design 0015).
            ranker=_choice(e, "PEJIP_RANKER", RANKERS),
            # The SSM parameter holding the SHA-256 of the routine's key.
            ranking_key_parameter=e.get("PEJIP_RANKING_KEY_PARAMETER") or None,
        )


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None
