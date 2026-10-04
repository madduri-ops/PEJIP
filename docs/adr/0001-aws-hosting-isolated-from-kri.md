# ADR-0001: Host PEJIP on AWS, isolated from the KRI dashboard

**Status:** Accepted (2026-10-04)

## Context

Babu wants PEJIP hosted on AWS as its own application, separate from the
CyberSecurity-KRI dashboard (`madduri-ops/CyberSecurity-KRI`), reusing the AWS setup
that project already has. The build policy (section 5) requires continuous deploy
on `main`, OIDC cloud auth with no long-lived keys, a post-deploy health gate, and
Terraform for all infrastructure including alarms. Section 10 requires PEJIP's
career data to be encrypted at rest with KMS-managed keys and readable only by the
app's own identity and Babu.

KRI's setup, read from its `infra/` Terraform and `.github/workflows/cd.yml`
(non-secret details only):

| Item | KRI value |
|---|---|
| AWS account | `275704950192` |
| Region | `us-west-2` |
| Compute | ECS Fargate behind an ALB, cluster and service `kri-portal-poc` |
| Images | ECR repository `kri-portal`, scan on push, keep last 10 images |
| GitHub auth | IAM OIDC provider for `token.actions.githubusercontent.com`; deploy role `kri-portal-github-actions` trusting `repo:madduri-ops/CyberSecurity-KRI:*` |
| Terraform state | S3 bucket `cybersecurity-kri-tfstate-275704950192`, key `kri-portal/terraform.tfstate`, DynamoDB lock table `cybersecurity-kri-tflock` |
| Network | VPC `10.0.0.0/16` |
| Alarms | SNS email topic plus a CloudWatch log metric filter and alarm |
| Tags | `Project`, `ManagedBy`, `Owner`, `Environment` via provider `default_tags` |

## Decision

PEJIP runs in the **same AWS account (`275704950192`) and region (`us-west-2`)** as
KRI, using the same ECS Fargate + ECR + Terraform + OIDC pattern, but with **its own
copy of every resource**. Nothing PEJIP deploys is created by, stored in, or
writable from KRI's Terraform or KRI's deploy role, and the reverse.

### Naming and tags

- Every resource name starts with `pejip-` (environment suffix where it applies,
  `pejip-prod` for the first and only environment).
- Provider `default_tags` on every resource:
  `Project = "PEJIP"`, `Application = "pejip"`, `Environment = "prod"`,
  `ManagedBy = "Terraform"`, `Owner = "Babu"`, `Repository = "madduri-ops/PEJIP"`.
- Resources that store career data also carry `DataClassification = "personal"`.
- `Project` is activated as a cost allocation tag so PEJIP's spend is visible on
  its own, and the AWS Budget for PEJIP filters on it.

### Resources

| Concern | PEJIP resource |
|---|---|
| Terraform state | Own S3 bucket `pejip-tfstate-275704950192`, key `pejip/prod/terraform.tfstate`, versioning on, public access blocked, SSE-KMS, S3 native state locking (`use_lockfile = true`, Terraform 1.10 or later), so no DynamoDB table is needed |
| Terraform code | `infra/` in this repo; a separate root module and state from KRI |
| Network | Own VPC `pejip-vpc`, CIDR `10.20.0.0/16` (does not overlap KRI's `10.0.0.0/16`), own subnets, security groups and ALB `pejip-alb` |
| Images | ECR repository `pejip`, **immutable tags** (images tagged by commit SHA and release version), scan on push, lifecycle keeps the last 10 images |
| Compute | ECS cluster `pejip-prod`, service `pejip-prod`, task family `pejip-prod` on Fargate |
| Task roles | `pejip-ecs-execution` (pull image, write logs to `/ecs/pejip-prod`, read `pejip/*` secrets) and `pejip-ecs-task` (runtime access to PEJIP's own data, KMS key and secrets only) |
| Encryption | Customer-managed KMS key `alias/pejip` for state, logs, database, buckets and secrets |
| Secrets | Secrets Manager names under `pejip/` |
| Logs and metrics | Log group `/ecs/pejip-prod`, CloudWatch namespace `PEJIP` |
| Alerts | SNS topic `pejip-alerts` with an email subscription to Babu |
| Alarms | ALB 5xx rate, unhealthy targets, running tasks below desired, task CPU and memory, the AI monthly cost cap (policy section 13) and an AWS Budget on `Project = PEJIP` |
| Domain | Own ACM certificate for a hostname Babu chooses (TBD); DNS stays at Babu's registrar, as with KRI |

### GitHub OIDC

- IAM allows one OIDC provider per issuer URL per account, and KRI's Terraform
  already manages the one for `token.actions.githubusercontent.com`. PEJIP
  **references it with a data source and does not manage it**. This provider is the
  only shared AWS object; it grants nothing by itself.
- Deploy role `pejip-github-deploy` trusts only
  `repo:madduri-ops/PEJIP:ref:refs/heads/main` (stricter than KRI's `:*`). It may
  push to the `pejip` ECR repository, register `pejip-prod` task definitions, update
  the `pejip-prod` service in the `pejip-prod` cluster, and pass only the two
  `pejip-ecs-*` roles. Every statement is scoped to `pejip` ARNs except
  `ecr:GetAuthorizationToken`, which AWS only accepts on `*`.
- Plan role `pejip-github-plan` trusts only
  `repo:madduri-ops/PEJIP:pull_request`, has read-only access to PEJIP's resources
  and state, and is used for `terraform plan` on pull requests.
- The role ARNs are stored as GitHub Actions variables in this repo
  (`AWS_DEPLOY_ROLE_ARN`, `AWS_PLAN_ROLE_ARN`). There are no AWS keys anywhere.

### Bootstrap

The state bucket and the first `terraform apply` (which creates the deploy and plan
roles) need an administrator, so Babu runs them once from a local shell with their
own AWS credentials. After that, every change goes through CI with OIDC.

## Consequences

- PEJIP can be deployed, changed or destroyed without touching KRI, and a mistake in
  one project's Terraform cannot alter the other's state.
- Costs are reported separately by tag, and the PEJIP budget alarm covers PEJIP only.
- One account means isolation rests on IAM scoping and naming, not an account
  boundary. KRI's current deploy role allows `ecs:UpdateService` and
  `ecs:RegisterTaskDefinition` on `*`, so until that role is narrowed to KRI's own
  cluster ARN, a KRI workflow could in principle update PEJIP's ECS service. Narrowing
  it is a change in the KRI repo, not here.
- A second VPC and ALB add roughly the cost of one more ALB per month; sharing KRI's
  ALB was rejected to keep the projects independent.
- If PEJIP's isolation needs grow (for example, separate billing or a hard blast
  radius for career data), move it to its own account under AWS Organizations; the
  `pejip-` naming and own state make that a lift and shift.

## Alternatives considered

- **Separate AWS account for PEJIP.** Strongest isolation, but needs AWS
  Organizations setup and a second OIDC provider and billing view. Deferred; this
  ADR keeps that path open.
- **Share KRI's cluster, ALB, ECR repository or state bucket.** Cheaper, but couples
  deploys, permissions and state between the two projects. Rejected.
- **Reuse KRI's deploy role.** It trusts every ref in the KRI repo and is not scoped
  to PEJIP. Rejected.
