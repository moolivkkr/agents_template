# __APP__ prod on AWS. A human (or a CI job with an admin role) runs plan/apply; agents only run fmt,
# validate and tflint (sdlc-guard asks before anything touches real state). Then:
#   scripts/k8s/eks-outputs.sh prod   -> deploy/k8s/overlays/prod/eks.env (commit it)
#   scripts/k8s/eks-bootstrap.sh prod -> External Secrets Operator + namespace + ALB IngressClass (admin, once)
provider "aws" {
  region = var.region
  default_tags {
    tags = { app = "__APP__", env = "prod" }
  }
}

module "platform" {
  source = "../../modules/platform"

  app                 = "__APP__"
  env                 = "prod"
  admin_role_arns     = var.admin_role_arns
  deployer_role_arn   = module.github_deploy.role_arn
  app_host            = var.app_host
  acm_certificate_arn = var.acm_certificate_arn
  images              = var.images
}

module "github_deploy" {
  source = "../../modules/github-oidc"

  name                 = "__APP__-prod-deploy"
  github_repository    = var.github_repository
  github_ids           = var.github_ids
  github_environment   = "prod"
  create_oidc_provider = var.create_oidc_provider
  oidc_provider_arn    = var.oidc_provider_arn
  ecr_repository_arns  = module.platform.ecr_repository_arns
  cluster_arn          = module.platform.cluster_arn
}
