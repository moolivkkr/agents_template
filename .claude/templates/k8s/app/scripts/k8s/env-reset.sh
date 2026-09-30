#!/bin/bash
# env-reset.sh <dev|qa> — wipe one environment back to empty and redeploy it: workloads, jobs,
# services, ingress, config, secrets AND database volumes are deleted; the namespace, its quota,
# RBAC and network policy (owned by the cluster bootstrap) are kept. Then:
#   dev -> deploy.sh dev --reuse   (same digests, fresh database, migrate + seed)
#   qa  -> deploy.sh qa            (re-promote the newest HEALTHY dev deploy)
# Approved for agents without asking (disposable non-prod data). It refuses anything but
# <app>-dev|qa, and the agent's RBAC confines it to this app's namespaces regardless.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
K="$(real_kubectl)" || die "kubectl not found"
[[ "$NS" =~ ^[a-z0-9-]+-(dev|qa)$ ]] || die "refusing to reset '$NS'"

log "reset $NS: deleting workloads, jobs, config, secrets and volumes (namespace kept)"
"$K" -n "$NS" delete deployments,statefulsets,cronjobs,jobs,services,ingresses,secrets --all --wait=true --timeout=180s >/dev/null
"$K" -n "$NS" delete configmaps --field-selector metadata.name!=kube-root-ca.crt --wait=true >/dev/null   # (--all + selector is an error)
"$K" -n "$NS" delete persistentvolumeclaims --all --wait=true --timeout=180s >/dev/null
rm -f "$OVERLAY/secrets.env"   # the old password died with the volume; deploy.sh makes a new one
left="$("$K" -n "$NS" get pods,pvc --no-headers 2>/dev/null | wc -l | tr -d ' ')"
[ "$left" = 0 ] || log "note: $left pod/pvc objects still terminating"

if [ "$ENV_NAME" = dev ]; then "$HERE/deploy.sh" dev --reuse; else "$HERE/deploy.sh" qa; fi
