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

### Python app

Python 3.11 or later (CI uses 3.12).

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Checks, the same ones CI runs:

```sh
ruff check . && ruff format --check . && mypy        # lint and types
pytest tests/unit                                     # unit tests
pytest -m "not system" --cov --cov-branch --cov-report=json \
  && python scripts/check_coverage.py                 # coverage gate and ratchet
pytest -m system                                      # CLI end to end against stub servers
pejip eval                                            # golden set, replaying recorded AI output
bandit -r src --severity-level high                   # SAST
```

`pejip eval --live` calls the model and needs `ANTHROPIC_API_KEY`; CI runs it when a
prompt, the AI client, the analysis code, `config/search.yaml` or `evals/` changes.
When coverage or an evaluation score rises, raise `coverage-baseline.json` or
`evals/baseline.json` in the same PR; neither may go down.

Tests and examples use synthetic data only. Never commit a real `profile.yaml`,
database or digest; `.gitignore` excludes them.

## Making a change

1. Cut a short-lived branch from `main`, one branch per change.
2. Make the change with tests. A bug fix always includes tests that reproduce it.
   If the change touches architecture, an interface, a data model, an integration or
   infrastructure, update `docs/architecture/` and the feature's doc in `docs/design/`
   in the same branch. A new job source also needs a row in `docs/sources.md`, and a
   new AI call states its expected monthly cost in the PR.
3. Run the hooks and the test suite locally.
4. Open a pull request. It merges (squash only) once every gate is green.

Never push directly to `main`, and never weaken a gate to get a PR through. Loosening
a gate needs Babu's explicit approval in the PR.

## Policy changes

Changing the build policy means editing `docs/BUILD_POLICY.md` in a PR, bumping its
"Last updated" date, and keeping `CLAUDE.md`, this guide and the project instructions
in step.
