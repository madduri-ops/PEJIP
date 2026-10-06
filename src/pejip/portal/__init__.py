"""The signed-in web portal: Home, Opportunities, Opportunity detail and Search Health.

Built from the portal mocks (spec section 12, design doc 0011). Pages read through
:class:`pejip.portal.data.PortalData`; sample data stands in until the persistent
database lands.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from importlib.resources import files
from typing import Annotated
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from pejip.accounts import DEFAULT_ACCOUNT_ID, alert_address
from pejip.auth import session_cookie_names
from pejip.config import SearchConfig
from pejip.portal import render
from pejip.portal.data import DECISIONS, Decisions, PortalData, SearchSettings
from pejip.portal.views import (
    MAX_COMPANY_FILTER,
    MAX_PEOPLE_QUERY,
    Filters,
    PeopleFilters,
    find_people,
    list_companies,
    list_opportunities,
    matured_roles,
    referral_paths,
    watchlist,
)
from pejip.search_settings import SettingsError, SettingsForm, current

# A decision form sends one short field; anything bigger is not from the page.
MAX_FORM_BYTES = 256
# The Settings form: a few hundred short terms at most (search_settings.MAX_TERMS).
MAX_SETTINGS_BYTES = 64 * 1024


def same_origin(request: Request) -> bool:
    """True when the form was sent by a page on this site (the CSRF check).

    Browsers mark every request with ``Sec-Fetch-Site``, which no page can set or
    change, so it decides when present. It must: the pages send
    ``Referrer-Policy: no-referrer``, under which browsers send ``Origin: null``
    with a form post even from this site, so Origin alone refused Babu's own saves.
    Without it (older browsers, scripts), Origin must match the Host header, which
    the load balancer keeps; a post from another site, which still carries the
    sign-in cookie, has an Origin that does not match.
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site == "same-origin"
    origin = request.headers.get("origin")
    return origin is not None and urlsplit(origin).netloc == request.headers.get("host")


STYLESHEET = files("pejip.portal").joinpath("static/portal.css").read_text(encoding="utf-8")

Clock = Callable[[], datetime]


