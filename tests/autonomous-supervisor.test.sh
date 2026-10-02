#!/usr/bin/env bash
# autonomous-supervisor.test.sh — scripts/startup-autonomous-run.sh, the outer loop for /autonomous
# (review 2026-09-30 §5/§6 P1). Every case drives the supervisor with tests/fixtures/fake-claude.sh as
# `claude` (scripted stream-json + run.json mutations); no real `claude -p` is ever launched.
# The supervisor runs under /bin/bash explicitly, which is bash 3.2 on macOS.
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
SUP="$ROOT/scripts/startup-autonomous-run.sh"
FAKE="$TEST_DIR/fixtures/fake-claude.sh"
HOOK="$ROOT/.claude/hooks/autonomous-continue.sh"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export AUTONOMOUS_NOTIFY=0 AUTONOMOUS_BACKOFF_BASE=0 AUTONOMOUS_BACKOFF_MAX=0 AUTONOMOUS_RATE_LIMIT_WAIT=0 \
       AUTONOMOUS_SUPERVISOR_POLL=0.05 AUTONOMOUS_SUPERVISOR_KILL_GRACE=2
unset AUTONOMOUS_MAX_COST_USD AUTONOMOUS_MAX_HOURS AUTONOMOUS_MAX_RESTARTS AUTONOMOUS_COMMAND AUTONOMOUS_SESSION_MODE 2>/dev/null || true

# new_proj NAME → fresh project dir + fake state dir; prints the project path
new_proj() { local p="$T/$1"; mkdir -p "$p/agent_state/autonomous" "$p/fake"; printf '%s' "$p"; }
# sup PROJECT PLAN [supervisor args…] → runs the supervisor; sets RC
sup() {
  local p="$1" plan="$2"; shift 2
  ( cd "$p" && FAKE_DIR="$p/fake" FAKE_PLAN="$plan" /bin/bash "$SUP" --claude-bin "$FAKE" "$@" ) >"$p/fake/out" 2>&1
  RC=$?
}
runj() { jq -r "$2" "$1/agent_state/autonomous/run.json" 2>/dev/null; }
supj() { jq -r "$2" "$1/agent_state/autonomous/supervisor.json" 2>/dev/null; }
calls() { cat "$1/fake/n" 2>/dev/null || echo 0; }

echo "── portability"
/bin/bash -n "$SUP" && ok "parses under /bin/bash ($(/bin/bash -c 'echo $BASH_VERSION'))" || bad "syntax error under /bin/bash"
b4="$(cat "$SUP" "$FAKE" | grep -vE "^[[:space:]]*#" | grep -nE '\$\{[A-Za-z_]+(,,|\^\^)|declare -A|local -A|mapfile|readarray|\|&|&>>|grep -[A-Za-z]*P|coproc' || true)"
[ -z "$b4" ] && ok "no bash-4-only syntax or grep -P" || { bad "bash-4 / grep -P constructs:"; printf '%s\n' "$b4" | sed 's/^/      /'; }
[ -x "$SUP" ] && ok "supervisor is executable" || bad "supervisor not executable"

P="$(new_proj usage)"; sup "$P" done --max-hours soon
[ "$RC" = 31 ] && [ "$(calls "$P")" = 0 ] && [ ! -d "$P/agent_state/autonomous/supervisor-runs" ] && ok "bad budget → exit 31 before touching anything" || bad "usage error handling (rc=$RC)"
sup "$P" done --session-mode sometimes; [ "$RC" = 31 ] && ok "bad --session-mode → exit 31" || bad "bad session mode accepted (rc=$RC)"

echo "── done"
P="$(new_proj done)"; sup "$P" done
[ "$RC" = 0 ] && ok "complete → exit 0" || bad "complete should exit 0 (rc=$RC)"
argv="$(head -1 "$P/fake/argv.log")"
for f in "-p" "--output-format stream-json" "--verbose" "--permission-mode auto" "--permission-prompts none" "--session-id "; do
  case "$argv" in *"$f"*) ;; *) bad "claude argv lacks '$f': $argv"; continue ;; esac
done
case "$argv" in *"-p /startup:autonomous "*|*"-p /startup:autonomous"*) ok "fresh run: /startup:autonomous with the verified flags" ;; *) bad "unexpected prompt: $argv" ;; esac
[ "$(runj "$P" .supervisor.exit_code)" = 0 ] && [ "$(runj "$P" .supervisor.state)" = complete ] && ok "outcome recorded in run.json .supervisor" || bad "run.json .supervisor not written"
grep -q 'exit 0 (complete)' "$P/agent_state/autonomous/supervisor.log" && ok "outcome in supervisor.log" || bad "supervisor.log missing outcome"
[ -s "$P/agent_state/autonomous/supervisor-runs/attempt-1.stream.jsonl" ] && ok "stream-json captured per attempt" || bad "stream not captured"
[ ! -d "$P/agent_state/autonomous/supervisor.lock" ] && ok "lock released on exit" || bad "lock left behind"
sup "$P" done; [ "$RC" = 0 ] && [ "$(calls "$P")" = 1 ] && ok "already-complete run: exit 0 without launching claude" || bad "complete run relaunched (rc=$RC calls=$(calls "$P"))"

