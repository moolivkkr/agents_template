#!/usr/bin/env bash
# dependency-graph.test.sh — guards agent ↔ command ↔ skill communication. Bug classes it catches,
# all found in the 2026-09 dependency review:
#   - a dependency or spawn naming an agent with no file (frontend_developer, test_developer)
#   - one-sided dependency declarations (A says B consumes it, B never heard of A) — 141 of these
#   - a hard `upstream` edge to an agent the orchestrator runs in the same/later wave
#   - an agent reading a file no agent/command writes (research/ vs reference/ drift)
#   - the orchestrator expecting a report name the agent never writes (quality_gate vs code_quality)
#   - agents never spawned by anything (test_runner, product_api_researcher, demo_*)
#   - skill packs nothing loads, and agents that load none
#   - template-resolved skill paths that don't exist (mockery.md, shadcn/ui.md)
#   - TC-ID scanners that can't see categories with digits (TC-E2E-*, TC-A11Y-*, TC-ME2E-*)
# Run: bash tests/dependency-graph.test.sh   (exit 0 = pass)

set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. Static graph: every finding class must be empty.
OUT="$(python3 "$TEST_DIR/lib/depgraph.py" --json 2>&1)" || { bad "depgraph.py crashed: $OUT"; OUT='{"findings":{}}'; }
for CLASS in DANGLING_AGENT DANGLING_SKILL ASYMMETRIC WAVE_ORDER IO_UNPRODUCED REPORT_NAME ORPHAN_AGENT ORPHAN_SKILL NO_SKILLS YAML_ERROR; do
  N="$(printf '%s' "$OUT" | jq -r --arg c "$CLASS" '.findings[$c] | length' 2>/dev/null)"
  if [ "$N" = "0" ]; then
    ok "$CLASS: none"
  else
    bad "$CLASS: ${N:-?} finding(s) — run: python3 tests/lib/depgraph.py"
    printf '%s' "$OUT" | jq -r --arg c "$CLASS" '.findings[$c][]?' 2>/dev/null | head -5 | sed 's/^/      /'
  fi
done

# 2. Derived downstream lists are in sync (nobody hand-edited one).
if python3 "$ROOT/.claude/agents/_sync-deps.py" --check >/dev/null 2>&1; then
  ok "dependency blocks in sync with _sync-deps.py"
else
  bad "dependency blocks out of sync — run: python3 .claude/agents/_sync-deps.py"
fi

# 3. Every skill pack named in agent_factory's resolution table exists.
FACTORY="$ROOT/.claude/agents/core/agent_factory.md"
TABLE="$(awk '/BEGIN skill-resolution/,/END skill-resolution/' "$FACTORY")"
if [ -z "$TABLE" ]; then
  bad "agent_factory.md has no <!-- BEGIN skill-resolution --> table"
else
  miss=0
  while IFS= read -r pack; do
    [ -f "$ROOT/.claude/skills/$pack" ] || { bad "resolution table names missing pack skills/$pack"; miss=1; }
  done < <(printf '%s\n' "$TABLE" | grep -oE '`[a-z-]+/[a-z0-9.-]+\.md`' | tr -d '`' | sort -u)
  [ "$miss" -eq 0 ] && ok "every pack in the skill-resolution table exists"
fi

# 4. Every template placeholder used in a skill path is either a direct-filename var or in the table.
DIRECT='LANG FRAMEWORK UI_FRAMEWORK DB_TECH ORM'   # values are filenames (go.md, gin.md, react.md, postgres.md)
for v in $(grep -ohE 'skills/[a-z]+/\{\{[A-Z0-9_]+\}\}\.md' "$ROOT"/.claude/agents/templates/*.tmpl "$ROOT"/.claude/agents/core/*.md | grep -oE '\{\{[A-Z0-9_]+\}\}' | tr -d '{}' | sort -u); do
  if printf ' %s ' "$DIRECT" | grep -q " $v "; then continue; fi
  if printf '%s' "$TABLE" | grep -q "{{$v}}"; then ok "placeholder {{$v}} has resolution rows"; else bad "placeholder {{$v}} is used in a skill path but has no row in agent_factory's resolution table"; fi
done

# 5. TC-ID scanners must accept digits in the category (TC-E2E-001, TC-A11Y-001, TC-ME2E-001).
if grep -rnE "TC-\[A-Z\]\+|TC-\\\\K\[A-Z\]\+" "$ROOT/.claude" >/dev/null 2>&1; then
  bad "a TC-ID scanner uses TC-[A-Z]+ (misses TC-E2E/TC-A11Y/TC-ME2E):"
  grep -rnE "TC-\[A-Z\]\+|TC-\\\\K\[A-Z\]\+" "$ROOT/.claude" | head -5 | sed 's/^/      /'
else
  ok "all TC-ID scanners accept digits in the category"
fi
got="$(printf 'x TC-E2E-001 TC-A11Y-002 TC-ME2E-003 TC-UI-004\n' | grep -oE 'TC-[A-Z0-9]+-[0-9]+' | wc -l | tr -d ' ')"
[ "$got" = "4" ] && ok "canonical TC regex matches E2E/A11Y/ME2E/UI ids" || bad "canonical TC regex matched $got/4 ids"

# 6. Mobile wiring: agents exist, orchestrator + /test spawn them, factory generates the template.
for a in mobile_e2e_orchestrator mobile_platform_auditor; do
  [ -f "$ROOT/.claude/agents/core/$a.md" ] && ok "core agent $a exists" || bad "core agent $a missing"
done
for t in mobile_developer mobile_test_agent; do
  [ -f "$ROOT/.claude/agents/templates/$t.tmpl" ] && ok "template $t exists" || bad "template $t.tmpl missing"
  grep -q "$t.tmpl" "$FACTORY" && ok "agent_factory generates $t" || bad "agent_factory never generates $t"
done
for a in mobile_developer mobile_test_agent mobile_e2e_orchestrator mobile_platform_auditor; do
  grep -qE "subagent_type: $a|Agent: $a|2A\.[0-9]+ +$a" "$ROOT/.claude/commands/develop-orchestrator.md" \
    && ok "develop-orchestrator spawns $a" || bad "develop-orchestrator never spawns $a"
done
grep -q "mobile_e2e_orchestrator" "$ROOT/.claude/commands/test.md" && ok "/test spawns mobile_e2e_orchestrator" || bad "/test never spawns mobile_e2e_orchestrator"

# 7. Generated-agent identity: template name: is the bare role, and its completion line uses it.
for t in "$ROOT"/.claude/agents/templates/*.tmpl; do
  role="$(basename "$t" .tmpl)"
  name="$(sed -n 's/^name: *"\{0,1\}\([^"]*\)"\{0,1\} *$/\1/p' "$t" | head -1)"
  [ "$name" = "$role" ] || { bad "$(basename "$t"): name '$name' != role '$role' (roster/subagent_type mismatch)"; continue; }
  grep -q "\"agent\":\"$role\"" "$t" && ok "$role: name + completion log use the bare role" || bad "$role: completion log does not use \"agent\":\"$role\""
done

echo "────────────────────────────────────────────"
echo "dependency-graph.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
