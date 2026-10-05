"""Unit tests for the HTTP surface."""

import asyncio

import httpx
import pytest

from pejip import __version__, api


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


def test_interactive_docs_are_disabled(client: Client) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


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
