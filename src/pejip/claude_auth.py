"""Keyless Claude credentials through Workload Identity Federation (ADR-0004).

PEJIP never holds a long-lived Claude API key in CI or in production. Each workload
proves who it is with a short-lived token from an identity provider it already has,
and the Anthropic SDK swaps that token for a short-lived Claude access token:

- GitHub Actions jobs use the Actions OIDC token (``id-token: write``).
- The app on ECS uses an AWS STS web identity token for its task role.

Usage::

    kwargs = federation_credentials(os.environ, sts=boto3.client("sts"))
    client = anthropic.Anthropic(
        credentials=anthropic.WorkloadIdentityCredentials(**kwargs) if kwargs else None
    )

``PEJIP_CLAUDE_IDENTITY`` picks the identity source (``github-actions`` or
``aws-sts``). When it is unset, ``federation_credentials`` returns ``None`` and the
SDK's own resolution applies, which is how a developer's ``ant auth login`` works
locally. Design: docs/design/0007-claude-identity-federation.md.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

# The audience Anthropic expects on federated identity tokens. Federation rules
# match it exactly, and the AWS policy in infra/claude_federation.tf allows no other.
AUDIENCE = "https://api.anthropic.com"

IDENTITY_SOURCE_ENV = "PEJIP_CLAUDE_IDENTITY"
GITHUB_ACTIONS = "github-actions"
AWS_STS = "aws-sts"

# AWS caps STS web identity tokens at this lifetime in the PEJIP policy.
AWS_TOKEN_SECONDS = 900
AWS_SIGNING_ALGORITHM = "RS256"
GITHUB_TIMEOUT_SECONDS = 10

# Static credentials outrank federation in the SDK, so a leftover one would
# silently replace it. Workloads that federate must not carry either.
_STATIC_CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

_IDS: dict[str, re.Pattern[str]] = {
    "ANTHROPIC_FEDERATION_RULE_ID": re.compile(r"^fdrl_[A-Za-z0-9]+$"),
    "ANTHROPIC_ORGANIZATION_ID": re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    ),
    "ANTHROPIC_SERVICE_ACCOUNT_ID": re.compile(r"^svac_[A-Za-z0-9]+$"),
}
_WORKSPACE_ENV = "ANTHROPIC_WORKSPACE_ID"
_WORKSPACE_ID = re.compile(r"^wrkspc_[A-Za-z0-9]+$")

_NOT_SET = "{} is not set"
_BAD_ID = "{} is not a valid ID"
_NO_GITHUB_OIDC = "GitHub OIDC is unavailable; the job needs `id-token: write`"
_GITHUB_NOT_HTTPS = "ACTIONS_ID_TOKEN_REQUEST_URL must use https"
_GITHUB_FETCH_FAILED = "could not fetch the GitHub OIDC token"
_GITHUB_EMPTY = "GitHub returned no OIDC token"
_STS_FAILED = "could not get an AWS STS web identity token"
_STS_EMPTY = "AWS STS returned no web identity token"
_LEFTOVER_KEY = "remove {}: it would override federation (ADR-0004)"
_NO_STS_CLIENT = f"{IDENTITY_SOURCE_ENV}={AWS_STS} needs an STS client"
_BAD_SOURCE = f"{IDENTITY_SOURCE_ENV} must be {GITHUB_ACTIONS!r} or {AWS_STS!r}"


class ClaudeAuthError(Exception):
    """Federation is misconfigured, or an identity token could not be obtained."""


class FederationKwargs(TypedDict):
    """Keyword arguments for ``anthropic.WorkloadIdentityCredentials``."""

    identity_token_provider: Callable[[], str]
    federation_rule_id: str
    organization_id: str
    service_account_id: str
    workspace_id: str | None


class StsClient(Protocol):
    """The part of a boto3 ``sts`` client this module uses."""

    def get_web_identity_token(self, **kwargs: Any) -> Mapping[str, Any]: ...


Opener = Callable[..., Any]


@dataclass(frozen=True)
class FederationSettings:
    """The non-secret IDs that name the Anthropic federation rule to use."""

    federation_rule_id: str
    organization_id: str
    service_account_id: str
    workspace_id: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> FederationSettings:
        values: dict[str, str] = {}
        for name, pattern in _IDS.items():
            value = env.get(name, "").strip()
            if not value:
                raise ClaudeAuthError(_NOT_SET.format(name))
            if not pattern.fullmatch(value):
                raise ClaudeAuthError(_BAD_ID.format(name))
            values[name] = value
        workspace = env.get(_WORKSPACE_ENV, "").strip() or None
        if workspace is not None and not _WORKSPACE_ID.fullmatch(workspace):
            raise ClaudeAuthError(_BAD_ID.format(_WORKSPACE_ENV))
        return cls(
            federation_rule_id=values["ANTHROPIC_FEDERATION_RULE_ID"],
            organization_id=values["ANTHROPIC_ORGANIZATION_ID"],
            service_account_id=values["ANTHROPIC_SERVICE_ACCOUNT_ID"],
            workspace_id=workspace,
        )


def github_actions_token_provider(
    env: Mapping[str, str], *, opener: Opener = urllib.request.urlopen
) -> Callable[[], str]:
    """Return a callable that fetches a fresh GitHub Actions OIDC token per call.

    A fresh token each time matters: Anthropic accepts each token (``jti``) once,
    and the SDK asks for a new one whenever it refreshes the Claude token.
    """
    request_url = env.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not request_url or not request_token:
        raise ClaudeAuthError(_NO_GITHUB_OIDC)
    if urllib.parse.urlsplit(request_url).scheme != "https":
        raise ClaudeAuthError(_GITHUB_NOT_HTTPS)
    separator = "&" if "?" in request_url else "?"
    url = f"{request_url}{separator}{urllib.parse.urlencode({'audience': AUDIENCE})}"

    def fetch() -> str:
        request = urllib.request.Request(  # noqa: S310 - https only, checked above
            url, headers={"Authorization": f"Bearer {request_token}"}
        )
        try:
            with opener(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
                body = json.load(response)
        except (OSError, ValueError) as exc:
            raise ClaudeAuthError(_GITHUB_FETCH_FAILED) from exc
        token = body.get("value") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise ClaudeAuthError(_GITHUB_EMPTY)
        return token

    return fetch


def aws_sts_token_provider(sts: StsClient) -> Callable[[], str]:
    """Return a callable that asks AWS STS for a fresh web identity token per call.

    ``sts`` must be a regional client (``GetWebIdentityToken`` has no global
    endpoint) running as a role allowed ``sts:GetWebIdentityToken``.
    """

    def fetch() -> str:
        try:
            response = sts.get_web_identity_token(
                Audience=[AUDIENCE],
                SigningAlgorithm=AWS_SIGNING_ALGORITHM,
                DurationSeconds=AWS_TOKEN_SECONDS,
            )
        except Exception as exc:  # boto3 raises many types; all mean "no token"
            raise ClaudeAuthError(_STS_FAILED) from exc
        token = response.get("WebIdentityToken")
        if not isinstance(token, str) or not token:
            raise ClaudeAuthError(_STS_EMPTY)
        return token

    return fetch


def federation_credentials(
    env: Mapping[str, str],
    *,
    sts: StsClient | None = None,
    opener: Opener = urllib.request.urlopen,
) -> FederationKwargs | None:
    """Build ``WorkloadIdentityCredentials`` arguments from the environment.

    Returns ``None`` when ``PEJIP_CLAUDE_IDENTITY`` is unset (local development).
    Raises ``ClaudeAuthError`` for any misconfiguration, including a static API key
    left in a federating workload, so a mistake fails at startup, not at first call.
    """
    source = env.get(IDENTITY_SOURCE_ENV, "").strip()
    if not source:
        return None
    leftover = [name for name in _STATIC_CREDENTIALS if name in env]
    if leftover:
        raise ClaudeAuthError(_LEFTOVER_KEY.format(", ".join(leftover)))
    settings = FederationSettings.from_env(env)
    if source == GITHUB_ACTIONS:
        provider = github_actions_token_provider(env, opener=opener)
    elif source == AWS_STS:
        if sts is None:
            raise ClaudeAuthError(_NO_STS_CLIENT)
        provider = aws_sts_token_provider(sts)
    else:
        raise ClaudeAuthError(_BAD_SOURCE)
    return FederationKwargs(
        identity_token_provider=provider,
        federation_rule_id=settings.federation_rule_id,
        organization_id=settings.organization_id,
        service_account_id=settings.service_account_id,
        workspace_id=settings.workspace_id,
    )
