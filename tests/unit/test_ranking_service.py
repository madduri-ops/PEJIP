"""How the ranking endpoints find their key hash, database and profile (design doc 0015)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from pejip import ranking_api
from pejip.config import Settings
from pejip.ranking_api import (
    KeyRequiredError,
    NotConfiguredError,
    RankingService,
    RankingServices,
    key_hash_from_ssm,
)
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


# ── One key per account (design doc 0016) ────────────────────────────────────
class ParamSsm:
    """SSM holding only the named parameters; any other is not found."""

    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.calls: list[str] = []

    def get_parameter(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs["Name"])
        if kwargs["Name"] not in self.values:
            return FakeSsm(error="ParameterNotFound").get_parameter(**kwargs)
        return {"Parameter": {"Name": kwargs["Name"], "Value": self.values[kwargs["Name"]]}}


def test_babus_account_falls_back_to_the_key_from_before_accounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ssm = ParamSsm({"/pejip/ranking-key-sha256": "OLD"})
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _r: ssm)
    env = {
        "PEJIP_RANKING_KEY_PARAMETER": "/pejip/accounts/{account}/ranking-key-sha256",
        "PEJIP_LEGACY_RANKING_KEY_PARAMETER": "/pejip/ranking-key-sha256",
    }

    assert RankingService.from_env(env).expected_hash() == "old"
    assert ssm.calls == ["/pejip/accounts/babu/ranking-key-sha256", "/pejip/ranking-key-sha256"]
    # Another account never borrows Babu's key.
    assert RankingService.from_env(env, "friend").expected_hash() is None

    ssm.values["/pejip/accounts/babu/ranking-key-sha256"] = "NEW"
    assert RankingService.from_env(env).expected_hash() == "new"


def test_a_fixed_hash_is_babus_alone() -> None:
    env = {"PEJIP_RANKING_KEY_SHA256": "abc"}
    assert RankingService.from_env(env, "friend").expected_hash() is None


def _keyed(key_hash: str | None, name: str) -> RankingService:
    return RankingService(lambda: key_hash, lambda: None, lambda: None, lambda: name)  # type: ignore[arg-type,return-value]


KEY_A, KEY_B = "a" * 40, "b" * 40


def _sha(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def test_the_key_picks_its_own_account() -> None:
    services = RankingServices(
        {"babu": _keyed(_sha(KEY_A), "babu"), "friend": _keyed(_sha(KEY_B), "friend")}
    )

    assert services.for_key(f"Bearer {KEY_A}") is services.by_account["babu"]
    assert services.for_key(f"bearer {KEY_B}") is services.by_account["friend"]
    with pytest.raises(KeyRequiredError):
        services.for_key(f"Bearer {'c' * 40}")
    with pytest.raises(KeyRequiredError):
        services.for_key("Bearer short")


def test_an_account_without_a_key_yet_is_skipped() -> None:
    services = RankingServices(
        {"babu": _keyed(None, "babu"), "friend": _keyed(_sha(KEY_B), "friend")}
    )

    assert services.for_key(f"Bearer {KEY_B}") is services.by_account["friend"]
    with pytest.raises(NotConfiguredError):
        RankingServices({"babu": _keyed(None, "babu")}).for_key(f"Bearer {KEY_A}")


def test_services_are_built_for_every_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _r: ParamSsm({}))
    env = {"PEJIP_ACCOUNTS": "babu,friend", "PEJIP_RANKING_KEY_PARAMETER": "/k/{account}"}

    services = RankingServices.from_env(env)

    assert list(services.by_account) == ["babu", "friend"]


def test_key_hash_from_ssm_reads_names_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ssm = ParamSsm({"/second": "TWO"})
    monkeypatch.setattr(ranking_api, "make_ssm_client", lambda _r: ssm)

    assert key_hash_from_ssm(None, "/first", "/second")() == "two"
    assert key_hash_from_ssm(None, "/first")() is None
