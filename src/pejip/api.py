"""HTTP surface of PEJIP.

It serves the health endpoint that the post-deploy gate and the load balancer poll,
and the web portal's pages (``pejip.portal``, design doc 0011). The system smoke
test and DAST exercise every route in the OpenAPI document automatically.

Every route except ``/healthz`` and the ranking routine's ``/api/ranking/*``
requires Google sign-in, checked by ``pejip.auth`` against the token the load
balancer adds (ADR-0006); the signed-in account is kept on ``request.state.account``
for the routes to key data by (design doc 0016). The ranking routes need the routine's key instead
(``pejip.ranking_api``, design doc 0015).
"""

import logging
import os
from collections.abc import Awaitable, Callable, Mapping

import uvicorn
import yaml
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pejip import __version__, portal
from pejip.accounts import DEFAULT_ACCOUNT_ID, open_store, sqlite_path
from pejip.auth import (
    OIDC_DATA_HEADER,
    PUBLIC_PATHS,
    AccountNotAllowedError,
    Authenticator,
    AuthSettings,
    SignInRequiredError,
)
from pejip.companies import load_search_config
from pejip.config import SearchConfig, Settings, load_config
from pejip.portal.data import PortalData
from pejip.portal.sample import SampleData
from pejip.portal.stored import StoreData
from pejip.profile import make_ssm_client
from pejip.ranking_api import RANKING_PREFIX, RankingService, RankingServices, screen
from pejip.ranking_api import router as ranking_router
from pejip.store import Store

log = logging.getLogger(__name__)

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


def _search_config(env: Mapping[str, str], account: str) -> SearchConfig | None:
    """The search configuration Settings shows an account; None without the file.

    The account's private companies are included (ADR-0009, design doc 0016). If
    they can't be read, the page still opens with the shipped setup; the daily
    run reports the problem.
    """
    settings = Settings.from_env(dict(env), account=account)
    if not settings.config_path.is_file():
        return None
    try:
        config, _ = load_search_config(settings, make_ssm_client)
    except (OSError, ValidationError, yaml.YAMLError, ClientError, BotoCoreError):
        log.warning("company_list_unreadable")
        return load_config(settings.config_path)
    return config


def _portal_data(env: Mapping[str, str], account: str, config: SearchConfig | None) -> PortalData:
    """The account's database as the portal reads it (design doc 0013).

    An empty SQLite database is not created here: the account's first search run
    makes it, and until then the pages say no search has run. Babu's data from
    before accounts is adopted the same way a run adopts it (design doc 0016).
    """
    settings = Settings.from_env(dict(env), account=account)
    database = sqlite_path(settings.database_url)
    legacy = sqlite_path(settings.legacy_database_url or "")
    if database is not None and not database.is_file():
        if legacy is None or not legacy.is_file():
            return StoreData(None, config)
        return StoreData(open_store(settings), config)
    return StoreData(Store(settings.database_url), config)


def create_app(
    env: Mapping[str, str] | None = None,
    data: PortalData | None = None,
    ranking: RankingService | RankingServices | None = None,
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
    # One service per account; a single service given (tests) is Babu's.
    if isinstance(ranking, RankingService):
        ranking = RankingServices({DEFAULT_ACCOUNT_ID: ranking})
    ranking_service = ranking or RankingServices.from_env(environment)

    # The ranking routine's routes skip sign-in below and are screened here
    # instead, before any body is read (ranking_api.screen).
    @app.middleware("http")
    async def screen_ranking_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(RANKING_PREFIX):
            refused = screen(ranking_service, request)
            if refused is not None:
                return JSONResponse({"detail": refused.detail}, status_code=refused.status_code)
        return await call_next(request)

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
            request.state.account = await authenticator.verify(
                request.headers.get(OIDC_DATA_HEADER)
            )
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

    configs: dict[str, SearchConfig | None] = {}

    def config_for(account: str) -> SearchConfig | None:
        # Read once per account, as the shared config was before accounts.
        if account not in configs:
            configs[account] = _search_config(environment, account)
        return configs[account]

    stored: dict[str, PortalData] = {}

    def data_for(account: str) -> PortalData:
        # One reader per account, opened on its first page view.
        if account not in stored:
            stored[account] = _portal_data(environment, account, config_for(account))
        return stored[account]

    if data is not None:
        app.include_router(portal.router(data, config_for=config_for))
    elif "PEJIP_DATABASE_URL" in environment:
        app.include_router(portal.router(config_for=config_for, data_for=data_for))
    else:
        app.include_router(portal.router(SampleData(), config_for=config_for))
    app.include_router(ranking_router(ranking_service))
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
