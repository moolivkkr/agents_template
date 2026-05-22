---
command: resume
description: "Resume paused work with full context restoration. Reads saved session state and continues from where work was paused."
arguments:
  - name: thread
    required: false
    description: "Named thread to resume (e.g. 'auth-refactor'). Omit to resume the default/latest session."
  - name: list
    required: false
    default: false
    description: "List all paused sessions instead of resuming"
---

# /resume — Restore Session and Continue

Reads the session state saved by `/pause` and restores full context — what was being done, where it left off, what's blocked, and what comes next. Routes to the appropriate command to continue work.

**Use when:** Starting a new session after a previous `/pause`, or picking up a named work thread.

**When NOT to use:** If starting a fresh phase — use `/plan` or `/develop` directly. If checking status — use `/status`.

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Agent result discipline:** `/resume` is a lightweight coordination command. No subagents are spawned. The parent session reads the pause snapshot, validates current state, and routes to the correct pipeline command.

**Read discipline:** The pause file is the primary input. Validate against current filesystem state but do not re-read source code or full specs.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 0 Find Session | ~3K (directory listing + LATEST.md) |
| Step 1 Restore Context | ~8K (pause file + git status + delta check) |
| Step 2 Verify Prerequisites | ~5K (gate files + artifact existence checks) |
| Step 3 Present Plan | ~2K (summary output) |
| Step 4 Route | ~1K (command suggestion) |

---

## Pipeline Anti-Rationalization Guard

**One rule:** Trust the pause file as the source of truth, but VERIFY against current state. If they conflict, surface the conflict — do not silently proceed with stale assumptions.

| Your Internal Reasoning | Correct Response |
|---|---|
| "The pause file says Step 3, but I can see Step 4 artifacts — I'll just jump to Step 5" | NO. Surface the discrepancy. Someone else may have run steps between pause and resume. Let the user decide. |
| "The uncommitted changes are gone, they must have been committed" | Check. Run `git log --oneline -5` to see if they were committed. If not, flag as LOST and warn the user. |
| "The pause file is old, I'll just start fresh" | Show the age and let the user decide. Stale context is better than no context. |
| "I know what needs to happen next, I'll skip the resume plan" | Show the plan. The user may have changed their mind, or new information may have arrived. |
| "The thread name doesn't match any directory, I'll use default" | STOP. The user asked for a specific thread. Tell them it doesn't exist and show what does exist. |
| "Phase gate passed since the pause — just tell the user it's done" | Show the FULL context: what was paused, what changed, and that the gate passed. The user needs to understand the full picture. |

---

## Step 0 — Find Session State

```bash
THREAD="${ARG_THREAD:-default}"
SESSION_BASE="agent_state/sessions"
```

### If `--list` flag: show all paused sessions

```bash
if [ "${ARG_LIST}" = "true" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Paused Sessions"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  if [ ! -d "$SESSION_BASE" ] || [ -z "$(ls -A "$SESSION_BASE" 2>/dev/null)" ]; then
    echo "  No paused sessions found."
    echo ""
    echo "  Pause a session with: /pause"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
  fi

  for thread_dir in "$SESSION_BASE"/*/; do
    [ -d "$thread_dir" ] || continue
    THREAD_NAME=$(basename "$thread_dir")
    LATEST="${thread_dir}LATEST.md"

    if [ -f "$LATEST" ]; then
      # Extract key fields from LATEST.md
      PAUSE_TIME=$(grep "^\- \*\*Timestamp:\*\*" "$LATEST" | sed 's/.*\*\* //')
      PAUSE_PHASE=$(grep "^\- \*\*Phase:\*\*" "$LATEST" | sed 's/.*\*\* //')
      PAUSE_COMMAND=$(grep "^\- \*\*Active command:\*\*" "$LATEST" | sed 's/.*\*\* //')
      PAUSE_STEP=$(grep "^\- \*\*Current step:\*\*" "$LATEST" | sed 's/.*\*\* //')
      PAUSE_REASON=$(grep "^\- \*\*Reason:\*\*" "$LATEST" | sed 's/.*\*\* //')
      PAUSE_STAGE=$(grep "^\- \*\*Pipeline stage:\*\*" "$LATEST" | sed 's/.*\*\* //')

      # Count pause history for this thread
      PAUSE_COUNT=$(ls "${thread_dir}"*-pause.md 2>/dev/null | wc -l | tr -d ' ')

      echo "  Thread: ${THREAD_NAME}"
      echo "    Paused:  ${PAUSE_TIME}"
      echo "    Phase:   ${PAUSE_PHASE}"
      echo "    Command: ${PAUSE_COMMAND} — ${PAUSE_STEP}"
      echo "    Stage:   ${PAUSE_STAGE}"
      echo "    Reason:  ${PAUSE_REASON}"
      echo "    History: ${PAUSE_COUNT} pause snapshot(s)"
      echo "    Resume:  /resume --thread=${THREAD_NAME}"
      echo ""
    fi
  done

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
fi
```

