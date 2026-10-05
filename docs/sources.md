# Job sources

The only job sources PEJIP may fetch (build policy section 11). A source not listed
here is not fetched. Every fetch goes through the shared limiter in
`src/pejip/sources/http.py`, which honours `robots.txt`, sends the user agent
`PEJIP/0.1 (personal job research; +https://github.com/madduri-ops/PEJIP)`, and
backs off on 429 and 5xx responses.

| Source | Access method | Terms | Rate limit we apply | Terms last reviewed |
|---|---|---|---|---|
| Greenhouse Job Board API | Official public API, `GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true` | [Job Board API docs](https://developers.greenhouse.io/job-board.html): job board data is public and GET endpoints need no authentication. No rate limit is published. | 1 request per second per host, 3 retries with exponential backoff | 2026-10-05 |
| Lever Postings API | Official public API, `GET https://api.lever.co/v0/postings/{site}?mode=json` | [Postings API docs](https://github.com/lever/postings-api): GET requests need no API key; the published limit (2 per second) applies only to application POSTs, which PEJIP never sends. | 1 request per second per host, 3 retries with exponential backoff | 2026-10-05 |
| Job-alert emails | Babu signs up for each career site's job alerts with `alerts@inbox.job-search.zephyr-mcg.com`, and Yahoo Mail Plus auto-forwards his whole Yahoo mailbox there for its LinkedIn job alerts (only emails from LinkedIn itself become roles; all other email is deleted unread and only counted); SES stores the emails in PEJIP's own bucket, which `pejip run` reads when `PEJIP_INBOX_BUCKET` is set ([design 0010](design/0010-job-alert-inbox.md)) | Each site's own alert feature, used as offered. PEJIP reads only the emails; it does not fetch the linked pages | Not applicable: no request goes to the career sites | 2026-10-05 |

Both APIs publish an employer's own open roles, so they also serve as the canonical
source for those roles (spec section 7.1).

## Adding or changing a source

1. Read the source's terms and confirm automated access for personal job research is
   allowed. No login-walled pages, CAPTCHA bypassing or rotating identities.
2. Add a row here with the terms link, access method, rate limit and review date.
3. Add the adapter under `src/pejip/sources/`, calling only `PoliteClient`, with
   tests against recorded payloads.
4. If a source's terms stop allowing our use, remove it from `config/search.yaml`
   and mark it disabled here in the same PR.

Which company boards are searched, and which careers pages an alert's links may
point at, is configuration, in `config/search.yaml`.
