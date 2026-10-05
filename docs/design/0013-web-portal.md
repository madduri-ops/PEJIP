# 0013: Web portal (Home, Opportunities, Opportunity detail, Companies, Watchlist, Search Health, Settings)

_Status: implemented (sample data). Last updated: 2026-10-05._

## Purpose

Give Babu a signed-in web view of the ranked roles at `job-search.zephyr-mcg.com`
instead of only the Markdown digest: what needs attention now, every active
opportunity with saved views and filters, and one role's full, cited explanation
(spec section 12).

## Scope

In scope: the Home, Opportunities, Opportunity detail, Companies, Watchlist,
Search Health and Settings pages from the portal mocks (`Main`, `Opportunities`,
`Opportunity`, `Companies`, `Watchlist`, `SearchHealth` and `Settings` boards on the shared mock canvas, style
guide in the project files), served by the existing FastAPI app behind Google
sign-in, reading from a data interface with synthetic sample data behind it.

Out of scope for now:

- Reading the real database. The persistent store is being added separately
  ([0011: Daily run and storage](0011-daily-run-and-storage.md) on its branch); a
  store-backed reader plugs into the same interface when it lands.
- Feedback buttons (Interested, Watch, Not interested, Already applied), the detail
  page's Decide actions and "This explanation is wrong", and "Search now": they need
  storage and a run trigger. The pages leave them out rather than
  show buttons that do nothing.
- Connections: listed in the navigation as "Soon".
- The Already applied and Archived views and the role family and job status filters
  from the Opportunities mock: they need stored feedback and job status.
- Editing settings, and the Settings sections that need stored data (career profile,
  compensation, notifications, LinkedIn import, learned preferences): Settings is a
  read-only view of `config/search.yaml` until settings are stored.
- On Watchlist, watched role families, "possibly closed" job status, before and
  after values for a change, and the reason Babu gave for watching: none is stored
  yet.
- The company detail screen (spec 12.20), "Watch company" and the sort menu on
  Companies: "See roles" opens Opportunities filtered to the company instead.
- On Search Health, search coverage by geographic scope and role family (spec 12.32)
  and run details beyond the history table: runs do not record scopes yet.

## Design

```mermaid
flowchart LR
    browser[Browser] -->|Google sign-in at the ALB| auth[pejip.auth middleware]
    auth --> routes[pejip.portal.router]
    routes --> views[pejip.portal.views: rank, views, filters, Pacific time]
    routes --> render[pejip.portal.render: HTML]
    routes --> data[(PortalData)]
    data -.today.-> sample[SampleData]
    data -.next.-> store[Store-backed reader]
```

- **Server-rendered HTML, no JavaScript.** Views and filters are links and a GET
  form, so every state has a URL and nothing runs in the browser. Expanding a
  reason's evidence uses `<details>`.
- **One place per mock part.** `render.py` has a function per building block (nav,
  run line, opportunity card, compact card, table, fit bars, concerns, evidence),
  and `static/portal.css` is the style guide's block plus the screen additions, so a
  change to a mock maps to one edit. No templating library is added.
- **Ranking:** priority band, then Fit (unknown last), then freshness. Low and
  unranked roles appear only in "All active".
- **Unknowns are shown** as "Unknown" or "Not published", never hidden (spec 12.41);
  each Fit number links to its explanation (12.40); concerns sit next to reasons.
- **Times** are shown in Pacific time. The Alpine image has no time zone database,
  so `views.to_pacific` applies the US daylight saving rules itself.

## Interfaces

