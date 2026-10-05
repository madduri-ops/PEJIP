locals {
  name       = "pejip-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
  # GitHub's OIDC sub claim for this repo carries immutable IDs:
  # repo:<owner>@<owner_id>/<repo>@<repo_id>:<context>
  repo_sub = "repo:${var.github_owner}@${var.github_owner_id}/${var.github_repo}@${var.github_repo_id}"

  state_bucket = "pejip-tfstate-${var.aws_account_id}"
  state_key    = "pejip/${var.environment}/terraform.tfstate"

  ecs_service_arn   = "arn:aws:ecs:${var.aws_region}:${local.account_id}:service/${local.name}/${local.name}"
  ecs_task_role_arn = "arn:aws:iam::${local.account_id}:role/pejip-ecs-*"

  task_family_arn = "arn:aws:ecs:${var.aws_region}:${local.account_id}:task-definition/${local.name}"

  log_group_name      = "/ecs/${local.name}"
  flow_log_group_name = "/vpc/${local.name}/flow-logs"
}

data "aws_caller_identity" "current" {}

# The GitHub OIDC provider is account-wide and managed by the KRI Terraform.
# PEJIP only reads it (ADR-0001, GitHub OIDC).
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}
