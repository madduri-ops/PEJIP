# 0012: Daily run and storage on AWS

_Status: accepted. Last updated: 2026-10-06._

## Purpose

Make PEJIP work without Babu: every morning it searches, ranks what it finds,
keeps the results, and emails Babu the digest. The stored results are also what
the portal will show. Decision record: [ADR-0007](../adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md).

## Scope

In scope: the data file system, the daily `pejip run` and `pejip purge`
schedules, the digest email, the career profile in SSM and keyless Claude on
ECS. Out of scope: alarms on run outcomes (monitoring, design 0011), portal
screens and API routes over the stored data, HTML email, and running more than once a day.

## Design

```mermaid
sequenceDiagram
    participant S as EventBridge Scheduler
    participant T as Fargate task (pejip run)
    participant P as SSM /pejip/profile
    participant J as Job sources and inbox bucket
    participant C as Claude API
    participant E as EFS /data
    participant N as SNS pejip-digest
    S->>T: weekdays 05:00, 10:00, 15:00 Pacific, RunTask (command override)
    T->>P: GetParameter (decrypted)
    T->>J: fetch boards, read alert emails
    T->>C: analyse new or changed roles (CostGuard, keyless)
    T->>E: store jobs, analyses, rankings, run; write digest
    T->>N: publish digest
    N-->>Babu: email
```

- **Infrastructure:** `infra/efs.tf` (file system, mount targets in both public
  subnets, access point, policy), `infra/digest.tf` (topic and email
  subscription), `infra/schedule.tf` (both schedules), and the task definition and role in
  `infra/ecs.tf`.
- **One task definition:** the API service and the scheduled tasks share the
  `pejip-prod` family. The schedules override the command and give the run
  0.5 vCPU and 1 GB. The Deploy workflow keeps the family on the latest image.
- **Degrading instead of failing:** the run needs the profile and Claude only to
  rank. If `/pejip/profile` does not exist yet, or Claude is switched off
  (`PEJIP_AI_ENABLED=false`, the default until the app's Console rule IDs are
  set), roles are still fetched, stored and emailed, marked unranked with the
  reason, and the digest carries a note saying why. Any other failure (no
  permission, a malformed profile) fails the run.
- **Run outcome for monitoring:** every run logs `run_finished` with its
  `status` (SUCCESS, PARTIAL or FAILED) to `/ecs/pejip-prod`. Monitoring (design
  0011) turns those log events into metrics in the `PEJIP` namespace and alarms
  on a FAILED run and on no completed run in 64 hours (26 before searches moved to weekdays only), which also covers a task
  that crashed or never started. The run exits 1 when it FAILED.

## Interfaces

Environment set by `infra/ecs.tf` for every task:

| Variable | Value |
|---|---|
| `PEJIP_CONFIG` | `/etc/pejip/search.yaml` (baked into the image from `config/search.yaml`) |
| `PEJIP_DATABASE_URL` | `sqlite:////data/pejip.db` |
| `PEJIP_AI_LEDGER` | `/data/pejip-ai-spend.db` |
| `PEJIP_OUTPUT_DIR` | `/data/output` |
| `PEJIP_INBOX_BUCKET` | `pejip-inbox-275704950192` |
| `PEJIP_PROFILE_PARAMETER` | `/pejip/accounts/{account}/profile` (when set, used instead of `PEJIP_PROFILE`; per account since design 0016) |
| `PEJIP_DIGEST_TOPICS` | each account's digest topic, `id=arn` pairs (Babu's is `pejip-digest`; design 0016) |
| `PEJIP_ACCOUNTS` | the accounts `run`, `digest` and `purge` loop over |
| `PEJIP_AI_ENABLED` | `true` once `claude_app_rule_id` and `claude_app_service_account_id` are set, else `false` |
| `PEJIP_CLAUDE_IDENTITY` and `ANTHROPIC_*` IDs | `aws-sts` and the app's Console IDs, only when Claude is enabled |

The digest email: subject `PEJIP digest YYYY-MM-DD: N need attention, M roles
(STATUS)`, body the Markdown digest as plain text, cut at a line boundary with a
note if it would pass SNS's 256 KB limit (`pejip.delivery`).

The profile parameter: the same YAML as `examples/profile.example.yaml`, stored
by Babu with `aws ssm put-parameter --type SecureString --key-id alias/pejip
--tier Intelligent-Tiering` (Intelligent-Tiering moves it to the advanced tier
only if it is over 4 KB).

## Data model

No schema change: the tables in `pejip.store` are created on first run. Files on
the data file system (root `/pejip`, owner 10001, mode 0700):

| Path in the task | What |
|---|---|
| `/data/pejip.db` | jobs, analyses, recommendations, runs, decisions (90-day retention) |
| `/data/pejip-ai-spend.db` | AI spend ledger behind the $100 monthly cap |
| `/data/output/digest-*.md` | digests, deleted after 90 days |

## Non-functional considerations

- **Security:** EFS encrypted with `alias/pejip`, TLS-only, mountable only by
  the task role through the access point; profile and digest topic encrypted
  with the same key; the task role can read only `/pejip/profile` and publish
  only to `pejip-digest`. No Claude key anywhere: the run federates with its task
  role (ADR-0004).
- **Privacy:** retention is unchanged (each run and the daily purge delete data
  past 90 days); no backups. The digest email is listed in `docs/SECURITY.md`.
- **Reliability:** a failed source or analysis is isolated as before; failed
  and missing runs alarm through monitoring (design 0011); Scheduler retries a
  task that fails to launch three times within an hour. The schedules live in
  their own group, `pejip-prod`, and `pejip-scheduler-failed` emails within
  minutes when Scheduler cannot start a task. After an apply that changes the
  schedules or the scheduler role, the check in `infra/README.md` ("Checking the
  schedules") starts a purge through the scheduler's own role.
- **Cost:** EFS at about $0.30 per GB-month for megabytes of data; a daily run of
  a few minutes at 0.5 vCPU is cents a month; SNS email is free at this volume.
- **Tests:** `tests/unit/test_cli.py` (SSM profile, Claude switch, digest email),
  `tests/unit/test_delivery.py`, `tests/unit/test_profile_parameter.py`, and
  `tests/integration/test_pipeline.py` (unranked runs). Terraform passes
  validate, tflint, checkov and plan in the Infra workflow.

## Alternatives considered

See [ADR-0007](../adr/0007-sqlite-on-efs-and-a-scheduled-daily-run.md):
RDS PostgreSQL, Aurora Serverless v2, SQLite synced through S3, DynamoDB, and SES
for the email.

## Open questions

- When the portal starts writing (for example, Babu marking a role as applied),
  revisit whether SQLite on EFS still fits or move to PostgreSQL.
