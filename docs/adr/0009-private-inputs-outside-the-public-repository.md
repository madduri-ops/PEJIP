# ADR-0009: Keep Babu's private inputs outside the public repository

**Status:** Accepted (2026-10-05)

## Context

The repository went private on 2026-10-05, which made every CI run count against
GitHub Free's 2,000 Actions minutes a month; one day of CI used about two thirds of
them. Babu made the repository public again the same day for free CI. The code and
configuration hold no career data, secrets or email addresses, and the portal is
behind Google sign-in ([ADR-0006](0006-google-sign-in-at-the-load-balancer.md)), but
two inputs still tell a reader about Babu's job search:

- the companies he targets (job boards, job-alert companies and their LinkedIn name
  variants), which were in `config/search.yaml`;
- his LinkedIn connections, which the daily run on AWS needs but which can never be
  committed ([design 0014](../design/0014-connection-matching.md)).

## Decision

- **Company list:** the committed `config/search.yaml` holds only the boards
  searched for testing. Babu's targets are a YAML file in the shape of
  `examples/companies.example.yaml` that `pejip run` adds at run time: locally from
  `PEJIP_COMPANIES`, on AWS from the SecureString SSM parameter `/pejip/companies`
  (`PEJIP_COMPANIES_PARAMETER`, encrypted with `alias/pejip`), stored by Babu like
  the career profile so it never enters Terraform state. A missing parameter is a
  digest note and the run searches the test boards; a malformed one fails the run.
- **Connections:** Babu uploads `Connections.csv` and his network decisions to
  `network/` in the encrypted, TLS-only job-alert bucket, where they expire 90 days
  after upload. The run's role can list and read that prefix only.

## Consequences

- New or changed target companies stay private; the list in the repository's
  history before this change remains readable.
- Changing the company list is a CloudShell `put-parameter`, not a PR, so it is not
  reviewed or versioned in git. The parameter keeps its own version history.
- Tests and examples use the test boards and invented companies only.
