# 0010: Job-alert inbox

_Status: accepted; receiving is on (infrastructure), reading the inbox lands in a follow-up PR. Last updated: 2026-10-05._

## Purpose

Babu's target companies are Google, NVIDIA, Meta, Micron, Anthropic, OpenAI and
Microsoft. Only Anthropic publishes its roles through an API whose terms allow
automated access (`docs/sources.md`). The others run their own or Workday career
sites, and OpenAI's public feed lists only a few of its roles. Every one of them
offers job-alert emails for a saved search, so PEJIP gets its own address to
receive those alerts and turns them into roles to rank.

## Scope

In scope:

- An SES-received address, `alerts@inbox.job-search.zephyr-mcg.com`, that Babu
  uses to sign up for each site's job alerts.
- An encrypted bucket that keeps each received message for at most 90 days.
- Read and delete access for the app's task role.

Out of scope here:

- Reading and parsing the messages (`pejip.sources.email_alerts`), which needs
  the `boto3` package and lands in the next PR.
- Fetching each alert's linked posting for its full description, which is checked
  per site against its robots.txt and terms before any adapter fetches it.
- Babu's own logins on the career sites: never used (site terms, the policy's ban
  on login-walled pages, and the risk of flagging his accounts).
- Gmail API or IMAP access to a personal mailbox: rejected, as both need a
  long-lived token or password (policy section 5) and expose the whole mailbox.

## Design

```mermaid
flowchart LR
    site[Career site job alert] -- email --> mx[MX inbox.job-search.zephyr-mcg.com]
    mx --> ses[SES receipt rule pejip-alerts-to-s3<br/>spam and virus scan, TLS required]
    ses --> s3[(S3 pejip-inbox-275704950192<br/>inbound/, SSE-KMS alias/pejip,<br/>expires after 90 days)]
    run[pejip run] -- list, get, delete --> s3
```

- The receiving domain is a subdomain of the app's host name. The host name is a
  CNAME to the load balancer, and DNS does not allow an MX record beside a CNAME.
- SES writes each message whole (MIME) under `inbound/`. The bucket encrypts with
  the PEJIP key, which lets SES generate data keys only through S3 and only for
  this account.
- The bucket accepts writes only from SES rules in the `pejip-inbox` rule set,
  denies anything without TLS and blocks public access.
- SES allows one active receipt rule set per account and region. The rule set is
  activated only when `inbox_receiving_enabled = true`, after checking that
  nothing else in the account uses SES receiving in `us-west-2`.

## Interfaces

- Address: `alerts@inbox.job-search.zephyr-mcg.com` (Terraform output `inbox_address`).
- DNS at the registrar (output `inbox_dns_records`): a TXT record
  `_amazonses.inbox.job-search` for domain verification, and an MX record
  `inbox.job-search` with value `10 inbound-smtp.us-west-2.amazonaws.com`.
- Task role `pejip-ecs-task`: `s3:ListBucket` on `inbound/`, `s3:GetObject` and
  `s3:DeleteObject` on `inbound/*`, and `kms:Decrypt` through S3.

## Data model

Messages are raw MIME objects at `inbound/<SES message id>`. They can hold Babu's
name and the alert's search terms, so the bucket is tagged
`DataClassification = personal`. A message is deleted after it is read, and the
lifecycle rule removes any message left after 90 days, plus deleted versions after
one day.

## Non-functional considerations

- **Privacy (policy section 10):** encrypted at rest with the PEJIP key and in
  transit (TLS required for delivery and for reads), 90-day expiry, no access
  logs that would copy the data elsewhere. AWS is already PEJIP's host, so no new
  third party receives personal data.
- **Security:** checkov runs on every infra change; the three skipped bucket
  checks (access logs, cross-region replication, event notifications) are
  documented in `inbox.tf`.
- **Cost:** SES receiving is $0.10 per 1,000 emails plus a little S3; a few
  alerts a day costs well under $1 a month.

## Alternatives considered

- Forwarding from a mailbox at Babu's email provider: works, but adds a mailbox
  and a forwarding rule for no gain. Babu chose signing up with PEJIP's address
  directly (2026-10-05).
- Gmail API, IMAP, or logging in to the career sites: rejected above.
- A licensed job-data provider: possible later; costs money and needs its own
  terms review.

## Open questions

- Which sites' posting pages may be fetched for full descriptions.
- The hosted app still needs a persistent store and a scheduled `pejip run`
  before inbox roles are ranked in AWS.
