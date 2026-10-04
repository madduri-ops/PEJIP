terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # State bucket and KMS key were created once by hand (ADR-0001, Bootstrap).
  # S3 native locking (use_lockfile) needs Terraform 1.10 or later.
  backend "s3" {
    bucket       = "pejip-tfstate-275704950192"
    key          = "pejip/prod/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    kms_key_id   = "arn:aws:kms:us-west-2:275704950192:key/fc979f49-0e8a-484b-94bc-eac21b5b5987"
    use_lockfile = true
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = {
      Project     = "PEJIP"
      Application = "pejip"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Babu"
      Repository  = "${var.github_owner}/${var.github_repo}"
    }
  }
}
