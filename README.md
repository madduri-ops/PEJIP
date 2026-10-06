# PEJIP

**Personal Executive Job Intelligence Platform:** a personal analyst that keeps
finding executive and senior-leadership roles, ranks which deserve attention, and
explains why.

## What we are building

A personal job-market intelligence analyst for an executive career search. It answers
one question:

> What are the best new opportunities for me right now, why do they fit, and where do
> I already have an advantage?

It behaves less like a job board and more like an analyst. The roadmap has three
phases:

- **Phase 1, FIND** (current): discover, understand, score, prioritize, explain,
  monitor and learn.
- **Phase 2, PURSUE:** tailor, network, apply and manage selected opportunities.
- **Phase 3, WIN & ANTICIPATE:** prepare for interviews, learn from outcomes, and spot
  opportunities before or as they emerge.

Phase 1 continuously discovers senior-leadership roles from company career sites, job
sources, professional signals and market intelligence; verifies and deduplicates them;
matches them against a structured career profile; uses LinkedIn connections as a
prioritization signal; and presents each opportunity with separate Fit, Confidence and
Priority assessments and an evidence-backed explanation. It ends at an informed human
decision. It does not apply for jobs, contact anyone, rewrite resumes or make career
decisions.

## Why we are building it

- Executive roles are scattered across career sites, boards and networks, and are
  described in titles that a short keyword list misses.
- A senior candidate's time is the scarcest input. Screening hundreds of listings to
  find the few that matter is the wrong use of it.
- Most tools collapse everything into one opaque score. A recommendation is only useful
  if it shows what the job requires, what the candidate has actually done, and how sure
  the system is.
- The most important part of the search is finding the right opportunities and
  understanding them correctly. Phase 1 makes that part dramatically better before
  automating anything else.

## How we are building it

- **Thin end-to-end slice first.** Build a working pipeline (discover, normalize,
  verify, analyse, match, score, explain, prioritize, present, learn), then improve
  coverage, intelligence and reliability from evidence.
- **Separate concepts stay separate.** Fit is not Priority, Fit is not Confidence,
  unknown is not negative, no evidence found is not a known gap, and one failed source
  is not a failed search.
- **AI interprets, rules decide.** AI reads jobs and drafts explanations; Fit and
  Priority come from deterministic, versioned scoring. Every recommendation traces from
  a job requirement to career evidence to the final score.
- **Never hide uncertainty.** Partial searches, missing data and failures are visible.
- **Configuration, not code.** Search taxonomy, geography, schedules, weights and
  sources are editable without a release.
- **Modular monolith with workers,** replaceable source and AI adapters, and privacy by
  design for career and network data.
- **Quality as a gate.** Every change passes the [build policy](docs/BUILD_POLICY.md):
  full coverage, blocking security gates, staged CI and continuous deploy.

## How we measure success

Phase 1 succeeds when the candidate can open the app and confidently answer:

- What strong opportunities exist, what is genuinely new, and what changed?
- Which best match my background, why, and where are the gaps or unknowns?
- Which deserve attention now, and do I know anyone relevant there?
- Did today's searches actually complete, and are failures visible?

The north star is **three referral-backed interviews per month**: interviews for roles
PEJIP surfaced, where a matured connection (a first-degree connection at the hiring
company in a comparable or more senior position) recommended the candidate.

We track that with:

- **Referral path:** high-Fit roles with a matured connection, and how many become
  referrals and interviews.
- **Recommendation quality:** precision of high-Fit recommendations, recall of known
  strong opportunities, false high-Fit and false low-Fit rates, and unsupported
  explanation rate.
- **Discovery quality:** relevant opportunities found and missed, time to discovery,
  canonical verification rate, and duplicate rate. Volume alone is not success.
- **Real-world signal:** share of high-Fit roles the candidate marks Interested, and
  share of low-Fit roles they reject.
- **Release gate:** a golden evaluation set that every scoring change must pass.

The [success scorecard](docs/success-scorecard.md) defines every metric, its target and
how it is analysed. Acceptance criteria and the Definition of Done are in sections 17
and 18 of the [specification](docs/spec/FIND-build-specification.md).

## Status

