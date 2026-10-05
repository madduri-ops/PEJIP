from __future__ import annotations

import dataclasses
import json
import runpy
import sys
import types
from pathlib import Path

import pytest

from pejip.evaluation import cli
from pejip.evaluation.baseline import DEFAULT_BASELINE, Regression, read_baseline
from pejip.evaluation.evaluate import METRICS
from pejip.evaluation.golden import load_golden_set
from pejip.evaluation.scorer import (
    EvalInput,
    Prediction,
    Scorer,
    ScorerLoadError,
    load_scorer,
)


@pytest.fixture
def scorers(monkeypatch: pytest.MonkeyPatch, oracle: Scorer) -> str:
    module = types.ModuleType("fake_scorers")
    module.oracle = oracle  # type: ignore[attr-defined]
    module.bad = lambda _item: Prediction(fit=50, confidence="LOW", priority="LOW")  # type: ignore[attr-defined]
    module.noisy = lambda item: dataclasses.replace(oracle(item), fit=0)  # type: ignore[attr-defined]
    module.not_callable = 3  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_scorers", module)
    return "fake_scorers"


@pytest.fixture
def baseline(tmp_path: Path) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(DEFAULT_BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_committed_baseline_is_valid() -> None:
    data = read_baseline(DEFAULT_BASELINE)
    # Spec invariants start at their ceiling: network never moves Fit, every
    # explanation cites the posting.
    assert data["metrics"]["network_invariance"] == 1.0
    assert data["metrics"]["citation_validity"] == 1.0


def test_read_baseline_rejects_wrong_metrics(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"metrics": {"fit_in_range": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="must list exactly"):
        read_baseline(path)


@pytest.mark.parametrize(
    "spec",
    [
        "no_colon",
        ":attr",
        "mod:",
        "does.not.exist:x",
        "fake_scorers:not_callable",
        "fake_scorers:missing",
    ],
)
@pytest.mark.usefixtures("scorers")
def test_load_scorer_errors(spec: str) -> None:
    with pytest.raises(ScorerLoadError):
        load_scorer(spec)


@pytest.mark.usefixtures("scorers")
def test_load_scorer_ok() -> None:
    scorer = load_scorer("fake_scorers:oracle")
    golden = load_golden_set()
    case = golden.cases[0]
    assert scorer(EvalInput(case.id, case.job, case.context, golden.profile)).fit > 0


def test_validate(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["validate"]) == 0
    assert "cases OK" in capsys.readouterr().out


def test_invalid_golden_set(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--golden", str(tmp_path), "validate"]) == 2
    assert "manifest.toml: file not found" in capsys.readouterr().err


@pytest.mark.usefixtures("scorers")
def test_run_passes_and_writes_report(baseline: Path, tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    code = cli.main(
        [
            "run",
            "--scorer",
            "fake_scorers:oracle",
            "--baseline",
            str(baseline),
            "--report",
            str(report),
        ]
    )
    assert code == 0
    assert json.loads(report.read_text())["metrics"]["fit_in_range"] == 1.0


@pytest.mark.usefixtures("scorers")
def test_run_with_workers(baseline: Path, tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    args = ["run", "--scorer", "fake_scorers:oracle", "--baseline", str(baseline)]
    assert cli.main([*args, "--workers", "4", "--report", str(report)]) == 0
    assert json.loads(report.read_text())["metrics"]["fit_in_range"] == 1.0


@pytest.mark.parametrize("workers", ["0", "-1", "two"])
def test_workers_must_be_a_positive_number(
    workers: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main(["run", "--scorer", "x:y", "--workers", workers])
    assert exited.value.code == 2
    assert "--workers" in capsys.readouterr().err


@pytest.mark.usefixtures("scorers")
def test_run_fails_below_baseline(baseline: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "--scorer", "fake_scorers:bad", "--baseline", str(baseline)]) == 1
    captured = capsys.readouterr()
    assert "REGRESSION citation_validity: 0.0000 is below the baseline 1.0000" in captured.err
    assert "G01:" in captured.out


@pytest.mark.usefixtures("scorers")
def test_invariants_gate_ignores_metrics_that_move_with_the_model(
    baseline: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    noisy = ["run", "--scorer", "fake_scorers:noisy", "--baseline", str(baseline)]
    assert cli.main(noisy) == 1
    assert "REGRESSION fit_in_range" in capsys.readouterr().err
    assert cli.main([*noisy, "--gate", "invariants"]) == 0
    bad = ["run", "--scorer", "fake_scorers:bad", "--baseline", str(baseline)]
    assert cli.main([*bad, "--gate", "invariants"]) == 1
    assert "REGRESSION citation_validity" in capsys.readouterr().err


@pytest.mark.usefixtures("scorers")
def test_run_bad_scorer_or_baseline(baseline: Path, tmp_path: Path) -> None:
    assert cli.main(["run", "--scorer", "nope", "--baseline", str(baseline)]) == 2
    assert (
        cli.main(
            [
                "run",
                "--scorer",
                "fake_scorers:oracle",
                "--baseline",
                str(tmp_path / "missing.json"),
            ]
        )
        == 2
    )


@pytest.mark.usefixtures("scorers")
def test_ratchet_only_raises(baseline: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        cli.main(["ratchet", "--scorer", "fake_scorers:oracle", "--baseline", str(baseline)]) == 0
    )
    raised = read_baseline(baseline)
    assert raised["scorer"] == "fake_scorers:oracle"
    assert all(raised["metrics"][name] == 1.0 for name in METRICS)
    assert "baseline raised" in capsys.readouterr().out

    # A worse scorer never lowers it.
    assert cli.main(["ratchet", "--scorer", "fake_scorers:bad", "--baseline", str(baseline)]) == 0
    assert read_baseline(baseline)["metrics"] == raised["metrics"]
    assert "baseline unchanged" in capsys.readouterr().out


def test_regression_str() -> None:
    assert (
        str(Regression("fit_in_range", 0.5, 0.25))
        == "fit_in_range: 0.2500 is below the baseline 0.5000"
    )


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["pejip.evaluation", "validate"])
    with pytest.raises(SystemExit) as info:
        runpy.run_module("pejip.evaluation", run_name="__main__")
    assert info.value.code == 0
