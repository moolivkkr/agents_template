#!/bin/bash
# tailnet-join.sh — runs as root INSIDE a sdlc-node-tailnet Lima VM. cluster-up.sh (TRANSPORT=tailnet)
# pipes it in with the variables below exported ahead of it, so secrets never appear in argv or on disk
# outside /etc/rancher/k3s. Idempotent: an existing tailnet login and k3s install are kept.
#
#   ROLE          server | agent
#   NODE_NAME     tailnet hostname and k8s node name (sdlc-server, sdlc-agent-<mac>)
#   TS_AUTHKEY    Tailscale auth key: reusable, pre-approved, tagged TS_TAG
#   TS_TAG        e.g. tag:k8s
#   K3S_TOKEN     cluster token (agents only)
#   SERVER_URL    https://<sdlc-server tailnet IP>:6443 (agents only)
#   CLUSTER_CIDR  SERVICE_CIDR   (server only)
set -euo pipefail

# Join BEFORE k3s starts. k3s skips its own `tailscale up --reset` when Tailscale is already running,
# so these settings survive; it then only runs `tailscale set --accept-routes --advertise-routes=<pod /24>`.
# --snat-subnet-routes=false keeps real source IPs on routed traffic: without it, packets from another
# node's pods (and from the lab Macs) arrive masqueraded as this node, and the env-isolation
# NetworkPolicy can no longer tell same-namespace pods from anything else.
if ! tailscale status >/dev/null 2>&1; then
  tailscale up --authkey="$TS_AUTHKEY" --hostname="$NODE_NAME" --advertise-tags="$TS_TAG" \
    --ssh --accept-routes --snat-subnet-routes=false
else
  tailscale set --hostname="$NODE_NAME" --ssh --accept-routes --snat-subnet-routes=false
fi
NODE_IP="$(tailscale ip -4)"
echo "tailnet-join: $NODE_NAME is $NODE_IP"

mkdir -p /etc/rancher/k3s
(umask 077; printf 'name=tailscale,joinKey=%s' "$TS_AUTHKEY" > /etc/rancher/k3s/vpn-auth)
# images are referenced as localhost:5001/...; each node pulls through its own registry NodePort
cat >/etc/rancher/k3s/registries.yaml <<EOF
mirrors:
  "localhost:5001":
    endpoint: ["http://$NODE_IP:30501"]
EOF

[ -d /var/lib/rancher/k3s ] && { echo "tailnet-join: k3s already installed"; exit 0; }
if [ "$ROLE" = server ]; then
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 \
    --vpn-auth-file=/etc/rancher/k3s/vpn-auth --node-name=$NODE_NAME \
    --cluster-cidr=$CLUSTER_CIDR --service-cidr=$SERVICE_CIDR \
    --tls-san=$NODE_IP --tls-san=$NODE_NAME --tls-san=127.0.0.1" sh -
else
  curl -sfL https://get.k3s.io | K3S_URL="$SERVER_URL" K3S_TOKEN="$K3S_TOKEN" \
    INSTALL_K3S_EXEC="agent --vpn-auth-file=/etc/rancher/k3s/vpn-auth --node-name=$NODE_NAME" sh -
fi
