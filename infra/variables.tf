variable "aws_account_id" {
  description = "AWS account PEJIP runs in. The provider refuses to run against any other account."
  type        = string
  default     = "275704950192"
}

variable "aws_region" {
  description = "AWS region PEJIP runs in."
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment, used in resource names (pejip-<environment>)."
  type        = string
  default     = "prod"
}

variable "github_owner" {
  description = "GitHub owner of the PEJIP repository."
  type        = string
  default     = "madduri-ops"
}

variable "github_repo" {
  description = "GitHub repository whose workflows may assume the PEJIP roles."
  type        = string
  default     = "PEJIP"
}

variable "github_owner_id" {
  description = "Numeric GitHub ID of the owner. GitHub puts it in the OIDC sub claim, so a renamed or re-created account can't match."
  type        = string
  default     = "289717107"
}

variable "github_repo_id" {
  description = "Numeric GitHub ID of the PEJIP repository, as it appears in the OIDC sub claim."
  type        = string
  default     = "1404604379"
}

variable "kms_key_id" {
  description = "ID of the bootstrap KMS key behind alias/pejip (ADR-0001). Imported, not created."
  type        = string
  default     = "fc979f49-0e8a-484b-94bc-eac21b5b5987"
}

variable "alert_email" {
  description = "Email address that receives PEJIP alerts. Not committed; pass with TF_VAR_alert_email."
  type        = string
  sensitive   = true
}

variable "monthly_budget_usd" {
  description = "Monthly AWS spend budget for resources tagged Project = PEJIP, in US dollars."
  type        = number
  default     = 50
}

variable "ai_monthly_cap_usd" {
  description = "Monthly Claude API spend cap in US dollars (policy section 13). Must match CostGuard's cap_usd in the app."
  type        = number
  default     = 100

  validation {
    condition     = var.ai_monthly_cap_usd > 0
    error_message = "The AI spend cap must be positive."
  }
}

variable "domain_name" {
  description = "Public hostname PEJIP is served on. DNS is at Babu's registrar, so its records are added by hand from the Terraform outputs."
  type        = string
  default     = "job-search.zephyr-mcg.com"
}

variable "vpc_cidr" {
  description = "CIDR of pejip-vpc (ADR-0001). Must not overlap KRI's 10.0.0.0/16."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for the public subnets. The ALB needs two. Listed here rather than looked up so terraform plan needs no extra read permissions."
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "The load balancer needs subnets in at least two availability zones."
  }
}

variable "container_port" {
  description = "Port the API listens on inside the container (PEJIP_PORT)."
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 512
}

variable "log_retention_days" {
  description = "Retention for PEJIP log groups. Capped at the 90-day data retention of policy section 10."
  type        = number
  default     = 90

  validation {
    condition     = var.log_retention_days <= 90
    error_message = "Logs may not be kept longer than the 90-day retention in policy section 10."
  }
}

variable "purge_schedule_enabled" {
  description = "Turns on the daily `pejip purge` task."
  type        = bool
  default     = true
}

variable "run_schedule_enabled" {
  description = "Turns on the daily `pejip run` that finds, ranks and emails the digest."
  type        = bool
  default     = true
}

variable "run_schedule" {
  description = "When the daily search runs: an EventBridge Scheduler cron expression in run_schedule_timezone."
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "run_schedule_timezone" {
  description = "Time zone for run_schedule. Babu is in the Bay Area."
  type        = string
  default     = "America/Los_Angeles"
}

variable "run_task_cpu" {
  description = "Fargate CPU units for the daily run (it parses every job board, so it gets more than the API)."
  type        = number
  default     = 512
}

variable "run_task_memory" {
  description = "Fargate memory in MiB for the daily run."
  type        = number
  default     = 1024
}

variable "claude_organization_id" {
  description = "Anthropic organization UUID (not a secret; also in the CI workflows)."
  type        = string
  default     = "a477af3f-5a3d-4ce5-baf6-dce8ef60bcba"
}

variable "claude_app_rule_id" {
  description = "Claude Console federation rule (fdrl_...) for the app's ECS task role. Empty keeps Claude off and roles unranked."
  type        = string
  default     = ""

  validation {
    condition     = var.claude_app_rule_id == "" || can(regex("^fdrl_[A-Za-z0-9]+$", var.claude_app_rule_id))
    error_message = "claude_app_rule_id must be empty or an fdrl_... ID."
  }
}

variable "claude_app_service_account_id" {
  description = "Claude Console service account (svac_...) the app's rule signs in as. Empty keeps Claude off."
  type        = string
  default     = ""

  validation {
    condition     = var.claude_app_service_account_id == "" || can(regex("^svac_[A-Za-z0-9]+$", var.claude_app_service_account_id))
    error_message = "claude_app_service_account_id must be empty or an svac_... ID."
  }
}

variable "sign_in_email" {
  description = "The one Google account allowed to sign in (ADR-0006). Not committed; pass with TF_VAR_sign_in_email. Defaults to alert_email."
  type        = string
  sensitive   = true
  default     = null
}

variable "sign_in_session_seconds" {
  description = "How long a Google sign-in lasts before the load balancer asks again."
  type        = number
  default     = 43200

  validation {
    condition     = var.sign_in_session_seconds >= 300 && var.sign_in_session_seconds <= 604800
    error_message = "The sign-in session must be between 5 minutes and 7 days."
  }
}

variable "inbox_domain" {
  description = "Domain whose mail SES receives for the job-alert inbox; its MX record points at SES."
  type        = string
  default     = "inbox.job-search.zephyr-mcg.com"
}

variable "inbox_receiving_enabled" {
  description = "Activates the pejip-inbox receipt rule set. SES allows one active rule set per account and region; on 2026-10-05 nothing else in this account used SES receiving in us-west-2. Re-check before adding another rule set (infra/README.md)."
  type        = bool
  default     = true
}