def router(  # noqa: PLR0913 - each data source is optional
    data: PortalData | None = None,
    clock: Clock | None = None,
    *,
    config: SearchConfig | None = None,
    config_for: Callable[[str], SearchConfig | None] | None = None,
    data_for: Callable[[str], PortalData] | None = None,
    search_settings: SearchSettings | None = None,
) -> APIRouter:
    """The portal's routes, reading the signed-in account's ``data_for``, else ``data``.

    Settings shows the signed-in account's search setup from ``config_for``
    (design doc 0016), or ``config`` where no account-aware source is given. With
    ``search_settings`` its search fields can be edited and saved (design doc 0017).
    """
    now_fn = clock or (lambda: datetime.now(UTC))
    routes = APIRouter(tags=["portal"], default_response_class=HTMLResponse)

    def account_of(request: Request) -> str:
        signed_in = getattr(request.state, "account", None)
        return signed_in.id if signed_in is not None else DEFAULT_ACCOUNT_ID

    def account_data(request: Request) -> PortalData:
        """Each page reads only the signed-in account's data (design doc 0016)."""
        if data_for is not None:
            return data_for(account_of(request))
        if data is None:
            msg = "the portal needs data or data_for"
            raise ValueError(msg)
        return data

    AccountData = Annotated[PortalData, Depends(account_data)]  # noqa: N806 - a type alias

    def frame(  # noqa: PLR0913 - the parts of a page
        *,
        data: PortalData,
        active: str,
        heading: str,
        subtitle: str,
        body: str,
        title: str = "",
        crumb: str = "",
    ) -> str:
        items = data.opportunities()
        return render.page(
            title=title or heading,
            active=active,
            heading=heading,
            subtitle=subtitle,
            body=body,
            run=data.latest_run(),
            now=now_fn(),
            sample=data.is_sample,
            attention=sum(o.priority in ("IMMEDIATE", "HIGH") for o in items),
            before_heading=crumb,
        )

    @routes.get("/")
    def home(data: AccountData) -> str:
        """Home: what needs attention since the last search (spec 12.4)."""
        body = render.home_body(data.opportunities(), data.latest_run(), now_fn())
        return frame(
            data=data,
            active="home",
            heading="What needs your attention",
            subtitle="Ranked roles from the latest search.",
            body=body,
            title="Home",
        )

    @routes.get("/opportunities")
    def opportunities(  # noqa: PLR0913 - one parameter per filter
        *,
        data: AccountData,
        view: Annotated[str, Query(max_length=32)] = "",
        priority: Annotated[str, Query(max_length=16)] = "",
        fit: Annotated[str, Query(max_length=8)] = "",
        confidence: Annotated[str, Query(max_length=16)] = "",
        company: Annotated[str, Query(max_length=100)] = "",
        work_model: Annotated[str, Query(max_length=16)] = "",
        scope: Annotated[str, Query(max_length=16)] = "",
        age: Annotated[str, Query(max_length=4)] = "",
        network: Annotated[str, Query(max_length=16)] = "",
        pay: Annotated[str, Query(max_length=16)] = "",
    ) -> str:
        """Every active opportunity, by view and filters (spec 12.6, 12.7)."""
        filters = Filters.from_query(
            {
                "view": view,
                "priority": priority,
                "fit": fit,
                "confidence": confidence,
                "company": company,
                "work_model": work_model,
                "scope": scope,
                "age": age,
                "network": network,
                "pay": pay,
            }
        )
        listing = list_opportunities(data.opportunities(), filters, now_fn())
        body = render.opportunities_body(listing, filters, now_fn())
        return frame(
            data=data,
            active="opportunities",
            heading="Opportunities",
            subtitle="Ranked by priority, then fit, then freshness.",
            body=body,
        )

    @routes.get("/opportunities/{opportunity_id}", responses={404: {"description": "Not found"}})
    def opportunity(
        data: AccountData,
        opportunity_id: Annotated[int, Path(ge=1, openapi_examples={"first": {"value": 1}})],
    ) -> HTMLResponse:
        """One opportunity with its full, cited explanation (spec 12.8, 12.9)."""
        items = data.opportunities()
        found = next((o for o in items if o.id == opportunity_id), None)
        if found is None:
            html = frame(
                data=data,
                active="opportunities",
                heading="Opportunity not found",
                subtitle="",
                body=render.not_found_body(),
            )
            return HTMLResponse(html, status_code=404)
        html = frame(
            data=data,
            active="opportunities",
            heading=found.title,
            subtitle=f"{found.company} · {found.location}",
            body=render.detail_body(
                found,
                now_fn(),
                company=next((c for c in data.companies() if c.name == found.company), None),
                open_roles=sum(1 for o in items if o.company == found.company),
                decide=isinstance(data, Decisions) and not data.is_sample,
            ),
            crumb='<div class="crumb"><a href="/opportunities">Opportunities</a></div>',
        )
        return HTMLResponse(html)

    _add_decision_route(routes, account_data)

    @routes.get("/connections")
    def connections(
        data: AccountData,
        q: Annotated[str, Query(max_length=MAX_PEOPLE_QUERY)] = "",
        company: Annotated[str, Query(max_length=MAX_COMPANY_FILTER)] = "",
        matured: Annotated[str, Query(max_length=1)] = "",
    ) -> str:
        """Who Babu knows at the companies that matter (spec 8.20 to 8.26)."""
        items = data.opportunities()
        network = data.network()
        filters = PeopleFilters(query=q, company=company or None, matured=matured == "1")
        body = render.connections_body(
            network,
            paths=referral_paths(items),
            matured_roles=matured_roles(items),
            people=find_people(network, items, filters) if network else [],
            filters=filters,
            now=now_fn(),
        )
        return frame(
            data=data,
            active="connections",
            heading="Connections",
            subtitle="Who you know at the companies you are tracking, from your LinkedIn export.",
            body=body,
        )

    @routes.get("/companies")
    def companies(data: AccountData, view: Annotated[str, Query(max_length=16)] = "all") -> str:
        """Companies that matter, whether or not they are hiring today (spec 12.18)."""
        listing = list_companies(data.companies(), data.opportunities(), view)
        return frame(
            data=data,
            active="companies",
            heading="Companies",
            subtitle="Companies that matter to your career, whether or not they have a "
            "matching opening today.",
            body=render.companies_body(listing, now_fn()),
        )

    @routes.get("/watchlist")
    def watched(data: AccountData) -> str:
        """What changed in watched jobs and companies (spec 12.22)."""
        listing = watchlist(data.companies(), data.opportunities(), now_fn())
        return frame(
            data=data,
            active="watchlist",
            heading="Watchlist",
            subtitle="What changed in the jobs and companies you are watching.",
            body=render.watchlist_body(listing, now_fn()),
        )

    def config_of(account: str) -> SearchConfig | None:
        return config_for(account) if config_for is not None else config

    _add_settings_routes(
        routes,
        frame=frame,
        account_of=account_of,
        account_data=account_data,
        config_of=config_of,
        search_settings=search_settings,
    )

    @routes.get("/search-health")
    def search_health(data: AccountData) -> str:
        """Search Health: what each recent run searched and what failed (spec 12.27)."""
        return frame(
            data=data,
            active="search-health",
            heading="Search Health",
            subtitle="Did the searches cover everything they should?",
            body=render.search_health_body(data.recent_runs(), now_fn()),
        )

    _add_session_routes(routes)
    return routes


