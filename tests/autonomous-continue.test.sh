#!/usr/bin/env bash
# autonomous-continue.test.sh — the /autonomous Stop/StopFailure/SessionStart hooks:
#   - block mid-run stops (JSON decision:block naming the next step), allow legitimate ones;
#   - never block while background tasks are pending (review 2026-09-30, A2);
#   - bind the run to one session and ignore others (A4);
#   - judge progress by a fingerprint (run.json, checkpoints, execution log, git), not run.json alone (A3);
#   - give up (mark "stalled") after MAX_NUDGES no-progress stops, so they can never loop forever;
#   - StopFailure records API errors; permanent ones pause the run (A5);
#   - SessionStart(compact/resume) restates the run position (A6).
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
H="$TEST_DIR/../.claude/hooks"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/agent_state/autonomous" "$T/agent_state/phases/1/checkpoints"
RUN="$T/agent_state/autonomous/run.json"
stop_input() { jq -nc --arg c "$T" --arg s "${1:-sess-A}" --argjson bg "${2:-[]}" '{cwd:$c, session_id:$s, hook_event_name:"Stop", background_tasks:$bg, session_crons:[]}'; }
# Prints "block" if the hook emitted decision:block, else "allow".
decide() { local out; out="$(stop_input "$@" | bash "$H/autonomous-continue.sh" 2>/dev/null)"; printf '%s' "$out" | jq -e '.decision=="block"' >/dev/null 2>&1 && echo block || echo allow; }
running() { jq -n --arg u "${1:-t1}" '{active:true,status:"running",session_id:null,phase:2,next_step:"plan",updated:$u}' > "$RUN"; }

rm -f "$RUN"; [ "$(decide)" = "allow" ] && ok "no run.json → allow" || bad "no run.json should allow"
for st in awaiting_human paused complete failed stalled; do
  jq -n --arg s "$st" '{active:true,status:$s,updated:"t1"}' > "$RUN"
  [ "$(decide)" = "allow" ] && ok "status=$st → allow" || bad "status=$st should allow"
done
jq -n '{active:false,status:"running",updated:"t1"}' > "$RUN"; [ "$(decide)" = "allow" ] && ok "active=false → allow" || bad "inactive run should allow"

running; [ "$(decide)" = "block" ] && ok "running → block" || bad "running should block"
[ "$(jq -r .session_id "$RUN")" = "sess-A" ] && ok "first stop binds the run to its session" || bad "session not bound"
msg="$(stop_input | bash "$H/autonomous-continue.sh" 2>/dev/null | jq -r .reason)"
printf '%s' "$msg" | grep -q "next step: plan" && ok "block reason names the next step" || bad "reason missing next step"

running; decide >/dev/null   # bind to sess-A
[ "$(decide sess-B)" = "allow" ] && ok "other session → allow (ignored)" || bad "foreign session should be ignored"
[ "$(jq -r '.nudges // 0' "$RUN")" = "1" ] && ok "foreign session spends no nudges" || bad "foreign session changed nudges"

running; n0="$(jq -r '.nudges // 0' "$RUN")"
[ "$(decide sess-A '[{"id":"t1","type":"subagent","status":"running","description":"wave 3"}]')" = "allow" ] \
  && ok "pending background task → allow" || bad "background task should allow stop"
[ "$(jq -r '.nudges // 0' "$RUN")" = "$n0" ] && ok "background wait spends no nudges" || bad "background wait changed nudges"

# No progress: blocks MAX_NUDGES (3) times, then marks stalled and allows.
running t9; r1="$(decide)"; r2="$(decide)"; r3="$(decide)"; r4="$(decide)"
[ "$r1$r2$r3" = "blockblockblock" ] && [ "$r4" = "allow" ] && ok "3 no-progress stops block, 4th allows" || bad "nudge sequence wrong: $r1 $r2 $r3 $r4"
[ "$(jq -r .status "$RUN")" = "stalled" ] && ok "stuck run marked stalled" || bad "stuck run not stalled"

# Progress inside one step (new checkpoint file, run.json unchanged) resets the nudge count.
running t9; decide >/dev/null; decide >/dev/null; decide >/dev/null
echo '{}' > "$T/agent_state/phases/1/checkpoints/wave-2.json"
[ "$(decide)" = "block" ] && [ "$(jq -r .nudges "$RUN")" = "1" ] && ok "checkpoint progress resets nudges" || bad "checkpoint progress not detected"
echo '{"agent":"x","status":"completed"}' >> "$T/agent_state/phases/1/execution.jsonl"
decide >/dev/null; [ "$(jq -r .nudges "$RUN")" = "1" ] && ok "execution-log progress resets nudges" || bad "execution-log progress not detected"

# StopFailure
fail_input() { jq -nc --arg c "$T" --arg e "$1" '{cwd:$c, session_id:"sess-A", hook_event_name:"StopFailure", error:$e, error_details:"x"}'; }
running; jq '.session_id="sess-A"' "$RUN" > "$RUN.t" && mv "$RUN.t" "$RUN"
fail_input rate_limit | bash "$H/autonomous-stopfailure.sh"
[ "$(jq -r .status "$RUN")" = "running" ] && [ "$(jq -r .last_error.type "$RUN")" = "rate_limit" ] && [ "$(jq -r .error_count "$RUN")" = "1" ] \
  && ok "StopFailure transient → recorded, still running" || bad "transient StopFailure handling wrong"
fail_input billing_error | bash "$H/autonomous-stopfailure.sh"
[ "$(jq -r .status "$RUN")" = "paused" ] && jq -r .reason "$RUN" | grep -q billing_error && ok "StopFailure permanent → paused with reason" || bad "permanent StopFailure should pause"

# SessionStart re-orientation
running; out="$(jq -nc --arg c "$T" '{cwd:$c, source:"compact"}' | bash "$H/autonomous-reorient.sh")"
printf '%s' "$out" | grep -q "next step: plan" && printf '%s' "$out" | grep -q "Skill tool" && ok "SessionStart(compact) restates position + rules" || bad "reorient output missing"
jq -n '{active:true,status:"complete"}' > "$RUN"; out="$(jq -nc --arg c "$T" '{cwd:$c, source:"resume"}' | bash "$H/autonomous-reorient.sh")"
[ -z "$out" ] && ok "SessionStart silent for a finished run" || bad "reorient should be silent when complete"

echo "────────────────────────────────────────────"
echo "autonomous-continue.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
