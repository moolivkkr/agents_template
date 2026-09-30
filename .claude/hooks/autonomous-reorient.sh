#!/usr/bin/env bash
# autonomous-reorient.sh — SessionStart hook (compact / resume): re-inject /autonomous run state.
#
# After compaction, invoked commands come back truncated (5k tokens each, 25k total, oldest first),
# and autonomous.md is invoked first, so its driver rules can drop out of context (review
# 2026-09-30, A6). SessionStart stdout is added to Claude's context, so this restates where the run
# is and what to do next. It speaks only when a run is active and not finished.
set -uo pipefail
INPUT="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0
field() { printf '%s' "$INPUT" | jq -r "$1" 2>/dev/null; }
DIR="$(field '.cwd // empty')"; DIR="${DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
RUN="$DIR/agent_state/autonomous/run.json"
[ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1 || exit 0
[ "$(jq -r '.active // false' "$RUN")" = "true" ] || exit 0
status="$(jq -r '.status // ""' "$RUN")"
case "$status" in running|awaiting_human|paused|stalled) ;; *) exit 0 ;; esac

src="$(field '.source // "startup"')"
phase="$(jq -r '.phase // "?"' "$RUN")"; step="$(jq -r '.step // "?"' "$RUN")"; next="$(jq -r '.next_step // "?"' "$RUN")"
cat <<EOF
## /autonomous run in progress (restated after ${src})
Status: ${status} · phase ${phase} · last completed step: ${step} · next step: ${next}
State: agent_state/autonomous/run.json (+ checkpoint.json, agent_state/phases/${phase}/checkpoints/).
EOF
case "$status" in
  running) cat <<'EOF'
You are executing /startup:autonomous. Continue with the next step in the same turn: invoke each
sub-command with the Skill tool (startup:<cmd>, with --auto where defined), ignore sub-commands'
"▶ Next" hints, and update run.json (step, next_step, updated) after every step. Only stop by setting
status to awaiting_human, paused (with reason), failed or complete. Re-read
~/.claude/commands/startup/autonomous.md "How this command runs" if its rules are no longer in context.
EOF
  ;;
  *) echo "The run is ${status}; do not continue it unless the user asks (e.g. /startup:autonomous --resume)." ;;
esac
exit 0
