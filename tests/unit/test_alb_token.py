"""Unit tests for the CI token signer (ci/alb_token.py)."""

import asyncio
from pathlib import Path

import httpx
import pytest

from ci import alb_token
from pejip.auth import Account, Authenticator, AuthSettings, KeyStore
from tests.alb import ACCOUNT_ID, ALB_ARN, ALLOWED_EMAIL


def test_main_writes_the_key_and_prints_a_valid_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key_dir = tmp_path / "keys"

    assert alb_token.main([str(key_dir), ALLOWED_EMAIL, ALB_ARN]) == 0

    token = capsys.readouterr().out.strip()
    pem = (key_dir / "ci-key").read_bytes()
    store = KeyStore(
        "https://keys.test/{kid}",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=pem)),
    )
    account = Account(ACCOUNT_ID, ALLOWED_EMAIL)
    settings = AuthSettings((account,), ALB_ARN, "https://keys.test/{kid}")
    assert asyncio.run(Authenticator(settings, store).verify(token)) == account


def test_main_explains_its_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert alb_token.main(["only-one"]) == 2
    assert "usage" in capsys.readouterr().err


def test_main_reads_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["alb_token"])

    assert alb_token.main() == 2
