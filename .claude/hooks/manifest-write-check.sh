#!/usr/bin/env bash
# manifest-write-check.sh — PostToolUse hook: re-verify a phase gate whenever a phase manifest is
# written. Handles the Write/Edit tools (tool_input.file_path) AND Bash (tool_input.command), because
# the canonical manifest write is `jq … > manifest.json.tmp && mv …` — a Bash `mv` that a
# Write|Edit-only matcher never saw (review 2026-09-30, B4). Only acts when the manifest claims a
# passed gate, so ordinary manifest edits during a phase stay quiet.
set -uo pipefail
INPUT="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0
DIR="${CLAUDE_PROJECT_DIR:-$(printf '%s' "$INPUT" | jq -r '.cwd // empty')}"; DIR="${DIR:-$PWD}"
target="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // empty')"
phase="$(printf '%s' "$target" | grep -Eo 'agent_state/phases/[0-9]+/manifest\.json' | head -1 | grep -Eo '[0-9]+' | head -1)"
[ -n "$phase" ] || exit 0
M="$DIR/agent_state/phases/$phase/manifest.json"
[ -f "$M" ] || exit 0
[ "$(jq -r 'try (.gate.passed) catch false' "$M" 2>/dev/null)" = "true" ] || [ -f "$DIR/agent_state/phases/$phase/gate.passed" ] || exit 0
exec "$DIR/.claude/hooks/verify-gate.sh" "$phase"
