"""Unit tests for the HTTP surface."""

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI

from ci.alb_token import AlbSigner
from pejip import __version__, api
from pejip.auth import OIDC_DATA_HEADER
from tests.alb import ALB_ARN, ALLOWED_EMAIL, auth_env, key_server


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


def test_interactive_docs_are_disabled(signed_in_app: FastAPI, signer: AlbSigner) -> None:
    token = signer.token(ALLOWED_EMAIL)

    assert _get(signed_in_app, "/docs", token).status_code == 404
    assert _get(signed_in_app, "/redoc", token).status_code == 404
