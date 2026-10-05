# Changelog

All notable changes to PEJIP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH` tags.

Add a line under **Unreleased** in every pull request that changes user-visible
behaviour, using the headings Added, Changed, Deprecated, Removed, Fixed and
Security. Releasing is described in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## Unreleased

### Changed

- The job search covers Anthropic, the one target company whose roles are
  available through an allowed public API; the example company boards are gone.
- For testing, the search also covers the public Greenhouse boards of nine Bay
  Area companies: Stripe, Databricks, Airbnb, Figma, Dropbox, Pinterest,
  Instacart, Robinhood and Scale AI.

### Added

- Job-alert inbox: `alerts@inbox.job-search.zephyr-mcg.com` receives career-site job
  alerts through Amazon SES into an encrypted bucket kept for 90 days.
- `pejip run` reads that inbox when `PEJIP_INBOX_BUCKET` is set: roles in alerts
  from Google, NVIDIA, Meta, Micron, OpenAI and Microsoft are ranked with the rest,
  and alert sign-up checks show up in the digest with their confirm link.
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
