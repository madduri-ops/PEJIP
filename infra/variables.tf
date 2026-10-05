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
