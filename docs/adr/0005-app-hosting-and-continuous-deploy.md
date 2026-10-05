# ADR-0005: Serve PEJIP from Fargate in public subnets behind a WAF-fronted ALB, deployed by GitHub Actions

**Status:** Accepted (2026-10-05)

## Context

[ADR-0001](0001-aws-hosting-isolated-from-kri.md) fixed where PEJIP runs (account
`275704950192`, `us-west-2`, isolated `pejip-*` resources) and the shape of the
stack (ECS Fargate behind an ALB, ECR, OIDC deploys). It left the network layout,
the edge protections, the deploy mechanics and the DNS steps to the first app code.

The build policy asks for continuous deploy on `main` with OIDC, a post-deploy
health gate, automatic rollback when that gate fails (section 15), email on deploy
success and failure (section 6), Terraform alarms (sections 5 and 14), and daily
expiry of data past 90 days (section 10). The PEJIP AWS budget is $50 a month and
the app today is one small API process plus batch commands.

DNS for `zephyr-mcg.com` is at Babu's registrar, not Route 53.

## Decision

- **Network:** `pejip-vpc` (`10.20.0.0/16`) has two public subnets in
  `us-west-2a` and `us-west-2b`, an internet gateway, a locked default security
  group and VPC flow logs. There are no private subnets or NAT gateway. Fargate
  tasks run in the public subnets with a public IP for outbound HTTPS; their
  security group admits only the ALB on the container port, so no task is
  reachable from the internet.
- **Edge:** ALB `pejip-alb` with an ACM certificate for `job-search.zephyr-mcg.com`,
  TLS 1.3/1.2 policy, HTTP redirected to HTTPS, invalid headers dropped and deletion
  protection on. AWS WAF (`pejip-alb`) runs the AWS managed common and
  known-bad-inputs rule groups and logs blocked requests only.
- **DNS:** stays at the registrar. Terraform outputs the certificate's validation
  CNAME and the ALB's DNS name; Babu adds both by hand (infra/README.md).
- **Compute:** ECS cluster and service `pejip-prod`, one 0.25 vCPU / 512 MiB task,
  read-only root filesystem, non-root user, deployment circuit breaker with
  rollback. Terraform owns the task definition's shape; the Deploy workflow owns
  the image, so the service ignores `task_definition` and `desired_count` drift
  and Terraform creates it at zero tasks.
- **Image:** one `Dockerfile` builds the wheel and installs only it on a
  digest-pinned `python:3.12-alpine`, with pip removed. Alpine was chosen over
  Debian slim because slim carried 56 high-severity OS package findings (util-linux,
  gcc runtime, pcre2, acl) that the image scan blocks on. The default command serves the API
  (`python -m pejip.api`); batch commands run from the same image with a command
  override.
- **Deploy:** `.github/workflows/deploy.yml`. Every pull request that can change
  the image builds it, runs it read-only, checks `/healthz` and scans it with grype
  (high and critical block, through `ci/severity_gate.py`); this is the required
  `Container image` check. On `main`, the same image is pushed to ECR by commit SHA,
  a new task definition revision is registered, the service is rolled and must
  settle on that revision, and the public `/healthz` must answer `ok`. Any failure
  after the rollout starts puts the service back on the previous revision. The
  result is published to `pejip-alerts`. Deploys start once the repository variable
  `DEPLOY_ENABLED` is `true`.
- **Scheduled work:** EventBridge Scheduler `pejip-purge-daily` runs
  `pejip purge` as a one-off task on the latest task definition revision at 09:30
  UTC. It is created disabled and turned on once the image has the command and the
  app has a persistent database.
- **Alarms:** target 5xx, load balancer 5xx, unhealthy targets, tasks below desired,
  CPU and memory above 80%, all to `pejip-alerts`.
- **Logs:** app, flow and WAF log groups are encrypted with `alias/pejip` and kept
  90 days, the policy's data retention limit.

## Consequences

- Expected cost is roughly $35 to $40 a month: ALB about $18 plus its two public
  IPs about $7, the Fargate task about $9 plus its IP about $4, WAF about $7 with
  low traffic, and small amounts of logs. That fits the $50 budget alongside the
  foundation, with little headroom; the budget alarm warns at 80% forecast.
- Tasks have public IPs. The task security group is the control that keeps them
  unreachable; checkov's CKV_AWS_333 is skipped inline with that reason.
- ALB access logs are off (CKV_AWS_91 skipped inline): ALB can only write them to
  an SSE-S3 bucket, not one encrypted with the PEJIP key. App logs, WAF blocked
  request logs, flow logs and ALB metrics cover request visibility.
- The WAF omits the anonymous IP list (CKV2_AWS_76 skipped inline) because it would
  block Babu on a VPN and the GitHub-hosted health gate; the known-bad-inputs group
  still covers Log4j.
- Before DNS is pointed at the ALB, the health gate cannot pass, so
  `DEPLOY_ENABLED` is set only after both records exist.
- The first `terraform apply` is two steps: create the certificate, add its
  validation record, then apply the rest, which waits for the certificate.

## Alternatives considered

- **Private subnets with a NAT gateway.** The usual layout, but a NAT gateway is
  about $33 a month before data, which with the ALB exceeds the budget. Revisit when
  the budget grows or the app holds data that warrants it; moving tasks to private
  subnets is a Terraform change with no app impact.
- **Private subnets with VPC interface endpoints** for ECR, logs and CloudWatch.
  Several endpoints at about $7 each cost as much as NAT, and job sources and the
  Anthropic API still need internet egress.
- **Route 53 hosted zone for the subdomain.** Automates validation and the alias
  record, but means delegating `job-search` from the registrar and paying for a
  zone; two one-time CNAMEs are simpler.
- **Third-party deploy actions** (`amazon-ecs-deploy-task-definition`). The AWS CLI
  steps are short, readable and need no extra action pinned and updated.
