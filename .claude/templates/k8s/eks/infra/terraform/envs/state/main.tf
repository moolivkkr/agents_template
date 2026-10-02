# Remote-state bucket for envs/staging and envs/prod — applied ONCE per account by a human, with LOCAL
# state (this root only creates the bucket the others keep their state in). Versioned, encrypted,
# private, TLS-only. Locking needs no DynamoDB table: the S3 backend's use_lockfile writes a lock object
# next to the state (developer.hashicorp.com/terraform/language/backend/s3; DynamoDB locking is deprecated).
terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.0, < 7.0" }
  }
}

variable "region" {
  description = "Region of the bucket (the backend blocks in envs/*/backend.tf must match)."
  type        = string
  default     = "us-east-1"
}

variable "bucket" {
  description = "Globally unique bucket name; envs/*/backend.tf use it."
  type        = string
  default     = "__APP__-terraform-state"
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "state" {
  bucket = var.bucket
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.tls_only.json
}

output "bucket" {
  description = "Put this in envs/*/backend.tf."
  value       = aws_s3_bucket.state.bucket
}
