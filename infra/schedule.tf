# Daily tasks (design doc 0012, policy section 10). EventBridge Scheduler runs
# the PEJIP image as one-off Fargate tasks with a command override:
#
# - `pejip run` at 05:00, 10:00 and 15:00 on weekdays: find roles, rank them,
#   store them on the data file system (efs.tf) and email the digest
#   (digest.tf). With ranker = "routine" (design doc 0015) it leaves new roles
#   for the Claude Code routine an hour later, and `pejip digest` emails the
#   ranked digest two hours after each search (07:00, 12:00, 17:00).
# - `pejip purge` once a day, so data past its 90-day window is deleted even on
#   a day the run fails.
#
# Both target the task family without a revision, so they always run the image
# the Deploy workflow last shipped. Run outcomes are alarmed from the app's
# `run_finished` log events (infra/monitoring.tf, design 0011).

locals {
  scheduled_tasks = {
    run = {
      name        = "pejip-run-daily"
      description = "Finds and ranks roles, then emails Babu the PEJIP digest"
      expression  = var.run_schedule
      timezone    = var.run_schedule_timezone
      enabled     = var.run_schedule_enabled
      command     = ["pejip", "run"]
      cpu         = var.run_task_cpu
      memory      = var.run_task_memory
    }
    digest = {
      name        = "pejip-digest-daily"
      description = "Emails Babu the PEJIP digest, ranked by the Claude Code routine"
      expression  = var.digest_schedule
      timezone    = var.run_schedule_timezone
      enabled     = var.run_schedule_enabled && var.ranker == "routine"
      command     = ["pejip", "digest"]
      cpu         = var.task_cpu
      memory      = var.task_memory
    }
    purge = {
      name        = "pejip-purge-daily"
      description = "Deletes PEJIP data past the 90-day retention window"
      expression  = "cron(30 9 * * ? *)"
      timezone    = "UTC"
      enabled     = var.purge_schedule_enabled
      command     = ["pejip", "purge"]
      cpu         = var.task_cpu
      memory      = var.task_memory
    }
  }
}

# PEJIP's own schedule group, so the scheduler-failure alarm (monitoring.tf)
# watches only PEJIP's schedules, never another app's in this account.
resource "aws_scheduler_schedule_group" "pejip" {
  name = local.name
}

moved {
  from = aws_scheduler_schedule.purge
  to   = aws_scheduler_schedule.task["purge"]
}

resource "aws_scheduler_schedule" "task" {
  for_each = local.scheduled_tasks

  name                         = each.value.name
  group_name                   = aws_scheduler_schedule_group.pejip.name
  description                  = each.value.description
  schedule_expression          = each.value.expression
  schedule_expression_timezone = each.value.timezone
  state                        = each.value.enabled ? "ENABLED" : "DISABLED"
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
      cpu    = tostring(each.value.cpu)
      memory = tostring(each.value.memory)
      containerOverrides = [{
        name    = "pejip"
        command = each.value.command
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
      variable = "kms:EncryptionContext:aws:scheduler:schedule:arn"
      values   = ["arn:aws:scheduler:${var.aws_region}:${local.account_id}:schedule/${local.name}/pejip-*"]
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