| Route | Shows |
|---|---|
| `GET /` | Home: counts, roles needing attention, new matches, changed roles, search health |
| `GET /opportunities` | Views (`view=attention, new, high-fit, immediate, watched, network, remote, bay-area, changed, all`) and filters (`priority`, `fit`, `confidence`, `company`, `work_model`, `scope=BAY_AREA\|US_REMOTE`, `age=1\|3\|7\|30` days, `network=connected\|none\|unknown`, `pay=published\|unpublished`); unknown values are ignored |
| `GET /opportunities/{opportunity_id}` | One role: summary, fit bars, concerns, cited reasons, why now, who you know, company intelligence (industry, open roles you match, watch state, signals), description, source and verification (where it was found and confirmed, requisition, first seen, last verified, original link) and history of meaningful changes; 404 page when unknown |
| `GET /companies` | Target companies as cards (state, watching, monitoring priority, matching and high-priority roles, connections, cited signals, top match, where jobs come from and any coverage gap) and discovered companies as a list; views `view=all, matching, watching, relevant, no-match, low`, unknown values show all |
| `GET /watchlist` | Changes first (watched jobs that changed, new roles at watched companies, watched companies with a signal from the last seven days), then every watched job and company |
| `GET /settings` | The real search configuration, read-only: seniority, role words and excluded titles; locations and whether they are a hard filter; schedule and AI limits; careers-site boards and job-alert companies with PEJIP's alert address; Fit weights and priority bands; retention and sharing |
| `GET /search-health` | Latest run, failed sources with their impact and last success (no raw errors, spec 12.31), every source in the latest run, recent run history |
| `GET /portal.css` | Styles |

All eight require sign-in like every route except `/healthz`. `create_app(data=...)`
takes any `pejip.portal.data.PortalData`:

```python
class PortalData(Protocol):
    is_sample: bool  # shows the sample-data banner

    def latest_run(self) -> SearchRun | None: ...
    def recent_runs(self) -> list[SearchRun]: ...  # newest first, with per-source results
    def opportunities(self) -> list[Opportunity]: ...
    def companies(self) -> list[Company]: ...  # targets and discovered companies
```

`Opportunity` carries what the pages need from the `jobs`, `recommendations`
(`fit`, `confidence`, `priority`, `detail` components) and explanation records
(`pejip.explain` points and citations), so the store-backed reader is a mapping
from those tables; `location_scope` is the geographic scope `pejip.discovery`
places the location in; `verified_on`, `requisition`, `last_verified_at` and
`history` (`HistoryEvent` records of discovery, verification, material changes and
scoring) feed the detail page's Source and verification and History sections, and
its Company intelligence comes from the matching `Company`. `SearchRun.sources` maps from the `runs.summary["sources"]` list
the pipeline already writes (`pejip.digest.SourceResult`, error text left out).
A company has "Matching jobs" when it has a role in the Immediate, High or Medium
band; otherwise the page shows its stored `relevance` (strategically relevant, no
current match, low relevance). Signals carry their source and date (spec 12.42);
target companies come from `config/search.yaml` once the store-backed reader lands,
and signals from the company-intelligence source when it exists.

## Data model

No storage. `pejip.portal.sample` holds invented roles ("Company A", "Person A")
with times relative to the clock; every page says the data is illustrative while it
is in use.

## Non-functional considerations

- **Security:** pages carry their own content security policy (`PAGE_CSP` in
  `pejip.api`): no script at all, styles only from the app and Google Fonts, forms
  only back to the app, no framing. Every value is HTML-escaped (a test feeds
  `<script>` through every field), and links to original postings are shown only for
  `http(s)` URLs, with `rel="noopener noreferrer"`. The smoke test and DAST cover the
  pages through the OpenAPI document; the detail route's example id lets both reach
  a real role.
- **Privacy:** the browser loads the IBM Plex fonts from Google Fonts; no PEJIP data
  is sent (see [SECURITY.md](../SECURITY.md)).
- **Accessibility:** real links, buttons, labelled form controls, `aria-current` on
  the active page and view, 44px touch targets, and layouts that stack at phone
  width with tables in a scroll box.
- **Performance:** one small HTML response and one stylesheet per page; no
  client-side work.
- **Tests:** `tests/unit/test_portal.py` (pages, views, filters, escaping, time
  display), `tests/unit/test_api.py` (page policy, injected data) and
  `tests/system/test_api_smoke.py` (every page against the running server).

## Alternatives considered

- **Jinja2 templates:** familiar, but a new direct dependency; plain functions with
  `html.escape` cover three pages.
- **A Next.js front end** (spec 14): heavier to build, host and test for one user
  today; can come later behind the same routes' data.
- **Inline styles from the mocks:** would need `'unsafe-inline'` in the CSP; moved
  into classes instead.

## Open questions

- Babu approved the mocks on 2026-10-05; the remaining screens follow them.
