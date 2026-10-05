"""Lever Postings API adapter (public GET endpoints, docs/sources.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pejip.config import SourceConfig
from pejip.models import Compensation, Posting
from pejip.sources.http import FetchError, PoliteClient
from pejip.sources.text import html_to_text

DEFAULT_API_BASE = "https://api.lever.co"
_WORK_MODELS = {"remote": "REMOTE", "hybrid": "HYBRID", "on-site": "ONSITE", "onsite": "ONSITE"}


def fetch_lever(client: PoliteClient, source: SourceConfig) -> list[Posting]:
    base = source.api_base or DEFAULT_API_BASE
    url = f"{base}/v0/postings/{source.board}"
    payload = client.get_json(url, params={"mode": "json"})
    if not isinstance(payload, list):
        raise FetchError(f"unexpected Lever payload for site {source.board}")
    return [_to_posting(source, job) for job in payload]


def _to_posting(source: SourceConfig, job: dict[str, Any]) -> Posting:
    categories = job.get("categories") or {}
    sections = [str(job.get("descriptionPlain") or "")]
    for item in job.get("lists") or []:
        sections.append(str(item.get("text") or ""))
        sections.append(html_to_text(str(item.get("content") or "")))
    sections.append(str(job.get("additionalPlain") or ""))
    description = "\n\n".join(s.strip() for s in sections if s.strip())
    created = job.get("createdAt")
    posted_at = (
        datetime.fromtimestamp(created / 1000, tz=UTC) if isinstance(created, int | float) else None
    )
    return Posting(
        source="lever",
        source_job_id=f"{source.board}:{job['id']}",
        company=source.company,
        title=str(job.get("text", "")).strip(),
        location=str(categories.get("location") or "").strip(),
        description=description,
        url=str(job.get("hostedUrl") or ""),
        posted_at=posted_at,
        compensation=_compensation(job.get("salaryRange")),
        work_model_hint=_WORK_MODELS.get(str(job.get("workplaceType") or "").lower()),
    )


def _compensation(salary: object) -> Compensation | None:
    if not isinstance(salary, dict) or salary.get("interval") not in (None, "per-year-salary"):
        return None
    low, high = salary.get("min"), salary.get("max")
    if not isinstance(low, int | float) and not isinstance(high, int | float):
        return None
    return Compensation(
        minimum=float(low) if isinstance(low, int | float) else None,
        maximum=float(high) if isinstance(high, int | float) else None,
        currency=str(salary.get("currency") or "") or None,
    )
