# ECS Fargate service for the PEJIP API (ADR-0001, ADR-0005).
#
# Terraform owns the cluster, service and the shape of the task definition. The
# Deploy workflow owns which image runs: it copies the latest pejip-prod task
# definition, swaps in the image it just pushed, registers that revision and
# points the service at it. So the service ignores task_definition and
# desired_count drift. Terraform's own revisions reuse the image the service is
# running now, because the daily schedules always start the family's latest
# revision: an apply must never leave them on an image that doesn't exist.

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "app" {
  #checkov:skip=CKV_AWS_338:Policy section 10 caps retention at 90 days
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.pejip.arn
}

# ── Roles ────────────────────────────────────────────────────────────────────
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# Used by ECS itself to pull the image and write logs.
resource "aws_iam_role" "ecs_execution" {
  name               = "pejip-ecs-execution"
  description        = "Pulls the PEJIP image and writes its logs"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "ecs_execution" {
  # GetAuthorizationToken has no resource-level permissions; AWS requires "*".
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "EcrPull"
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.app.arn]
  }

  statement {
    sid       = "EcrDecrypt"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.pejip.arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }
}

resource "aws_iam_role_policy" "ecs_execution" {
  name   = "pejip-ecs-execution"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution.json
}

# Used by the running app: PEJIP metrics (the AI cost guard), the job-alert
# inbox and the network uploads beside it, the data file system (efs.tf), the career profile parameter and the
# digest topic (digest.tf).
resource "aws_iam_role" "ecs_task" {
  name               = "pejip-ecs-task"
  description        = "Runtime identity of the PEJIP app"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "ecs_task" {
  # PutMetricData has no resource-level permissions; the namespace condition
  # limits it to PEJIP's own metrics.
  statement {
    sid       = "PejipMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["PEJIP"]
    }
  }

  # The job-alert inbox (inbox.tf): read new messages and delete them once read.
  statement {
    sid       = "InboxList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.inbox.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.inbox_prefix}*"]
    }
  }

  statement {
    sid       = "InboxMessages"
    actions   = ["s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.inbox.arn}/${local.inbox_prefix}*"]
  }

  # Babu's LinkedIn export and network decisions, uploaded to network/ in the
  # same encrypted, 90-day bucket (design doc 0014). Read only: the run never
  # writes or deletes them.
  statement {
    sid       = "NetworkList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.inbox.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.network_prefix}*"]
    }
  }

  statement {
    sid       = "NetworkRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.inbox.arn}/${local.network_prefix}*"]
  }

  statement {
    sid       = "InboxDecrypt"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.pejip.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["s3.${var.aws_region}.amazonaws.com"]
    }
  }

  # The data file system (efs.tf), only through its access point.
  statement {
    sid       = "DataFileSystem"
    actions   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
    resources = [aws_efs_file_system.data.arn]

    condition {
      test     = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values   = [aws_efs_access_point.data.arn]
    }
  }

  # Babu's career profile and target companies (ADR-0009), SecureStrings Babu
  # stores by hand (never in Terraform, so they never reach the state file).
  statement {
    sid     = "CareerProfile"
    actions = ["ssm:GetParameter"]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter${local.profile_parameter}",
      "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter${local.companies_parameter}",
    ]
  }

  statement {
    sid       = "CareerProfileDecrypt"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.pejip.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }

  # Emails the digest (digest.tf). The topic is encrypted with the PEJIP key.
  statement {
    sid       = "SendDigest"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.digest.arn]
  }

  statement {
    sid       = "SendDigestEncrypt"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey*"]
    resources = [aws_kms_key.pejip.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["sns.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name   = "pejip-ecs-task"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task.json
}

# ── Task definition and service ──────────────────────────────────────────────
resource "aws_security_group" "tasks" {
  name        = "pejip-tasks"
  description = "PEJIP tasks: inbound only from the load balancer, outbound HTTPS"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "pejip-tasks"
  }
}

resource "aws_vpc_security_group_ingress_rule" "tasks_from_alb" {
  security_group_id            = aws_security_group.tasks.id
  description                  = "From the PEJIP load balancer on the container port"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

# ECR, CloudWatch, job sources and the Anthropic API are all HTTPS.
resource "aws_vpc_security_group_egress_rule" "tasks_https" {
  security_group_id = aws_security_group.tasks.id
  description       = "HTTPS to AWS APIs, job sources and the Anthropic API"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# The image the service runs right now (set by the Deploy workflow). Read by
# name, so it adds no dependency on the service resource below.
data "aws_ecs_service" "live" {
  service_name = local.name
  cluster_arn  = "arn:aws:ecs:${var.aws_region}:${local.account_id}:cluster/${local.name}"
}

data "aws_ecs_container_definition" "live" {
  task_definition = data.aws_ecs_service.live.task_definition
  container_name  = "pejip"
}

locals {
  data_dir            = "/data"
  profile_parameter   = "/pejip/profile"
  companies_parameter = "/pejip/companies"

  # What `pejip run` and `pejip purge` read (design doc 0012). The API reads only
  # the company list, for the Settings page (ADR-0009).
  run_environment = [
    { name = "PEJIP_DATABASE_URL", value = "sqlite:///${local.data_dir}/pejip.db" },
    { name = "PEJIP_AI_LEDGER", value = "${local.data_dir}/pejip-ai-spend.db" },
    { name = "PEJIP_OUTPUT_DIR", value = "${local.data_dir}/output" },
    { name = "PEJIP_INBOX_BUCKET", value = aws_s3_bucket.inbox.id },
    { name = "PEJIP_NETWORK_BUCKET", value = aws_s3_bucket.inbox.id },
    { name = "PEJIP_PROFILE_PARAMETER", value = local.profile_parameter },
    { name = "PEJIP_COMPANIES_PARAMETER", value = local.companies_parameter },
    { name = "PEJIP_DIGEST_TOPIC_ARN", value = aws_sns_topic.digest.arn },
  ]

  # Keyless Claude access (ADR-0004). Until the app's federation rule exists in
  # the Claude Console, Claude is switched off and roles are listed unranked.
  claude_ready = var.claude_app_rule_id != "" && var.claude_app_service_account_id != ""
  claude_environment = local.claude_ready ? [
    { name = "PEJIP_AI_ENABLED", value = "true" },
    { name = "PEJIP_CLAUDE_IDENTITY", value = "aws-sts" },
    { name = "ANTHROPIC_ORGANIZATION_ID", value = var.claude_organization_id },
    { name = "ANTHROPIC_FEDERATION_RULE_ID", value = var.claude_app_rule_id },
    { name = "ANTHROPIC_SERVICE_ACCOUNT_ID", value = var.claude_app_service_account_id },
    ] : [
    { name = "PEJIP_AI_ENABLED", value = "false" },
  ]
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "data"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.data.id
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.data.id
        iam             = "ENABLED"
      }
    }
  }

  # Task-local scratch space (Fargate ephemeral storage, encrypted by AWS).
  volume {
    name = "tmp"
  }

  # Tasks mount the data file system at start, so its mount targets must exist.
  depends_on = [aws_efs_mount_target.data]

  container_definitions = jsonencode([{
    name      = "pejip"
    image     = data.aws_ecs_container_definition.live.image
    essential = true
    # The image's default command serves the API (python -m pejip.api).
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    environment = concat([
      { name = "PEJIP_HOST", value = "0.0.0.0" },
      { name = "PEJIP_PORT", value = tostring(var.container_port) },
      { name = "PEJIP_ENVIRONMENT", value = var.environment },
      # Google sign-in check (ADR-0006): who may sign in, and which load
      # balancer's tokens to trust.
      { name = "PEJIP_AUTH_ALLOWED_EMAIL", value = local.sign_in_email },
      { name = "PEJIP_AUTH_ALB_ARN", value = aws_lb.app.arn },
    ], local.run_environment, local.claude_environment)
    # The data file system (efs.tf) and a scratch /tmp, since the root
    # filesystem is read-only.
    mountPoints = [
      { sourceVolume = "data", containerPath = local.data_dir, readOnly = false },
      { sourceVolume = "tmp", containerPath = "/tmp", readOnly = false },
    ]
    readonlyRootFilesystem = true
    user                   = "10001"
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "pejip"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name                   = local.name
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.app.arn
  launch_type            = "FARGATE"
  desired_count          = 0
  enable_execute_command = false
  propagate_tags         = "SERVICE"

  # Health checks get a minute before a slow start counts against the task.
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  # A deployment whose tasks keep failing is stopped and rolled back by ECS.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets         = aws_subnet.public[*].id
    security_groups = [aws_security_group.tasks.id]
    #checkov:skip=CKV_AWS_333:No NAT gateway (ADR-0005); the task security group admits only the ALB
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "pejip"
    container_port   = var.container_port
  }

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  depends_on = [aws_lb_listener.https]
}
