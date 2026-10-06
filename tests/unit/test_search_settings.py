"""Search settings saved from the portal (design doc 0017): the form, storage and use."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytest

from pejip.companies import SAVED_UNREADABLE, apply_saved, load_search_config
from pejip.config import Settings, load_config
from pejip.search_settings import (
    MAX_TERM_CHARS,
    MAX_TERMS,
    SavedSettings,
    SettingsError,
    SettingsForm,
    current,
    with_saved,
)
from pejip.store import Store
from tests.conftest import NOW, ROOT
from tests.unit.test_profile_parameter import FakeSsm

CONFIG = load_config(ROOT / "config" / "search.yaml")
SCOPES = list(CONFIG.geography.scopes)


def _fields(**changes: str) -> dict[str, list[str]]:
    fields = {
        "seniority_patterns": "vice president\nhead of",
        "role_terms": "operations",
        "excluded_title_patterns": "",
        "places.BAY_AREA": "oakland",
        "preference.BAY_AREA": "PREFERRED",
        "places.US_REMOTE": "",
        "preference.US_REMOTE": "ACCEPTABLE",
        "hard_filter": "on",
    }
    fields.update(changes)
    return {key: [value] for key, value in fields.items()}


def test_the_shipped_settings_round_trip_through_the_form() -> None:
    saved = SettingsForm.of(current(CONFIG)).parse()
    assert saved == current(CONFIG)
    assert with_saved(CONFIG, saved) == CONFIG


def test_a_posted_form_is_cleaned_up() -> None:
    fields = _fields(
        seniority_patterns="  Vice   President \n\nHEAD OF, chief\nvice president",
        excluded_title_patterns="intern",
    )
    saved = SettingsForm.posted(fields, SCOPES).parse()

    assert saved.taxonomy.seniority_patterns == ["vice president", "head of", "chief"]
    assert saved.taxonomy.excluded_title_patterns == ["intern"]
    assert saved.geography.scopes["BAY_AREA"].places == ["oakland"]
    assert saved.geography.scopes["US_REMOTE"].places == []
    assert saved.geography.hard_filter is True


def test_only_the_offered_locations_are_read_and_the_box_can_be_cleared() -> None:
    fields = _fields(**{"places.MARS": "olympus mons", "preference.MARS": "PREFERRED"})
    del fields["hard_filter"]
    saved = SettingsForm.posted(fields, ["BAY_AREA"]).parse()
    assert list(saved.geography.scopes) == ["BAY_AREA"]
    assert saved.geography.hard_filter is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"seniority_patterns": " \n "}, "Seniority a title needs: enter at least one"),
        ({"role_terms": ""}, "Role words a title needs: enter at least one"),
        (
            {"role_terms": "\n".join(f"term{n}" for n in range(MAX_TERMS + 1))},
            f"at most {MAX_TERMS} entries",
        ),
        ({"role_terms": "a" * (MAX_TERM_CHARS + 1)}, "can't be used"),
        ({"excluded_title_patterns": "<script>"}, "Titles always left out: “<script>”"),
        ({"places.BAY_AREA": "-oakland"}, "Places for Bay Area"),
        ({"preference.US_REMOTE": "SOMETIMES"}, "Choose a preference for Us Remote"),
    ],
)
def test_bad_values_are_refused_with_the_field_named(changes: dict[str, str], message: str) -> None:
    with pytest.raises(SettingsError, match=message):
        SettingsForm.posted(_fields(**changes), SCOPES).parse()


def test_messages_use_the_pages_names_for_locations() -> None:
    form = SettingsForm.posted(_fields(**{"preference.BAY_AREA": ""}), SCOPES)
    with pytest.raises(SettingsError, match="Choose a preference for San Francisco Bay Area"):
        form.parse({"BAY_AREA": "San Francisco Bay Area"})


def test_the_store_keeps_only_the_latest_save_until_reset(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'p.db'}")
    assert store.saved_search_settings() is None

    first = current(CONFIG).model_dump()
    store.save_search_settings(first, NOW)
    second = {**first, "geography": {"hard_filter": False, "scopes": {}}}
    store.save_search_settings(second, NOW)

    assert store.saved_search_settings() == (second, NOW)
    assert '"search_settings"' in store.export_all()
    store.save_search_settings(None, NOW)
    assert store.saved_search_settings() is None


def test_saved_times_come_back_in_utc(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'p.db'}")
    store.save_search_settings({}, datetime(2026, 10, 6, 15, 0))  # noqa: DTZ001 - as SQLite returns
    saved = store.saved_search_settings()
    assert saved is not None
    assert saved[1] == datetime.fromisoformat("2026-10-06T15:00:00+00:00")


def _saved_store(tmp_path: Path, saved: SavedSettings | dict[str, object]) -> Store:
    store = Store(f"sqlite:///{tmp_path / 'p.db'}")
    value = saved.model_dump() if isinstance(saved, SavedSettings) else saved
    store.save_search_settings(value, NOW)
    return store


def test_saved_settings_replace_the_shipped_ones(tmp_path: Path) -> None:
    mine = SettingsForm.posted(_fields(role_terms="privacy"), SCOPES).parse()
    config, note = apply_saved(CONFIG, _saved_store(tmp_path, mine))
    assert config.taxonomy.role_terms == ["privacy"]
    assert config.scoring == CONFIG.scoring
    assert note is None
    assert apply_saved(CONFIG, None) == (CONFIG, None)


def test_unreadable_saved_settings_fall_back_and_say_so(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _saved_store(tmp_path, {"taxonomy": "secret words"})
    with caplog.at_level(logging.WARNING):
        config, note = apply_saved(CONFIG, store)
    assert config == CONFIG
    assert note == SAVED_UNREADABLE
    assert [r.getMessage() for r in caplog.records] == ["saved_settings_unreadable"]
    assert "secret words" not in caplog.text


def test_the_run_notes_both_a_missing_company_list_and_unreadable_settings(
    tmp_path: Path,
) -> None:
    settings = Settings.from_env(
        {
            "PEJIP_CONFIG": str(ROOT / "config" / "search.yaml"),
            "PEJIP_COMPANIES_PARAMETER": "/pejip/accounts/{account}/companies",
        }
    )
    store = _saved_store(tmp_path, {"taxonomy": {}})
    _, note = load_search_config(settings, lambda _r: FakeSsm(error="ParameterNotFound"), store)
    assert note is not None
    assert note.startswith("Your company list is not stored yet")
    assert note.endswith(SAVED_UNREADABLE)
