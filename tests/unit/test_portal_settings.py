"""The editable Settings page (design doc 0017). All data is synthetic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI

from pejip import portal
from pejip.config import SearchConfig
from pejip.portal import MAX_SETTINGS_BYTES
from pejip.search_settings import SavedSettings, current
from tests.unit.test_portal import CONFIG, NOW, FakeData

FORM = "application/x-www-form-urlencoded"


class FakeSettings:
    """Records saves; ``saved_at`` is what the page is told."""

    def __init__(self, saved_at: datetime | None = None) -> None:
        self._saved_at = saved_at
        self.saves: list[tuple[str, SavedSettings | None]] = []

    def saved_at(self, account: str) -> datetime | None:
        assert account == "babu"
        return self._saved_at

    def save(self, account: str, saved: SavedSettings | None) -> None:
        self.saves.append((account, saved))


def _app(settings: FakeSettings | None, config: SearchConfig | None = CONFIG) -> FastAPI:
    app = FastAPI()
    app.include_router(
        portal.router(
            FakeData([], None), clock=lambda: NOW, config=config, search_settings=settings
        )
    )
    return app


def _call(app: FastAPI, method: str, path: str, **kwargs: object) -> httpx.Response:
    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            return await client.request(method, path, **kwargs)  # type: ignore[arg-type]

    return asyncio.run(call())


def _post(
    app: FastAPI, fields: dict[str, str], origin: str | None = "https://test"
) -> httpx.Response:
    headers = {"content-type": FORM, **({"origin": origin} if origin else {})}
    return _call(app, "POST", "/settings", content=urlencode(fields), headers=headers)


def _fields(**changes: str) -> dict[str, str]:
    return {
        "seniority_patterns": "vice president\nhead of",
        "role_terms": "operations\nprivacy",
        "excluded_title_patterns": "intern",
        "places.BAY_AREA": "oakland\nsan jose",
        "preference.BAY_AREA": "PREFERRED",
        "places.US_REMOTE": "",
        "preference.US_REMOTE": "ACCEPTABLE",
        "hard_filter": "on",
        **changes,
    }


def test_the_page_offers_the_current_settings_as_a_form() -> None:
    html = _call(_app(FakeSettings()), "GET", "/settings").text

    assert '<form method="post" action="/settings" id="edit">' in html
    assert '<label for="seniority_patterns">Words that make a title senior</label>' in html
    assert "vice president\nhead of\n" in html
    assert '<option value="PREFERRED" selected>Preferred</option>' in html
    assert "<legend>San Francisco Bay Area</legend>" in html
    assert "Remote roles in the US count here too." in html
    assert 'name="hard_filter" checked>' in html
    assert "Using the default settings." in html
    assert "Go back to the defaults" not in html
    assert "read-only here" not in html
    assert f"Scoring version {CONFIG.scoring.version}." in html  # still shown, read-only


def test_after_a_save_the_page_says_when_and_offers_the_defaults() -> None:
    saved_at = datetime(2026, 10, 6, 15, 5, tzinfo=UTC)  # 8:05 AM PDT
    app = _app(FakeSettings(saved_at))

    html = _call(app, "GET", "/settings").text
    assert "Your settings, saved Oct 6, 8:05 AM PDT." in html
    assert '<input type="hidden" name="action" value="reset">' in html

    just = _call(app, "GET", "/settings?saved=1").text
    assert "Saved. The next search, ranking and digest use these settings." in just


def test_after_a_reset_the_page_says_the_defaults_are_back() -> None:
    html = _call(_app(FakeSettings()), "GET", "/settings?saved=1").text
    assert "Back to the default settings. The next search uses them." in html


def test_without_somewhere_to_save_the_page_stays_read_only() -> None:
    html = _call(_app(None), "GET", "/settings").text
    assert "These settings are read-only here" in html
    assert 'id="edit"' not in html


def test_a_save_keeps_the_cleaned_up_values() -> None:
    settings = FakeSettings()
    response = _post(_app(settings), _fields(role_terms="Operations\nprivacy, Trust"))

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?saved=1"
    [(account, saved)] = settings.saves
    assert account == "babu"
    assert saved is not None
    assert saved.taxonomy.role_terms == ["operations", "privacy", "trust"]
    assert saved.geography.scopes["BAY_AREA"].places == ["oakland", "san jose"]


def test_going_back_to_the_defaults_clears_the_save() -> None:
    settings = FakeSettings(NOW)
    response = _post(_app(settings), {"action": "reset"})
    assert response.status_code == 303
    assert settings.saves == [("babu", None)]


def test_a_refused_save_shows_what_was_typed_and_why() -> None:
    settings = FakeSettings()
    response = _post(_app(settings), _fields(role_terms="", excluded_title_patterns="<b>x</b>"))

    assert response.status_code == 422
    assert "Not saved. Role words a title needs: enter at least one" in response.text
    assert "&lt;b&gt;x&lt;/b&gt;</textarea>" in response.text
    assert "<b>x</b>" not in response.text
    assert settings.saves == []


def test_forms_from_other_sites_are_refused() -> None:
    settings = FakeSettings()
    app = _app(settings)
    assert _post(app, _fields(), origin="https://evil.example").status_code == 403
    assert _post(app, _fields(), origin=None).status_code == 403
    assert settings.saves == []


def test_saving_needs_somewhere_to_save_and_a_configuration() -> None:
    assert _post(_app(None), _fields()).status_code == 404
    assert _post(_app(FakeSettings(), config=None), _fields()).status_code == 404


def test_an_oversized_form_is_refused() -> None:
    settings = FakeSettings()
    big = _fields(role_terms="a" * MAX_SETTINGS_BYTES)
    assert _post(_app(settings), big).status_code == 413
    assert settings.saves == []


def test_the_form_round_trips_the_shipped_settings() -> None:
    settings = FakeSettings()
    app = _app(settings)
    # What the page would send unchanged.
    fields = _fields(
        seniority_patterns="\n".join(CONFIG.taxonomy.seniority_patterns),
        role_terms="\n".join(CONFIG.taxonomy.role_terms),
        excluded_title_patterns="\n".join(CONFIG.taxonomy.excluded_title_patterns),
        **{"places.BAY_AREA": "\n".join(CONFIG.geography.scopes["BAY_AREA"].places)},
    )
    assert _post(app, fields).status_code == 303
    assert settings.saves[0][1] == current(CONFIG)


def test_the_page_describes_the_current_schedule_ranking_and_privacy() -> None:
    html = _call(_app(None), "GET", "/settings").text

    assert "Weekdays at 5 AM, 10 AM and 3 PM Pacific" in html
    assert "when it came from one of your job alerts" in html
    assert "<h3>Words that never count as senior</h3>" in html
    assert "As soon as ranking finishes; otherwise at 7 AM, 12 PM and 5 PM Pacific" in html
    assert "AI spending cap" not in html
    assert "Pay against your profile&#x27;s minimum" in html
    assert "Immediate also needs a role posted in the last 3 days." in html
    assert "A matured connection at the company adds 10 Priority points." in html
    assert "Otherwise, any first-degree connection there adds 3 Priority points." in html
    assert "Only for roles with Fit 60 or more" in html
    assert "Fit 75 or more, is flagged in the digest as your call." in html
    assert "saved search settings until you change them" in html
    assert "your own email address and have your mailbox forward them" in html


def test_without_a_network_boost_the_page_leaves_the_network_out() -> None:
    scoring = CONFIG.scoring.model_copy(update={"network_priority_boost": {}})
    html = _call(_app(None, CONFIG.model_copy(update={"scoring": scoring})), "GET", "/settings")
    assert "Your network" not in html.text
