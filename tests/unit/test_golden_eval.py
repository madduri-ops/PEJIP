from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pejip import golden_eval
from pejip.ai.client import AIClient
from pejip.analysis import EvidenceMatching, JobAnalysis
from pejip.config import SearchConfig
from pejip.cost import CostGuard
from pejip.evaluation.golden import GoldenSet, load_golden_set
from pejip.evaluation.scorer import EvalInput
from pejip.scoring import Recommendation
from tests import factories as f
from tests.conftest import NOW, FakeMessages, response

QUOTES = (
    "lead an enterprise-wide, multi-year transformation roadmap",
    "own a $90M transformation portfolio",
)


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return load_golden_set()


def g01(golden: GoldenSet) -> EvalInput:
    case = next(c for c in golden.cases if c.id == "G01")
    return EvalInput(case.id, case.job, case.context, golden.profile)


def london(golden: GoldenSet) -> EvalInput:
    case = next(c for c in golden.cases if c.job.location.startswith("London"))
    return EvalInput(case.id, case.job, case.context, golden.profile)


def model_output(**overrides: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    reqs = [
        f.requirement("R1", quote=QUOTES[0]),
        f.requirement("R2", category="LEADERSHIP", quote=QUOTES[1]),
    ]
    analysis = f.analysis(reqs, role_family="Enterprise Transformation", **overrides)
    matching = f.matching([f.match("R1", evidence=["E1"]), f.match("R2", evidence=["E2"])])
    return analysis, matching


def record(directory: Path, case_id: str, version: str) -> None:
    analysis, matching = model_output()
    data = {"golden_set_version": version, "analysis": analysis, "matching": matching}
    (directory / f"{case_id}.json").write_text(json.dumps(data))


def test_profile_maps_levels_achievements_and_scope(golden: GoldenSet) -> None:
    profile = golden_eval.career_profile(golden.profile)
    assert profile.target_seniority == ["C_LEVEL", "SVP", "VP", "HEAD_OF", "SENIOR_DIRECTOR"]
    ids = [e.id for e in profile.evidence]
    assert ids == [f"E{i}" for i in range(1, len(golden.profile["achievements"]) + 2)]
    assert profile.evidence[-1].kind == "SCOPE"
    assert "manager of managers" in profile.evidence[-1].text
    assert profile.compensation.minimum == golden.profile["search_preferences"]["min_base_usd"]
    assert "Moving away from" in profile.career_direction


def test_profile_without_manager_of_managers(golden: GoldenSet) -> None:
    data = {**golden.profile, "experience": {**golden.profile["experience"]}}
    data["experience"]["manager_of_managers"] = False
    assert "manager of managers" not in golden_eval.career_profile(data).evidence[-1].text


def test_replay_scores_a_case_from_its_recording(
    golden: GoldenSet, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(golden_eval, "RECORDINGS_DIR", tmp_path)
    record(tmp_path, "G01", golden.version)
    prediction = golden_eval.replay_scorer(g01(golden))
    assert prediction.fit == 100.0
    assert prediction.priority == "IMMEDIATE"
    assert "STRONG_TRANSFORMATION_MATCH" in prediction.positive_reasons
    assert "EXECUTIVE_SCOPE_MATCH" in prediction.positive_reasons
    assert "FRESH_POSTING" in prediction.positive_reasons
    assert set(prediction.citations) == set(QUOTES)


def test_replay_needs_a_recording_for_this_set_version(
    golden: GoldenSet, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(golden_eval, "RECORDINGS_DIR", tmp_path)
    with pytest.raises(golden_eval.MissingRecordingError, match="no recording"):
        golden_eval.replay_scorer(g01(golden))
    record(tmp_path, "G01", "0.0.0")
    with pytest.raises(golden_eval.MissingRecordingError):
        golden_eval.replay_scorer(g01(golden))


def test_roles_outside_every_geography_are_excluded(
    golden: GoldenSet, config: SearchConfig
) -> None:
    analysis, matching = model_output()
    item = london(golden)
    quote = item.job.description.strip().splitlines()[0].strip()
    analysis["requirements"] = [f.requirement("R1", quote=quote)]
    matching = f.matching([f.match("R1")])
    prediction = golden_eval.predict(
        item,
        JobAnalysis.model_validate(analysis),
        EvidenceMatching.model_validate(matching),
        config,
    )
    assert prediction.priority == "EXCLUDED"
    assert "HARD_FILTER_TRIGGERED" in prediction.concerns


def test_no_fit_means_unranked(
    golden: GoldenSet, config: SearchConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis, matching = model_output()

    def no_fit(*_args: Any) -> Recommendation:
        return Recommendation(None, [], 0, "LOW", 0, [], "UNRANKED", None, 0, "UNKNOWN", "")

    monkeypatch.setattr(golden_eval, "score_job", no_fit)
    with pytest.raises(golden_eval.UnrankedError, match="G01 has no Fit"):
        golden_eval.predict(
            g01(golden),
            JobAnalysis.model_validate(analysis),
            EvidenceMatching.model_validate(matching),
            config,
        )


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("AI Governance", "AI_TRANSFORMATION_MATCH"),
        ("AI/ML Enablement", "AI_TRANSFORMATION_MATCH"),
        ("Developer Platforms", "STRONG_PLATFORM_MATCH"),
        ("Program / Portfolio Leadership", "PORTFOLIO_LEADERSHIP_MATCH"),
        ("Technology Operations", "OPERATIONS_LEADERSHIP_MATCH"),
        ("Marketing", None),
    ],
)
def test_role_match_is_named_by_role_family(family: str, expected: str | None) -> None:
    analysis = JobAnalysis.model_validate(f.analysis(role_family=family))
    rec = Recommendation(90, [], 0, "HIGH", 1, [], "HIGH", 90, 1, "STRONG", "PREFERRED")
    rec.reason_codes.append("STRONG_ROLE_MATCH")
    positive, _ = golden_eval.reason_vocabulary(rec, analysis, excluded=False)
    assert positive == ((expected,) if expected else ())


def test_concerns_are_translated_once_each() -> None:
    analysis = JobAnalysis.model_validate(f.analysis(missing_information=["TEAM_SIZE"]))
    rec = Recommendation(40, [], 0, "LOW", 0, [], "LOW", 40, 9, "UNKNOWN", "UNKNOWN")
    rec.reason_codes.extend(
        ["SALES_QUOTA_CONCERN", "SALES_HEAVY_CONCERN", "CAREER_DIRECTION_GAP", "UNMAPPED"]
    )
    _, concerns = golden_eval.reason_vocabulary(rec, analysis, excluded=False)
    assert concerns == ("QUOTA_CARRYING", "CAREER_DIRECTION_CONCERN", "MISSING_INFORMATION")


def test_live_scorer_calls_the_model_once_per_case_and_records(
    golden: GoldenSet, config: SearchConfig, guard: CostGuard, tmp_path: Path
) -> None:
    analysis, matching = model_output()
    fake = FakeMessages(response(analysis), response(matching))
    score = golden_eval.make_live_scorer(
        AIClient(config.ai, guard, messages=fake, clock=lambda: NOW), tmp_path / "rec"
    )
    first = score(g01(golden))
    again = score(g01(golden))
    assert first == again
    assert len(fake.calls) == 2
    saved = json.loads((tmp_path / "rec" / "G01.json").read_text())
    assert saved["golden_set_version"] == golden.version
    assert saved["provenance"]["analysis"]["prompt_id"] == "JOB_ANALYSIS"
    assert JobAnalysis.model_validate(saved["analysis"]).role_family == "Enterprise Transformation"


def test_live_scorer_builds_one_client_per_run(
    golden: GoldenSet, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis, matching = model_output()
    fake = FakeMessages(response(analysis), response(matching))
    built: list[CostGuard] = []

    def client(cfg: Any, guard: CostGuard) -> AIClient:
        built.append(guard)
        return AIClient(cfg, guard, messages=fake, clock=lambda: NOW)

    monkeypatch.setattr(golden_eval, "AIClient", client)
    for record_dir in (str(tmp_path), None):
        golden_eval._live.cache_clear()
        if record_dir:
            monkeypatch.setenv("PEJIP_EVAL_RECORD_DIR", record_dir)
        else:
            monkeypatch.delenv("PEJIP_EVAL_RECORD_DIR")
            fake.queue += [response(analysis), response(matching)]
        assert golden_eval.live_scorer(g01(golden)).fit == 100.0
        assert golden_eval.live_scorer(g01(golden)).fit == 100.0
    golden_eval._live.cache_clear()
    assert len(built) == 2
    assert built[0].cap_usd == golden_eval.LIVE_RUN_CAP_USD
    assert (tmp_path / "G01.json").exists()
