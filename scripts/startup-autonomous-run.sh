#!/usr/bin/env bash
# startup-autonomous-run.sh — external supervisor for /startup:autonomous (review 2026-09-30 §5, §6 P1).
#
# The in-session Stop hook (autonomous-continue.sh) keeps ONE session going between steps. It can't
# help once that session is gone: a crash, a hook-marked stall, an API error that ends the turn
# through StopFailure, or a closed terminal. This thin outer loop owns that case. It runs
#   claude -p "<cmd> --resume" --output-format stream-json --verbose \
#          --permission-mode auto --permission-prompts none [--max-budget-usd <remaining>]
# reads agent_state/autonomous/run.json each time the child exits, and decides: done, stop for a
# human, wait, or restart with backoff. It enforces budgets (cost, wall-clock hours, restarts), keeps
# one supervisor per repo, forwards SIGINT/SIGTERM to the child, and notifies locally only.
#
# Usage: startup-autonomous-run.sh [options] [-- <args for a FRESH /autonomous run>]
#   --project DIR          project root (default: current directory)
#   --command CMD          slash command to run (default: /autonomous when the project itself has
#                          .claude/commands/autonomous.md, i.e. the framework repo; else
#                          /startup:autonomous, how install.sh installs it). Env AUTONOMOUS_COMMAND.
#   --session-mode MODE    resume   (default) one long session; a restart resumes the same session id
#                                   (claude -p --resume <id>), as autonomous.md assumes today.
#                          per-step one fresh `claude -p` per pipeline step (/autonomous --one_step);
#                                   meant for a later A/B via /eval.
#   --max-cost-usd N       stop when the summed total_cost_usd reaches N (default: none)
#   --max-hours N          stop after N wall-clock hours since this run was first supervised (default 24)
#   --max-restarts N       stop after N restarts (crash/stall/failed/API error) (default 10)
#   --reset-budgets        start cost/hours/restart counters from zero for this run
#   --permission-mode M    passed to claude (default auto)
#   --claude-bin PATH      claude executable (default: env CLAUDE_BIN or `claude` on PATH)
#   --claude-arg ARG       extra argument for claude, repeatable (e.g. --claude-arg --model --claude-arg opus)
#   --dry-run              print the claude command that would run, then exit 0
#   -h | --help
# Budgets can also come from env (AUTONOMOUS_MAX_COST_USD / _MAX_HOURS / _MAX_RESTARTS), run.json
# `.budgets`, or agent_state/autonomous/supervisor.config.json; precedence flag > env > run.json > config.
#
# Exit codes (also recorded in run.json .supervisor and agent_state/autonomous/supervisor.log):
#    0 run complete                         20 max_restarts exceeded
#   10 awaiting_human (checkpoint/security)  21 max_cost_usd reached
#   11 paused for a human (non-API reason)   22 max_hours reached
#   12 permanent API error (billing, auth…)  30 another supervisor holds the lock
#                                            31 usage error / missing prerequisite (claude, jq)
#                                            32 no run state after launch (Step 0 pre-flight failed)
#  129 SIGHUP, 130 SIGINT, 143 SIGTERM (child is sent SIGINT, then SIGTERM after a grace period)
#
# Portable to macOS bash 3.2 and Linux: no associative arrays, no ${x,,}, no grep -P, no mapfile.
# Test hooks (env): AUTONOMOUS_SUPERVISOR_CLOCK_FILE (epoch seconds read from this file instead of
# `date`), AUTONOMOUS_BACKOFF_BASE / _MAX, AUTONOMOUS_RATE_LIMIT_WAIT, AUTONOMOUS_SUPERVISOR_POLL,
# AUTONOMOUS_SUPERVISOR_KILL_GRACE, AUTONOMOUS_NOTIFY=0 (log only).
set -uo pipefail

PROG="startup-autonomous-run"
EX_DONE=0; EX_HUMAN=10; EX_PAUSED=11; EX_API_PERMANENT=12
EX_MAX_RESTARTS=20; EX_MAX_COST=21; EX_MAX_HOURS=22
EX_LOCKED=30; EX_USAGE=31; EX_NO_RUN=32

PROJECT="$PWD"; CMD="${AUTONOMOUS_COMMAND:-}"; SESSION_MODE="${AUTONOMOUS_SESSION_MODE:-resume}"
F_COST=""; F_HOURS=""; F_RESTARTS=""; RESET_BUDGETS=0; DRY_RUN=0
PERM_MODE="${AUTONOMOUS_PERMISSION_MODE:-auto}"; CLAUDE_BIN="${CLAUDE_BIN:-claude}"
EXTRA=(); PASSTHRU=()

