# Job-alert inbox (design doc 0010). Amazon SES receives mail for
# alerts@inbox.job-search.zephyr-mcg.com and stores each message in an
# encrypted bucket; `pejip run` reads new messages, turns the alerts into roles
# and deletes what it has read. Anything left is deleted after 90 days
# (policy section 10).
#
# The receiving domain is a subdomain of the app's host name because the host
# name itself is a CNAME to the load balancer, and a CNAME cannot sit beside an
# MX record.
#
# SES has one active receipt rule set per account and region, shared with
# anything else in this account. The rule set below is only activated when
# inbox_receiving_enabled is true; check that nothing else uses SES receiving
# in this region first (infra/README.md).

locals {
  inbox_bucket  = "pejip-inbox-${var.aws_account_id}"
  inbox_address = "alerts@${var.inbox_domain}"
  inbox_prefix  = "inbound/"

  # Each account's LinkedIn export goes under network/<account>/ (design docs
  # 0014 and 0016); the same 90-day expiry applies.
  network_prefix = "network/"
}

resource "aws_ses_domain_identity" "inbox" {
  domain = var.inbox_domain
}

# ── Bucket ───────────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "inbox" {
  #checkov:skip=CKV_AWS_18:Access logs would hold the same 90-day personal data in a second place; CloudTrail covers access
  #checkov:skip=CKV_AWS_144:Single-region by design (ADR-0001); mail is short-lived and re-sent by each alert
  #checkov:skip=CKV2_AWS_62:The app reads the bucket on each run; no event consumers
  bucket = local.inbox_bucket

  tags = {
    DataClassification = "personal"
  }
}

resource "aws_s3_bucket_public_access_block" "inbox" {
  bucket                  = aws_s3_bucket.inbox.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "inbox" {
  bucket = aws_s3_bucket.inbox.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "inbox" {
  bucket = aws_s3_bucket.inbox.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.pejip.arn
    }
  }
}

resource "aws_s3_bucket_versioning" "inbox" {
  bucket = aws_s3_bucket.inbox.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "inbox" {
  bucket = aws_s3_bucket.inbox.id

  rule {
    id     = "retention-90-days"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    # A deleted message stays recoverable for a day, then is gone.
    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "expired-delete-markers"
    status = "Enabled"

    filter {}

    expiration {
      expired_object_delete_marker = true
    }
  }
}

data "aws_iam_policy_document" "inbox_bucket" {
  statement {
    sid       = "SesDelivers"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.inbox.arn}/${local.inbox_prefix}*"]

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ses:${var.aws_region}:${local.account_id}:receipt-rule-set/pejip-inbox:receipt-rule/*"]
    }
  }

  statement {
    sid       = "TlsOnly"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.inbox.arn, "${aws_s3_bucket.inbox.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "inbox" {
  bucket = aws_s3_bucket.inbox.id
  policy = data.aws_iam_policy_document.inbox_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.inbox]
}

# ── Receiving ────────────────────────────────────────────────────────────────
resource "aws_ses_receipt_rule_set" "inbox" {
  rule_set_name = "pejip-inbox"
}

resource "aws_ses_receipt_rule" "inbox" {
  name          = "pejip-alerts-to-s3"
  rule_set_name = aws_ses_receipt_rule_set.inbox.rule_set_name
  recipients    = [local.inbox_address]
  enabled       = true
  scan_enabled  = true
  tls_policy    = "Require"

  s3_action {
    bucket_name       = aws_s3_bucket.inbox.id
    object_key_prefix = local.inbox_prefix
    position          = 1
  }

  # SES checks it can write to the bucket when the rule is created.
  depends_on = [aws_s3_bucket_policy.inbox, aws_kms_key.pejip]
}

resource "aws_ses_active_receipt_rule_set" "inbox" {
  count         = var.inbox_receiving_enabled ? 1 : 0
  rule_set_name = aws_ses_receipt_rule_set.inbox.rule_set_name
}
