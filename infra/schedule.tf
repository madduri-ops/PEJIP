# Daily retention purge (policy section 10). EventBridge Scheduler runs the
# PEJIP image once a day as a one-off Fargate task with the command
# `pejip purge`, so data past its 90-day window is deleted even on days with no
# search. It targets the task family without a revision, so it always runs the
# image the Deploy workflow last shipped.
#
# The schedule is created disabled. Turn it on (purge_schedule_enabled = true)
# once the deployed image has the `pejip purge` command and the app has a
# persistent database; until then the task would have nothing to purge.

resource "aws_scheduler_schedule" "purge" {
  name                         = "pejip-purge-daily"
  description                  = "Deletes PEJIP data past the 90-day retention window"
  schedule_expression          = "cron(30 9 * * ? *)"
  schedule_expression_timezone = "UTC"
  state                        = var.purge_schedule_enabled ? "ENABLED" : "DISABLED"
  kms_key_arn                  = aws_kms_key.pejip.arn

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = local.task_family_arn
      launch_type         = "FARGATE"
      task_count          = 1
      propagate_tags      = "TASK_DEFINITION"

      network_configuration {
        subnets          = aws_subnet.public[*].id
        security_groups  = [aws_security_group.tasks.id]
        assign_public_ip = true
      }
    }

    input = jsonencode({
      containerOverrides = [{
        name    = "pejip"
        command = ["pejip", "purge"]
      }]
    })

    retry_policy {
      maximum_retry_attempts       = 3
      maximum_event_age_in_seconds = 3600
    }
  }
}

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "pejip-scheduler"
  description        = "Lets EventBridge Scheduler start PEJIP's scheduled tasks"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid       = "RunPejipTasks"
    actions   = ["ecs:RunTask"]
    resources = ["${local.task_family_arn}:*", local.task_family_arn]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }

  # The schedule is encrypted with the PEJIP key; Scheduler decrypts it with
  # this role, only for PEJIP's own schedules.
  statement {
    sid       = "DecryptSchedule"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.pejip.arn]

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:scheduler:schedule-arn"
      values   = ["arn:aws:scheduler:${var.aws_region}:${local.account_id}:schedule/default/pejip-*"]
    }
  }

  statement {
    sid       = "TagPejipTasks"
    actions   = ["ecs:TagResource"]
    resources = ["arn:aws:ecs:${var.aws_region}:${local.account_id}:task/${local.name}/*"]

    condition {
      test     = "StringEquals"
      variable = "ecs:CreateAction"
      values   = ["RunTask"]
    }
  }

  statement {
    sid       = "PassPejipTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_execution.arn, aws_iam_role.ecs_task.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "pejip-scheduler"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
