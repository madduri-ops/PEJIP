"""Runs the installed ``pejip`` CLI as a subprocess against local stub servers.

The stubs stand in for a Greenhouse board and the Anthropic Messages API, so the
real HTTP clients, configuration loading, database, prompts and digest writer are
all exercised exactly as in production.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml

from pejip.cost import CostGuard, SqliteLedger
from tests import factories as f
from tests.conftest import ROOT

BOARD = {
    "jobs": [
        {
            "id": 7,
            "title": "VP, Technology Operations",
            "location": {"name": "San Francisco, CA"},
            "absolute_url": "https://boards.example/7",
            "first_published": "2026-10-04T09:00:00+00:00",
            "content": (
                "&lt;p&gt;Lead technology operations.&lt;/p&gt;"
                "&lt;p&gt;Own portfolio governance.&lt;/p&gt;"
            ),
        },
        {
            "id": 8,
            "title": "Office Manager",
            "location": {"name": "San Francisco, CA"},
            "content": "",
        },
    ]
}


class Stub(BaseHTTPRequestHandler):
    model_requests: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, *_args: Any) -> None:
        return

    def _send(self, status: int, body: Any) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.startswith("/v1/boards/acme/jobs"):
            self._send(200, BOARD)
        else:
            self._send(404, {})

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        Stub.model_requests.append(request)
        content = request["messages"][0]["content"]
        if "<posting>" in content:
            reqs = [
                f.requirement("R1", quote="Lead technology operations"),
                f.requirement("R2", category="CAPABILITY", quote="Own portfolio governance"),
            ]
            payload = f.analysis(reqs)
        else:
            payload = f.matching([f.match("R1"), f.match("R2", evidence=["E4"])])
        self._send(
            200,
            {
                "id": "msg_stub",
                "type": "message",
                "role": "assistant",
                "model": request["model"],
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1200, "output_tokens": 400},
            },
        )


@pytest.fixture
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    thread.join()
    httpd.server_close()


def test_cli_run_produces_an_explained_digest(server: str, tmp_path: Path) -> None:
    config = yaml.safe_load((ROOT / "config" / "search.yaml").read_text())
    config["sources"] = [
        {"adapter": "greenhouse", "company": "Acme", "board": "acme", "api_base": server}
    ]
    config["fetch"]["min_interval_seconds"] = 0
    (tmp_path / "search.yaml").write_text(yaml.safe_dump(config))
    env = {
        **os.environ,
        "PEJIP_CONFIG": str(tmp_path / "search.yaml"),
        "PEJIP_PROFILE": str(ROOT / "examples" / "profile.example.yaml"),
        "PEJIP_DATABASE_URL": f"sqlite:///{tmp_path / 'pejip.db'}",
        "PEJIP_OUTPUT_DIR": str(tmp_path / "out"),
        "PEJIP_AI_LEDGER": str(tmp_path / "spend.db"),
        "ANTHROPIC_API_KEY": "test-key-not-real",
        "ANTHROPIC_BASE_URL": server,
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pejip", "run"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    digests = list((tmp_path / "out").glob("digest-*.md"))
    assert len(digests) == 1
    text = digests[0].read_text()
    assert "[VP, Technology Operations](https://boards.example/7) at Acme **New**" in text
    assert "Fit **100**" in text
    assert '"Lead technology operations"; E1' in text
    assert "| Acme (greenhouse) | OK | 2 | 1 |" in text
    assert "Office Manager" not in text

    assert len(Stub.model_requests) == 2
    assert Stub.model_requests[0]["model"] == "claude-opus-5-5"
    assert "Alex Example" not in json.dumps(Stub.model_requests)

    logs = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
    assert {"run_started", "run_finished", "digest_written"} <= {entry["event"] for entry in logs}
    assert len({entry["run_id"] for entry in logs if entry["event"] != "digest_written"}) == 1
    assert "alex@example.com" not in result.stderr

    exported = tmp_path / "export.json"
    subprocess.run(
        [sys.executable, "-m", "pejip", "export", "export.json"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
    )
    data = json.loads(exported.read_text())
    assert data["recommendations"][0]["fit"] == 100.0
    ledger = SqliteLedger(tmp_path / "spend.db")
    spend = {(line.feature, line.model) for line in CostGuard(ledger).breakdown()}
    ledger.close()
    assert spend == {("job_analysis", "claude-opus-5-5"), ("evidence_matching", "claude-opus-5-5")}
    assert data["recommendations"][0]["scoring_version"] == "fit-1"
