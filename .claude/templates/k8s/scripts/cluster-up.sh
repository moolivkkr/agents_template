#!/bin/bash
# cluster-up.sh — build (or resume) the sdlc lab cluster: k3s in Lima on one or two Macs.
#
# HUMAN-RUN, once per machine pair. It creates VMs, reads the admin kubeconfig and writes the agent
# kubeconfig and guard policy — all things the permission guard denies to agents on purpose.
# Idempotent: re-running resumes/repairs instead of recreating.
#
#   SERVER_SSH=tb2 SERVER_IP=10.10.10.20 AGENT_IP=10.10.10.30 .claude/templates/k8s/scripts/cluster-up.sh
#
#   SERVER_SSH  ssh host of the Mac that runs the k3s server VM ("" = this Mac runs it)
#   SERVER_IP   the server Mac's Thunderbolt/LAN address the agent joins through
#   AGENT_IP    this Mac's address on the same link ("" = single node, no agent VM here)
#
# Outputs (this Mac):
#   ~/.kube/sdlc-lab-admin.yaml         cluster-admin — for this script and app-namespaces.sh only
#   ~/.kube/sdlc-lab.json               agent kubeconfig (ServiceAccount sdlc-agent, token) — agents use this
#   ~/.config/sdlc-guard/policy.json    guard policy pinning that kubeconfig's server + CA
set -euo pipefail

SERVER_SSH="${SERVER_SSH-}"
SERVER_IP="${SERVER_IP:-10.10.10.20}"
AGENT_IP="${AGENT_IP-10.10.10.30}"
SERVER_NODE_IP="${SERVER_NODE_IP:-172.30.10.2}"
AGENT_NODE_IP="${AGENT_NODE_IP:-172.30.10.3}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S="$(cd "$HERE/.." && pwd)"
ADMIN_KC="$HOME/.kube/sdlc-lab-admin.yaml"
AGENT_KC="$HOME/.kube/sdlc-lab.json"
POLICY="${SDLC_GUARD_POLICY:-$HOME/.config/sdlc-guard/policy.json}"
export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'cluster-up: %s\n' "$*" >&2; exit 1; }
on_server() {   # run a command on the server Mac (local when SERVER_SSH is empty)
  if [ -n "$SERVER_SSH" ]; then ssh -o BatchMode=yes "$SERVER_SSH" "export PATH=/opt/homebrew/bin:\$PATH; $*"; else bash -c "$*"; fi
}
instance_status() { limactl list "$1" --format '{{.Status}}' 2>/dev/null || true; }
server_status() { on_server "limactl list sdlc-server --format '{{.Status}}' 2>/dev/null || true"; }

for t in limactl kubectl python3; do command -v "$t" >/dev/null || die "$t not found"; done
KC=(kubectl --kubeconfig "$ADMIN_KC")

# ── 1. server VM ────────────────────────────────────────────────────────────────────────────────
say "k3s server VM (sdlc-server) on ${SERVER_SSH:-this Mac}"
case "$(server_status)" in
  Running) echo "already running" ;;
  Stopped) on_server "limactl start --tty=false sdlc-server" ;;
  *)
    if [ -n "$SERVER_SSH" ]; then
      scp -q "$K8S/lima/sdlc-server.yaml" "$SERVER_SSH:/tmp/sdlc-server.yaml"; TPL=/tmp/sdlc-server.yaml
    else TPL="$K8S/lima/sdlc-server.yaml"; fi
    on_server "limactl create --tty=false --name sdlc-server \
      --set '.param.externalIP=\"$SERVER_IP\" | .param.nodeIP=\"$SERVER_NODE_IP\"' \
      --set '(.portForwards[] | select(.hostIP == \"10.10.10.20\") | .hostIP) = \"$SERVER_IP\"' $TPL \
      && limactl start --tty=false sdlc-server" ;;
esac

# ── 2. admin kubeconfig + join token ────────────────────────────────────────────────────────────
say "admin kubeconfig -> $ADMIN_KC"
mkdir -p "$HOME/.kube"; umask 077
on_server "limactl shell sdlc-server sudo cat /etc/rancher/k3s/k3s.yaml" \
  | sed -e "s#https://127.0.0.1:6443#https://$SERVER_IP:6443#" -e 's#: default$#: sdlc-lab-admin#' > "$ADMIN_KC.tmp"
mv "$ADMIN_KC.tmp" "$ADMIN_KC"; chmod 600 "$ADMIN_KC"
"${KC[@]}" get --raw /readyz >/dev/null || die "API https://$SERVER_IP:6443 not reachable from this Mac"
TOKEN="$(on_server "limactl shell sdlc-server sudo cat /var/lib/rancher/k3s/server/node-token")"
[ -n "$TOKEN" ] || die "could not read the join token"

