#!/usr/bin/env bash
# autonomous-continue.sh — Stop hook that keeps a /autonomous run going.
#
# The failure it fixes: /autonomous chains many sub-commands (/init, /discuss, /plan, /design,
# /develop, /accept). Each ends by printing "▶ Next: /plan ..." and the model ends its turn, so the
# user had to re-type the next command even though they started /autonomous.
#
# Contract: /autonomous writes agent_state/autonomous/run.json:
#   {"active":true,"status":"running|awaiting_human|paused|complete|failed|stalled",
#    "session_id":null|"<bound session>","phase":N,"step":"<done>","next_step":"<to run>","updated":"<iso>"}
#
# While status == "running", ending the turn is blocked with a JSON {"decision":"block","reason":…}
# naming the next step. It does NOT block when:
#   - status is awaiting_human / paused / complete / failed / stalled (legitimate stops);
#   - the Stop input lists background_tasks or session_crons: the session is waiting for background
#     agents (subagents run in the background by default) and will be woken by their notification —
#     blocking here used to mark healthy /develop runs "stalled" (review 2026-09-30, A2);
#   - the stop comes from a different session than the one the run is bound to (A4). The first Stop
#     after Step 0 / --resume binds the run (run.json.session_id null → this session);
#   - the run made NO progress across MAX_NUDGES blocked stops. Progress is a fingerprint over
#     run.json.updated, the newest wave checkpoint, execution.jsonl line counts and git state, so
#     several turns inside one long /develop step are not mistaken for a stall (A3). A stuck run is
#     marked "stalled" and allowed to end instead of looping.
# Do not add a stop_hook_active early-exit: it stays true for the rest of the user turn, which would
# allow only one continuation (Claude Code v2.1.285). Claude Code's own cap stops 8 consecutive
# blocks without tool use, which only a genuinely stuck loop hits.
set -uo pipefail

MAX_NUDGES="${AUTONOMOUS_MAX_NUDGES:-3}"
INPUT="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

field() { printf '%s' "$INPUT" | jq -r "$1" 2>/dev/null; }
DIR="$(field '.cwd // empty')"; DIR="${DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
SESSION="$(field '.session_id // empty')"
RUN="$DIR/agent_state/autonomous/run.json"

[ -f "$RUN" ] || exit 0
jq -e . "$RUN" >/dev/null 2>&1 || exit 0
[ "$(jq -r '.active // false' "$RUN")" = "true" ] && [ "$(jq -r '.status // ""' "$RUN")" = "running" ] || exit 0

# Supervised per-step mode (scripts/startup-autonomous-run.sh --session-mode per-step): the supervisor
# writes step_boundary.json with the (phase, next_step) at launch and its own pid. Once the run has
# moved past that step, the turn may end; the supervisor starts the next step in a fresh session.
# A boundary whose supervisor is gone is stale and ignored.
B="$DIR/agent_state/autonomous/step_boundary.json"
if [ -f "$B" ] && jq -e . "$B" >/dev/null 2>&1; then
  bpid="$(jq -r '.supervisor_pid // empty' "$B")"
  if [ -n "$bpid" ] && kill -0 "$bpid" 2>/dev/null \
     && [ "$(jq -r '"\(.phase // "")|\(.next_step // "")"' "$B")" != "$(jq -r '"\(.phase // "")|\(.next_step // "")"' "$RUN")" ]; then
    exit 0
  fi
fi

# Waiting on background work is not a stop: let the turn end without spending a nudge.
pending="$(field '((.background_tasks // []) | length) + ((.session_crons // []) | length)')"
[ "${pending:-0}" -gt 0 ] 2>/dev/null && exit 0

write_run() { local tmp; tmp="$(mktemp)" && jq "$@" "$RUN" > "$tmp" && mv "$tmp" "$RUN"; }

# Session binding: first stop after Step 0 / --resume claims the run; other sessions are ignored.
bound="$(jq -r '.session_id // empty' "$RUN")"
if [ -n "$SESSION" ]; then
  if [ -z "$bound" ]; then write_run --arg s "$SESSION" '.session_id = $s'
  elif [ "$bound" != "$SESSION" ]; then exit 0
  fi
fi

# Progress fingerprint (portable: macOS bash 3.2 / BSD tools and Linux).
# GNU stat first: GNU `stat -f %m` prints file-system info to stdout, so a BSD-first form yields junk on Linux
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }
newest_ckpt="$(ls -t "$DIR"/agent_state/phases/*/checkpoints/*.json 2>/dev/null | head -1)"
exec_lines="$(cat "$DIR"/agent_state/phases/*/execution.jsonl 2>/dev/null | wc -l | tr -d ' ')"
git_state="$(git -C "$DIR" rev-parse HEAD 2>/dev/null)$(git -C "$DIR" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
hash() { if command -v shasum >/dev/null 2>&1; then shasum | cut -c1-16; else sha1sum | cut -c1-16; fi; }
fp="$(printf '%s|%s|%s|%s' "$(jq -r '.updated // ""' "$RUN")" "${newest_ckpt:+$(mtime "$newest_ckpt")}" "$exec_lines" "$git_state" | hash)"

last="$(jq -r '.last_progress_fp // ""' "$RUN")"
nudges="$(jq -r '.nudges // 0' "$RUN")"
if [ "$fp" = "$last" ]; then nudges=$((nudges + 1)); else nudges=1; fi

if [ "$nudges" -gt "$MAX_NUDGES" ]; then
  write_run '.status = "stalled" | .stalled_reason = "no progress (run.json, checkpoints, execution log, git) across repeated stops"'
  echo "autonomous-continue: run marked stalled (no progress across ${MAX_NUDGES} stops); allowing stop." >&2
  exit 0
fi
write_run --arg f "$fp" --argjson n "$nudges" '.last_progress_fp = $f | .nudges = $n'

phase="$(jq -r '.phase // "?"' "$RUN")"
next="$(jq -r '.next_step // "the next step in /autonomous"' "$RUN")"
reason="⏩ /autonomous run is still in progress (phase ${phase}, next step: ${next}). Do not end the turn. A sub-command's \"▶ Next: …\" line is for standalone use only; under /autonomous continue directly with ${next} as described in the autonomous command, and update agent_state/autonomous/run.json when it completes. Only stop by setting run.json status to awaiting_human (the checkpoint or a security pause), paused (with a reason), failed, or complete."
jq -nc --arg r "$reason" '{decision: "block", reason: $r}'
exit 0
