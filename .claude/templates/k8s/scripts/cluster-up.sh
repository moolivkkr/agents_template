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
# TAILNET mode — any number of Macs on one Tailscale tailnet, every VM its own tailnet device:
#
#   TRANSPORT=tailnet SERVER_MAC=macstudio51 AGENT_MACS="macm4 studio52 studio256" \
#     TS_AUTHKEY=tskey-auth-... .claude/templates/k8s/scripts/cluster-up.sh
#
#   SERVER_MAC    tailnet name of the Mac that runs sdlc-server ("" = this Mac)
#   AGENT_MACS    tailnet names of the Macs that each run one sdlc-agent VM (this Mac may be one)
#   TS_AUTHKEY    reusable, pre-approved auth key tagged $TS_TAG (prompted for when unset; only
#                 needed while a VM still has to join). The tailnet policy must own the tag and
#                 auto-approve CLUSTER_CIDR for it (lima-k8s-lab.md "Tailnet mode").
#   TS_TAG        default tag:k8s;  CLUSTER_CIDR / SERVICE_CIDR default 10.42.0.0/16 / 10.43.0.0/16
# Remote Macs are driven over ssh (Remote Login on, keys installed: `ssh <mac> true` must work).
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
TRANSPORT="${TRANSPORT:-thunderbolt}"

if [ "$TRANSPORT" = tailnet ]; then
# ── 1–3 (tailnet). server VM, then one agent VM per Mac, each joined to the tailnet ──────────────
SERVER_MAC="${SERVER_MAC-}"; AGENT_MACS="${AGENT_MACS-}"
TS_TAG="${TS_TAG:-tag:k8s}"
CLUSTER_CIDR="${CLUSTER_CIDR:-10.42.0.0/16}"; SERVICE_CIDR="${SERVICE_CIDR:-10.43.0.0/16}"
TS_CLI="$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)"
REMOTE_TS='$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)'
ts_json() { "$TS_CLI" status --json; }
SELF_MAC="$(ts_json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].split(".")[0])')" \
  || die "Tailscale is not running on this Mac"
is_self() { [ -z "$1" ] || [ "$1" = "$SELF_MAC" ]; }
on_mac() {   # run a command on a lab Mac by tailnet name (local for this Mac); stdin is passed through
  local m="$1"; shift
  if is_self "$m"; then bash -c "$*"; else ssh -o BatchMode=yes "$m" "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH; $*"; fi
}
ts_ipv4() {  # tailnet IPv4 of a device by its tailnet name, from this Mac's view of the tailnet
  ts_json | python3 -c '
import json,sys
d=json.load(sys.stdin); want=sys.argv[1]
for p in [d["Self"]]+list((d.get("Peer") or {}).values()):
    if p["DNSName"].split(".")[0]==want:
        print(next(i for i in p["TailscaleIPs"] if ":" not in i)); break' "$1"
}
is_self "$SERVER_MAC" && SERVER_SSH="" || SERVER_SSH="$SERVER_MAC"   # on_server/server_status use it

tailnet_node() {   # <mac> <lima instance> <node name> <role>
  local m="$1" inst="$2" name="$3" role="$4" tpl="$K8S/lima/sdlc-node-tailnet.yaml"
  say "k3s $role VM ($inst -> node $name) on ${m:-$SELF_MAC}"
  on_mac "$m" "for b in limactl ssh; do command -v \$b >/dev/null || { echo \"\$b missing\" >&2; exit 1; }; done; $REMOTE_TS set --accept-routes" \
    || die "$m: needs Lima (brew install lima) and Tailscale; accept-routes could not be set"
  case "$(on_mac "$m" "limactl list $inst --format '{{.Status}}' 2>/dev/null || true")" in
    Running) echo "already running" ;;
    Stopped) on_mac "$m" "limactl start --tty=false $inst" ;;
    *)
      if ! is_self "$m"; then scp -q "$tpl" "$m:/tmp/sdlc-node-tailnet.yaml"; tpl=/tmp/sdlc-node-tailnet.yaml; fi
      on_mac "$m" "limactl create --tty=false --name $inst $tpl && limactl start --tty=false $inst" ;;
  esac
  if [ -z "${TS_AUTHKEY:-}" ] && ! on_mac "$m" "limactl shell $inst tailscale status >/dev/null 2>&1"; then
    read -rsp "Tailscale auth key ($TS_TAG, reusable, pre-approved): " TS_AUTHKEY; echo
  fi
  # secrets travel on stdin, never in argv
  { printf 'export ROLE=%q NODE_NAME=%q TS_AUTHKEY=%q TS_TAG=%q K3S_TOKEN=%q SERVER_URL=%q CLUSTER_CIDR=%q SERVICE_CIDR=%q\n' \
      "$role" "$name" "${TS_AUTHKEY:-}" "$TS_TAG" "${TOKEN:-}" "${SERVER_URL:-}" "$CLUSTER_CIDR" "$SERVICE_CIDR"
    cat "$HERE/tailnet-join.sh"
  } | on_mac "$m" "limactl shell $inst sudo bash -s" || die "$name: tailnet-join failed"
}