The Phase 1 (FIND) specification is complete, and the first end-to-end slice is a
command line tool: it fetches roles from configured Greenhouse and Lever company
boards and from career-site job-alert emails sent to PEJIP's own inbox, ranks them with separate Fit, Confidence and Priority, and writes a Markdown
digest that explains each ranking with cited evidence, including matured LinkedIn
connections at the hiring company ([design 0014](docs/design/0014-connection-matching.md)).
Feedback, notifications and feature API endpoints come next. The web portal's Home,
Opportunities, detail, Companies, Watchlist, Connections, Search Health and Settings pages show each
account's own search results ([design 0013](docs/design/0013-web-portal.md)). The build policy,
repository hygiene, the Python CI pipeline, a health endpoint, the golden evaluation
set for rankings and foundation AWS infrastructure are in place. The hosting stack
and continuous deploy for `job-search.zephyr-mcg.com` are defined
([ADR-0005](docs/adr/0005-app-hosting-and-continuous-deploy.md)), and the search
runs there every morning, keeps its results in an encrypted database and emails the
digest ([ADR-0007](docs/adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md)). See the
[design doc](docs/design/0008-find-thin-slice.md) and the [changelog](CHANGELOG.md).

## Getting started

Setup, local checks and the branch and pull request flow are in
[CONTRIBUTING.md](CONTRIBUTING.md). To run a search:

```sh
pip install -e .
cp examples/profile.example.yaml profile.yaml   # then replace with your own evidence
export ANTHROPIC_API_KEY=...                     # from your shell, never committed
pejip run                                        # writes output/digest-*.md
```

To add who you know, point `PEJIP_CONNECTIONS` at your LinkedIn Connections export
(kept outside the repository) and check it first with `pejip connections <file>`.
On AWS, upload it instead as described in [infra/README.md](infra/README.md).

The title taxonomy, geography, model, scoring weights and the boards searched for
testing are in [config/search.yaml](config/search.yaml). Your own target companies
stay out of the repository: point `PEJIP_COMPANIES` at a copy of
[examples/companies.example.yaml](examples/companies.example.yaml) kept elsewhere
([ADR-0009](docs/adr/0009-private-inputs-outside-the-public-repository.md)).

## Project structure

| Path | What it holds |
|---|---|
| [`src/pejip/`](src/pejip/) | The application package (CLI, pipeline, sources, AI client, scoring) |
| [`config/`](config/) | Search, source, AI and scoring configuration |
| [`tests/`](tests/) | Unit, integration and system tests |
| [`examples/`](examples/) | Synthetic example profile, LinkedIn export and network decisions |
| [`docs/spec/`](docs/spec/) | Product and engineering build specification (primary product reference) |
| [`docs/BUILD_POLICY.md`](docs/BUILD_POLICY.md) | Binding CI/CD and engineering policy |
| [`docs/success-scorecard.md`](docs/success-scorecard.md) | North star, success metrics and targets |
| [`docs/architecture/`](docs/architecture/) | System overview, components, data flow |
| [`docs/design/`](docs/design/) | One design doc per feature |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`ci/`](ci/) | CI gate scripts (coverage ratchet, severity gate, build-artifact check) and release tooling |
| [`CHANGELOG.md`](CHANGELOG.md) | Changes in each release; versions are tagged `vMAJOR.MINOR.PATCH` |
| [`docs/sources.md`](docs/sources.md) | Job sources we may fetch, with their terms |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Security posture and third parties that receive personal data |
| [`eval/`](eval/) | Golden evaluation set and baseline that every ranking change must hold (see its README) |
| [`infra/`](infra/) | Terraform for the AWS footprint (see its README) |
| [`Dockerfile`](Dockerfile) | Production container image, deployed by the Deploy workflow |
| [`.github/`](.github/) | CI workflows, Dependabot, PR template, branch protection ruleset |
| [`CLAUDE.md`](CLAUDE.md) | Guidance for Claude working in this repo |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [build policy](docs/BUILD_POLICY.md).

## Security

Security posture, the third parties that receive personal data and how to report a
vulnerability are in [docs/SECURITY.md](docs/SECURITY.md).

## License

Private project. All rights reserved; no license is granted to use, copy or
distribute this code.
