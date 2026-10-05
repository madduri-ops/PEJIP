# ADR-0008: Rank roles through a Claude Code routine on Babu's plan

**Status:** Proposed (2026-10-05)

## Context

Ranking needs one model step per new or changed role: job analysis and evidence
matching. The API path ([ADR-0004](0004-keyless-claude-access.md)) works, but it
bills prepaid API credits, at an estimated $10 to $25 a month. On 2026-10-05
Babu chose to use their Claude plan instead. A plan can't be used through the
API, and Anthropic's terms describe plan sign-in as for ordinary use of Claude
Code, which an unattended server job may not be. Claude Code routines, which
are scheduled cloud sessions on claude.ai, do draw on the plan.

## Decision

- A daily Claude Code routine at 07:00 PT performs the model step. It fetches
  the waiting roles and the career profile from two PEJIP endpoints, analyses
  them with the versioned prompts, and posts the results back.
- PEJIP validates and grounds every result with the same code as the API path,
  then stores it. A new 08:00 PT task scores the roles and emails the digest;
  the 06:00 run no longer emails.
- The routine authenticates with one scoped bearer key, which is an exception to
  the no-long-lived-keys rule (policy section 5). The key is stored only in the
  routine's cloud environment and is hashed on AWS. It is rotated every 90 days.
- The routine path must pass the committed golden set before it is switched on
  and whenever a prompt changes.

Design: [0015](../design/0015-ranking-routine.md).

## Consequences

- There is no API spend, and ranking draws on Babu's plan usage.
- The digest arrives at 08:00 PT instead of 06:00.
- One long-lived secret exists, with a narrow reach.
- The career profile and postings enter routine session transcripts on
  claude.ai, which sit outside PEJIP's 90-day purge until Babu deletes them.
  `docs/SECURITY.md` lists this.
- A missed routine delays ranking by a day; it never blocks the digest.

## Alternatives considered

API credits; Claude Code headless on Fargate with a plan token; a routine with
AWS access keys; exchanging data through the repository. See design 0015.
