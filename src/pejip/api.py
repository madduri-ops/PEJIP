"""HTTP surface of PEJIP.

It serves the health endpoint that the post-deploy gate and the load balancer poll,
and the web portal's pages (``pejip.portal``, design doc 0011). The system smoke
test and DAST exercise every route in the OpenAPI document automatically.

Every route except ``/healthz`` and the ranking routine's ``/api/ranking/*``
requires Babu's Google sign-in, checked by ``pejip.auth`` against the token the
load balancer adds (ADR-0006). The ranking routes need the routine's key instead
(``pejip.ranking_api``, design doc 0015).
"""

import os
from collections.abc import Awaitable, Callable, Mapping

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from pejip import __version__, portal
from pejip.auth import (
    OIDC_DATA_HEADER,
    PUBLIC_PATHS,
    AccountNotAllowedError,
    Authenticator,
    AuthSettings,
    SignInRequiredError,
)
from pejip.portal.data import PortalData
from pejip.portal.sample import SampleData
from pejip.ranking_api import RANKING_PREFIX, RankingService
from pejip.ranking_api import router as ranking_router

# Sent on every response. JSON responses get a CSP that denies everything; HTML
# pages get PAGE_CSP instead.
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}

# Portal pages: no script at all, styles only from the app and Google Fonts (the
# IBM Plex typefaces), forms post only back to the app.
PAGE_CSP = (
    "default-src 'none'; style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self'; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'"
)


def create_app(
    env: Mapping[str, str] | None = None,
    data: PortalData | None = None,
    ranking: RankingService | None = None,
) -> FastAPI:
    """Build the API. Interactive docs are off; the OpenAPI document stays for DAST.

    Sign-in settings come from ``env`` (the process environment by default). The
    portal reads ``data``, sample data by default until the database lands. The
    ranking routine's endpoints use ``ranking``, built from ``env`` by default.
    """
    app = FastAPI(title="PEJIP", version=__version__, docs_url=None, redoc_url=None)
    environment = os.environ if env is None else env
    settings = AuthSettings.from_env(environment)
    authenticator = Authenticator(settings) if settings else None

    # Registered before the security headers middleware, so refusals get them too.
    @app.middleware("http")
    async def require_sign_in(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # The ranking routine's routes check its own key instead (ranking_api).
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith(RANKING_PREFIX):
            return await call_next(request)
        if authenticator is None:
            return JSONResponse({"detail": "sign-in is not configured"}, status_code=503)
        try:
            await authenticator.verify(request.headers.get(OIDC_DATA_HEADER))
        except SignInRequiredError:
            return JSONResponse({"detail": "sign-in required"}, status_code=401)
        except AccountNotAllowedError:
            return JSONResponse({"detail": "this account is not allowed"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Content-Security-Policy"] = PAGE_CSP
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness check used by the load balancer and the post-deploy health gate."""
        return {"status": "ok", "version": __version__}

    app.include_router(portal.router(SampleData() if data is None else data))
    app.include_router(ranking_router(ranking or RankingService.from_env(environment)))
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
