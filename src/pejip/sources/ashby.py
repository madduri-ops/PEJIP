"""Ashby public job posting API adapter (public GET endpoint, docs/sources.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pejip.config import SourceConfig
from pejip.models import Compensation, Posting
from pejip.sources.http import InvalidPayloadError, PoliteClient
from pejip.sources.text import html_to_text

DEFAULT_API_BASE = "https://api.ashbyhq.com"
_WORK_MODELS = {"remote": "REMOTE", "hybrid": "HYBRID", "onsite": "ONSITE"}


def fetch_ashby(client: PoliteClient, source: SourceConfig) -> list[Posting]:
    base = source.api_base or DEFAULT_API_BASE
    url = f"{base}/posting-api/job-board/{source.board}"
    payload = client.get_json(url, params={"includeCompensation": "true"})
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise InvalidPayloadError("Ashby", source.board)
    # Unlisted jobs are hidden from the company's own careers page, so PEJIP skips them.
    return [_to_posting(source, job) for job in jobs if job.get("isListed", True)]


def _to_posting(source: SourceConfig, job: dict[str, Any]) -> Posting:
    places = [str(job.get("location") or "").strip()]
    places += [str(s.get("location") or "").strip() for s in job.get("secondaryLocations") or []]
    description = str(job.get("descriptionPlain") or "").strip() or html_to_text(
        str(job.get("descriptionHtml") or "")
    )
    workplace = str(job.get("workplaceType") or "").lower().replace("-", "")
    return Posting(
        source="ashby",
        source_job_id=f"{source.board}:{job['id']}",
        company=source.company,
        title=str(job.get("title", "")).strip(),
        location="; ".join(p for p in places if p),
        description=description,
        url=str(job.get("jobUrl") or ""),
        posted_at=_published(job.get("publishedAt")),
        compensation=_compensation(job.get("compensation")),
        work_model_hint=_WORK_MODELS.get(workplace)
        or ("REMOTE" if job.get("isRemote") is True else None),
    )


def _published(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compensation(comp: object) -> Compensation | None:
    """The yearly salary range, when the board publishes one."""
    if not isinstance(comp, dict):
        return None
    for part in comp.get("summaryComponents") or []:
        if part.get("compensationType") != "Salary" or part.get("interval") != "1 YEAR":
            continue
        low, high = part.get("minValue"), part.get("maxValue")
        if not isinstance(low, int | float) and not isinstance(high, int | float):
            continue
        return Compensation(
            minimum=float(low) if isinstance(low, int | float) else None,
            maximum=float(high) if isinstance(high, int | float) else None,
            currency=str(part.get("currencyCode") or "") or None,
        )
    return None
