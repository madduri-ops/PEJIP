# GitHub Actions roles (ADR-0001, GitHub OIDC). Both trust only this repository,
# and every permission is scoped to PEJIP's own resources.

# ── Deploy role: assumed by workflows on main ────────────────────────────────
data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.repo_sub}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "pejip-github-deploy"
  description          = "Assumed by GitHub Actions on main of ${var.github_owner}/${var.github_repo} to deploy PEJIP"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  # GetAuthorizationToken has no resource-level permissions; AWS requires "*".
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # The ECR repository is encrypted with the PEJIP key.
  statement {
    sid       = "EcrEncryption"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.pejip.arn]
  }

  statement {
    sid       = "EcsDeployService"
    actions   = ["ecs:DescribeServices", "ecs:UpdateService"]
    resources = [local.ecs_service_arn]
  }

  # Task definition registration and lookup have no resource-level permissions
  # for new revisions; AWS requires "*".
  statement {
    sid       = "EcsTaskDefinitions"
    actions   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
    resources = ["*"]
  }

  statement {
    sid       = "PassPejipTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [local.ecs_task_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "pejip-github-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

# ── Plan role: assumed by pull request workflows, read only ──────────────────
data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.repo_sub}:pull_request"]
    }
  }
}

resource "aws_iam_role" "github_plan" {
  name                 = "pejip-github-plan"
  description          = "Assumed by GitHub Actions on pull requests of ${var.github_owner}/${var.github_repo} to run terraform plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "plan" {
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]
  }

  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/${local.state_key}"]
  }

  # terraform plan takes the S3 lock by writing and removing a .tflock object.
  statement {
    sid       = "StateLock"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/${local.state_key}.tflock"]
  }

  statement {
    sid       = "StateEncryption"
    actions   = ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey", "kms:GetKeyPolicy", "kms:GetKeyRotationStatus", "kms:ListResourceTags"]
    resources = [aws_kms_key.pejip.arn]
  }

  # Listing aliases has no resource-level permissions; AWS requires "*".
  statement {
    sid       = "KmsAliases"
    actions   = ["kms:ListAliases"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadEcr"
    actions   = ["ecr:DescribeRepositories", "ecr:GetLifecyclePolicy", "ecr:ListTagsForResource"]
    resources = [aws_ecr_repository.app.arn]
  }

  statement {
    sid       = "ReadIam"
    actions   = ["iam:GetRole", "iam:GetRolePolicy", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies"]
    resources = ["arn:aws:iam::${local.account_id}:role/pejip-*"]
  }

  statement {
    sid       = "ReadOidcProvider"
    actions   = ["iam:GetOpenIDConnectProvider"]
    resources = [data.aws_iam_openid_connect_provider.github.arn]
  }

  # The OIDC provider data source looks the provider up by URL.
  statement {
    sid       = "ListOidcProviders"
    actions   = ["iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadSns"
    actions   = ["sns:GetSubscriptionAttributes", "sns:GetTopicAttributes", "sns:ListSubscriptionsByTopic", "sns:ListTagsForResource"]
    resources = ["arn:aws:sns:${var.aws_region}:${local.account_id}:pejip-*"]
  }

  statement {
    sid       = "ReadBudget"
    actions   = ["budgets:ListTagsForResource", "budgets:ViewBudget"]
    resources = ["arn:aws:budgets::${local.account_id}:budget/pejip-*"]
  }
}

resource "aws_iam_role_policy" "github_plan" {
  name   = "pejip-github-plan"
  role   = aws_iam_role.github_plan.id
  policy = data.aws_iam_policy_document.plan.json
}
