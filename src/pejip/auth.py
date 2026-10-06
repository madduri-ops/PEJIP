"""Sign-in check for requests that reach PEJIP through the load balancer (ADR-0006).

The load balancer signs the user in with Google before it forwards a request,
then passes the signed-in user's claims in the ``x-amzn-oidc-data`` header: a JWT
the load balancer signs with ES256 (a P-256 key whose public half AWS publishes
per region by key id). The app trusts a request only when that token is signed by
the load balancer PEJIP runs behind, has not expired, and names a Google-verified
email address in the account registry. The request then belongs to that account
(design doc 0016). Everything except ``/healthz`` requires it, so a request that
skips the load balancer, or a Google account not in the registry, gets nothing.

The registry holds at most :data:`MAX_ACCOUNTS` accounts. Each one adds work to
every scheduled run and a digest topic, so the cap keeps the shared site's cost
known; raising it is a deliberate change.

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

from pejip.accounts import ACCOUNT_ID_PATTERN, DEFAULT_ACCOUNT_ID

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

# Every account has its own storage, inbox, digest and ranking key (design doc 0016).
MAX_ACCOUNTS = 5


class SignInRequiredError(Exception):
    """The request carries no valid token from PEJIP's load balancer (401)."""


class AccountNotAllowedError(Exception):
    """A valid token for an email that is not in the account registry (403)."""


@dataclass(frozen=True)
class Account:
    """A signed-in person: a short id that keys their data, and their Google email."""

    id: str
    email: str


def parse_accounts(value: str) -> tuple[Account, ...]:
    """Read the registry: comma-separated ``id=email`` pairs.

    Ids must be plain (lowercase letters, digits and dashes, starting with a
    letter) and unique; emails are compared without case and must be unique too.
    The error never repeats an email, since the message may reach the logs.
    """
    accounts: list[Account] = []
    for entry in value.split(","):
        if not entry.strip():
            continue
        account_id, separator, email = entry.partition("=")
        account_id, email = account_id.strip(), email.strip().lower()
        if not separator or not ACCOUNT_ID_PATTERN.fullmatch(account_id) or "@" not in email:
            msg = "PEJIP_AUTH_ACCOUNTS entries must be id=email"
            raise ValueError(msg)
        accounts.append(Account(account_id, email))
    if len({a.id for a in accounts}) != len(accounts):
        msg = "PEJIP_AUTH_ACCOUNTS repeats an account id"
        raise ValueError(msg)
    if len({a.email for a in accounts}) != len(accounts):
        msg = "PEJIP_AUTH_ACCOUNTS repeats an email"
        raise ValueError(msg)
    return tuple(accounts)


@dataclass(frozen=True)
class AuthSettings:
    """Who may sign in, and how their token is checked."""

    accounts: tuple[Account, ...]
    alb_arn: str
    key_url: str

    def account_for(self, email: str) -> Account | None:
        """The account a verified email signs in as, if any."""
        wanted = email.strip().lower()
        return next((a for a in self.accounts if a.email == wanted), None)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AuthSettings | None":
        """Read the settings, or None when sign-in is not configured.

        ``PEJIP_AUTH_ACCOUNTS`` (``id=email`` pairs) and ``PEJIP_AUTH_ALB_ARN`` turn
        it on; the ECS task definition sets both. ``PEJIP_AUTH_ALLOWED_EMAIL`` alone
        still works, as account ``babu``, so an older task definition keeps signing
        in after a rollback. ``PEJIP_AUTH_KEY_URL`` overrides where signing keys
        are fetched (``{kid}`` is replaced by the key id); tests use it.
        """
        accounts = parse_accounts(env.get("PEJIP_AUTH_ACCOUNTS", ""))
        if not accounts:
            email = env.get("PEJIP_AUTH_ALLOWED_EMAIL", "").strip()
            accounts = parse_accounts(f"{DEFAULT_ACCOUNT_ID}={email}") if email else ()
        alb_arn = env.get("PEJIP_AUTH_ALB_ARN", "").strip()
        if not accounts or not alb_arn:
            return None
        if len(accounts) > MAX_ACCOUNTS:
            msg = f"at most {MAX_ACCOUNTS} accounts may sign in"
            raise ValueError(msg)
        arn_parts = alb_arn.split(":")
        if len(arn_parts) < 6 or not arn_parts[3]:  # noqa: PLR2004 - arn:partition:service:region:account:resource
            msg = "PEJIP_AUTH_ALB_ARN is not a load balancer ARN"
            raise ValueError(msg)
        default_url = ALB_KEY_URL.replace("{region}", arn_parts[3])
        return cls(
            accounts=accounts,
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
    """Checks the load balancer's token and returns the signed-in account."""

    def __init__(self, settings: AuthSettings, keys: KeyStore | None = None) -> None:
        self.settings = settings
        self._keys = keys or KeyStore(settings.key_url)

    async def verify(self, token: str | None, now: float | None = None) -> Account:
        """Return the signed-in account, or raise if the token does not prove one."""
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
        account = self.settings.account_for(email)
        if account is None:
            raise AccountNotAllowedError
        return account


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
