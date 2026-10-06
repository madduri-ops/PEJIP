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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ci.alb_token import AlbSigner
from pejip.api import PAGE_CSP
from pejip.auth import OIDC_DATA_HEADER, PUBLIC_PATHS
from pejip.models import Posting
from pejip.ranking_api import RANKING_PREFIX
from pejip.store import Store
from tests.alb import ALB_ARN, ALLOWED_EMAIL, auth_env, key_server

SIGNER = AlbSigner(ALB_ARN)


def _seed(database: Path) -> None:
    """One searched role, so the role page has something to show."""
    store = Store(f"sqlite:///{database}")
    now = datetime.now(UTC)
    job = store.upsert_job(
        Posting("greenhouse", "b:1", "Co", "VP Ops", "Oakland, CA", "Lead.", "https://e.com/1"),
        now,
    )
    store.start_run("seed", now)
    store.finish_run("seed", "OK", {"sources": [], "seen": [[job.job_id, "NEW_POSTING"]]}, now)


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
    _seed(data / "pejip.db")
    with key_server(SIGNER) as key_url:
        env = {
            **os.environ,
            **auth_env(key_url),
            "PEJIP_HOST": "127.0.0.1",
            "PEJIP_PORT": str(port),
            # The ranking routine's endpoints, with a throwaway key and one seeded role.
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
    assert [r["title"] for r in response.json()["roles"]] == ["VP Ops"]  # the seeded role
    assert "email" not in response.json()["profile"]


def test_portal_pages_carry_the_page_policy(base_url: str) -> None:
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    for path in ("/", "/opportunities", "/opportunities/1"):
        response = httpx.get(f"{base_url}{path}", headers=signed_in)
        assert response.headers["content-security-policy"] == PAGE_CSP, path
        assert "<script" not in response.text, path


def test_server_hides_its_identity(base_url: str) -> None:
    assert "server" not in httpx.get(f"{base_url}/healthz").headers


def test_settings_are_saved_on_the_running_server(base_url: str) -> None:
    # Design doc 0017: the Settings form saves to the account's database.
    signed_in = {OIDC_DATA_HEADER: SIGNER.token(ALLOWED_EMAIL)}
    form = {**signed_in, "content-type": "application/x-www-form-urlencoded"}
    body = (
        "seniority_patterns=vice+president&role_terms=operations&excluded_title_patterns="
        "&places.BAY_AREA=oakland&preference.BAY_AREA=PREFERRED"
        "&places.US_REMOTE=&preference.US_REMOTE=ACCEPTABLE&hard_filter=on"
    )
    url = f"{base_url}/settings"
    elsewhere = httpx.post(url, content=body, headers={**form, "origin": "https://evil.example"})
    assert elsewhere.status_code == 403
    host = {**form, "origin": base_url}
    saved = httpx.post(url, content=body, headers=host)
    assert saved.status_code == 303
    page = httpx.get(f"{url}?saved=1", headers=signed_in).text
    assert "Saved. The next search, ranking and digest use these settings." in page
    assert ">oakland</textarea>" in page
    assert httpx.post(url, content="action=reset", headers=host).status_code == 303
    assert "Using the default settings." in httpx.get(url, headers=signed_in).text
    # What a browser sends from the live page: Origin null (no-referrer), Sec-Fetch-Site.
    browser = {**form, "origin": "null", "sec-fetch-site": "same-origin"}
    assert httpx.post(url, content=body, headers=browser).status_code == 303
    assert httpx.post(url, content="action=reset", headers=browser).status_code == 303
