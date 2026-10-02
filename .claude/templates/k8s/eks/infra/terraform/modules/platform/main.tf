# One environment of the app on AWS: VPC (3 AZs), EKS Auto Mode cluster, ECR repositories, RDS for
# PostgreSQL with a Secrets Manager-managed master password, the migrator/app role secrets (write-only),
# and EKS Pod Identity for External Secrets Operator. Choices and sources: skill infrastructure/eks.md.
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  name      = "${var.app}-${var.env}"
  namespace = "${var.app}-${var.env}"
  prod      = var.env == "prod"
  azs       = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  tags      = merge({ app = var.app, env = var.env, "managed-by" = "terraform" }, var.tags)
  db_users  = { migrator = "app_migrator", app = "app_runtime" } # = deploylib.py DB_ROLES
}

# ── network ───────────────────────────────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7" # v6.7.3 on 2026-09-18

  name             = local.name
  cidr             = var.vpc_cidr
  azs              = local.azs
  private_subnets  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets   = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, 48 + i)]
  database_subnets = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, 64 + i)]

  enable_nat_gateway     = true
  single_nat_gateway     = !local.prod # prod: one NAT per AZ, so losing an AZ never cuts egress
  one_nat_gateway_per_az = local.prod

  create_database_subnet_group = true

  # EKS Auto Mode places load balancers by these tags (docs.aws.amazon.com/eks/latest/userguide/tag-subnets-auto.html)
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }

  tags = local.tags
}

# ── cluster: EKS Auto Mode ────────────────────────────────────────────────────────────────────────
# Auto Mode runs compute (Karpenter), the ALB/NLB controller, EBS CSI, the Pod Identity agent and
# network policy as AWS-managed capabilities (docs.aws.amazon.com/eks/latest/userguide/automode.html):
# nothing for us to install or patch on the nodes, and nodes are replaced at most every 21 days.
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.26" # v21.26.0 on 2026-09-23; v21 renamed cluster_* inputs (docs/UPGRADE-21.0.md)

  name               = local.name
  kubernetes_version = var.kubernetes_version

  endpoint_public_access       = length(var.endpoint_public_access_cidrs) > 0
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs
  endpoint_private_access      = true

  # Access entries only (no aws-auth ConfigMap), and nobody is admin just for having run Terraform.
  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = false

  compute_config = {
    enabled    = true
    node_pools = ["general-purpose", "system"]
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  addons = {
    # HPA needs the metrics API; metrics-server is an EKS community add-on
    # (docs.aws.amazon.com/eks/latest/userguide/community-addons.html).
    metrics-server = {}
  }

  access_entries = merge(
    { for i, arn in var.admin_role_arns : "admin-${i}" => {
      principal_arn = arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    } },
    {
      deployer = {
        principal_arn     = var.deployer_role_arn
        kubernetes_groups = ["${var.app}-deployers"] # + the ExternalSecret RBAC in eks-cluster.yaml
        policy_associations = {
          namespace_admin = {
            policy_arn   = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"
            access_scope = { type = "namespace", namespaces = [local.namespace] }
          }
        }
      }
    }
  )

  tags = local.tags
}

# ── registry ──────────────────────────────────────────────────────────────────────────────────────
# Images arrive here only by promotion (scripts/k8s/promote-eks.sh: crane copy, same digest). Tags are
# immutable: <git-sha> and <env>-healthy-<git-sha> are evidence and can never be moved to another image.
resource "aws_ecr_repository" "app" {
  for_each             = toset(var.images)
  name                 = "${var.app}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name
  # Keep every tagged image up to a generous count (rollback targets are tagged); drop untagged layers.
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "expire untagged images after 14 days"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 14 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "keep the newest 300 tagged images"
        selection    = { tagStatus = "tagged", tagPatternList = ["*"], countType = "imageCountMoreThan", countNumber = 300 }
        action       = { type = "expire" }
      },
    ]
  })
}

# ── database: RDS for PostgreSQL ──────────────────────────────────────────────────────────────────
resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "PostgreSQL from the cluster's private subnets only"
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "db" {
  for_each          = toset(module.vpc.private_subnets_cidr_blocks)
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
  description       = "pods (EKS Auto Mode nodes run in the private subnets)"
}

