"""Integration tests: the API served by a real uvicorn server over real HTTP.

Sign-in is on, with signing keys fetched over HTTP from a local key server the way
the app fetches the load balancer's keys from AWS (ADR-0006).
"""

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from ci.alb_token import AlbSigner
from pejip import api
from pejip.auth import OIDC_DATA_HEADER
from tests.alb import ALB_ARN, ALLOWED_EMAIL, auth_env, key_server

SIGNER = AlbSigner(ALB_ARN)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    port = _free_port()
    with key_server(SIGNER) as key_url:
        server = uvicorn.Server(
            uvicorn.Config(
                api.create_app(env=auth_env(key_url)),
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
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
    response = httpx.get(
        f"{base_url}/openapi.json", headers={OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    )

    assert "/healthz" in response.json()["paths"]


def test_sign_in_is_enforced_over_http(base_url: str) -> None:
    assert httpx.get(f"{base_url}/openapi.json").status_code == 401
    wrong = {OIDC_DATA_HEADER: SIGNER.token("someone@example.com")}
    assert httpx.get(f"{base_url}/openapi.json", headers=wrong).status_code == 403
