output "github_deploy_role_arn" {
  description = "Set as the GitHub Actions variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_deploy.arn
}

output "github_plan_role_arn" {
  description = "Set as the GitHub Actions variable AWS_PLAN_ROLE_ARN."
  value       = aws_iam_role.github_plan.arn
}

output "ecr_repository_url" {
  description = "Where CI pushes PEJIP images."
  value       = aws_ecr_repository.app.repository_url
}

output "alerts_topic_arn" {
  description = "SNS topic every PEJIP alarm and budget notifies."
  value       = aws_sns_topic.alerts.arn
}

output "ai_spend_alarm_names" {
  description = "CloudWatch alarms that email at 50% to 100% of the monthly AI spend cap."
  value       = sort([for alarm in aws_cloudwatch_metric_alarm.ai_spend : alarm.alarm_name])
}