### Load session state

```bash
SESSION_DIR="${SESSION_BASE}/${THREAD}"
LATEST_FILE="${SESSION_DIR}/LATEST.md"

if [ ! -d "$SESSION_DIR" ]; then
  # Fallback: check for auto-checkpoints (no explicit /pause was run)
  # If checkpoints exist for any in-progress phase, offer checkpoint-based resume
  CHECKPOINT_PHASE=""
  for dir in agent_state/phases/*/checkpoints; do
    [ -d "$dir" ] || continue
    PHASE_NUM=$(echo "$dir" | grep -oE 'phases/[0-9]+' | grep -oE '[0-9]+')
    if [ ! -f "agent_state/phases/${PHASE_NUM}/gate.passed" ]; then
      CHECKPOINT_PHASE="$PHASE_NUM"
      LATEST_WAVE=$(ls "$dir"/wave-*.json 2>/dev/null | sort -V | tail -1)
    fi
  done

  if [ -n "$CHECKPOINT_PHASE" ] && [ -n "$LATEST_WAVE" ]; then
    WAVE_NUM=$(echo "$LATEST_WAVE" | grep -oE 'wave-[0-9]+' | grep -oE '[0-9]+')
    COMPACT_CTX="agent_state/phases/${CHECKPOINT_PHASE}/checkpoints/compact-context.md"
    HAS_COMPACT=$([ -f "$COMPACT_CTX" ] && echo true || echo false)

    echo "No explicit /pause session found, but auto-checkpoints detected:"
    echo ""
    echo "  Phase:         ${CHECKPOINT_PHASE}"
    echo "  Last wave:     ${WAVE_NUM}"
    echo "  Checkpoint:    ${LATEST_WAVE}"
    if [ "$HAS_COMPACT" = "true" ]; then
      echo "  Compact ctx:   ${COMPACT_CTX} (post-compaction state saved)"
    fi
    echo ""
    echo "  Resume with: /develop --phase=${CHECKPOINT_PHASE}"
    echo "  (Will skip Waves 1-${WAVE_NUM} and start at Wave $((WAVE_NUM + 1)))"
    if [ "$HAS_COMPACT" = "true" ]; then
      echo ""
      echo "  ⚡ Compact context exists — read ${COMPACT_CTX} first for full session state"
      echo "    (includes completed wave summaries, decisions, and next steps)"
    fi
    exit 0
  fi

  echo "⛔ No session found for thread '${THREAD}'"
  echo ""
  echo "  Available threads:"
  ls -1 "$SESSION_BASE" 2>/dev/null | while read t; do
    echo "    - $t"
  done
  echo ""
  echo "  Options:"
  echo "    /resume --list          — see all paused sessions"
  echo "    /resume --thread=NAME   — resume a specific thread"
  echo "    /resume                 — resume the 'default' thread"
  exit 1
fi

if [ ! -f "$LATEST_FILE" ]; then
  echo "⛔ Thread '${THREAD}' exists but has no LATEST.md"
  echo ""
  echo "  This may indicate a corrupted session. Check:"
  echo "    ls ${SESSION_DIR}/"
  echo ""
  echo "  If pause files exist, copy the most recent one to LATEST.md:"
  echo "    cp ${SESSION_DIR}/<latest-pause-file>.md ${SESSION_DIR}/LATEST.md"
  exit 1
fi
```

Read the pause file:

