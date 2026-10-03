# lib.sh — sourced by scripts/k8s/*.sh. Resolves the project, env, namespace and tools.
# Env model: <app>-dev is built from the working tree; <app>-qa only ever receives digests that
# passed in dev (promotion), and <app>-prod only digests that passed in qa, so what each env runs is
# byte-identical to what the env before it verified. dev, qa and prod are namespaces on the lab cluster.
# A project with deploy/k8s/overlays/prod/eks.env runs prod on Amazon EKS instead: <app>-staging (EKS)
# gets qa's digests copied into ECR, <app>-prod gets staging's (promote-eks.sh).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
K8S_DIR="$ROOT/deploy/k8s"
[ -f "$K8S_DIR/app.env" ] || { echo "no $K8S_DIR/app.env" >&2; exit 1; }
# shellcheck source=/dev/null
. "$K8S_DIR/app.env"
export PATH="$PATH:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/sdlc-lab.json}"
DL="$HERE/deploylib.py"

die() { echo "$(basename "$0"): $*" >&2; exit 1; }
log() { printf '== %s\n' "$*" >&2; }

env_setup() {  # $1 = dev|qa|prod (lab cluster namespaces) | staging, or prod with eks.env (Amazon EKS)
  ENV_NAME="${1:-}"
  # ENV_KIND: lab | eks.   PROMOTE_FROM: the env whose newest HEALTHY digests this env receives (none = built here)
  PROMOTE_FROM=""
  case "$ENV_NAME" in
    dev) ENV_KIND=lab ;;
    qa) ENV_KIND=lab; PROMOTE_FROM=dev ;;
    prod) if [ -f "$K8S_DIR/overlays/prod/eks.env" ]; then ENV_KIND=eks; else ENV_KIND=lab; PROMOTE_FROM=qa; fi ;;
    staging) [ -f "$K8S_DIR/overlays/staging/eks.env" ] || die "no deploy/k8s/overlays/staging/eks.env — instantiate the EKS layer first (instantiate.sh <project> <app> --eks)"
      ENV_KIND=eks ;;
    *) die "usage: $(basename "$0") <dev|qa|prod|staging> — got '${ENV_NAME}'" ;;
  esac
  NS="$APP-$ENV_NAME"
  OVERLAY="$K8S_DIR/overlays/$ENV_NAME"
  BASE_URL="http://$APP-$ENV_NAME.localhost:$INGRESS_PORT"
  HIST="$ROOT/agent_state/deploy/$ENV_NAME/history.jsonl"
  [ "$ENV_KIND" = eks ] && eks_setup
  [ "$ENV_NAME:$ENV_KIND" = prod:lab ] && lab_prod_setup
  return 0
}

# ── lab prod (<app>-prod on the lab cluster) ──────────────────────────────────────────────────────
# HUMAN-ONLY. The agent's ServiceAccount has no write access in <app>-prod (app-namespaces.sh binds it
# "admin" in dev/qa only) and the guard denies agents `deploy.sh prod` and any write to *-prod. A human
# deploys with the admin kubeconfig (or PROD_KUBECONFIG); the agent's kubeconfig is refused outright.
lab_prod_setup() {
  export KUBECONFIG="${PROD_KUBECONFIG:-$HOME/.kube/sdlc-lab-admin.yaml}"
  [ -f "$KUBECONFIG" ] || die "prod needs the admin kubeconfig: $KUBECONFIG not found (set PROD_KUBECONFIG)"
  local agent
  agent="$(cd "$HOME/.kube" 2>/dev/null && pwd -P)/sdlc-lab.json"
  [ "$(cd "$(dirname "$KUBECONFIG")" && pwd -P)/$(basename "$KUBECONFIG")" != "$agent" ] \
    || die "prod is never deployed with the agent kubeconfig (sdlc-lab.json); use the admin kubeconfig"
}
prod_confirm() {  # $1 = what is about to happen. CI sets CONFIRM_PROD=<app>-prod; a human types it.
  [ "${CONFIRM_PROD:-}" = "$NS" ] && return 0
  [ -t 0 ] || die "refusing to $1 without confirmation: set CONFIRM_PROD=$NS (CI) or run it from a terminal"
  local answer
  printf 'About to %s in %s. Type the namespace to confirm: ' "$1" "$NS" >&2
  read -r answer
  [ "$answer" = "$NS" ] || die "not confirmed"
}

# ── Amazon EKS (staging, prod) ────────────────────────────────────────────────────────────────────
# eks.env: non-secret coordinates from `terraform output` (scripts/k8s/eks-outputs.sh). The kubeconfig is
# NEVER defaulted for these envs: EKS_KUBECONFIG must name one (`aws eks update-kubeconfig --name
# <cluster> --kubeconfig <file>` by a human or CI), it may not be the lab's, and its current context must be
# the cluster in eks.env. The agent's lab kubeconfig can't reach EKS, and the guard refuses agents here.
eks_setup() {
  local f="$OVERLAY/eks.env"
  # shellcheck source=/dev/null
  . "$f"
  BASE_URL="https://$APP_HOST"
  if grep -vE '^[[:space:]]*(#|$)' "$f" | grep -qE '000000000000|example\.com|placeholder'; then
    EKS_PLACEHOLDERS=1
  else
    EKS_PLACEHOLDERS=0
  fi
}
eks_kube_check() {  # call before any kubectl against staging/prod
  [ "$EKS_PLACEHOLDERS" = 0 ] || die "$OVERLAY/eks.env still has placeholder values: fill it from Terraform (scripts/k8s/eks-outputs.sh $ENV_NAME)"
  [ -n "${EKS_KUBECONFIG:-}" ] || die "set EKS_KUBECONFIG to a kubeconfig for $EKS_CLUSTER_NAME (aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --region $AWS_REGION --kubeconfig <file>); the lab kubeconfig is never used for $ENV_NAME"
  local lab
  lab="$(cd "$HOME/.kube" 2>/dev/null && pwd -P)/sdlc-lab.json"
  [ "$(cd "$(dirname "$EKS_KUBECONFIG")" && pwd -P)/$(basename "$EKS_KUBECONFIG")" != "$lab" ] || die "EKS_KUBECONFIG is the lab kubeconfig"
  export KUBECONFIG="$EKS_KUBECONFIG"
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null)" || die "no current context in $EKS_KUBECONFIG"
  [ "$ctx" = "$EKS_CLUSTER_ARN" ] || die "current context is '$ctx', expected the $ENV_NAME cluster $EKS_CLUSTER_ARN (eks.env)"
  kubectl get --raw /readyz >/dev/null 2>&1 || die "EKS API for $EKS_CLUSTER_NAME not reachable (credentials expired? aws sso login)"
}

