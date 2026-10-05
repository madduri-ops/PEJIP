from __future__ import annotations

from typing import Any

from pejip.digest import Digest, DigestItem, SourceResult, render
from tests.conftest import NOW


def job(title: str, location: str = "Oakland, CA") -> dict[str, Any]:
    return {"title": title, "url": f"https://jobs/{title}", "company": "Co", "location": location}


def rec(fit: float | None, priority: str) -> dict[str, Any]:
    long_quote = "x" * 130
    return {
        "fit": fit,
        "confidence": "HIGH",
        "priority": priority,
        "detail": {
            "explanation": {
                "why_it_fits": [
                    {
                        "text": "Strong match",
                        "citations": [
                            {"type": "posting", "quote": "Lead ops"},
                            {"type": "profile", "evidence_id": "E1"},
                        ],
                    }
                ],
                "concerns": [
                    {"text": "Long", "citations": [{"type": "posting", "quote": long_quote}]}
                ],
                "why_now": [
                    {
                        "text": "Posted today",
                        "citations": [{"type": "job_field", "field": "posted_at"}],
                    }
                ],
                "who_you_know": [],
            }
        },
    }


def test_render_groups_items_and_shows_search_health() -> None:
    digest = Digest(
        run_id="run-1",
        generated_at=NOW,
        status="PARTIAL",
        sources=[
            SourceResult("A (lever)", "OK", 10, 2),
            SourceResult("B (greenhouse)", "FAILED", error="HTTP 500"),
        ],
        items=[
            DigestItem(job("Top"), "NEW_POSTING", rec(95, "IMMEDIATE")),
            DigestItem(job("Strong new"), "NEW_POSTING", rec(80, "MEDIUM")),
            DigestItem(job("Changed", location=""), "MATERIALLY_CHANGED", rec(60, "MEDIUM")),
            DigestItem(job("Failed"), "PREVIOUSLY_SEEN", None, "analysis failed"),
            DigestItem(job("Pending"), "PREVIOUSLY_SEEN", None),
            DigestItem(job("No fit"), "PREVIOUSLY_SEEN", rec(None, "UNRANKED")),
        ],
        notes=["The monthly AI spend cap was reached; remaining roles are unranked."],
    )
    text = render(digest, strong_match_fit=75)
    sections = text.split("\n## ")
    assert "[Top](https://jobs/Top) at Co **New**" in sections[1]
    assert "Strong new" in sections[2]
    assert "Changed** " not in text
    assert "**Changed**" in sections[3]
    assert "Location not stated" in sections[3]
    assert "Unranked: analysis failed" in sections[4]
    assert "Unranked: not analysed yet" in sections[4]
    assert "Fit **unknown**" in sections[4]
    assert '("Lead ops"; E1)' in text
    assert '"' + "x" * 117 + '..."' in text
    assert "(job posted_at)" in text
    assert "| B (greenhouse) | FAILED: HTTP 500 | 0 | 0 |" in text
    assert text.endswith("remaining roles are unranked.\n")


def test_render_empty_digest() -> None:
    text = render(Digest("r", NOW, "SUCCESS", []), strong_match_fit=75)
    assert text.count("Nothing here this run.") == 4
