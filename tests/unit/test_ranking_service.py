"""How the ranking endpoints find their key hash, database and profile (design doc 0015)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pejip import ranking_api
from pejip.config import Settings
from pejip.ranking_api import RankingService, key_hash_from_ssm
from tests.conftest import ROOT
from tests.unit.test_profile_parameter import FakeSsm

CONFIG = str(ROOT / "config" / "search.yaml")
PROFILE = str(ROOT / "examples" / "profile.example.yaml")


def test_a_fixed_hash_wins_and_is_normalised() -> None:
    service = RankingService.from_env({"PEJIP_RANKING_KEY_SHA256": " ABC "})
    assert service.expected_hash() == "abc"


def test_without_any_key_setting_there_is_no_hash() -> None:
    assert RankingService.from_env({}).expected_hash() is None


def test_the_hash_comes_from_ssm_and_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    ssm = FakeSsm(value=" DEF\n")
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _region: ssm)
    service = RankingService.from_env({"PEJIP_RANKING_KEY_PARAMETER": "/pejip/ranking-key"})
    now = [0.0]
    service.clock = lambda: now[0]
    assert service.expected_hash() == "def"
    now[0] = ranking_api.KEY_HASH_TTL_SECONDS
    assert service.expected_hash() == "def"
    assert len(ssm.calls) == 1
    now[0] = ranking_api.KEY_HASH_TTL_SECONDS + 1
    service.expected_hash()
    assert len(ssm.calls) == 2
    assert ssm.calls[0] == {"Name": "/pejip/ranking-key", "WithDecryption": True}


def test_a_missing_parameter_means_no_key_yet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ranking_api, "make_ssm_client", lambda _r: FakeSsm(error="ParameterNotFound")
    )
    assert key_hash_from_ssm("us-west-2", "/p")() is None


def test_other_ssm_errors_are_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _r: FakeSsm(error="AccessDenied"))
    with pytest.raises(Exception, match="AccessDenied"):
        key_hash_from_ssm("us-west-2", "/p")()


def test_store_only_where_a_database_is_named(tmp_path: Path) -> None:
    assert RankingService.from_env({}).store() is None
    service = RankingService.from_env({"PEJIP_DATABASE_URL": f"sqlite:///{tmp_path / 'db'}"})
    store = service.store()
    assert store is not None
    assert service.store() is store


def test_profile_from_ssm_a_file_or_nowhere(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _r: FakeSsm())
    assert RankingService.from_env({"PEJIP_PROFILE_PARAMETER": "/pejip/profile"}).profile()
    assert RankingService.from_env({"PEJIP_PROFILE": PROFILE}).profile()
    missing = str(tmp_path / "none.yaml")
    assert RankingService.from_env({"PEJIP_PROFILE": missing}).profile() is None


def test_config_is_read_from_the_configured_path() -> None:
    service = RankingService.from_env({"PEJIP_CONFIG": CONFIG})
    assert service.config().ai.max_jobs_per_run > 0


def test_ranker_setting() -> None:
    assert Settings.from_env({}).ranker == "api"
    assert Settings.from_env({"PEJIP_RANKER": " Routine "}).ranker == "routine"
    with pytest.raises(ValueError, match="PEJIP_RANKER must be one of"):
        Settings.from_env({"PEJIP_RANKER": "magic"})
    assert Settings.from_env({"PEJIP_RANKING_KEY_PARAMETER": "/k"}).ranking_key_parameter == "/k"
