#!/usr/bin/env bash
# agent-registry.test.sh — guards the registry-drift bug classes found in the 2026-07 review:
#   - a roster required an agent name with no corresponding file (e2e_test_agent) → gate landmine
#   - INVENTORY.md core count drifted from disk (said 58, was 63)
# Run: bash tests/agent-registry.test.sh   (exit 0 = pass)

set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
CORE="$ROOT/.claude/agents/core"
TMPL="$ROOT/.claude/agents/templates"
ORCH="$ROOT/.claude/commands/develop-orchestrator.md"
INV="$ROOT/.claude/agents/INVENTORY.md"

PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

# agent name resolves if core/<name>.md OR templates/<name>.tmpl.md exists.
resolves() { [ -f "$CORE/$1.md" ] || [ -f "$TMPL/$1.tmpl.md" ]; }

# 1. Every name in the orchestrator's base REQUIRED roster resolves to a real agent file.
REQ_LINE="$(grep -m1 "^REQUIRED='" "$ORCH" | sed "s/^REQUIRED='//; s/'$//")"
if [ -z "$REQ_LINE" ]; then
  bad "could not find REQUIRED='[...]' base roster line in develop-orchestrator.md"
else
  names="$(printf '%s' "$REQ_LINE" | jq -r '.[]' 2>/dev/null)"
  if [ -z "$names" ]; then bad "REQUIRED roster line is not valid JSON: $REQ_LINE"; else
    miss=0
    while IFS= read -r n; do
      [ -z "$n" ] && continue
      resolves "$n" || { bad "roster agent '$n' has no core/ or templates/ file"; miss=1; }
    done <<< "$names"
    [ "$miss" -eq 0 ] && ok "all base-roster agent names resolve to real agent files"
  fi
fi

# 2. INVENTORY.md "Core agents" count matches the actual number of core/*.md files.
ACTUAL="$(ls "$CORE"/*.md 2>/dev/null | wc -l | tr -d ' ')"
STATED="$(grep -oE 'Core agents \(`\.claude/agents/core/`\) \| [0-9]+' "$INV" | grep -oE '[0-9]+$' | head -1)"
if [ -z "$STATED" ]; then
  bad "could not parse the 'Core agents' count from INVENTORY.md"
elif [ "$STATED" != "$ACTUAL" ]; then
  bad "INVENTORY 'Core agents' count ($STATED) != actual core/*.md files ($ACTUAL)"
else
  ok "INVENTORY core count matches disk ($ACTUAL)"
fi

# 3. Every findings/review agent that produces a report ends with the machine-readable count line.
#    (Spot-check the 3 new agents — they must carry the trailing BLOCKING:N WARNING:N INFO:N line.)
for a in reliability_agent threat_model_agent accessibility_auditor; do
  if [ -f "$CORE/$a.md" ] && tail -3 "$CORE/$a.md" | grep -q 'BLOCKING:N WARNING:N INFO:N'; then
    ok "$a ends with the machine-readable count line"
  else
    bad "$a missing the trailing 'BLOCKING:N WARNING:N INFO:N' count line"
  fi
done

echo "────────────────────────────────────────────"
echo "agent-registry.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
