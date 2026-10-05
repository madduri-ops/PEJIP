# PEJIP infrastructure

Terraform for PEJIP's AWS footprint, isolated from the KRI dashboard. The decision
and the naming, tagging and IAM rules are in
[ADR-0001](../docs/adr/0001-aws-hosting-isolated-from-kri.md) and build policy
section 5.1.

## What is here today (foundation)

| File | Resources |
|---|---|
| `kms.tf` | Adopts the bootstrap key `alias/pejip` (import blocks) and manages its policy |
| `ecr.tf` | ECR repository `pejip`, immutable tags, scan on push, KMS-encrypted, keeps 10 images |
| `iam_github.tf` | `pejip-github-deploy` (main only) and `pejip-github-plan` (pull requests, read only) |
| `alerts.tf` | SNS topic `pejip-alerts` with Babu's email, and the `pejip-monthly` budget on `Project = PEJIP` |
| `claude_federation.tf` | Outbound web identity federation for the account and policy `pejip-claude-federation`, so the app gets short-lived Claude tokens with no API key ([design](../docs/design/0004-claude-identity-federation.md)) |
| `ai_cost.tf` | Alarms `pejip-ai-spend-50pct` to `-100pct` on the app's month-to-date Claude spend, emailing through `pejip-alerts` ([design](../docs/design/0002-ai-cost-guard.md)) |

The VPC, load balancer, ECS service, certificate for `job-search.zephyr-mcg.com` and
the service alarms land with the first app code, when there is something to run.

## Bootstrap (done once, by hand)

The state bucket `pejip-tfstate-275704950192` and KMS key `alias/pejip` were created
from CloudShell on 2026-10-04, and the `Project` cost allocation tag was activated.

The first `terraform apply` ran from CloudShell on 2026-10-04 (2 imported, 10 added,
1 changed), and the GitHub variables and secret below were set the same day.

## Applying

Until the CD workflow lands, Babu applies from AWS CloudShell in `us-west-2`:

```sh
cd infra
export TF_VAR_alert_email='you@example.com'
terraform init
terraform plan
terraform apply
```

Pull requests that touch `infra/` run lint, checkov and (once `AWS_PLAN_ROLE_ARN` is
set) `terraform plan` in the `Infra` workflow.

## GitHub settings after the first apply

- Variables: `AWS_DEPLOY_ROLE_ARN`, `AWS_PLAN_ROLE_ARN` (from `terraform output`).
- Secret: `ALERT_EMAIL`, used by `terraform plan` in CI.
