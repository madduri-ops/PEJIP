"""Adapter that runs the FIND ranking pipeline over the golden evaluation set.

``python -m pejip.evaluation run --scorer pejip.golden_eval:replay_scorer`` scores
each case from the AI output recorded for it in ``eval/recordings/``, so changes to
scoring logic, weights or thresholds are measured without calling the model.
``live_scorer`` calls the model instead and, when ``PEJIP_EVAL_RECORD_DIR`` is set,
writes what it got there in the recording format, so a prompt or model change can
refresh the recordings (see ``eval/README.md``).

The adapter only translates: the golden profile into a :class:`CareerProfile`, the
case into a posting and job facts, and :class:`Recommendation` reason codes into
the golden set's vocabulary. Ranking itself is the same code the pipeline runs.
"""

from __future__ import annotations

import json
import os
import threading
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from pejip.ai.client import AIClient
from pejip.analysis import (
    EvidenceMatching,
    JobAnalysis,
    PostingText,
    analyze_job,
    ground_analysis,
    ground_matching,
)
from pejip.config import SearchConfig, load_config
from pejip.cost import CostGuard, SqliteLedger
from pejip.discovery import classify_location
from pejip.evaluation.golden import DEFAULT_GOLDEN_DIR, Job
from pejip.evaluation.scorer import EvalInput, Prediction
from pejip.explain import build_explanation, verify_citations
from pejip.profile import CareerProfile, Evidence, Seniority
from pejip.scoring import JobFacts, NetworkFacts, Recommendation, score_job

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "search.yaml"
RECORDINGS_DIR = ROOT / "eval" / "recordings"
EVAL_NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
# The live run's own cap: the whole set costs a few dollars, so this only stops a
# runaway. Production spend is capped by the shared ledger, not this one.
LIVE_RUN_CAP_USD = 25

LEVELS: dict[str, list[Seniority]] = {
    "EXECUTIVE": ["C_LEVEL", "SVP"],
    "VP_EQUIVALENT": ["VP", "HEAD_OF"],
    "SENIOR_DIRECTOR_EQUIVALENT": ["SENIOR_DIRECTOR"],
    "DIRECTOR_EQUIVALENT": ["DIRECTOR"],
}
# STRONG_ROLE_MATCH named for the kind of role, by keywords in the role family.
ROLE_FAMILY_REASONS = (
    (("ai ", "ai/", " ml", "machine learning"), "AI_TRANSFORMATION_MATCH"),
    (("transformation",), "STRONG_TRANSFORMATION_MATCH"),
    (("platform", "developer"), "STRONG_PLATFORM_MATCH"),
    (("portfolio", "program", "pmo"), "PORTFOLIO_LEADERSHIP_MATCH"),
    (("operations",), "OPERATIONS_LEADERSHIP_MATCH"),
)
POSITIVE = {
    "EXECUTIVE_SCOPE_MATCH": "EXECUTIVE_SCOPE_MATCH",
    "CAREER_DIRECTION_MATCH": "CAREER_DIRECTION_MATCH",
    "FRESH_POSTING": "FRESH_POSTING",
}
CONCERNS = {
    "SENIORITY_SCOPE_GAP": "SCOPE_CONCERN",
    "INDIVIDUAL_CONTRIBUTOR_CONCERN": "SCOPE_CONCERN",
    "CAPABILITY_GAP": "TECHNICAL_DEPTH_GAP",
    "DOMAIN_INDUSTRY_GAP": "INDUSTRY_GAP",
    "CAREER_DIRECTION_GAP": "CAREER_DIRECTION_CONCERN",
    "SALES_QUOTA_CONCERN": "QUOTA_CARRYING",
    "SALES_HEAVY_CONCERN": "QUOTA_CARRYING",
    "HANDS_ON_CONCERN": "HANDS_ON_CONCERN",
    "COMPENSATION_CONCERN": "COMPENSATION_CONCERN",
    "LOCATION_CONCERN": "LOCATION_CONCERN",
}


