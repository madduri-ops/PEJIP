"""Unit tests for the coverage gate and ratchet."""

import json
from pathlib import Path

import pytest

from ci import coverage_gate


def _report(lines: tuple[int, int], branches: tuple[int, int]) -> dict[str, object]:
    return {
        "totals": {
            "covered_lines": lines[0],
            "num_statements": lines[1],
            "covered_branches": branches[0],
            "num_branches": branches[1],
        }
    }


def _write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_measure_floors_to_two_decimals() -> None:
    measured = coverage_gate.measure(_report((2, 3), (0, 0)))

    assert measured == {"line": 66.66, "branch": 100.0}


@pytest.mark.parametrize(
    ("measured", "baseline", "base", "expected"),
    [
        ({"line": 100.0, "branch": 96.0}, {"line": 100.0, "branch": 95.0}, None, []),
        (
            {"line": 99.99, "branch": 96.0},
            {"line": 100.0, "branch": 95.0},
            None,
            ["line coverage 99.99% is below 100.00%"],
        ),
        (
            {"line": 100.0, "branch": 96.0},
            {"line": 100.0, "branch": 97.0},
            None,
            ["branch coverage 96.00% is below 97.00%"],
        ),
        (
            {"line": 100.0, "branch": 94.0},
            {"line": 100.0, "branch": 90.0},
            None,
            ["branch coverage 94.00% is below 95.00%"],
        ),
        (
            {"line": 100.0, "branch": 98.0},
            {"line": 100.0, "branch": 96.0},
            {"line": 100.0, "branch": 97.0},
            ["branch baseline lowered from 97.00% to 96.00%; the ratchet never goes down"],
        ),
        (
            {"line": 100.0, "branch": 98.0},
            {"line": 100.0, "branch": 98.0},
            {"line": 100.0, "branch": 97.0},
            [],
        ),
    ],
)
def test_check(
    measured: dict[str, float],
    baseline: dict[str, float],
    base: dict[str, float] | None,
    expected: list[str],
) -> None:
    assert coverage_gate.check(measured, baseline, base) == expected


def test_main_passes_at_baseline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = _write(tmp_path / "coverage.json", _report((10, 10), (19, 20)))
    baseline = _write(tmp_path / "baseline.json", {"line": 100.0, "branch": 95.0})

    assert coverage_gate.main(["--report", str(report), "--baseline", str(baseline)]) == 0
    assert "::notice::" not in capsys.readouterr().out


def test_main_fails_below_baseline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = _write(tmp_path / "coverage.json", _report((9, 10), (20, 20)))
    baseline = _write(tmp_path / "baseline.json", {"line": 100.0, "branch": 95.0})

    assert coverage_gate.main(["--report", str(report), "--baseline", str(baseline)]) == 1
    assert "::error::line coverage 90.00% is below 100.00%" in capsys.readouterr().out


def test_main_fails_when_baseline_lowered(tmp_path: Path) -> None:
    report = _write(tmp_path / "coverage.json", _report((10, 10), (20, 20)))
    baseline = _write(tmp_path / "baseline.json", {"line": 100.0, "branch": 95.0})
    base = _write(tmp_path / "base.json", {"line": 100.0, "branch": 99.0})

    argv = ["--report", str(report), "--baseline", str(baseline), "--base-baseline", str(base)]
    assert coverage_gate.main(argv) == 1


def test_main_notes_improvement_without_update(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = _write(tmp_path / "coverage.json", _report((10, 10), (20, 20)))
    baseline = _write(tmp_path / "baseline.json", {"line": 100.0, "branch": 95.0})

    assert coverage_gate.main(["--report", str(report), "--baseline", str(baseline)]) == 0
    assert "::notice::Coverage is above the baseline" in capsys.readouterr().out
    assert json.loads(baseline.read_text(encoding="utf-8"))["branch"] == 95.0


def test_main_update_raises_baseline(tmp_path: Path) -> None:
    report = _write(tmp_path / "coverage.json", _report((10, 10), (39, 40)))
    baseline = _write(tmp_path / "baseline.json", {"line": 100.0, "branch": 95.0})

    argv = ["--report", str(report), "--baseline", str(baseline), "--update"]
    assert coverage_gate.main(argv) == 0
    assert json.loads(baseline.read_text(encoding="utf-8")) == {"line": 100.0, "branch": 97.5}
