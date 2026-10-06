"""Unit tests for the HTTP surface."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request

from ci.alb_token import AlbSigner
from pejip import __version__, api
from pejip.auth import OIDC_DATA_HEADER
from pejip.portal.data import Company, Opportunity, SearchRun
from tests.alb import ACCOUNT_ID, ALB_ARN, ALLOWED_EMAIL, auth_env, key_server
from tests.unit.test_profile_parameter import FakeSsm


class Client:
    """Calls the app in process through httpx's ASGI transport, with no network."""

    def get(self, path: str) -> httpx.Response:
        return asyncio.run(self._get(path))

    async def _get(self, path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=api.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)


@pytest.fixture
def client() -> Client:
    return Client()


def test_healthz_reports_ok_and_version(client: Client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_every_response_carries_security_headers(client: Client) -> None:
    for path in ("/healthz", "/no-such-path"):
        headers = client.get(path).headers
        for name, value in api.SECURITY_HEADERS.items():
            assert headers[name] == value


def test_html_pages_get_the_page_policy(signer: AlbSigner) -> None:
    with key_server(signer) as key_url:
        app = api.create_app(env=auth_env(key_url))
        response = _get(app, "/", signer.token(ALLOWED_EMAIL))

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == api.PAGE_CSP
    assert "script-src" not in api.PAGE_CSP
    assert "unsafe-inline" not in api.PAGE_CSP
    assert response.headers["X-Frame-Options"] == "DENY"


def test_portal_reads_the_data_it_is_given(signer: AlbSigner) -> None:
    class NoData:
        is_sample = False

        def latest_run(self) -> None:
            return None

        def recent_runs(self) -> list[SearchRun]:
            return []

        def companies(self) -> list[Company]:
            return []

        def opportunities(self) -> list[Opportunity]:
            return []

        def network(self) -> None:
            return None

    with key_server(signer) as key_url:
        app = api.create_app(env=auth_env(key_url), data=NoData())
        html = _get(app, "/", signer.token(ALLOWED_EMAIL)).text

    assert "Sample data" not in html
    assert "No search has run yet" in html


def test_main_binds_to_localhost_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.delenv("PEJIP_HOST", raising=False)
    monkeypatch.delenv("PEJIP_PORT", raising=False)
    monkeypatch.setattr("uvicorn.run", lambda _app, **kwargs: calls.append(kwargs))

    api.main()

    assert calls == [{"host": "127.0.0.1", "port": 8000, "server_header": False}]


def test_main_reads_host_and_port_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("PEJIP_HOST", "0.0.0.0")  # noqa: S104 - container bind, test only
    monkeypatch.setenv("PEJIP_PORT", "9000")
    monkeypatch.setattr("uvicorn.run", lambda _app, **kwargs: calls.append(kwargs))

    api.main()

    assert calls == [{"host": "0.0.0.0", "port": 9000, "server_header": False}]  # noqa: S104


# ── Sign-in (ADR-0006) ───────────────────────────────────────────────────────
def _get(app: FastAPI, path: str, token: str | None = None) -> httpx.Response:
    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {OIDC_DATA_HEADER: token} if token else {}
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(call())


def test_protected_routes_fail_closed_without_sign_in_settings() -> None:
    app = api.create_app(env={})

    assert _get(app, "/healthz").status_code == 200
    response = _get(app, "/openapi.json")
    assert response.status_code == 503
    assert response.json() == {"detail": "sign-in is not configured"}


@pytest.fixture
def signer() -> AlbSigner:
    return AlbSigner(ALB_ARN)


@pytest.fixture
def signed_in_app(signer: AlbSigner) -> Iterator[FastAPI]:
    with key_server(signer) as key_url:
        yield api.create_app(env=auth_env(key_url))


def test_healthz_needs_no_sign_in(signed_in_app: FastAPI) -> None:
    assert _get(signed_in_app, "/healthz").status_code == 200


def test_protected_route_needs_a_token(signed_in_app: FastAPI) -> None:
    response = _get(signed_in_app, "/openapi.json")

    assert response.status_code == 401
    assert response.json() == {"detail": "sign-in required"}
    for name, value in api.SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_protected_route_refuses_another_account(signed_in_app: FastAPI, signer: AlbSigner) -> None:
    response = _get(signed_in_app, "/openapi.json", signer.token("someone@example.com"))

    assert response.status_code == 403
    assert response.json() == {"detail": "this account is not allowed"}


def test_protected_route_serves_the_allowed_account(
    signed_in_app: FastAPI, signer: AlbSigner
) -> None:
    response = _get(signed_in_app, "/openapi.json", signer.token(ALLOWED_EMAIL))

    assert response.status_code == 200
    assert "/healthz" in response.json()["paths"]


def test_routes_see_the_signed_in_account(signed_in_app: FastAPI, signer: AlbSigner) -> None:
    # Later routes key every read and write by this account (design doc 0016).
    @signed_in_app.get("/whoami-test")
    def whoami(request: Request) -> dict[str, str]:
        return {"account": request.state.account.id}

    response = _get(signed_in_app, "/whoami-test", signer.token(ALLOWED_EMAIL))

    assert response.json() == {"account": ACCOUNT_ID}


def test_interactive_docs_are_disabled(signed_in_app: FastAPI, signer: AlbSigner) -> None:
    token = signer.token(ALLOWED_EMAIL)

    assert _get(signed_in_app, "/docs", token).status_code == 404
    assert _get(signed_in_app, "/redoc", token).status_code == 404


def test_settings_page_reads_the_search_configuration(signer: AlbSigner, tmp_path: Path) -> None:
    with key_server(signer) as key_url:
        token = signer.token(ALLOWED_EMAIL)
        default = _get(api.create_app(env=auth_env(key_url)), "/settings", token).text
        missing = {**auth_env(key_url), "PEJIP_CONFIG": str(tmp_path / "absent.yaml")}
        absent = _get(api.create_app(env=missing), "/settings", token).text

    assert "Seniority a title needs" in default
    assert "The search configuration is not available on this server." in absent


EXAMPLE_COMPANIES = Path("examples/companies.example.yaml").read_text()


def test_settings_page_adds_the_private_companies(
    signer: AlbSigner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    companies = tmp_path / "companies.yaml"
    companies.write_text(EXAMPLE_COMPANIES)
    ssm = FakeSsm(value=EXAMPLE_COMPANIES)
    monkeypatch.setattr(api, "make_ssm_client", lambda _region: ssm)
    with key_server(signer) as key_url:
        token = signer.token(ALLOWED_EMAIL)
        from_file = {**auth_env(key_url), "PEJIP_COMPANIES": str(companies)}
        local = _get(api.create_app(env=from_file), "/settings", token).text
        from_ssm = {**auth_env(key_url), "PEJIP_COMPANIES_PARAMETER": "/pejip/companies"}
        aws = _get(api.create_app(env=from_ssm), "/settings", token).text

    assert "<h3>Northwind Robotics</h3>" in local
    assert "<h3>Contoso Silicon</h3>" in aws
    assert ssm.calls == [{"Name": "/pejip/companies", "WithDecryption": True}]


def test_settings_page_opens_without_a_readable_company_list(
    signer: AlbSigner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "companies.yaml"
    broken.write_text("sources: [")
    monkeypatch.setattr(api, "make_ssm_client", lambda _region: FakeSsm(error="AccessDenied"))
    with key_server(signer) as key_url:
        token = signer.token(ALLOWED_EMAIL)
        bad_file = {**auth_env(key_url), "PEJIP_COMPANIES": str(broken)}
        denied = {**auth_env(key_url), "PEJIP_COMPANIES_PARAMETER": "/pejip/companies"}
        pages = [
            _get(api.create_app(env=env), "/settings", token).text for env in (bad_file, denied)
        ]

    for page in pages:
        assert "Seniority a title needs" in page
        assert "Northwind Robotics" not in page


def test_settings_page_shows_each_account_its_own_setup(
    signer: AlbSigner, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each account sees its own companies and its own job-alert address (design doc 0016).
    ssm = FakeSsm(value=EXAMPLE_COMPANIES)
    monkeypatch.setattr(api, "make_ssm_client", lambda _region: ssm)
    with key_server(signer) as key_url:
        env = {
            **auth_env(key_url),
            "PEJIP_AUTH_ACCOUNTS": f"{ACCOUNT_ID}={ALLOWED_EMAIL},friend=friend@example.com",
            "PEJIP_COMPANIES_PARAMETER": "/pejip/accounts/{account}/companies",
            "PEJIP_PROFILE": "/profiles/{account}.yaml",
        }
        app = api.create_app(env=env)
        babu = _get(app, "/settings", signer.token(ALLOWED_EMAIL)).text
        friend = _get(app, "/settings", signer.token("friend@example.com")).text
        _get(app, "/settings", signer.token("friend@example.com"))  # read once per account

    assert "alerts@inbox.job-search.zephyr-mcg.com" in babu
    assert "friend@inbox.job-search.zephyr-mcg.com" in friend
    assert "alerts@inbox" not in friend
    assert [c["Name"] for c in ssm.calls] == [
        "/pejip/accounts/babu/companies",
        "/pejip/accounts/friend/companies",
    ]


def _post(app: FastAPI, path: str, token: str | None, cookies: dict[str, str]) -> httpx.Response:
    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {OIDC_DATA_HEADER: token} if token else {}
        async with httpx.AsyncClient(
            transport=transport, base_url="https://test", cookies=cookies
        ) as client:
            return await client.post(path, headers=headers)

    return asyncio.run(call())


def test_sign_out_expires_every_session_shard(signed_in_app: FastAPI, signer: AlbSigner) -> None:
    cookies = {
        "AWSELBAuthSessionCookie-0": "a",
        "AWSELBAuthSessionCookie-1": "b",
        "other": "kept",
    }
    response = _post(signed_in_app, "/signout", signer.token(ALLOWED_EMAIL), cookies)

    assert response.status_code == 303
    assert response.headers["location"] == "/signed-out"
    expired = response.headers.get_list("set-cookie")
    assert len(expired) == 2
    for shard, header in zip(("0", "1"), expired, strict=True):
        assert header.startswith(f'AWSELBAuthSessionCookie-{shard}=""')
        assert "Max-Age=0" in header
        assert "Path=/" in header
        assert "Secure" in header
        assert "HttpOnly" in header


def test_sign_out_needs_sign_in(signed_in_app: FastAPI) -> None:
    response = _post(signed_in_app, "/signout", None, {})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_signed_out_page_and_styles_need_no_sign_in(signed_in_app: FastAPI) -> None:
    page = _get(signed_in_app, "/signed-out")
    styles = _get(signed_in_app, "/portal.css")

    assert page.status_code == 200
    assert "You are signed out" in page.text
    assert '<a class="btn primary" href="/">Sign in again</a>' in page.text
    assert "Sample data" not in page.text
    assert page.headers["Content-Security-Policy"] == api.PAGE_CSP
    assert styles.status_code == 200
    assert ".signout" in styles.text
