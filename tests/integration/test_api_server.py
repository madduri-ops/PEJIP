"""Integration tests: the API served by a real uvicorn server over real HTTP."""

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from pejip import api


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_healthz_over_http(base_url: str) -> None:
    response = httpx.get(f"{base_url}/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_openapi_lists_healthz(base_url: str) -> None:
    paths = httpx.get(f"{base_url}/openapi.json").json()["paths"]

    assert "/healthz" in paths
