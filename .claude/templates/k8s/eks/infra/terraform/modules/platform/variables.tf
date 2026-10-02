variable "app" {
  description = "App slug (a DNS label); names every resource and the Kubernetes namespace <app>-<env>."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,40}[a-z0-9]$", var.app))
    error_message = "app must be a DNS label."
  }
}

variable "env" {
  description = "Environment: staging or prod (one cluster, VPC and database per environment)."
  type        = string
  validation {
    condition     = contains(["staging", "prod"], var.env)
    error_message = "env must be staging or prod."
  }
}

variable "kubernetes_version" {
  # EKS standard support on 2026-10-01: 1.36 (until 2027-08-02), 1.35, 1.34
  # (docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html). Upgrade one minor at a time.
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.36"
}

variable "vpc_cidr" {
  description = "VPC CIDR. Must equal VPC_CIDR in eks.env (the app NetworkPolicy admits the ALB from it)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Availability zones to span (subnets, NAT, the API's zone spread)."
  type        = number
  default     = 3
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint (IAM still authenticates every call). Narrow it to your office/VPN and CI egress when you can; [] makes the endpoint private-only (CI then needs a runner inside the VPC)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "admin_role_arns" {
  description = "IAM role ARNs of the humans who administer this cluster (cluster-admin access entries; they run eks-bootstrap.sh). No IAM user, no long-lived keys."
  type        = list(string)
}

variable "deployer_role_arn" {
  description = "IAM role CI assumes through GitHub OIDC (module github-oidc). Gets admin in the app namespace only, as Kubernetes group <app>-deployers."
  type        = string
}

variable "images" {
  description = "Image names built for the app (deploy/k8s/images.txt); one ECR repository <app>/<name> each."
  type        = list(string)
  default     = ["api"]
}

variable "app_host" {
  description = "Public hostname of the app (APP_HOST in eks.env); point its DNS at the ALB after the first deploy."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ACM certificate (in this region) covering app_host; the ALB terminates TLS with it."
  type        = string
}

variable "postgres_major_version" {
  description = "RDS for PostgreSQL major version. Keep it equal to the postgres image major the db-* Jobs use (components/eks)."
  type        = string
  default     = "17"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage_gb" {
  description = "Initial gp3 storage; autoscaling may grow it to 5x."
  type        = number
  default     = 20
}

variable "db_password_version" {
  description = "Bump to rotate the migrator and app passwords (write-only: Terraform writes new values to Secrets Manager; the next deploy's db-roles Job applies them; then restart the pods)."
  type        = number
  default     = 1
}

variable "service_policies" {
  description = "Optional AWS access for app pods: service account name in <app>-<env> -> IAM policy JSON. Each gets its own role through an EKS Pod Identity association."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Extra tags for every resource."
  type        = map(string)
  default     = {}
}
