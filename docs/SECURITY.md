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
  that machine's disk encryption. The deployed service will store data only in
  KMS-encrypted AWS storage under `alias/pejip` (ADR-0001).
- **Job-alert inbox:** alert emails sent to `alerts@inbox.job-search.zephyr-mcg.com`
  are received by Amazon SES and stored in the bucket `pejip-inbox-275704950192`,
  encrypted with `alias/pejip`, TLS-only, and deleted after 90 days
  ([design 0010](design/0010-job-alert-inbox.md)). AWS is already PEJIP's host,
  so no new third party receives personal data.
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
| Google (sign-in) | Nothing from PEJIP: Babu signs in to their own Google account, and the load balancer receives their e-mail address and Google ID back ([ADR-0006](adr/0006-google-sign-in-at-the-load-balancer.md)) | Only Babu can use `job-search.zephyr-mcg.com` | Any career data |

Job sources (docs/sources.md) receive only anonymous GET requests with our user
agent; no personal data is sent to them.

## Access to the hosted app

Every route except `/healthz` needs Google sign-in at the load balancer, and the
app admits only the configured address (`pejip.auth`, ADR-0006). The OAuth client
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
