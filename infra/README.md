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
| `claude_federation.tf` | Outbound web identity federation for the account and policy `pejip-claude-federation`, attached to the app's task role `pejip-ecs-task`, so the app gets short-lived Claude tokens with no API key ([design](../docs/design/0007-claude-identity-federation.md)) |
| `ai_cost.tf` | Alarms `pejip-ai-spend-50pct` to `-100pct` on the app's month-to-date Claude spend, emailing through `pejip-alerts` ([design](../docs/design/0002-ai-cost-guard.md)) |
| `network.tf` | `pejip-vpc` (`10.20.0.0/16`), two public subnets, internet gateway, locked default security group, VPC flow logs |
| `alb.tf` | ACM certificate for `job-search.zephyr-mcg.com`, ALB `pejip-alb` (HTTPS with Google sign-in, HTTP redirect), WAF `pejip-alb` with blocked-request logs |
| `auth.tf` | Google sign-in: reads the OAuth client from SSM, keeps `/healthz` open, lets the ALB reach Google ([ADR-0006](../docs/adr/0006-google-sign-in-at-the-load-balancer.md)) |
| `ecs.tf` | ECS cluster and service `pejip-prod`, task definition (data volume, run settings, Claude switch), roles `pejip-ecs-execution` and `pejip-ecs-task`, log group `/ecs/pejip-prod` |
| `efs.tf` | EFS file system `pejip-prod-data` (KMS-encrypted, TLS-only, no backups) holding the SQLite database, spend ledger and digests, with its access point and mount targets ([design](../docs/design/0012-daily-run-and-storage.md)) |
| `digest.tf` | SNS topic `pejip-digest` that emails Babu the daily digest |
| `schedule.tf` | `pejip-run-daily` (weekdays 05:00, 10:00, 15:00 Pacific, `pejip run`), `pejip-digest-daily` (weekdays 07:00, 12:00, 17:00, `pejip digest`) and `pejip-purge-daily` (`pejip purge`) schedules and their `pejip-scheduler` role |
| `inbox.tf` | Job-alert inbox: SES receiving for `alerts@inbox.job-search.zephyr-mcg.com` into the encrypted bucket `pejip-inbox-275704950192` (90-day expiry) ([design](../docs/design/0010-job-alert-inbox.md)) |
| `alarms.tf` | 5xx, unhealthy target, tasks-below-desired, CPU and memory alarms to `pejip-alerts` |
| `monitoring.tf` | Log metric filters for search runs, source failures and errors; alarms `pejip-search-run-failed`, `pejip-source-failures`, `pejip-app-errors` and `pejip-search-stalled` (only while `run_schedule_enabled` is on); dashboard `pejip` ([design](../docs/design/0011-monitoring.md)) |

The hosting decisions (public subnets without NAT, WAF rules, DNS at the registrar,
cost) are in [ADR-0005](../docs/adr/0005-app-hosting-and-continuous-deploy.md) and
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
export TF_VAR_sign_in_email='you@gmail.com'   # optional; defaults to the alert email
# optional account registry (design 0016); one account until per-account storage lands
# export TF_VAR_sign_in_accounts='{ babu = "you@gmail.com" }'
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

## Job-alert inbox (once)

Steps 1 and 2 were done on 2026-10-05: nothing else in the account used SES
receiving, and `inbox_receiving_enabled` now defaults to `true`.

1. Check that nothing else in the account receives mail through SES here. SES
   allows one active receipt rule set per account and region, and activating
   PEJIP's would switch off any other:
   `aws ses describe-active-receipt-rule-set --region us-west-2`
   Go on only if it prints nothing (or `pejip-inbox`).
2. Change the default of `inbox_receiving_enabled` in `variables.tf` to `true`
   in a pull request, so every later plan and apply keeps the rule set active,
   then `terraform apply` once it has merged.
3. Print the DNS records with `terraform output inbox_dns_records` and add both at
   the registrar: the TXT record (domain verification) and the MX record.
