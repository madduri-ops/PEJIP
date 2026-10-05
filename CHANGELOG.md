# Changelog

All notable changes to PEJIP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH` tags.

Add a line under **Unreleased** in every pull request that changes user-visible
behaviour, using the headings Added, Changed, Deprecated, Removed, Fixed and
Security. Releasing is described in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## Unreleased

### Added

- Hosting for `https://job-search.zephyr-mcg.com` in Terraform: VPC, load balancer
  with WAF and HTTPS certificate, ECS Fargate service, service alarms and a daily
  retention purge schedule (off until the app has a database).
- Production container image, scanned on every pull request, and continuous deploy
  on `main` with a health gate, automatic rollback and email on the result.

### Security

- Keyless Claude access: CI and the app authenticate to the Claude API through
  Workload Identity Federation (GitHub Actions OIDC, AWS STS) instead of an API key.
- The app's ECS task role can now request identity tokens for the Claude API only.

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
