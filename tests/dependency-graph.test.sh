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

# 1b. Regression (board review 2026-09-30, ARCH-08): the IO check's glob must be segment-aware. With
#     fnmatch, '*' crossed '/', so a command naming agent_state/phases/${PHASE}/manifest.json "produced"
#     every per-agent agent_state/phases/N/<agent>/manifest.json input, including ones nobody writes.
FX="$(mktemp -d "${TMPDIR:-/tmp}/depgraph-fx.XXXXXX")"
mkdir -p "$FX/.claude/agents/core" "$FX/.claude/commands" "$FX/.claude/skills/core"
printf '%s\n' '---' 'name: producer_agent' 'skill_packs: []' 'output:' \
  '  primary: "agent_state/phases/{{PHASE}}/producer_agent/manifest.json"' '---' '# producer' \
  > "$FX/.claude/agents/core/producer_agent.md"
printf '%s\n' '---' 'name: consumer_agent' 'skill_packs: []' 'input:' '  required:' \
  '    - path: agent_state/phases/{{PHASE}}/producer_agent/manifest.json' \
  '    - path: agent_state/phases/{{PHASE}}/no_such_agent/manifest.json' \
  '    - path: agent_state/phases/{{PHASE}}/manifest.json' '---' '# consumer' \
  > "$FX/.claude/agents/core/consumer_agent.md"
printf '%s\n' '# run' 'Spawn producer_agent then consumer_agent.' \
  'The parent writes agent_state/phases/${PHASE}/manifest.json at the gate.' > "$FX/.claude/commands/run.md"
FXOUT="$(DEPGRAPH_ROOT="$FX" python3 "$TEST_DIR/lib/depgraph.py" --json 2>&1)"
UNPROD="$(printf '%s' "$FXOUT" | jq -r '.findings.IO_UNPRODUCED[]?' 2>/dev/null)"
if printf '%s\n' "$UNPROD" | grep -q "no_such_agent/manifest.json"; then
  ok "IO check reports an unproduced per-agent manifest input (a '*' no longer crosses '/')"
else
  bad "IO check missed agent_state/phases/N/no_such_agent/manifest.json (fnmatch '*' crossing '/'?): ${FXOUT:0:300}"
fi
if printf '%s\n' "$UNPROD" | grep -qE "producer_agent/manifest.json|phases/TMPL_PHASE/manifest.json"; then
  bad "IO check false-positive on a produced input: $UNPROD"
else
  ok "IO check still accepts inputs an agent or command produces at the same depth"
fi
rm -rf "$FX"

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

# 8. Google Stitch: every mcp__stitch__* tool named in a command/skill/agent exists in the verified
#    tool surface (stitch-design.md, verified 2026-09-29 against the live MCP), the fake bash probe is
#    gone from commands, and generation calls always come with a deviceType rule.
STITCH_TOOLS="list_projects create_project get_project delete_project list_screens get_screen generate_screen_from_text edit_screens generate_variants create_design_system update_design_system list_design_systems apply_design_system upload_design_md create_design_system_from_design_md"
used="$(grep -rhoE 'mcp__stitch__[a-z_]+' "$ROOT/.claude" | sed 's/mcp__stitch__//' | sort -u)"
unknown=0
for t in $used; do printf ' %s ' "$STITCH_TOOLS" | grep -q " $t " || { bad "unknown Stitch tool referenced: mcp__stitch__$t"; unknown=1; }; done
[ "$unknown" -eq 0 ] && ok "all referenced Stitch tools exist ($(printf '%s\n' $used | wc -l | tr -d ' ') used)"
if grep -rn "mcp_stitch_probe" "$ROOT/.claude/commands" >/dev/null 2>&1; then bad "commands still call the nonexistent mcp_stitch_probe"; else ok "no fake Stitch probe in commands"; fi
for f in "$ROOT/.claude/commands/design.md" "$ROOT/.claude/commands/stitch.md"; do
  grep -q "stitch-design.md" "$f" && grep -q "deviceType" "$f" && ok "$(basename "$f") follows stitch-design.md with deviceType" \
    || bad "$(basename "$f") does not reference stitch-design.md + deviceType"
done
[ -f "$ROOT/.claude/agents/core/ui_standards_auditor.md" ] && ok "core agent ui_standards_auditor exists" || bad "ui_standards_auditor missing"
grep -q "subagent_type: ui_standards_auditor" "$ROOT/.claude/commands/ui-audit.md" && ok "/ui-audit spawns ui_standards_auditor" || bad "/ui-audit never spawns ui_standards_auditor"
grep -q "Agent: ui_standards_auditor" "$ROOT/.claude/commands/develop-orchestrator.md" && ok "develop-orchestrator runs ui_standards_auditor in Wave 4" || bad "develop-orchestrator never runs ui_standards_auditor"
grep -q '"pages"' "$ROOT/.claude/skills/ui/stitch-design.md" && ok "stitch.json schema carries the all-pages baseline map" || bad "stitch-design.md lacks the pages map"
if grep -nE "mcp__stitch__" "$ROOT/.claude/agents/core/ui_standards_auditor.md" | grep -v "Do not call\|does not call\|No Stitch MCP" >/dev/null; then bad "ui_standards_auditor calls Stitch directly (parent must)"; else ok "ui_standards_auditor leaves Stitch calls to the parent"; fi
grep -q "get_project" "$ROOT/.claude/commands/design.md" && ok "/design fetches the screen instance before create_design_system_from_design_md" \
  || bad "/design calls create_design_system_from_design_md without get_project (missing selectedScreenInstance)"

echo "────────────────────────────────────────────"
echo "dependency-graph.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
