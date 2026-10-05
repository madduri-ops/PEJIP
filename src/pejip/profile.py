"""Master Career Profile (spec 8.2 to 8.11).

The profile is personal data. It lives in a local YAML file outside the repository
(see ``PEJIP_PROFILE``) and only the evidence items and career direction are sent to
the AI provider (``ai_view``), never contact details.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
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
            raise ValueError("evidence ids must be unique")
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
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CareerProfile.model_validate(data)
