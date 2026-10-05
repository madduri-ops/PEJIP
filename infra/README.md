# PEJIP infrastructure

Terraform for PEJIP's AWS footprint, isolated from the KRI dashboard. The decision
and the naming, tagging and IAM rules are in
[ADR-0001](../docs/adr/0001-aws-hosting-isolated-from-kri.md) and build policy
section 5.1.

## What is here

| File | Resources |
|---|---|
| `kms.tf` | Adopts the bootstrap key `alias/pejip` (import blocks) and manages its policy |
| `ecr.tf` | ECR repository `pejip`, immutable tags, scan on push, KMS-encrypted, keeps the last 10 images plus up to 100 release images tagged `v*` |
| `iam_github.tf` | `pejip-github-deploy` (main only) and `pejip-github-plan` (pull requests, read only) |
| `alerts.tf` | SNS topic `pejip-alerts` with Babu's email, and the `pejip-monthly` budget on `Project = PEJIP` |
| `ai_cost.tf` | Alarms `pejip-ai-spend-50pct` to `-100pct` on the app's month-to-date Claude spend, emailing through `pejip-alerts` ([design](../docs/design/0002-ai-cost-guard.md)) |
| `network.tf` | `pejip-vpc` (`10.20.0.0/16`), two public subnets, internet gateway, locked default security group, VPC flow logs |
| `alb.tf` | ACM certificate for `job-search.zephyr-mcg.com`, ALB `pejip-alb` (HTTPS, HTTP redirect), WAF `pejip-alb` with blocked-request logs |
| `ecs.tf` | ECS cluster and service `pejip-prod`, task definition, roles `pejip-ecs-execution` and `pejip-ecs-task`, log group `/ecs/pejip-prod` |
| `schedule.tf` | `pejip-purge-daily` schedule running `pejip purge` (created disabled) and its `pejip-scheduler` role |
| `alarms.tf` | 5xx, unhealthy target, tasks-below-desired, CPU and memory alarms to `pejip-alerts` |

The hosting decisions (public subnets without NAT, WAF rules, DNS at the registrar,
cost) are in [ADR-0004](../docs/adr/0004-app-hosting-and-continuous-deploy.md) and
[design 0005](../docs/design/0005-app-hosting-and-deploy.md).

## Bootstrap (done once, by hand)

The state bucket `pejip-tfstate-275704950192` and KMS key `alias/pejip` were created
from CloudShell on 2026-10-04, and the `Project` cost allocation tag was activated.

The first `terraform apply` ran from CloudShell on 2026-10-04 (2 imported, 10 added,
1 changed), and the GitHub variables and secret below were set the same day.

## Applying

Babu applies from AWS CloudShell in `us-west-2`. CloudShell's home folder can be
wiped; if `~/PEJIP` or `~/bin/terraform` is missing, re-clone the repo and reinstall
Terraform 1.13.3 to `~/bin`.

```sh
cd ~/PEJIP && git pull && cd infra
export TF_VAR_alert_email='you@example.com'
terraform init
terraform plan
terraform apply
```

Pull requests that touch `infra/` run lint, checkov and `terraform plan` in the
`Infra` workflow.

## First deploy of the hosting stack (once)

1. Create only the certificate:
   `terraform apply -target=aws_acm_certificate.app`
2. Print its validation record with `terraform output certificate_validation_records`
   and add it at the registrar as a CNAME (name and value exactly as shown).
3. Apply everything else with `terraform apply`. It waits until ACM sees the record
   and issues the certificate, then creates the network, load balancer, firewall,
   ECS service (at zero tasks), schedule and alarms.
4. Print the load balancer's name with `terraform output alb_dns_name` and add a
   CNAME at the registrar: name `job-search`, value that DNS name.
5. In GitHub, set the repository variable `DEPLOY_ENABLED` to `true`, then run the
   Deploy workflow from the Actions tab (Run workflow on `main`). It pushes the
   first image, scales the service to one task and checks
   `https://job-search.zephyr-mcg.com/healthz`.

After that every merge to `main` that changes the app deploys on its own.

## GitHub settings

- Variables: `AWS_DEPLOY_ROLE_ARN`, `AWS_PLAN_ROLE_ARN` (from `terraform output`),
  `DEPLOY_ENABLED` (`true` once the first deploy steps above are done) and
  optionally `APP_URL` (defaults to `https://job-search.zephyr-mcg.com`).
- Secret: `ALERT_EMAIL`, used by `terraform plan` in CI.
- Required check `Container image` (from the Deploy workflow) in Settings > Rules,
  matching `.github/rulesets/main.json`.
