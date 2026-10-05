"""Integration tests: the rollback drill against real app processes."""

import json
import socket
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ci import rollback_drill
from pejip import __version__

PYTHON = sys.executable


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _script(tmp_path: Path, body: str) -> str:
    path = tmp_path / "fake-python"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def test_drill_passes_with_real_builds(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--current", PYTHON, "--previous", PYTHON, "--previous-version", __version__]
    assert rollback_drill.main([*args, "--port", str(_free_port())]) == 0
    out = capsys.readouterr().out
    assert f"roll back to previous release: healthy, version {__version__}" in out
    assert out.rstrip().endswith("Rollback drill passed.")


def test_drill_fails_when_the_previous_release_reports_another_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--current", PYTHON, "--previous", PYTHON, "--previous-version", "0.0.1"]
    assert rollback_drill.main([*args, "--port", str(_free_port())]) == 1
    assert "expected version 0.0.1" in capsys.readouterr().out


def test_drill_fails_when_a_build_exits(tmp_path: Path) -> None:
    broken = _script(tmp_path, "exit 3")
    with pytest.raises(rollback_drill.DrillError, match="exited with code 3"):
        rollback_drill.drill(PYTHON, broken, __version__, _free_port(), 30)


def test_drill_fails_when_a_build_never_gets_healthy(tmp_path: Path) -> None:
    hung = _script(tmp_path, "exec sleep 30")
    with pytest.raises(rollback_drill.DrillError, match=r"not healthy within 0\.5s"):
        rollback_drill.step("hung", hung, _free_port(), 0.5)


def test_stop_kills_a_build_that_ignores_terminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rollback_drill, "STOP_TIMEOUT", 0.5)
    ready = tmp_path / "ready"
    stubborn = _script(tmp_path, f"trap '' TERM\ntouch {ready}\nwhile :; do sleep 0.1; done")
    process = rollback_drill.serve(stubborn, _free_port())
    deadline = time.monotonic() + 10
    while not ready.exists():
        assert time.monotonic() < deadline, "script did not start"
        time.sleep(0.05)
    rollback_drill.stop(process)
    assert process.returncode == -9


class _Handler(BaseHTTPRequestHandler):
    status = 200
    body = b"{}"

    def do_GET(self) -> None:
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture
def fake_app() -> Iterator[tuple[int, type[_Handler]]]:
    handler = type("Handler", (_Handler,), {})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1], handler
    server.shutdown()
    server.server_close()


def test_health_ignores_an_unhealthy_status(fake_app: tuple[int, type[_Handler]]) -> None:
    port, handler = fake_app
    handler.status = 503
    assert rollback_drill.health(port) is None


def test_health_returns_the_body(fake_app: tuple[int, type[_Handler]]) -> None:
    port, handler = fake_app
    handler.body = json.dumps({"status": "ok", "version": "9.9.9"}).encode()
    assert rollback_drill.health(port) == {"status": "ok", "version": "9.9.9"}


def test_health_with_nothing_listening() -> None:
    assert rollback_drill.health(_free_port()) is None


def test_wait_healthy_keeps_waiting_while_starting(
    tmp_path: Path, fake_app: tuple[int, type[_Handler]]
) -> None:
    port, handler = fake_app
    handler.body = json.dumps({"status": "starting"}).encode()
    process = rollback_drill.serve(_script(tmp_path, "exec sleep 30"), port)
    try:
        with pytest.raises(rollback_drill.DrillError, match="not healthy"):
            rollback_drill.wait_healthy(process, port, 0.5)
    finally:
        rollback_drill.stop(process)
