from __future__ import annotations

import json
import os
import runpy
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest

from pejip import cli
from pejip.config import Settings
from pejip.digest import Digest
from pejip.models import Posting
from pejip.store import Store
from tests.conftest import NOW, ROOT
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


@pytest.mark.usefixtures("env")
def test_with_the_routine_the_run_defers_the_email(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    RecordingPipeline.built.clear()
    sns = FakeSns()
    monkeypatch.setattr(cli, "Pipeline", RecordingPipeline)
    monkeypatch.setattr(cli, "make_sns_client", lambda _r: sns)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setenv("PEJIP_RANKER", "routine")
    monkeypatch.setenv("PEJIP_DIGEST_TOPIC_ARN", "arn:aws:sns:us-west-2:111111111111:pejip-digest")
    with caplog.at_level("INFO", logger="pejip"):
        assert cli.main(["run"]) == 0
    args, kwargs = RecordingPipeline.built[-1]
    assert args[3] is None  # the routine does the model step, not the API
    assert kwargs["routine"] is True
    assert kwargs["unranked_reason"] == cli.ROUTINE_PENDING
    assert sns.calls == []
    assert "digest_deferred" in [r.getMessage() for r in caplog.records]


def test_routine_reason_without_a_profile() -> None:
    settings = Settings.from_env({"PEJIP_RANKER": "routine", "PEJIP_PROFILE_PARAMETER": "/p"})
    assert cli._unranked_reason(settings, None) == (
        "no career profile is stored yet (SSM parameter /p)"
    )


@pytest.mark.usefixtures("env")
def test_digest_needs_a_finished_run(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    with caplog.at_level("ERROR", logger="pejip"):
        assert cli.main(["digest"]) == 1
    assert "digest_without_run" in [r.getMessage() for r in caplog.records]


def _finished_run(env: Path, seen: list[list[Any]], started: datetime | None = None) -> Store:
    # The digest checks the run's age against the real clock.
    started = started or datetime.now(UTC)
    store = Store(f"sqlite:///{env / 'cli.db'}")
    store.start_run("r1", started)
    summary = {"sources": [{"name": "A", "status": "OK"}], "seen": seen, "notes": ["n"]}
    store.finish_run("r1", "PARTIAL", summary, started)
    return store


def test_digest_emails_the_latest_run_ranked_again(
    env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _finished_run(env, [])
    sns = FakeSns()
    monkeypatch.setattr(cli, "make_sns_client", lambda _r: sns)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setenv("PEJIP_RANKER", "routine")
    monkeypatch.setenv("PEJIP_DIGEST_TOPIC_ARN", "arn:aws:sns:us-west-2:111111111111:pejip-digest")
    with caplog.at_level("INFO", logger="pejip"):
        assert cli.main(["digest"]) == 0
    [call] = sns.calls
    assert "finished **SUCCESS**" in call["Message"]
    assert "routine_results_missing" not in [r.getMessage() for r in caplog.records]
    assert len(list((env / "out").glob("digest-*.md"))) == 1


def test_digest_says_when_the_routine_did_not_report(
    env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    store = _finished_run(env, [])
    posting = Posting(
        source="greenhouse",
        source_job_id="1",
        company="Example Co",
        title="VP Technology Operations",
        location="Remote",
        description="Lead technology operations.",
        url="https://example.test/1",
    )
    now = datetime.now(UTC)
    job_id = store.upsert_job(posting, now).job_id
    store.finish_run(
        "r1", "PARTIAL", {"sources": [], "seen": [[job_id, "NEW_POSTING"]], "notes": []}, now
    )
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setenv("PEJIP_RANKER", "routine")
    with caplog.at_level("INFO", logger="pejip"):
        assert cli.main(["digest"]) == 0
    missing = [r for r in caplog.records if r.getMessage() == "routine_results_missing"]
    assert missing[0].levelname == "ERROR"
    [written] = (env / "out").glob("digest-*.md")
    assert "The ranking routine did not report" in written.read_text()


def test_digest_of_a_stale_run_says_so_and_alarms(
    env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    started = datetime.now(UTC) - timedelta(hours=cli.STALE_RUN_HOURS + 1)
    _finished_run(env, [], started)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setenv("PEJIP_RANKER", "routine")
    with caplog.at_level("INFO", logger="pejip"):
        assert cli.main(["digest"]) == 0
    stale = [r for r in caplog.records if r.getMessage() == "digest_run_stale"]
    assert stale[0].levelname == "ERROR"
    [written] = (env / "out").glob("digest-*.md")
    assert "No search has finished since" in written.read_text()


def test_a_crashing_digest_logs_an_error(
    env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _finished_run(env, [])

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise ConnectionError

    monkeypatch.setattr(cli, "_deliver", broken)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    with caplog.at_level("ERROR", logger="pejip"), pytest.raises(ConnectionError):
        cli.main(["digest"])
    assert "digest_crashed" in [r.getMessage() for r in caplog.records]
