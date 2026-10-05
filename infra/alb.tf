# Load balancer, certificate and firewall for job-search.zephyr-mcg.com
# (ADR-0001, ADR-0005). DNS stays at Babu's registrar: the certificate's
# validation record and the hostname's CNAME are added there by hand from the
# outputs (infra/README.md, "First deploy").

# ── Certificate ──────────────────────────────────────────────────────────────
resource "aws_acm_certificate" "app" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Waits until the validation CNAME is live at the registrar and ACM has issued
# the certificate. The HTTPS listener depends on it.
resource "aws_acm_certificate_validation" "app" {
  certificate_arn = aws_acm_certificate.app.arn

  timeouts {
    create = "2h"
  }
}

# ── Security groups ──────────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "pejip-alb"
  description = "PEJIP load balancer: HTTPS from the internet, HTTP only to redirect"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "pejip-alb"
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from anywhere"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  #checkov:skip=CKV_AWS_260:Port 80 only answers with a redirect to HTTPS
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from anywhere, redirected to HTTPS"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_to_tasks" {
  security_group_id            = aws_security_group.alb.id
  description                  = "To PEJIP tasks on the container port"
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

# ── Load balancer ────────────────────────────────────────────────────────────
resource "aws_lb" "app" {
  #checkov:skip=CKV2_AWS_76:Log4j is covered by the known-bad-inputs rule group; the anonymous IP list it also demands would block Babu on a VPN and the GitHub-hosted health gate (ADR-0005)
  #checkov:skip=CKV_AWS_91:Access logs need an SSE-S3 bucket (ALB cannot write with a KMS key); request data comes from app logs, WAF metrics and flow logs instead (ADR-0005)
  name                       = "pejip-alb"
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
  enable_deletion_protection = true
}

resource "aws_lb_target_group" "app" {
  name                 = local.name
  port                 = var.container_port
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "/healthz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.app.certificate_arn

  # Sign in with Google first (auth.tf), then forward. /healthz skips sign-in
  # through aws_lb_listener_rule.healthz.
  default_action {
    type  = "authenticate-oidc"
    order = 1

    authenticate_oidc {
      issuer                     = local.google_oidc.issuer
      authorization_endpoint     = local.google_oidc.authorization_endpoint
      token_endpoint             = local.google_oidc.token_endpoint
      user_info_endpoint         = local.google_oidc.user_info_endpoint
      client_id                  = data.aws_ssm_parameter.google_client_id.value
      client_secret              = data.aws_ssm_parameter.google_client_secret.value
      scope                      = "openid email"
      session_timeout            = var.sign_in_session_seconds
      on_unauthenticated_request = "authenticate"
    }
  }

  default_action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ── Web application firewall ─────────────────────────────────────────────────
resource "aws_wafv2_web_acl" "app" {
  name        = "pejip-alb"
  description = "AWS managed common and known-bad-input rules in front of PEJIP"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "aws-common"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"

        # Counted here and blocked by "body-size" below everywhere except the
        # ranking routine's answers, which run well past the 8 KB limit.
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "pejip-aws-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-known-bad-inputs"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "pejip-aws-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # The common rule set's 8 KB body limit, except for POST /api/ranking/analyses
  # (design doc 0015), whose answers are checked by the routine's key and by the
  # app's own validation instead.
  rule {
    name     = "body-size"
    priority = 3

    action {
      block {}
    }

    statement {
      and_statement {
        statement {
          label_match_statement {
            scope = "LABEL"
            key   = "awswaf:managed:aws:core-rule-set:SizeRestrictions_Body"
          }
        }
        statement {
          not_statement {
            statement {
              byte_match_statement {
                search_string         = "/api/ranking/analyses"
                positional_constraint = "EXACTLY"

                field_to_match {
                  uri_path {}
                }

                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "pejip-body-size"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "pejip-alb"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "app" {
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.app.arn
}

# WAF logs: blocked requests only, so the log holds attack traffic rather than
# Babu's own requests. The group name must start with aws-waf-logs-.
resource "aws_cloudwatch_log_group" "waf" {
  #checkov:skip=CKV_AWS_338:Policy section 10 caps retention at 90 days
  name              = "aws-waf-logs-pejip"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.pejip.arn
}

resource "aws_wafv2_web_acl_logging_configuration" "app" {
  resource_arn            = aws_wafv2_web_acl.app.arn
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]

  logging_filter {
    default_behavior = "DROP"

    filter {
      behavior    = "KEEP"
      requirement = "MEETS_ANY"

      condition {
        action_condition {
          action = "BLOCK"
        }
      }
    }
  }
}
