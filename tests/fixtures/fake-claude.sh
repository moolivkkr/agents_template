#!/bin/bash
# fake-claude.sh — stand-in for `claude -p` in tests/autonomous-supervisor.test.sh. Never calls a model.
# Each invocation pops the next action from $FAKE_PLAN (comma-separated; counter in $FAKE_DIR/n),
# appends its argv to $FAKE_DIR/argv.log, emits stream-json on stdout and mutates run.json like a real
# /autonomous session would. Actions:
#   done        status complete, active false           human     status awaiting_human
#   progress    advance next_step, stay running, rc 0   crash     no result, rc 1, run.json untouched
#   stall       status stalled                          failed    status failed
#   billing     StopFailure billing_error → paused      ratelimit StopFailure rate_limit, still running
#   paused      status paused (escalation)              cost=N    result total_cost_usd N, no progress
#   clock=N     advance the clock file by N seconds     hang      wait for a signal (records INT/TERM)
#   nostate     delete run.json and exit 1 (pre-flight failure)
# A missing run.json is created first (Step 0), unless the action is nostate.
set -u
D="${FAKE_DIR:?}"; RUN="$PWD/agent_state/autonomous/run.json"
n=$(( $(cat "$D/n" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$D/n"
printf '%s\n' "$*" >> "$D/argv.log"
action="$(printf '%s' "${FAKE_PLAN:-done}" | cut -d, -f"$n")"; action="${action:-done}"
sid=""; prev=""
for a in "$@"; do
  case "$prev" in --session-id|--resume) sid="$a" ;; esac; prev="$a"
done
sid="${sid:-00000000-0000-4000-8000-000000000000}"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
upd() { local t; t="$(mktemp)"; jq "$@" "$RUN" > "$t" && mv "$t" "$RUN"; }
emit_init() { jq -nc --arg s "$sid" '{type:"system",subtype:"init",session_id:$s}'; }
emit_result() { jq -nc --arg s "$sid" --argjson c "${1:-0.10}" --arg st "${2:-success}" '{type:"result",subtype:$st,is_error:false,total_cost_usd:$c,session_id:$s}'; }

mkdir -p "$(dirname "$RUN")"
if [ ! -f "$RUN" ] && [ "$action" != "nostate" ]; then
  jq -n --arg now "$now" '{active:true,status:"running",session_id:null,phase:0,step:"preflight_complete",next_step:"init",started:"2026-10-01T00:00:00Z",updated:$now,error_count:0}' > "$RUN"
fi
case "$action" in
  done)      emit_init; upd --arg u "$now-$n" '.status="complete" | .active=false | .updated=$u'; emit_result 0.10 ;;
  human)     emit_init; upd --arg u "$now-$n" '.status="awaiting_human" | .next_step="develop" | .updated=$u'; emit_result 0.10 ;;
  progress)  emit_init; upd --arg u "$now-$n" --arg s "step$n" '.step=.next_step | .next_step=$s | .updated=$u'; emit_result 0.10 ;;
  crash)     echo "boom" >&2; exit 1 ;;
  stall)     emit_init; upd '.status="stalled"'; emit_result 0.10 ;;
  failed)    emit_init; upd '.status="failed"'; emit_result 0.10 ;;
  paused)    emit_init; upd '.status="paused" | .reason="escalation limit"'; emit_result 0.10 ;;
  billing)   emit_init; upd '.status="paused" | .reason="API error: billing_error" | .last_error={type:"billing_error",kind:"permanent",details:"x"} | .error_count=((.error_count//0)+1)'; exit 1 ;;
  ratelimit) emit_init; upd '.last_error={type:"rate_limit",kind:"transient",details:"Rate limit exceeded. Retry after 0 seconds."} | .error_count=((.error_count//0)+1)'; exit 1 ;;
  cost=*)    emit_init; emit_result "${action#cost=}" ;;
  clock=*)   emit_init; c="$(cat "$AUTONOMOUS_SUPERVISOR_CLOCK_FILE")"; echo $((c + ${action#clock=})) > "$AUTONOMOUS_SUPERVISOR_CLOCK_FILE"; emit_result 0.01 ;;
  hang)      emit_init
             trap 'echo INT >> "$D/signals"; exit 130' INT
             trap 'echo TERM >> "$D/signals"; exit 143' TERM
             echo ready > "$D/hanging"
             i=0; while [ "$i" -lt 300 ]; do sleep 0.1; i=$((i + 1)); done ;;
  nostate)   rm -f "$RUN"; echo "requirements/ empty" >&2; exit 1 ;;
esac
exit 0
