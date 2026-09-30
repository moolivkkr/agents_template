#!/bin/bash
# cluster-check.sh — prove the sdlc lab cluster works end to end, from THIS Mac. Admin kubeconfig.
#
# Checks, each PASS/FAIL (exit 1 on any FAIL):
#   nodes     every node Ready
#   push      an image copied into the in-cluster registry through localhost:5001 (crane)
#   pull      one pod per node starts from localhost:5001/... (each node's containerd mirror)
#   pod-ip    pod -> pod across nodes, both directions, ROUNDS times
#   svc-dns   pod -> Service by DNS name across nodes, both directions, ROUNDS times
#   ingress   http://sdlc-check.localhost:18080 from this Mac (Traefik via the Lima forward)
# Everything it creates lives in namespace sdlc-system and is deleted at the end.
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
cleanup() { "${K[@]}" delete pod,svc,ingress -l sdlc-check=1 --ignore-not-found --wait=false >/dev/null 2>&1; }
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

if [ "${#PODS[@]}" -ge 2 ]; then
  A="${PODS[0]}"; B="${PODS[1]}"
  IPA="$("${K[@]}" get pod "$A" -o jsonpath='{.status.podIP}')"; IPB="$("${K[@]}" get pod "$B" -o jsonpath='{.status.podIP}')"
  echo "== cross-node traffic, $ROUNDS rounds ($A=$IPA, $B=$IPB)"
  e=0; for _ in $(seq 1 "$ROUNDS"); do fetch "$A" "http://$IPB/" || e=$((e+1)); fetch "$B" "http://$IPA/" || e=$((e+1)); done
  [ "$e" = 0 ] && ok "pod-ip both directions ($((ROUNDS*2))/$((ROUNDS*2)))" || bad "pod-ip: $e/$((ROUNDS*2)) failed"
  e=0; for _ in $(seq 1 "$ROUNDS"); do fetch "$A" "http://$B/" || e=$((e+1)); fetch "$B" "http://$A.sdlc-system.svc.cluster.local/" || e=$((e+1)); done
  [ "$e" = 0 ] && ok "svc-dns both directions ($((ROUNDS*2))/$((ROUNDS*2)))" || bad "svc-dns: $e/$((ROUNDS*2)) failed"
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

echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
