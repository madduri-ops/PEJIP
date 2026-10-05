from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pejip.config import SearchConfig, Settings
from pejip.models import Posting
from pejip.profile import CareerProfile, load_profile


def test_config_loads_and_validates(config: SearchConfig) -> None:
    assert config.ai.model == "claude-opus-5-5"
    assert config.ai.monthly_cap_usd == 100.0
    assert config.retention_days == 90
    assert sum(config.scoring.fit_weights.values()) == 100
    assert {s.adapter for s in config.sources} == {"greenhouse", "lever"}


def test_config_rejects_unknown_fields(config: SearchConfig) -> None:
    data = config.model_dump()
    data["surprise"] = True
    with pytest.raises(ValidationError):
        SearchConfig.model_validate(data)


def test_settings_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults = Settings.from_env({})
    assert defaults.config_path == Path("config/search.yaml")
    assert defaults.database_url == "sqlite:///pejip.db"
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
    assert profile.email is not None and profile.email not in view
    assert "E1" in view and "career_direction" in view
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