4. Sign up for each career site's job alerts with
   `terraform output inbox_address`.

## Daily run and storage (once)

[Design 0012](../docs/design/0012-daily-run-and-storage.md). After the apply that
creates the data file system, schedules and digest topic:

1. Run the Deploy workflow on `main` (or merge any app change) so the image with
   `pejip run`'s AWS support is live. The apply's own task definition revision
   reuses the image the service is running, so the schedules never point at an
   image that doesn't exist.
2. Click the link in the "AWS Notification - Subscription Confirmation" email for
   `pejip-digest`. No digest is delivered until then.
3. Store the career profile (the same YAML as `examples/profile.example.yaml`)
   from CloudShell, after uploading the file:
   `aws ssm put-parameter --name /pejip/accounts/babu/profile --type SecureString --key-id alias/pejip --tier Intelligent-Tiering --value file://profile.yaml`,
   then delete the uploaded copy. To replace it later, add `--overwrite`.
4. Create the app's Claude Console rule (the App column in
   [design 0007](../docs/design/0007-claude-identity-federation.md)) and set its
   IDs as the defaults of `claude_app_rule_id` and
   `claude_app_service_account_id` in `variables.tf`; apply again and deploy.
   Until then `PEJIP_AI_ENABLED` is `false` and roles are emailed unranked.

To run a search now instead of waiting for the morning, start the schedule's task
by hand from CloudShell:

```sh
aws ecs run-task --cluster pejip-prod --task-definition pejip-prod --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$(terraform output -json | jq -r '.public_subnet_ids.value | join(",")')],securityGroups=[$(terraform output -raw tasks_security_group_id)],assignPublicIp=ENABLED}" \
  --overrides '{"cpu":"512","memory":"1024","containerOverrides":[{"name":"pejip","command":["pejip","run"]}]}'
```

## Moving to per-account places (once, before applying design 0016 step 2)

[Design 0016](../docs/design/0016-accounts.md). Each account's data now lives
under its own id. Babu's database and digests on EFS move by themselves the first
time the app opens them (the old database stays as it was, for a rollback). The
profile, companies and LinkedIn files move by hand, from CloudShell, **before**
`terraform apply`, so no run looks for them in the new place too early:

```sh
for name in profile companies; do
  if value=$(aws ssm get-parameter --name /pejip/$name --with-decryption --query Parameter.Value --output text 2>/dev/null); then
    aws ssm put-parameter --name /pejip/accounts/babu/$name --type SecureString --key-id alias/pejip --tier Intelligent-Tiering --value "$value"
  fi
done
aws s3 mv --recursive s3://pejip-inbox-275704950192/network/ s3://pejip-inbox-275704950192/network/babu/ --exclude "babu/*"
```

Then pull and apply as usual. Once a digest has arrived from the new places, the
old parameters can go: `aws ssm delete-parameter --name /pejip/profile` and the
same for `/pejip/companies`.

## Target companies (once, then on each change)

[ADR-0009](../docs/adr/0009-private-inputs-outside-the-public-repository.md). Babu's
target companies are not in the public repository. From CloudShell, upload the list
(same format as `examples/companies.example.yaml`), store it, then delete the copy:

```sh
aws ssm put-parameter --name /pejip/accounts/babu/companies --type SecureString --key-id alias/pejip --tier Intelligent-Tiering --value file://companies.yaml
rm companies.yaml
```

Add `--overwrite` to change it later. Until it exists, each digest says so and only
the test boards in `config/search.yaml` are searched.

## LinkedIn connections (each refresh)

[Design 0014](../docs/design/0014-connection-matching.md). Upload only
`Connections.csv` from the LinkedIn data export, never the whole archive, from
CloudShell (Actions, Upload file), then delete the uploaded copy:

```sh
aws s3 cp Connections.csv s3://pejip-inbox-275704950192/network/babu/Connections.csv
rm Connections.csv
```

