output "eks_env" {
  description = "Read by scripts/k8s/eks-outputs.sh into deploy/k8s/overlays/<env>/eks.env."
  value       = module.platform.eks_env
}

output "deploy_role_arn" {
  description = "GitHub Environment variable AWS_DEPLOY_ROLE_ARN for this environment."
  value       = module.github_deploy.role_arn
}
