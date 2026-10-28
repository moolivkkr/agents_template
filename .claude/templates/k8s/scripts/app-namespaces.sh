#!/bin/bash
# app-namespaces.sh — create a project's environments on the sdlc lab cluster. HUMAN-RUN (admin
# kubeconfig), once per project; idempotent.
#
#   .claude/templates/k8s/scripts/app-namespaces.sh <app> [env ...]     (default envs: dev qa prod)
#
# For each env it creates namespace <app>-<env> with:
#   - labels  sdlc.io/app=<app>  sdlc.io/env=<env>
#   - dev/qa (and test/e2e/perf/demo): RoleBinding  ClusterRole "admin" -> ServiceAccount
#     sdlc-system/sdlc-agent  (agents deploy here, and only here; "admin" cannot edit the ResourceQuota
#     or delete the namespace)
#   - prod: NO agent RoleBinding. The agent keeps only its cluster-wide "view" (no Secrets), so it can
#     read prod's state but never change it; a human deploys prod with the admin kubeconfig. Any
#     sdlc-agent-admin binding left in a prod namespace is deleted. Quota: PROD_QUOTA_* (default 2x).
#   - ResourceQuota + LimitRange  (no NodePort/LoadBalancer Services: traffic enters via the ingress)
#   - NetworkPolicy  ingress only from the same namespace and from kube-system (Traefik), so dev and qa
#     of one app, and different apps, cannot reach each other. In tailnet mode (cluster-up.sh writes
#     ConfigMap sdlc-system/lab-network) the lab Macs' tailnet IPs are allowed too, so every lab Mac
#     reaches pod IPs directly; other tailnet devices and other namespaces still cannot.
# Ingress host convention: <app>-<env>.localhost  ->  http://<app>-<env>.localhost:18080 on the dev Mac.
set -euo pipefail
APP="${1:?usage: $0 <app> [env ...]}"; shift
ENVS=("$@"); [ "${#ENVS[@]}" -gt 0 ] || ENVS=(dev qa prod)
ADMIN_KC="${ADMIN_KC:-$HOME/.kube/sdlc-lab-admin.yaml}"
CPU="${QUOTA_CPU:-4}"; MEM="${QUOTA_MEMORY:-8Gi}"; STORAGE="${QUOTA_STORAGE:-20Gi}"
P_CPU="${PROD_QUOTA_CPU:-8}"; P_MEM="${PROD_QUOTA_MEMORY:-16Gi}"; P_STORAGE="${PROD_QUOTA_STORAGE:-40Gi}"
export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
LAB_FROM=""   # extra NetworkPolicy peers: one ipBlock per lab Mac (tailnet mode only)
# mac-ips: a lab Mac -> pod IP arrives with the Mac's own tailnet IP. node-ips: a lab Mac -> ClusterIP
# (Postgres, any Service) is masqueraded by kube-proxy to the node that routed it. Pod -> pod and
# pod -> Service keep the pod's own IP, so other namespaces stay refused.
for ip in $("${KUBECTL:-kubectl}" --kubeconfig "$ADMIN_KC" -n sdlc-system get configmap lab-network -o jsonpath='{.data.mac-ips} {.data.node-ips}' 2>/dev/null); do
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "lab-network: bad mac-ips entry '$ip'" >&2; exit 1; }
  LAB_FROM="$LAB_FROM
    - ipBlock: {cidr: $ip/32}"
done

[[ "$APP" =~ ^[a-z][a-z0-9-]{0,40}[a-z0-9]$ ]] || { echo "app name must be a DNS label (a-z, 0-9, -)" >&2; exit 1; }
if [[ "$APP" =~ (^|-)(prod|production|prd|live)(-|$) ]]; then echo "refusing a prod-looking app name: $APP" >&2; exit 1; fi

for ENV in "${ENVS[@]}"; do
  case "$ENV" in
    dev|qa|prod) ;;
    test|e2e|perf|demo) echo "note: agents can write $APP-$ENV only if the guard policy allows it (make-policy --namespaces '*-dev,*-qa,*-$ENV')" >&2 ;;
    *) echo "env '$ENV' is not a recognised env (dev qa prod, or non-prod test e2e perf demo)" >&2; exit 1 ;;
  esac
  NS="$APP-$ENV"
  QCPU="$CPU"; QMEM="$MEM"; QSTORAGE="$STORAGE"
  if [ "$ENV" = prod ]; then
    QCPU="$P_CPU"; QMEM="$P_MEM"; QSTORAGE="$P_STORAGE"
    AGENT_BINDING=""
  else
    AGENT_BINDING="---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: sdlc-agent-admin, namespace: $NS}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: admin}
subjects: [{kind: ServiceAccount, name: sdlc-agent, namespace: sdlc-system}]"
  fi
  cat <<EOF | "${KUBECTL:-kubectl}" --kubeconfig "$ADMIN_KC" apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: $NS
  labels: {sdlc.io/app: $APP, sdlc.io/env: $ENV}
$AGENT_BINDING
---
apiVersion: v1
kind: ResourceQuota
metadata: {name: env-quota, namespace: $NS}
spec:
  hard:
    requests.cpu: "$QCPU"
    limits.memory: $QMEM
    requests.storage: $QSTORAGE
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
    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}$LAB_FROM
EOF
  if [ "$ENV" = prod ]; then
    # never leave agents write access to prod, whatever an earlier run or a hand edit created
    "${KUBECTL:-kubectl}" --kubeconfig "$ADMIN_KC" -n "$NS" delete rolebinding sdlc-agent-admin --ignore-not-found >/dev/null
    if "${KUBECTL:-kubectl}" --kubeconfig "$ADMIN_KC" auth can-i create deployments -n "$NS" --as=system:serviceaccount:sdlc-system:sdlc-agent >/dev/null 2>&1; then
      echo "✗ sdlc-agent can still write $NS — check other RoleBindings/ClusterRoleBindings" >&2; exit 1
    fi
  fi
done
echo "✅ ${ENVS[*]/#/$APP-} ready. Agents deploy dev/qa with KUBECONFIG=~/.kube/sdlc-lab.json and -n $APP-<env>;"
echo "   prod is read-only to agents: a human runs  scripts/k8s/deploy.sh prod  (admin kubeconfig)."
