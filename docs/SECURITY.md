# Security

Security posture for PEJIP. The binding rules are in the
[build policy](BUILD_POLICY.md) (sections 3, 10 and 14); this page records how the
code meets them and what is shared outside the project.

## Reporting a vulnerability

Report privately to the owner through a GitHub security advisory on this
repository. Do not open a public issue.

## Personal data

PEJIP treats the career profile (`profile.yaml`), compensation preferences, the
LinkedIn connections export and network decisions, stored analyses and
recommendations as personal data.

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
- **LinkedIn connections:** the export is a local file outside the repository
  (`PEJIP_CONNECTIONS`, and the decisions file `PEJIP_NETWORK_DECISIONS`; both
  git-ignored names). PEJIP never needs a LinkedIn login, drops e-mail addresses as
  it reads the file, sends no connection data to Claude or any other service, and
  logs no names or profile URLs ([design 0014](design/0014-connection-matching.md)).
  On AWS the export and decisions file are uploaded by Babu to `network/` in the
  inbox bucket (encrypted with `alias/pejip`, TLS-only, deleted 90 days after
  upload); the app's role can list and read that prefix only.
  The names and titles of the connections shown for a role are stored with that
  role's recommendation, so they follow its 90-day retention, export and deletion.
- **Retention:** each run deletes jobs, analyses, recommendations, AI usage and run
  records older than 90 days (`pejip purge` does the same on demand).
- **Export and deletion:** `pejip export <file>` writes every stored row as JSON;
  `pejip delete-all --yes` deletes them all.
- **Logs:** all logs go through a JSON formatter that redacts personal fields and
  scrubs e-mail addresses and phone numbers; `tests/unit/test_logs.py` proves it.
- **Tests and examples:** synthetic data only (`examples/profile.example.yaml`,
  `examples/Connections.example.csv`, the golden set's `eval/golden/profile.toml`).

## Third parties that receive personal data

| Service | What is sent | Why | Not sent |
|---|---|---|---|
| Anthropic API (Claude) | Job posting text, and from the profile only the headline, target seniority, career direction and evidence items (`CareerProfile.ai_view`) | Job analysis and requirement-to-evidence matching | Name, e-mail, compensation preferences, anything else in the profile |
| Google (Gmail), through Amazon SNS email | The daily digest: roles, rankings and explanations that cite profile evidence IDs and posting quotes, sent from the encrypted `pejip-digest` topic to Babu's own address | Babu reads the digest in their own mailbox ([ADR-0007](adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md)). Emailed copies are outside PEJIP's 90-day purge: they stay until Babu deletes them. Babu accepted this exception to policy section 10 on 2026-10-05, choosing the full digest over a summary-only email | The profile itself, contact details, compensation preferences |
| Google (sign-in) | Nothing from PEJIP: Babu signs in to their own Google account, and the load balancer receives their e-mail address and Google ID back ([ADR-0006](adr/0006-google-sign-in-at-the-load-balancer.md)) | Only Babu can use `job-search.zephyr-mcg.com` | Any career data |

| Google Fonts | Nothing from PEJIP: the browser fetches the IBM Plex font files for the portal pages, with no referrer | The portal's typefaces | Any page content or career data |

Job sources (docs/sources.md) receive only anonymous GET requests with our user
agent; no personal data is sent to them.

## Access to the hosted app

Every route except `/healthz` needs Google sign-in at the load balancer, and the
app admits only the configured address (`pejip.auth`, ADR-0006). Portal pages run
no script and send a strict content security policy; every value they show is
HTML-escaped ([design 0013](design/0013-web-portal.md)). The OAuth client
ID and secret are in SSM Parameter Store (`/pejip/google-oauth/*`, encrypted with
`alias/pejip`), never in the repository.

## Secrets

- No Claude API key exists in CI or AWS: jobs and the app get short-lived Claude
  tokens through Workload Identity Federation (ADR-0004). Locally, `ANTHROPIC_API_KEY`
  or `ant auth login` is read by the Anthropic SDK; a key is never logged or
  committed and lives only in your shell environment.
- Gitleaks runs in pre-commit and CI and blocks on any finding.

## Automated gates

The CI workflow runs lint, SAST (bandit), dependency audit (grype) and DAST (ZAP
against the health endpoint), with high and critical findings blocking, plus the
secrets scan (any finding blocks) and the Terraform gates in the Infra workflow.
See [ADR-0002](adr/0002-python-toolchain-and-ci-gates.md).
