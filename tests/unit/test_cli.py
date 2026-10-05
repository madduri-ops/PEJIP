from __future__ import annotations

import json
import os
import runpy
import shutil
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

from pejip import cli
from pejip.config import Settings
from pejip.digest import Digest
from pejip.network.matching import NetworkIndex
from pejip.store import Store
from tests.conftest import NOW, ROOT
from tests.linkedin import export, row
from tests.unit.test_delivery import FakeSns
from tests.unit.test_profile_parameter import FakeSsm


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


@pytest.mark.parametrize(
    "case",
    [
        ("missing.csv", None, "a network file could not be opened (FileNotFoundError)"),
        ("bad.csv", None, "the LinkedIn export could not be read (no 'First Name,"),
        ("good.csv", "missing.yaml", "a network file could not be opened"),
        ("good.csv", "bad.yaml", "the network decisions file has an invalid entry"),
    ],
)
def test_a_bad_network_file_is_noted_and_never_stops_the_run(
    env: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    case: tuple[str, str | None, str],
) -> None:
    connections, decisions, problem = case
    (env / "bad.csv").write_text("Name,Headline\nAvery Secretname,VP\n")
    (env / "good.csv").write_bytes(export(row()))
    (env / "bad.yaml").write_text(
        "titles: [{company: A, position: Secret Title, role_level: KING, matured: true}]\n"
    )
    built: list[dict[str, Any]] = []

    class StubPipeline:
        def __init__(self, *_args: Any, **kwargs: Any) -> None:
            built.append(kwargs)

        def run(self) -> Digest:
            return Digest("run-1", NOW, "SUCCESS", [])

    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    monkeypatch.setenv("PEJIP_CONNECTIONS", str(env / connections))
    if decisions:
        monkeypatch.setenv("PEJIP_NETWORK_DECISIONS", str(env / decisions))
    assert cli.main(["run"]) == 0
    assert built[-1]["network"] is None
    [digest] = list((env / "out").glob("digest-*.md"))
    assert f"Connections were not used this run: {problem}" in digest.read_text()
    logged = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    assert "Secret" not in logged


def test_connections_refuses_a_missing_file(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["connections", str(env / "absent.csv")]) == 2
    assert "could not be opened" in capsys.readouterr().err


class RecordingPipeline:
    """Stands in for Pipeline and records what the CLI built it with."""

    built: ClassVar[list[tuple[tuple[Any, ...], dict[str, Any]]]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        RecordingPipeline.built.append((args, kwargs))

    def run(self) -> Digest:
        return Digest("run-1", NOW, "SUCCESS", [])


@pytest.mark.usefixtures("env")
def test_on_aws_the_profile_comes_from_ssm_and_the_digest_is_emailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    RecordingPipeline.built.clear()
    sns = FakeSns()
    regions: list[str | None] = []

    def fake_ssm(region: str | None) -> FakeSsm:
        regions.append(region)
        return FakeSsm()

    def fake_sns(region: str | None) -> FakeSns:
        regions.append(region)
        return sns

    monkeypatch.setattr(cli, "Pipeline", RecordingPipeline)
    monkeypatch.setattr(cli, "make_ssm_client", fake_ssm)
    monkeypatch.setattr(cli, "make_sns_client", fake_sns)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("PEJIP_PROFILE_PARAMETER", "/pejip/profile")
    monkeypatch.setenv("PEJIP_DIGEST_TOPIC_ARN", "arn:aws:sns:us-west-2:111111111111:pejip-digest")
    assert cli.main(["run"]) == 0

    args, _kwargs = RecordingPipeline.built[-1]
    assert args[1] is not None  # the profile
    assert args[3] is not None  # the AI client
    assert regions == ["us-west-2", "us-west-2"]
    [call] = sns.calls
    assert call["TopicArn"].endswith(":pejip-digest")
    assert call["Subject"].startswith("PEJIP digest 2026-10-05")
    assert "finished **SUCCESS**" in call["Message"]


@pytest.mark.usefixtures("env")
def test_without_a_stored_profile_or_claude_the_run_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    RecordingPipeline.built.clear()
    monkeypatch.setattr(cli, "Pipeline", RecordingPipeline)
    monkeypatch.setattr(cli, "make_ssm_client", lambda _r: FakeSsm(error="ParameterNotFound"))
    monkeypatch.setenv("PEJIP_PROFILE_PARAMETER", "/pejip/profile")
    assert cli.main(["run"]) == 0
    args, kwargs = RecordingPipeline.built[-1]
    assert args[1] is None
    assert kwargs["unranked_reason"] == (
        "no career profile is stored yet (SSM parameter /pejip/profile)"
    )

    monkeypatch.setenv("PEJIP_AI_ENABLED", "false")
    assert cli.main(["run"]) == 0
    _args, kwargs = RecordingPipeline.built[-1]
    assert kwargs["unranked_reason"] == (
        "no career profile is stored yet (SSM parameter /pejip/profile)"
        " and Claude access is not set up for this workload yet"
    )

    monkeypatch.delenv("PEJIP_PROFILE_PARAMETER")
    monkeypatch.setenv("PEJIP_AI_ENABLED", "false")
    assert cli.main(["run"]) == 0
    args, kwargs = RecordingPipeline.built[-1]
    assert args[1] is not None
    assert args[3] is None
    assert kwargs["unranked_reason"] == "Claude access is not set up for this workload yet"


@pytest.mark.usefixtures("env")
def test_a_crashed_run_logs_an_error_and_reraises(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class CrashingPipeline:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def run(self) -> Digest:
            raise RuntimeError("boom")

    monkeypatch.setattr(cli, "Pipeline", CrashingPipeline)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    with caplog.at_level("ERROR", logger="pejip"), pytest.raises(RuntimeError):
        cli.main(["run"])
    crashed = [r for r in caplog.records if r.getMessage() == "run_crashed"]
    assert len(crashed) == 1
    assert crashed[0].levelname == "ERROR"
    assert crashed[0].exc_info is not None


def test_unranked_reason_has_a_fallback() -> None:
    settings = Settings.from_env({})
    assert cli._unranked_reason(settings, object()) == "ranking is not set up"  # type: ignore[arg-type]


def test_a_failed_digest_email_still_purges_old_digests(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class SendFailedError(Exception):
        pass

    class FailingSns:
        def publish(self, **_kwargs: Any) -> dict[str, Any]:
            raise SendFailedError

    monkeypatch.setattr(cli, "Pipeline", RecordingPipeline)
    monkeypatch.setattr(cli, "make_sns_client", lambda _r: FailingSns())
    monkeypatch.setenv("PEJIP_DIGEST_TOPIC_ARN", "arn:aws:sns:us-west-2:111111111111:pejip-digest")
    out = env / "out"
    out.mkdir()
    old = out / "digest-old.md"
    old.write_text("old")
    hundred_days_ago = time.time() - 100 * 86400
    os.utime(old, (hundred_days_ago, hundred_days_ago))
    with pytest.raises(SendFailedError):
        cli.main(["run"])
    assert not old.exists()
