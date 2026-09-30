#!/usr/bin/env bash
# autonomous-continue.sh — Stop hook that keeps a /autonomous run going.
#
# The failure it fixes: /autonomous chains many sub-commands (/init, /discuss, /plan, /design,
# /develop, /accept). Each sub-command ends by printing "▶ Next: /plan ..." and the model ends its
# turn, so the user has to re-type the next command even though they started /autonomous.
#
# Contract: /autonomous writes agent_state/autonomous/run.json:
#   {"active":true,"status":"running|awaiting_human|paused|complete|failed",
#    "phase":N,"step":"<done step>","next_step":"<step to run>","updated":"<iso>"}
# While status == "running", ending the turn is blocked (exit 2) and the model is told the exact
# next step. It stops blocking when:
#   - status is awaiting_human / paused / complete / failed (legitimate stops), or
#   - the run made NO progress (run.json "updated" unchanged) across MAX_NUDGES blocked stops, so a
#     genuinely stuck run ends instead of looping forever. run.json is then marked "stalled".
# Exit 0 = allow stop. Exit 2 = block stop; stderr is shown to the model.
set -uo pipefail

MAX_NUDGES="${AUTONOMOUS_MAX_NUDGES:-2}"
INPUT="$(cat 2>/dev/null || true)"
DIR="$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)"
DIR="${DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
RUN="$DIR/agent_state/autonomous/run.json"

command -v jq >/dev/null 2>&1 || exit 0
[ -f "$RUN" ] || exit 0
jq -e . "$RUN" >/dev/null 2>&1 || exit 0

active="$(jq -r '.active // false' "$RUN")"
status="$(jq -r '.status // ""' "$RUN")"
[ "$active" = "true" ] && [ "$status" = "running" ] || exit 0

updated="$(jq -r '.updated // ""' "$RUN")"
last="$(jq -r '.last_nudged_update // ""' "$RUN")"
nudges="$(jq -r '.nudges // 0' "$RUN")"
if [ "$updated" = "$last" ]; then nudges=$((nudges + 1)); else nudges=1; fi

if [ "$nudges" -gt "$MAX_NUDGES" ]; then
  tmp="$(mktemp)"; jq '.status = "stalled" | .stalled_reason = "no checkpoint progress across repeated stops"' "$RUN" > "$tmp" && mv "$tmp" "$RUN"
  echo "autonomous-continue: run marked stalled (no progress since ${updated}); allowing stop." >&2
  exit 0
fi

tmp="$(mktemp)"
jq --arg u "$updated" --argjson n "$nudges" '.last_nudged_update = $u | .nudges = $n' "$RUN" > "$tmp" && mv "$tmp" "$RUN"

phase="$(jq -r '.phase // "?"' "$RUN")"
next="$(jq -r '.next_step // "the next step in /autonomous"' "$RUN")"
cat >&2 <<EOF
⏩ /autonomous run is still in progress (phase ${phase}, next step: ${next}).
Do not end the turn. A sub-command's "▶ Next: ..." line is for standalone use only; under
/autonomous, continue directly with ${next} as described in the autonomous command, updating
agent_state/autonomous/run.json after it completes.
Only stop by setting run.json "status" to awaiting_human (the Step 3 checkpoint or a security
pause), paused (with a "reason"), failed, or complete.
EOF
exit 2
