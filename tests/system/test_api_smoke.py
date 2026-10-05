"""System test and API smoke test (docs/BUILD_POLICY.md section 2).

Starts the installed application as its own process, the way it runs in production,
and calls every GET endpoint in its OpenAPI document. CI runs this against the built
wheel, not the source tree.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    port = _free_port()
    env = {**os.environ, "PEJIP_HOST": "127.0.0.1", "PEJIP_PORT": str(port)}
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


def test_every_get_endpoint_responds(base_url: str) -> None:
    paths = httpx.get(f"{base_url}/openapi.json").json()["paths"]
    get_paths = [path for path, ops in paths.items() if "get" in ops]
    assert get_paths, "OpenAPI document lists no GET endpoints"

    for path in get_paths:
        response = httpx.get(f"{base_url}{path}")
        assert response.status_code == 200, f"GET {path} returned {response.status_code}"


def test_server_hides_its_identity(base_url: str) -> None:
    assert "server" not in httpx.get(f"{base_url}/healthz").headers
