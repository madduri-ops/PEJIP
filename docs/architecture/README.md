# Architecture

Living architecture docs for PEJIP. They describe the system as it is on `main` and
are updated in the same pull request as any change to architecture, interfaces,
data models, integrations or infrastructure (see
[docs/BUILD_POLICY.md](../BUILD_POLICY.md), section 7).

| Doc | Covers |
|---|---|
| [overview.md](overview.md) | Purpose, context, and the system at a glance |
| [components.md](components.md) | Each component, its responsibility and interfaces |
| [data-flow.md](data-flow.md) | How data moves from sources to ranked, explained roles |

Diagrams are written in [Mermaid](https://mermaid.js.org/) inside the Markdown so they
render on GitHub and change visibly in review. Decisions behind the architecture are
recorded as ADRs in [docs/adr/](../adr/); feature-level detail lives in
[docs/design/](../design/).
