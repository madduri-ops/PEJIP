# PEJIP

**Personal Executive Job Intelligence Platform:** a personal analyst that keeps
finding executive and senior-leadership roles, ranks which deserve attention, and
explains why.

> **Draft:** the four philosophy sections below are a first draft written for Babu to
> confirm or adjust. Remove this note once they are agreed.

## What we are building

A personal job-market intelligence analyst for one person's executive career search.
It works continuously in the background:

- **Finds** executive and senior-leadership opportunities across many sources,
  including roles that are hard to spot on general job boards.
- **Ranks** them by how well each one fits the candidate's experience, goals and
  constraints, so the few that matter rise to the top.
- **Explains** every ranking in plain language: why a role fits, where it falls short,
  and what is worth checking before acting.

It is **not** a job board. A job board lists everything and leaves the judgement to
the reader. PEJIP does the judgement and shows its working.

## Why we are building it

- Executive roles are scarce, scattered across boards, search firms, company sites and
  networks, and often described in vague titles that keyword search misses.
- Senior candidates have little time. Reading hundreds of listings to find a handful
  worth pursuing is the wrong use of it.
- Generic job tools optimise for volume and clicks. An executive search needs the
  opposite: fewer, better opportunities, with reasons that can be trusted.
- A ranking without an explanation is a black box. Explaining every decision makes the
  system's judgement checkable, correctable and better over time.

## How we are building it

- **Signal over volume.** Every feature is judged by whether it helps decide which
  roles deserve attention, not by how many roles it can show.
- **Explainable by design.** Each score comes with the evidence behind it. If the
  system cannot explain a ranking, it does not show it as a recommendation.
- **Personal first.** The candidate's profile, preferences and feedback drive the
  ranking, and the data stays private to them.
- **Quality as a gate, not an afterthought.** 100% line coverage, blocking security
  gates, staged CI and continuous deploy, as set out in the
  [build policy](docs/BUILD_POLICY.md).
- **Small, reviewed, documented changes.** Trunk-based development, one short-lived
  branch per change, and architecture and design docs that change with the code.

## How we measure success

- **Precision of attention:** most of the roles PEJIP puts at the top are ones the
  candidate judges worth pursuing.
- **Coverage of the market:** relevant roles the candidate hears about elsewhere were
  already found by PEJIP, and found early.
- **Trust in the explanations:** the candidate agrees with the stated reasons, and
  disagreements feed back into better rankings.
- **Time saved:** less time spent screening listings, more time spent on the few
  opportunities that matter.
- **Outcomes:** conversations, interviews and offers that trace back to roles PEJIP
  surfaced.

Concrete targets for each measure will be set as the first components land and
recorded in the [architecture overview](docs/architecture/overview.md).

## Status

Early stage. The build policy, repository hygiene and documentation skeletons are in
place; application code has not landed yet.

## Getting started

Setup, local checks and the branch and pull request flow are in
[CONTRIBUTING.md](CONTRIBUTING.md). Language-specific steps are added there as each
part of the app lands.

## Project structure

| Path | What it holds |
|---|---|
| [`docs/BUILD_POLICY.md`](docs/BUILD_POLICY.md) | Binding CI/CD and engineering policy |
| [`docs/architecture/`](docs/architecture/) | System overview, components, data flow |
| [`docs/design/`](docs/design/) | One design doc per feature |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`.github/`](.github/) | Dependabot, PR template, branch protection ruleset |
| [`CLAUDE.md`](CLAUDE.md) | Guidance for Claude working in this repo |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [build policy](docs/BUILD_POLICY.md).

## Security

Security posture and how to report a vulnerability will live in
`docs/SECURITY.md` (required by the build policy, section 7). Until it lands, report
issues privately to the owner through a GitHub security advisory on this repository.

## License

Private project. All rights reserved; no license is granted to use, copy or
distribute this code.
