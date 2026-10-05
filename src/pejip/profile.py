"""Master Career Profile (spec 8.2 to 8.11).

The profile is personal data. It lives in a local YAML file outside the repository
(see ``PEJIP_PROFILE``), or in AWS in a SecureString SSM parameter encrypted with
``alias/pejip`` (see ``PEJIP_PROFILE_PARAMETER``). Only the evidence items and
career direction are sent to the AI provider (``ai_view``), never contact details.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, cast

import yaml
from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field, model_validator

Seniority = Literal[
    "C_LEVEL",
    "SVP",
    "VP",
    "HEAD_OF",
    "SENIOR_DIRECTOR",
    "DIRECTOR",
    "BELOW_DIRECTOR",
    "UNKNOWN",
]
EvidenceKind = Literal["EXPERIENCE", "ACHIEVEMENT", "CAPABILITY", "SCOPE"]


class DuplicateEvidenceIdError(ValueError):
    """Two evidence items share an id, so citations would be ambiguous."""

    def __init__(self) -> None:
        super().__init__("evidence ids must be unique")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(_Strict):
    id: str = Field(pattern=r"^E\d+$")
    kind: EvidenceKind
    text: str = Field(min_length=1)


class CompensationPreference(_Strict):
    currency: str = "USD"
    minimum: float | None = None
    preferred: float | None = None
    minimum_is_hard_filter: bool = False


class CareerProfile(_Strict):
    name: str
    email: str | None = None
    headline: str
    target_seniority: list[Seniority] = Field(min_length=1)
    career_direction: str
    evidence: list[Evidence] = Field(min_length=1)
    compensation: CompensationPreference = CompensationPreference()

    @model_validator(mode="after")
    def _unique_evidence_ids(self) -> CareerProfile:
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise DuplicateEvidenceIdError
        return self

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.evidence}

    def ai_view(self) -> str:
        """The minimum profile fields the matching task needs, as YAML."""
        view = {
            "headline": self.headline,
            "target_seniority": list(self.target_seniority),
            "career_direction": self.career_direction,
            "evidence": [e.model_dump() for e in self.evidence],
        }
        return yaml.safe_dump(view, sort_keys=False, allow_unicode=True)


def load_profile(path: Path) -> CareerProfile:
    return parse_profile(path.read_text(encoding="utf-8"))


def parse_profile(text: str) -> CareerProfile:
    return CareerProfile.model_validate(yaml.safe_load(text))


class SsmClient(Protocol):
    """The one SSM call the profile needs (a boto3 SSM client satisfies it)."""

    def get_parameter(self, **kwargs: Any) -> dict[str, Any]: ...


def make_ssm_client(region: str | None) -> SsmClient:
    """A boto3 SSM client using the task role's credentials (no keys in config)."""
    import boto3  # noqa: PLC0415  (only runs where the profile is a parameter)

    return cast(SsmClient, boto3.client("ssm", region_name=region))


def read_parameter(client: SsmClient, name: str) -> str | None:
    """A decrypted SSM parameter's value, or None when it is not stored yet.

    Any other failure (no permission, throttling) raises.
    """
    try:
        response = client.get_parameter(Name=name, WithDecryption=True)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return None
        raise
    value: str = response["Parameter"]["Value"]
    return value


def load_profile_parameter(client: SsmClient, name: str) -> CareerProfile | None:
    """The profile stored in SSM, or None when Babu has not stored one yet.

    Any other failure (no permission, a malformed profile) raises, so a broken
    setup fails the run loudly instead of quietly ranking nothing.
    """
    value = read_parameter(client, name)
    return None if value is None else parse_profile(value)