echo "── command name"
P="$(new_proj cmdname)"; mkdir -p "$P/.claude/commands"; touch "$P/.claude/commands/autonomous.md"
sup "$P" done; grep -q -- '-p /autonomous' "$P/fake/argv.log" && ok "framework repo (project command present) → /autonomous" || bad "should use /autonomous inside the framework repo"
P="$(new_proj cmdflag)"; sup "$P" done --command /my:autonomous; grep -q -- '-p /my:autonomous' "$P/fake/argv.log" && ok "--command overrides the name" || bad "--command ignored"
P="$(new_proj passthru)"; sup "$P" done -- --skip_init --max_phases=2
grep -q -- '/startup:autonomous --skip_init --max_phases=2' "$P/fake/argv.log" && ok "args after -- go to a fresh run" || bad "passthrough args lost: $(cat "$P/fake/argv.log")"

echo "── awaiting_human"
P="$(new_proj human)"; sup "$P" progress,human
[ "$RC" = 10 ] && ok "awaiting_human → exit 10" || bad "awaiting_human should exit 10 (rc=$RC)"
grep -q 'waiting for a human' "$P/fake/out" && ok "clear message names the wait" || bad "no human-facing message"
sed -n 2p "$P/fake/argv.log" | grep -q -- '--resume' && ok "second launch resumes (prompt --resume, same session)" || bad "restart did not resume"
s1="$(sed -n 1p "$P/fake/argv.log" | sed -nE 's/.*--session-id ([^ ]+).*/\1/p')"; s2="$(sed -n 2p "$P/fake/argv.log" | sed -nE 's/.*--resume ([^ ]+).*/\1/p')"
[ -n "$s1" ] && [ "$s1" = "$s2" ] && ok "resume mode reuses the session id ($s1)" || bad "session ids differ: '$s1' vs '$s2'"
c="$(calls "$P")"; sup "$P" done; [ "$RC" = 10 ] && [ "$(calls "$P")" = "$c" ] && ok "re-run while awaiting_human: exit 10 without launching" || bad "relaunched an awaiting_human run"

echo "── crash → restart → done"
P="$(new_proj crash)"; sup "$P" crash,stall,done
[ "$RC" = 0 ] && [ "$(calls "$P")" = 3 ] && ok "crash and stall restarted, then done (3 launches)" || bad "crash/stall recovery wrong (rc=$RC calls=$(calls "$P"))"
[ "$(supj "$P" .restarts)" = 2 ] && ok "restarts counted (2)" || bad "restarts=$(supj "$P" .restarts)"
grep -q 'restart 1/10' "$P/agent_state/autonomous/supervisor.log" && ok "restart logged with budget" || bad "restart not logged"

echo "── max_restarts"
P="$(new_proj maxr)"; sup "$P" crash,crash,crash,done --max-restarts 2
[ "$RC" = 20 ] && [ "$(calls "$P")" = 3 ] && ok "max_restarts=2 → exit 20 after 3 launches" || bad "max_restarts (rc=$RC calls=$(calls "$P"))"
[ "$(runj "$P" .status)" = paused ] && runj "$P" .reason | grep -q max_restarts && ok "breach pauses run.json with the reason" || bad "breach not recorded in run.json"
[ "$(runj "$P" .supervisor.exit_code)" = 20 ] && ok "exit code recorded in run.json" || bad "exit code not in run.json"
P="$(new_proj failedr)"; sup "$P" failed,done; [ "$RC" = 0 ] && ok "status failed → restarted" || bad "failed should restart (rc=$RC)"

