"""Unit tests for the SAST, DAST and dependency audit severity gate."""

import json
from pathlib import Path

import pytest

from ci import severity_gate
from ci.severity_gate import Finding


def _bandit(*severities: str) -> dict[str, object]:
    return {
        "results": [
            {"issue_severity": s, "test_id": "B101", "filename": "src/x.py", "line_number": 3}
            for s in severities
        ]
    }


def _grype(*severities: str) -> dict[str, object]:
    return {
        "matches": [
            {
                "vulnerability": {"severity": s, "id": "GHSA-xxxx"},
                "artifact": {"name": "pkg", "version": "1.0"},
            }
            for s in severities
        ]
    }


def _zap(*riskcodes: str) -> dict[str, object]:
    return {
        "site": [
            {
                "@name": "http://localhost:8000",
                "alerts": [
                    {"riskcode": r, "pluginid": "10021", "name": "Alert"} for r in riskcodes
                ],
            }
        ]
    }


def test_bandit_findings() -> None:
    assert severity_gate.bandit_findings(_bandit("HIGH")) == [Finding("high", "B101", "src/x.py:3")]


def test_grype_findings() -> None:
    assert severity_gate.grype_findings(_grype("Critical")) == [
        Finding("critical", "GHSA-xxxx", "pkg==1.0")
    ]


def test_zap_findings() -> None:
    assert severity_gate.zap_findings(_zap("0", "1", "2", "3")) == [
        Finding(severity, "10021 Alert", "http://localhost:8000")
        for severity in ("informational", "low", "medium", "high")
    ]


@pytest.mark.parametrize(
    ("tool", "report", "exit_code"),
    [
        ("bandit", _bandit("LOW", "MEDIUM"), 0),
        ("bandit", _bandit("LOW", "HIGH"), 1),
        ("grype", _grype("Negligible", "Low", "Medium", "Unknown"), 0),
        ("grype", _grype("High"), 1),
        ("grype", _grype("Critical"), 1),
        ("zap", _zap("0", "1", "2"), 0),
        ("zap", _zap("3"), 1),
        ("zap", {"site": []}, 0),
    ],
)
def test_main_blocks_only_high_and_critical(
    tmp_path: Path, tool: str, report: dict[str, object], exit_code: int
) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert severity_gate.main([tool, str(path)]) == exit_code


def test_main_prints_every_finding(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_bandit("LOW", "HIGH")), encoding="utf-8")

    severity_gate.main(["bandit", str(path)])

    out = capsys.readouterr().out
    assert out.count("B101") == 2
    assert "bandit: 2 findings, 1 high or critical." in out
    assert "::error::bandit found 1 high or critical findings" in out