tailnet_node "$SERVER_MAC" sdlc-server sdlc-server server
for _ in $(seq 1 60); do on_server "limactl shell sdlc-server sudo test -s /var/lib/rancher/k3s/server/node-token" && break; sleep 5; done
SERVER_IP="$(on_server "limactl shell sdlc-server tailscale ip -4")"
[ -n "$SERVER_IP" ] || die "could not read sdlc-server's tailnet IP"
SERVER_URL="https://$SERVER_IP:6443"

say "admin kubeconfig -> $ADMIN_KC"
mkdir -p "$HOME/.kube"; umask 077
for _ in $(seq 1 30); do on_server "limactl shell sdlc-server sudo test -s /etc/rancher/k3s/k3s.yaml" && break; sleep 5; done
on_server "limactl shell sdlc-server sudo cat /etc/rancher/k3s/k3s.yaml" \
  | sed -e "s#https://127.0.0.1:6443#$SERVER_URL#" -e 's#: default$#: sdlc-lab-admin#' > "$ADMIN_KC.tmp"
mv "$ADMIN_KC.tmp" "$ADMIN_KC"; chmod 600 "$ADMIN_KC"
"${KC[@]}" get --raw /readyz >/dev/null || die "API $SERVER_URL not reachable from this Mac (is this Mac on the tailnet?)"
TOKEN="$(on_server "limactl shell sdlc-server sudo cat /var/lib/rancher/k3s/server/node-token")"
[ -n "$TOKEN" ] || die "could not read the join token"

NODES=1
for m in $AGENT_MACS; do
  [ "$m" = "${SERVER_MAC:-$SELF_MAC}" ] && die "$m runs sdlc-server; list it in SERVER_MAC only"
  NODES=$((NODES+1)); tailnet_node "$m" sdlc-agent "sdlc-agent-$m" agent
done
unset TOKEN TS_AUTHKEY

else
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
fi   # TRANSPORT

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
if [ "$TRANSPORT" = tailnet ]; then
  # lab hosts = every lab Mac and every node VM, by tailnet name and IPv4. Only devices named here:
  # other machines on the same tailnet stay non-local to the guard.
  LIMA_ARGS=(); [ -z "$SERVER_SSH" ] && LIMA_ARGS+=(--lima-instance sdlc-server)
  HOST_ARGS=(); MAC_IPS=()
  for m in "${SERVER_MAC:-$SELF_MAC}" $AGENT_MACS; do
    is_self "$m" && [ "$m" != "${SERVER_MAC:-$SELF_MAC}" ] && LIMA_ARGS+=(--lima-instance sdlc-agent)
    ip="$(ts_ipv4 "$m")"; [ -n "$ip" ] || die "no tailnet IPv4 for $m"
    MAC_IPS+=("$ip"); HOST_ARGS+=(--lab-host "$m" --lab-host "$ip")
  done
  for n in sdlc-server $(for m in $AGENT_MACS; do echo "sdlc-agent-$m"; done); do
    ip="$(ts_ipv4 "$n")"; [ -n "$ip" ] || die "no tailnet IPv4 for node $n"
    HOST_ARGS+=(--lab-host "$n" --lab-host "$ip")
  done
  # app-namespaces.sh reads this to let the lab Macs (and only them) reach pod IPs directly
  "${KC[@]}" -n sdlc-system create configmap lab-network --from-literal=transport=tailnet \
    --from-literal=mac-ips="${MAC_IPS[*]}" --dry-run=client -o yaml | "${KC[@]}" apply -f - >/dev/null
else
  LIMA_ARGS=(); [ -n "$AGENT_IP" ] && LIMA_ARGS+=(--lima-instance sdlc-agent); [ -z "$SERVER_SSH" ] && LIMA_ARGS+=(--lima-instance sdlc-server)
  HOST_ARGS=(--lab-host "$SERVER_IP"); [ -n "$AGENT_IP" ] && HOST_ARGS+=(--lab-host "$AGENT_IP")
fi
python3 "$MP" --kubeconfig "$AGENT_KC" --pin "$AGENT_KC" --namespaces '*-dev,*-qa' \
  ${LIMA_ARGS[@]+"${LIMA_ARGS[@]}"} "${HOST_ARGS[@]}" --out "$POLICY"   # (empty-array safe on bash 3.2)

say "done"
echo "Next: per project, create its namespaces:  $HERE/app-namespaces.sh <app>"
echo "Verify the cluster end to end:              $HERE/cluster-check.sh"
