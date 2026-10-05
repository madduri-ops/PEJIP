# Contributing to PEJIP

All work follows [docs/BUILD_POLICY.md](docs/BUILD_POLICY.md). This guide covers the
day-to-day steps.

## Setup

1. Clone the repository.
2. Install [pre-commit](https://pre-commit.com/) and enable the hooks:

   ```sh
   pip install pre-commit
   pre-commit install
   ```

3. Run the hooks once over the whole repo: `pre-commit run --all-files`.

Infrastructure work in `infra/` also needs [Terraform](https://developer.hashicorp.com/terraform/install)
1.10 or later and [TFLint](https://github.com/terraform-linters/tflint) on your PATH;
the pre-commit hooks run `terraform fmt` and `tflint`, and CI adds `terraform validate`,
checkov and, on pull requests, `terraform plan`. See [infra/README.md](infra/README.md).

### Python

The app is Python 3.12 in `src/pejip/` (see
[ADR-0002](docs/adr/0002-python-toolchain-and-ci-gates.md)). Install it with its dev
tools into a virtual environment; the pre-commit `mypy` hook uses this install:

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
```

Run what CI runs:

```sh
ruff check . && ruff format --check . && mypy          # lint
COVERAGE_FILE=.coverage.unit pytest tests/unit --cov --cov-report=
COVERAGE_FILE=.coverage.integration pytest tests/integration --cov --cov-report=
COVERAGE_FILE=.coverage.system pytest tests/system --cov --cov-report=
coverage combine && coverage json -o coverage.json && python -m ci.coverage_gate
```

Tests go in `tests/unit/`, `tests/integration/` or `tests/system/`; the directory
decides the CI stage. Coverage must stay at 100% line and at or above the branch
baseline in `.coverage-baseline.json`. When your change raises coverage, run
`python -m ci.coverage_gate --update` and commit the new baseline; it can never be
lowered. Run the API locally with `python -m pejip.api` (http://127.0.0.1:8000/healthz).

The golden evaluation set lives in `eval/` and its harness in `src/pejip/evaluation`
(tests in `tests/unit/evaluation`). `python -m pejip.evaluation validate` checks the
set. A change to prompts, models, ranking logic or scoring weights must hold the
evaluation baseline; see [eval/README.md](eval/README.md).

### Container image

The production image is built from the root `Dockerfile` (see
[ADR-0005](docs/adr/0005-app-hosting-and-continuous-deploy.md)). The `hadolint`
pre-commit hook lints it and needs Docker. To check it the way CI does:

```sh
docker build -t pejip:local .
docker run --rm --read-only --user 10001 -p 8000:8000 pejip:local   # http://127.0.0.1:8000/healthz
```

Pull requests that change `src/`, `pyproject.toml`, the `Dockerfile` or
`.dockerignore` build, smoke test and scan the image in the `Container image` check.
Merges to `main` that change them deploy to production through the Deploy workflow.

Language-specific setup for any other part of the app is added here as it lands.

## Making a change

1. Cut a short-lived branch from `main`, one branch per change.
2. Make the change with tests. A bug fix always includes tests that reproduce it.
   If the change touches architecture, an interface, a data model, an integration or
   infrastructure, update `docs/architecture/` and the feature's doc in `docs/design/`
   in the same branch.
3. Run the hooks and the test suite locally.
4. Open a pull request. It merges (squash only) once every gate is green.

Never push directly to `main`, and never weaken a gate to get a PR through. Loosening
a gate needs Babu's explicit approval in the PR.

## Policy changes

Changing the build policy means editing `docs/BUILD_POLICY.md` in a PR, bumping its
"Last updated" date, and keeping `CLAUDE.md`, this guide and the project instructions
in step.

## Releasing

Versions follow [semantic versioning](https://semver.org/) and are tagged
`vMAJOR.MINOR.PATCH` (build policy section 15). The design is in
[docs/design/0006-releases-and-rollback.md](docs/design/0006-releases-and-rollback.md).

- **Every PR** that changes user-visible behaviour adds a line under `## Unreleased`
  in [CHANGELOG.md](CHANGELOG.md). The `release-check` pre-commit hook
  (`python -m ci.release check`) keeps the changelog's structure and the version in
  `pyproject.toml` in step.
- **Cutting a release:** on a branch, run `python -m ci.release prepare X.Y.Z`. It
  moves the Unreleased notes into a dated `## X.Y.Z` section and bumps
  `pyproject.toml`. Merge that PR, then run the Release workflow on `main`:

  ```sh
  gh workflow run release.yml
  ```

  (or Actions > Release > Run workflow). It checks `CHANGELOG.md` against
  `pyproject.toml`, tags `main`'s head `vX.Y.Z` and publishes a GitHub Release with
  that version's notes.
- **Rolling back:** a failed post-deploy health gate rolls back automatically. The
  one-command manual rollback (`gh workflow run rollback.yml`) arrives with the deploy
  workflow; see the design doc's Rollback section. CI's **Rollback drill** job
  exercises a rollback to the previous release on every app change.