The bucket encrypts it with `alias/pejip` and deletes it 90 days later; the next
morning's run uses it and the digest says when it was last refreshed. Answers to
"Your call" questions go in `network/babu/network-decisions.yaml` the same way (see
`examples/network-decisions.example.yaml`). A new upload replaces the old one.

## Ranking routine (once, then every 90 days)

[Design 0015](../docs/design/0015-ranking-routine.md). With `ranker = "routine"`
(the default), on weekdays `pejip run` at 05:00, 10:00 and 15:00 PT stores roles
without ranking them, a Claude Code routine on Babu's claude.ai plan analyses
them at 06:04, 11:04 and 16:04, and `pejip digest` emails the ranked digest at
07:00, 12:00 and 17:00.

1. In CloudShell, make the key and store only its SHA-256 on AWS:
   `key=$(openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-48)`, then
   `printf %s "$key" | sha256sum | cut -d' ' -f1 > key.sha256` and
   `aws ssm put-parameter --name /pejip/ranking-key-sha256 --type SecureString --key-id alias/pejip --value "$(cat key.sha256)" --overwrite`.
   Copy `$key` once (`echo "$key"`), then `rm key.sha256; unset key`.
2. Apply and deploy.
3. In claude.ai, add a cloud environment for the routine with the secret
   `PEJIP_RANKING_KEY` (the key from step 1), `PEJIP_RANKING_URL=https://job-search.zephyr-mcg.com`,
   and network access to `job-search.zephyr-mcg.com`. The key is pasted only there.
4. Create the routine at claude.ai/code/routines in that environment, with
   three weekday schedule triggers at 6:04 AM, 11:04 AM and 4:04 PM Pacific.

To rotate, repeat steps 1 and 3. The app reads the new hash within five minutes,
so the old key stops working then.

## Google sign-in

Every route except `/healthz` requires signing in with a Google account in the
account registry: `sign_in_accounts`, or `sign_in_email` alone as account `babu`
([design 0016](../docs/design/0016-accounts.md),
[ADR-0006](../docs/adr/0006-google-sign-in-at-the-load-balancer.md),
[design 0009](../docs/design/0009-google-sign-in.md)). One-time setup:

1. In Google Cloud Console, create (or pick) a project and set up the OAuth
   consent screen: External, app name `PEJIP`, publishing status **Testing**, and
   add your Google address as the only test user.
2. Create an OAuth client ID of type **Web application** with the authorized
   redirect URI `https://job-search.zephyr-mcg.com/oauth2/idpresponse`
   (`terraform output google_redirect_uri`).
3. In CloudShell, store the client ID and secret (the secret is typed, not echoed):

   ```sh
   aws ssm put-parameter --name /pejip/google-oauth/client-id --type String \
     --value 'CLIENT_ID.apps.googleusercontent.com'
   read -rs SECRET && aws ssm put-parameter --name /pejip/google-oauth/client-secret \
     --type SecureString --key-id alias/pejip --value "$SECRET" && unset SECRET
   ```

4. Let CI's plan read them: `terraform apply -target=aws_iam_role_policy.github_plan`.
5. Apply everything with `terraform apply`, then redeploy so the running task picks
   up the sign-in settings: run the Deploy workflow with `image_tag` set to the
   commit running now.

To rotate the secret, update the parameter (`--overwrite`) and run `terraform apply`.

## GitHub settings

- Variables: `AWS_DEPLOY_ROLE_ARN`, `AWS_PLAN_ROLE_ARN` (from `terraform output`),
  `DEPLOY_ENABLED` (`true` once the first deploy steps above are done) and
  optionally `APP_URL` (defaults to `https://job-search.zephyr-mcg.com`).
- Secret: `ALERT_EMAIL`, used by `terraform plan` in CI.
- Required check `Container image` (from the Deploy workflow) in Settings > Rules,
  matching `.github/rulesets/main.json`.
