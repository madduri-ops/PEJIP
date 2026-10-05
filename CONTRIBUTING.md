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

The golden evaluation harness lives in `src/pejip/evaluation` with its tests in
`tests/unit/evaluation`; `python -m pejip.evaluation validate` checks the set. A change to prompts, models, ranking logic or scoring weights must hold the evaluation
baseline; see [eval/README.md](eval/README.md).

Language-specific setup (runtimes, package installs, test commands) is added here as
each part of the app lands.

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
