"""The signed-in web portal: Home, Opportunities and Opportunity detail pages.

Built from the portal mocks (spec section 12, design doc 0011). Pages read through
:class:`pejip.portal.data.PortalData`; sample data stands in until the persistent
database lands.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from importlib.resources import files
from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import HTMLResponse, Response

from pejip.portal import render
from pejip.portal.data import PortalData
from pejip.portal.views import Filters, list_opportunities

STYLESHEET = files("pejip.portal").joinpath("static/portal.css").read_text(encoding="utf-8")

Clock = Callable[[], datetime]


def router(data: PortalData, clock: Clock | None = None) -> APIRouter:
    """The portal's routes, reading from ``data``."""
    now_fn = clock or (lambda: datetime.now(UTC))
    routes = APIRouter(tags=["portal"], default_response_class=HTMLResponse)

    def frame(  # noqa: PLR0913 - the parts of a page
        *, active: str, heading: str, subtitle: str, body: str, title: str = "", crumb: str = ""
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
    def home() -> str:
        """Home: what needs attention since the last search (spec 12.4)."""
        body = render.home_body(data.opportunities(), data.latest_run(), now_fn())
        return frame(
            active="home",
            heading="What needs your attention",
            subtitle="Ranked roles from the latest search.",
            body=body,
            title="Home",
        )

    @routes.get("/opportunities")
    def opportunities(  # noqa: PLR0913 - one parameter per filter
        *,
        view: Annotated[str, Query(max_length=32)] = "",
        priority: Annotated[str, Query(max_length=16)] = "",
        fit: Annotated[str, Query(max_length=8)] = "",
        confidence: Annotated[str, Query(max_length=16)] = "",
        company: Annotated[str, Query(max_length=100)] = "",
        work_model: Annotated[str, Query(max_length=16)] = "",
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
            }
        )
        listing = list_opportunities(data.opportunities(), filters)
        body = render.opportunities_body(listing, filters, now_fn())
        return frame(
            active="opportunities",
            heading="Opportunities",
            subtitle="Ranked by priority, then fit, then freshness.",
            body=body,
        )

    @routes.get("/opportunities/{opportunity_id}", responses={404: {"description": "Not found"}})
    def opportunity(
        opportunity_id: Annotated[int, Path(ge=1, openapi_examples={"first": {"value": 1}})],
    ) -> HTMLResponse:
        """One opportunity with its full, cited explanation (spec 12.8, 12.9)."""
        found = next((o for o in data.opportunities() if o.id == opportunity_id), None)
        if found is None:
            html = frame(
                active="opportunities",
                heading="Opportunity not found",
                subtitle="",
                body=render.not_found_body(),
            )
            return HTMLResponse(html, status_code=404)
        html = frame(
            active="opportunities",
            heading=found.title,
            subtitle=f"{found.company} · {found.location}",
            body=render.detail_body(found, now_fn()),
            crumb='<div class="crumb"><a href="/opportunities">Opportunities</a></div>',
        )
        return HTMLResponse(html)

    @routes.get("/portal.css", response_class=Response)
    def stylesheet() -> Response:
        """The portal's styles."""
        return Response(STYLESHEET, media_type="text/css")

    return routes
