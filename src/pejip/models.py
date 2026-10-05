"""Domain records shared across the pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Compensation:
    minimum: float | None
    maximum: float | None
    currency: str | None


@dataclass(frozen=True)
class Posting:
    """A job posting as one source reported it (a source observation, spec 13.18)."""

    source: str
    source_job_id: str
    company: str
    title: str
    location: str
    description: str
    url: str
    posted_at: datetime | None = None
    compensation: Compensation | None = None
    work_model_hint: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable identity of the posting across runs (spec 13.42)."""
        return hashlib.sha256(f"{self.source}|{self.source_job_id}".encode()).hexdigest()

    @property
    def content_hash(self) -> str:
        """Changes when the substance of the posting changes (spec 13.44)."""
        body = "\n".join([self.title, self.location, self.description])
        return hashlib.sha256(body.encode()).hexdigest()
