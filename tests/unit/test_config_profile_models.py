from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pejip.config import SearchConfig, Settings
from pejip.models import Posting
from pejip.profile import CareerProfile, load_profile


def test_config_loads_and_validates(config: SearchConfig) -> None:
    assert config.ai.model == "claude-opus-5-5"
    assert config.ai.max_jobs_per_run == 40
    assert config.retention_days == 90
    assert sum(config.scoring.fit_weights.values()) == 100
    assert {s.adapter for s in config.sources} == {"greenhouse"}
    assert config.sources[0].company == "Anthropic"
    boards = [s.board for s in config.sources]
    assert len(boards) == len(set(boards))


def test_config_rejects_unknown_fields(config: SearchConfig) -> None:
    data = config.model_dump()
    data["surprise"] = True
    with pytest.raises(ValidationError):
        SearchConfig.model_validate(data)


@pytest.mark.parametrize("days", [0, 91])
def test_retention_can_be_shortened_but_never_lengthened(config: SearchConfig, days: int) -> None:
    data = config.model_dump()
    data["retention_days"] = days
    with pytest.raises(ValidationError):
        SearchConfig.model_validate(data)


def test_settings_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults = Settings.from_env({})
    assert defaults.config_path == Path("config/search.yaml")
    assert defaults.database_url == "sqlite:///pejip.db"
    assert defaults.ai_ledger_path == Path("pejip-ai-spend.db")
    assert (defaults.inbox_bucket, defaults.aws_region) == (None, None)
    assert (defaults.connections_path, defaults.network_decisions_path) == (None, None)
    network = Settings.from_env({"PEJIP_CONNECTIONS": "c.csv", "PEJIP_NETWORK_DECISIONS": "d.yaml"})
    assert network.connections_path == Path("c.csv")
    assert network.network_decisions_path == Path("d.yaml")
    assert defaults.network_bucket is None
    assert Settings.from_env({"PEJIP_NETWORK_BUCKET": "b"}).network_bucket == "b"
    assert (defaults.profile_parameter, defaults.digest_topic_arn) == (None, None)
    assert defaults.ai_enabled
    aws = Settings.from_env(
        {
            "PEJIP_PROFILE_PARAMETER": "/pejip/profile",
            "PEJIP_DIGEST_TOPIC_ARN": "arn:aws:sns:us-west-2:111111111111:pejip-digest",
            "PEJIP_AI_ENABLED": "False",
        }
    )
    assert aws.profile_parameter == "/pejip/profile"
    assert aws.digest_topic_arn == "arn:aws:sns:us-west-2:111111111111:pejip-digest"
    assert not aws.ai_enabled
    for value, expected in (("off", False), ("0", False), ("no", False), ("ON", True), ("1", True)):
        assert Settings.from_env({"PEJIP_AI_ENABLED": value}).ai_enabled is expected
    with pytest.raises(ValueError, match="PEJIP_AI_ENABLED must be one of"):
        Settings.from_env({"PEJIP_AI_ENABLED": "maybe"})
    inbox = Settings.from_env({"PEJIP_INBOX_BUCKET": "b", "AWS_REGION": "us-west-2"})
    assert (inbox.inbox_bucket, inbox.aws_region) == ("b", "us-west-2")
    custom = Settings.from_env(
        {
            "PEJIP_CONFIG": "c.yaml",
            "PEJIP_PROFILE": "p.yaml",
            "PEJIP_DATABASE_URL": "sqlite://",
            "PEJIP_OUTPUT_DIR": "out",
        }
    )
    assert (custom.config_path, custom.profile_path, custom.output_dir) == (
        Path("c.yaml"),
        Path("p.yaml"),
        Path("out"),
    )
    monkeypatch.setenv("PEJIP_PROFILE", "from-env.yaml")
    assert Settings.from_env().profile_path == Path("from-env.yaml")


def test_profile_ai_view_leaves_out_contact_details(profile: CareerProfile) -> None:
    view = profile.ai_view()
    assert profile.name not in view
    assert profile.email is not None
    assert profile.email not in view
    assert "E1" in view
    assert "career_direction" in view
    assert set(profile.evidence_by_id()) == {f"E{i}" for i in range(1, 9)}


def test_profile_rejects_duplicate_evidence_ids(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text(
        "name: A\nheadline: H\ntarget_seniority: [VP]\ncareer_direction: D\n"
        "evidence:\n  - {id: E1, kind: EXPERIENCE, text: a}\n  - {id: E1, kind: SCOPE, text: b}\n"
    )
    with pytest.raises(ValidationError, match="unique"):
        load_profile(path)


def test_posting_identity_and_content_hash() -> None:
    a = Posting("lever", "x:1", "Co", "VP Ops", "SF", "Body", "https://e/1")
    b = Posting("lever", "x:1", "Co", "VP Ops", "SF", "Changed body", "https://e/1")
    assert a.fingerprint == b.fingerprint
    assert a.content_hash != b.content_hash
