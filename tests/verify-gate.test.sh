#!/usr/bin/env bash
# verify-gate.test.sh — committed regression test for the framework's linchpin enforcement hook.
#
# This is the CODE form of eval task T-004 (agent_state/eval/suite/T-004-gate-blocks-missing-review):
# it proves the phase gate is real deterministic CODE, not prose a model is trusted to follow. If a
# change ever weakens .claude/hooks/verify-gate.sh (or someone un-wires it), one of these assertions
# flips and the regression is caught BY NAME — no manual /eval run required.
#
# Run: bash tests/verify-gate.test.sh   (exit 0 = all pass, non-zero = a guarantee regressed)
# Wire into CI / a pre-commit hook so weakening the gate fails the build.
#
# Dependencies: bash, jq (same as the hook). No bats, no network.

set -uo pipefail

# Locate the hook relative to this test file, so it runs from any cwd.
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TEST_DIR/.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/verify-gate.sh"

PASS=0; FAIL=0
FIXROOT="$(mktemp -d)"
trap 'rm -rf "$FIXROOT"' EXIT

# assert_exit <expected_code> <test-name> -- <hook args...>   (fixture cwd = $CWD env)
run_hook() { CLAUDE_PROJECT_DIR="$1" bash "$HOOK" "${@:2}" 2>&1; }

check() {  # check <name> <expected_exit> <actual_exit> [must-contain]
  local name="$1" want="$2" got="$3" needle="${4:-}"
  if [ "$got" != "$want" ]; then
    echo "  ✗ FAIL: $name — expected exit $want, got $got"; FAIL=$((FAIL+1)); return
  fi
  if [ -n "$needle" ] && ! printf '%s' "$LAST_OUT" | grep -qF "$needle"; then
    echo "  ✗ FAIL: $name — output missing expected text: '$needle'"; FAIL=$((FAIL+1)); return
  fi
  echo "  ✓ $name"; PASS=$((PASS+1))
}

# Build a phase fixture dir and return its project-root path. Args: name, then it's caller-populated.
new_phase() {
  local d="$FIXROOT/$1"; mkdir -p "$d/agent_state/phases/1/reports"; ( cd "$d" && git init -q 2>/dev/null ); echo "$d"
}

# --- 1. Clean, complete gate → PASS (exit 0) ---
D=$(new_phase clean)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","security_reviewer","code_quality_verifier"]}
J
for a in backend_developer code_reviewer_I code_reviewer_II security_reviewer code_quality_verifier; do
  echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":\"reports/$a.md\",\"ts\":\"t\"}" >> "$D/agent_state/phases/1/execution.jsonl"
  printf 'Report for %s\ntotal: 5\nBLOCKING: 0\n' "$a" > "$D/agent_state/phases/1/reports/$a.md"
done
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "clean complete gate PASSes" 0 "$?"

# --- 2. Missing required agent (security_reviewer never completed) → BLOCK naming it (T-004 core) ---
D=$(new_phase missing_review)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","security_reviewer","code_quality_verifier"]}
J
for a in backend_developer code_reviewer_I code_reviewer_II code_quality_verifier; do
  echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":null,\"ts\":\"t\"}" >> "$D/agent_state/phases/1/execution.jsonl"
done
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "missing security_reviewer BLOCKs (named)" 2 "$?" "security_reviewer"

# --- 3. Forged gate.passed with NO contract files → BLOCK (gate.passed-without-evidence bug) ---
D=$(new_phase forged)
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "forged gate.passed w/o contract BLOCKs" 2 "$?"

# --- 4. Unresolved BLOCKING finding in a report → BLOCK naming the report ---
D=$(new_phase blocking)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'Findings\nBLOCKING: IDOR in GET /users/:id\n' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "unresolved BLOCKING report BLOCKs (named)" 2 "$?" "security_review.md"

# --- 5. Roster FLOOR: impl agent present but reviewer dropped from roster → BLOCK ---
D=$(new_phase thin_roster)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","code_quality_verifier"]}
J
for a in backend_developer code_reviewer_I code_reviewer_II code_quality_verifier; do
  echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":null,\"ts\":\"t\"}" >> "$D/agent_state/phases/1/execution.jsonl"
done
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "thin roster (drops security_reviewer) BLOCKs on FLOOR" 2 "$?" "FLOOR"

# --- 6. Docs-only phase (no impl agent) → floor not required → PASS ---
D=$(new_phase docs_only)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["documentation_agent"]}
J
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "docs-only phase (no floor) PASSes" 0 "$?"

# --- 7. Valid gate.forced overrides a finding-blocker → FORCED PASS (exit 0) ---
D=$(new_phase forced_ok)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'Findings\nBLOCKING: accepted risk\n' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"gate_item":"security_review","details":"x"}],"user_rationale":"accepted, tracked"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "valid gate.forced → FORCED PASS" 0 "$?" "FORCED PASS"

# --- 8. gate.forced must NOT override a structurally incomplete roster → still BLOCK ---
D=$(new_phase forced_incomplete)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","security_reviewer","code_quality_verifier"]}
J
echo '{"agent":"backend_developer","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"x":1}],"user_rationale":"skip everything"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "gate.forced does NOT bypass incomplete roster" 2 "$?"

# --- 9. Empty gate.forced must not disarm the gate → BLOCK ---
D=$(new_phase forced_empty)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/s.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'BLOCKING: x\n' > "$D/agent_state/phases/1/reports/s.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "empty gate.forced does NOT disarm gate" 2 "$?"

echo "────────────────────────────────────────────"
echo "verify-gate.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
