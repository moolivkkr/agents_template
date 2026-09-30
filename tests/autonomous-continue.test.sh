#!/usr/bin/env bash
# autonomous-continue.test.sh — the Stop hook blocks mid-run stops, allows legitimate ones, and
# gives up (marks "stalled") when the run makes no progress, so it can never loop forever.
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$TEST_DIR/../.claude/hooks/autonomous-continue.sh"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/agent_state/autonomous"
RUN="$T/agent_state/autonomous/run.json"
run_hook() { printf '{"cwd":"%s","hook_event_name":"Stop"}' "$T" | bash "$HOOK" 2>/dev/null; echo $?; }

rm -f "$RUN"; [ "$(run_hook)" = "0" ] && ok "no run.json → stop allowed" || bad "no run.json should allow stop"

for st in awaiting_human paused complete failed; do
  echo "{\"active\":true,\"status\":\"$st\",\"updated\":\"t1\"}" > "$RUN"
  [ "$(run_hook)" = "0" ] && ok "status=$st → stop allowed" || bad "status=$st should allow stop"
done

echo '{"active":true,"status":"running","phase":2,"next_step":"plan","updated":"t1"}' > "$RUN"
[ "$(run_hook)" = "2" ] && ok "running → stop blocked (nudge 1)" || bad "running should block stop"
msg="$(printf '{"cwd":"%s"}' "$T" | bash "$HOOK" 2>&1 >/dev/null)"
printf '%s' "$msg" | grep -q "next step: plan" && ok "block message names the next step" || bad "block message missing next step"
# That was nudge 2 with no progress; the third stop without progress must be allowed + marked stalled.
[ "$(run_hook)" = "0" ] && ok "no progress after max nudges → stop allowed" || bad "stuck run should be allowed to stop"
[ "$(jq -r .status "$RUN")" = "stalled" ] && ok "stuck run marked stalled" || bad "stuck run not marked stalled"

echo '{"active":true,"status":"running","next_step":"design","updated":"t1","nudges":2,"last_nudged_update":"t1"}' > "$RUN"
tmp="$(mktemp)"; jq '.updated="t2"' "$RUN" > "$tmp" && mv "$tmp" "$RUN"
[ "$(run_hook)" = "2" ] && ok "progress made (updated changed) → blocking resumes" || bad "progress should reset nudges"

echo '{"active":false,"status":"running","updated":"t1"}' > "$RUN"
[ "$(run_hook)" = "0" ] && ok "active=false → stop allowed" || bad "inactive run should allow stop"

echo "────────────────────────────────────────────"
echo "autonomous-continue.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
