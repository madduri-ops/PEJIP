# Google sign-in in front of PEJIP (ADR-0006, design 0009).
#
# The HTTPS listener signs every request in with Google before forwarding it
# (alb.tf), except /healthz, which the post-deploy health gate polls from
# GitHub. Google lets any account sign in to an OAuth client, so the app checks
# the signed-in address against sign_in_email (src/pejip/auth.py) and refuses
# everyone else.
#
# Babu creates the OAuth client in Google Cloud and stores its ID and secret in
# SSM Parameter Store, encrypted with alias/pejip (infra/README.md, "Google
# sign-in"). They never appear in the repository.

data "aws_ssm_parameter" "google_client_id" {
  name = "/pejip/google-oauth/client-id"
}

data "aws_ssm_parameter" "google_client_secret" {
  name            = "/pejip/google-oauth/client-secret"
  with_decryption = true
}

locals {
  # Babu's sign-in address; the alert address unless set separately.
  sign_in_email = coalesce(var.sign_in_email, var.alert_email)

  google_oidc = {
    issuer                 = "https://accounts.google.com"
    authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint         = "https://oauth2.googleapis.com/token"
    user_info_endpoint     = "https://openidconnect.googleapis.com/v1/userinfo"
  }
}

# The health check path stays open: the load balancer's own target health checks
# never pass through the listener, but the Deploy workflow's health gate does.
resource "aws_lb_listener_rule" "healthz" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 1

  condition {
    path_pattern {
      values = ["/healthz"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# The ranking routine runs on claude.ai, not in a browser, so it can't sign in
# with Google. Its two endpoints skip sign-in here and check the routine's key
# in the app instead (design doc 0015, ADR-0008).
resource "aws_lb_listener_rule" "ranking" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 2

  condition {
    path_pattern {
      values = ["/api/ranking/*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Sign out (POST /signout) expires the load balancer's session cookie and lands
# here. This page and its stylesheet skip sign-in, or Google would sign Babu
# straight back in. The page shows no data.
resource "aws_lb_listener_rule" "signed_out" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 3

  condition {
    path_pattern {
      values = ["/signed-out", "/portal.css"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# The load balancer calls Google's token and user info endpoints itself when a
# sign-in completes.
resource "aws_vpc_security_group_egress_rule" "alb_to_google" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS to the Google sign-in endpoints"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