class MissingRecordingError(LookupError):
    """No recorded AI output for this case and golden set version."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"no recording at {path}; refresh it with the live scorer")


class UnrankedError(ValueError):
    """The pipeline could not compute a Fit, so the role stays unranked."""

    def __init__(self, case_id: str) -> None:
        super().__init__(f"{case_id} has no Fit")


def golden_set_version(golden_dir: Path = DEFAULT_GOLDEN_DIR) -> str:
    with (golden_dir / "manifest.toml").open("rb") as fh:
        version: str = tomllib.load(fh)["golden_set_version"]
    return version


def career_profile(data: dict[str, Any]) -> CareerProfile:
    """Map the golden set's synthetic profile onto the pipeline's profile model."""
    evidence = [
        Evidence(id=f"E{i}", kind="ACHIEVEMENT", text=item["text"])
        for i, item in enumerate(data["achievements"], 1)
    ]
    exp = data["experience"]
    evidence.append(
        Evidence(
            id=f"E{len(evidence) + 1}",
            kind="SCOPE",
            text=(
                f"{exp['years_leadership']} years in leadership; largest organization "
                f"{exp['largest_org_people']} people"
                + (", manager of managers" if exp["manager_of_managers"] else "")
                + f"; largest budget ${exp['largest_budget_usd']:,}; portfolios of up to "
                f"{exp['largest_portfolio_programs']} programs; executive exposure to "
                + ", ".join(exp["executive_exposure"])
                + "; industries: "
                + ", ".join(exp["industries"])
            ),
        )
    )
    prefs = data["search_preferences"]
    return CareerProfile(
        name="Golden set profile",
        email="golden@example.com",
        headline=data["headline"],
        target_seniority=[s for level in data["target_levels"] for s in LEVELS[level]],
        career_direction=(
            "Wants next: "
            + "; ".join(data["wants_next"])
            + ". Moving away from: "
            + "; ".join(data["moving_away_from"])
            + "."
        ),
        evidence=evidence,
        compensation={
            "minimum": prefs["min_base_usd"],
            "preferred": prefs["preferred_base_usd"],
            "minimum_is_hard_filter": False,
        },
    )


def posting_text(job: Job) -> PostingText:
    return PostingText(job.title, job.company, job.location, job.description.strip())


def job_record(job: Job) -> dict[str, Any]:
    posted = EVAL_NOW - timedelta(hours=job.posted_hours_ago)
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description.strip(),
        "posted_at": posted,
        "first_seen_at": posted,
        "comp_min": job.base_min_usd,
        "comp_max": job.base_max_usd,
    }


def reason_vocabulary(
    rec: Recommendation, analysis: JobAnalysis, excluded: bool
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Translate reason codes into the golden set's positive reasons and concerns."""
    positive: list[str] = []
    concerns: list[str] = []
    family = f" {analysis.role_family.lower()} "
    for code in rec.reason_codes:
        if code == "STRONG_ROLE_MATCH":
            positive += [r for words, r in ROLE_FAMILY_REASONS if any(w in family for w in words)]
        elif code in POSITIVE:
            positive.append(POSITIVE[code])
        elif code in CONCERNS:
            concerns.append(CONCERNS[code])
    if analysis.missing_information:
        concerns.append("MISSING_INFORMATION")
    if excluded:
        concerns.append("HARD_FILTER_TRIGGERED")
    return tuple(dict.fromkeys(positive)), tuple(dict.fromkeys(concerns))


