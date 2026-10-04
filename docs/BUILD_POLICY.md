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

### 5.1 AWS hosting

PEJIP runs on AWS as its own application, isolated from the CyberSecurity-KRI
dashboard. The full decision is [ADR-0001](adr/0001-aws-hosting-isolated-from-kri.md).

- **Account and region:** AWS account `275704950192`, region `us-west-2` (shared with
  KRI); isolation comes from separate resources, scoped IAM and separate state.
- **Nothing shared with KRI:** PEJIP has its own Terraform state, VPC, ALB, ECR
  repository, ECS cluster and service, IAM roles, KMS key, secrets, log groups, SNS
  topic and alarms. No PEJIP Terraform references a KRI resource, and no KRI resource
  is granted access to PEJIP's. The GitHub OIDC identity provider is the one
  account-wide object both use; PEJIP reads it with a data source and does not manage it.
- **Naming:** every resource name starts with `pejip-` (`pejip-prod` for the
  environment-scoped ones); secrets live under `pejip/`, logs under `/ecs/pejip-prod`,
  metrics in the `PEJIP` namespace.
- **Tags:** provider `default_tags` set `Project = "PEJIP"`, `Application = "pejip"`,
  `Environment`, `ManagedBy = "Terraform"`, `Owner = "Babu"` and
  `Repository = "madduri-ops/PEJIP"`; resources holding career data add
  `DataClassification = "personal"`. `Project` is a cost allocation tag and the
  PEJIP AWS Budget filters on it.
- **Terraform state:** S3 bucket `pejip-tfstate-275704950192`, key
  `pejip/prod/terraform.tfstate`, versioned, encrypted with the `alias/pejip` KMS key,
  public access blocked, S3 native locking.
- **Deploy identity:** GitHub Actions assumes `pejip-github-deploy` (trusts only
  `main` of `madduri-ops/PEJIP`) to deploy, and `pejip-github-plan` (pull requests,
  read only) for `terraform plan`. Both are scoped to `pejip` resource ARNs. Role
  ARNs are GitHub Actions variables; no AWS keys exist in GitHub or the repo.
- **Images:** ECR repository `pejip` with immutable tags (commit SHA and release
  version), scan on push, last 10 images kept.
- **Changes to hosting** (account, region, a shared resource, a wider IAM scope) need
  a new ADR that supersedes ADR-0001.

## 6. Alerting

- Email alerts on CI failure.
- Email alerts on deploy success and on deploy failure.

## 7. Documentation and review

- **Architecture docs** live in `docs/architecture/`: a system overview, the component
  catalogue, data flow, and diagrams written in Mermaid so they render on GitHub and
  diff in review.
- **Design docs** live in `docs/design/`, one file per feature, covering its purpose,
  interfaces, data model, and the trade-offs taken.
- **Docs change with the code:** a pull request that changes architecture, a
  component's responsibilities, an interface or API, a data model or schema, an
  external integration, or infrastructure updates the affected architecture and
  design docs in the same PR. A new feature adds its design doc in the PR that
  introduces it. The PR template carries a docs checkbox, and stale or missing docs
  block the merge the same way a failing gate does.
- Architecture decision records live in `docs/adr/`. A significant decision gets an
  ADR, and the architecture and design docs are updated to reflect it.
- Security posture and reporting live in `docs/SECURITY.md`.
- Code review by Claude is **on demand only**, not scheduled.

## 8. Branching and merging

Trunk-based development, since every merge to `main` deploys:

- Work happens on short-lived feature branches cut from `main`, one branch per change.
- Changes reach `main` only through a pull request, and only when every gate is green.
- Pull requests are squash merged.
- No direct pushes to `main`.
- **Auto-merge when green:** once a pull request is ready, complies with this policy and
  passes every gate, Claude squash merges it without waiting to be asked. A PR with a
  failing gate, a merge conflict, an unresolved review thread or an open question is
  not merged. A PR that loosens a gate still waits for Babu's explicit approval.
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

## 10. Data privacy

PEJIP holds Babu's career data: profile, compensation, preferences, applications and
notes. It is treated as personal data.

- **Encryption:** personal data is encrypted at rest (cloud KMS-managed keys) and in
  transit (TLS 1.2 or later). No plaintext copies in buckets, caches, test fixtures or
  CI artifacts.
