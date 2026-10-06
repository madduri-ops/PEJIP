# Changelog

All notable changes to PEJIP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH` tags.

Add a line under **Unreleased** in every pull request that changes user-visible
behaviour, using the headings Added, Changed, Deprecated, Removed, Fixed and
Security. Releasing is described in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## Unreleased

### Added

- Per-account job-alert inbox, digest email and scheduled runs (design doc 0016,
  step 3): each account receives job alerts at its own address and its digest
  at its own email; the daily run, digest and purge go through every account in
  turn, and one account's failure doesn't stop the others. Babu's `alerts@`
  address and digest subscription carry over unchanged.
- Per-account storage (design doc 0016, step 2): each account's database,
  digests, profile, companies and LinkedIn files live under its own id
  (`/data/accounts/<id>/`, `/pejip/accounts/<id>/...`, `network/<id>/`). Babu's
  existing database and digests move to `accounts/babu` by themselves on first
  use; the profile, companies and LinkedIn files move by hand before applying
  (`infra/README.md`).
- Sign-in by account (design doc 0016, step 1): the app maps the signed-in Google
  email to an account through `PEJIP_AUTH_ACCOUNTS` (`id=email` pairs, Terraform
  variable `sign_in_accounts`), so later steps can keep each person's data
  separate. Only one account may sign in until per-account storage lands.
  `PEJIP_AUTH_ALLOWED_EMAIL` alone still signs Babu in as account `babu`.

- Ranking through a Claude Code routine on Babu's plan (design doc 0015): on AWS
  the 06:00 run stores new roles without calling Claude, the routine analyses
  them at 07:00 through two key-protected endpoints (`/api/ranking/queue` and
  `/api/ranking/analyses`), and a new `pejip digest` task emails the ranked digest
  at 08:00. If the routine sends nothing, the digest still goes out with those
  roles unranked and a note, and an alarm fires.

### Changed

- Searches run on weekdays only, at 5 AM, 10 AM and 3 PM Pacific, and the ranked
  digest arrives at 7 AM, 12 PM and 5 PM. The stalled-search alarm waits 64
  hours so weekends don't trip it; a digest built from a search more than 4
  hours old says so and alarms.
- Job analysis and evidence matching can run in a Claude Code session as well as
  through the API: `python -m pejip.routine` lays out each step with the same
  prompt, input and schema, and checks every answer the way the API path does
  (design doc 0015). The golden set can be scored through it.
- The portal's sidebar shows the full name, Personal Executive Job Intelligence
  Platform, instead of PEJIP.
- `python -m pejip.evaluation run` takes `--workers N` to score several golden
  cases at once; the live model evaluation in CI uses six.
- The live model evaluation in CI runs only on pull requests labelled
  `live-eval`, so CI makes no paid model calls by default.
- The job search covers Anthropic, the one target company whose roles are
  available through an allowed public API; the example company boards are gone.
- For testing, the search also covers the public Greenhouse boards of nine Bay
  Area companies: Stripe, Databricks, Airbnb, Figma, Dropbox, Pinterest,
  Instacart, Robinhood and Scale AI.

### Added

- The portal has a Connections page at `/connections`: the last LinkedIn import as
  a snapshot, who you know for each open role (matured, your call, below the
  role's level), employer names waiting for your decision, and a searchable list
  of every imported connection.
- An opportunity's page shows company intelligence (industry, other roles you
  match, watch state and recent signals), where the role was found and verified,
  and a history of meaningful changes.
- Opportunities has a Bay Area view and filters for location, posting age,
  network and whether pay is published.
- The portal has a read-only Settings page at `/settings` showing the real search
  setup: titles, locations, schedule, sources and the alert address, how ranking
  works, and data retention.
- The portal has a Watchlist page at `/watchlist`: what changed in watched jobs
  and companies, then everything watched.
- The portal has a Companies page at `/companies`: target companies with their
  matching roles, connections and signals, why a company without an opening stays
  relevant, and companies discovered in searches.
- Connection matching: `pejip run` reads a LinkedIn Connections export
  (`PEJIP_CONNECTIONS`) and shows, for each role, your matured connections
  (first-degree, at the hiring company, at the role's level or above). They raise
  Application Priority, never Fit. Unclear titles and ambiguous employer names are
  asked about instead of guessed, and answered in a decisions file
  (`PEJIP_NETWORK_DECISIONS`).
- `pejip connections <file>` checks an export before use: counts, rejected rows,
  connections per tracked company and employer names to review.
- On AWS the daily run reads the LinkedIn export and network decisions Babu uploads
  to `network/` in the encrypted inbox bucket (deleted after 90 days).
- A network decisions file that is not valid YAML no longer stops a run; the digest
  says so instead.
- Babu's target companies are no longer in the public repository: `pejip run` adds
  them from `PEJIP_COMPANIES` or, on AWS, the encrypted SSM parameter
  `/pejip/companies` (ADR-0009). `config/search.yaml` keeps only the test boards.
- A job board such as LinkedIn is no longer treated as a company your connections
  can work at.
- The portal has a Search Health page at `/search-health`: the latest search, any
  failed sources with their impact and last success, every source searched, and
  recent runs.
- PEJIP searches on its own every morning at 6am Pacific on AWS, keeps its results
  in an encrypted SQLite database on EFS, and emails Babu the digest. Data past 90
  days is purged daily.
- On AWS the career profile is read from the encrypted SSM parameter
  `/pejip/profile`. Until it exists, or until Claude access is set up for the app,
  roles are still found and emailed, listed as unranked with the reason.
- Monitoring: email alerts when a search run fails, a job source can't be
  fetched, the app logs an error, or no search has finished in 26 hours, plus a `pejip` CloudWatch dashboard for search runs,
  source failures, errors, Claude spend and every alarm.
- Web portal at `job-search.zephyr-mcg.com`: Home, Opportunities (saved views and
  filters) and Opportunity detail pages with cited explanations, built from the
  portal mocks. They show illustrative sample data until the database is connected.
- Job-alert inbox: `alerts@inbox.job-search.zephyr-mcg.com` receives career-site job
  alerts through Amazon SES into an encrypted bucket kept for 90 days.
- `pejip run` reads that inbox when `PEJIP_INBOX_BUCKET` is set: roles in alerts
  from Google, NVIDIA, Meta, Micron, OpenAI and Microsoft are ranked with the rest,
  and alert sign-up checks show up in the digest with their confirm link.
- LinkedIn job alerts forwarded to the inbox (inline or as attachments) become
  roles with each employer's name and location. Other forwarded email is deleted
  and only counted in the digest; a sign-up note appears only for a configured
  job site's confirm link. LinkedIn links count only in emails from LinkedIn
  itself, and an email in an unreadable charset is skipped instead of stopping
  the run.
- First end-to-end FIND slice as the `pejip` command line tool: fetches roles from
  configured Greenhouse and Lever company boards, filters them by the search
  taxonomy and geography, analyses each with Claude, scores Fit, Confidence and
  Priority with deterministic rules, and writes a Markdown digest that explains
  every ranking with cited evidence.
- `pejip purge`, `pejip export` and `pejip delete-all` for retention, export and
  deletion of stored data.
- The ranking pipeline is scored against the golden evaluation set in CI, from
  recorded model output on every change and live when prompts or AI code change.
- One-command production rollback: `gh workflow run rollback.yml` redeploys the
  previous (or a named) release through the deploy health gate.
- Each release's container image is tagged with its version and kept, so it stays
  available to roll back to.
- Hosting for `https://job-search.zephyr-mcg.com` in Terraform: VPC, load balancer
  with WAF and HTTPS certificate, ECS Fargate service, service alarms and a daily
  retention purge schedule (off until the app has a database).
