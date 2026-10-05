# Persistent storage for PEJIP's database (ADR-0007, design doc 0012). The
# SQLite database, the AI spend ledger and the written digests live on one
# encrypted EFS file system, mounted at /data in every PEJIP task over TLS
# through an access point that maps all access to the app's user (10001).
#
# No backups: everything here is kept for at most 90 days (policy section 10),
# and a backup would keep deleted rows for longer. EFS stores data redundantly
# across availability zones; job postings are re-fetched on the next run.

resource "aws_efs_file_system" "data" {
  #checkov:skip=CKV2_AWS_18:No backups by design; a backup would keep personal data past the 90-day retention (policy section 10)
  creation_token   = "${local.name}-data"
  encrypted        = true
  kms_key_id       = aws_kms_key.pejip.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name               = "${local.name}-data"
    DataClassification = "personal"
  }
}

# Explicitly off, so EFS's account-level automatic backups never apply here.
resource "aws_efs_backup_policy" "data" {
  file_system_id = aws_efs_file_system.data.id

  backup_policy {
    status = "DISABLED"
  }
}

resource "aws_security_group" "efs" {
  name        = "pejip-efs"
  description = "PEJIP data file system: NFS only from PEJIP tasks"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "pejip-efs"
  }
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_tasks" {
  security_group_id            = aws_security_group.efs.id
  description                  = "NFS from PEJIP tasks"
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_vpc_security_group_egress_rule" "tasks_to_efs" {
  security_group_id            = aws_security_group.tasks.id
  description                  = "NFS to the PEJIP data file system"
  referenced_security_group_id = aws_security_group.efs.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_efs_mount_target" "data" {
  count = length(aws_subnet.public)

  file_system_id  = aws_efs_file_system.data.id
  subnet_id       = aws_subnet.public[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# Every mount sees /pejip as its root and acts as the app user, whatever the
# client asks for, so files are created 0700 and owned by 10001.
resource "aws_efs_access_point" "data" {
  file_system_id = aws_efs_file_system.data.id

  posix_user {
    uid = 10001
    gid = 10001
  }

  root_directory {
    path = "/pejip"

    creation_info {
      owner_uid   = 10001
      owner_gid   = 10001
      permissions = "0700"
    }
  }

  tags = {
    Name = "${local.name}-data"
  }
}

data "aws_iam_policy_document" "efs" {
  # Only the app's task role may mount, only through the access point.
  statement {
    sid       = "PejipTasksThroughAccessPoint"
    actions   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
    resources = [aws_efs_file_system.data.arn]

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.ecs_task.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values   = [aws_efs_access_point.data.arn]
    }
  }

  statement {
    sid       = "TlsOnly"
    effect    = "Deny"
    actions   = ["*"]
    resources = [aws_efs_file_system.data.arn]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_efs_file_system_policy" "data" {
  file_system_id = aws_efs_file_system.data.id
  policy         = data.aws_iam_policy_document.efs.json
}
