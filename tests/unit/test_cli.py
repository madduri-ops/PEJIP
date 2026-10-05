from __future__ import annotations

import json
import os
import runpy
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

from pejip import cli
from pejip.digest import Digest
from pejip.network.matching import NetworkIndex
from pejip.store import Store
from tests.conftest import NOW, ROOT
from tests.linkedin import export, row


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copy(ROOT / "examples" / "profile.example.yaml", tmp_path / "profile.yaml")
    monkeypatch.setenv("PEJIP_CONFIG", str(ROOT / "config" / "search.yaml"))
    monkeypatch.setenv("PEJIP_PROFILE", str(tmp_path / "profile.yaml"))
    monkeypatch.setenv("PEJIP_DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("PEJIP_AI_LEDGER", str(tmp_path / "spend.db"))
    monkeypatch.setenv("PEJIP_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    return tmp_path


@pytest.mark.parametrize(("status", "code"), [("SUCCESS", 0), ("PARTIAL", 0), ("FAILED", 1)])
def test_run_writes_the_digest(
    env: Path, monkeypatch: pytest.MonkeyPatch, status: str, code: int
) -> None:
    class StubPipeline:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def run(self) -> Digest:
            return Digest("run-1", NOW, status, [])

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    assert cli.main(["run"]) == code
    written = list((env / "out").glob("digest-*.md"))
    assert len(written) == 1
    assert f"finished **{status}**" in written[0].read_text()


def test_purge_export_and_delete(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = Store(f"sqlite:///{env / 'cli.db'}")
    store.start_run("r1", NOW)
    assert cli.main(["purge"]) == 0
    out = env / "export.json"
    assert cli.main(["export", str(out)]) == 0
    assert json.loads(out.read_text())["runs"][0]["id"] == "r1"
    assert cli.main(["delete-all"]) == 2
    assert "Refusing" in capsys.readouterr().err
    assert cli.main(["delete-all", "--yes"]) == 0
    assert json.loads(store.export_all())["runs"] == []


@pytest.mark.usefixtures("env")
def test_run_reads_the_inbox_only_when_a_bucket_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict[str, Any]] = []

    class StubPipeline:
        def __init__(self, *_args: Any, **kwargs: Any) -> None:
            built.append(kwargs)

        def run(self) -> Digest:
            return Digest("run-1", NOW, "SUCCESS", [])

    regions: list[str | None] = []

    def fake_client(region: str | None) -> object:
        regions.append(region)
        return object()

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    monkeypatch.setattr(cli, "make_s3_client", fake_client)
    assert cli.main(["run"]) == 0
    assert built[-1]["inbox"] is None
    monkeypatch.setenv("PEJIP_INBOX_BUCKET", "inbox-bucket")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    assert cli.main(["run"]) == 0
    assert built[-1]["inbox"] is not None
    assert regions == ["us-west-2"]


@pytest.mark.usefixtures("env")
def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["pejip", "purge"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("pejip", run_name="__main__")
    assert exit_info.value.code == 0


@pytest.mark.parametrize("command", ["run", "purge"])
def test_old_digests_are_deleted_and_recent_ones_kept(
    env: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    class StubPipeline:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def run(self) -> Digest:
            return Digest("run-1", NOW, "SUCCESS", [])

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    out = env / "out"
    out.mkdir()
    old, recent = out / "digest-old.md", out / "digest-recent.md"
    old.write_text("old")
    recent.write_text("recent")
    hundred_days_ago = time.time() - 100 * 86400
    os.utime(old, (hundred_days_ago, hundred_days_ago))
    assert cli.main([command]) == 0
    assert not old.exists()
    assert recent.exists()


def test_connections_reports_counts_and_names_to_review_but_no_people(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    upload = env / "Connections.csv"
    upload.write_bytes(
        export(
            row("Avery", "Synthetic", "Anthropic, PBC", "SVP Technology"),
            row("Casey", "Synthetic", "Anthropic", "Partner"),
            row("Devon", "Synthetic", "Stripe Cloud", "VP"),
            *[row("", "", "Anthropic", "VP")] * 7,
        )
    )
    assert cli.main(["connections", str(upload)]) == 0
    out = capsys.readouterr().out
    assert "Valid connections: 3" in out
    assert "no first or last name: lines 8, 9, 10, 11, 12 and 2 more" in out
    assert "Anthropic: 2 connections, 1 unclear titles" in out
    assert "Stripe Cloud: 1 held back, could be Stripe" in out
    assert "Synthetic" not in out


def test_connections_with_nothing_to_report(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    upload = env / "Connections.csv"
    upload.write_bytes(export(row(company="Elsewhere")))
    assert cli.main(["connections", str(upload)]) == 0
    out = capsys.readouterr().out
    assert "At tracked companies:\n  none" in out
    assert "Employer names to review:\n  none" in out


def test_connections_refuses_an_unreadable_file(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    upload = env / "Profile.csv"
    upload.write_text("Name,Headline\n")
    assert cli.main(["connections", str(upload)]) == 2
    assert "header row" in capsys.readouterr().err


@pytest.mark.usefixtures("env")
def test_run_uses_connections_only_when_an_export_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[dict[str, Any]] = []

    class StubPipeline:
        def __init__(self, *_args: Any, **kwargs: Any) -> None:
            built.append(kwargs)

        def run(self) -> Digest:
            return Digest("run-1", NOW, "SUCCESS", [])

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    assert cli.main(["run"]) == 0
    assert built[-1]["network"] is None
    monkeypatch.setenv("PEJIP_CONNECTIONS", str(ROOT / "examples" / "Connections.example.csv"))
    monkeypatch.setenv(
        "PEJIP_NETWORK_DECISIONS", str(ROOT / "examples" / "network-decisions.example.yaml")
    )
    assert cli.main(["run"]) == 0
    network = built[-1]["network"]
    assert isinstance(network, NetworkIndex)
    assert "Scale AI" in network.by_company
