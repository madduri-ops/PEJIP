"""The executive digest (spec 11.8 to 11.15), rendered as Markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

SECTION_ORDER = ("IMMEDIATE", "HIGH")


@dataclass(frozen=True)
class DigestItem:
    job: dict[str, Any]
    discovery: str
    recommendation: dict[str, Any] | None
    failure: str | None = None


@dataclass
class SourceResult:
    name: str
    status: str  # OK or FAILED
    fetched: int = 0
    candidates: int = 0
    error: str | None = None


@dataclass
class Digest:
    run_id: str
    generated_at: datetime
    status: str
    sources: list[SourceResult]
    items: list[DigestItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _cite(cite: dict[str, str]) -> str:
    if cite["type"] == "posting":
        quote = cite["quote"]
        return f'"{quote[:117]}..."' if len(quote) > 120 else f'"{quote}"'
    if cite["type"] == "profile":
        return cite["evidence_id"]
    return f"job {cite['field']}"


def _points(points: list[dict[str, Any]]) -> list[str]:
    lines = []
    for point in points:
        cites = "; ".join(_cite(c) for c in point["citations"])
        lines.append(f"  - {point['text']}" + (f" ({cites})" if cites else ""))
    return lines


def _render_item(item: DigestItem) -> list[str]:
    job, rec = item.job, item.recommendation
    new = " **New**" if item.discovery == "NEW_POSTING" else ""
    changed = " **Changed**" if item.discovery == "MATERIALLY_CHANGED" else ""
    lines = [f"### [{job['title']}]({job['url']}) at {job['company']}{new}{changed}"]
    lines.append(f"{job['location'] or 'Location not stated'}")
    lines.append("")
    if rec is None:
        lines.append(f"- Unranked: {item.failure or 'not analysed yet'}")
        return [*lines, ""]
    detail = rec["detail"]
    fit = "unknown" if rec["fit"] is None else f"{rec['fit']:.0f}"
    lines.append(
        f"- Fit **{fit}**, Confidence **{rec['confidence']}**, Priority **{rec['priority']}**"
    )
    explanation = detail["explanation"]
    for title, key in (
        ("Why it fits", "why_it_fits"),
        ("Concerns", "concerns"),
        ("Why now", "why_now"),
        ("Who you know", "who_you_know"),
    ):
        if explanation[key]:
            lines.append(f"- {title}:")
            lines.extend(_points(explanation[key]))
    return [*lines, ""]


def _priority(item: DigestItem) -> str:
    return item.recommendation["priority"] if item.recommendation else "UNRANKED"


def _fit(item: DigestItem) -> float:
    rec = item.recommendation
    return float(rec["fit"]) if rec and rec["fit"] is not None else -1.0


def render(digest: Digest, strong_match_fit: float) -> str:
    items = sorted(digest.items, key=_fit, reverse=True)
    attention = [i for i in items if _priority(i) in SECTION_ORDER]
    strong = [
        i
        for i in items
        if i not in attention and i.discovery == "NEW_POSTING" and _fit(i) >= strong_match_fit
    ]
    unranked = [i for i in items if i.recommendation is None or i.recommendation["fit"] is None]
    shown = {id(i) for i in attention + strong + unranked}
    other = [i for i in items if id(i) not in shown]

    lines = [
        f"# PEJIP digest, {digest.generated_at:%Y-%m-%d %H:%M} UTC",
        "",
        f"Search run `{digest.run_id}` finished **{digest.status}**.",
        "",
    ]
    for title, group in (
        ("Requires your attention", attention),
        ("New strong matches", strong),
        ("Other opportunities", other),
        ("Unranked", unranked),
    ):
        lines += [f"## {title}", ""]
        if not group:
            lines += ["Nothing here this run.", ""]
        for item in group:
            lines += _render_item(item)

    lines += [
        "## Search health",
        "",
        "| Source | Status | Fetched | Candidates |",
        "|---|---|---|---|",
    ]
    for src in digest.sources:
        status = src.status if src.error is None else f"{src.status}: {src.error}"
        lines.append(f"| {src.name} | {status} | {src.fetched} | {src.candidates} |")
    lines.append("")
    lines += [f"- {note}" for note in digest.notes]
    return "\n".join(lines).rstrip() + "\n"
