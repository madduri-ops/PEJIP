# Security

Security posture for PEJIP. The binding rules are in the
[build policy](BUILD_POLICY.md) (sections 3, 10 and 14); this page records how the
code meets them and what is shared outside the project.

## Reporting a vulnerability

Report privately to the owner through a GitHub security advisory on this
repository. Do not open a public issue.

## Personal data

PEJIP treats the career profile (`profile.yaml`), compensation preferences, stored
analyses and recommendations as personal data.

- **Where it lives:** the profile is a local YAML file outside the repository
  (`PEJIP_PROFILE`, git-ignored). Run data is in the database at
  `PEJIP_DATABASE_URL` (SQLite by default, git-ignored). Digests are written to
  `PEJIP_OUTPUT_DIR` (git-ignored).
- **At rest:** until PEJIP is deployed, it runs on Babu's own machine and relies on
  that machine's disk encryption. On AWS, run data, the AI spend ledger and
  digests are on the EFS file system `pejip-prod-data`, encrypted with
  `alias/pejip`, TLS-only, mountable only by the app's task role, with no backups
  so nothing outlives the 90-day window ([ADR-0007](adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md)).
  The career profile is the SecureString SSM parameter `/pejip/profile`, encrypted
  with `alias/pejip` and stored by Babu, never by Terraform or in the repository.
- **Job-alert inbox:** alert emails sent to `alerts@inbox.job-search.zephyr-mcg.com`
  are received by Amazon SES and stored in the bucket `pejip-inbox-275704950192`,
  encrypted with `alias/pejip`, TLS-only, and deleted after 90 days
  ([design 0010](design/0010-job-alert-inbox.md)). AWS is already PEJIP's host,
  so no new third party receives personal data. Babu forwards his Yahoo mailbox
  there for its LinkedIn alerts, so the bucket also receives his other email:
  `pejip run` deletes any email that lists no roles, records only how many, and
  never logs or shows its sender, subject or content.
- **Retention:** each run deletes jobs, analyses, recommendations, AI usage and run
  records older than 90 days (`pejip purge` does the same on demand).
- **Export and deletion:** `pejip export <file>` writes every stored row as JSON;
  `pejip delete-all --yes` deletes them all.
- **Logs:** all logs go through a JSON formatter that redacts personal fields and
  scrubs e-mail addresses and phone numbers; `tests/unit/test_logs.py` proves it.
- **Tests and examples:** synthetic data only (`examples/profile.example.yaml`,
  the golden set's `eval/golden/profile.toml`).

## Third parties that receive personal data

| Service | What is sent | Why | Not sent |
|---|---|---|---|
| Anthropic API (Claude) | Job posting text, and from the profile only the headline, target seniority, career direction and evidence items (`CareerProfile.ai_view`) | Job analysis and requirement-to-evidence matching | Name, e-mail, compensation preferences, anything else in the profile |
| Claude Code on claude.ai (the ranking routine, Babu's plan) | The roles waiting for analysis (posting text) and from the profile only the headline, target seniority, career direction and evidence items, served by `GET /api/ranking/queue` ([design 0015](design/0015-ranking-routine.md), [ADR-0008](adr/0008-ranking-through-a-claude-code-routine.md)) | Job analysis and evidence matching without paid API calls. The routine's session transcripts stay in Babu's claude.ai history until Babu deletes them, outside PEJIP's 90-day purge, an exception to policy section 10 that comes with Babu's choice of the routine on 2026-10-05. Nothing is committed: the routine works in scratch space | Name, e-mail, compensation preferences, anything else in the profile |
| Google (Gmail), through Amazon SNS email | The daily digest: roles, rankings and explanations that cite profile evidence IDs and posting quotes, sent from the encrypted `pejip-digest` topic to Babu's own address | Babu reads the digest in their own mailbox ([ADR-0007](adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md)). Emailed copies are outside PEJIP's 90-day purge: they stay until Babu deletes them. Babu accepted this exception to policy section 10 on 2026-10-05, choosing the full digest over a summary-only email | The profile itself, contact details, compensation preferences |
| Google (sign-in) | Nothing from PEJIP: Babu signs in to their own Google account, and the load balancer receives their e-mail address and Google ID back ([ADR-0006](adr/0006-google-sign-in-at-the-load-balancer.md)) | Only Babu can use `job-search.zephyr-mcg.com` | Any career data |

| Google Fonts | Nothing from PEJIP: the browser fetches the IBM Plex font files for the portal pages, with no referrer | The portal's typefaces | Any page content or career data |

Job sources (docs/sources.md) receive only anonymous GET requests with our user
agent; no personal data is sent to them.

## Access to the hosted app

Every route except `/healthz` and `/api/ranking/*` needs Google sign-in at the load balancer, and the
app admits only the configured address (`pejip.auth`, ADR-0006). Portal pages run
no script and send a strict content security policy; every value they show is
HTML-escaped ([design 0013](design/0013-web-portal.md)). The OAuth client
ID and secret are in SSM Parameter Store (`/pejip/google-oauth/*`, encrypted with
`alias/pejip`), never in the repository.

The ranking routine runs on claude.ai and can't sign in with Google, so its two
endpoints, `/api/ranking/queue` and `/api/ranking/analyses`, skip sign-in and
need `Authorization: Bearer <key>` instead (`pejip.ranking_api`). The app
compares the key's SHA-256 with `/pejip/ranking-key-sha256` (SSM SecureString,
`alias/pejip`) in constant time; a wrong or missing key gets 401 and no response
is cached. Every answer is validated and grounded before it is stored.

## Secrets

- No Claude API key exists in CI or AWS: jobs and the app get short-lived Claude
  tokens through Workload Identity Federation (ADR-0004). Locally, `ANTHROPIC_API_KEY`
  or `ant auth login` is read by the Anthropic SDK; a key is never logged or
  committed and lives only in your shell environment.
- The ranking routine's key is PEJIP's one long-lived secret, an exception to
  policy section 5 that Babu approved on 2026-10-05. It exists only as a secret
  in the routine's claude.ai cloud environment; AWS holds just its SHA-256. It
  opens only the two ranking endpoints and is rotated every 90 days (steps in
  `infra/README.md`).
- Gitleaks runs in pre-commit and CI and blocks on any finding.

## Automated gates

The CI workflow runs lint, SAST (bandit), dependency audit (grype) and DAST (ZAP
against the health endpoint), with high and critical findings blocking, plus the
secrets scan (any finding blocks) and the Terraform gates in the Infra workflow.
See [ADR-0002](adr/0002-python-toolchain-and-ci-gates.md).
