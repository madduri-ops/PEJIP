"""Signs tokens the way PEJIP's load balancer does, for DAST and tests (ADR-0006).

The load balancer passes the signed-in user to the app in an ES256 JWT whose header
names the signing key (``kid``) and the load balancer (``signer``). This module makes
a throwaway key pair and signs such tokens, so CI can exercise the app's real
sign-in check without AWS or Google.

Usage::

    python -m ci.alb_token KEY_DIR EMAIL ALB_ARN

writes the public key to ``KEY_DIR/<kid>`` (serve the directory and point
``PEJIP_AUTH_KEY_URL`` at ``http://host/{kid}``) and prints a token for EMAIL that
is valid for an hour.
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

TOKEN_LIFETIME_SECONDS = 3600


def _b64(data: bytes, *, pad: bool = True) -> str:
    # The load balancer pads its base64url segments; do the same by default.
    encoded = base64.urlsafe_b64encode(data).decode()
    return encoded if pad else encoded.rstrip("=")


class AlbSigner:
    """A throwaway signing key standing in for the load balancer's."""

    def __init__(self, alb_arn: str, kid: str = "ci-key") -> None:
        self.alb_arn = alb_arn
        self.kid = kid
        self._key = ec.generate_private_key(ec.SECP256R1())

    def public_pem(self) -> bytes:
        """The public key in PEM, as AWS publishes it."""
        return self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def token(
        self,
        email: str,
        *,
        expires: float | None = None,
        header: dict[str, Any] | None = None,
        claims: dict[str, Any] | None = None,
        pad: bool = True,
    ) -> str:
        """Sign a token for ``email``.

        ``header`` and ``claims`` override fields; ``pad=False`` leaves out base64
        padding, as standard JWT libraries do.
        """
        exp = int(time.time() + TOKEN_LIFETIME_SECONDS if expires is None else expires)
        fields: dict[str, Any] = {
            "alg": "ES256",
            "kid": self.kid,
            "signer": self.alb_arn,
            "iss": "https://accounts.google.com",
            "client": "ci-client",
            "exp": exp,
        }
        fields.update(header or {})
        payload: dict[str, Any] = {
            "sub": "ci-subject",
            "email": email,
            "email_verified": True,
        }
        payload.update(claims or {})
        signing_input = ".".join(
            _b64(json.dumps(part).encode(), pad=pad) for part in (fields, payload)
        )
        der = self._key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return f"{signing_input}.{_b64(signature, pad=pad)}"


def main(argv: list[str] | None = None) -> int:
    """Write the public key and print a token. Returns the exit code."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:  # noqa: PLR2004 - KEY_DIR EMAIL ALB_ARN
        print("usage: python -m ci.alb_token KEY_DIR EMAIL ALB_ARN", file=sys.stderr)
        return 2
    key_dir, email, alb_arn = args
    signer = AlbSigner(alb_arn)
    Path(key_dir).mkdir(parents=True, exist_ok=True)
    (Path(key_dir) / signer.kid).write_bytes(signer.public_pem())
    print(signer.token(email))
    return 0


if __name__ == "__main__":
    sys.exit(main())
