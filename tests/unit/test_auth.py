"""Unit tests for the load balancer sign-in check (pejip.auth, ADR-0006)."""

import asyncio
import base64
import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from ci.alb_token import AlbSigner
from pejip.auth import (
    AccountNotAllowedError,
    Authenticator,
    AuthSettings,
    KeyStore,
    SignInRequiredError,
    session_cookie_names,
)
from tests.alb import ALB_ARN, ALLOWED_EMAIL

KEY_URL = "https://keys.test/{kid}"


def _store(responses: dict[str, httpx.Response]) -> tuple[KeyStore, list[str]]:
    """A KeyStore whose fetches are answered from ``responses`` by path."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return responses.get(request.url.path, httpx.Response(404))

    return KeyStore(KEY_URL, transport=httpx.MockTransport(handler)), calls


def _authenticator(signer: AlbSigner) -> Authenticator:
    store, _ = _store({f"/{signer.kid}": httpx.Response(200, content=signer.public_pem())})
    settings = AuthSettings(allowed_email=ALLOWED_EMAIL, alb_arn=ALB_ARN, key_url=KEY_URL)
    return Authenticator(settings, store)


def _verify(authenticator: Authenticator, token: str | None) -> str:
    return asyncio.run(authenticator.verify(token))


@pytest.fixture
def signer() -> AlbSigner:
    return AlbSigner(ALB_ARN)


# ── Settings ─────────────────────────────────────────────────────────────────
def test_settings_off_without_email_or_arn() -> None:
    assert AuthSettings.from_env({}) is None
    assert AuthSettings.from_env({"PEJIP_AUTH_ALLOWED_EMAIL": ALLOWED_EMAIL}) is None
    assert AuthSettings.from_env({"PEJIP_AUTH_ALB_ARN": ALB_ARN}) is None


def test_settings_derive_the_regional_key_url() -> None:
    settings = AuthSettings.from_env(
        {"PEJIP_AUTH_ALLOWED_EMAIL": " Owner@Example.com ", "PEJIP_AUTH_ALB_ARN": ALB_ARN}
    )

    assert settings == AuthSettings(
        allowed_email=ALLOWED_EMAIL,
        alb_arn=ALB_ARN,
        key_url="https://public-keys.auth.elb.us-west-2.amazonaws.com/{kid}",
    )


def test_settings_take_a_key_url_override() -> None:
    settings = AuthSettings.from_env(
        {
            "PEJIP_AUTH_ALLOWED_EMAIL": ALLOWED_EMAIL,
            "PEJIP_AUTH_ALB_ARN": ALB_ARN,
            "PEJIP_AUTH_KEY_URL": KEY_URL,
        }
    )

    assert settings is not None
    assert settings.key_url == KEY_URL


@pytest.mark.parametrize("arn", ["not-an-arn", "arn:aws:elasticloadbalancing::0:lb"])
def test_settings_reject_a_malformed_arn(arn: str) -> None:
    with pytest.raises(ValueError, match="not a load balancer ARN"):
        AuthSettings.from_env(
            {"PEJIP_AUTH_ALLOWED_EMAIL": ALLOWED_EMAIL, "PEJIP_AUTH_ALB_ARN": arn}
        )


# ── Tokens ───────────────────────────────────────────────────────────────────
def test_accepts_the_allowed_verified_email(signer: AlbSigner) -> None:
    assert _verify(_authenticator(signer), signer.token(ALLOWED_EMAIL)) == ALLOWED_EMAIL


def test_email_match_ignores_case(signer: AlbSigner) -> None:
    assert _verify(_authenticator(signer), signer.token("OWNER@example.COM")) == ALLOWED_EMAIL


def test_accepts_unpadded_segments(signer: AlbSigner) -> None:
    token = signer.token(ALLOWED_EMAIL, pad=False)

    assert "=" not in token
    assert _verify(_authenticator(signer), token) == ALLOWED_EMAIL


def test_accepts_email_verified_as_a_string(signer: AlbSigner) -> None:
    token = signer.token(ALLOWED_EMAIL, claims={"email_verified": "true"})

    assert _verify(_authenticator(signer), token) == ALLOWED_EMAIL


def test_claims_expiry_used_when_header_has_none(signer: AlbSigner) -> None:
    authenticator = _authenticator(signer)
    expired = signer.token(ALLOWED_EMAIL, header={"exp": None}, claims={"exp": 1})
    fresh = signer.token(ALLOWED_EMAIL, header={"exp": None}, claims={"exp": 2**40})

    with pytest.raises(SignInRequiredError):
        _verify(authenticator, expired)
    assert _verify(authenticator, fresh) == ALLOWED_EMAIL


@pytest.mark.parametrize("token", [None, "", "abc", "a.b", "a.b.c.d"])
def test_rejects_missing_or_malformed_tokens(signer: AlbSigner, token: str | None) -> None:
    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), token)


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "HS256"},
        {"alg": "none"},
        {"signer": "arn:aws:elasticloadbalancing:us-west-2:111111111111:loadbalancer/app/x/1"},
        {"kid": 7},
        {"kid": "../etc/passwd"},
        {"kid": "unknown-key"},
    ],
)
def test_rejects_wrong_header_fields(signer: AlbSigner, header: dict[str, object]) -> None:
    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), signer.token(ALLOWED_EMAIL, header=header))


def test_rejects_an_expired_token(signer: AlbSigner) -> None:
    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), signer.token(ALLOWED_EMAIL, expires=1))


def test_allows_small_clock_skew(signer: AlbSigner) -> None:
    authenticator = _authenticator(signer)
    token = signer.token(ALLOWED_EMAIL, expires=1000)

    assert asyncio.run(authenticator.verify(token, now=1030)) == ALLOWED_EMAIL
    with pytest.raises(SignInRequiredError):
        asyncio.run(authenticator.verify(token, now=1100))


def test_rejects_a_token_signed_by_another_key(signer: AlbSigner) -> None:
    impostor = AlbSigner(ALB_ARN, kid=signer.kid)

    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), impostor.token(ALLOWED_EMAIL))


def test_rejects_a_tampered_payload(signer: AlbSigner) -> None:
    header, _, signature = signer.token("someone@example.com").split(".")
    claims = {"email": ALLOWED_EMAIL, "email_verified": True}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()

    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), f"{header}.{payload}.{signature}")


@pytest.mark.parametrize("signature", ["AAAA", "!!!!"])
def test_rejects_a_malformed_signature(signer: AlbSigner, signature: str) -> None:
    header, payload, _ = signer.token(ALLOWED_EMAIL).split(".")

    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), f"{header}.{payload}.{signature}")


@pytest.mark.parametrize("segment", ["A", "!!!!", "bm90LWpzb24", "WzFd", "_w"])
def test_rejects_a_header_that_is_not_a_json_object(signer: AlbSigner, segment: str) -> None:
    _, payload, signature = signer.token(ALLOWED_EMAIL).split(".")

    with pytest.raises(SignInRequiredError):
        _verify(_authenticator(signer), f"{segment}.{payload}.{signature}")


def test_refuses_another_account(signer: AlbSigner) -> None:
    with pytest.raises(AccountNotAllowedError):
        _verify(_authenticator(signer), signer.token("someone@example.com"))


def test_refuses_an_unverified_email(signer: AlbSigner) -> None:
    with pytest.raises(AccountNotAllowedError):
        _verify(
            _authenticator(signer), signer.token(ALLOWED_EMAIL, claims={"email_verified": False})
        )


def test_refuses_a_token_without_email(signer: AlbSigner) -> None:
    with pytest.raises(AccountNotAllowedError):
        _verify(_authenticator(signer), signer.token(ALLOWED_EMAIL, claims={"email": None}))


# ── Key store ────────────────────────────────────────────────────────────────
def test_key_store_fetches_once_then_caches(signer: AlbSigner) -> None:
    store, calls = _store({"/k1": httpx.Response(200, content=signer.public_pem())})

    first = asyncio.run(store.get("k1"))
    second = asyncio.run(store.get("k1"))

    assert first is second
    assert calls == ["/k1"]


def test_key_store_cache_is_bounded(signer: AlbSigner) -> None:
    pem = signer.public_pem()
    store, calls = _store({f"/k{i}": httpx.Response(200, content=pem) for i in range(20)})

    for i in range(20):
        asyncio.run(store.get(f"k{i}"))
    asyncio.run(store.get("k0"))

    assert len(calls) == 21


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(200, content=b"not a key"),
    ],
)
def test_key_store_rejects_unusable_responses(response: httpx.Response) -> None:
    store, _ = _store({"/k": response})

    with pytest.raises(SignInRequiredError):
        asyncio.run(store.get("k"))


def test_key_store_rejects_a_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    store = KeyStore(KEY_URL, transport=httpx.MockTransport(handler))

    with pytest.raises(SignInRequiredError):
        asyncio.run(store.get("k"))


@pytest.mark.parametrize(
    "key",
    [
        rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key(),
        ec.generate_private_key(ec.SECP384R1()).public_key(),
    ],
)
def test_key_store_rejects_keys_that_are_not_p256(key: object) -> None:
    assert isinstance(key, rsa.RSAPublicKey | ec.EllipticCurvePublicKey)
    pem = key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    store, _ = _store({"/k": httpx.Response(200, content=pem)})

    with pytest.raises(SignInRequiredError):
        asyncio.run(store.get("k"))


def test_session_cookie_names_always_include_the_first_shard() -> None:
    assert session_cookie_names({}) == ["AWSELBAuthSessionCookie-0"]
    assert session_cookie_names(
        {"AWSELBAuthSessionCookie-2": "x", "AWSELBAuthSessionCookie": "y", "other": "z"}
    ) == ["AWSELBAuthSessionCookie-0", "AWSELBAuthSessionCookie-2"]
