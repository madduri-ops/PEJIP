# CLAUDE.md

Guidance for Claude and other contributors working in this repository.

## Project

PEJIP (Personal Executive Job Intelligence Platform): a personal analyst that keeps
finding executive and senior-leadership roles, ranks which deserve attention, and
explains why. It is not a generic job board.

## Build policy

All work must follow [docs/BUILD_POLICY.md](docs/BUILD_POLICY.md). Read it before
adding code, tests, CI workflows or infrastructure. In short:

- 100% line coverage, 95% branch coverage, lint passing, coverage ratchet that never goes down.
- Security gates fail the build: secrets (any finding), SAST/DAST/dependency audit (high and critical).
- Every bug fix ships with tests that cover it.
- Never add `|| true`, `continue-on-error` or similar to make a gate pass.
- Trunk-based branching: one short-lived branch off `main` per change, merged only by PR with all gates green, squash merges, no direct pushes to `main`; branch protection lives in `.github/rulesets/main.json`.
- Once a PR is ready, follows this policy and passes every gate, squash merge it without waiting to be asked (except a PR that loosens a gate, which needs Babu's approval).
- Architecture docs (`docs/architecture/`) and per-feature design docs (`docs/design/`) are updated in the same PR as any change to architecture, interfaces, data models, integrations or infrastructure; significant decisions also get an ADR in `docs/adr/`.
- Dependabot covers every package ecosystem, pre-commit hooks run locally and in CI, and `CONTRIBUTING.md` stays current.

## Product policies

Sections 10 to 15 of the build policy, in short:

- **Data privacy:** career data is encrypted at rest and in transit, personal data kept for 90 days, never in logs or test fixtures, and shared with an outside service only when listed in `docs/SECURITY.md`.
- **Job sources:** fetch only sources listed in `docs/sources.md` whose terms allow it, honour `robots.txt`, and route every fetch through the shared rate limiter.
- **AI quality:** prompts are versioned files, ranking changes must pass the committed evaluation set, and every explanation cites its evidence.
- **AI cost:** all AI calls go through one client that enforces the $100 monthly cap and alerts at 50% and every 10% after; a PR adding an AI call states its expected cost.
- **Observability:** structured logs, metrics and traces, with personal data redacted and a test that proves it.
- **Releases:** semantic version tags, `CHANGELOG.md`, backward-compatible migrations and a tested rollback.

## Keeping the policy current

When the build policy changes (a new rule, a changed threshold, a gate added or
removed), update `docs/BUILD_POLICY.md` in the same change and bump its
"Last updated" date. The policy is mirrored in the PEJIP project instructions, so
those must be updated too. Do not let the code, CI config and policy drift apart:
if a change would violate the policy, either change the code or propose a policy
update explicitly.
