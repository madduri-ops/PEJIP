"""HTML for the portal pages, following the mocks' style guide (spec section 12).

Pages are built from small functions so each part of a mock maps to one place to
change. Every value from the data source goes through :func:`e` (HTML escaping), and
the pages carry no inline script or style, so the strict content security policy in
``pejip.api`` holds.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from html import escape
from urllib.parse import quote

from pejip.config import SearchConfig
from pejip.portal.data import Citation, Opportunity, Point, SearchRun, Signal, SourceStatus
from pejip.portal.views import (
    AGE_CHOICES,
    COMPANY_VIEWS,
    CONFIDENCE_CHOICES,
    FIT_CHOICES,
    NETWORK_CHOICES,
    PAY_CHOICES,
    PRIORITY_CHOICES,
    SCOPE_CHOICES,
    SHOWN_BANDS,
    VIEWS,
    WORK_MODEL_CHOICES,
    CompanyListing,
    CompanyRow,
    Filters,
    Listing,
    Watchlist,
    age,
    latest_signal,
    rank,
    when,
)

FONTS = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600"
    "&family=IBM+Plex+Serif:wght@500;600&display=swap"
)
PRIORITY_PILL = {"IMMEDIATE": "p-imm", "HIGH": "p-high", "EXCLUDED": "p-fail"}
STATUS_CLASS = {"SUCCESS": "ok", "PARTIAL": "partial"}
COMPONENT_LABEL = {
    "ROLE_RESPONSIBILITY": "Role / responsibility",
    "SENIORITY_SCOPE": "Seniority / scope",
    "CAPABILITY": "Capability",
    "LEADERSHIP": "Leadership",
    "CAREER_DIRECTION": "Career direction",
    "DOMAIN_INDUSTRY": "Domain / industry",
}
FIELD_LABEL = {
    "posted_at": "Employer posting date",
    "first_seen_at": "Date PEJIP first saw the role",
    "location": "Stated location",
    "comp_min": "Stated pay",
    "comp_max": "Stated pay",
}
# Concern kinds by how ``pejip.explain`` words them (mock: Concerns and gaps).
CONCERN_KIND = (
    ("Gap:", "k-gap", "Real gap"),
    ("The posting does not state", "k-miss", "Missing information"),
    ("Not enough profile evidence", "k-unk", "Unknown"),
)
LOW_COMPONENT = 0.85
SCOPE_LABEL = {"BAY_AREA": "San Francisco Bay Area", "US_REMOTE": "United States remote"}
AGE_LABEL = {1: "Last 24 hours", 3: "Last 3 days", 7: "Last week", 30: "Last 30 days"}
NETWORK_LABEL = {
    "connected": "Has connections",
    "none": "No connections",
    "unknown": "Not imported yet",
}
PAY_LABEL = {"published": "Pay published", "unpublished": "Pay not published"}
# Navigation in spec order (12.1): (key, label, link), with no link while a page is
# still to come.
NAV = (
    ("home", "Home", "/"),
    ("opportunities", "Opportunities", "/opportunities"),
    ("companies", "Companies", "/companies"),
    ("watchlist", "Watchlist", "/watchlist"),
    ("connections", "Connections", None),
    ("search-health", "Search Health", "/search-health"),
    ("settings", "Settings", "/settings"),
)


def e(value: object) -> str:
    """Escape text for HTML element content and quoted attributes."""
    return escape(str(value), quote=True)


def words(code: str) -> str:
    """IMMEDIATE -> Immediate, NEW_POSTING -> New posting."""
    return code.replace("_", " ").capitalize()


def opportunity_url(o: Opportunity) -> str:
    return f"/opportunities/{o.id}"


# ── Page frame ───────────────────────────────────────────────────────────────
def _nav(active: str, attention: int) -> str:
    def link(key: str, label: str, href: str | None) -> str:
        if href is None:
            return f'<span class="nl off">{label}<span class="soon">Soon</span></span>'
        on = " on" if key == active else ""
        current = ' aria-current="page"' if key == active else ""
        count = attention if key == "opportunities" else 0
        badge = f'<span class="count">{count}</span>' if count else ""
        return f'<a class="nl{on}" href="{href}"{current}>{label}{badge}</a>'

    return (
        '<nav class="nav" aria-label="Main">'
        '<div class="brand">PEJIP</div>'
        '<div class="brand-sub">Executive Job Intelligence</div>'
        + "".join(link(*item) for item in NAV)
        + '<div class="foot">Signed in with Google</div></nav>'
    )


def _status(status: str) -> str:
    return f'<span class="{STATUS_CLASS.get(status, "fail")}">{e(status)}</span>'


def run_line(run: SearchRun | None, now: datetime) -> str:
    if run is None:
        return '<div class="run"><span>No search has run yet</span></div>'
    return (
        f'<div class="run"><span>Last search: {when(run.started_at, now)} · '
        f"{_status(run.status)}</span>"
        f"<span>Next: {when(run.next_run_at, now) if run.next_run_at else 'Not scheduled'}"
        "</span></div>"
    )


def page(  # noqa: PLR0913 - the frame every page shares
    *,
    title: str,
    active: str,
    heading: str,
    subtitle: str,
    body: str,
    run: SearchRun | None,
    now: datetime,
    sample: bool,
    attention: int,
    before_heading: str = "",
) -> str:
    banner = (
        '<div class="sample">Sample data until the database is connected. Companies, '
        "people and numbers are illustrative.</div>"
        if sample
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>PEJIP · {e(title)}</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="stylesheet" href="{e(FONTS)}">'
        '<link rel="stylesheet" href="/portal.css"></head><body>'
        f'<div class="shell">{_nav(active, attention)}'
        f'<main class="main"><div class="wrap">{before_heading}'
        f'<div class="topbar"><div><h1>{e(heading)}</h1>'
        f'<div class="muted">{e(subtitle)}</div></div>{run_line(run, now)}</div>'
        f"{banner}{body}</div></main></div></body></html>"
    )


# ── Building blocks ──────────────────────────────────────────────────────────
def priority_pill(priority: str) -> str:
    return f'<span class="pill {PRIORITY_PILL.get(priority, "p-med")}">{e(words(priority))}</span>'


def fit_block(o: Opportunity, link: bool = True) -> str:
    if o.fit is None:
        return '<div><div class="fitl">Fit</div><div class="unk">Unknown</div></div>'
    score = f"{o.fit:.0f}"
    label = f'<a href="{opportunity_url(o)}#fit">Why {score}</a>' if link else "Fit"
    return f'<div><div class="fit">{score}</div><div class="fitl">{label}</div></div>'


def _connections(o: Opportunity) -> str:
    if o.connections is None:
        return '<span class="unk">Network: Unknown</span>'
    count = len(o.connections)
    if not count:
        return "<span>No connections</span>"
    return f"<span>{count} connection{'' if count == 1 else 's'}</span>"


def _meta(o: Opportunity, now: datetime) -> str:
    place = e(o.location) + (f" · {e(o.work_model)}" if o.work_model else "")
    pay = (
        f"<span>{e(o.compensation)}</span>"
        if o.compensation
        else '<span class="unk">Compensation: Not published</span>'
    )
    posted = f"Posted {age(o.posted_at, now)} · " if o.posted_at else ""
    flags = ""
    if o.discovery != "PREVIOUSLY_SEEN":
        flags += f'<span class="chip">{e(o.discovery.replace("_", " "))}</span>'
    if o.watched:
        flags += '<span class="state">WATCHING</span>'
    return (
        f'<div class="row meta"><span>Confidence: <strong>{e(o.confidence)}</strong></span>'
        f"<span>{place}</span>{pay}"
        f"<span>{posted}first seen {age(o.first_seen_at, now)}</span>"
        f"{_connections(o)}{flags}</div>"
    )


def _first(points: tuple[Point, ...]) -> str | None:
    return points[0].text if points else None


def _why(o: Opportunity, compact: bool = False) -> str:
    parts = [
        ("", "Why it fits", _first(o.why_it_fits)),
        ("", "Why now", None if compact else _first(o.why_now)),
        (' class="concern"', "Concern", _first(o.concerns)),
    ]
    cells = "".join(
        f'<div{cls}><span class="lbl">{label}</span>{e(text)}</div>'
        for cls, label, text in parts
        if text
    )
    one = " one" if compact else ""
    return f'<div class="why{one}">{cells}</div>' if cells else ""


def card(o: Opportunity, now: datetime, label: str = "") -> str:
    """The opportunity card (spec 12.5), used wherever a role is listed in full."""
    hot = " hot" if o.priority == "IMMEDIATE" else ""
    tag = f'<span class="lbl">{e(label)}</span>' if label else ""
    return (
        f'<article class="card{hot}">{tag}<div class="row spread"><div>'
        f'<a class="title" href="{opportunity_url(o)}">{e(o.title)}</a>'
        f'<div class="co">{e(o.company)}</div></div>'
        f'<div class="row">{priority_pill(o.priority)}{fit_block(o)}</div></div>'
        f"{_meta(o, now)}{_why(o)}"
        f'<div class="actions"><a class="btn primary" href="{opportunity_url(o)}">'
        "View details</a></div></article>"
    )


def mini_card(o: Opportunity, now: datetime) -> str:
    """A compact card for grids of new matches."""
    place = e(o.location) + (f" · {e(o.work_model)}" if o.work_model else "")
    return (
        f'<article class="card"><div class="row spread">{priority_pill(o.priority)}'
        f"{fit_block(o)}</div><div>"
        f'<a class="title" href="{opportunity_url(o)}">{e(o.title)}</a>'
        f'<div class="co">{e(o.company)}</div></div>'
        f'<div class="meta">Confidence: <strong>{e(o.confidence)}</strong> · {place} · '
        f"first seen {age(o.first_seen_at, now)}</div>{_why(o, compact=True)}</article>"
    )


def _section(heading: str, body: str, link: tuple[str, str] | None = None) -> str:
    more = f'<a href="{link[0]}">{e(link[1])}</a>' if link else ""
    return f'<section><div class="hrow"><h2>{e(heading)}</h2>{more}</div>{body}</section>'


def _empty(text: str) -> str:
    return f'<div class="empty">{e(text)}</div>'


# ── Home ─────────────────────────────────────────────────────────────────────
def home_body(items: list[Opportunity], run: SearchRun | None, now: datetime) -> str:
    """Executive dashboard: counts, what needs attention, new matches, changes, health."""
    items = rank(items)
    attention = [o for o in items if o.priority in ("IMMEDIATE", "HIGH")]
    new = [
        o
        for o in items
        if o.discovery == "NEW_POSTING" and o not in attention and o.priority in SHOWN_BANDS
    ]
    changed = [o for o in items if o.discovery == "MATERIALLY_CHANGED"]
    tiles = (
        ("immediate", "Immediate", sum(o.priority == "IMMEDIATE" for o in items), " imm"),
        ("attention", "High priority", sum(o.priority == "HIGH" for o in items), ""),
        ("new", "New postings", sum(o.discovery == "NEW_POSTING" for o in items), ""),
        ("changed", "Roles that changed", len(changed), ""),
        ("watched", "Watched roles", sum(o.watched for o in items), ""),
    )
    tile_html = "".join(
        f'<a class="tile{cls}" href="/opportunities?view={key}">'
        f'<div class="n">{count}</div><div class="l">{label}</div></a>'
        for key, label, count, cls in tiles
    )
    attention_html = (
        '<div class="stackl">' + "".join(card(o, now) for o in attention) + "</div>"
        if attention
        else _empty("Nothing needs your attention right now.")
    )
    new_html = (
        '<div class="grid3">' + "".join(mini_card(o, now) for o in new[:3]) + "</div>"
        if new
        else _empty("No other new postings since the last search.")
    )
    changed_html = (
        '<div class="list">'
        + "".join(
            f'<div class="li"><div class="grow">'
            f'<a class="title" href="{opportunity_url(o)}">{e(o.title)}</a>'
            f'<div class="muted">{e(o.company)}</div></div>'
            f'<span class="chip">{e(o.change_note or "Posting changed")}</span></div>'
            for o in changed
        )
        + "</div>"
        if changed
        else _empty("No role changed since the last search.")
    )
    return (
        f'<section aria-label="Summary"><div class="tiles">{tile_html}</div></section>'
        + _section("Requires your attention", attention_html)
        + _section("New strong matches", new_html, ("/opportunities?view=new", "See all new"))
        + '<div class="grid2">'
        + _section("Roles that changed", changed_html, ("/opportunities?view=changed", "See all"))
        + _section("Search health", health_card(run, now), ("/search-health", "Details"))
        + "</div>"
    )


def health_card(run: SearchRun | None, now: datetime) -> str:
    if run is None:
        return _empty("No search has run yet.")
    nxt = when(run.next_run_at, now) if run.next_run_at else "Not scheduled"
    return (
        '<div class="card"><div class="row">'
        f'<div><span class="lbl">Last search</span>{when(run.started_at, now)} · '
        f"{_status(run.status)}</div>"
        f'<div><span class="lbl">Sources</span>{run.sources_searched} of '
        f"{run.sources_total} searched</div>"
        f'<div><span class="lbl">This run</span>{run.new} new · {run.changed} changed · '
        f"{run.expired} expired</div>"
        f'<div><span class="lbl">Next search</span>{nxt}</div></div></div>'
    )


# ── Opportunities ────────────────────────────────────────────────────────────
def _options(name: str, label: str, choices: Iterable[tuple[str, str]], chosen: str) -> str:
    opts = "".join(
        f'<option value="{e(value)}"{" selected" if value == chosen else ""}>{e(text)}</option>'
        for value, text in choices
    )
    return (
        f'<div><label for="f-{name}">{label}</label>'
        f'<select id="f-{name}" name="{name}">{opts}</select></div>'
    )


def _filters_form(f: Filters) -> str:
    return (
        '<form class="filters" method="get" action="/opportunities">'
        f'<input type="hidden" name="view" value="{e(f.view)}">'
        + _options(
            "priority",
            "Priority",
            [("", "Any priority"), *((p, words(p)) for p in PRIORITY_CHOICES)],
            f.priority,
        )
        + _options(
            "fit",
            "Fit range",
            [("", "Any fit"), *((str(n), f"{n} and above") for n in FIT_CHOICES)],
            str(f.min_fit) if f.min_fit else "",
        )
        + _options(
            "confidence",
            "Confidence",
            [("", "Any confidence"), *((c, words(c)) for c in CONFIDENCE_CHOICES)],
            f.confidence,
        )
        + _options(
            "work_model",
            "Work model",
            [("", "Any work model"), *((w, w) for w in WORK_MODEL_CHOICES)],
            f.work_model,
        )
        + _options(
            "scope",
            "Location",
            [("", "Any location"), *((s, SCOPE_LABEL.get(s, words(s))) for s in SCOPE_CHOICES)],
            f.scope,
        )
        + _options(
            "age",
            "Posting age",
            [("", "Any age"), *((str(d), AGE_LABEL[d]) for d in AGE_CHOICES)],
            str(f.max_age_days) if f.max_age_days else "",
        )
        + _options(
            "network",
            "Network",
            [("", "Any network"), *((n, NETWORK_LABEL[n]) for n in NETWORK_CHOICES)],
            f.network,
        )
        + _options(
            "pay",
            "Compensation",
            [("", "Any compensation"), *((p, PAY_LABEL[p]) for p in PAY_CHOICES)],
            f.pay,
        )
        + '<div><label for="f-company">Company</label>'
        f'<input id="f-company" name="company" type="text" maxlength="100" '
        f'placeholder="Any company" value="{e(f.company)}"></div>'
        '<div class="go"><button class="btn primary" type="submit">Apply</button>'
        f'<a class="btn" href="/opportunities?view={e(f.view)}">Clear</a></div></form>'
    )


def _table(items: list[Opportunity]) -> str:
    rows = "".join(
        f"<tr><td>{priority_pill(o.priority)}</td>"
        f'<td><span class="tfit">{"Unknown" if o.fit is None else f"{o.fit:.0f}"}</span></td>'
        f'<td><a class="tl" href="{opportunity_url(o)}">{e(o.title)}</a>'
        f'<div class="muted">{e(o.company)}</div></td>'
        f"<td>{e(o.location)}{f' · {e(o.work_model)}' if o.work_model else ''}</td>"
        + (
            f'<td class="num">{e(o.compensation)}</td>'
            if o.compensation
            else '<td class="unk">Not published</td>'
        )
        + f"<td>{e(_first(o.concerns) or 'None noted')}</td></tr>"
        for o in items
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Priority</th>'
        '<th scope="col">Fit</th><th scope="col">Role</th><th scope="col">Location</th>'
        '<th scope="col">Compensation</th><th scope="col">Main concern</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def opportunities_body(listing: Listing, f: Filters, now: datetime) -> str:
    def view_link(key: str, label: str) -> str:
        on = key == listing.view.key
        attrs = ' class="btn sel" aria-current="page"' if on else ' class="btn"'
        return (
            f'<a{attrs} href="/opportunities?view={key}">'
            f'{e(label)}<span class="c">{listing.counts[key]}</span></a>'
        )

    views = "".join(view_link(v.key, v.label) for v in VIEWS)
    cards = (
        '<div class="stack">' + "".join(card(o, now) for o in listing.in_view) + "</div>"
        if listing.in_view
        else _empty(
            "No opportunity matches this view and these filters."
            if f.any_set
            else "No opportunity is in this view right now."
        )
    )
    others = (
        _section(f"Other active opportunities · {len(listing.others)}", _table(listing.others))
        if listing.others
        else ""
    )
    if listing.view.key != "all":
        others += (
            '<p class="note">Low-priority and unranked roles appear only in '
            '<a href="/opportunities?view=all">All active</a>.</p>'
        )
    return (
        f'<section aria-labelledby="views-h"><h2 id="views-h">Views</h2>'
        f'<div class="views">{views}</div></section>'
        f'<section aria-labelledby="filters-h"><h2 id="filters-h">Filters</h2>'
        f"{_filters_form(f)}</section>"
        + _section(f"{listing.view.label} · {len(listing.in_view)}", cards)
        + others
    )


# ── Opportunity detail ───────────────────────────────────────────────────────
def _kv(label: str, value: str | None, unknown: str = "Unknown") -> str:
    shown = (
        f'<span class="v">{e(value)}</span>' if value else f'<span class="v unk">{unknown}</span>'
    )
    return f'<div class="kv"><span class="lbl">{label}</span>{shown}</div>'


def _citation(c: Citation) -> str:
    if c.kind == "posting":
        label, text = "Job evidence", f'<span class="quote">"{e(c.text)}"</span>'
    elif c.kind == "profile":
        label, text = "Profile evidence", e(c.text)
    else:
        label, text = "From the job record", e(FIELD_LABEL.get(c.text, c.text))
    return f'<div><span class="lbl">{label}</span>{text}</div>'


def _point(p: Point, open_first: bool = False) -> str:
    if not p.citations:
        return f'<div class="gap"><span class="t">{e(p.text)}</span></div>'
    cites = "".join(_citation(c) for c in p.citations)
    is_open = " open" if open_first else ""
    return (
        f'<details class="ev"{is_open}><summary><span class="plus">+</span>'
        f'<strong>{e(p.text)}</strong><span class="more">Evidence</span></summary>'
        f'<div class="evb">{cites}</div></details>'
    )


def _concern(p: Point) -> str:
    cls, label = next(
        ((c, lbl) for prefix, c, lbl in CONCERN_KIND if p.text.startswith(prefix)),
        ("k-pref", "Concern"),
    )
    cites = "".join(_citation(c) for c in p.citations)
    return (
        f'<div class="gap"><div class="row"><span class="pill {cls}">{label}</span>'
        f'<span class="t">{e(p.text)}</span></div>{cites}</div>'
    )


def _bars(o: Opportunity) -> str:
    rows = []
    for c in o.components:
        label = e(COMPONENT_LABEL.get(c.name, words(c.name)))
        if c.value is None:
            rows.append(
                f'<div class="bar"><span>{label}</span><span class="unk">Unknown</span>'
                '<span class="s">-</span></div>'
            )
            continue
        score = round(c.value * 100)
        lo = " lo" if c.value < LOW_COMPONENT else ""
        rows.append(
            f'<div class="bar"><span>{label}</span>'
            '<svg class="track" viewBox="0 0 100 10" preserveAspectRatio="none" '
            'role="img" aria-hidden="true">'
            '<rect class="bg" width="100" height="10" rx="5"/>'
            f'<rect class="v{lo}" width="{score}" height="10" rx="5"/></svg>'
            f'<span class="s">{score}</span></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>' if rows else _empty("Not scored yet.")


def _network(o: Opportunity) -> str:
    if o.connections is None:
        return '<p class="note">Your LinkedIn connections have not been imported yet.</p>'
    if not o.connections:
        return '<p class="note">No first-degree connections at this company.</p>'
    rows = "".join(
        f'<div class="li netli"><strong>{e(c.name)}</strong><span class="meta">{e(c.role)}</span>'
        f'<span class="chip">{e(words(c.strength))}</span></div>'
        for c in o.connections
    )
    return f'<div class="list bare">{rows}</div>'


def _description(text: str) -> str:
    paragraphs = [p for p in text.splitlines() if p.strip()]
    return '<div class="jd">' + "".join(f"<p>{e(p)}</p>" for p in paragraphs) + "</div>"


def _original(url: str) -> str:
    # Only web links: a source could send a javascript: or data: URL.
    if url.startswith(("https://", "http://")):
        return (
            f'<a href="{e(url)}" rel="noopener noreferrer" target="_blank">'
            "Open original posting</a>"
        )
    return '<span class="unk">No link to the original posting</span>'


def detail_body(o: Opportunity, now: datetime) -> str:
    fit = "Unknown" if o.fit is None else f"{o.fit:.0f}"
    summary = (
        '<section class="card hot" aria-labelledby="sum-h"><h2 id="sum-h">Summary</h2>'
        f'<div class="big">{fit_block(o, link=False)}'
        f"<div>{priority_pill(o.priority)}"
        '<div class="fitl">Priority · <a href="#now">why</a></div></div>'
        f'<div><strong>{e(o.confidence)}</strong><div class="fitl">Confidence</div></div></div>'
        '<div class="summary">'
        + _kv("Location", o.location)
        + _kv("Work model", o.work_model)
        + _kv("Compensation", o.compensation, "Not published")
        + _kv("Employer posted", when(o.posted_at, now) if o.posted_at else None)
        + _kv("First seen", when(o.first_seen_at, now))
        + _kv("Source", o.source.capitalize())
        + "</div></section>"
    )
    fits = "".join(_point(p, i == 0) for i, p in enumerate(o.why_it_fits))
    concerns = "".join(_concern(p) for p in o.concerns)
    now_items = "".join(_point(p) for p in o.why_now)
    return (
        summary + '<section class="grid2">'
        f'<div class="card" id="fit"><h2>Fit analysis · {fit}</h2>{_bars(o)}'
        '<p class="note">Fit measures qualification only. Network, freshness and urgency '
        "affect priority, never fit.</p></div>"
        f'<div class="card" id="concerns"><h2>Concerns and gaps · {len(o.concerns)}</h2>'
        f"{concerns or _empty('No concerns found.')}</div></section>"
        '<section class="card" id="why"><h2>Why it fits</h2>'
        f'<div class="reasons">{fits or _empty("No strong reasons found.")}</div></section>'
        '<section class="grid2">'
        f'<div class="card" id="now"><div class="row spread"><h2>Why act now</h2>'
        f"{priority_pill(o.priority)}</div>"
        + (f'<div class="reasons">{now_items}</div>' if now_items else _empty("Nothing urgent."))
        + '<p class="note">Priority is separate from fit, so urgency and network never '
        "inflate how qualified you are.</p></div>"
        f'<div class="card" id="network"><h2>Who you know · '
        f"{'Unknown' if o.connections is None else len(o.connections)}</h2>"
        f"{_network(o)}</div></section>"
        f'<section class="card" id="jd"><h2>Job description</h2>{_description(o.description)}'
        f"<div>{_original(o.url)}</div></section>"
        '<div class="row spread"><a href="/opportunities">Back to opportunities</a></div>'
    )


def not_found_body() -> str:
    return _empty("This opportunity is no longer active or was never found.") + (
        '<div><a href="/opportunities">Back to opportunities</a></div>'
    )


# ── Search Health ────────────────────────────────────────────────────────────
SOURCE_PILL = {"OK": ("p-ok", "Healthy"), "FAILED": ("p-fail", "Failed")}
RUN_PILL = {"SUCCESS": "p-ok", "PARTIAL": "p-warn"}


def _run_pill(status: str) -> str:
    return f'<span class="pill {RUN_PILL.get(status, "p-fail")}">{e(status)}</span>'


def _source_pill(status: str) -> str:
    cls, label = SOURCE_PILL.get(status, ("p-warn", words(status)))
    return f'<span class="pill {cls}">{e(label)}</span>'


def _last_ok(name: str, earlier: list[SearchRun], now: datetime) -> str:
    for run in earlier:
        if any(s.name == name and s.status == "OK" for s in run.sources):
            return when(run.started_at, now)
    return "None in recent runs"


def _failures(latest: SearchRun, earlier: list[SearchRun], now: datetime) -> str:
    failed = [s for s in latest.sources if s.status != "OK"]
    if not failed:
        return ""
    cards = "".join(
        '<div class="card"><div class="row spread">'
        f"<h3>{e(s.name)}</h3>{_source_pill(s.status)}</div>"
        '<div class="summary">'
        + _kv("Last successful search", _last_ok(s.name, earlier, now))
        + _kv("This run", when(latest.started_at, now))
        + _kv("Impact", "Results from this source may be incomplete.")
        + _kv("Retry", "At the next scheduled search")
        + "</div></div>"
        for s in failed
    )
    return _section(f"Sources that failed · {len(failed)}", f'<div class="stackl">{cards}</div>')


def _sources_table(sources: tuple[SourceStatus, ...]) -> str:
    if not sources:
        return _empty("This run did not record its sources.")
    ranked = sorted(sources, key=lambda s: (s.status == "OK", s.name))
    rows = "".join(
        f"<tr><td>{e(s.name)}</td><td>{_source_pill(s.status)}</td>"
        f'<td class="num">{s.fetched}</td><td class="num">{s.candidates}</td></tr>'
        for s in ranked
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Source</th>'
        '<th scope="col">Status</th><th scope="col">Roles fetched</th>'
        '<th scope="col">Senior roles kept</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _history(runs: list[SearchRun], now: datetime) -> str:
    rows = "".join(
        f"<tr><td>{when(r.started_at, now)}</td><td>{_run_pill(r.status)}</td>"
        f'<td class="num">{r.sources_searched} of {r.sources_total}</td>'
        f'<td class="num">{r.new}</td><td class="num">{r.changed}</td>'
        f'<td class="num">{r.expired}</td></tr>'
        for r in runs
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Started</th>'
        '<th scope="col">Status</th><th scope="col">Sources searched</th>'
        '<th scope="col">New</th><th scope="col">Changed</th><th scope="col">Expired</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def search_health_body(runs: list[SearchRun], now: datetime) -> str:
    """Did the searches actually cover what they should (spec 12.27 to 12.31)?"""
    if not runs:
        return _empty("No search has run yet. The first scheduled search will show here.")
    latest, earlier = runs[0], runs[1:]
    return (
        _section("Latest search", health_card(latest, now))
        + _failures(latest, earlier, now)
        + _section(
            f"Sources in the latest search · {len(latest.sources)}", _sources_table(latest.sources)
        )
        + _section(f"Recent searches · {len(runs)}", _history(runs, now))
        + '<p class="note">"No jobs found" and "source failed" are different: a failed '
        "source is listed here so a quiet day is never mistaken for an empty market.</p>"
    )


# ── Companies ────────────────────────────────────────────────────────────────
COMPANY_STATE = {
    "MATCHING_JOBS": ("p-high", "Matching jobs"),
    "STRATEGICALLY_RELEVANT": ("p-ok", "Strategically relevant"),
    "NO_CURRENT_MATCH": ("p-med", "No current match"),
    "LOW_RELEVANCE": ("p-med", "Low relevance"),
}


def company_roles_url(name: str) -> str:
    """The Opportunities page filtered to one company, across every band."""
    return f"/opportunities?view=all&company={quote(name, safe='')}"


def _company_state(state: str) -> str:
    cls, label = COMPANY_STATE.get(state, ("p-med", words(state)))
    return f'<span class="pill {cls}">{e(label)}</span>'


def _signals(signals: tuple[Signal, ...], now: datetime) -> str:
    if not signals:
        return '<p class="note">No relevant signals in the last 90 days.</p>'
    items = "".join(
        f"<li><div><strong>{e(s.text)}</strong>"
        f'<div class="src">{e(s.source)} · {age(s.seen_at, now)}</div></div></li>'
        for s in signals
    )
    return f'<ul class="plus-list">{items}</ul>'


def _stat(value: object, label: str) -> str:
    return f'<div><div class="fit">{e(value)}</div><div class="fitl">{label}</div></div>'


def company_card(row: CompanyRow, now: datetime) -> str:
    """A target company (spec 12.19), or why it stays relevant without a match (12.21)."""
    c = row.company
    watching = '<span class="state">WATCHING</span>' if c.watching else ""
    industry = f'<div class="co">{e(c.industry)}</div>' if c.industry else ""
    connections = "Unknown" if c.connections is None else c.connections
    if row.jobs:
        top = row.jobs[0]
        fit = "Unknown" if top.fit is None else f"{top.fit:.0f}"
        middle = (
            '<div class="row">'
            + _stat(len(row.jobs), "Matching jobs" if len(row.jobs) != 1 else "Matching job")
            + _stat(row.high_priority, "High-priority")
            + _stat(connections, "Connections")
            + '</div><div><span class="lbl">Relevant signals</span>'
            + _signals(c.signals, now)
            + "</div>"
            f'<div class="meta">Top match: <a href="{opportunity_url(top)}">{e(top.title)}</a>'
            f" · Fit {fit} · {e(words(top.priority))}</div>"
        )
    else:
        middle = (
            '<p class="verdict">No suitable opening currently.</p>'
            '<div class="row">'
            + _stat(connections, "Connections")
            + '</div><div><span class="lbl">Why this company remains relevant</span>'
            + _signals(c.signals, now)
            + "</div>"
        )
    note = f' · <span class="unk">{e(c.coverage_note)}</span>' if c.coverage_note else ""
    return (
        '<article class="card"><div class="row spread"><div>'
        f"<h3>{e(c.name)}</h3>{industry}</div>"
        f'<div class="row">{_company_state(row.state)}{watching}</div></div>'
        f'<div class="meta">Monitoring priority: <strong>{e(c.monitoring)}</strong></div>'
        f"{middle}"
        f'<div class="src">Jobs from: {e(c.job_source)}{note}</div>'
        f'<div class="actions"><a class="btn" href="{e(company_roles_url(c.name))}">'
        "See roles</a></div></article>"
    )


def _discovered(rows: list[CompanyRow]) -> str:
    items = "".join(
        f'<div class="li"><div class="grow"><h3>{e(r.company.name)}</h3>'
        f'<div class="muted">{e(r.company.industry or "Industry unknown")}'
        + (f" · {e(r.company.low_reason)}" if r.company.low_reason else "")
        + "</div></div>"
        f"{_company_state(r.state)}"
        f'<a href="{e(company_roles_url(r.company.name))}">See roles</a></div>'
        for r in rows
    )
    return f'<div class="list">{items}</div>'


def companies_body(listing: CompanyListing, now: datetime) -> str:
    """Target company universe, with or without openings today (spec 12.18)."""

    def view_link(key: str, label: str) -> str:
        on = key == listing.view.key
        attrs = ' class="btn sel" aria-current="page"' if on else ' class="btn"'
        return (
            f'<a{attrs} href="/companies?view={key}">'
            f'{e(label)}<span class="c">{listing.counts[key]}</span></a>'
        )

    tiles = "".join(
        f'<a class="tile" href="/companies?view={v.key}">'
        f'<div class="n">{listing.counts[v.key]}</div><div class="l">{e(v.label)}</div></a>'
        for v in COMPANY_VIEWS[1:]
    )
    views = "".join(view_link(v.key, v.label) for v in COMPANY_VIEWS)
    targets = (
        '<div class="grid2">' + "".join(company_card(r, now) for r in listing.targets) + "</div>"
        if listing.targets
        else _empty("No target company is in this view.")
    )
    discovered = (
        _section(
            f"Discovered in searches · {len(listing.discovered)}", _discovered(listing.discovered)
        )
        if listing.discovered
        else ""
    )
    return (
        f'<section aria-label="Summary"><div class="tiles">{tiles}</div></section>'
        f'<section aria-labelledby="cviews-h"><h2 id="cviews-h">Views</h2>'
        f'<div class="views">{views}</div></section>'
        + _section(f"Target companies · {len(listing.targets)}", targets)
        + discovered
        + '<p class="note">Watching a company raises how closely PEJIP follows it. It never '
        "raises the Fit of its jobs.</p>"
    )


# ── Watchlist ────────────────────────────────────────────────────────────────
def _changed_card(o: Opportunity, now: datetime) -> str:
    return card(o, now, f"Watched job changed · {o.change_note or 'posting changed'}")


def _signal_rows(rows: list[tuple[CompanyRow, Signal]], now: datetime) -> str:
    items = ""
    for r, newest in rows:
        items += (
            f'<div class="li"><div class="grow"><h3>{e(r.company.name)}</h3>'
            f"<div><strong>{e(newest.text)}</strong></div>"
            f'<div class="src">{e(newest.source)} · {age(newest.seen_at, now)}</div></div>'
            f"{_company_state(r.state)}</div>"
        )
    return f'<div class="list">{items}</div>'


def _watched_jobs(items: list[Opportunity]) -> str:
    rows = "".join(
        f'<tr><td><a class="tl" href="{opportunity_url(o)}">{e(o.title)}</a></td>'
        f"<td>{e(o.company)}</td>"
        f'<td><span class="tfit">{"Unknown" if o.fit is None else f"{o.fit:.0f}"}</span></td>'
        f"<td>{priority_pill(o.priority)}</td>"
        f"<td>{e(o.change_note or 'No change')}</td></tr>"
        for o in items
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Role</th>'
        '<th scope="col">Company</th><th scope="col">Fit</th><th scope="col">Priority</th>'
        f'<th scope="col">Last change</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _watched_companies(rows: list[CompanyRow], now: datetime) -> str:
    def signal(r: CompanyRow) -> str:
        newest = latest_signal(r.company)
        if newest is None:
            return '<span class="unk">None in 90 days</span>'
        return f"{e(newest.text)} · {age(newest.seen_at, now)}"

    body = "".join(
        f"<tr><td>{e(r.company.name)}</td><td>{e(r.company.monitoring)}</td>"
        f'<td class="num">{len(r.jobs)}'
        + (f" · {r.high_priority} high-priority" if r.high_priority else "")
        + f"</td><td>{signal(r)}</td>"
        f'<td><a href="{e(company_roles_url(r.company.name))}">See roles</a></td></tr>'
        for r in rows
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Company</th>'
        '<th scope="col">Monitoring</th><th scope="col">Matching jobs</th>'
        '<th scope="col">Latest signal</th><th scope="col">Roles</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def watchlist_body(w: Watchlist, now: datetime) -> str:
    """Changes in watched jobs and companies first, then everything watched (12.22)."""
    tiles = (
        (len(w.changed_jobs), "Watched jobs changed", "#changed"),
        (len(w.new_at_watched), "New roles at watched companies", "#new-roles"),
        (len(w.new_signals), "Watched companies with new signals", "#signals"),
    )
    tile_html = "".join(
        f'<a class="tile" href="{href}"><div class="n">{n}</div><div class="l">{label}</div></a>'
        for n, label, href in tiles
    )
    changed = (
        '<div class="stackl">' + "".join(_changed_card(o, now) for o in w.changed_jobs) + "</div>"
        if w.changed_jobs
        else _empty("No watched job changed since the last search.")
    )
    new_roles = (
        '<div class="stackl">' + "".join(card(o, now) for o in w.new_at_watched) + "</div>"
        if w.new_at_watched
        else _empty("No new role at a watched company.")
    )
    signals = (
        _signal_rows(w.new_signals, now)
        if w.new_signals
        else _empty("No new signal at a watched company this week.")
    )
    jobs = (
        _watched_jobs(w.jobs)
        if w.jobs
        else _empty("You are not watching any job yet. Watched roles show a Watching tag.")
    )
    companies = (
        _watched_companies(w.companies, now)
        if w.companies
        else _empty("You are not watching any company yet.")
    )
    return (
        f'<section aria-label="Summary"><div class="tiles">{tile_html}</div></section>'
        f'<div id="changed">{_section("Watched jobs that changed", changed)}</div>'
        f'<div id="new-roles">{_section("New roles at watched companies", new_roles)}</div>'
        f'<div id="signals">{_section("New signals at watched companies", signals)}</div>'
        + _section(f"Watched jobs · {len(w.jobs)}", jobs)
        + _section(f"Watched companies · {len(w.companies)}", companies)
        + '<p class="note">Watching a company raises how closely PEJIP follows it and may '
        "raise Application Priority. It never changes the Fit of its jobs.</p>"
    )


# ── Settings ─────────────────────────────────────────────────────────────────
# PEJIP's own alert address (design doc 0010); Babu signs up for job alerts with it.
ALERT_ADDRESS = "alerts@inbox.job-search.zephyr-mcg.com"
ADAPTER_LABEL = {"greenhouse": "Public Greenhouse job board", "lever": "Public Lever job board"}
MONTHLY_AI_CAP = "$100"
ANY_PLACE = "Any remote role in the US"


def _chips(values: Iterable[str]) -> str:
    return (
        '<div class="views">'
        + "".join(f'<span class="chip">{e(v)}</span>' for v in values)
        + "</div>"
    )


def _settings_card(heading: str, anchor: str, body: str) -> str:
    return f'<section class="card" id="{anchor}"><h2>{e(heading)}</h2>{body}</section>'


def _locations(config: SearchConfig) -> str:
    rows = "".join(
        f"<tr><td>{e(SCOPE_LABEL.get(key, words(key)))}</td>"
        f"<td>{e(words(scope.preference))}</td>"
        f"<td>{e(', '.join(p.title() for p in scope.places) or ANY_PLACE)}</td></tr>"
        for key, scope in config.geography.scopes.items()
    )
    rule = (
        "Roles outside every location are hidden."
        if config.geography.hard_filter
        else "Roles outside these locations are kept, with lower priority."
    )
    return (
        '<div class="tbl"><table><thead><tr><th scope="col">Location</th>'
        '<th scope="col">Preference</th><th scope="col">Places</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div><p class="note">{rule}</p>'
    )


def _sources(config: SearchConfig) -> str:
    boards = "".join(
        f'<div class="li"><div class="grow"><h3>{e(s.company)}</h3>'
        f'<div class="muted">{e(ADAPTER_LABEL.get(s.adapter, s.adapter))}</div></div>'
        '<span class="pill p-ok">On</span></div>'
        for s in config.sources
    )
    alerts = (
        "".join(
            f'<div class="li"><div class="grow"><h3>{e(a.company)}</h3>'
            f'<div class="muted">{"Job board alerts" if a.job_board else "Careers site alerts"}'
            "</div></div></div>"
            for a in config.inbox.companies
        )
        if config.inbox
        else ""
    )
    alert_html = (
        f'<h3>Job-alert emails</h3><p class="note">Sign up for each company\'s job alerts with '
        f"<strong>{e(ALERT_ADDRESS)}</strong>. PEJIP reads only links to the careers pages "
        f'listed here.</p><div class="list">{alerts}</div>'
        if alerts
        else '<p class="note">Job-alert emails are not set up.</p>'
    )
    return (
        f'<h3>Careers sites · {len(config.sources)}</h3><div class="list">{boards}</div>'
        f"{alert_html}"
        '<p class="note">PEJIP reads only sources whose terms allow it, follows each '
        "site's robots.txt and limits how often it asks. Live status is on "
        '<a href="/search-health">Search Health</a>.</p>'
    )


def _ranking(config: SearchConfig) -> str:
    s = config.scoring
    weights = "".join(
        f'<div class="kv"><span class="lbl">{e(COMPONENT_LABEL.get(k, words(k)))}</span>'
        f'<span class="v">{v:.0f}%</span></div>'
        for k, v in s.fit_weights.items()
    )
    bands = "".join(
        f'<div class="kv"><span class="lbl">{e(words(band))}</span>'
        f'<span class="v">Priority {threshold:.0f}+'
        + (f", Fit {s.priority_min_fit[band]:.0f}+" if band in s.priority_min_fit else "")
        + "</span></div>"
        for band, threshold in s.priority_thresholds.items()
    )
    return (
        f'<p class="note">Scoring version {e(s.version)}.</p>'
        f'<h3>What makes up Fit</h3><div class="summary">{weights}</div>'
        f'<h3>Priority bands</h3><div class="summary">{bands}</div>'
        '<p class="note">Fit measures qualification only. Freshness, pay and location '
        "affect priority, never fit.</p>"
    )


def settings_body(config: SearchConfig | None) -> str:
    """What PEJIP searches for, when, and how it ranks: read-only for now (12.35)."""
    if config is None:
        return _empty("The search configuration is not available on this server.")
    t = config.taxonomy
    jump = "".join(
        f'<a class="btn" href="#{anchor}">{label}</a>'
        for anchor, label in (
            ("roles", "Roles and titles"),
            ("locations", "Locations"),
            ("schedule", "Search schedule"),
            ("sources", "Sources"),
            ("ranking", "Ranking"),
            ("privacy", "Privacy and data"),
        )
    )
    roles = (
        "<h3>Seniority a title needs</h3>"
        + _chips(t.seniority_patterns)
        + "<h3>Role words a title needs</h3>"
        + _chips(t.role_terms)
        + "<h3>Titles always left out</h3>"
        + _chips(t.excluded_title_patterns)
    )
    schedule = (
        '<div class="summary">'
        + _kv("Search", "Daily at 6:00 AM Pacific")
        + _kv("Roles analysed per search", str(config.ai.max_jobs_per_run))
        + _kv("AI spending cap", f"{MONTHLY_AI_CAP} a month")
        + "</div>"
    )
    privacy = (
        '<div class="summary">'
        + _kv("Kept", f"{config.retention_days} days, then deleted")
        + _kv("Storage and transfer", "Encrypted at rest and in transit")
        + _kv(
            "Shared with", "Anthropic (Claude), only the job and profile text each analysis needs"
        )
        + _kv("Logs", "No personal data")
        + "</div>"
    )
    return (
        '<p class="note">These settings are read-only here for now; they change through '
        "the search configuration file.</p>"
        f'<nav class="views" aria-label="Settings sections">{jump}</nav>'
        + _settings_card("Roles and titles", "roles", roles)
        + _settings_card("Locations", "locations", _locations(config))
        + _settings_card("Search schedule", "schedule", schedule)
        + _settings_card("Sources", "sources", _sources(config))
        + _settings_card("Ranking", "ranking", _ranking(config))
        + _settings_card("Privacy and data", "privacy", privacy)
    )