# ── 3. agent VM on this Mac ─────────────────────────────────────────────────────────────────────
NODES=1
if [ -n "$AGENT_IP" ]; then
  NODES=2
  say "k3s agent VM (sdlc-agent) on this Mac"
  case "$(instance_status sdlc-agent)" in
    Running) echo "already running" ;;
    Stopped) limactl start --tty=false sdlc-agent ;;
    *)
      limactl create --tty=false --name sdlc-agent \
        --set ".param.serverURL=\"https://$SERVER_IP:6443\" | .param.token=\"$TOKEN\" | .param.externalIP=\"$AGENT_IP\" | .param.nodeIP=\"$AGENT_NODE_IP\"" \
        --set "(.portForwards[] | select(.hostIP == \"10.10.10.30\") | .hostIP) = \"$AGENT_IP\"" \
        "$K8S/lima/sdlc-agent.yaml"
      limactl start --tty=false sdlc-agent ;;
  esac
fi
unset TOKEN

say "waiting for $NODES Ready node(s)"
for _ in $(seq 1 60); do
  READY="$("${KC[@]}" get nodes --no-headers 2>/dev/null | awk '$2=="Ready"' | wc -l | tr -d ' ')"
  [ "$READY" -ge "$NODES" ] && break; sleep 5
done
"${KC[@]}" get nodes -o wide
[ "${READY:-0}" -ge "$NODES" ] || die "only ${READY:-0}/$NODES nodes Ready"

# ── 4. registry + agent identity ────────────────────────────────────────────────────────────────
say "registry (NodePort 30501) + sdlc-agent ServiceAccount"
"${KC[@]}" apply -f "$K8S/cluster/registry.yaml" -f "$K8S/cluster/rbac.yaml" -f "$K8S/cluster/traefik-config.yaml"
"${KC[@]}" -n sdlc-system rollout status deploy/registry --timeout=300s

say "agent kubeconfig -> $AGENT_KC"
for _ in $(seq 1 30); do
  SA_TOKEN="$("${KC[@]}" -n sdlc-system get secret sdlc-agent-token -o jsonpath='{.data.token}' 2>/dev/null | base64 -d)"
  [ -n "$SA_TOKEN" ] && break; sleep 2
done
[ -n "${SA_TOKEN:-}" ] || die "ServiceAccount token was not issued"
CA="$("${KC[@]}" config view --raw --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')"
SA_TOKEN="$SA_TOKEN" CA="$CA" SERVER="https://$SERVER_IP:6443" OUT="$AGENT_KC" python3 - <<'PY'
import json, os
cfg = {"apiVersion": "v1", "kind": "Config", "current-context": "sdlc-lab",
       "clusters": [{"name": "sdlc-lab", "cluster": {"server": os.environ["SERVER"],
                     "certificate-authority-data": os.environ["CA"]}}],
       "contexts": [{"name": "sdlc-lab", "context": {"cluster": "sdlc-lab", "user": "sdlc-agent"}}],
       "users": [{"name": "sdlc-agent", "user": {"token": os.environ["SA_TOKEN"]}}]}
fd = os.open(os.environ["OUT"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(cfg, f, indent=1)
PY
unset SA_TOKEN
kubectl --kubeconfig "$AGENT_KC" auth can-i create namespaces >/dev/null 2>&1 \
  && die "agent kubeconfig can create namespaces — RBAC is too broad" || echo "agent identity: read-only cluster-wide (as intended)"

# ── 5. guard policy ─────────────────────────────────────────────────────────────────────────────
say "guard policy -> $POLICY"
MP="$HOME/.claude/hooks/sdlc-guard-make-policy.py"
[ -f "$MP" ] || MP="$(cd "$K8S/../.." && pwd)/guard/make-policy.py"
[ -f "$MP" ] || die "make-policy.py not found (run ./install.sh --guard)"
LIMA_ARGS=(); [ -n "$AGENT_IP" ] && LIMA_ARGS+=(--lima-instance sdlc-agent); [ -z "$SERVER_SSH" ] && LIMA_ARGS+=(--lima-instance sdlc-server)
HOST_ARGS=(--lab-host "$SERVER_IP"); [ -n "$AGENT_IP" ] && HOST_ARGS+=(--lab-host "$AGENT_IP")
python3 "$MP" --kubeconfig "$AGENT_KC" --pin "$AGENT_KC" --namespaces '*-dev,*-qa' \
  ${LIMA_ARGS[@]+"${LIMA_ARGS[@]}"} "${HOST_ARGS[@]}" --out "$POLICY"   # (empty-array safe on bash 3.2)

say "done"
echo "Next: per project, create its namespaces:  $HERE/app-namespaces.sh <app>"
echo "Verify the cluster end to end:              $HERE/cluster-check.sh"
