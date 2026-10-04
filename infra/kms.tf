# The key was created by hand during bootstrap so it could encrypt the state
# bucket before Terraform existed. Terraform adopts it here to manage its policy.
import {
  to = aws_kms_key.pejip
  id = var.kms_key_id
}

import {
  to = aws_kms_alias.pejip
  id = "alias/pejip"
}

resource "aws_kms_key" "pejip" {
  description         = "PEJIP data and Terraform state"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.kms.json

  tags = {
    DataClassification = "personal"
  }
}

resource "aws_kms_alias" "pejip" {
  name          = "alias/pejip"
  target_key_id = aws_kms_key.pejip.key_id
}

data "aws_iam_policy_document" "kms" {
  # In a key policy, Resource "*" means "this key" and kms:* for the account root
  # is the AWS default that keeps the key manageable; checkov reads them as
  # account-wide grants, which they are not.
  #checkov:skip=CKV_AWS_109:Key policy; "*" is scoped to this key
  #checkov:skip=CKV_AWS_111:Key policy; "*" is scoped to this key
  #checkov:skip=CKV_AWS_356:Key policy; "*" is scoped to this key
  # Account administrators keep full control (the AWS default key policy).
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }

  # AWS Budgets and CloudWatch alarms publish to the encrypted alerts topic.
  statement {
    sid       = "AlertPublishers"
    actions   = ["kms:GenerateDataKey*", "kms:Decrypt"]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com", "cloudwatch.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}
