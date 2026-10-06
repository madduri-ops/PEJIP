"""Shared helpers for tests of the load balancer sign-in check (ADR-0006)."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ci.alb_token import AlbSigner

ALB_ARN = "arn:aws:elasticloadbalancing:us-west-2:000000000000:loadbalancer/app/test/0"
ALLOWED_EMAIL = "owner@example.com"
ACCOUNT_ID = "babu"


def auth_env(key_url: str) -> dict[str, str]:
    """Environment that turns sign-in on against a test key server."""
    return {
        "PEJIP_AUTH_ACCOUNTS": f"{ACCOUNT_ID}={ALLOWED_EMAIL}",
        "PEJIP_AUTH_ALB_ARN": ALB_ARN,
        "PEJIP_AUTH_KEY_URL": key_url,
    }


@contextmanager
def key_server(signer: AlbSigner) -> Iterator[str]:
    """Serve ``signer``'s public key over HTTP; yields the ``{kid}`` URL template."""
    pem = signer.public_pem()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == f"/{signer.kid}":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(pem)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            """Keep test output quiet."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/{{kid}}"
    finally:
        server.shutdown()
        server.server_close()
