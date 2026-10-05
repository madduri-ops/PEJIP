"""Greenhouse Job Board API adapter (public GET endpoints, docs/sources.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pejip.config import SourceConfig
from pejip.models import Compensation, Posting
from pejip.sources.http import FetchError, PoliteClient
from pejip.sources.text import extract_salary_range, html_to_text

DEFAULT_API_BASE = "https://boards-api.greenhouse.io"


def fetch_greenhouse(client: PoliteClient, source: SourceConfig) -> list[Posting]:
    base = source.api_base or DEFAULT_API_BASE
    url = f"{base}/v1/boards/{source.board}/jobs"
    payload = client.get_json(url, params={"content": "true"})
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise FetchError(f"unexpected Greenhouse payload for board {source.board}")
    return [_to_posting(source, job) for job in payload["jobs"]]


def _to_posting(source: SourceConfig, job: dict[str, Any]) -> Posting:
    location = (job.get("location") or {}).get("name") or ""
    published = job.get("first_published") or job.get("updated_at")
    description = html_to_text(str(job.get("content") or ""))
    salary = extract_salary_range(description)
    return Posting(
        source="greenhouse",
        source_job_id=f"{source.board}:{job['id']}",
        company=source.company,
        title=str(job.get("title", "")).strip(),
        location=str(location).strip(),
        description=description,
        url=str(job.get("absolute_url") or ""),
        posted_at=_parse_time(published),
        compensation=Compensation(salary[0], salary[1], "USD") if salary else None,
    )


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
