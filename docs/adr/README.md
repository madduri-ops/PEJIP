# Architecture decision records

One file per decision, named `NNNN-short-title.md`, using the
[Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):
Title, Status, Context, Decision, Consequences. ADRs are never edited after they are
accepted; a later ADR supersedes an earlier one. When an ADR changes the
architecture, update [docs/architecture/](../architecture/) in the same PR.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-aws-hosting-isolated-from-kri.md) | Host PEJIP on AWS, isolated from the KRI dashboard | Accepted |
| [0002](0002-python-toolchain-and-ci-gates.md) | Python toolchain and CI gates | Proposed |
| [0003](0003-python-cli-first-slice.md) | Build the first FIND slice as a Python batch CLI with a portable store | Accepted |
