# ADR-0010: One deployment, with each account's data kept separate

**Status:** Accepted (2026-10-06)

## Context

Babu wants a friend to use PEJIP, with each person's searches independent and
private. Until now PEJIP admitted one Google account
([ADR-0006](0006-google-sign-in-at-the-load-balancer.md)) and kept one database,
one profile, one company list, one connections file, one inbox and one digest. The
AWS budget is $50 a month and hosting already costs about $35 to $40, mostly the
load balancer and WAF.

## Decision

Keep one deployment and key everything personal to the signed-in account: an
account registry maps each verified email to an account id, and each account gets
its own SQLite file, SSM parameters, S3 prefixes, inbox address, digest topic and
ranking key ([design 0016](../design/0016-accounts.md)). Each person's roles are
ranked by a Claude Code routine on their own Claude plan, never on Babu's.

Isolation is by separate files and paths, not by an `account_id` column in shared
tables.

## Consequences

- About $1 to $2 a month more; the budget holds.
- A forgotten filter cannot leak data, because another account's rows are never in
  the file a request opens.
- Babu, as AWS administrator, can technically read every account's data. The friend
  is told and agrees before uploading anything.
- Until per-account storage lands, the registry is limited to one account, enforced
  in the app and in Terraform.

## Alternatives considered

- **A deployment per person:** strongest isolation, but about $35 to $40 a month
  more (second ALB, WAF, service, alarms), past the budget, and every deploy and
  apply doubles.
- **The friend runs their own copy** of the public repository in their own AWS
  account: no cost or exposure to Babu, but they would run Terraform, AWS and
  Google setup themselves.
- **One shared database with an `account_id` column:** least code, but every query,
  export and purge must filter correctly forever; one miss is a privacy leak.
- **Ranking the friend's roles on Babu's plan:** Babu's plan is a personal
  subscription and would spend its limits on someone else's search.
