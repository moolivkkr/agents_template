#!/bin/bash
# app-namespaces.sh — create a project's environments on the sdlc lab cluster. HUMAN-RUN (admin
# kubeconfig), once per project; idempotent.
#
#   .claude/templates/k8s/scripts/app-namespaces.sh <app> [env ...]     (default envs: dev qa)
#
# For each env it creates namespace <app>-<env> with:
#   - labels  sdlc.io/app=<app>  sdlc.io/env=<env>
#   - RoleBinding  ClusterRole "admin" -> ServiceAccount sdlc-system/sdlc-agent  (agents deploy here, and
#     only here; "admin" cannot edit the ResourceQuota or delete the namespace)
#   - ResourceQuota + LimitRange  (no NodePort/LoadBalancer Services: traffic enters via the ingress)
#   - NetworkPolicy  ingress only from the same namespace and from kube-system (Traefik), so dev and qa
#     of one app, and different apps, cannot reach each other
# Ingress host convention: <app>-<env>.localhost  ->  http://<app>-<env>.localhost:18080 on the dev Mac.
set -euo pipefail
APP="${1:?usage: $0 <app> [env ...]}"; shift
ENVS=("$@"); [ "${#ENVS[@]}" -gt 0 ] || ENVS=(dev qa)
ADMIN_KC="${ADMIN_KC:-$HOME/.kube/sdlc-lab-admin.yaml}"
CPU="${QUOTA_CPU:-4}"; MEM="${QUOTA_MEMORY:-8Gi}"; STORAGE="${QUOTA_STORAGE:-20Gi}"
export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

[[ "$APP" =~ ^[a-z][a-z0-9-]{0,40}[a-z0-9]$ ]] || { echo "app name must be a DNS label (a-z, 0-9, -)" >&2; exit 1; }
if [[ "$APP" =~ (^|-)(prod|production|prd|live)(-|$) ]]; then echo "refusing a prod-looking app name: $APP" >&2; exit 1; fi

for ENV in "${ENVS[@]}"; do
  case "$ENV" in
    dev|qa) ;;
    test|e2e|perf|demo) echo "note: agents can write $APP-$ENV only if the guard policy allows it (make-policy --namespaces '*-dev,*-qa,*-$ENV')" >&2 ;;
    *) echo "env '$ENV' is not a recognised non-prod env (dev qa test e2e perf demo)" >&2; exit 1 ;;
  esac
  NS="$APP-$ENV"
  cat <<EOF | kubectl --kubeconfig "$ADMIN_KC" apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: $NS
  labels: {sdlc.io/app: $APP, sdlc.io/env: $ENV}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: sdlc-agent-admin, namespace: $NS}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: admin}
subjects: [{kind: ServiceAccount, name: sdlc-agent, namespace: sdlc-system}]
---
apiVersion: v1
kind: ResourceQuota
metadata: {name: env-quota, namespace: $NS}
spec:
  hard:
    requests.cpu: "$CPU"
    limits.memory: $MEM
    requests.storage: $STORAGE
    persistentvolumeclaims: "5"
    pods: "40"
    services.nodeports: "0"
    services.loadbalancers: "0"
---
apiVersion: v1
kind: LimitRange
metadata: {name: env-defaults, namespace: $NS}
spec:
  limits:
  - type: Container
    defaultRequest: {cpu: 50m, memory: 64Mi}
    default: {cpu: "1", memory: 512Mi}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: env-isolation, namespace: $NS}
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
  - from:
    - podSelector: {}
    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
EOF
done
echo "✅ ${ENVS[*]/#/$APP-} ready. Agents deploy with KUBECONFIG=~/.kube/sdlc-lab.json and -n $APP-<env>."
