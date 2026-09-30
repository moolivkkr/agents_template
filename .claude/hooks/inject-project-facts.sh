#!/usr/bin/env bash
# SessionStart hook — surfaces Tier 0 ground-truth facts AND Tier 0.5 active decisions into every
# new session. Part of the Shared Context Protocol (~/.claude/skills/core/shared-context-protocol.md).
# Safe by design: no-ops silently if the source files are absent or have no active entries.

set -euo pipefail

FACTS_FILE="docs/PROJECT_FACTS.md"
DECISIONS_FILE="docs/DECISIONS.md"

# Extract ACTIVE fact headings (a fact heading followed by "status: active").
active_facts=""
if [ -f "$FACTS_FILE" ]; then
  active_facts=$(awk '
    !c && /<!--/ { c=1 } c { if (/-->/) c=0; next }   # skip commented example blocks (phantom facts)
    /^### F-/ { title=$0; capture=1 }
    capture && /^- status: active/ { print title; capture=0 }
  ' "$FACTS_FILE")
fi

# Extract ACTIVE decision headings (a decision heading followed by "status: active").
active_decisions=""
if [ -f "$DECISIONS_FILE" ]; then
  active_decisions=$(awk '
    !c && /<!--/ { c=1 } c { if (/-->/) c=0; next }   # skip commented example blocks
    /^### D-/ { title=$0; capture=1 }
    capture && /^- status: active/ { print title; capture=0 }
  ' "$DECISIONS_FILE")
fi

# Nothing to inject if both are empty.
[ -n "$active_facts" ] || [ -n "$active_decisions" ] || exit 0

# Emit as additionalContext for the session (stdout is injected by Claude Code SessionStart).
echo "GROUND TRUTH — active facts + settled decisions every action must honor. These override any"
echo "conflicting assumption. Read the source files for detail; if a task touches anything RETIRED,"
echo "superseded, or reversed here, stop and flag it."
echo ""

if [ -n "$active_facts" ]; then
  echo "## Facts (docs/PROJECT_FACTS.md) — Tier 0, immutable ground truth"
  echo "$active_facts"
  echo ""
fi

if [ -n "$active_decisions" ]; then
  echo "## Decisions (docs/DECISIONS.md) — Tier 0.5, settled calls with rationale"
  echo "$active_decisions"
  echo ""
fi

echo "(Add/change facts with /remember; decisions are recorded only via .claude/hooks/remember.sh decide"
echo " (ADR/debate agents do it; others propose, the parent records). Both reach every session and subagent.)"