```bash
# Read LATEST.md — this is the primary context for the entire /resume command
cat "${LATEST_FILE}"
```

Extract structured data from the pause file:

```bash
PAUSE_TIMESTAMP=$(grep "^\- \*\*Timestamp:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_PHASE=$(grep "^\- \*\*Phase:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_COMMAND=$(grep "^\- \*\*Active command:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_STEP=$(grep "^\- \*\*Current step:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_STAGE=$(grep "^\- \*\*Pipeline stage:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_REASON=$(grep "^\- \*\*Reason:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_BRANCH=$(grep "^\- \*\*Branch:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
PAUSE_SHA=$(grep "^\- \*\*SHA:\*\*" "$LATEST_FILE" | sed 's/.*\*\* //')
```

---

## Step 1 — Restore Context

### Display saved context

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Resuming: ${THREAD}
  Paused:   ${PAUSE_TIMESTAMP}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Phase:     ${PAUSE_PHASE}
  Command:   ${PAUSE_COMMAND}
  Step:      ${PAUSE_STEP}
  Stage:     ${PAUSE_STAGE}
  Reason:    ${PAUSE_REASON}
```

### Check what changed since pause

```bash
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
CURRENT_SHA=$(git rev-parse --short HEAD 2>/dev/null)
CURRENT_DIRTY=$(git status --porcelain 2>/dev/null)

# Commits since pause
if [ -n "$PAUSE_SHA" ]; then
  NEW_COMMITS=$(git log --oneline "${PAUSE_SHA}..HEAD" 2>/dev/null)
  NEW_COMMIT_COUNT=$(echo "$NEW_COMMITS" | grep -c '.' 2>/dev/null || echo 0)
else
  NEW_COMMITS=""
  NEW_COMMIT_COUNT=0
fi
```

### Report deltas

```
Changes since pause:
  Branch:       ${PAUSE_BRANCH} → ${CURRENT_BRANCH} (${same | CHANGED})
  SHA:          ${PAUSE_SHA} → ${CURRENT_SHA} (${N} new commits)
  Uncommitted:  ${N files | clean}
```

If `NEW_COMMIT_COUNT` > 0:
```
  New commits since pause:
${NEW_COMMITS}
```

### Flag stale state

Calculate time elapsed since pause:

```bash
# Parse pause timestamp and compare to now
PAUSE_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$PAUSE_TIMESTAMP" "+%s" 2>/dev/null || date -d "$PAUSE_TIMESTAMP" "+%s" 2>/dev/null || echo 0)
NOW_EPOCH=$(date "+%s")
ELAPSED_SECONDS=$((NOW_EPOCH - PAUSE_EPOCH))
ELAPSED_HOURS=$((ELAPSED_SECONDS / 3600))
ELAPSED_DAYS=$((ELAPSED_HOURS / 24))
```

```bash
if [ "$ELAPSED_DAYS" -gt 7 ]; then
  echo "⚠ STALE SESSION — paused ${ELAPSED_DAYS} days ago"
  echo "  Significant changes may have occurred. Review carefully before resuming."
  echo "  Consider: /status to check current project state"
elif [ "$ELAPSED_DAYS" -gt 1 ]; then
  echo "ℹ Session paused ${ELAPSED_DAYS} days ago"
elif [ "$ELAPSED_HOURS" -gt 0 ]; then
  echo "ℹ Session paused ${ELAPSED_HOURS} hours ago"
fi
```

### Check for lost uncommitted changes

```bash
# Parse uncommitted file list from pause file
# Compare against current git status
# Flag files that were noted as modified but are now clean (not in any new commit)
```

If uncommitted changes from the pause are missing and not found in new commits:
```
⚠ LOST CHANGES — the following files had uncommitted changes at pause time but are now clean:
  - ${file1}
  - ${file2}

  These changes may have been lost. Check:
    git stash list          — changes may have been stashed
    git reflog              — changes may be in reflog
    git log --all --diff-filter=M -- ${file}  — check if committed on another branch
```

---

## Step 2 — Verify Prerequisites

### Phase gate state

```bash
PHASE=${PAUSE_PHASE}

