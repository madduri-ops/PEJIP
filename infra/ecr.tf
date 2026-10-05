resource "aws_ecr_repository" "app" {
  name                 = "pejip"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.pejip.arn
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  # Release images (tagged vX.Y.Z alongside their commit SHA) match the first
  # rule, so the keep-10 rule can't expire them and any release can be rolled
  # back to. ECR never applies a lower-priority rule to an image a higher one
  # matched.
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 100 release images (v tags)"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 100
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last 10 other images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
