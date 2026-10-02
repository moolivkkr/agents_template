# __APP__ staging on AWS. A human (or a CI job with an admin role) runs plan/apply; agents only run fmt,
# validate and tflint (sdlc-guard asks before anything touches real state). Then:
#   scripts/k8s/eks-outputs.sh staging   -> deploy/k8s/overlays/staging/eks.env (commit it)
#   scripts/k8s/eks-bootstrap.sh staging -> External Secrets Operator + namespace + ALB IngressClass (admin, once)
provider "aws" {
  region = var.region
  default_tags {
    tags = { app = "__APP__", env = "staging" }
  }
}

module "platform" {
  source = "../../modules/platform"

  app                 = "__APP__"
  env                 = "staging"
  admin_role_arns     = var.admin_role_arns
  deployer_role_arn   = module.github_deploy.role_arn
  app_host            = var.app_host
  acm_certificate_arn = var.acm_certificate_arn
  images              = var.images
}

module "github_deploy" {
  source = "../../modules/github-oidc"

  name                 = "__APP__-staging-deploy"
  github_repository    = var.github_repository
  github_ids           = var.github_ids
  github_environment   = "staging"
  create_oidc_provider = var.create_oidc_provider
  oidc_provider_arn    = var.oidc_provider_arn
  ecr_repository_arns  = module.platform.ecr_repository_arns
  cluster_arn          = module.platform.cluster_arn
}