echo "── max_cost_usd"
P="$(new_proj cost)"; sup "$P" cost=0.6,cost=1.2,done --max-cost-usd 1
[ "$RC" = 21 ] && [ "$(calls "$P")" = 2 ] && ok "max_cost_usd=1 → exit 21 once the run's cost ≥ 1" || bad "max_cost (rc=$RC calls=$(calls "$P"))"
[ "$(supj "$P" .total_cost_usd)" = 1.2 ] && ok "cost read from stream-json result total_cost_usd" || bad "total_cost_usd=$(supj "$P" .total_cost_usd)"
sed -n 2p "$P/fake/argv.log" | grep -q -- '--max-budget-usd 0.4000' && ok "remaining budget passed to claude --max-budget-usd" || bad "no --max-budget-usd: $(sed -n 2p "$P/fake/argv.log")"
# Resumed session: total_cost_usd is cumulative, so the latest value replaces (no double count).
P="$(new_proj costresume)"; jq -n '{active:true,status:"running",phase:1,next_step:"plan",started:"s",updated:"u",error_count:0}' > "$P/agent_state/autonomous/run.json"
sup "$P" cost=0.5,cost=0.8,done --max-cost-usd 5
[ "$(supj "$P" .total_cost_usd)" = 0.9 ] && ok "resumed session: a larger total_cost_usd replaces (cumulative, no double count); a smaller one is added (0.8 + 0.1)" || bad "resumed cost=$(supj "$P" .total_cost_usd) (want 0.9)"
P="$(new_proj costenv)"; AUTONOMOUS_MAX_COST_USD=0.05 sup "$P" cost=0.1,done; [ "$RC" = 21 ] && ok "budget from env" || bad "env budget ignored (rc=$RC)"
P="$(new_proj costcfg)"; echo '{"max_cost_usd":0.05}' > "$P/agent_state/autonomous/supervisor.config.json"; sup "$P" cost=0.1,done
[ "$RC" = 21 ] && ok "budget from supervisor.config.json" || bad "config budget ignored (rc=$RC)"

echo "── max_hours (injected clock)"
P="$(new_proj hours)"; CF="$P/fake/clock"; echo 1000000 > "$CF"
AUTONOMOUS_SUPERVISOR_CLOCK_FILE="$CF" sup "$P" clock=7200,crash,done --max-hours 1
[ "$RC" = 22 ] && [ "$(calls "$P")" = 1 ] && ok "max_hours=1 → exit 22 when the clock passes the deadline" || bad "max_hours (rc=$RC calls=$(calls "$P"))"
P="$(new_proj hoursrun)"; CF="$P/fake/clock"; echo 1000000 > "$CF"
( sleep 1; echo 1010000 > "$CF" ) & bump=$!
AUTONOMOUS_SUPERVISOR_CLOCK_FILE="$CF" sup "$P" hang --max-hours 1; wait "$bump" 2>/dev/null
[ "$RC" = 22 ] && grep -q INT "$P/fake/signals" 2>/dev/null && ok "deadline during a run: child sent SIGINT, exit 22" || bad "running child not stopped at deadline (rc=$RC)"

echo "── API errors"
P="$(new_proj billing)"; sup "$P" billing,done
[ "$RC" = 12 ] && [ "$(calls "$P")" = 1 ] && ok "billing_error → exit 12, not retried" || bad "billing (rc=$RC calls=$(calls "$P"))"
P="$(new_proj rate)"; sup "$P" ratelimit,done
[ "$RC" = 0 ] && grep -q 'rate_limit' "$P/agent_state/autonomous/supervisor.log" && ok "rate_limit → wait (Retry-After parsed) and resume" || bad "rate_limit handling (rc=$RC)"
P="$(new_proj stale)"; jq -n '{active:true,status:"running",phase:1,next_step:"plan",started:"s",updated:"u",error_count:3,last_error:{type:"billing_error",kind:"permanent"}}' > "$P/agent_state/autonomous/run.json"
sup "$P" done; [ "$RC" = 0 ] && ok "an OLD billing error (fixed, then re-run) does not stop the run" || bad "stale billing error stopped the run (rc=$RC)"
P="$(new_proj paused)"; sup "$P" paused; [ "$RC" = 11 ] && ok "paused (escalation) → exit 11" || bad "paused should exit 11 (rc=$RC)"
P="$(new_proj nostate)"; sup "$P" nostate; [ "$RC" = 32 ] && ok "no run.json after launch → exit 32" || bad "no-state should exit 32 (rc=$RC)"

echo "── lock"
P="$(new_proj lock)"; mkdir "$P/agent_state/autonomous/supervisor.lock"; sleep 30 & holder=$!; echo "$holder" > "$P/agent_state/autonomous/supervisor.lock/pid"
sup "$P" done; [ "$RC" = 30 ] && [ "$(calls "$P")" = 0 ] && ok "live lock holder → exit 30, claude not launched" || bad "lock contention (rc=$RC)"
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null
sup "$P" done; [ "$RC" = 0 ] && ok "stale lock (dead holder) reclaimed" || bad "stale lock not reclaimed (rc=$RC)"

