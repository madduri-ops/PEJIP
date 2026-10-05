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
