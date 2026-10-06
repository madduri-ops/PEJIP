# ADR-0011: A job title is one signal of level, not a gate

**Status:** Accepted (2026-10-06)

## Context

Discovery dropped every role whose title lacked a configured seniority word before
any analysis. On 2026-10-06 a LinkedIn alert listed "Director, Technical Program
Management" at Meta; only Senior and Executive Director counted, so the role was
parsed and then discarded, while a "Senior Director" from the same email went
through. Babu's direction the same day: titles are one thing PEJIP looks at, not the
thing. Levels differ by company (a Yahoo VP, a Google Lead Portfolio Program Manager
and a Meta Director can be the same job), pay is the second signal when a title is
unclear, and California postings must state pay.

## Decision

- Discovery still needs a role-family word in the title and an in-scope location.
- A role is kept for ranking when any one of these holds: its title reads as senior
  (plain Director now included); it came from one of Babu's own job-alert emails
  (he chose those searches); or the top of its posted pay is at or above the
  profile's minimum. Excluded titles such as Assistant Vice President are kept on
  pay too.
- Posted pay whose top is below the profile minimum rules a role out whatever its
  title ("if the pay is not in our range, just ignore it", Babu, 2026-10-06), before
  any ranking work is spent on it.
- A careers-board role with an unclear title and no posted pay is held back. Each
  run's digest notes count the roles kept on pay and held back for no pay. Roles
  left out for low pay are not mentioned at all ("don't even bring it to me").
- Fit and Priority are unchanged: the analysis still infers the role's real level
  from its scope.

## Consequences

More roles reach the ranking routine on Babu's Claude plan (still at most
`ai.max_jobs_per_run` per run), so a backlog may take a few runs to clear. A
follow-up flags strong matches whose level looks below target as Babu's call and
records his decision, so later rules can learn from it.
