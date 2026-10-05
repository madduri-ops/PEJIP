# Search, error and spend monitoring (policy section 14, design 0011).
#
# The app already writes structured JSON logs to /ecs/pejip-prod, so search and
# error metrics come from log metric filters rather than extra API calls in the
# app: `run_finished` (with its status), `source_failed` and any ERROR line.
# Each alarm emails Babu through pejip-alerts once, on the way into ALARM.
# Spend alarms are in ai_cost.tf and the hosting alarms in alarms.tf; the
# dashboard shows all of them in one place.

locals {
  search_metrics = {
    SearchRunsSucceeded = "{ ($.event = \"run_finished\") && ($.status = \"SUCCESS\") }"
    SearchRunsPartial   = "{ ($.event = \"run_finished\") && ($.status = \"PARTIAL\") }"
    SearchRunsFailed    = "{ ($.event = \"run_finished\") && ($.status = \"FAILED\") }"
    SourceFailures      = "{ $.event = \"source_failed\" }"
    AppErrors           = "{ ($.level = \"ERROR\") || ($.level = \"CRITICAL\") }"
  }
}

resource "aws_cloudwatch_log_metric_filter" "search" {
  for_each = local.search_metrics

  name           = "pejip-${each.key}"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = each.value

  metric_transformation {
    namespace = "PEJIP"
    name      = each.key
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "search_run_failed" {
  alarm_name          = "pejip-search-run-failed"
  alarm_description   = "A PEJIP search run finished FAILED: every job source failed. The run's digest lists each source's error."
  namespace           = "PEJIP"
  metric_name         = aws_cloudwatch_log_metric_filter.search["SearchRunsFailed"].metric_transformation[0].name
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}

# A single broken source makes the run PARTIAL, not FAILED, so it gets its own
# alarm. The dashboard's "Source failures by source" table names the source.
resource "aws_cloudwatch_metric_alarm" "source_failures" {
  alarm_name          = "pejip-source-failures"
  alarm_description   = "A PEJIP job source could not be fetched. See the Source failures table on the pejip dashboard for which one."
  namespace           = "PEJIP"
  metric_name         = aws_cloudwatch_log_metric_filter.search["SourceFailures"].metric_transformation[0].name
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "app_errors" {
  alarm_name          = "pejip-app-errors"
  alarm_description   = "PEJIP logged an error (a crashed run, failed spend reporting, or another ERROR line). See Recent errors on the pejip dashboard."
  namespace           = "PEJIP"
  metric_name         = aws_cloudwatch_log_metric_filter.search["AppErrors"].metric_transformation[0].name
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}

# A stalled pipeline: no run finished (SUCCESS or PARTIAL) in 26 hours, which
# covers a schedule that stopped, a task that never started and a crash before
# run_finished. It exists only while the daily run schedule is on
# (schedule.tf); otherwise it would alarm for a search that is not meant to run.
# This one also emails when it clears.
resource "aws_cloudwatch_metric_alarm" "search_stalled" {
  count = var.run_schedule_enabled ? 1 : 0

  alarm_name          = "pejip-search-stalled"
  alarm_description   = "No PEJIP search run has finished in 26 hours. Check the daily search schedule and the task's logs."
  evaluation_periods  = 26
  datapoints_to_alarm = 26
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions

  metric_query {
    id          = "completed"
    expression  = "FILL(succeeded, 0) + FILL(partial, 0)"
    label       = "Search runs completed"
    return_data = true
  }

  metric_query {
    id = "succeeded"

    metric {
      namespace   = "PEJIP"
      metric_name = aws_cloudwatch_log_metric_filter.search["SearchRunsSucceeded"].metric_transformation[0].name
      stat        = "Sum"
      period      = 3600
    }
  }

  metric_query {
    id = "partial"

    metric {
      namespace   = "PEJIP"
      metric_name = aws_cloudwatch_log_metric_filter.search["SearchRunsPartial"].metric_transformation[0].name
      stat        = "Sum"
      period      = 3600
    }
  }
}

locals {
  monitored_alarm_arns = concat(
    [
      aws_cloudwatch_metric_alarm.search_run_failed.arn,
      aws_cloudwatch_metric_alarm.source_failures.arn,
      aws_cloudwatch_metric_alarm.app_errors.arn,
    ],
    aws_cloudwatch_metric_alarm.search_stalled[*].arn,
    [for alarm in aws_cloudwatch_metric_alarm.ai_spend : alarm.arn],
    [
      aws_cloudwatch_metric_alarm.app_5xx.arn,
      aws_cloudwatch_metric_alarm.alb_5xx.arn,
      aws_cloudwatch_metric_alarm.unhealthy_targets.arn,
      aws_cloudwatch_metric_alarm.tasks_below_desired.arn,
      aws_cloudwatch_metric_alarm.cpu_high.arn,
      aws_cloudwatch_metric_alarm.memory_high.arn,
    ],
  )

  log_source = "SOURCE '${aws_cloudwatch_log_group.app.name}'"
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "pejip"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Search runs per day"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = true
          stat    = "Sum"
          period  = 86400
          metrics = [
            ["PEJIP", "SearchRunsSucceeded", { label = "Succeeded", color = "#2ca02c" }],
            ["PEJIP", "SearchRunsPartial", { label = "Partial", color = "#ff7f0e" }],
            ["PEJIP", "SearchRunsFailed", { label = "Failed", color = "#d62728" }],
          ]
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Source failures by source (time range)"
          region = var.aws_region
          view   = "table"
          query  = "${local.log_source} | filter event = \"source_failed\" | stats count(*) as failures, latest(@timestamp) as last_failed by source | sort failures desc"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Claude API spend this month (USD)"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Maximum"
          period = 3600
          metrics = [
            ["PEJIP", "AISpendMonthToDateUSD", "Environment", var.environment, { label = "Month to date" }],
          ]
          yAxis = { left = { min = 0, max = var.ai_monthly_cap_usd } }
          annotations = {
            horizontal = [
              { label = "50% alert", value = var.ai_monthly_cap_usd / 2, color = "#ff7f0e" },
              { label = "Monthly cap", value = var.ai_monthly_cap_usd, color = "#d62728" },
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Errors per hour"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 3600
          metrics = [
            ["PEJIP", "AppErrors", { label = "Logged errors" }],
            ["PEJIP", "SourceFailures", { label = "Source failures" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.app.arn_suffix, "TargetGroup", aws_lb_target_group.app.arn_suffix, { label = "App 5xx" }],
          ]
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title  = "Recent errors"
          region = var.aws_region
          view   = "table"
          query  = "${local.log_source} | filter level = \"ERROR\" or level = \"CRITICAL\" | fields @timestamp, event, error_type, run_id | sort @timestamp desc | limit 20"
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 18
        width  = 24
        height = 4
        properties = {
          title  = "Alarms"
          alarms = local.monitored_alarm_arns
        }
      },
    ]
  })
}
