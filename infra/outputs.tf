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

output "google_redirect_uri" {
  description = "Add as an authorized redirect URI on the Google OAuth client."
  value       = "https://${var.domain_name}/oauth2/idpresponse"
}

output "inbox_address" {
  description = "Forward job-alert emails here."
  value       = local.inbox_address
}

output "inbox_dns_records" {
  description = "Add both at the zephyr-mcg.com registrar so SES can verify the domain and receive its mail."
  value = [
    {
      name  = "_amazonses.${var.inbox_domain}"
      type  = "TXT"
      value = aws_ses_domain_identity.inbox.verification_token
    },
    {
      name  = var.inbox_domain
      type  = "MX"
      value = "10 inbound-smtp.${var.aws_region}.amazonaws.com"
    },
  ]
}

output "digest_topic_arn" {
  description = "SNS topic the daily run emails the digest through. Babu confirms its subscription email once."
  value       = try(aws_sns_topic.digest[local.owner_account].arn, null)
}

output "profile_parameter_name" {
  description = "SSM SecureString (key alias/pejip) that holds Babu's career profile YAML. Stored by hand, never by Terraform."
  value       = replace(local.profile_parameter, "{account}", "babu")
}

output "public_subnet_ids" {
  description = "Subnets PEJIP tasks run in (for starting a run by hand, infra/README.md)."
  value       = aws_subnet.public[*].id
}

output "tasks_security_group_id" {
  description = "Security group PEJIP tasks use (for starting a run by hand, infra/README.md)."
  value       = aws_security_group.tasks.id
}

output "dashboard_url" {
  description = "The pejip CloudWatch dashboard: search runs, source failures, errors, Claude spend and every PEJIP alarm."
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "ranking_key_parameter_name" {
  description = "SSM parameter for the SHA-256 of the ranking routine's key (design doc 0015); Babu stores it."
  value       = replace(local.ranking_key_parameter, "{account}", local.owner_account)
}
