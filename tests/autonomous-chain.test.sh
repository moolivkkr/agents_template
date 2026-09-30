#!/usr/bin/env bash
# autonomous-chain.test.sh — static guards for the /autonomous orchestration chain. Each check is a
# stall found in the 2026-09 review, where "/startup:autonomous stops and I have to jump in":
#   - sub-commands referenced with a flag they don't define (/accept --auto)
#   - /design ordered before /plan (it hard-stops without PHASE_PLAN + data-contracts)
#   - no instruction on HOW to run a sub-command, so the model asks the user to type it
#   - sub-commands whose --auto never suppresses "surface to user"
#   - no Stop hook holding the run open, or hooks never installed into projects
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
C="$ROOT/.claude/commands"
A="$C/autonomous.md"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

args_of() { awk '/^---$/{n++; next} n==1' "$C/$1.md" | sed -n 's/^  - name: *//p'; }

# 1. Every `/cmd --flag` in autonomous.md names a real command and a flag that command defines.
bad_refs=0
while IFS= read -r ref; do
  cmd="$(printf '%s' "$ref" | sed -E 's#^/([a-z-]+).*#\1#')"
  [ -f "$C/$cmd.md" ] || { bad "autonomous references /$cmd, which does not exist"; bad_refs=1; continue; }
  for flag in $(printf '%s' "$ref" | grep -oE -- '--[a-z_-]+' | sed 's/^--//'); do
    f_us="$(printf '%s' "$flag" | tr '-' '_')"
    args_of "$cmd" | grep -qxE "$flag|$f_us" || { bad "/$cmd has no --$flag argument (used by autonomous: $ref)"; bad_refs=1; }
  done
done < <(grep -oE '`/[a-z-]{2,}( --[a-z_=-]+(=[A-Za-z0-9${}N_-]+)?)*' "$A" | tr -d '`' | sort -u)   # {2,}: skip the /x /y placeholders
[ "$bad_refs" -eq 0 ] && ok "every sub-command + flag referenced by /autonomous exists"

# 2. /design runs after /plan (phase 1 steps and the per-phase loop).
p2b="$(grep -n '^### Step 2b' "$A" | cut -d: -f1)"; p2c="$(grep -n '^### Step 2c' "$A" | cut -d: -f1)"
[ -n "$p2b" ] && [ -n "$p2c" ] && [ "$p2c" -gt "$p2b" ] && grep -q 'Step 2c.*AFTER /plan' "$A" \
  && ok "phase 1: /design (2c) comes after /plan (2b)" || bad "phase 1: /design is not after /plan"
loop="$(awk '/^## Step 5/,/^### Post-Phase/' "$A")"
lp="$(printf '%s\n' "$loop" | grep -n '/plan --auto' | head -1 | cut -d: -f1)"; ld="$(printf '%s\n' "$loop" | grep -n '/design --phase' | head -1 | cut -d: -f1)"
[ -n "$lp" ] && [ -n "$ld" ] && [ "$ld" -gt "$lp" ] && ok "phase N loop: /design after /plan" || bad "phase N loop: /design is not after /plan"
grep -q 'PHASE_PLAN.md' "$C/design.md" && ok "(/design still requires PHASE_PLAN — ordering matters)" || bad "/design no longer checks PHASE_PLAN (re-check ordering rule)"

# 3. /autonomous says how to run sub-commands and how to keep going.
grep -q 'skill: "startup:' "$A" && ok "/autonomous runs sub-commands via the Skill tool" || bad "/autonomous never says to invoke sub-commands via the Skill tool"
grep -q 'Next: /y' "$A" && tr '\n' ' ' < "$A" | grep -qiE 'continue +immediately' && ok "/autonomous overrides sub-command 'Next' hints" || bad "/autonomous doesn't override sub-commands' '▶ Next' lines"
grep -q 'run.json' "$A" && grep -q 'awaiting_human' "$A" && ok "/autonomous maintains run.json with legitimate stop states" || bad "/autonomous has no run.json run-state"
grep -q 'force_gate_policy' "$A" && grep -q 'force_gate_policy' "$C/develop.md" && ok "force-gate approval defined once, honoured by /develop" || bad "force-gate policy conflict between /autonomous and /develop"
if grep -nE 'Run /map.*echo|echo "▶ Mapping codebase' "$A" >/dev/null; then bad "Step 1b /map is still only an echo"; else ok "Step 1b actually runs /map"; fi

# 4. Every sub-command honours auto mode (flag OR active run.json).
for c in init map discuss design plan develop develop-orchestrator accept; do
  grep -q '\*\*Auto mode.\*\* `--auto` is set, OR `agent_state/autonomous/run.json`' "$C/$c.md" \
    && ok "/$c honours auto mode" || bad "/$c lacks the auto-mode contract"
done
unguarded="$(grep -nE 'surface to (the )?user|escalate to (the )?user' "$C/plan.md" "$C/develop-orchestrator.md" | grep -viE 'auto mode' | grep -vE '^[^:]+:[0-9]+:> ' || true)"   # skip the auto-mode contract block itself
[ -z "$unguarded" ] && ok "every 'surface/escalate to user' in plan + orchestrator has an auto-mode branch" || { bad "unguarded user-surface points:"; printf '%s\n' "$unguarded" | sed 's/^/      /'; }

# 5. Stop hook registered, executable, and installed into projects.
S="$ROOT/.claude/settings.json"
jq -e '.hooks.Stop[].hooks[] | select(.command | test("autonomous-continue.sh"))' "$S" >/dev/null 2>&1 && ok "Stop hook autonomous-continue.sh registered" || bad "autonomous-continue.sh not registered on Stop"
[ -x "$ROOT/.claude/hooks/autonomous-continue.sh" ] && ok "autonomous-continue.sh executable" || bad "autonomous-continue.sh not executable"
if jq -r '.. | .command? // empty' "$S" | grep -E '\.claude/hooks/' | grep -vq 'CLAUDE_PROJECT_DIR'; then bad "a hook path is relative (breaks outside the repo root)"; else ok "hook paths use \$CLAUDE_PROJECT_DIR"; fi
grep -q 'hooks/startup' "$ROOT/install.sh" && ok "install.sh stages hooks" || bad "install.sh never installs hooks"
grep -q '.claude/hooks' "$ROOT/new-project.sh" && ok "new-project.sh copies hooks into the project" || bad "new-project.sh never copies hooks"

echo "────────────────────────────────────────────"
echo "autonomous-chain.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
