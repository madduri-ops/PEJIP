# ADR-0002: Build the first FIND slice as a Python batch CLI with a portable store

**Status:** Accepted (2026-10-05)

## Context

The FIND specification (section 14.4) recommends Python and FastAPI for the
backend, PostgreSQL as the canonical store, a worker pool and a Next.js frontend.
The README commits to a thin end-to-end slice first: discover, analyse, score,
explain and present, then improve coverage and reliability from evidence. The
build policy requires every AI call to go through one cost-capped client, versioned
prompts with an evaluation gate, and deterministic, explainable scoring.

The AWS foundation (ADR-0001) is in place, but the VPC, ALB and ECS service land
with the first deployable app, and nothing yet needs a web interface to be useful:
Babu can read a digest file.

## Decision

- The first slice is a Python 3.11+ package, `pejip`, run as a command line batch
  job (`pejip run`). It writes a Markdown digest per run.
- Persistence uses SQLAlchemy Core with portable types. It runs on SQLite locally
  and in tests, and on PostgreSQL unchanged when the service is deployed.
- AI calls use the Anthropic SDK through a single `AIClient` that enforces the
  monthly cap, records spend per feature and model, requests schema-constrained
  JSON, and opts into server-side refusal fallbacks. The default model is
  `claude-opus-5-5` at `medium` effort, set in `config/search.yaml`.
- AI only extracts structured requirements and requirement-to-evidence judgements.
  Fit, Confidence, Priority, reason codes and explanation text are computed by
  deterministic code from validated data (spec 9.41, 14.35).
- Sources start with the public Greenhouse and Lever job board APIs: official,
  unauthenticated, and the employer's own canonical postings.

## Consequences

- Babu can run PEJIP today with a profile file and an API key, before any hosting
  work.
- FastAPI, the scheduler, the worker pool and the frontend are still to come; the
  pipeline is written as a plain function of its inputs so it can run inside a
  worker unchanged.
- Spend-threshold alerts are emitted as structured `ai_spend_threshold` log events;
  the CloudWatch metric filter and alarm that email them land with deployment.
- Aggregator, professional and market-intelligence sources (spec 7.2 to 7.4) need
  their own terms review before they are added to `docs/sources.md`.

## Alternatives considered

- **Start with FastAPI, PostgreSQL and a web UI.** Matches the end-state stack but
  delays the first useful ranking behind hosting, auth and frontend work.
- **Let the model return the Fit score.** Simpler, but violates the spec's
  deterministic scoring boundary and makes scores impossible to audit or tune.
