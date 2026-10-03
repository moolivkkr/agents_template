#!/bin/bash
# seed.sh <dev|qa|prod|staging> — (re)load static/reference data into <app>-<env> by running the digest-pinned
# db-seed Job template. Idempotent by contract (the app's seed command must upsert), so it is safe to
# run at any time; deploy.sh runs it on every deploy and env-reset.sh after a wipe.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
[ "$ENV_KIND" = eks ] && eks_kube_check   # EKS: human or CI only, explicit EKS_KUBECONFIG
[ "$ENV_NAME" = prod ] && prod_confirm "re-run the seed"   # lab prod: human only, admin kubeconfig
JOB="seed-$(date +%s)"
kc create job "$JOB" --from=cronjob/db-seed >/dev/null
if kc wait --for=condition=complete "job/$JOB" --timeout=240s >/dev/null 2>&1; then
  log "$NS: seed complete ($JOB)"
else
  kc logs "job/$JOB" --tail=40 >&2 || true; die "$NS: seed failed ($JOB)"
fi
