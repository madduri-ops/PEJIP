"""Unit tests for per-account settings and adopting the pre-account data (design doc 0016)."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pejip import accounts
from pejip.accounts import check_account_id, fill, open_store, prepare, sqlite_path
from pejip.config import Settings


def _settings(tmp_path: Path, account: str = "babu", **extra: str) -> Settings:
    env = {
        "PEJIP_DATABASE_URL": f"sqlite:///{tmp_path}/accounts/{{account}}/pejip.db",
        "PEJIP_OUTPUT_DIR": f"{tmp_path}/accounts/{{account}}/output",
        "PEJIP_LEGACY_DATABASE_URL": f"sqlite:///{tmp_path}/pejip.db",
        "PEJIP_LEGACY_OUTPUT_DIR": f"{tmp_path}/output",
        **extra,
    }
    return Settings.from_env(env, account=account)


def _legacy_database(tmp_path: Path, value: str = "babu's row") -> Path:
    path = tmp_path / "pejip.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE t (v TEXT)")
        db.execute("INSERT INTO t VALUES (?)", (value,))
        db.commit()
    return path


def _rows(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as db:
        return [r[0] for r in db.execute("SELECT v FROM t")]


# ── Ids and places ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("account", ["babu", "friend-2", "a"])
def test_valid_account_ids(account: str) -> None:
    assert check_account_id(account) == account


@pytest.mark.parametrize("account", ["", "Babu", "1x", "../x", "a/b", "x" * 33])
def test_invalid_account_ids(account: str) -> None:
    with pytest.raises(ValueError, match="account ids"):
        check_account_id(account)


def test_fill_puts_the_account_in_every_placeholder() -> None:
    assert fill("/pejip/accounts/{account}/profile", "friend") == "/pejip/accounts/friend/profile"
    assert fill("/pejip/profile", "friend") == "/pejip/profile"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:////data/accounts/babu/pejip.db", Path("/data/accounts/babu/pejip.db")),
        ("sqlite:///pejip.db", Path("pejip.db")),
        ("sqlite:///:memory:", None),
        ("sqlite:///", None),
        ("sqlite://", None),
        ("postgresql://db/pejip", None),
    ],
)
def test_sqlite_path(url: str, expected: Path | None) -> None:
    assert sqlite_path(url) == expected


# ── Settings ─────────────────────────────────────────────────────────────────
def test_settings_fill_per_account_places() -> None:
    env = {
        "PEJIP_DATABASE_URL": "sqlite:////data/accounts/{account}/pejip.db",
        "PEJIP_OUTPUT_DIR": "/data/accounts/{account}/output",
        "PEJIP_PROFILE_PARAMETER": "/pejip/accounts/{account}/profile",
        "PEJIP_COMPANIES_PARAMETER": "/pejip/accounts/{account}/companies",
        "PEJIP_NETWORK_PREFIX": "network/{account}/",
    }

    friend = Settings.from_env(env, account="friend")

    assert friend.account == "friend"
    assert friend.database_url == "sqlite:////data/accounts/friend/pejip.db"
    assert friend.output_dir == Path("/data/accounts/friend/output")
    assert friend.profile_parameter == "/pejip/accounts/friend/profile"
    assert friend.companies_parameter == "/pejip/accounts/friend/companies"
    assert friend.network_prefix == "network/friend/"


def test_settings_default_to_babus_account_or_pejip_account() -> None:
    assert Settings.from_env({}).account == "babu"
    assert Settings.from_env({"PEJIP_ACCOUNT": "friend"}).account == "friend"
    assert Settings.from_env({"PEJIP_ACCOUNT": "friend"}, account="babu").account == "babu"
    defaults = Settings.from_env({})
    assert defaults.network_prefix == "network/"
    assert defaults.profile_parameter is None


def test_settings_refuse_a_bad_account() -> None:
    with pytest.raises(ValueError, match="account ids"):
        Settings.from_env({"PEJIP_ACCOUNT": "../babu"})


def test_only_babus_account_sees_the_legacy_data(tmp_path: Path) -> None:
    babu = _settings(tmp_path)
    friend = _settings(tmp_path, account="friend")

    assert babu.legacy_database_url == f"sqlite:///{tmp_path}/pejip.db"
    assert babu.legacy_output_dir == tmp_path / "output"
    assert friend.legacy_database_url is None
    assert friend.legacy_output_dir is None


# ── Adopting the pre-account data ────────────────────────────────────────────
def test_babus_account_adopts_a_copy_of_the_legacy_database(tmp_path: Path) -> None:
    legacy = _legacy_database(tmp_path)

    prepare(_settings(tmp_path))

    adopted = tmp_path / "accounts" / "babu" / "pejip.db"
    assert _rows(adopted) == ["babu's row"]
    assert _rows(legacy) == ["babu's row"]  # kept for a rollback
    assert [p.name for p in adopted.parent.iterdir()] == ["pejip.db"]  # no scratch left


def test_another_account_never_receives_the_legacy_database(tmp_path: Path) -> None:
    _legacy_database(tmp_path)

    prepare(_settings(tmp_path, account="friend"))

    folder = tmp_path / "accounts" / "friend"
    assert folder.is_dir()
    assert not (folder / "pejip.db").exists()


def test_an_adopted_database_is_never_overwritten(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _legacy_database(tmp_path)
    prepare(settings)
    adopted = tmp_path / "accounts" / "babu" / "pejip.db"
    with closing(sqlite3.connect(adopted)) as db:
        db.execute("INSERT INTO t VALUES ('written after adopting')")
        db.commit()

    prepare(settings)

    assert _rows(adopted) == ["babu's row", "written after adopting"]


def test_a_race_to_adopt_keeps_the_first_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _legacy_database(tmp_path)
    target = tmp_path / "accounts" / "babu" / "pejip.db"

    def lose_the_race(_source: Path, destination: Path) -> None:
        Path(destination).write_bytes(b"the other process's copy")
        raise FileExistsError

    monkeypatch.setattr(accounts.os, "link", lose_the_race)
    prepare(_settings(tmp_path))

    assert target.read_bytes() == b"the other process's copy"
    assert [p.name for p in target.parent.iterdir()] == ["pejip.db"]


def test_nothing_to_adopt_without_a_legacy_database(tmp_path: Path) -> None:
    prepare(_settings(tmp_path))

    assert not (tmp_path / "accounts" / "babu" / "pejip.db").exists()


@pytest.mark.parametrize(
    "extra",
    [
        {"PEJIP_LEGACY_DATABASE_URL": "postgresql://db/legacy"},
        {"PEJIP_DATABASE_URL": "sqlite:///{tmp}/pejip.db"},
        {"PEJIP_DATABASE_URL": "sqlite:///:memory:"},
        {"PEJIP_LEGACY_DATABASE_URL": ""},
    ],
)
def test_nothing_to_adopt_when_the_places_do_not_allow_it(
    tmp_path: Path, extra: dict[str, str]
) -> None:
    _legacy_database(tmp_path)
    filled = {k: v.replace("{tmp}", str(tmp_path)) for k, v in extra.items()}

    prepare(_settings(tmp_path, **filled))

    assert not (tmp_path / "accounts" / "babu" / "pejip.db").exists()
    assert _rows(tmp_path / "pejip.db") == ["babu's row"]


def test_babus_account_takes_over_the_legacy_digests(tmp_path: Path) -> None:
    legacy = tmp_path / "output"
    legacy.mkdir()
    old = legacy / "digest-2026-09-01.md"
    old.write_text("old digest")
    os.utime(old, (1_000_000, 1_000_000))
    (legacy / "kept-dir").mkdir()
    (legacy / "link").symlink_to(old)
    target = tmp_path / "accounts" / "babu" / "output"
    target.mkdir(parents=True)
    (target / "clash.md").write_text("account copy")
    (legacy / "clash.md").write_text("legacy copy")

    prepare(_settings(tmp_path))

    moved = target / "digest-2026-09-01.md"
    assert moved.read_text() == "old digest"
    assert moved.stat().st_mtime == 1_000_000  # the purge still deletes it on time
    assert (target / "clash.md").read_text() == "account copy"
    assert (legacy / "clash.md").exists()
    assert (legacy / "link").is_symlink()
    assert (legacy / "kept-dir").is_dir()


def test_digests_are_left_alone_without_a_distinct_legacy_folder(tmp_path: Path) -> None:
    prepare(_settings(tmp_path))  # no legacy folder on disk
    assert not (tmp_path / "accounts" / "babu" / "output").exists()

    same = str(tmp_path / "accounts" / "babu" / "output")
    prepare(_settings(tmp_path, PEJIP_LEGACY_OUTPUT_DIR=same))
    assert not Path(same).exists()


def test_open_store_gives_a_working_store_in_the_accounts_folder(tmp_path: Path) -> None:
    store = open_store(_settings(tmp_path, account="friend"))

    assert store.latest_run() is None
    store.engine.dispose()
    assert (tmp_path / "accounts" / "friend" / "pejip.db").is_file()
