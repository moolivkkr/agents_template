variable "name" {
  description = "Role name, e.g. <app>-<env>-deploy."
  type        = string
}

variable "github_repository" {
  description = "owner/repo whose workflows may assume the role."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be owner/repo."
  }
}

variable "github_ids" {
  description = "Numeric owner and repository ids (gh api repos/OWNER/REPO --jq '.owner.id, .id'). Set them: repositories created or renamed after 2026-07-15 send the immutable subject repo:OWNER@OWNER_ID/REPO@REPO_ID:... (github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/)."
  type        = object({ owner_id = string, repo_id = string })
  default     = null
}

variable "github_environment" {
  description = "GitHub Environment the deploy job runs in (staging or prod). Only jobs in that environment get the role; protect prod with required reviewers."
  type        = string
}

variable "create_oidc_provider" {
  description = "Create the account's token.actions.githubusercontent.com OIDC provider (exactly one per account: false in the second environment of a shared account, and pass oidc_provider_arn)."
  type        = bool
  default     = true
}

variable "oidc_provider_arn" {
  description = "Existing GitHub OIDC provider ARN when create_oidc_provider is false."
  type        = string
  default     = null
}

variable "ecr_repository_arns" {
  description = "Repositories the deploy reads (digest check) and tags (<env>-healthy-<sha>); promote-eks.sh prod also copies into them."
  type        = list(string)
}

variable "cluster_arn" {
  description = "EKS cluster the role may describe (aws eks update-kubeconfig). Kubernetes rights come from its access entry."
  type        = string
}

variable "tags" {
  description = "Tags for the role."
  type        = map(string)
  default     = {}
}
