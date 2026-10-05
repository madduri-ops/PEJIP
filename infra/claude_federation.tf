# Keyless Claude access for the app (ADR-0004, docs/design/0007-claude-identity-federation.md).
# The ECS task asks AWS STS for a short-lived web identity token addressed to
# Anthropic and swaps it for a short-lived Claude token. No Claude API key exists
# anywhere in AWS.

locals {
  claude_audience = "https://api.anthropic.com"
}

# Account-level switch that lets IAM principals call sts:GetWebIdentityToken. It
# grants nothing by itself: a principal also needs the policy below. Deleting this
# resource would turn the switch off for the whole account, so it is protected.
resource "aws_iam_outbound_web_identity_federation" "this" {
  lifecycle {
    prevent_destroy = true
  }
}

# Tokens only for Anthropic, only RS256, at most 15 minutes. Attached to the app's
# ECS task role by the hosting Terraform.
data "aws_iam_policy_document" "claude_federation" {
  statement {
    sid       = "ClaudeIdentityToken"
    actions   = ["sts:GetWebIdentityToken"]
    resources = ["*"]

    condition {
      test     = "ForAllValues:StringEquals"
      variable = "sts:IdentityTokenAudience"
      values   = [local.claude_audience]
    }

    # ForAllValues passes when the key is absent; require it to be present.
    condition {
      test     = "Null"
      variable = "sts:IdentityTokenAudience"
      values   = ["false"]
    }

    condition {
      test     = "NumericLessThanEquals"
      variable = "sts:DurationSeconds"
      values   = ["900"]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:SigningAlgorithm"
      values   = ["RS256"]
    }
  }
}

resource "aws_iam_policy" "claude_federation" {
  name        = "pejip-claude-federation"
  description = "Lets PEJIP workloads get short-lived identity tokens for the Claude API"
  policy      = data.aws_iam_policy_document.claude_federation.json
}

# The plan role reads these resources on every pull request plan. Kept here, next
# to what it reads, rather than in iam_github.tf.
data "aws_iam_policy_document" "plan_claude_federation" {
  statement {
    sid       = "ReadClaudeFederationPolicy"
    actions   = ["iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions"]
    resources = [aws_iam_policy.claude_federation.arn]
  }

  # Reading the account switch has no resource-level permissions; AWS requires "*".
  statement {
    sid       = "ReadOutboundFederation"
    actions   = ["iam:GetOutboundWebIdentityFederationInfo"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "plan_claude_federation" {
  name   = "pejip-github-plan-claude-federation"
  role   = aws_iam_role.github_plan.id
  policy = data.aws_iam_policy_document.plan_claude_federation.json
}

output "claude_federation_issuer_url" {
  description = "Register as the AWS issuer in the Claude Console (Settings > Workload identity)."
  value       = aws_iam_outbound_web_identity_federation.this.issuer_identifier
}

output "claude_federation_policy_arn" {
  description = "Attach to any PEJIP role that calls Claude (the ECS task role)."
  value       = aws_iam_policy.claude_federation.arn
}
