#!/bin/bash
# eks-outputs.sh <staging|prod> — write deploy/k8s/overlays/<env>/eks.env from the Terraform outputs of
# infra/terraform/envs/<env> (`terraform output -json` reads the remote state: needs AWS credentials, so
# a human or CI runs it; sdlc-guard asks before an agent touches real state). Only non-secret values.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
case "$ENV_NAME" in staging|prod) ;; *) die "usage: eks-outputs.sh <staging|prod>" ;; esac
TF_DIR="$ROOT/infra/terraform/envs/$ENV_NAME"
[ -d "$TF_DIR" ] || die "no $TF_DIR"
terraform -chdir="$TF_DIR" output -json eks_env | python3 - "$OVERLAY/eks.env" "$ENV_NAME" <<'PY'
import json, sys
path, env = sys.argv[1], sys.argv[2]
vals = json.load(sys.stdin)
keys = ["AWS_REGION", "AWS_ACCOUNT_ID", "EKS_CLUSTER_NAME", "EKS_CLUSTER_ARN", "ECR_REGISTRY", "APP_HOST",
        "ACM_CERTIFICATE_ARN", "DB_HOST", "DB_MASTER_SECRET_ARN", "DB_MIGRATOR_SECRET", "DB_APP_SECRET", "VPC_CIDR"]
missing = [k for k in keys if not vals.get(k)]
if missing:
    sys.exit(f"eks-outputs: terraform output eks_env lacks {', '.join(missing)}")
with open(path, "w") as f:
    f.write(f"# Non-secret coordinates of the {env} environment, written by scripts/k8s/eks-outputs.sh from\n"
            f"# `terraform output -json eks_env` (infra/terraform/envs/{env}). Commit it; never put a credential here.\n")
    f.writelines(f"{k}={vals[k]}\n" for k in keys)
print(f"eks-outputs: wrote {path}", file=sys.stderr)
PY
