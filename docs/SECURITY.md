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
- **Retention:** each run deletes jobs, analyses, recommendations, AI usage and run
  records older than 90 days (`pejip purge` does the same on demand).
- **Export and deletion:** `pejip export <file>` writes every stored row as JSON;
  `pejip delete-all --yes` deletes them all.
- **Logs:** all logs go through a JSON formatter that redacts personal fields and
  scrubs e-mail addresses and phone numbers; `tests/unit/test_logs.py` proves it.
- **Tests and examples:** synthetic data only (`examples/profile.example.yaml`,
  `evals/golden.yaml`).

## Third parties that receive personal data

| Service | What is sent | Why | Not sent |
|---|---|---|---|
| Anthropic API (Claude) | Job posting text, and from the profile only the headline, target seniority, career direction and evidence items (`CareerProfile.ai_view`) | Job analysis and requirement-to-evidence matching | Name, e-mail, compensation preferences, anything else in the profile |

Job sources (docs/sources.md) receive only anonymous GET requests with our user
agent; no personal data is sent to them.

## Secrets

- `ANTHROPIC_API_KEY` is read from the environment by the Anthropic SDK. It is never
  logged or committed; locally it lives in your shell environment, in CI it is the
  `ANTHROPIC_API_KEY` repository secret used only by the live evaluation job.
- Gitleaks runs in pre-commit and CI and blocks on any finding.

## Automated gates

Lint, SAST (bandit; high severity blocks, full report uploaded), dependency audit
(pip-audit; any known vulnerability blocks), secrets scanning, and the Terraform
gates in the Infra workflow. DAST and the API smoke test are added with the first
HTTP endpoint.