usage() { sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }
die_usage() { echo "$PROG: $*" >&2; exit "$EX_USAGE"; }
need_val() { [ $# -ge 2 ] && [ -n "$2" ] || die_usage "$1 needs a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --project) need_val "$@"; PROJECT="$2"; shift 2 ;;
    --command) need_val "$@"; CMD="$2"; shift 2 ;;
    --session-mode) need_val "$@"; SESSION_MODE="$2"; shift 2 ;;
    --max-cost-usd) need_val "$@"; F_COST="$2"; shift 2 ;;
    --max-hours) need_val "$@"; F_HOURS="$2"; shift 2 ;;
    --max-restarts) need_val "$@"; F_RESTARTS="$2"; shift 2 ;;
    --reset-budgets) RESET_BUDGETS=1; shift ;;
    --permission-mode) need_val "$@"; PERM_MODE="$2"; shift 2 ;;
    --claude-bin) need_val "$@"; CLAUDE_BIN="$2"; shift 2 ;;
    --claude-arg) need_val "$@"; EXTRA[${#EXTRA[@]}]="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; while [ $# -gt 0 ]; do PASSTHRU[${#PASSTHRU[@]}]="$1"; shift; done ;;
    *) die_usage "unknown option: $1 (see --help)" ;;
  esac
done

case "$SESSION_MODE" in resume|per-step) ;; *) die_usage "--session-mode must be resume or per-step" ;; esac
is_num() { printf '%s' "$1" | grep -Eq '^[0-9]+([.][0-9]+)?$'; }
command -v jq >/dev/null 2>&1 || die_usage "jq is required"
[ -d "$PROJECT" ] || die_usage "no such project directory: $PROJECT"
PROJECT="$(cd "$PROJECT" && pwd)"
if [ -z "$CMD" ]; then
  if [ -f "$PROJECT/.claude/commands/autonomous.md" ]; then CMD="/autonomous"; else CMD="/startup:autonomous"; fi
fi

SDIR="$PROJECT/agent_state/autonomous"
RUN="$SDIR/run.json"; STATE="$SDIR/supervisor.json"; LOG="$SDIR/supervisor.log"
LOCK="$SDIR/supervisor.lock"; BOUNDARY="$SDIR/step_boundary.json"; RUNS_DIR="$SDIR/supervisor-runs"
CONFIG="$SDIR/supervisor.config.json"

# ── small helpers ────────────────────────────────────────────────────────────────────────────────
now() {
  local f="${AUTONOMOUS_SUPERVISOR_CLOCK_FILE:-}"
  if [ -n "$f" ] && [ -s "$f" ]; then tr -dc '0-9' < "$f"; else date +%s; fi
}
iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { local m; m="$(iso) $*"; printf '%s\n' "$m" >> "$LOG"; printf '%s: %s\n' "$PROG" "$*" >&2; }
notify() {   # local only: macOS notification, else terminal bell; never a network call
  [ "${AUTONOMOUS_NOTIFY:-1}" = "0" ] && return 0
  if [ "$(uname -s)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$(printf '%s' "$2" | tr -d '"\\')\" with title \"$(printf '%s' "$1" | tr -d '"\\')\"" >/dev/null 2>&1 || true
  elif [ -t 2 ]; then printf '\a' >&2
  fi
}
rj() { [ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1 && jq -r "$1" "$RUN" 2>/dev/null; }
sj() { jq -r "$1" "$STATE" 2>/dev/null; }
st_update() { local t; t="$(mktemp "$SDIR/.sup.XXXXXX")" && jq "$@" "$STATE" > "$t" && mv "$t" "$STATE"; }
gt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a+0 > b+0)}'; }   # a > b, floats
ge() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a+0 >= b+0)}'; }
new_uuid() {
  local u=""
  if command -v uuidgen >/dev/null 2>&1; then u="$(uuidgen)"
  elif [ -r /proc/sys/kernel/random/uuid ]; then u="$(cat /proc/sys/kernel/random/uuid)"
  else u="$(python3 -c 'import uuid;print(uuid.uuid4())' 2>/dev/null)"; fi
  printf '%s' "$u" | tr 'A-F' 'a-f'
}

