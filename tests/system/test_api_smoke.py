"""System test and API smoke test (docs/BUILD_POLICY.md section 2).

Starts the installed application as its own process, the way it runs in production,
with Google sign-in on (ADR-0006), and calls every GET endpoint in its OpenAPI
document: with a token signed the way the load balancer signs it, without one, and
for an account that is not allowed. CI runs this against the built wheel, not the
source tree.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest

from ci.alb_token import AlbSigner
from pejip.auth import OIDC_DATA_HEADER, PUBLIC_PATHS
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
        env = {
            **os.environ,
            **auth_env(key_url),
            "PEJIP_HOST": "127.0.0.1",
            "PEJIP_PORT": str(port),
        }
        process = subprocess.Popen([sys.executable, "-m", "pejip.api"], env=env)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 20
        try:
            while True:
                assert process.poll() is None, "server exited during startup"
                assert time.monotonic() < deadline, "server did not become healthy"
                try:
                    if httpx.get(f"{url}/healthz").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            yield url
        finally:
            process.terminate()
            process.wait(timeout=10)


@pytest.fixture(scope="module")
def get_paths(base_url: str) -> list[str]:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    paths = httpx.get(f"{base_url}/openapi.json", headers=signed_in).json()["paths"]
    found = [path for path, ops in paths.items() if "get" in ops]
    assert found, "OpenAPI document lists no GET endpoints"
    return found


def test_every_get_endpoint_responds(base_url: str, get_paths: list[str]) -> None:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    for path in get_paths:
        response = httpx.get(f"{base_url}{path}", headers=signed_in)
        assert response.status_code == 200, f"GET {path} returned {response.status_code}"


def test_every_protected_endpoint_requires_sign_in(base_url: str, get_paths: list[str]) -> None:
    other_account = {OIDC_DATA_HEADER: SIGNER.token("someone@example.com")}
    for path in [*get_paths, "/openapi.json"]:
        if path in PUBLIC_PATHS:
            continue
        assert httpx.get(f"{base_url}{path}").status_code == 401, path
        assert httpx.get(f"{base_url}{path}", headers=other_account).status_code == 403, path


def test_server_hides_its_identity(base_url: str) -> None:
    assert "server" not in httpx.get(f"{base_url}/healthz").headers
