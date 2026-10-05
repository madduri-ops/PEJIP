# Changelog

All notable changes to PEJIP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH` tags.

Add a line under **Unreleased** in every pull request that changes user-visible
behaviour, using the headings Added, Changed, Deprecated, Removed, Fixed and
Security. Releasing is described in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## Unreleased

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
- Release tooling: this changelog, version checks, tagged GitHub Releases and a
  rollback workflow.