# ── budgets: flag > env > run.json .budgets > supervisor.config.json > default ─────────────────────
budget() {   # $1 key, $2 flag value, $3 env value, $4 default
  local v="$2"
  [ -n "$v" ] || v="$3"
  [ -n "$v" ] || v="$(rj ".budgets.$1 // empty")"
  [ -n "$v" ] || { [ -f "$CONFIG" ] && v="$(jq -r ".$1 // empty" "$CONFIG" 2>/dev/null)"; }
  [ -n "$v" ] || v="$4"
  printf '%s' "$v"
}
MAX_COST="$(budget max_cost_usd "$F_COST" "${AUTONOMOUS_MAX_COST_USD:-}" "")"
MAX_HOURS="$(budget max_hours "$F_HOURS" "${AUTONOMOUS_MAX_HOURS:-}" 24)"
MAX_RESTARTS="$(budget max_restarts "$F_RESTARTS" "${AUTONOMOUS_MAX_RESTARTS:-}" 10)"
[ -z "$MAX_COST" ] || is_num "$MAX_COST" || die_usage "max_cost_usd must be a number: $MAX_COST"
is_num "$MAX_HOURS" || die_usage "max_hours must be a number: $MAX_HOURS"
printf '%s' "$MAX_RESTARTS" | grep -Eq '^[0-9]+$' || die_usage "max_restarts must be an integer: $MAX_RESTARTS"
BACKOFF_BASE="${AUTONOMOUS_BACKOFF_BASE:-30}"; BACKOFF_MAX="${AUTONOMOUS_BACKOFF_MAX:-900}"
RATE_WAIT="${AUTONOMOUS_RATE_LIMIT_WAIT:-300}"; POLL="${AUTONOMOUS_SUPERVISOR_POLL:-5}"
KILL_GRACE="${AUTONOMOUS_SUPERVISOR_KILL_GRACE:-30}"
mkdir -p "$RUNS_DIR" || die_usage "cannot create $RUNS_DIR"

build_cmd() {   # sets ARGV for one launch; $1 = session flag (--session-id|--resume), $2 = id
  local prompt="$CMD"
  if [ -f "$RUN" ]; then prompt="$prompt --resume"
  elif [ ${#PASSTHRU[@]} -gt 0 ]; then prompt="$prompt ${PASSTHRU[*]}"; fi
  [ "$SESSION_MODE" = "per-step" ] && prompt="$prompt --one_step"
  ARGV=("$CLAUDE_BIN" -p "$prompt" --output-format stream-json --verbose
        --permission-mode "$PERM_MODE" --permission-prompts none "$1" "$2")
  if [ -n "$MAX_COST" ]; then
    local rem; rem="$(awk -v m="$MAX_COST" -v s="$(sj '.total_cost_usd // 0')" 'BEGIN{r=m-s; if(r<0)r=0; printf "%.4f", r}')"
    [ "${AUTONOMOUS_PASS_BUDGET:-1}" = "1" ] && ARGV=("${ARGV[@]}" --max-budget-usd "$rem")
  fi
  [ ${#EXTRA[@]} -gt 0 ] && ARGV=("${ARGV[@]}" "${EXTRA[@]}")
  return 0
}

if [ "$DRY_RUN" = "1" ]; then
  [ -f "$STATE" ] || echo '{}' > "$STATE"
  build_cmd --session-id "<new-uuid>"; printf '%q ' "${ARGV[@]}"; echo; exit 0
fi

# ── single-instance lock (mkdir is atomic; a dead holder's lock is reclaimed) ─────────────────────
acquire_lock() {
  local i holder
  for i in 1 2; do
    if mkdir "$LOCK" 2>/dev/null; then echo "$$" > "$LOCK/pid"; return 0; fi
    holder="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
      echo "$PROG: another supervisor (pid $holder) is running for $PROJECT" >&2; exit "$EX_LOCKED"
    fi
    rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null   # stale: holder is gone
  done
  echo "$PROG: could not take the lock $LOCK" >&2; exit "$EX_LOCKED"
}
acquire_lock
CHILD=""; FINISHED=0
cleanup() { rm -f "$BOUNDARY"; rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT

# ── supervisor state (persisted per run, keyed by run.json .started) ───────────────────────────────
RUN_STARTED="$(rj '.started // empty')"
if [ "$RESET_BUDGETS" = "1" ] || [ ! -f "$STATE" ] || ! jq -e . "$STATE" >/dev/null 2>&1 \
   || { [ -n "$RUN_STARTED" ] && [ "$(sj '.run_started // empty')" != "$RUN_STARTED" ]; }; then
  jq -n --arg rs "$RUN_STARTED" --argjson t "$(now)" \
    '{run_started:$rs, started_epoch:$t, total_cost_usd:0, cost_by_session:{}, restarts:0, attempts:0, session_id:null}' > "$STATE"
fi
st_update --arg m "$SESSION_MODE" --arg c "$MAX_COST" --arg h "$MAX_HOURS" --arg r "$MAX_RESTARTS" --argjson p "$$" \
  '.session_mode=$m | .pid=$p | .state="running" | .budgets={max_cost_usd:($c|if .=="" then null else tonumber end), max_hours:($h|tonumber), max_restarts:($r|tonumber)}'
DEADLINE="$(awk -v s="$(sj .started_epoch)" -v h="$MAX_HOURS" 'BEGIN{printf "%d", s + h*3600}')"

record_run() {   # mirror supervisor state into run.json (only while no child is running)
  [ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1 || return 0
  local t; t="$(mktemp "$SDIR/.run.XXXXXX")"
  jq --slurpfile s "$STATE" --arg now "$(iso)" '.supervisor = ($s[0] | {state, exit_code, exit_reason, session_mode, budgets,
       total_cost_usd, restarts, attempts, session_id, updated: $now})' "$RUN" > "$t" && mv "$t" "$RUN"
}

finish() {   # $1 exit code, $2 state, $3 reason; budget breaches also pause the run so nothing resumes it silently
  FINISHED=1
  st_update --argjson c "$1" --arg s "$2" --arg r "$3" '.exit_code=$c | .state=$s | .exit_reason=$r | .ended=now'
  if [ "$1" -ge 20 ] && [ "$1" -le 22 ] && [ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1; then
    case "$(rj '.status // ""')" in running|stalled|failed)
      local t; t="$(mktemp "$SDIR/.run.XXXXXX")"
      jq --arg r "supervisor: $3 — raise the budget (or --reset-budgets) and re-run the supervisor, or /autonomous --resume" \
        '.status="paused" | .reason=$r' "$RUN" > "$t" && mv "$t" "$RUN" ;;
    esac
  fi
  record_run
  log "exit $1 ($2): $3"
  notify "/autonomous: $2" "$3"
  exit "$1"
}

# ── signals: forward to the child (SIGINT ends its turn cleanly; SIGTERM after a grace period) ───────
on_signal() {
  local sig="$1" code="$2" i=0
  trap '' INT TERM HUP
  log "received SIG$sig"
  if [ -n "$CHILD" ] && kill -0 "$CHILD" 2>/dev/null; then
    kill -INT "$CHILD" 2>/dev/null
    while kill -0 "$CHILD" 2>/dev/null && [ "$i" -lt "$((KILL_GRACE * 10))" ]; do sleep 0.1; i=$((i + 1)); done
    if kill -0 "$CHILD" 2>/dev/null; then kill -TERM "$CHILD" 2>/dev/null; i=0
      while kill -0 "$CHILD" 2>/dev/null && [ "$i" -lt 100 ]; do sleep 0.1; i=$((i + 1)); done
      kill -0 "$CHILD" 2>/dev/null && kill -KILL "$CHILD" 2>/dev/null
    fi
    wait "$CHILD" 2>/dev/null
  fi
  CHILD=""
  finish "$code" "interrupted" "supervisor received SIG$sig; child stopped — re-run the supervisor to continue"
}
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
trap 'on_signal HUP 129' HUP   # closed terminal: the child is in its own process group and would not see it

isleep() { [ "$1" -gt 0 ] 2>/dev/null || return 0; sleep "$1" & wait $!; }   # interruptible by traps

# ── stream-json accounting ──────────────────────────────────────────────────────────────────────────
# total_cost_usd on a result is cumulative for a RESUMED session (Claude Code ≥ 2.1.277: earlier
# spend is restored), so per session we keep the latest value; a smaller value (older CLI, or a crash
# result that reports zero) is added instead of replacing. Run total = sum over sessions.
account() {   # $1 stream file
  local res sid cost
  res="$(jq -R -c 'fromjson? | select(type=="object" and .type=="result")' "$1" 2>/dev/null | tail -1)"
  sid="$(jq -R -r 'fromjson? | select(type=="object") | .session_id // empty' "$1" 2>/dev/null | head -1)"
  [ -n "$sid" ] && [ "$SESSION_MODE" = "resume" ] && st_update --arg s "$sid" '.session_id=$s'
  RESULT_SUBTYPE=""
  [ -n "$res" ] || return 0
  RESULT_SUBTYPE="$(printf '%s' "$res" | jq -r '.subtype // ""')"
  cost="$(printf '%s' "$res" | jq -r '.total_cost_usd // 0')"
  sid="$(printf '%s' "$res" | jq -r '.session_id // empty')"; sid="${sid:-unknown}"
  st_update --arg s "$sid" --argjson c "${cost:-0}" '
    .cost_by_session[$s] = (if $c >= (.cost_by_session[$s] // 0) then $c else (.cost_by_session[$s] // 0) + $c end)
    | .total_cost_usd = (([.cost_by_session[]] | add // 0) * 1000000 | round / 1000000)'
}

check_budgets() {
  local spent; spent="$(sj '.total_cost_usd // 0')"
  if [ -n "$MAX_COST" ] && ge "$spent" "$MAX_COST"; then
    finish "$EX_MAX_COST" "budget_exceeded" "max_cost_usd reached: spent \$$spent of \$$MAX_COST"
  fi
  [ "$(now)" -ge "$DEADLINE" ] && finish "$EX_MAX_HOURS" "budget_exceeded" "max_hours reached (${MAX_HOURS}h)"
  return 0
}

snap() { rj '"\(.phase // "")|\(.step // "")|\(.next_step // "")|\(.updated // "")"'; }

# ── start-up: things a fresh supervisor must not resume over ────────────────────────────────────────
case "$(rj '.status // ""')" in
  complete) finish "$EX_DONE" "complete" "run already complete" ;;
  awaiting_human) finish "$EX_HUMAN" "awaiting_human" "run is waiting for a human: $(rj '.reason // .next_step // "checkpoint"') — answer it in an interactive session (/autonomous --resume), then re-run the supervisor" ;;
esac
log "start: project=$PROJECT cmd=$CMD mode=$SESSION_MODE budgets cost=${MAX_COST:-none} hours=$MAX_HOURS restarts=$MAX_RESTARTS"
[ -n "$MAX_COST" ] || log "warning: no max_cost_usd set; only hours and restarts bound this run"

BACKOFF="$BACKOFF_BASE"
while :; do
  check_budgets
  attempt="$(( $(sj '.attempts // 0') + 1 ))"
  st_update --argjson a "$attempt" '.attempts=$a'
  sid="$(sj '.session_id // empty')"
  if [ "$SESSION_MODE" = "resume" ] && [ -n "$sid" ]; then build_cmd --resume "$sid"
  else sid="$(new_uuid)"; build_cmd --session-id "$sid"; [ "$SESSION_MODE" = "resume" ] && st_update --arg s "$sid" '.session_id=$s'; fi
  before="$(snap)"; err_before="$(rj '.error_count // 0')"; err_before="${err_before:-0}"
  if [ "$SESSION_MODE" = "per-step" ]; then   # the Stop hook lets the turn end once (phase, next_step) moves
    jq -n --argjson p "$$" --arg ph "$(rj '.phase // ""')" --arg ns "$(rj '.next_step // ""')" \
      '{supervisor_pid:$p, phase:$ph, next_step:$ns}' > "$BOUNDARY"
  fi
  record_run
  stream="$RUNS_DIR/attempt-$attempt.stream.jsonl"; errf="$RUNS_DIR/attempt-$attempt.stderr.log"
  log "attempt $attempt: $(printf '%q ' "${ARGV[@]}")"

  set -m   # own process group: a background child of a non-interactive shell otherwise ignores SIGINT
  "${ARGV[@]}" > "$stream" 2> "$errf" < /dev/null &
  CHILD=$!
  set +m
  while kill -0 "$CHILD" 2>/dev/null; do
    if [ "$(now)" -ge "$DEADLINE" ]; then
      log "max_hours reached while attempt $attempt was running; stopping it"
      kill -INT "$CHILD" 2>/dev/null; i=0
      while kill -0 "$CHILD" 2>/dev/null && [ "$i" -lt "$((KILL_GRACE * 10))" ]; do sleep 0.1; i=$((i + 1)); done
      kill -0 "$CHILD" 2>/dev/null && kill -TERM "$CHILD" 2>/dev/null
      wait "$CHILD" 2>/dev/null; CHILD=""; rm -f "$BOUNDARY"; account "$stream"
      finish "$EX_MAX_HOURS" "budget_exceeded" "max_hours reached (${MAX_HOURS}h)"
    fi
    sleep "$POLL" & wait $!
  done
  wait "$CHILD"; rc=$?; CHILD=""
  rm -f "$BOUNDARY"
  account "$stream"
  # A --resume that never started (unknown/unsaved session) must not be retried forever: start fresh.
  if [ "$SESSION_MODE" = "resume" ] && [ "$rc" -ne 0 ] && ! grep -q '"session_id"' "$stream" 2>/dev/null; then
    st_update '.session_id=null'
  fi
  st_update --argjson rc "$rc" --arg sub "$RESULT_SUBTYPE" '.last_exit={rc:$rc, result_subtype:$sub}'
  log "attempt $attempt exited rc=$rc result=${RESULT_SUBTYPE:-none} status=$(rj '.status // "none"') cost_total=\$$(sj '.total_cost_usd')"

  [ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1 \
    || finish "$EX_NO_RUN" "no_run_state" "claude exited (rc=$rc) without a valid run.json — Step 0 pre-flight probably failed; see $errf and $stream"

  status="$(rj '.status // ""')"; err_type="$(rj '.last_error.type // ""')"; err_kind="$(rj '.last_error.kind // ""')"
  err_now="$(rj '.error_count // 0')"; new_err=0; [ "${err_now:-0}" -gt "$err_before" ] 2>/dev/null && new_err=1
  case "$status" in
    complete) finish "$EX_DONE" "complete" "run complete" ;;
    awaiting_human) finish "$EX_HUMAN" "awaiting_human" "waiting for a human: $(rj '.reason // .next_step // "checkpoint"') — answer in an interactive session (/autonomous --resume), then re-run the supervisor" ;;
  esac
  if [ "$new_err" = 1 ] && { [ "$err_type" = "billing_error" ] || [ "$err_kind" = "permanent" ]; }; then
    finish "$EX_API_PERMANENT" "api_error" "permanent API error: $err_type — not retried; fix it, then re-run the supervisor"
  fi
  [ "$status" = "paused" ] && finish "$EX_PAUSED" "paused" "run paused: $(rj '.reason // "no reason given"')"
  [ "$RESULT_SUBTYPE" = "error_max_budget_usd" ] && [ -n "$MAX_COST" ] && \
    finish "$EX_MAX_COST" "budget_exceeded" "max_cost_usd reached inside the run (claude --max-budget-usd): spent \$$(sj .total_cost_usd) of \$$MAX_COST"
  check_budgets

  after="$(snap)"; progressed=0; [ "$after" != "$before" ] && progressed=1
  if [ "$SESSION_MODE" = "per-step" ] && [ "$status" = "running" ] && [ "$progressed" = 1 ] && [ "$rc" -eq 0 ]; then
    log "step done ($before → $after); next step in a fresh session"; BACKOFF="$BACKOFF_BASE"; continue
  fi

  # Everything else is a restart: crash (rc≠0), stalled, failed, or a turn that ended mid-run.
  restarts="$(( $(sj '.restarts // 0') + 1 ))"
  st_update --argjson r "$restarts" '.restarts=$r'
  [ "$restarts" -gt "$MAX_RESTARTS" ] && finish "$EX_MAX_RESTARTS" "budget_exceeded" "max_restarts exceeded ($MAX_RESTARTS); last status=$status rc=$rc"
  [ "$progressed" = 1 ] && BACKOFF="$BACKOFF_BASE"
  wait_s="$BACKOFF"; why="status=${status:-?} rc=$rc"
  if [ "$new_err" = 1 ] && [ "$err_type" = "rate_limit" ]; then
    ra="$(rj '.last_error.details // ""' | sed -nE 's/.*[Rr]etry[- ]after:? *([0-9]+).*/\1/p' | head -1)"
    wait_s="${ra:-$RATE_WAIT}"; why="rate_limit"
  elif [ "$new_err" = 1 ]; then why="api_error=$err_type"
  fi
  if [ "$(( $(now) + wait_s ))" -ge "$DEADLINE" ] && [ "$wait_s" -gt 0 ]; then
    finish "$EX_MAX_HOURS" "budget_exceeded" "max_hours would pass during the ${wait_s}s wait ($why)"
  fi
  log "restart $restarts/$MAX_RESTARTS after ${wait_s}s ($why)"
  st_update --arg w "$why" '.state="waiting" | .last_restart_reason=$w'; record_run
  isleep "$wait_s"
  st_update '.state="running"'
  [ "$progressed" = 1 ] || BACKOFF="$(awk -v b="$BACKOFF" -v m="$BACKOFF_MAX" 'BEGIN{n=b*2; if(n<1)n=b; if(n>m)n=m; printf "%d", n}')"
done
