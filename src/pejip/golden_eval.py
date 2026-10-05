"""Golden evaluation set (spec 9.42, 17.31; policy section 12).

``replay`` scores each case's recorded AI output with the current scoring code, so
any change to scoring logic, weights or thresholds is measured without calling the
model. ``live`` re-runs the prompts against the configured model, so prompt and
model changes are measured too. Either mode fails when the share of passing cases
drops below the committed baseline in ``evals/baseline.json``.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from pejip.ai.client import AIClient, AIError
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
from pejip.explain import UnsupportedClaimError, build_explanation, verify_citations
from pejip.profile import CareerProfile, load_profile
from pejip.scoring import JobFacts, Recommendation, score_job

EVAL_NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@dataclass
class CaseResult:
    id: str
    passed: bool
    fit: float | None = None
    confidence: str | None = None
    priority: str | None = None
    failures: list[str] = field(default_factory=list)


def check_expectations(rec: Recommendation, expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    low, high = expected["fit"]
    if rec.fit is None or not low <= rec.fit <= high:
        failures.append(f"fit {rec.fit} outside [{low}, {high}]")
    if rec.confidence not in expected["confidence"]:
        failures.append(f"confidence {rec.confidence} not in {expected['confidence']}")
    if rec.priority not in expected["priority"]:
        failures.append(f"priority {rec.priority} not in {expected['priority']}")
    missing = [r for r in expected.get("reasons", []) if r not in rec.reason_codes]
    if missing:
        failures.append(f"missing reasons {missing}")
    present = [r for r in expected.get("absent_reasons", []) if r in rec.reason_codes]
    if present:
        failures.append(f"unexpected reasons {present}")
    return failures


def evaluate_case(
    case: dict[str, Any],
    config: SearchConfig,
    profile: CareerProfile,
    ai: AIClient | None,
) -> CaseResult:
    posting = case["posting"]
    job = {
        "title": posting["title"],
        "company": posting["company"],
        "location": posting["location"],
        "description": posting["description"],
        "posted_at": EVAL_NOW - timedelta(days=posting["age_days"]),
        "first_seen_at": EVAL_NOW,
        "comp_min": posting.get("comp_min"),
        "comp_max": posting.get("comp_max"),
    }
    try:
        if ai is None:
            text = "\n".join([job["title"], job["company"], job["location"], job["description"]])
            analysis, _ = ground_analysis(
                JobAnalysis.model_validate(case["recorded"]["analysis"]), text
            )
            matching = ground_matching(
                EvidenceMatching.model_validate(case["recorded"]["matching"]), analysis, profile
            )
        else:
            outcome = analyze_job(ai, profile, PostingText.from_job(job))
            analysis, matching = outcome.analysis, outcome.matching
    except AIError as exc:
        return CaseResult(case["id"], False, failures=[f"analysis failed: {exc}"])
    facts = JobFacts(
        posted_at=job["posted_at"],
        first_seen_at=job["first_seen_at"],
        comp_min=job["comp_min"],
        comp_max=job["comp_max"],
        location_preference=classify_location(job["location"], config.geography).preference,
        as_of=EVAL_NOW,
    )
    rec = score_job(analysis, matching, profile, facts, config.scoring)
    failures = check_expectations(rec, case["expected"])
    try:
        verify_citations(build_explanation(analysis, matching, rec, job), job, profile)
    except UnsupportedClaimError as exc:
        failures.append(str(exc))
    return CaseResult(case["id"], not failures, rec.fit, rec.confidence, rec.priority, failures)


@dataclass(frozen=True)
class EvalPaths:
    config: Path
    cases: Path
    baseline: Path
    profile: Path


def run_eval(paths: EvalPaths, *, live: bool, ai: AIClient | None = None) -> int:
    config = load_config(paths.config)
    profile = load_profile(paths.profile)
    cases = yaml.safe_load(paths.cases.read_text(encoding="utf-8"))
    mode = "live" if live else "replay"
    if live and ai is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("Live evaluation needs ANTHROPIC_API_KEY.\n")
            return 2
        # CI runs are bounded by the set size; the cap guards production spend.
        ai = AIClient(config.ai, CostGuard(SqliteLedger(":memory:")))
    results = [evaluate_case(c, config, profile, ai if live else None) for c in cases]
    score = round(sum(r.passed for r in results) / len(results), 4)
    baseline = float(json.loads(paths.baseline.read_text(encoding="utf-8"))[mode])
    report = {
        "mode": mode,
        "score": score,
        "baseline": baseline,
        "cases": [vars(r) for r in results],
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    if score < baseline:
        sys.stderr.write(f"Evaluation score {score} is below the {mode} baseline {baseline}.\n")
        return 1
    if score > baseline:
        sys.stderr.write(
            f"Evaluation score {score} beats the {mode} baseline {baseline}; "
            "raise evals/baseline.json in this PR.\n"
        )
    return 0
