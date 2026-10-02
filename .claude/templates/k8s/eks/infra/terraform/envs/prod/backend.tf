# Remote state, one key per environment, S3-native locking (use_lockfile: Terraform 1.11+). The bucket
# comes from envs/state (apply that once first). Backend blocks can't use variables: edit these three
# values when the bucket or region differ.
terraform {
  backend "s3" {
    bucket       = "__APP__-terraform-state"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