def predict(
    item: EvalInput, analysis: JobAnalysis, matching: EvidenceMatching, config: SearchConfig
) -> Prediction:
    """Score one case the way the pipeline does and phrase it as a Prediction."""
    profile = career_profile(item.profile)
    posting = posting_text(item.job)
    text = "\n".join([posting.title, posting.company, posting.location, posting.description])
    analysis, _ = ground_analysis(analysis, text)
    matching = ground_matching(matching, analysis, profile)
    job = job_record(item.job)
    geo = classify_location(item.job.location, config.geography)
    facts = JobFacts(
        posted_at=job["posted_at"],
        first_seen_at=job["first_seen_at"],
        comp_min=job["comp_min"],
        comp_max=job["comp_max"],
        location_preference=geo.preference,
        as_of=EVAL_NOW,
        # The golden set records counts, not titles; strong relationships stand in for
        # matured connections so the network boost and Fit invariance are exercised.
        network=NetworkFacts(
            first_degree=item.context.connections,
            matured=item.context.strong_relationships,
            your_call=0,
        ),
    )
    rec = score_job(analysis, matching, profile, facts, config.scoring)
    if rec.fit is None:
        raise UnrankedError(item.case_id)
    explanation = build_explanation(analysis, matching, rec, job)
    verify_citations(explanation, job, profile)
    # The pipeline drops roles outside every geography scope before ranking them.
    excluded = config.geography.hard_filter and geo.preference == "INELIGIBLE"
    positive, concerns = reason_vocabulary(rec, analysis, excluded)
    quotes = [
        cite["quote"]
        for section in explanation.values()
        for point in section
        for cite in point["citations"]
        if cite["type"] == "posting"
    ]
    return Prediction(
        fit=rec.fit,
        confidence=rec.confidence,
        priority="EXCLUDED" if excluded else rec.priority,
        positive_reasons=positive,
        concerns=concerns,
        citations=tuple(dict.fromkeys(quotes)),
    )


@cache
def _config() -> SearchConfig:
    return load_config(CONFIG_PATH)


def recording_path(case_id: str, directory: Path | None = None) -> Path:
    return (directory or RECORDINGS_DIR) / f"{case_id}.json"


def load_recording(case_id: str) -> dict[str, Any]:
    path = recording_path(case_id)
    if not path.exists():
        raise MissingRecordingError(path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data["golden_set_version"] != golden_set_version():
        raise MissingRecordingError(path)
    return data


def replay_scorer(item: EvalInput) -> Prediction:
    """Score a case from its recorded AI output (no model call)."""
    data = load_recording(item.case_id)
    return predict(
        item,
        JobAnalysis.model_validate(data["analysis"]),
        EvidenceMatching.model_validate(data["matching"]),
        _config(),
    )


def make_live_scorer(
    ai: AIClient, record_dir: Path | None = None
) -> Callable[[EvalInput], Prediction]:
    """A scorer that calls the model once per case and optionally records the output."""
    outputs: dict[str, tuple[JobAnalysis, EvidenceMatching]] = {}

    def score(item: EvalInput) -> Prediction:
        # Network probes score the same case twice; the model is called once.
        if item.case_id not in outputs:
            profile = career_profile(item.profile)
            outcome = analyze_job(ai, profile, posting_text(item.job))
            outputs[item.case_id] = (outcome.analysis, outcome.matching)
            if record_dir is not None:
                record_dir.mkdir(parents=True, exist_ok=True)
                recording = {
                    "golden_set_version": golden_set_version(),
                    "provenance": outcome.provenance,
                    "analysis": outcome.analysis.model_dump(),
                    "matching": outcome.matching.model_dump(),
                }
                recording_path(item.case_id, record_dir).write_text(
                    json.dumps(recording, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
        analysis, matching = outputs[item.case_id]
        return predict(item, analysis, matching, _config())

    return score


_LIVE_LOCK = threading.Lock()


@cache
def _live() -> Callable[[EvalInput], Prediction]:
    # One client, spend ledger and output cache for the whole evaluation run.
    guard = CostGuard(SqliteLedger(":memory:"), cap_usd=LIVE_RUN_CAP_USD)
    record = os.environ.get("PEJIP_EVAL_RECORD_DIR")
    return make_live_scorer(AIClient(_config().ai, guard), Path(record) if record else None)


def live_scorer(item: EvalInput) -> Prediction:
    """Score a case by calling the model; needs Claude credentials (``pejip.claude_auth``)."""
    # Cases may be scored on several threads; they must share one client and cap.
    with _LIVE_LOCK:
        score = _live()
    return score(item)
