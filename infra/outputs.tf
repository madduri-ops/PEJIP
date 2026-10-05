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

output "claude_federation_issuer_url" {
  description = "Register as the AWS issuer in the Claude Console (Settings > Workload identity)."
  value       = aws_iam_outbound_web_identity_federation.this.issuer_identifier
}

output "claude_federation_policy_arn" {
  description = "Attach to any PEJIP role that calls Claude (the ECS task role)."
  value       = aws_iam_policy.claude_federation.arn
}
