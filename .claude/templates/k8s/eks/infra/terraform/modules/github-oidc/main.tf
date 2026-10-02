# GitHub Actions -> AWS with OIDC: short-lived credentials per job, no stored access keys
# (docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
# The trust is pinned to ONE repository AND one GitHub Environment, so only a job declared with
# `environment: <env>` — for prod, one a required reviewer approved — can assume the role.
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # No thumbprint_list: IAM validates GitHub's certificate against its trusted CAs; a thumbprint is no
  # longer required (docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html).
}

locals {
  provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.oidc_provider_arn
  owner        = split("/", var.github_repository)[0]
  repo         = split("/", var.github_repository)[1]
  subjects = compact([
    "repo:${var.github_repository}:environment:${var.github_environment}",
    var.github_ids == null ? "" : "repo:${local.owner}@${var.github_ids.owner_id}/${local.repo}@${var.github_ids.repo_id}:environment:${var.github_environment}",
  ])
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals" # exact match: no wildcard branch/ref can slip in
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.subjects
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = var.name
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this action has no resource-level scoping
  }
  statement {
    sid = "EcrReadTagCopy"
    actions = [
      "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability", "ecr:DescribeImages",
      "ecr:PutImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
    ]
    resources = var.ecr_repository_arns
  }
  statement {
    sid       = "Kubeconfig"
    actions   = ["eks:DescribeCluster"]
    resources = [var.cluster_arn]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${var.name}-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
