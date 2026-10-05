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

output "certificate_validation_records" {
  description = "Add each as a CNAME at the zephyr-mcg.com registrar so ACM can issue the certificate."
  value = [for o in aws_acm_certificate.app.domain_validation_options : {
    name  = o.resource_record_name
    type  = o.resource_record_type
    value = o.resource_record_value
  }]
}

output "alb_dns_name" {
  description = "Point a CNAME for the hostname (job-search) at this name at the registrar."
  value       = aws_lb.app.dns_name
}

output "app_url" {
  description = "Public URL the Deploy workflow's health gate polls."
  value       = "https://${var.domain_name}"
}
