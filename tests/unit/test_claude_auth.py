"""Keyless Claude credentials (pejip.claude_auth, ADR-0004)."""

from __future__ import annotations

import io
import json
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest

from pejip import claude_auth
from pejip.claude_auth import (
    AUDIENCE,
    ClaudeAuthError,
    FederationSettings,
    aws_sts_token_provider,
    federation_credentials,
    github_actions_token_provider,
)

ORG = "4f0a1c2e-9b8d-4e7f-a6b5-c4d3e2f1a0b9"
IDS = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_01AbC",
    "ANTHROPIC_ORGANIZATION_ID": ORG,
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_01XyZ",
}
GITHUB = {
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.example.test/oidc?api-version=2.0",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
}


class FakeOpener:
    """Stands in for urlopen: records each request and returns queued bodies."""

    def __init__(self, *bodies: bytes | Exception) -> None:
        self.bodies = list(bodies)
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: urllib.request.Request, *, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        self.timeouts.append(timeout)
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return io.BytesIO(body)


class FakeSts:
    def __init__(self, *responses: Mapping[str, Any] | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get_web_identity_token(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def token_body(value: object) -> bytes:
    return json.dumps({"value": value}).encode()


# ── FederationSettings ──────────────────────────────────────────────────────


def test_settings_read_ids_and_optional_workspace() -> None:
    settings = FederationSettings.from_env({**IDS, "ANTHROPIC_WORKSPACE_ID": " wrkspc_01Q "})
    assert settings == FederationSettings(
        federation_rule_id="fdrl_01AbC",
        organization_id=ORG,
        service_account_id="svac_01XyZ",
        workspace_id="wrkspc_01Q",
    )


def test_settings_workspace_defaults_to_none() -> None:
    assert FederationSettings.from_env({**IDS, "ANTHROPIC_WORKSPACE_ID": ""}).workspace_id is None


@pytest.mark.parametrize("name", sorted(IDS))
def test_settings_require_each_id(name: str) -> None:
    env = {k: v for k, v in IDS.items() if k != name}
    with pytest.raises(ClaudeAuthError, match=f"{name} is not set"):
        FederationSettings.from_env(env)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ANTHROPIC_FEDERATION_RULE_ID", "rule_01"),
        ("ANTHROPIC_ORGANIZATION_ID", "not-a-uuid"),
        ("ANTHROPIC_SERVICE_ACCOUNT_ID", "svac_bad id"),
        ("ANTHROPIC_WORKSPACE_ID", "default"),
    ],
)
def test_settings_reject_malformed_ids(name: str, value: str) -> None:
    with pytest.raises(ClaudeAuthError, match=f"{name} is not a valid ID"):
        FederationSettings.from_env({**IDS, name: value})


# ── GitHub Actions ──────────────────────────────────────────────────────────


def test_github_fetches_a_fresh_token_for_the_anthropic_audience() -> None:
    opener = FakeOpener(token_body("jwt-1"), token_body("jwt-2"))
    fetch = github_actions_token_provider(GITHUB, opener=opener)

    assert fetch() == "jwt-1"
    assert fetch() == "jwt-2"
    request = opener.requests[0]
    assert request.full_url == (
        "https://token.example.test/oidc?api-version=2.0&audience=https%3A%2F%2Fapi.anthropic.com"
    )
    assert request.get_header("Authorization") == "Bearer request-token"
    assert opener.timeouts == [claude_auth.GITHUB_TIMEOUT_SECONDS] * 2


def test_github_adds_query_when_url_has_none() -> None:
    opener = FakeOpener(token_body("jwt"))
    env = {**GITHUB, "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.example.test/oidc"}
    github_actions_token_provider(env, opener=opener)()
    assert opener.requests[0].full_url.endswith("/oidc?audience=https%3A%2F%2Fapi.anthropic.com")


@pytest.mark.parametrize("missing", sorted(GITHUB))
def test_github_needs_id_token_permission(missing: str) -> None:
    env = {k: v for k, v in GITHUB.items() if k != missing}
    with pytest.raises(ClaudeAuthError, match="id-token: write"):
        github_actions_token_provider(env)


def test_github_refuses_plain_http() -> None:
    env = {**GITHUB, "ACTIONS_ID_TOKEN_REQUEST_URL": "http://token.example.test/oidc"}
    with pytest.raises(ClaudeAuthError, match="https"):
        github_actions_token_provider(env)


