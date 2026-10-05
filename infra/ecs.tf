# ECS Fargate service for the PEJIP API (ADR-0001, ADR-0005).
#
# Terraform owns the cluster, service and the shape of the task definition. The
# Deploy workflow owns which image runs: it copies the latest pejip-prod task
# definition, swaps in the image it just pushed, registers that revision and
# points the service at it. So the service ignores task_definition and
# desired_count drift, and Terraform's own revision names a placeholder tag that
# never runs (the service starts at zero tasks; the first deploy scales it to one).

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

# Used by the running app. Today it only publishes PEJIP metrics (the AI cost
# guard); data, secrets and KMS access are added with the features that need them.
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

  container_definitions = jsonencode([{
    name      = "pejip"
    image     = "${aws_ecr_repository.app.repository_url}:bootstrap"
    essential = true
    # The image's default command serves the API (python -m pejip.api).
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    environment = [
      { name = "PEJIP_HOST", value = "0.0.0.0" },
      { name = "PEJIP_PORT", value = tostring(var.container_port) },
      { name = "PEJIP_ENVIRONMENT", value = var.environment },
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
