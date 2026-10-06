"""Search, scoring and AI configuration loaded from YAML (spec 3.8, 4.8, 9.7)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pejip import accounts
from pejip.retention import RETENTION_DAYS

# Where SES stores job-alert mail in the inbox bucket (design doc 0010); since
# design doc 0016 each account reads its own folder under it.
INBOX_PREFIX = "inbound/"

Adapter = Literal["greenhouse", "lever", "ashby"]
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
    account: str = accounts.DEFAULT_ACCOUNT_ID
    network_prefix: str = "network/"
    inbox_prefix: str = INBOX_PREFIX
    legacy_database_url: str | None = None
    legacy_output_dir: Path | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, account: str | None = None) -> Settings:
        """Read the settings for ``account`` (``PEJIP_ACCOUNT``, else Babu's).

        Settings naming a personal place carry an ``{account}`` placeholder
        (design doc 0016), filled in here. Babu's account may also use a place
        without one (local runs, and the settings from before accounts); any other
        account must not, so it can never share Babu's database, inbox, files or
        digest. Unset, such a place defaults to one under ``accounts/<id>/``.
        The pre-account locations (``PEJIP_LEGACY_*``) are kept only for Babu's
        account, the one account that may adopt them.
        """
        e = dict(os.environ) if env is None else env
        who = accounts.check_account_id(
            account or e.get("PEJIP_ACCOUNT") or accounts.DEFAULT_ACCOUNT_ID
        )
        owner = who == accounts.DEFAULT_ACCOUNT_ID

        def place(name: str, default: str | None = None, own: str | None = None) -> str | None:
            value = e.get(name) or None
            if value is None:
                value = default if owner else own
            elif not owner and accounts.PLACEHOLDER not in value:
                msg = f"{name} must contain {accounts.PLACEHOLDER} for accounts other than Babu's"
                raise ValueError(msg)
            return accounts.fill(value, who) if value else None

        def path(name: str, default: str | None = None, own: str | None = None) -> Path | None:
            return _optional_path(place(name, default, own))

        return cls(
            account=who,
            config_path=Path(e.get("PEJIP_CONFIG", "config/search.yaml")),
            profile_path=Path(
                place("PEJIP_PROFILE", "profile.yaml", "accounts/{account}/profile.yaml") or ""
            ),
            database_url=place(
                "PEJIP_DATABASE_URL", "sqlite:///pejip.db", "sqlite:///accounts/{account}/pejip.db"
            )
            or "",
            output_dir=Path(place("PEJIP_OUTPUT_DIR", "output", "accounts/{account}/output") or ""),
            legacy_database_url=(e.get("PEJIP_LEGACY_DATABASE_URL") or None) if owner else None,
            legacy_output_dir=_optional_path(e.get("PEJIP_LEGACY_OUTPUT_DIR")) if owner else None,
            # One spend ledger for the whole deployment: the $100 cap is shared.
            ai_ledger_path=Path(e.get("PEJIP_AI_LEDGER", "pejip-ai-spend.db")),
            # The job-alert inbox is read only where a bucket is named (in AWS), from
            # the account's own prefix in it.
            inbox_bucket=e.get("PEJIP_INBOX_BUCKET") or None,
            inbox_prefix=place("PEJIP_INBOX_PREFIX", INBOX_PREFIX, "inbound/{account}/") or "",
            aws_region=e.get("AWS_REGION") or None,
            # A LinkedIn Connections export and the candidate's network decisions, both
            # kept outside the repository (design doc 0014).
            connections_path=path("PEJIP_CONNECTIONS"),
            network_decisions_path=path("PEJIP_NETWORK_DECISIONS"),
            # On AWS they are uploaded to network/<account>/ in this bucket instead.
            network_bucket=e.get("PEJIP_NETWORK_BUCKET") or None,
            network_prefix=place("PEJIP_NETWORK_PREFIX", "network/", "network/{account}/") or "",
            # Target companies, kept out of the public repository (ADR-0009): a local
            # file, or on AWS an encrypted SSM parameter.
            companies_path=path("PEJIP_COMPANIES"),
            companies_parameter=place("PEJIP_COMPANIES_PARAMETER"),
            # In AWS the profile is an encrypted SSM parameter, not a file.
            profile_parameter=place("PEJIP_PROFILE_PARAMETER"),
            # Where `pejip run` emails the digest (an SNS topic per account), when set.
            digest_topic_arn=_digest_topic(e, who),
            # Off until the workload can sign in to Claude; roles are then unranked.
            ai_enabled=_flag(e, "PEJIP_AI_ENABLED", default=True),
            # Who does the model step: the API, or the Claude Code routine (design 0015).
            ranker=_choice(e, "PEJIP_RANKER", RANKERS),
            # The SSM parameter holding the SHA-256 of the routine's key.
            ranking_key_parameter=place("PEJIP_RANKING_KEY_PARAMETER"),
        )


def _digest_topic(env: Mapping[str, str], account: str) -> str | None:
    """The account's digest topic: its entry in ``PEJIP_DIGEST_TOPICS`` (``id=arn`` pairs).

    ``PEJIP_DIGEST_TOPIC_ARN``, the single topic from before accounts, is Babu's
    alone: another account without an entry gets no email rather than Babu's.
    """
    topics = accounts.parse_pairs(env.get("PEJIP_DIGEST_TOPICS", ""), "PEJIP_DIGEST_TOPICS")
    if topics:
        return topics.get(account)
    if account == accounts.DEFAULT_ACCOUNT_ID:
        return env.get("PEJIP_DIGEST_TOPIC_ARN") or None
    return None


def account_ids(env: Mapping[str, str]) -> list[str]:
    """The accounts a scheduled command runs for.

    ``PEJIP_ACCOUNT`` names one; otherwise every id in ``PEJIP_ACCOUNTS``
    (comma-separated), else Babu's account alone.
    """
    one = env.get("PEJIP_ACCOUNT", "").strip()
    if one:
        return [accounts.check_account_id(one)]
    listed = [a.strip() for a in env.get("PEJIP_ACCOUNTS", "").split(",") if a.strip()]
    return [accounts.check_account_id(a) for a in dict.fromkeys(listed)] or [
        accounts.DEFAULT_ACCOUNT_ID
    ]


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None
