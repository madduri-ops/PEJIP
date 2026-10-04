# Build Policy (CI/CD)

This is the binding CI/CD policy for PEJIP. Every change, by a person or by Claude,
must comply with it. When the policy changes, update this file in the same change
(see [Keeping this policy current](#keeping-this-policy-current)).

_Owner: Babu (@madduri-ops). Last updated: 2026-10-04._

## 1. Code quality and coverage

- **Line coverage:** 100%.
- **Branch coverage:** 95%, measured across functional, integration and system tests.
- **Lint:** must pass; the lint step fails when warnings exceed a set threshold.
- **Coverage ratchet:** a committed coverage baseline is the enforced threshold. It is
  raised on `main` whenever coverage improves and never goes down.

## 2. Testing

- Every bug fix adds matching functional, integration and/or system tests.
- Non-functional aspects of the app are tested: performance, security, reliability,
  accessibility, and others as they apply.
- **API smoke test:** every endpoint is exercised against the real running server.
- **Build-artifact check:** verifies that dev/demo-only code is stripped from
  production builds.

## 3. Security gates

Security gates must **fail the build**. No `|| true`, no `continue-on-error`, no
forcing exit code 0.

| Gate | Blocks the build | Reported only (uploaded as artifacts) |
|---|---|---|
| Secrets scanning | Any finding | n/a |
| SAST | High, critical | Medium, low |
| DAST (against the real app surface) | High, critical | Medium, low |
| Dependency audit | High, critical | Medium, low |

## 4. Pipeline shape

Staged pipeline, in this order:

1. Lint
2. Unit tests
3. In parallel: integration tests, SAST, system tests
4. DAST

CI hygiene:

- Cancel superseded runs.
- Skip CI on docs-only changes.
- Run the heaviest gates on pull requests.
- Upload coverage, DAST and system-test reports as artifacts.

## 5. Deployment and infrastructure

- Continuous deploy on `main`.
- Cloud auth via OIDC; no long-lived keys.
- Post-deploy health gate that polls a health endpoint.
- Infrastructure as code (Terraform), including alarms.

## 6. Alerting

- Email alerts on CI failure.
- Email alerts on deploy success and on deploy failure.

## 7. Documentation and review

- Architecture decision records live in `docs/adr/`.
- Security posture and reporting live in `docs/SECURITY.md`.
- Code review by Claude is **on demand only**, not scheduled.

## 8. Branching and merging

Trunk-based development, since every merge to `main` deploys:

- Work happens on short-lived feature branches cut from `main`, one branch per change.
- Changes reach `main` only through a pull request, and only when every gate is green.
- Pull requests are squash merged.
- No direct pushes to `main`.
- **Branch protection as code:** the `main` protection rules are checked in at
  `.github/rulesets/main.json` (required status checks, PR required, squash only,
  no force pushes or deletions) and applied to the repository from that file.
  Any change to the rules goes through a PR that edits it.

## 9. Dependencies and local checks

- **Dependabot:** `.github/dependabot.yml` opens weekly update PRs for every package
  ecosystem in the repo, GitHub Actions included. When a new ecosystem is added
  (npm, pip, Docker, Terraform), it is added to `dependabot.yml` in the same change.
  Dependabot PRs pass the same gates as any other PR.
- **Pre-commit hooks:** `.pre-commit-config.yaml` runs fast checks before each commit:
  secrets scanning, whitespace and file hygiene, and the lint and format tools for
  each language in the repo. CI runs the same hooks, so skipping them locally does
  not skip them.
- **Contributor guide:** `CONTRIBUTING.md` explains the local setup, how to run the
  hooks and tests, and the branch and PR flow. It is updated when any of those change.

## Keeping this policy current

- This file is the source of truth in the repo. The same policy is also kept in the
  PEJIP project instructions; when the policy changes, update both in the same change.
- Policy changes go through a pull request that edits this file and bumps the
  "Last updated" date.
- Gates may be tightened at any time. Loosening a gate (lower threshold, non-blocking
  severity, skipped check) requires Babu's explicit approval in the PR.
