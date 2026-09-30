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

for f in "$K8S"/scripts/*.sh; do
  /bin/bash -n "$f" 2>/dev/null && ok "bash 3.2 parses $(basename "$f")" || bad "$(basename "$f") does not parse under /bin/bash"
  [ -x "$f" ] && ok "$(basename "$f") is executable" || bad "$(basename "$f") is not executable"
done
# bash 3.2 + set -u: "${arr[@]}" on an empty array aborts; scripts must use ${arr[@]+"${arr[@]}"}
for f in "$K8S"/scripts/*.sh; do
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

echo "────────────────────────────────────────────"
echo "k8s-templates.test.sh: $PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" -eq 0 ]
