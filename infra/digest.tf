# Digest email (design docs 0012 and 0016). `pejip run` publishes each
# account's digest to that account's own topic and SNS emails it, as plain
# text, to that account's address only. Encrypted with the PEJIP key; only the
# app's task role may publish (ecs.tf). Babu's topic keeps its old name, so his
# confirmed subscription carries over.
resource "aws_sns_topic" "digest" {
  for_each          = toset(local.account_ids)
  name              = each.key == local.owner_account ? "pejip-digest" : "pejip-digest-${each.key}"
  kms_master_key_id = aws_kms_key.pejip.arn

  tags = {
    DataClassification = "personal"
  }
}

# AWS emails a confirmation link; nothing is delivered until it is clicked.
resource "aws_sns_topic_subscription" "digest_email" {
  for_each  = toset(local.account_ids)
  topic_arn = aws_sns_topic.digest[each.key].arn
  protocol  = "email"
  endpoint  = each.key == local.owner_account ? var.alert_email : local.sign_in_accounts[each.key]
}

moved {
  from = aws_sns_topic.digest
  to   = aws_sns_topic.digest["babu"]
}

moved {
  from = aws_sns_topic_subscription.digest_email
  to   = aws_sns_topic_subscription.digest_email["babu"]
}
