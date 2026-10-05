# ADR-0007: Keep PEJIP's data in SQLite on encrypted EFS, written by a scheduled daily run

**Status:** Accepted (2026-10-05)

## Context

PEJIP is hosted on AWS ([ADR-0005](0005-app-hosting-and-continuous-deploy.md)),
but `pejip run` has only run on a laptop: nothing searches on its own, and the
container has a read-only root filesystem, so nothing it writes would survive the
task. The store is SQLAlchemy Core, so SQLite and PostgreSQL both work
([ADR-0003](0003-python-cli-first-slice.md)).

The constraints: one user; one writer (a run a day, plus the daily purge); later
a portal that reads. Data must be encrypted at rest and in transit and kept no
longer than 90 days (policy section 10). AWS spend has a $50 monthly budget, most
of it already taken by the load balancer and the API task.

## Decision

- **Database:** a SQLite file on an Amazon EFS file system (`pejip-prod-data`),
  encrypted with `alias/pejip`, mounted at `/data` in every PEJIP task over TLS
  through an access point that forces the app's user (10001) and a 0700 root.
  The file system policy admits only the `pejip-ecs-task` role through that
  access point and denies non-TLS access. The AI spend ledger and the written
  digests live beside the database.
- **No backups:** a backup would keep deleted personal data past 90 days. EFS
  already stores data redundantly across availability zones, and postings are
  re-fetched on the next run.
- **Daily run:** EventBridge Scheduler starts `pejip run` as a one-off Fargate
  task at 06:00 America/Los_Angeles (0.5 vCPU, 1 GB), from the same task family
  the Deploy workflow updates, so it always runs the image last deployed. The
  existing `pejip purge` schedule is switched on.
- **Digest delivery:** the run publishes the digest to an encrypted SNS topic,
  `pejip-digest`, which emails it to Babu as plain text.
- **Career profile:** a SecureString SSM parameter (`/pejip/profile`, encrypted
  with `alias/pejip`) that Babu stores by hand, so it never enters Terraform state
  or the public repository. The run reads it with its task role.
- **Failure alerts:** owned by monitoring (design 0012), which alarms from the
  run's `run_finished` log events: a FAILED run, and no completed run in 26 hours.

## Consequences

- Storage costs cents a month (EFS bills per GB stored; PEJIP holds megabytes).
- SQLite allows one writer at a time. The run and the purge are minutes apart at
  most once a day and SQLite's file locking works over EFS (NFSv4.1); a busy
  portal that writes would need a rethink (see Alternatives).
- Without the profile or Claude access, the run still fetches, stores and emails
  roles, listed as unranked with the reason. Claude stays off on AWS until the
  app's federation rule exists in the Claude Console
  ([ADR-0004](0004-keyless-claude-access.md)); its IDs are Terraform variables.
- The digest reaches Babu's mailbox, so Google (Gmail) holds a copy under Babu's
  own account; `docs/SECURITY.md` lists it.
- A `terraform apply` registers a task definition revision with a placeholder
  image; a deploy must follow before the next scheduled run (infra/README.md).

## Alternatives considered

- **RDS PostgreSQL (db.t4g.micro):** the spec's eventual choice and the natural
  fit for a busy multi-writer portal, but about $15 a month before storage, a
  third of the budget, for a database that is written once a day.
- **Aurora Serverless v2 scaling to zero:** near-zero idle cost, but seconds of
  resume latency, more moving parts (cluster, instances, secrets) and a higher
  floor whenever it wakes.
- **SQLite file copied to and from S3 around each run:** cheap, but a crash
  mid-run or a reader during a run could lose or see half-written data.
- **DynamoDB:** cheap and serverless, but a rewrite of the store and its queries.
- **Emailing through SES:** HTML email, but needs DKIM records at the registrar
  and recipient verification while SES is in its sandbox; SNS needed one
  confirmation click.
