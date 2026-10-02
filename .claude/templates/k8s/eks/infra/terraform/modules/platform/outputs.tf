output "eks_env" {
  description = "Non-secret coordinates for deploy/k8s/overlays/<env>/eks.env (scripts/k8s/eks-outputs.sh)."
  value = {
    AWS_REGION           = data.aws_region.current.region
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
    EKS_CLUSTER_NAME     = module.eks.cluster_name
    EKS_CLUSTER_ARN      = module.eks.cluster_arn
    ECR_REGISTRY         = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.region}.amazonaws.com"
    APP_HOST             = var.app_host
    ACM_CERTIFICATE_ARN  = var.acm_certificate_arn
    DB_HOST              = aws_db_instance.db.address
    DB_MASTER_SECRET_ARN = aws_db_instance.db.master_user_secret[0].secret_arn
    DB_MIGRATOR_SECRET   = aws_secretsmanager_secret.db["migrator"].name
    DB_APP_SECRET        = aws_secretsmanager_secret.db["app"].name
    VPC_CIDR             = var.vpc_cidr
  }
}

output "ecr_repository_arns" {
  description = "ECR repositories (the deployer role may read and tag them)."
  value       = [for r in aws_ecr_repository.app : r.arn]
}

output "cluster_arn" {
  description = "EKS cluster ARN (the context name `aws eks update-kubeconfig` writes)."
  value       = module.eks.cluster_arn
}
