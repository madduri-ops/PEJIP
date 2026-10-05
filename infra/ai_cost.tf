# AI cost alarms (docs/BUILD_POLICY.md section 13, docs/design/ai-cost-guard.md).
# The app's cost guard (src/pejip/cost) publishes month-to-date Claude API spend
# to PEJIP/AISpendMonthToDateUSD after every call. Each alarm below emails Babu
# through pejip-alerts the first time spend reaches its share of the cap in a
# month. The metric drops back to near zero when a new month starts, which
# returns the alarms to OK without a notification.
locals {
  ai_spend_alert_percents = toset(["50", "60", "70", "80", "90", "100"])
}

resource "aws_cloudwatch_metric_alarm" "ai_spend" {
  for_each = local.ai_spend_alert_percents

  alarm_name        = "pejip-ai-spend-${each.key}pct"
  alarm_description = "PEJIP Claude API spend reached ${each.key}% of the $${var.ai_monthly_cap_usd} monthly cap. The cost guard refuses non-essential calls at 100%."

  namespace   = "PEJIP"
  metric_name = "AISpendMonthToDateUSD"
  dimensions = {
    Environment = var.environment
  }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = var.ai_monthly_cap_usd * tonumber(each.key) / 100
  # Spend is only published when a call is made; gaps keep the current state
  # so a quiet day doesn't reset an alarm and re-send its email.
  treat_missing_data = "ignore"

  alarm_actions = [aws_sns_topic.alerts.arn]
}
