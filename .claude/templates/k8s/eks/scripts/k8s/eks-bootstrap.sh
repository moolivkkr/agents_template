#!/bin/bash
# eks-bootstrap.sh <staging|prod> — once per cluster, by a HUMAN with cluster-admin (the EKS access entry
# Terraform gives var.admin_role_arns). Installs External Secrets Operator (pinned chart; its controller
# gets AWS access through the EKS Pod Identity association Terraform created for
# external-secrets/external-secrets) and applies deploy/k8s/eks-cluster.yaml: the app namespace (Pod
# Security "restricted"), the Auto Mode ALB IngressClass + IngressClassParams (ACM certificate), and the
# deployers' RBAC for ExternalSecrets. Idempotent. sdlc-guard refuses agents.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
case "$ENV_NAME" in staging|prod) ;; *) die "usage: eks-bootstrap.sh <staging|prod>" ;; esac
ESO_CHART_VERSION="${ESO_CHART_VERSION:-2.11.0}"   # charts.external-secrets.io index, 2026-09-21 (app v2.11.0)
eks_kube_check
command -v helm >/dev/null || die "helm not installed"
log "External Secrets Operator $ESO_CHART_VERSION -> namespace external-secrets"
helm upgrade --install external-secrets external-secrets --repo https://charts.external-secrets.io \
  --version "$ESO_CHART_VERSION" --namespace external-secrets --create-namespace \
  --set installCRDs=true --set serviceAccount.name=external-secrets --wait --timeout 5m >/dev/null
log "cluster objects for $NS"
ENV="$ENV_NAME" ACM_CERTIFICATE_ARN="$ACM_CERTIFICATE_ARN" python3 - "$K8S_DIR/eks-cluster.yaml" <<'PY' | kubectl apply -f -
import os, string, sys
print(string.Template(open(sys.argv[1]).read()).substitute(ENV=os.environ["ENV"], ACM_CERTIFICATE_ARN=os.environ["ACM_CERTIFICATE_ARN"]))
PY
log "done: deploy with scripts/k8s/deploy.sh $ENV_NAME once something is promoted (promote-eks.sh $ENV_NAME)"
