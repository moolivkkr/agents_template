---
skill: terraform
description: Terraform patterns — remote state with locking, modules, workspaces vs directories, variable/output discipline, and safe plan/apply workflow
version: "1.0"
tags:
  - terraform
  - iac
  - infrastructure
  - state
  - modules
---

# Terraform patterns for reproducible infrastructure-as-code.

## Layout
```
infra/
  modules/                 # reusable, versioned building blocks
    network/  { main.tf variables.tf outputs.tf }
    service/  { main.tf variables.tf outputs.tf }
  envs/
    dev/   { main.tf backend.tf terraform.tfvars }
    prod/  { main.tf backend.tf terraform.tfvars }
```

- One directory per environment (`envs/dev`, `envs/prod`) — clearer and safer than one config driven by workspaces
- Reusable logic lives in `modules/`; env dirs are thin, wiring modules with env-specific vars
- Never hardcode env values in modules — pass everything via `variables.tf`

## Remote State + Locking
State holds real resource IDs and secrets — never commit it, always lock it.
```hcl
# backend.tf
terraform {
  required_version = ">= 1.6"
  backend "s3" {
    bucket         = "acme-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tf-locks"   # prevents concurrent apply corruption
    encrypt        = true
  }
}
```

- One state file per environment (separate `key`) — blast radius is contained
- Locking (DynamoDB / GCS / native) is mandatory for any shared/CI state
- Add `.terraform/`, `*.tfstate*`, `*.tfvars` (if they hold secrets) to `.gitignore`

## Modules
```hcl
module "api" {
  source  = "../../modules/service"
  name    = "api"
  cpu     = var.api_cpu
  image   = var.api_image
  subnets = module.network.private_subnet_ids
}
```

- Pin module and provider versions (`required_providers`, `?ref=v1.2.0` for git sources) — reproducible plans
- Expose only what callers need via `outputs.tf`; keep internals private
- Prefer `for_each` over `count` for stable addressing when creating a set of resources (avoids index-shift churn)

## Variables & Secrets
- Declare every input in `variables.tf` with `type`, `description`, and `validation` where useful
- Never put secrets in `.tfvars` committed to git — source from a secrets manager / env (`TF_VAR_*`) / `sensitive = true`
- Mark secret outputs `sensitive = true` so they don't print in plan/apply logs

## Workflow
```bash
terraform fmt -recursive && terraform validate
terraform plan -out=tf.plan          # review the plan — never apply blind
terraform apply tf.plan              # apply the exact reviewed plan
```

- Always `plan` before `apply`; in CI, apply the saved plan artifact, not a fresh plan
- Run `fmt` + `validate` (and `tflint`/`checkov` for policy) in CI on every PR
- Treat drift seriously: `plan` showing unexpected changes means someone edited infra out-of-band — reconcile, don't blindly apply

## Rules
- State is the source of truth for what exists — protect it (remote, encrypted, locked, versioned)
- Never `terraform destroy` in prod without an explicit, reviewed plan
- Idempotency is the contract: a second `apply` with no code change must show "no changes"
- Keep provider and Terraform versions pinned so CI and local produce identical plans