resource "aws_db_parameter_group" "db" {
  name   = "${local.name}-pg${var.postgres_major_version}"
  family = "postgres${var.postgres_major_version}"
  parameter {
    name  = "rds.force_ssl" # every client connects with sslmode=require (components/eks)
    value = "1"
  }
  parameter {
    name  = "password_encryption"
    value = "scram-sha-256"
  }
  parameter {
    # db-roles.sh can't switch statement logging off for its password session on RDS (no superuser):
    # keep it off here so ALTER ROLE ... PASSWORD is never written to the PostgreSQL log.
    name  = "log_statement"
    value = "none"
  }
  tags = local.tags
}

resource "aws_db_instance" "db" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = var.postgres_major_version # major only: RDS picks the default minor, auto-upgraded
  instance_class = var.db_instance_class

  db_name  = "app" # = DB_NAME in the overlay's app-config
  username = "app_admin"
  # The master password is created, stored and rotated by RDS in Secrets Manager: it never exists in
  # Terraform (docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html). ESO reads it
  # for the db-roles Job only (DB_SUPERUSER_* keys).
  manage_master_user_password = true

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_allocated_storage_gb * 5
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = local.prod
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.db.name
  publicly_accessible    = false

  backup_retention_period         = local.prod ? 14 : 7
  copy_tags_to_snapshot           = true
  deletion_protection             = local.prod
  skip_final_snapshot             = !local.prod
  final_snapshot_identifier       = local.prod ? "${local.name}-final" : null
  auto_minor_version_upgrade      = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = true

  tags = local.tags
}

# ── the two application roles' credentials ────────────────────────────────────────────────────────
# Write-only (Terraform 1.11+): the generated passwords go to Secrets Manager and never into state or
# plans. db-roles.sh (run by every deploy) creates/converges the roles with exactly these passwords.
ephemeral "random_password" "db" {
  for_each = local.db_users
  length   = 48
  special  = false # deploylib PASSWORD rule: [A-Za-z0-9._~-]{16,} (it goes into DATABASE_URL unescaped)
}

resource "aws_secretsmanager_secret" "db" {
  for_each                = local.db_users
  name                    = "${var.app}/${var.env}/db-${each.key}" # = DB_MIGRATOR_SECRET / DB_APP_SECRET
  description             = "${var.app} ${var.env}: PostgreSQL role ${each.value} (read by External Secrets Operator)"
  recovery_window_in_days = 7
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  for_each                 = local.db_users
  secret_id                = aws_secretsmanager_secret.db[each.key].id
  secret_string_wo         = jsonencode({ username = each.value, password = ephemeral.random_password.db[each.key].result })
  secret_string_wo_version = var.db_password_version
}

# ── External Secrets Operator: EKS Pod Identity, read-only on this environment's three secrets ────
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eso" {
  name               = "${local.name}-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  tags               = local.tags
}

data "aws_iam_policy_document" "eso_read" {
  statement {
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = concat(
      [aws_db_instance.db.master_user_secret[0].secret_arn],
      [for s in aws_secretsmanager_secret.db : s.arn],
    )
  }
}

resource "aws_iam_role_policy" "eso_read" {
  name   = "read-${local.name}-db-secrets"
  role   = aws_iam_role.eso.id
  policy = data.aws_iam_policy_document.eso_read.json
}

resource "aws_eks_pod_identity_association" "eso" {
  cluster_name    = module.eks.cluster_name
  namespace       = "external-secrets"
  service_account = "external-secrets" # eks-bootstrap.sh installs the chart with this name
  role_arn        = aws_iam_role.eso.arn
  tags            = local.tags
}

# ── optional AWS access for app pods (Pod Identity, one role per service account) ─────────────────
resource "aws_iam_role" "service" {
  for_each           = var.service_policies
  name               = "${local.name}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  tags               = local.tags
}

resource "aws_iam_role_policy" "service" {
  for_each = var.service_policies
  name     = "${local.name}-${each.key}"
  role     = aws_iam_role.service[each.key].id
  policy   = each.value
}

resource "aws_eks_pod_identity_association" "service" {
  for_each        = var.service_policies
  cluster_name    = module.eks.cluster_name
  namespace       = local.namespace
  service_account = each.key
  role_arn        = aws_iam_role.service[each.key].arn
  tags            = local.tags
}