# Check if phase gate state has changed since pause
if [ -f "agent_state/phases/${PHASE}/gate.passed" ]; then
  GATE_TIME=$(stat -f "%Sm" -t "%Y-%m-%dT%H:%M:%SZ" "agent_state/phases/${PHASE}/gate.passed" 2>/dev/null || stat -c "%y" "agent_state/phases/${PHASE}/gate.passed" 2>/dev/null)
  echo "✅ Phase ${PHASE} gate has PASSED (at ${GATE_TIME})"
  echo "   The paused work may already be complete."
  echo ""
  echo "   Options:"
  echo "     /status                      — check overall project state"
  echo "     /develop --phase=$((PHASE+1)) — start next phase"
  echo "     /resume --thread=${THREAD}    — review what was done (informational only)"
fi

# Check if previous phase gates are still valid
if [ "$PHASE" -gt 1 ]; then
  PREV_GATE="agent_state/phases/$((PHASE-1))/gate.passed"
  if [ ! -f "$PREV_GATE" ]; then
    echo "⚠ Phase $((PHASE-1)) gate no longer exists — may have been reset"
    echo "  The paused phase ${PHASE} cannot continue until Phase $((PHASE-1)) passes."
    echo "  Run: /develop --phase=$((PHASE-1))"
  fi
fi
```

### Verify referenced files still exist

```bash
# Parse the "Completed" section from the pause file and check each referenced path
# Example: if pause says "Audit complete: agent_state/phases/2/audit_report.md" — verify it exists

MISSING_ARTIFACTS=()
# For each completed item path in the pause file:
#   if [ ! -f "$path" ]; then MISSING_ARTIFACTS+=("$path"); fi

