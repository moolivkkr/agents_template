#!/usr/bin/env bash
# k8s-templates.test.sh — static checks for .claude/templates/k8s: scripts parse under macOS bash 3.2,
# Lima templates validate (when limactl is installed), cluster manifests pass kubeconform (when
# installed; CRDs like HelmChartConfig are skipped). Run: bash tests/k8s-templates.test.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S="$REPO/.claude/templates/k8s"
PASS=0; FAIL=0; SKIP=0
ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
skip() { echo "  - skip: $1"; SKIP=$((SKIP+1)); }

for f in "$K8S"/scripts/*.sh "$K8S"/app/instantiate.sh "$K8S"/app/scripts/k8s/*.sh; do
  /bin/bash -n "$f" 2>/dev/null && ok "bash 3.2 parses $(basename "$f")" || bad "$(basename "$f") does not parse under /bin/bash"
  [ -x "$f" ] && ok "$(basename "$f") is executable" || bad "$(basename "$f") is not executable"
done
# bash 3.2 + set -u: "${arr[@]}" on an empty array aborts; scripts must use ${arr[@]+"${arr[@]}"}
for f in "$K8S"/scripts/*.sh "$K8S"/app/scripts/k8s/*.sh; do
  if grep -q 'set -[a-z]*u' "$f" && grep -nE '"\$\{[A-Z_]+_ARGS\[@\]\}"' "$f" | grep -v '+"' >/dev/null; then
    bad "$(basename "$f"): *_ARGS[@] expanded without the empty-array guard"
  fi
done

if command -v limactl >/dev/null; then
  for f in "$K8S"/lima/*.yaml; do
    limactl validate "$f" >/dev/null 2>&1 && ok "limactl validate $(basename "$f")" || bad "limactl validate $(basename "$f")"
  done
else skip "limactl not installed"; fi

# Lima applies the FIRST matching portForwards rule: the same guestPort+proto twice is dead config
python3 - "$K8S"/lima/*.yaml <<'PY' && ok "no duplicate guestPort forwards in Lima templates" || bad "duplicate guestPort forward (Lima uses the first match only)"
import re, sys
bad = False
for p in sys.argv[1:]:
    seen = set()
    for block in re.split(r"\n- ", open(p).read().split("portForwards:", 1)[1].split("\ncopyToHost", 1)[0]):
        m = re.search(r"guestPort:\s*(\d+)", block)
        if not m: continue
        key = (m.group(1), (re.search(r"proto:\s*(\w+)", block) or [None, "tcp"])[1])
        if key in seen: print(f"{p}: guestPort {key}"); bad = True
        seen.add(key)
sys.exit(1 if bad else 0)
PY

KC="$(command -v kubeconform || ls "$HOME/go/bin/kubeconform" 2>/dev/null)"
if [ -n "$KC" ]; then
  "$KC" -strict -summary -skip HelmChartConfig -ignore-missing-schemas "$K8S"/cluster/*.yaml >/dev/null 2>&1 \
    && ok "kubeconform cluster/*.yaml" || bad "kubeconform cluster/*.yaml: $("$KC" -strict -skip HelmChartConfig "$K8S"/cluster/*.yaml 2>&1 | head -3)"
else skip "kubeconform not installed"; fi

# ── app layer: instantiate the fixture, render both overlays, validate, exercise deploylib ──────────
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
bash "$K8S/app/instantiate.sh" "$W" demo >/dev/null && ok "instantiate.sh demo" || bad "instantiate.sh failed"
grep -rq "__APP__" "$W" && bad "unreplaced __APP__ placeholders" || ok "all __APP__ placeholders replaced"
grep -qxF 'deploy/k8s/overlays/*/secrets.env' "$W/.gitignore" && ok "secrets.env gitignored" || bad "secrets.env not gitignored"
again="$(bash "$K8S/app/instantiate.sh" "$W" demo)"   # (not piped into grep -q: SIGPIPE + pipefail)
echo "$again" | grep -q "kept" && ! echo "$again" | grep -q "created" && ok "instantiate.sh never overwrites" || bad "instantiate.sh overwrote files"
KUBECTL="$(command -v kubectl || ls /Applications/Docker.app/Contents/Resources/bin/kubectl 2>/dev/null)"
for e in dev qa; do
  printf 'DB_USER=app\nDB_PASSWORD=x\n' > "$W/deploy/k8s/overlays/$e/secrets.env"
  if [ -n "$KUBECTL" ] && "$KUBECTL" kustomize "$W/deploy/k8s/overlays/$e" > "$W/$e.yaml" 2>"$W/$e.err"; then
    grep -q "namespace: demo-$e" "$W/$e.yaml" && grep -q "host: demo-$e.localhost" "$W/$e.yaml" \
      && ok "overlay $e renders (namespace demo-$e, host demo-$e.localhost)" || bad "overlay $e: wrong namespace/host"
    [ -n "$KC" ] && { "$KC" -strict -summary "$W/$e.yaml" >/dev/null 2>&1 && ok "kubeconform overlay $e" || bad "kubeconform overlay $e"; }
  elif [ -n "$KUBECTL" ]; then bad "overlay $e does not render: $(head -2 "$W/$e.err")"
  else skip "kubectl not installed (overlay $e)"; fi
done
DL="$W/scripts/k8s/deploylib.py"; KZ="$W/deploy/k8s/overlays/dev/kustomization.yaml"; D1=sha256:$(printf a%.0s {1..64}); D2=sha256:$(printf b%.0s {1..64})
python3 "$DL" set-images "$KZ" "api=localhost:5001/demo/api@$D1" && [ "$(python3 "$DL" get-images "$KZ")" = "api=localhost:5001/demo/api@$D1" ] \
  && ok "deploylib set-images/get-images round-trip" || bad "deploylib set/get-images"
python3 "$DL" set-images "$KZ" "api=localhost:5001/demo/api:latest" 2>/dev/null && bad "deploylib accepted a tag (must be digest)" || ok "deploylib refuses non-digest refs"
H="$W/h.jsonl"
printf '%s\n' "{\"verdict\":\"HEALTHY\",\"git_sha\":\"v1\",\"images\":{\"api\":\"r@$D1\"}}" "{\"verdict\":\"HEALTHY\",\"git_sha\":\"v2\",\"images\":{\"api\":\"r@$D2\"}}" "{\"verdict\":\"DEGRADED\",\"git_sha\":\"v3\",\"images\":{}}" > "$H"
[ "$(python3 "$DL" pick "$H" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')" = v2 ] && ok "pick: newest HEALTHY (skips DEGRADED)" || bad "pick newest HEALTHY"
[ "$(python3 "$DL" pick "$H" --differs "api=r@$D2" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')" = v1 ] && ok "pick --differs: rollback target" || bad "pick --differs"

echo "────────────────────────────────────────────"
echo "k8s-templates.test.sh: $PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" -eq 0 ]
