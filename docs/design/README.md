# Design docs

One design doc per feature, named `NNNN-short-title.md` (for example
`0001-role-discovery.md`). Copy [TEMPLATE.md](TEMPLATE.md) to start one.

A feature's design doc is added in the pull request that introduces the feature and
updated in every later PR that changes its interfaces, data model or behaviour (see
[docs/BUILD_POLICY.md](../BUILD_POLICY.md), section 7). Decisions with lasting
consequences also get an ADR in [docs/adr/](../adr/).

| Doc | Status |
|---|---|
| [0001: CI pipeline and health endpoint](0001-ci-pipeline.md) | Implemented |
| [0002: AI cost guard](0002-ai-cost-guard.md) | Implemented |
| [0003: Golden evaluation set](0003-golden-evaluation-set.md) | Implemented |
| [0004: Data retention](0004-data-retention.md) | Implemented |
| [0005: App hosting and continuous deploy](0005-app-hosting-and-deploy.md) | Implemented |
| [0006: Releases and rollback](0006-releases-and-rollback.md) | Implemented |
| [0007: Keyless Claude access](0007-claude-identity-federation.md) | Accepted |
| [0008: FIND thin slice](0008-find-thin-slice.md) | Implemented |
| [0009: Google sign-in](0009-google-sign-in.md) | Implemented |
