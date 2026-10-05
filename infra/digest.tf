# Digest email (design doc 0012). `pejip run` publishes each day's digest to
# this topic and SNS emails it to Babu as plain text. Encrypted with the PEJIP
# key; only the app's task role may publish (ecs.tf).
resource "aws_sns_topic" "digest" {
  name              = "pejip-digest"
  kms_master_key_id = aws_kms_key.pejip.arn

  tags = {
    DataClassification = "personal"
  }
}

# AWS emails a confirmation link; nothing is delivered until it is clicked.
resource "aws_sns_topic_subscription" "digest_email" {
  topic_arn = aws_sns_topic.digest.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
