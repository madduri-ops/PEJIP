"""The routine's command line (design doc 0015): the golden set through the workbench."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pejip import golden_eval, routine, workbench
from pejip.evaluation.cli import main as evaluation_main
from pejip.evaluation.golden import load_golden_set

RECORDINGS = Path(__file__).resolve().parents[2] / "eval" / "recordings"


def _answer_from_recordings(work: Path, skip: str | None = None) -> None:
    """Answer every case with the committed recording, as a session would."""
    for recording in sorted(RECORDINGS.glob("*.json")):
        if recording.stem == skip:
            continue
        data = json.loads(recording.read_text(encoding="utf-8"))
        folder = work / "roles" / recording.stem
        (folder / workbench.ANALYSIS_FILE).write_text(json.dumps(data["analysis"]))
        (folder / workbench.MATCHING_FILE).write_text(json.dumps(data["matching"]))


def test_next_walks_the_steps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    work = tmp_path / "w"
    assert routine.main(["--work", str(work), "eval-prepare"]) == 0
    cases = len(load_golden_set().cases)
    assert f"Prepared {cases} golden cases" in capsys.readouterr().out

    assert routine.main(["--work", str(work), "next"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("STEP role G01 job_analysis")
    assert str(work / "roles" / "G01" / "step.md") in out

    (work / "roles" / "G01" / workbench.ANALYSIS_FILE).write_text("{}")
    routine.main(["--work", str(work), "next"])
    assert capsys.readouterr().out.startswith("REDO role G01 job_analysis: ")

    routine.main(["--work", str(work), "next", "--role", "G02"])
    assert capsys.readouterr().out.startswith("STEP role G02 job_analysis")
    assert routine.main(["--work", str(work), "next", "--role", "G99"]) == 2
    assert "no role 'G99'" in capsys.readouterr().err

    _answer_from_recordings(work)
    routine.main(["--work", str(work), "next"])
    assert capsys.readouterr().out.startswith("DONE: every role")
    routine.main(["--work", str(work), "next", "--role", "G02"])
    assert capsys.readouterr().out.startswith("DONE: this role")


def test_the_golden_set_scores_the_same_through_the_workbench(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    work, out = tmp_path / "w", tmp_path / "recordings"
    routine.main(["--work", str(work), "eval-prepare"])
    _answer_from_recordings(work)
    args = ["--work", str(work), "eval-record", "--out", str(out), "--model", "test-model"]
    assert routine.main(args) == 0
    recording = json.loads((out / "G01.json").read_text(encoding="utf-8"))
    assert recording["provenance"] == {"ranker": "routine", "model": "test-model"}
    assert recording["golden_set_version"] == golden_eval.golden_set_version()

    report = tmp_path / "report.json"
    scorer = ["--scorer", "pejip.golden_eval:replay_scorer"]
    assert evaluation_main(["run", *scorer, "--report", str(report)]) == 0
    committed = json.loads(report.read_text(encoding="utf-8"))["metrics"]
    monkeypatch.setenv("PEJIP_EVAL_RECORDINGS", str(out))
    assert evaluation_main(["run", *scorer, "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["metrics"] == committed
    capsys.readouterr()


def test_record_names_cases_without_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = tmp_path / "w"
    routine.main(["--work", str(work), "eval-prepare"])
    _answer_from_recordings(work, skip="G02")
    args = ["--work", str(work), "eval-record", "--out", str(tmp_path / "r"), "--model", "m"]
    assert routine.main(args) == 1
    assert "No valid answers for: G02" in capsys.readouterr().out


def test_skip_and_refusals(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    work = tmp_path / "w"
    routine.main(["--work", str(work), "eval-prepare"])
    assert routine.main(["--work", str(work), "skip", "G01", "keeps failing"]) == 0
    assert "Skipped role G01." in capsys.readouterr().out
    assert routine.main(["--work", str(work), "skip", "G99", "why"]) == 2
    assert "no role 'G99'" in capsys.readouterr().err
