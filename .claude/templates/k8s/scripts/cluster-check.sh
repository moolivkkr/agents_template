#!/bin/bash
# cluster-check.sh — prove the sdlc lab cluster works end to end, from THIS Mac. Admin kubeconfig.
#
# Checks, each PASS/FAIL (exit 1 on any FAIL):
#   nodes     every node Ready
#   push      an image copied into the in-cluster registry through localhost:5001 (crane)
#   pull      one pod per node starts from localhost:5001/... (each node's containerd mirror)
#   pod-ip    pod -> pod across nodes, both directions, ROUNDS times (first node <-> every other node)
#   svc-dns   pod -> Service by DNS name across nodes, both directions, ROUNDS times
#   mac-pod   tailnet mode only: this Mac -> every pod IP over the tailnet's pod routes
#   mac-svc   tailnet mode only: this Mac -> a ClusterIP, and by its cluster.local name (split DNS)
#   registry  tailnet mode only: the registry NodePort does NOT answer on any node's tailnet IP
#   https     tailnet mode only: https://sdlc-check.localhost:18443 (Traefik websecure via the Lima forward)
#   ingress   http://sdlc-check.localhost:18080 from this Mac (Traefik via the Lima forward)
# Everything it creates (pods, services, ingress in sdlc-system, and its registry image) is deleted at the end.
set -uo pipefail
ADMIN_KC="${ADMIN_KC:-$HOME/.kube/sdlc-lab-admin.yaml}"
REGISTRY="${REGISTRY:-localhost:5001}"
INGRESS_URL="${INGRESS_URL:-http://sdlc-check.localhost:18080/}"
ROUNDS="${ROUNDS:-5}"
IMG="$REGISTRY/sdlc-check/nginx:alpine"
export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
K=(kubectl --kubeconfig "$ADMIN_KC" -n sdlc-system)
PASS=0; FAIL=0
ok()  { echo "  PASS $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }
fetch() { "${K[@]}" exec "$1" -- wget -qO- -T 5 "$2" 2>/dev/null | grep -q '<title>Welcome'; }
cleanup() {
  "${K[@]}" delete pod,svc,ingress -l sdlc-check=1 --ignore-not-found --wait=false >/dev/null 2>&1
  d="$(crane digest "$IMG" 2>/dev/null)" && crane delete "${IMG%:*}@$d" >/dev/null 2>&1   # leave the registry as found
}
trap cleanup EXIT

echo "== nodes"
NODES=($(kubectl --kubeconfig "$ADMIN_KC" get nodes --no-headers | awk '{print $1}'))
NOTREADY="$(kubectl --kubeconfig "$ADMIN_KC" get nodes --no-headers | awk '$2!="Ready"' | wc -l | tr -d ' ')"
[ "${#NODES[@]}" -gt 0 ] && [ "$NOTREADY" = 0 ] && ok "${#NODES[@]} node(s) Ready: ${NODES[*]}" || bad "nodes not Ready"

echo "== push ($IMG)"
if crane copy --platform linux/arm64 nginx:alpine "$IMG" >/dev/null 2>&1 && crane digest "$IMG" >/dev/null 2>&1; then
  ok "crane copy -> $IMG ($(crane digest "$IMG" | cut -c1-19))"
else bad "could not push to $REGISTRY (is the registry forward up? limactl list)"; fi

echo "== pull (one pod per node)"
cleanup; sleep 2
PODS=()
for n in "${NODES[@]}"; do
  p="check-${n##*-}"; PODS+=("$p")
  cat <<EOF | "${K[@]}" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata: {name: $p, labels: {sdlc-check: "1", app: $p}}
spec:
  nodeName: $n
  containers: [{name: web, image: "$IMG", ports: [{containerPort: 80}]}]
---
apiVersion: v1
kind: Service
metadata: {name: $p, labels: {sdlc-check: "1"}}
spec: {selector: {app: $p}, ports: [{port: 80}]}
EOF
done
if "${K[@]}" wait --for=condition=Ready "${PODS[@]/#/pod/}" --timeout=180s >/dev/null 2>&1; then
  ok "pods started from $REGISTRY on every node"
else bad "pods did not start: $("${K[@]}" get pods -l sdlc-check=1 --no-headers 2>&1 | tr '\n' ';')"; fi

[ "${#PODS[@]}" -ge 1 ] && A="${PODS[0]}" && IPA="$("${K[@]}" get pod "$A" -o jsonpath='{.status.podIP}')"
for B in ${PODS[@]+"${PODS[@]:1}"}; do
  IPB="$("${K[@]}" get pod "$B" -o jsonpath='{.status.podIP}')"
  echo "== cross-node traffic, $ROUNDS rounds ($A=$IPA, $B=$IPB)"
  e=0; for _ in $(seq 1 "$ROUNDS"); do fetch "$A" "http://$IPB/" || e=$((e+1)); fetch "$B" "http://$IPA/" || e=$((e+1)); done
  [ "$e" = 0 ] && ok "pod-ip $A<->$B ($((ROUNDS*2))/$((ROUNDS*2)))" || bad "pod-ip $A<->$B: $e/$((ROUNDS*2)) failed"
  e=0; for _ in $(seq 1 "$ROUNDS"); do fetch "$A" "http://$B/" || e=$((e+1)); fetch "$B" "http://$A.sdlc-system.svc.cluster.local/" || e=$((e+1)); done
  [ "$e" = 0 ] && ok "svc-dns $A<->$B ($((ROUNDS*2))/$((ROUNDS*2)))" || bad "svc-dns $A<->$B: $e/$((ROUNDS*2)) failed"
done

if [ "$("${K[@]}" get configmap lab-network -o jsonpath='{.data.transport}' 2>/dev/null)" = tailnet ]; then
  echo "== this Mac -> pod IPs over the tailnet"
  for P in ${PODS[@]+"${PODS[@]}"}; do
    IP="$("${K[@]}" get pod "$P" -o jsonpath='{.status.podIP}')"
    curl -s -m 5 "http://$IP/" | grep -q '<title>Welcome' && ok "mac-pod $P ($IP)" \
      || bad "mac-pod $P ($IP): no route? (tailscale set --accept-routes; pod routes approved in the admin console?)"
  done
  echo "== registry NodePort is NOT on the tailnet (it has no auth)"
  for n in "${NODES[@]}"; do
    NIP="$(kubectl --kubeconfig "$ADMIN_KC" get node "$n" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}' | awk '{print $1}')"
    curl -s -m 4 -o /dev/null "http://$NIP:30501/v2/" && bad "registry answers on $n ($NIP:30501): NodePorts must be loopback-only" \
      || ok "registry closed on $n's tailnet IP"
  done
  echo "== this Mac -> Services over the tailnet (ClusterIP route, then cluster.local via split DNS)"
  if [ "${#PODS[@]}" -ge 1 ]; then
    P="${PODS[0]}"; SIP="$("${K[@]}" get svc "$P" -o jsonpath='{.spec.clusterIP}')"
    curl -s -m 5 "http://$SIP/" | grep -q '<title>Welcome' && ok "mac-svc $P ($SIP)" \
      || bad "mac-svc $P ($SIP): is the Service CIDR route advertised by sdlc-server and approved?"
    FQDN="$P.sdlc-system.svc.cluster.local"
    if dscacheutil -q host -a name "$FQDN" 2>/dev/null | grep -q ip_address; then
      curl -s -m 5 "http://$FQDN/" | grep -q '<title>Welcome' && ok "mac-dns $FQDN" || bad "mac-dns $FQDN resolves but does not answer"
    else
      bad "mac-dns $FQDN does not resolve: add split DNS cluster.local -> 10.43.0.10 in the Tailscale admin console"
    fi
  fi
fi

echo "== ingress ($INGRESS_URL)"
HOST="$(printf '%s' "$INGRESS_URL" | sed -E 's#^https?://([^:/]+).*#\1#')"
cat <<EOF | "${K[@]}" apply -f - >/dev/null
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: {name: sdlc-check, labels: {sdlc-check: "1"}}
spec:
  rules:
  - host: $HOST
    http: {paths: [{path: /, pathType: Prefix, backend: {service: {name: ${PODS[0]}, port: {number: 80}}}}]}
EOF
got=""; for _ in $(seq 1 15); do got="$(curl -s -m 5 "$INGRESS_URL" | grep -c '<title>Welcome')"; [ "$got" -ge 1 ] && break; sleep 2; done
[ "${got:-0}" -ge 1 ] && ok "ingress reachable from this Mac" || bad "ingress $INGRESS_URL not reachable"
if [ "$("${K[@]}" get configmap lab-network -o jsonpath='{.data.transport}' 2>/dev/null)" = tailnet ]; then
  # Traefik's default certificate is self-signed, hence -k: this proves the path, not the cert
  curl -sk -m 5 --resolve "$HOST:18443:127.0.0.1" "https://$HOST:18443/" | grep -q '<title>Welcome' \
    && ok "https ingress https://$HOST:18443 from this Mac" || bad "https ingress :18443 not reachable (Lima forward 443->18443?)"
fi

echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
