from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path
from typing import Any

import pytest

from pejip import cli, evaluation
from pejip.ai.client import AIClient
from pejip.config import SearchConfig
from pejip.digest import Digest
from pejip.evaluation import run_eval
from pejip.store import Store
from tests.conftest import NOW, ROOT, FakeMessages, response


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copy(ROOT / "examples" / "profile.example.yaml", tmp_path / "profile.yaml")
    monkeypatch.setenv("PEJIP_CONFIG", str(ROOT / "config" / "search.yaml"))
    monkeypatch.setenv("PEJIP_PROFILE", str(tmp_path / "profile.yaml"))
    monkeypatch.setenv("PEJIP_DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("PEJIP_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    return tmp_path


@pytest.mark.parametrize(("status", "code"), [("SUCCESS", 0), ("PARTIAL", 0), ("FAILED", 1)])
def test_run_writes_the_digest(
    env: Path, monkeypatch: pytest.MonkeyPatch, status: str, code: int
) -> None:
    class StubPipeline:
        def __init__(self, *args: Any) -> None:
            self.args = args

        def run(self) -> Digest:
            return Digest("run-1", NOW, status, [])

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    assert cli.main(["run"]) == code
    written = list((env / "out").glob("digest-*.md"))
    assert len(written) == 1 and f"finished **{status}**" in written[0].read_text()


def test_purge_export_and_delete(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = Store(f"sqlite:///{env / 'cli.db'}")
    store.record_ai_usage("f", "m", 1, 1, 0.5, NOW)
    assert cli.main(["purge"]) == 0
    out = env / "export.json"
    assert cli.main(["export", str(out)]) == 0
    assert "ai_usage" in json.loads(out.read_text())
    assert cli.main(["delete-all"]) == 2
    assert "Refusing" in capsys.readouterr().err
    assert cli.main(["delete-all", "--yes"]) == 0
    assert json.loads(store.export_all())["ai_usage"] == []


def test_eval_replay_via_cli(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(
        [
            "eval",
            "--cases",
            str(ROOT / "evals" / "golden.yaml"),
            "--baseline",
            str(ROOT / "evals" / "baseline.json"),
            "--profile",
            str(ROOT / "examples" / "profile.example.yaml"),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["mode"] == "replay"
    assert report["score"] >= report["baseline"]


def test_module_entry_point(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["pejip", "purge"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("pejip", run_name="__main__")
    assert exit_info.value.code == 0


def eval_args(tmp_path: Path, baseline: dict[str, float]) -> dict[str, Any]:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline))
    return {
        "config_path": ROOT / "config" / "search.yaml",
        "cases_path": ROOT / "evals" / "golden.yaml",
        "baseline_path": path,
        "profile_path": ROOT / "examples" / "profile.example.yaml",
    }


def test_eval_fails_below_baseline_and_asks_to_ratchet_above_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_eval(live=False, **eval_args(tmp_path, {"replay": 1.01, "live": 0})) == 1
    assert "below the replay baseline" in capsys.readouterr().err
    assert run_eval(live=False, **eval_args(tmp_path, {"replay": 0.5, "live": 0})) == 0
    assert "raise evals/baseline.json" in capsys.readouterr().err


def test_live_eval_needs_a_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert run_eval(live=True, **eval_args(tmp_path, {"replay": 1, "live": 0})) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_live_eval_builds_a_client_from_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: SearchConfig
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    built: list[AIClient] = []

    def fake_client(cfg: Any, store: Store) -> AIClient:
        client = AIClient(cfg, store, messages=FakeMessages(*[response("bad")] * 40))
        built.append(client)
        return client

    monkeypatch.setattr(evaluation, "AIClient", fake_client)
    assert run_eval(live=True, **eval_args(tmp_path, {"replay": 1, "live": 0})) == 0
    assert len(built) == 1


def test_live_eval_replays_recorded_outputs_through_the_model_path(
    tmp_path: Path, config: SearchConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    cases = yaml.safe_load((ROOT / "evals" / "golden.yaml").read_text())
    queue = []
    for case in cases:
        queue += [response(case["recorded"]["analysis"]), response(case["recorded"]["matching"])]
    client = AIClient(
        config.ai, Store("sqlite://"), messages=FakeMessages(*queue), clock=lambda: NOW
    )
    assert run_eval(live=True, ai=client, **eval_args(tmp_path, {"replay": 1, "live": 1.0})) == 0
    assert json.loads(capsys.readouterr().out)["score"] == 1.0


def test_live_eval_counts_model_failures(
    tmp_path: Path, config: SearchConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    client = AIClient(
        config.ai,
        Store("sqlite://"),
        messages=FakeMessages(*[response("bad")] * 40),
        clock=lambda: NOW,
    )
    assert run_eval(live=True, ai=client, **eval_args(tmp_path, {"replay": 1, "live": 0.5})) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["score"] == 0.0
    assert report["cases"][0]["failures"][0].startswith("analysis failed")


def test_unsupported_claims_fail_a_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def reject(*_args: Any) -> None:
        raise evaluation.UnsupportedClaim("unresolved citation")

    monkeypatch.setattr(evaluation, "verify_citations", reject)
    assert run_eval(live=False, **eval_args(tmp_path, {"replay": 0, "live": 0})) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["score"] == 0.0
    assert "unresolved citation" in report["cases"][0]["failures"]


def test_expectation_checks_report_each_mismatch() -> None:
    from types import SimpleNamespace

    rec = SimpleNamespace(fit=None, confidence="LOW", priority="LOW", reason_codes=["X"])
    failures = evaluation.check_expectations(
        rec,  # type: ignore[arg-type]
        {
            "fit": [80, 100],
            "confidence": ["HIGH"],
            "priority": ["HIGH"],
            "reasons": ["Y"],
            "absent_reasons": ["X"],
        },
    )
    assert len(failures) == 5
