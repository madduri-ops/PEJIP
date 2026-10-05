"""System test and API smoke test (docs/BUILD_POLICY.md section 2).

Starts the installed application as its own process, the way it runs in production,
with Google sign-in on (ADR-0006), and calls every GET endpoint in its OpenAPI
document: with a token signed the way the load balancer signs it, without one, and
for an account that is not allowed. CI runs this against the built wheel, not the
source tree.
"""

import hashlib
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from ci.alb_token import AlbSigner
from pejip.api import PAGE_CSP
from pejip.auth import OIDC_DATA_HEADER, PUBLIC_PATHS
from pejip.ranking_api import RANKING_PREFIX
from tests.alb import ALB_ARN, ALLOWED_EMAIL, auth_env, key_server

SIGNER = AlbSigner(ALB_ARN)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


RANKING_KEY = "k" * 40
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = _free_port()
    data = tmp_path_factory.mktemp("data")
    with key_server(SIGNER) as key_url:
        env = {
            **os.environ,
            **auth_env(key_url),
            "PEJIP_HOST": "127.0.0.1",
            "PEJIP_PORT": str(port),
            # The ranking routine's endpoints, with a throwaway key and empty database.
            "PEJIP_RANKING_KEY_SHA256": hashlib.sha256(RANKING_KEY.encode()).hexdigest(),
            "PEJIP_DATABASE_URL": f"sqlite:///{data / 'pejip.db'}",
            "PEJIP_PROFILE": str(ROOT / "examples" / "profile.example.yaml"),
            "PEJIP_CONFIG": str(ROOT / "config" / "search.yaml"),
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


def _with_examples(path: str, operation: dict[str, Any]) -> str:
    """Fill each path parameter with the first example the OpenAPI document gives."""
    for param in operation.get("parameters", []):
        if param["in"] == "path":
            example = next(iter(param["examples"].values()))["value"]
            path = path.replace("{" + param["name"] + "}", str(example))
    assert not re.search(r"\{\w+\}", path), f"{path} has a path parameter with no example"
    return path


@pytest.fixture(scope="module")
def get_paths(base_url: str) -> list[str]:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    paths = httpx.get(f"{base_url}/openapi.json", headers=signed_in).json()["paths"]
    found = [
        _with_examples(path, ops["get"])
        for path, ops in paths.items()
        if "get" in ops and not path.startswith(RANKING_PREFIX)
    ]
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


def test_ranking_endpoints_need_the_routines_key(base_url: str) -> None:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    queue = f"{base_url}{RANKING_PREFIX}queue"
    assert httpx.get(queue).status_code == 401
    assert httpx.get(queue, headers=signed_in).status_code == 401
    wrong = {"Authorization": "Bearer " + "x" * 40}
    assert httpx.get(queue, headers=wrong).status_code == 401
    response = httpx.get(queue, headers={"Authorization": f"Bearer {RANKING_KEY}"})
    assert response.status_code == 200
    assert response.json()["roles"] == []
    assert "email" not in response.json()["profile"]


def test_portal_pages_carry_the_page_policy(base_url: str) -> None:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    for path in ("/", "/opportunities", "/opportunities/1"):
        response = httpx.get(f"{base_url}{path}", headers=signed_in)
        assert response.headers["content-security-policy"] == PAGE_CSP, path
        assert "<script" not in response.text, path


def test_server_hides_its_identity(base_url: str) -> None:
    assert "server" not in httpx.get(f"{base_url}/healthz").headers