@pytest.mark.parametrize("failure", [OSError("down"), ValueError("bad json")])
def test_github_wraps_fetch_failures(failure: Exception) -> None:
    fetch = github_actions_token_provider(GITHUB, opener=FakeOpener(failure))
    with pytest.raises(ClaudeAuthError, match="could not fetch") as caught:
        fetch()
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("body", [token_body(""), token_body(7), b"[]", b"{}"])
def test_github_rejects_responses_without_a_token(body: bytes) -> None:
    fetch = github_actions_token_provider(GITHUB, opener=FakeOpener(body))
    with pytest.raises(ClaudeAuthError, match="no OIDC token"):
        fetch()


# ── AWS STS ─────────────────────────────────────────────────────────────────


def test_sts_requests_a_short_lived_rs256_token_per_call() -> None:
    sts = FakeSts({"WebIdentityToken": "aws-1"}, {"WebIdentityToken": "aws-2"})
    fetch = aws_sts_token_provider(sts)

    assert fetch() == "aws-1"
    assert fetch() == "aws-2"
    assert (
        sts.calls
        == [{"Audience": [AUDIENCE], "SigningAlgorithm": "RS256", "DurationSeconds": 900}] * 2
    )


def test_sts_wraps_client_errors() -> None:
    failure = RuntimeError("AccessDenied")
    fetch = aws_sts_token_provider(FakeSts(failure))
    with pytest.raises(ClaudeAuthError, match="could not get") as caught:
        fetch()
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("response", [{}, {"WebIdentityToken": ""}, {"WebIdentityToken": 3}])
def test_sts_rejects_responses_without_a_token(response: Mapping[str, Any]) -> None:
    with pytest.raises(ClaudeAuthError, match="no web identity token"):
        aws_sts_token_provider(FakeSts(response))()


# ── federation_credentials ──────────────────────────────────────────────────


@pytest.mark.parametrize("source", [None, "", "  "])
def test_unset_source_leaves_credentials_to_the_sdk(source: str | None) -> None:
    env = {} if source is None else {claude_auth.IDENTITY_SOURCE_ENV: source}
    assert federation_credentials({**env, "ANTHROPIC_API_KEY": "local-dev"}) is None


def test_github_source_builds_sdk_arguments() -> None:
    env = {**IDS, **GITHUB, "PEJIP_CLAUDE_IDENTITY": "github-actions"}
    opener = FakeOpener(token_body("jwt"))

    kwargs = federation_credentials(env, opener=opener)

    assert kwargs is not None
    assert kwargs["identity_token_provider"]() == "jwt"
    assert {k: v for k, v in kwargs.items() if k != "identity_token_provider"} == {
        "federation_rule_id": "fdrl_01AbC",
        "organization_id": ORG,
        "service_account_id": "svac_01XyZ",
        "workspace_id": None,
    }


def test_aws_source_uses_the_given_sts_client() -> None:
    env = {**IDS, "PEJIP_CLAUDE_IDENTITY": "aws-sts", "ANTHROPIC_WORKSPACE_ID": "wrkspc_01Q"}
    sts = FakeSts({"WebIdentityToken": "aws"})

    kwargs = federation_credentials(env, sts=sts)

    assert kwargs is not None
    assert kwargs["identity_token_provider"]() == "aws"
    assert kwargs["workspace_id"] == "wrkspc_01Q"


def test_aws_source_needs_an_sts_client() -> None:
    with pytest.raises(ClaudeAuthError, match="needs an STS client"):
        federation_credentials({**IDS, "PEJIP_CLAUDE_IDENTITY": "aws-sts"})


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(ClaudeAuthError, match="must be 'github-actions' or 'aws-sts'"):
        federation_credentials({**IDS, "PEJIP_CLAUDE_IDENTITY": "api-key"})


@pytest.mark.parametrize(
    "leftover",
    [
        ["ANTHROPIC_API_KEY"],
        ["ANTHROPIC_AUTH_TOKEN"],
        ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
    ],
)
def test_static_credentials_block_federation(leftover: list[str]) -> None:
    # Even an empty value counts: the SDK would still pick it over federation.
    env = {**IDS, **GITHUB, "PEJIP_CLAUDE_IDENTITY": "github-actions"}
    env.update(dict.fromkeys(leftover, ""))
    with pytest.raises(ClaudeAuthError, match="override federation"):
        federation_credentials(env)


def test_errors_never_echo_secret_values() -> None:
    env = {**IDS, "ANTHROPIC_API_KEY": "sk-ant-secret", "PEJIP_CLAUDE_IDENTITY": "aws-sts"}
    with pytest.raises(ClaudeAuthError) as caught:
        federation_credentials(env)
    assert "sk-ant-secret" not in str(caught.value)