kc() { kubectl -n "$NS" "$@"; }

git_sha() { git -C "$ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo nogit; }
# The commit the gate binds evidence to: last commit touching code (same pathspec as verify-gate.sh).
CODE_EXCL=(':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays')
code_sha() { git -C "$ROOT" log -1 --format=%H -- . "${CODE_EXCL[@]}" 2>/dev/null || true; }

# The real kubectl behind sdlc-guard's PATH shim. Used ONLY by env-reset.sh for its namespaced bulk
# delete, which the shim refuses (as it should at the prompt). RBAC still confines it to this app's
# namespaces, and env-reset.sh refuses anything but <app>-dev|qa.
real_kubectl() {
  local self d IFS=:
  self="$(cd "${SDLC_GUARD_SHIMS:-$HOME/.claude/hooks/sdlc-guard-shims}" 2>/dev/null && pwd -P || true)"
  for d in $PATH; do
    [ -n "$d" ] || continue
    [ -n "$self" ] && [ "$(cd "$d" 2>/dev/null && pwd -P)" = "$self" ] && continue
    if [ -x "$d/kubectl" ]; then echo "$d/kubectl"; return 0; fi
  done
  return 1
}

# ── shared by deploy.sh (lab) and deploy-eks.sh (EKS). Callers define STEPS, DIGESTS and step(). ─────
stuck() { kc get pods ${1:+-l "$1"} -o json 2>/dev/null | python3 "$DL" stuck --digests "${DIGESTS[@]}"; }
run_job() {  # $1 cronjob template, $2 step name — fails fast on a pod that can never start
  local job="$2-$(date +%s)" i s f r
  kc create job "$job" --from="cronjob/$1" >/dev/null || { step "$2" fail; return 1; }
  for i in $(seq 1 120); do
    s="$(kc get job "$job" -o jsonpath='{.status.succeeded}')"; [ "${s:-0}" -ge 1 ] && { step "$2" ok; return 0; }
    f="$(kc get job "$job" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')"; [ "$f" = True ] && break
    r="$(stuck "job-name=$job")"; [ -n "$r" ] && { log "$r"; break; }
    sleep 2
  done
  step "$2" fail; log "$2 job failed:"; kc logs "job/$job" --tail=40 >&2 || true
  kc delete job "$job" --wait=false >/dev/null 2>&1 || true   # a never-started Job never TTLs out
  return 1
}
wait_rollout() {  # $1 deployment.apps/<name> — fails fast when a new-digest pod can never start
  local i sel r
  sel="$(kc get "$1" -o jsonpath='{.spec.selector.matchLabels.app}')"
  for i in $(seq 1 120); do
    kc rollout status "$1" --timeout=2s >/dev/null 2>&1 && return 0
    r="$(stuck "${sel:+app=$sel}")"; [ -n "$r" ] && { log "$1: $r"; return 1; }
    sleep 1
  done
  return 1
}
digest_parity() {  # every running pod of each image name runs exactly the deployed digest
  local pair name digest ids id parity=ok
  for pair in "${IMAGES[@]}"; do
    name="${pair%%=*}"; digest="${pair##*@}"
    ids="$(kc get pods -l "app=$name" --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.status.containerStatuses[*].imageID}{"\n"}{end}')"
    [ -n "$ids" ] || { parity=fail; log "no running pods for $name"; continue; }
    while IFS= read -r id; do case "$id" in *"@$digest") ;; *) parity=fail; log "pod runs $id, expected @$digest" ;; esac; done <<< "$ids"
  done
  step digest_parity "$parity"; [ "$parity" = ok ]
}
prune_generated() {  # $1 rendered.yaml — kustomize renames generated ConfigMaps/Secrets (<name>-<hash>) on
  # every content change and `apply` never deletes: remove generated objects the current render no longer references.
  local current prefixes obj base
  current="$(kc apply -f "$1" --dry-run=client -o name 2>/dev/null | grep -E '^(configmap|secret)/' || true)"
  prefixes="$(printf '%s\n' "$current" | sed -nE 's#^(configmap|secret)/(.*)-[a-z0-9]{10}$#\1/\2#p' | sort -u)"
  for obj in $(kc get configmaps,secrets -o name 2>/dev/null); do
    base="$(printf '%s' "$obj" | sed -nE 's#^(configmap|secret)/(.*)-[a-z0-9]{10}$#\1/\2#p')"
    [ -n "$base" ] || continue
    printf '%s\n' "$prefixes" | grep -qxF "$base" || continue          # not one of our generators
    printf '%s\n' "$current" | grep -qxF "$obj" && continue             # the one in use
    kc delete "$obj" --wait=false >/dev/null 2>&1 && log "removed stale $obj"
  done
}
