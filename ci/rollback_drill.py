"""Rollback drill (docs/BUILD_POLICY.md section 15, docs/design/0006-releases-and-rollback.md).

Exercises a rollback on every change: serves the build under test, swaps it for the
release a rollback would return to, checks that release comes up healthy and reports
its own version, then rolls forward again. Each build is a Python interpreter with
that build's wheel installed, served the way production serves it.

    python -m ci.rollback_drill --current venv-head/bin/python \\
        --previous venv-prev/bin/python --previous-version 0.1.0
"""

import argparse
import http.client
import json
import os
import subprocess  # nosec B404
import sys
import time
from collections.abc import Sequence

HOST = "127.0.0.1"
STOP_TIMEOUT = 10.0


class DrillError(Exception):
    """A step of the drill failed; the message says which."""


def health(port: int) -> dict[str, str] | None:
    """The /healthz body, or None while nothing healthy is listening."""
    connection = http.client.HTTPConnection(HOST, port, timeout=2)
    try:
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        body = response.read()
    except OSError:
        return None
    finally:
        connection.close()
    if response.status != http.client.OK:
        return None
    parsed: dict[str, str] = json.loads(body)
    return parsed


def serve(python: str, port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "PEJIP_HOST": HOST, "PEJIP_PORT": str(port)}
    # The interpreter is chosen by CI; no shell.
    return subprocess.Popen(  # noqa: S603  # nosec B603
        [python, "-m", "pejip.api"], env=env
    )


def wait_healthy(process: subprocess.Popen[bytes], port: int, timeout: float) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            msg = f"the app exited with code {process.returncode} before it was healthy"
            raise DrillError(msg)
        body = health(port)
        if body is not None and body.get("status") == "ok":
            return body
        time.sleep(0.2)
    msg = f"the app was not healthy within {timeout:g}s"
    raise DrillError(msg)


def stop(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def step(name: str, python: str, port: int, timeout: float, version: str | None = None) -> None:
    """Serve one build until healthy, check its version, then stop it."""
    process = serve(python, port)
    try:
        body = wait_healthy(process, port, timeout)
    finally:
        stop(process)
    if version is not None and body.get("version") != version:
        msg = f"{name}: expected version {version}, /healthz reported {body.get('version')}"
        raise DrillError(msg)
    print(f"{name}: healthy, version {body.get('version')}")


def drill(current: str, previous: str, previous_version: str, port: int, timeout: float) -> None:
    step("deploy current build", current, port, timeout)
    step("roll back to previous release", previous, port, timeout, previous_version)
    step("roll forward to current build", current, port, timeout)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", required=True, help="interpreter with the build under test")
    parser.add_argument("--previous", required=True, help="interpreter with the rollback target")
    parser.add_argument("--previous-version", required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        drill(args.current, args.previous, args.previous_version, args.port, args.timeout)
    except DrillError as error:
        print(f"::error::Rollback drill failed: {error}")
        return 1
    print("Rollback drill passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
