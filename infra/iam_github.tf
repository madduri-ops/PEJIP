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

  # The workflow tags each revision it registers with Project = PEJIP, since
  # provider default_tags don't reach revisions registered outside Terraform.
  statement {
    sid       = "EcsTagTaskDefinitions"
    actions   = ["ecs:TagResource"]
    resources = ["${local.task_family_arn}:*"]

    condition {
      test     = "StringEquals"
      variable = "ecs:CreateAction"
      values   = ["RegisterTaskDefinition"]
    }
  }

  # Deploy success and failure emails (policy section 6).
  statement {
    sid       = "NotifyDeploys"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
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
    sid       = "ReadAlarms"
    actions   = ["cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource"]
    resources = ["arn:aws:cloudwatch:${var.aws_region}:${local.account_id}:alarm:pejip-*"]
  }

  statement {
    sid       = "ReadDashboards"
    actions   = ["cloudwatch:GetDashboard"]
    resources = ["arn:aws:cloudwatch::${local.account_id}:dashboard/pejip*"]
  }

  statement {
    sid       = "ReadMetricFilters"
    actions   = ["logs:DescribeMetricFilters"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*pejip*"]
  }

  statement {
    sid       = "ReadBudget"
    actions   = ["budgets:ListTagsForResource", "budgets:ViewBudget"]
    resources = ["arn:aws:budgets::${local.account_id}:budget/pejip-*"]
  }

  # EC2, load balancer and ECS task definition descriptions have
  # no resource-level permissions; AWS requires "*". All are read only.
  statement {
    sid = "ReadHostingDescriptions"
    actions = [
      "ec2:DescribeFlowLogs",
      "ec2:DescribeInternetGateways",
      "ec2:DescribeNetworkAcls",
      "ec2:DescribeRouteTables",
      "ec2:DescribeSecurityGroupRules",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcs",
      "ecs:DescribeTaskDefinition",
      "elasticloadbalancing:DescribeListenerAttributes",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeLoadBalancerAttributes",
      "elasticloadbalancing:DescribeLoadBalancers",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:DescribeTags",
      "elasticloadbalancing:DescribeTargetGroupAttributes",
      "elasticloadbalancing:DescribeTargetGroups",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "ReadVpcAttributes"
    actions   = ["ec2:DescribeVpcAttribute"]
    resources = ["arn:aws:ec2:${var.aws_region}:${local.account_id}:vpc/*"]
  }

  statement {
    sid       = "ReadCertificates"
    actions   = ["acm:DescribeCertificate", "acm:ListTagsForCertificate"]
    resources = ["arn:aws:acm:${var.aws_region}:${local.account_id}:certificate/*"]
  }

  statement {
    sid       = "ReadLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*"]
  }

  statement {
    sid       = "ReadEcs"
    actions   = ["ecs:DescribeClusters", "ecs:DescribeServices", "ecs:ListTagsForResource"]
    resources = ["arn:aws:ecs:${var.aws_region}:${local.account_id}:*/${local.name}*"]
  }

  statement {
    sid       = "ReadLogGroupTags"
    actions   = ["logs:ListTagsForResource", "logs:ListTagsLogGroup"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*pejip*"]
  }

  statement {
    sid       = "ReadWaf"
    actions   = ["wafv2:GetLoggingConfiguration", "wafv2:GetWebACL", "wafv2:ListTagsForResource"]
    resources = ["arn:aws:wafv2:${var.aws_region}:${local.account_id}:regional/*/pejip-*/*"]
  }

  # GetWebACLForResource looks up whichever web ACL protects the load balancer,
  # so IAM checks it against every regional web ACL (regional/webacl/*/*), not
  # a named one. Read-only, and still limited to this account and region.
  statement {
    sid       = "ReadWafAssociation"
    actions   = ["wafv2:GetWebACLForResource"]
    resources = ["arn:aws:wafv2:${var.aws_region}:${local.account_id}:regional/webacl/*/*", "arn:aws:elasticloadbalancing:${var.aws_region}:${local.account_id}:loadbalancer/app/pejip-*/*"]
  }

  # Plan reads the Google OAuth client the listener signs in with (auth.tf).
  # The values are already in the state this role can read.
  statement {
    sid       = "ReadGoogleOauthClient"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/pejip/google-oauth/*"]
  }

  # The job-alert inbox (inbox.tf). Bucket configuration only, never messages.
  statement {
    sid = "ReadInboxBucket"
    actions = [
      "s3:GetAccelerateConfiguration",
      "s3:GetBucketAcl",
      "s3:GetBucketCORS",
      "s3:GetBucketLogging",
      "s3:GetBucketObjectLockConfiguration",
      "s3:GetBucketOwnershipControls",
      "s3:GetBucketPolicy",
      "s3:GetBucketPublicAccessBlock",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketTagging",
      "s3:GetBucketVersioning",
      "s3:GetBucketWebsite",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]
    resources = ["arn:aws:s3:::pejip-inbox-${var.aws_account_id}"]
  }

  # SES receipt rule and identity reads have no resource-level permissions;
  # AWS requires "*". All are read only.
  statement {
    sid       = "ReadSesReceiving"
    actions   = ["ses:DescribeActiveReceiptRuleSet", "ses:DescribeReceiptRule", "ses:DescribeReceiptRuleSet", "ses:GetIdentityVerificationAttributes"]
    resources = ["*"]
  }

  statement {
    sid     = "ReadSchedules"
    actions = ["scheduler:GetSchedule", "scheduler:GetScheduleGroup", "scheduler:ListTagsForResource"]
    resources = [
      "arn:aws:scheduler:${var.aws_region}:${local.account_id}:schedule/default/pejip-*",
      "arn:aws:scheduler:${var.aws_region}:${local.account_id}:schedule/${local.name}/pejip-*",
      "arn:aws:scheduler:${var.aws_region}:${local.account_id}:schedule-group/${local.name}",
    ]
  }

  # The data file system (efs.tf). Configuration only; the plan role can't mount it.
  statement {
    sid = "ReadDataFileSystem"
    actions = [
      "elasticfilesystem:DescribeAccessPoints",
      "elasticfilesystem:DescribeBackupPolicy",
      "elasticfilesystem:DescribeFileSystemPolicy",
      "elasticfilesystem:DescribeFileSystems",
      "elasticfilesystem:DescribeLifecycleConfiguration",
      "elasticfilesystem:DescribeMountTargetSecurityGroups",
      "elasticfilesystem:DescribeMountTargets",
      "elasticfilesystem:ListTagsForResource",
    ]
    resources = [
      "arn:aws:elasticfilesystem:${var.aws_region}:${local.account_id}:file-system/*",
      "arn:aws:elasticfilesystem:${var.aws_region}:${local.account_id}:access-point/*",
    ]
  }

  # Describing a mount target's network interface; no resource-level permissions.
  statement {
    sid       = "ReadMountTargetInterfaces"
    actions   = ["ec2:DescribeNetworkInterfaces"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_plan" {
  name   = "pejip-github-plan"
  role   = aws_iam_role.github_plan.id
  policy = data.aws_iam_policy_document.plan.json
}
