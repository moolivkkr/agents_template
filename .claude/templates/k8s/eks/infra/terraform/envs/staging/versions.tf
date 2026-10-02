terraform {
  # 1.11+: write-only arguments (secret_string_wo) and S3-native state locking (use_lockfile).
  required_version = ">= 1.11"
  required_providers {
    # hashicorp/aws 6.x (6.67.0 on 2026-09-30); terraform-aws-modules/eks v21 requires >= 6.0.
    aws = { source = "hashicorp/aws", version = ">= 6.0, < 7.0" }
    # ephemeral "random_password": the DB passwords never enter state or plan files.
    random = { source = "hashicorp/random", version = ">= 3.7" }
  }
}
