# ADR-0002: Python toolchain and CI gates

**Status:** Proposed (2026-10-05)

## Context

The first application code is Python, as the FIND specification recommends
(section 14.4: Python, FastAPI, PostgreSQL). The build policy (sections 1 to 4 and
9) requires 100% line and 95% branch coverage across unit, integration and system
tests with a ratchet, lint with a warning threshold, blocking security gates
(secrets: any finding; SAST, DAST, dependency audit: high and critical), a staged
pipeline, an API smoke test against the running server, a build-artifact check,
Dependabot for every ecosystem and pre-commit hooks that CI also runs. Several
threads are adding Python code at once, so the layout and tools need to be fixed
before they land.

## Decision

- **Layout:** one package, `src/pejip/`, built with hatchling from `pyproject.toml`.
  Tests live in `tests/unit/`, `tests/integration/` and `tests/system/`; the
  directory decides the CI stage. CI gate scripts live in `ci/` and are tested and
  covered like app code.
- **Python 3.12**, dependencies pinned exactly in `pyproject.toml` and kept current
  by Dependabot (`pip`).
- **HTTP surface:** FastAPI served by uvicorn (`python -m pejip.api`), starting with
  the `/healthz` endpoint the load balancer and post-deploy gate poll. Interactive
  docs are off; the OpenAPI document stays on because the smoke test and DAST
  enumerate routes from it.
- **Lint:** ruff (lint and format) and mypy `--strict`. Ruff has no warning level,
  so the warning threshold is zero.
- **Tests and coverage:** pytest with coverage.py branch coverage. Each test stage
  writes its own data file and a final job combines them. The committed
  `.coverage-baseline.json` is the threshold, never below the 100% line and 95%
  branch policy floors; the gate fails if a PR lowers it below the base branch's,
  and prompts the PR to raise it when coverage improves.
- **Secrets:** gitleaks over the full git history in CI and on staged changes in
  pre-commit.
- **SAST:** bandit; **dependency audit:** grype over the resolved environment;
  **DAST:** OWASP ZAP API scan against the installed app. Each scanner runs in
  report mode so every finding is uploaded, and `ci/severity_gate.py` fails the
  build on high and critical findings.
- **Build-artifact check:** `ci/check_wheel.py` fails if the wheel ships anything
  besides the `pejip` package, or any dev, demo or test code. System tests run
  against the installed wheel.
- **Required checks:** every CI job is listed in `.github/rulesets/main.json`.
  Docs-only changes skip the app stages, and skipped jobs count as passed, so the
  change-detection job is required too. Hooks and the secrets scan always run.

## Consequences

- Every Python PR runs the same staged gates; adding an endpoint automatically adds
  it to the smoke test and the DAST scan.
- Contributors install with `pip install -e '.[dev]'` and run the same commands CI
  runs (see `CONTRIBUTING.md`).
- The ratchet raises the bar only when a PR commits a higher baseline, so a PR that
  improves coverage carries its own baseline bump.
- Scanner choices (bandit, grype, ZAP, gitleaks) can change in a later ADR without
  touching the gate script contract: report in JSON, gate on severity.