- Production container image, scanned on every pull request, and continuous deploy
  on `main` with a health gate, automatic rollback and email on the result.

### Security

- Keyless Claude access: CI and the app authenticate to the Claude API through
  Workload Identity Federation (GitHub Actions OIDC, AWS STS) instead of an API key.
- The app's ECS task role can now request identity tokens for the Claude API only.
- `AIClient` and the live evaluation job sign in to Claude without an API key; the
  `ANTHROPIC_API_KEY` secret is no longer used by CI.
- Google sign-in on `https://job-search.zephyr-mcg.com`: the load balancer signs
  every request in with Google and the app admits only Babu's account. Only
  `/healthz` stays open, for the deploy health gate.

### Fixed

- The Terraform plan check can read the load balancer's WAF association again
  (`wafv2:GetWebACLForResource` is checked against every regional web ACL).
- Deploy waits for the ECS rollout to finish instead of failing a healthy
  deploy whose rollout was still marked in progress.

## 0.1.0 - 2026-10-05

### Added

- Build policy, README philosophy, FIND build specification, architecture docs and
  ADRs for AWS hosting and the Python toolchain.
- Foundation AWS infrastructure in Terraform: KMS key, state bucket, ECR repository,
  GitHub OIDC deploy and plan roles, alert topic and budget.
- Staged CI pipeline with lint, unit, integration and system tests, SAST, dependency
  audit, DAST, secrets scan and a coverage ratchet.
- Health endpoint `GET /healthz` reporting the running version.
- AI cost guard enforcing the $100 monthly cap, with spend alarms from 50% to 100%.
- Golden evaluation set and harness for rankings.
- 90-day retention window for personal data, postings and rankings, with an
  expired-file purge.
- Release tooling: this changelog, version checks, tagged GitHub Releases and a
  rollback workflow.
