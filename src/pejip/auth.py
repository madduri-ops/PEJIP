"""Sign-in check for requests that reach PEJIP through the load balancer (ADR-0006).

The load balancer signs Babu in with Google before it forwards a request, then
passes the signed-in user's claims in the ``x-amzn-oidc-data`` header: a JWT the
load balancer signs with ES256 (a P-256 key whose public half AWS publishes per
region by key id). The app trusts a request only when that token is signed by the
load balancer PEJIP runs behind, has not expired, and names the one allowed,
Google-verified email address. Everything except ``/healthz`` requires it, so a
request that skips the load balancer, or a Google account that is not Babu's,
gets nothing.

When sign-in is not configured the app fails closed: every protected route
answers 503.
"""

import base64
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

OIDC_DATA_HEADER = "x-amzn-oidc-data"

# Reachable without signing in: the post-deploy health gate polls /healthz, and the
# page Sign out lands on (with its stylesheet) must not sign Babu straight back in.
PUBLIC_PATHS = frozenset({"/healthz", "/signed-out", "/portal.css"})

# The load balancer keeps the sign-in session in this cookie, split into shards
# named -0, -1 and so on when it is large.
ALB_SESSION_COOKIE = "AWSELBAuthSessionCookie"

# Where AWS publishes the load balancer's signing keys, by region and key id.
ALB_KEY_URL = "https://public-keys.auth.elb.{region}.amazonaws.com/{kid}"

# Clock skew allowed when checking the token's expiry, in seconds.
EXPIRY_LEEWAY_SECONDS = 60

# Load balancer key ids are UUIDs. Anything else is refused before it is put in a URL.
_KID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,128}$")

# Signing keys kept in memory. The load balancer rotates them rarely.
_MAX_CACHED_KEYS = 16

_P256_COORDINATE_BYTES = 32


class SignInRequiredError(Exception):
    """The request carries no valid token from PEJIP's load balancer (401)."""


class AccountNotAllowedError(Exception):
    """A valid token for an account other than the allowed one (403)."""


@dataclass(frozen=True)
class AuthSettings:
    """Who may sign in, and how their token is checked."""

    allowed_email: str
    alb_arn: str
    key_url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AuthSettings | None":
        """Read the settings, or None when sign-in is not configured.

        ``PEJIP_AUTH_ALLOWED_EMAIL`` and ``PEJIP_AUTH_ALB_ARN`` turn it on; the ECS
        task definition sets both. ``PEJIP_AUTH_KEY_URL`` overrides where signing
        keys are fetched (``{kid}`` is replaced by the key id); tests use it.
        """
        email = env.get("PEJIP_AUTH_ALLOWED_EMAIL", "").strip()
        alb_arn = env.get("PEJIP_AUTH_ALB_ARN", "").strip()
        if not email or not alb_arn:
            return None
        arn_parts = alb_arn.split(":")
        if len(arn_parts) < 6 or not arn_parts[3]:  # noqa: PLR2004 - arn:partition:service:region:account:resource
            msg = "PEJIP_AUTH_ALB_ARN is not a load balancer ARN"
            raise ValueError(msg)
        default_url = ALB_KEY_URL.replace("{region}", arn_parts[3])
        return cls(
            allowed_email=email.lower(),
            alb_arn=alb_arn,
            key_url=env.get("PEJIP_AUTH_KEY_URL", default_url),
        )


def _b64decode(segment: str) -> bytes:
    """Decode base64url with or without padding (the load balancer pads)."""
    stripped = segment.rstrip("=")
    try:
        return base64.urlsafe_b64decode(stripped + "=" * (-len(stripped) % 4))
    except ValueError as error:  # binascii.Error is a ValueError
        raise SignInRequiredError from error


def _json_segment(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_b64decode(segment))
    except (UnicodeDecodeError, ValueError) as error:
        raise SignInRequiredError from error
    if not isinstance(value, dict):
        raise SignInRequiredError
    return value


class KeyStore:
    """Fetches and caches the load balancer's public signing keys."""

    def __init__(self, key_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key_url = key_url
        self._transport = transport
        self._keys: dict[str, ec.EllipticCurvePublicKey] = {}

    async def get(self, kid: str) -> ec.EllipticCurvePublicKey:
        """Return the public key for ``kid``, fetching it on first use."""
        if not _KID_PATTERN.fullmatch(kid):
            raise SignInRequiredError
        if kid in self._keys:
            return self._keys[kid]
        url = self._key_url.replace("{kid}", kid)
        try:
            async with httpx.AsyncClient(timeout=5, transport=self._transport) as client:
                response = await client.get(url)
            response.raise_for_status()
            key = serialization.load_pem_public_key(response.content)
        except (httpx.HTTPError, ValueError) as error:
            raise SignInRequiredError from error
        if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
            raise SignInRequiredError
        if len(self._keys) >= _MAX_CACHED_KEYS:
            self._keys.clear()
        self._keys[kid] = key
        return key


class Authenticator:
    """Checks the load balancer's token and returns the signed-in email."""

    def __init__(self, settings: AuthSettings, keys: KeyStore | None = None) -> None:
        self.settings = settings
        self._keys = keys or KeyStore(settings.key_url)

    async def verify(self, token: str | None, now: float | None = None) -> str:
        """Return the allowed email, or raise if the token does not prove it."""
        if not token:
            raise SignInRequiredError
        parts = token.split(".")
        if len(parts) != 3:  # noqa: PLR2004 - header.payload.signature
            raise SignInRequiredError
        header = _json_segment(parts[0])
        if header.get("alg") != "ES256" or header.get("signer") != self.settings.alb_arn:
            raise SignInRequiredError
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise SignInRequiredError
        key = await self._keys.get(kid)
        _verify_signature(key, parts)

        # The load balancer puts the expiry in the header; claims come from Google.
        claims = _json_segment(parts[1])
        expires = header.get("exp")
        if expires is None:
            expires = claims.get("exp")
        current = time.time() if now is None else now
        if not isinstance(expires, int | float) or expires + EXPIRY_LEEWAY_SECONDS < current:
            raise SignInRequiredError

        email = claims.get("email")
        verified = claims.get("email_verified") in (True, "true")
        if not isinstance(email, str) or not verified:
            raise AccountNotAllowedError
        if email.strip().lower() != self.settings.allowed_email:
            raise AccountNotAllowedError
        return self.settings.allowed_email


def _verify_signature(key: ec.EllipticCurvePublicKey, parts: list[str]) -> None:
    """Check a JWS ES256 signature: raw r || s over ``header.payload``."""
    signature = _b64decode(parts[2])
    if len(signature) != 2 * _P256_COORDINATE_BYTES:
        raise SignInRequiredError
    r = int.from_bytes(signature[:_P256_COORDINATE_BYTES], "big")
    s = int.from_bytes(signature[_P256_COORDINATE_BYTES:], "big")
    try:
        key.verify(
            encode_dss_signature(r, s),
            f"{parts[0]}.{parts[1]}".encode(),
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as error:
        raise SignInRequiredError from error


def session_cookie_names(cookies: Mapping[str, str]) -> list[str]:
    """Every load balancer session cookie shard to expire on sign-out.

    The first shard is always included, so sign-out clears the session even when
    the browser did not send the cookie with this request.
    """
    names = {name for name in cookies if name.startswith(f"{ALB_SESSION_COOKIE}-")}
    names.add(f"{ALB_SESSION_COOKIE}-0")
    return sorted(names)
