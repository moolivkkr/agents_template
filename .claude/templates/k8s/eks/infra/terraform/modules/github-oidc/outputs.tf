output "role_arn" {
  description = "Set as the GitHub Environment variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.deploy.arn
}

output "oidc_provider_arn" {
  description = "The GitHub OIDC provider (reuse it in the account's other environment)."
  value       = local.provider_arn
}
