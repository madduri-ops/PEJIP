"""Search, scoring and AI configuration loaded from YAML (spec 3.8, 4.8, 9.7)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

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


class Price(_Strict):
    input: float = Field(ge=0)
    output: float = Field(ge=0)


class AIConfig(_Strict):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]
    max_tokens: int = Field(gt=0)
    monthly_cap_usd: float = Field(gt=0)
    alert_thresholds_percent: list[int]
    max_jobs_per_run: int = Field(ge=0)
    pricing: dict[str, Price]


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


class SearchConfig(_Strict):
    sources: list[SourceConfig]
    fetch: FetchConfig
    taxonomy: TaxonomyConfig
    geography: GeographyConfig
    ai: AIConfig
    scoring: ScoringConfig
    retention_days: int = Field(gt=0)


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

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = dict(os.environ) if env is None else env
        return cls(
            config_path=Path(e.get("PEJIP_CONFIG", "config/search.yaml")),
            profile_path=Path(e.get("PEJIP_PROFILE", "profile.yaml")),
            database_url=e.get("PEJIP_DATABASE_URL", "sqlite:///pejip.db"),
            output_dir=Path(e.get("PEJIP_OUTPUT_DIR", "output")),
        )
