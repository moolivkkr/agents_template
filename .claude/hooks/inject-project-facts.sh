#!/usr/bin/env bash
# SessionStart hook — surfaces Tier 0 ground-truth facts into every new session.
# Part of the Shared Context Protocol (.claude/skills/core/shared-context-protocol.md).
# Safe by design: no-ops silently if the facts file is absent or has no active facts.

set -euo pipefail

FACTS_FILE="docs/PROJECT_FACTS.md"

# Nothing to inject if the project has no facts file yet.
[ -f "$FACTS_FILE" ] || exit 0

# Extract only ACTIVE fact blocks (a fact heading followed within a few lines by
# "status: active"). We print the heading line + the one-line summary of each active fact.
active=$(awk '
  /^### F-/ { title=$0; buf=""; capture=1 }
  capture && /^- status: active/ { print title }
' "$FACTS_FILE")

[ -n "$active" ] || exit 0

# Emit as additionalContext for the session (stdout is injected by Claude Code SessionStart).
cat <<EOF
GROUND TRUTH (docs/PROJECT_FACTS.md) — active facts every action must honor. These override
any conflicting assumption. Read the file for full details; if a task touches anything RETIRED
or superseded here, stop and flag it.

$active

(Add or change facts with /remember — they propagate to every session and subagent.)
EOF