if [ ${#MISSING_ARTIFACTS[@]} -gt 0 ]; then
  echo "⚠ Artifacts referenced in pause file are MISSING:"
  for f in "${MISSING_ARTIFACTS[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "  These may have been deleted or moved. The pipeline step that produced them"
  echo "  may need to be re-run."
fi
```

### Verify branch state

```bash
if [ "$CURRENT_BRANCH" != "$PAUSE_BRANCH" ]; then
  echo "⚠ Branch changed: was '${PAUSE_BRANCH}', now '${CURRENT_BRANCH}'"
  echo "  If the paused work was on '${PAUSE_BRANCH}', switch back:"
  echo "    git checkout ${PAUSE_BRANCH}"
fi
```

---

## Step 3 — Present Resume Plan

Display the full context restoration with a clear action plan.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Resume Plan — ${THREAD}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHERE YOU LEFT OFF
  Phase:   ${PAUSE_PHASE}
  Command: ${PAUSE_COMMAND}
  Step:    ${PAUSE_STEP}
  Stage:   ${PAUSE_STAGE}

WHAT WAS DONE
  ${numbered list of completed items from pause file}

WHAT WAS IN PROGRESS
  ${list of in-progress items, or "Nothing — paused between steps"}

WHAT WAS BLOCKED
  ${list of blockers, or "Nothing blocked"}

DECISIONS MADE
  ${list of decisions, or "None recorded"}

OPEN QUESTIONS
  ${list, or "None"}

CHANGES SINCE PAUSE
  ${summary of new commits, branch changes, file modifications}

WHAT'S NEXT
  ${numbered next steps from pause file, adjusted for any state changes detected}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**User confirmation:** Present the plan and wait for the user to confirm before routing.

```
Proceed with:
  1. Continue as planned → ${RESUME_COMMAND}
  2. Start fresh        → re-run ${PAUSE_COMMAND} from the beginning
  3. Check status first → /status
  4. Abort resume       → exit (session state preserved)

Choice [1]:
```

In `--auto` mode (if the original `/pause` was auto): skip confirmation and proceed with option 1.

---

## Step 4 — Route to Appropriate Command

Based on the paused command and step, construct the exact command to resume.

### Routing table

| Paused Command | Paused Stage | Resume Command |
|---|---|---|
| `/plan` | `planning-context` | `/plan --phase=${PHASE}` (resume detection skips completed steps) |
| `/plan` | `planning-specs` | `/plan --phase=${PHASE}` (resume detection skips completed steps) |
| `/plan` | `planning-verification` | `/plan --phase=${PHASE}` (resume detection skips to verification) |
| `/plan` | `planning-final` | `/plan --phase=${PHASE}` (resume detection skips to output) |
| `/develop` | `pre-implementation` | `/develop --phase=${PHASE}` |
| `/develop` | `auditing` | `/develop --phase=${PHASE}` (will re-run audit — idempotent) |
| `/develop` | `implementing` | `/develop --phase=${PHASE}` (resume detection sees audit, skips to impl) |
| `/develop` | `reviewing` | `/develop --phase=${PHASE}` (resume detection sees tests, routes to review) |
| `/develop` | `iterating` | `/develop --phase=${PHASE}` (resume detection sees reviews, routes to feedback) |
| `/develop` | `gating` | `/develop --phase=${PHASE}` (resume detection sees feedback, routes to gate) |
| `/test` | any | `/test --phase=${PHASE}` |
| `/review` | any | `/review` |
| `/hotfix` | any | `/hotfix --phase=${PHASE} --component=${COMPONENT} --description="${DESCRIPTION}"` |
| `none` | `complete` | Phase complete. Suggest `/develop --phase=$((PHASE+1))` or `/status`. |
| `/plan` | `not-started` | `/plan --phase=${PHASE}` |

### Present the routing

```
▶ Recommended command:
  ${RESUME_COMMAND}

  This will resume ${PAUSE_COMMAND} at ${PAUSE_STEP}.
  The existing resume detection in ${PAUSE_COMMAND} will skip completed steps
  and continue from where artifacts exist.
```

### Log the resume event

```bash
EXECUTION_LOG="agent_state/phases/${PAUSE_PHASE}/execution.jsonl"
RESUME_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if [ -f "$EXECUTION_LOG" ]; then
  echo "{\"ts\":\"${RESUME_TIMESTAMP}\",\"event\":\"session_resumed\",\"phase\":${PAUSE_PHASE},\"thread\":\"${THREAD}\",\"paused_at\":\"${PAUSE_TIMESTAMP}\",\"resumed_at\":\"${RESUME_TIMESTAMP}\",\"pipeline_stage\":\"${PAUSE_STAGE}\"}" >> "$EXECUTION_LOG"
fi
```

### Archive the resumed session

After the user confirms and the resume command begins, mark the session as resumed:

```bash
# Rename LATEST.md to indicate it was consumed
RESUME_MARKER="agent_state/sessions/${THREAD}/${TIMESTAMP}-resumed.md"
cp "${LATEST_FILE}" "${RESUME_MARKER}"

# Append resume metadata to LATEST.md
cat >> "${LATEST_FILE}" << EOF

---
## Resumed
- **Resumed at:** ${RESUME_TIMESTAMP}
- **Resumed by:** $(whoami)@$(hostname)
- **Command executed:** ${RESUME_COMMAND}
- **Archive:** ${RESUME_MARKER}
EOF
```

---

## Output

```
✅ Session resumed — context restored from agent_state/sessions/${THREAD}/LATEST.md

  Thread:    ${THREAD}
  Phase:     ${PAUSE_PHASE}
  Paused:    ${PAUSE_TIMESTAMP} (${ELAPSED_HOURS}h ago)
  Stage:     ${PAUSE_STAGE}
  Changes:   ${NEW_COMMIT_COUNT} new commits since pause

  ▶ Continue with: ${RESUME_COMMAND}
```

---

## Rules

- `/resume` is read-only against source code — it reads state, presents a plan, and routes. It does not modify implementation files.
- The pause file is the SOURCE OF TRUTH for session context — but it must be validated against current filesystem state
- NEVER silently skip a discrepancy — if the pause file says one thing and reality says another, surface it to the user
- If the thread does not exist, STOP — do not fall back to a different thread without explicit user consent
- If the phase gate has passed since the pause, inform the user — the paused work may be moot
- Branch mismatches are WARNINGS, not blockers — the user decides whether to switch branches
- Lost uncommitted changes are flagged prominently — this represents potential data loss
- The routing table is deterministic — given a paused stage, there is exactly one correct resume command
- Session state is preserved even after resume — the pause snapshot remains as an audit trail
- Time elapsed since pause is always shown — sessions older than 7 days get a STALE warning
- `/resume --list` is always safe and makes no changes — it is a read-only inventory command
