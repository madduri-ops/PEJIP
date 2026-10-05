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
| [0004](0004-keyless-claude-access.md) | Keyless Claude access through Workload Identity Federation | Accepted |
| [0005](0005-app-hosting-and-continuous-deploy.md) | Serve PEJIP from Fargate behind a WAF-fronted ALB, deployed by GitHub Actions | Accepted |
| [0006](0006-google-sign-in-at-the-load-balancer.md) | Require Google sign-in at the load balancer, with an allow-list check in the app | Accepted |
| [0007](0007-sqlite-on-efs-and-a-scheduled-daily-run.md) | Keep PEJIP's data in SQLite on encrypted EFS, written by a scheduled daily run | Accepted |
| [0008](0008-ranking-through-a-claude-code-routine.md) | Rank roles through a Claude Code routine on Babu's plan | Proposed |