def _add_session_routes(routes: APIRouter) -> None:
    """Routes that read no account data: Sign out, where it lands, and the styles."""

    # GET too, out of the API schema: after an expired session, Google sends the
    # browser back to /signout as a GET once it has signed in again.
    @routes.get("/signout", response_class=Response, include_in_schema=False)
    @routes.post("/signout", response_class=Response)
    def sign_out(request: Request) -> Response:
        """Expire the load balancer's sign-in session, then show the signed-out page.

        Google has no sign-out endpoint for a single site, so this ends PEJIP's session
        only; Babu stays signed in to Google itself (ADR-0006).
        """
        response = RedirectResponse("/signed-out", status_code=303)
        for name in session_cookie_names(request.cookies):
            response.delete_cookie(name, path="/", secure=True, httponly=True)
        return response

    @routes.get("/signed-out")
    def signed_out() -> str:
        """Where Sign out lands. Open without sign-in, so it shows no data."""
        return render.signed_out_page()

    @routes.get("/portal.css", response_class=Response)
    def stylesheet() -> Response:
        """The portal's styles."""
        return Response(STYLESHEET, media_type="text/css")


def _add_decision_route(routes: APIRouter, account_data: Callable[[Request], PortalData]) -> None:
    """The form the role page's decision buttons post to."""

    @routes.post(
        "/opportunities/{opportunity_id}/decision",
        response_class=Response,
        responses={303: {"description": "Back to the role"}, 403: {}, 404: {}, 422: {}},
    )
    async def decide(
        request: Request,
        data: Annotated[PortalData, Depends(account_data)],
        opportunity_id: Annotated[int, Path(ge=1)],
    ) -> Response:
        """Record Babu's decision about a role (spec 10.2), then show the role again."""
        if not same_origin(request):
            return Response("Forms are only accepted from this site.", status_code=403)
        body = await request.body()
        fields = (
            parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
            if len(body) <= MAX_FORM_BYTES
            else {}
        )
        choice = fields.get("decision", [None])[0]  # "" clears the decision
        if choice is None or choice not in {*DECISIONS, ""}:
            return Response("Not a decision this page offers.", status_code=422)
        if not isinstance(data, Decisions) or not data.decide(opportunity_id, choice or None):
            return Response("Opportunity not found.", status_code=404)
        return RedirectResponse(f"/opportunities/{opportunity_id}#decision", status_code=303)


Frame = Callable[..., str]


def _add_settings_routes(  # noqa: PLR0913 - what the Settings routes read
    routes: APIRouter,
    *,
    frame: Frame,
    account_of: Callable[[Request], str],
    account_data: Callable[[Request], PortalData],
    config_of: Callable[[str], SearchConfig | None],
    search_settings: SearchSettings | None,
) -> None:
    """Settings, and the form that saves its search fields (spec 12.35, design doc 0017)."""
    AccountData = Annotated[PortalData, Depends(account_data)]  # noqa: N806 - a type alias

    def settings_page(
        request: Request,
        data: PortalData,
        *,
        form: SettingsForm | None = None,
        error: str = "",
        saved: bool = False,
    ) -> str:
        account = account_of(request)
        shown = config_of(account)
        editing = None
        if search_settings is not None and shown is not None:
            editing = render.SettingsEditing(
                form=form or SettingsForm.of(current(shown)),
                saved_at=search_settings.saved_at(account),
                error=error,
                just_saved=saved,
            )
        return frame(
            data=data,
            active="settings",
            heading="Settings",
            subtitle="What PEJIP searches for, when, and how it ranks.",
            body=render.settings_body(shown, alert_address(account), editing),
        )

    @routes.get("/settings")
    def settings(
        request: Request, data: AccountData, saved: Annotated[str, Query(max_length=1)] = ""
    ) -> str:
        """What PEJIP searches for, when, and how it ranks (spec 12.35)."""
        return settings_page(request, data, saved=saved == "1")

    @routes.post(
        "/settings",
        response_class=Response,
        responses={303: {"description": "Back to Settings"}, 403: {}, 404: {}, 413: {}, 422: {}},
    )
    async def save_settings(request: Request, data: AccountData) -> Response:
        """Save the account's search settings, or go back to the defaults (design doc 0017)."""
        if not same_origin(request):
            return Response("Forms are only accepted from this site.", status_code=403)
        account = account_of(request)
        shown = config_of(account)
        if search_settings is None or shown is None:
            return Response("Settings can't be changed on this server.", status_code=404)
        body = await request.body()
        if len(body) > MAX_SETTINGS_BYTES:
            return Response("That is more than the Settings form sends.", status_code=413)
        fields = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        if fields.get("action", [""])[0] == "reset":
            search_settings.save(account, None)
            return RedirectResponse("/settings?saved=1", status_code=303)
        form = SettingsForm.posted(fields, list(shown.geography.scopes))
        try:
            parsed = form.parse(render.SCOPE_LABEL)
        except SettingsError as exc:
            page = settings_page(request, data, form=form, error=str(exc))
            return HTMLResponse(page, status_code=422)
        search_settings.save(account, parsed)
        return RedirectResponse("/settings?saved=1", status_code=303)