- **Access:** only the app's own service identity and Babu can read it, with
  least-privilege IAM defined in Terraform. No public buckets or endpoints that
  return personal data without authentication.
- **Retention:** personal data, job postings and derived rankings are each
  kept for **90 days**. Expired data is deleted by a scheduled
  job that has its own tests. Backups follow the same retention.
- **Deletion and export:** a tested command deletes or exports all personal data on
  request.
- **Third parties:** personal data is sent to an outside service (an AI provider,
  for example) only when that service is listed in `docs/SECURITY.md` with what is
  sent and why, and only with the minimum fields the task needs.
- **Test data:** tests and demos use synthetic data, never real personal data.

## 11. Job source rules

- **Allowed sources only:** a job source is used only when its terms of service or
  API terms permit automated access for this use. Each source is recorded in
  `docs/sources.md` with a link to its terms, the access method (official API, feed or
  page fetch), its rate limit and the date its terms were last reviewed. A source not
  listed there is not fetched.
- **Robots and terms:** page fetchers honour `robots.txt`. No login-walled scraping,
  CAPTCHA bypassing or rotating identities to evade limits.
- **Rate limits on every fetch:** every source client goes through a shared limiter
  with a per-source budget, backoff on 429 and 5xx responses, and a clear user agent.
  A fetch path that bypasses the limiter fails review, and the limiter has tests.
- **Terms change:** when a source's terms stop allowing our use, it is disabled in
  the same change that updates `docs/sources.md`.

## 12. AI quality

- **Versioned prompts:** prompts live in the repo as files with a version, never
  inline strings built at runtime. Every ranking and explanation records the prompt
  version and model that produced it.
- **Evaluation set:** a committed test set of job postings with expected rankings and
  reasons is the quality bar. A change to a prompt, model, ranking logic or scoring
  weights runs the evaluation in CI, and the PR fails if scores drop below the
  committed baseline. Like coverage, the baseline only goes up.
- **Explanations cite evidence:** every "why this role" explanation cites the
  specific facts it relies on (posting text, company data, profile fields), and each
  citation resolves to stored source data. An explanation with an unsupported claim
  fails its tests.
- **Failure handling:** model errors, timeouts and malformed output are handled and
  tested; a failed ranking is shown as unranked, never as a made-up result.

## 13. AI cost limits

- **Monthly cap:** total AI spend is capped at **$100 per month**.
  Calls go through one client that tracks spend and refuses new non-essential
  calls once the cap is reached.
- **Alerts:** email alerts at **50% of the cap and at every further 10%** (60%, 70%,
  80%, 90%, 100%), configured in Terraform alongside the other alarms.
- **Visibility:** spend is recorded per feature and per model so the cost of each
  feature is known.
- **Cost in review:** a PR that adds an AI call or changes a model states its
  expected monthly cost.

## 14. Observability

- **Structured logs:** logs are structured (JSON) with a request or job id that ties
  related entries together.
- **Metrics and traces:** each service emits metrics (request rate, errors, latency,
  fetch counts per source, AI calls and spend) and distributed traces across
  fetching, ranking and the API.
- **No personal data in logs:** logs, metrics, traces and error reports never contain
  personal data or secrets. Logging goes through a redaction layer, and a test
  asserts that known personal fields are redacted.
- **Alarms:** alarms on error rate, failed fetch runs and stalled pipelines are
  defined in Terraform and email Babu, in line with section 6.

## 15. Releases

- **Semantic versioning:** releases are tagged `vMAJOR.MINOR.PATCH`.
- **Changelog:** `CHANGELOG.md` is updated in each PR that changes user-visible
  behaviour, and each release lists its changes.
- **Tested rollback:** each deploy can be rolled back to the previous release with
  one documented command or workflow. Rollback is exercised in CI or a staging
  environment, and a failed post-deploy health gate rolls back automatically.
- **Data migrations:** schema migrations are backward compatible with the previous
  release so a rollback does not break on the new schema.

## Keeping this policy current

- This file is the source of truth in the repo. The same policy is also kept in the
  PEJIP project instructions; when the policy changes, update both in the same change.
- Policy changes go through a pull request that edits this file and bumps the
  "Last updated" date.
- Gates may be tightened at any time. Loosening a gate (lower threshold, non-blocking
  severity, skipped check) requires Babu's explicit approval in the PR.