echo "── signals"
P="$(new_proj sigterm)"
# Job control on, so the backgrounded supervisor doesn't start with SIGINT ignored (a non-interactive
# shell's async children do; an ignored-on-entry signal can't be trapped, and the child would inherit it).
set -m
( cd "$P" && FAKE_DIR="$P/fake" FAKE_PLAN="hang" exec /bin/bash "$SUP" --claude-bin "$FAKE" ) >"$P/fake/out" 2>&1 &
spid=$!; i=0; while [ ! -f "$P/fake/hanging" ] && [ "$i" -lt 100 ]; do sleep 0.1; i=$((i+1)); done
kill -TERM "$spid"; wait "$spid"; RC=$?; set +m
[ "$RC" = 143 ] && ok "SIGTERM → supervisor exits 143" || bad "SIGTERM exit code $RC"
grep -q INT "$P/fake/signals" 2>/dev/null && ok "signal forwarded to the child (SIGINT first, so its turn ends cleanly)" || bad "child never got the signal"
[ "$(runj "$P" .supervisor.state)" = interrupted ] && ok "interruption recorded in run.json" || bad "interruption not recorded"
[ ! -d "$P/agent_state/autonomous/supervisor.lock" ] && ok "lock released after SIGTERM" || bad "lock left after SIGTERM"

echo "── per-step session mode"
P="$(new_proj perstep)"; sup "$P" progress,progress,done --session-mode per-step
[ "$RC" = 0 ] && [ "$(calls "$P")" = 3 ] && ok "per-step: one launch per step, then done" || bad "per-step (rc=$RC calls=$(calls "$P"))"
[ "$(supj "$P" .total_cost_usd)" = 0.3 ] && ok "per-step: costs of distinct sessions are summed (3 x 0.1)" || bad "per-step cost=$(supj "$P" .total_cost_usd)"
[ "$(supj "$P" .restarts)" = 0 ] && ok "step continuations are not restarts" || bad "per-step counted restarts=$(supj "$P" .restarts)"
grep -q -- '--one_step' "$P/fake/argv.log" && ! grep -q -- '--resume [0-9a-f]\{8\}-' "$P/fake/argv.log" && ok "fresh session per step (--one_step, never --resume <id>)" || bad "per-step argv wrong"
s="$(sed -nE 's/.*--session-id ([^ ]+).*/\1/p' "$P/fake/argv.log" | sort -u | wc -l | tr -d ' ')"; [ "$s" = 3 ] && ok "3 distinct session ids" || bad "session ids not distinct ($s)"

echo "── Stop hook honours the per-step boundary"
H="$T/hook"; mkdir -p "$H/agent_state/autonomous"; R="$H/agent_state/autonomous/run.json"; BND="$H/agent_state/autonomous/step_boundary.json"
decide() { jq -nc --arg c "$H" '{cwd:$c, session_id:"s1", hook_event_name:"Stop", background_tasks:[], session_crons:[]}' | bash "$HOOK" 2>/dev/null | jq -e '.decision=="block"' >/dev/null 2>&1 && echo block || echo allow; }
jq -n '{active:true,status:"running",session_id:null,phase:1,next_step:"design",updated:"u1"}' > "$R"
jq -n --argjson p "$$" '{supervisor_pid:$p, phase:"1", next_step:"plan"}' > "$BND"
[ "$(decide)" = allow ] && ok "step moved past the boundary → turn may end" || bad "boundary passed but hook blocked"
jq -n --argjson p "$$" '{supervisor_pid:$p, phase:"1", next_step:"design"}' > "$BND"
[ "$(decide)" = block ] && ok "still on the boundary step → block" || bad "hook allowed stop mid-step"
jq -n '{supervisor_pid:999999, phase:"1", next_step:"plan"}' > "$BND"
[ "$(decide)" = block ] && ok "stale boundary (supervisor gone) ignored" || bad "stale boundary honoured"

echo "── dry run + docs wiring"
P="$(new_proj dry)"; out="$( cd "$P" && /bin/bash "$SUP" --dry-run --claude-bin claude --max-cost-usd 3 )"
printf '%s' "$out" | grep -q -- '--permission-prompts none' && printf '%s' "$out" | grep -q -- '--max-budget-usd 3.0000' && ok "--dry-run prints the claude command" || bad "dry run output: $out"
grep -q 'startup-autonomous-run' "$ROOT/install.sh" && ok "install.sh ships the supervisor" || bad "install.sh does not ship the supervisor"
grep -q 'startup-autonomous-run.sh' "$ROOT/docs/AUTONOMOUS_GUIDE.md" && grep -q 'startup-autonomous-run.sh' "$ROOT/.claude/commands/autonomous.md" && ok "guide + command document the supervisor" || bad "supervisor not documented"
grep -qE '^  - name: one_step' "$ROOT/.claude/commands/autonomous.md" && ok "/autonomous defines --one_step" || bad "/autonomous lacks one_step"
for code in 0 10 11 12 20 21 22 30 31 32 129 130 143; do
  grep -qE "^\| *\`?$code\`? *\|" "$ROOT/docs/AUTONOMOUS_GUIDE.md" || { bad "exit code $code missing from the guide's table"; continue; }
done
ok "exit-code table checked"

echo "────────────────────────────────────────────"
echo "autonomous-supervisor.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
