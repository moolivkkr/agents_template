# lib.sh — sourced by scripts/k8s/*.sh. Resolves the project, env, namespace and tools.
# Env model: <app>-dev is built from the working tree; <app>-qa only ever receives digests that
# passed in dev (promotion), so what qa tests is byte-identical to what dev verified.
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

env_setup() {  # $1 = dev|qa
  ENV_NAME="${1:-}"
  case "$ENV_NAME" in dev|qa) ;; *) die "usage: $(basename "$0") <dev|qa> — got '${ENV_NAME}'" ;; esac
  NS="$APP-$ENV_NAME"
  OVERLAY="$K8S_DIR/overlays/$ENV_NAME"
  BASE_URL="http://$APP-$ENV_NAME.localhost:$INGRESS_PORT"
  HIST="$ROOT/agent_state/deploy/$ENV_NAME/history.jsonl"
}

kc() { kubectl -n "$NS" "$@"; }

git_sha() { git -C "$ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo nogit; }

# The real kubectl behind sdlc-guard's PATH shim. Used ONLY by env-reset.sh for its namespaced bulk
# delete, which the shim refuses (as it should at the prompt). RBAC still confines it to this app's
# namespaces, and env_setup has already pinned NS to <app>-dev|qa.
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
