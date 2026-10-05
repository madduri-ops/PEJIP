"""HTTP surface of PEJIP.

Today it serves only the health endpoint that the post-deploy gate and the load
balancer poll. Feature endpoints are added here as they land; the system smoke test
and DAST exercise every route in the OpenAPI document automatically.
"""

import os
from collections.abc import Awaitable, Callable

import uvicorn
from fastapi import FastAPI, Request, Response

from pejip import __version__

# Sent on every response. The API serves JSON only, so the CSP denies everything.
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def create_app() -> FastAPI:
    """Build the API. Interactive docs are off; the OpenAPI document stays for DAST."""
    app = FastAPI(title="PEJIP", version=__version__, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness check used by the load balancer and the post-deploy health gate."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()


def main() -> None:
    """Serve the API. Binds to localhost unless PEJIP_HOST says otherwise (containers)."""
    uvicorn.run(
        app,
        host=os.environ.get("PEJIP_HOST", "127.0.0.1"),
        port=int(os.environ.get("PEJIP_PORT", "8000")),
        server_header=False,
    )


if __name__ == "__main__":
    main()
