variable "region" {
  description = "AWS region of this environment."
  type        = string
  default     = "us-east-1"
}

variable "admin_role_arns" {
  description = "IAM roles (SSO permission-set roles) of the cluster's human administrators."
  type        = list(string)
}

variable "app_host" {
  description = "Public hostname."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ACM certificate for app_host, in var.region."
  type        = string
}

variable "images" {
  description = "Image names from deploy/k8s/images.txt."
  type        = list(string)
  default     = ["api"]
}

variable "github_repository" {
  description = "owner/repo of the app."
  type        = string
}

variable "github_ids" {
  description = "Numeric owner/repo ids for GitHub's immutable OIDC subject (see modules/github-oidc)."
  type        = object({ owner_id = string, repo_id = string })
  default     = null
}

variable "create_oidc_provider" {
  description = "false when another environment in the same account already created the GitHub OIDC provider."
  type        = bool
  default     = true
}

variable "oidc_provider_arn" {
  description = "Existing provider ARN when create_oidc_provider is false."
  type        = string
  default     = null
}
