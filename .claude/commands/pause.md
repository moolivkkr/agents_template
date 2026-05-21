---
command: pause
description: "Save current work state for later resumption. Captures what was being worked on, what's done, what's blocked, and next steps."
arguments:
  - name: phase
    required: false
    description: "Phase being worked on. Auto-detected from current agent_state."
  - name: reason
    required: false
    description: "Why work is being paused (e.g. 'context limit', 'blocked on API', 'end of day')"
  - name: thread
    required: false
    description: "Named thread for this work stream (e.g. 'auth-refactor', 'phase-3-ui'). Enables multiple paused contexts."
---

# /pause — Save Session State

Explicitly saves the current work state — what was being done, what's complete, what's blocked, and what comes next — so a future session can resume with full context. Writes structured state to `agent_state/sessions/` for consumption by `/resume`.

**Use when:** Context window is filling up, you're blocked on external input, ending a work session, or switching to a different work stream.

**When NOT to use:** If you're done with the phase — run the gate instead. If you just need status — use `/status`.

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Agent result discipline:** `/pause` is a lightweight command. No subagents are spawned. The parent session reads existing state files and writes the pause snapshot directly.

**Read discipline:** Read each state file once, extract summary, move on. Do NOT load full spec files or source code — only metadata and summaries.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 0 Detect | ~8K (agent_state files + git status) |
| Step 1 Capture Work | ~10K (execution.jsonl + manifest + git diff summary) |
| Step 2 Capture Decisions | ~5K (decision-log.md if exists) |
| Step 3 Write State | ~2K (output only — writing, not reading) |
| Step 4 Recommend | ~1K (summary only) |

---

## Pipeline Anti-Rationalization Guard

**One rule:** Capture the FULL state, not the convenient subset. If you're tempted to skip a section because "it's obvious," that's exactly the context that will be lost.

| Your Internal Reasoning | Correct Response |
|---|---|
| "The git diff is too big to summarize" | Summarize by file — name + one-line change description. Full diff is in git, not the pause file. |
| "There are no blockers, I'll skip that section" | Write "Blockers: none" explicitly. Absence of a section is ambiguous; explicit "none" is not. |
| "The decisions are obvious from the code" | Decisions are obvious NOW. In 3 days they won't be. Log them. |
| "I'll just save the phase number, that's enough" | Phase number tells you WHERE, not WHAT or WHY. Capture all three. |
| "Uncommitted changes are fine, they'll still be there" | Maybe. Maybe not. Note them explicitly so /resume can verify. |
| "I don't need to save which step I'm on" | The step is the MOST IMPORTANT thing to save. It determines where /resume routes you. |

---

## Step 0 — Detect Current State

```bash
THREAD="${ARG_THREAD:-default}"
REASON="${ARG_REASON:-unspecified}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
TIMESTAMP_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

### Detect active phase

```bash
# Find the latest passed gate
LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)

# Check for in-progress phase (has execution.jsonl but no gate.passed)
for dir in agent_state/phases/*/; do
  PHASE_NUM=$(basename "$dir")
  if [ -f "${dir}execution.jsonl" ] && [ ! -f "${dir}gate.passed" ]; then
    ACTIVE_PHASE="$PHASE_NUM"
  fi
done

PHASE=${ARG_PHASE:-${ACTIVE_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}}
echo "▶ Pausing work on Phase $PHASE"
```

### Check git status

```bash
GIT_BRANCH=$(git branch --show-current 2>/dev/null)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null)
GIT_DIRTY=$(git status --porcelain 2>/dev/null)
GIT_STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
UNCOMMITTED_FILES=$(git diff --name-only 2>/dev/null)
UNTRACKED_FILES=$(git ls-files --others --exclude-standard 2>/dev/null)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
```

### Check for running agents

```bash
EXECUTION_LOG="agent_state/phases/${PHASE}/execution.jsonl"
if [ -f "$EXECUTION_LOG" ]; then
  # Get the last entry to determine pipeline state
  LAST_ENTRY=$(tail -1 "$EXECUTION_LOG")
  LAST_EVENT=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('event', json.load(open('/dev/stdin')).get('status','unknown')))" 2>/dev/null || echo "unknown")
  LAST_AGENT=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent',''))" 2>/dev/null || echo "")
  LAST_STEP=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('step',''))" 2>/dev/null || echo "")
fi
```

### Identify pipeline stage

Determine what command was being executed and which step:

```bash
# Check for active lock (indicates /develop was running)
LOCK_FILE="agent_state/phases/${PHASE}/.lock"
HAS_LOCK=$([ -f "$LOCK_FILE" ] && echo true || echo false)

# Detect pipeline stage from existing artifacts
HAS_AUDIT=$([ -f "agent_state/phases/${PHASE}/audit_report.md" ] && echo true || echo false)
HAS_REPORTS_DIR=$([ -d "agent_state/phases/${PHASE}/reports" ] && echo true || echo false)
HAS_UNIT_TESTS=$([ -f "agent_state/phases/${PHASE}/reports/unit_tests.md" ] && echo true || echo false)
HAS_E2E_TESTS=$([ -f "agent_state/phases/${PHASE}/reports/e2e_results.md" ] && echo true || echo false)
HAS_CODE_REVIEW=$([ -f "agent_state/phases/${PHASE}/reports/code_quality_review.md" ] && echo true || echo false)
HAS_ACCEPTANCE=$([ -f "agent_state/phases/${PHASE}/reports/acceptance_report.md" ] && echo true || echo false)
HAS_FEEDBACK=$([ -f "agent_state/phases/${PHASE}/reports/collective_feedback.md" ] && echo true || echo false)
HAS_MANIFEST=$([ -f "agent_state/phases/${PHASE}/manifest.json" ] && echo true || echo false)
HAS_GATE=$([ -f "agent_state/phases/${PHASE}/gate.passed" ] && echo true || echo false)

# Detect if /plan was in progress
HAS_PHASE_PLAN=$([ -f "docs/design/phases/${PHASE}/PHASE_PLAN.md" ] && echo true || echo false)
HAS_PHASE_CONTEXT=$([ -f "docs/design/phases/${PHASE}/phase_context.md" ] && echo true || echo false)
HAS_SPECS=$(ls docs/design/phases/${PHASE}/specs/*.md 2>/dev/null | head -1 && echo true || echo false)
HAS_DATA_CONTRACTS=$([ -f "docs/design/phases/${PHASE}/specs/data-contracts.md" ] && echo true || echo false)
HAS_VERIFICATION=$([ -f "docs/design/phases/${PHASE}/VERIFICATION_REPORT.md" ] && echo true || echo false)
HAS_INDEX=$([ -f "docs/design/phases/${PHASE}/INDEX.md" ] && echo true || echo false)

# Determine active command and step
if [ "$HAS_GATE" = "true" ]; then
  ACTIVE_COMMAND="none"
  ACTIVE_STEP="complete"
  PIPELINE_STAGE="complete"
elif [ "$HAS_FEEDBACK" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 6 — Gate"
  PIPELINE_STAGE="gating"
elif [ "$HAS_CODE_REVIEW" = "true" ] || [ "$HAS_ACCEPTANCE" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 5 — Collective Feedback (Wave 5)"
  PIPELINE_STAGE="iterating"
elif [ "$HAS_UNIT_TESTS" = "true" ] || [ "$HAS_E2E_TESTS" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 4 — Review + Acceptance (Wave 4)"
  PIPELINE_STAGE="reviewing"
elif [ "$HAS_AUDIT" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 2 — Implementation (Wave 2) or Step 3 — Testing (Wave 3)"
  PIPELINE_STAGE="implementing"
elif [ "$HAS_LOCK" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 0/1 — Orient + Audit (Wave 1)"
  PIPELINE_STAGE="auditing"
elif [ "$HAS_INDEX" = "true" ]; then
  ACTIVE_COMMAND="/develop"
  ACTIVE_STEP="Step 0 — Orient (specs complete, implementation not started)"
  PIPELINE_STAGE="pre-implementation"
elif [ "$HAS_VERIFICATION" = "true" ]; then
  ACTIVE_COMMAND="/plan"
  ACTIVE_STEP="Step 5 — Output Index"
  PIPELINE_STAGE="planning-final"
elif [ "$HAS_SPECS" = "true" ]; then
  ACTIVE_COMMAND="/plan"
  ACTIVE_STEP="Step 4 — Spec Verification"
  PIPELINE_STAGE="planning-verification"
elif [ "$HAS_PHASE_PLAN" = "true" ]; then
  ACTIVE_COMMAND="/plan"
  ACTIVE_STEP="Step 2 — Backend Specifications"
  PIPELINE_STAGE="planning-specs"
elif [ "$HAS_PHASE_CONTEXT" = "true" ]; then
  ACTIVE_COMMAND="/plan"
  ACTIVE_STEP="Step 1b — Phase Context Validation"
  PIPELINE_STAGE="planning-context"
else
  ACTIVE_COMMAND="/plan"
  ACTIVE_STEP="Step 0 — Not started"
  PIPELINE_STAGE="not-started"
fi
```

Print detection summary:

```
Session state detected:
  Phase:          ${PHASE}
  Active command: ${ACTIVE_COMMAND}
  Current step:   ${ACTIVE_STEP}
  Pipeline stage: ${PIPELINE_STAGE}
  Git branch:     ${GIT_BRANCH} @ ${GIT_SHA}
  Uncommitted:    ${N files} modified, ${N files} staged, ${N files} untracked
```

---

## Step 1 — Capture Work Context

Read state files to build a snapshot of completed, in-progress, and pending work.

### Completed items

Scan for artifacts that exist — these represent completed work:

```bash
COMPLETED_ITEMS=()

# Planning artifacts
[ "$HAS_PHASE_PLAN" = "true" ] && COMPLETED_ITEMS+=("Phase plan written: docs/design/phases/${PHASE}/PHASE_PLAN.md")
[ "$HAS_PHASE_CONTEXT" = "true" ] && COMPLETED_ITEMS+=("Phase context written: docs/design/phases/${PHASE}/phase_context.md")
[ "$HAS_DATA_CONTRACTS" = "true" ] && COMPLETED_ITEMS+=("Data contracts written: docs/design/phases/${PHASE}/specs/data-contracts.md")
[ "$HAS_VERIFICATION" = "true" ] && COMPLETED_ITEMS+=("Specs verified: docs/design/phases/${PHASE}/VERIFICATION_REPORT.md")
[ "$HAS_INDEX" = "true" ] && COMPLETED_ITEMS+=("Plan index written: docs/design/phases/${PHASE}/INDEX.md")

# Development artifacts
[ "$HAS_AUDIT" = "true" ] && COMPLETED_ITEMS+=("Audit complete: agent_state/phases/${PHASE}/audit_report.md")
[ "$HAS_UNIT_TESTS" = "true" ] && COMPLETED_ITEMS+=("Unit tests complete: agent_state/phases/${PHASE}/reports/unit_tests.md")
[ "$HAS_E2E_TESTS" = "true" ] && COMPLETED_ITEMS+=("E2E tests complete: agent_state/phases/${PHASE}/reports/e2e_results.md")
[ "$HAS_CODE_REVIEW" = "true" ] && COMPLETED_ITEMS+=("Code review complete: agent_state/phases/${PHASE}/reports/code_quality_review.md")
[ "$HAS_ACCEPTANCE" = "true" ] && COMPLETED_ITEMS+=("Acceptance tests complete: agent_state/phases/${PHASE}/reports/acceptance_report.md")
[ "$HAS_FEEDBACK" = "true" ] && COMPLETED_ITEMS+=("Collective feedback complete: agent_state/phases/${PHASE}/reports/collective_feedback.md")

# Spec files
SPEC_COUNT=$(ls docs/design/phases/${PHASE}/specs/*.md 2>/dev/null | wc -l | tr -d ' ')
[ "$SPEC_COUNT" -gt 0 ] && COMPLETED_ITEMS+=("${SPEC_COUNT} spec file(s) written in docs/design/phases/${PHASE}/specs/")
```

### In-progress items

Determine what was actively being worked on when the session was interrupted:

```bash
# Check execution log for agents that started but didn't complete
if [ -f "$EXECUTION_LOG" ]; then
  STARTED_AGENTS=$(python3 -c "
import json, sys
started = set()
completed = set()
for line in open('$EXECUTION_LOG'):
    try:
        entry = json.loads(line.strip())
        agent = entry.get('agent', '')
        status = entry.get('status', entry.get('event', ''))
        if status == 'started' and agent:
            started.add(agent)
        elif status in ('completed', 'failed') and agent:
            completed.add(agent)
    except: pass
in_progress = started - completed
for a in sorted(in_progress):
    print(a)
" 2>/dev/null)
fi
```

### Blocked items

Check for known blockers:

```bash
# Check for gate failures
GATE_FAILURES=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null)

# Check for unresolved debates
UNRESOLVED_DEBATES=$(ls agent_state/debates/unresolved.json 2>/dev/null)

# Check for migration failures
MIGRATION_FAILURE=$(ls agent_state/phases/${PHASE}/migration_failure.json 2>/dev/null)

# Check for reconciliation issues
RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
HAS_MISSING_COVERAGE=$([ -f "$RECON_FILE" ] && grep -q "MISSING" "$RECON_FILE" && echo true || echo false)
```

### Uncommitted changes summary

```bash
# Summarize git diff by file (name + insertion/deletion counts)
git diff --stat 2>/dev/null
git diff --cached --stat 2>/dev/null
```

---

## Step 2 — Capture Decision Context

### Decisions made this session

```bash
DECISION_LOG="agent_state/phases/${PHASE}/decision-log.md"
if [ -f "$DECISION_LOG" ]; then
  # Extract decision titles (## Decision: <title> lines)
  grep "^## Decision:" "$DECISION_LOG"
fi
```

### Open questions

Scan for escalations and debates that are unresolved:

```bash
# Unresolved debate requests
for f in agent_state/debates/*-verdict.json; do
  [ -f "$f" ] || continue
  echo "Resolved: $(basename $f)"
done

for f in agent_state/debates/*.json; do
  [ -f "$f" ] || continue
  [[ "$f" == *-verdict.json ]] && continue
  [[ "$f" == *unresolved.json ]] && continue
  VERDICT="${f%-*}-verdict.json"
  [ ! -f "$VERDICT" ] && echo "OPEN: $(basename $f)"
done
```

### Key findings from reviews/tests

If review or test reports exist, extract their summary sections:

```bash
# Extract first 5 lines of each report (typically the summary)
for report in agent_state/phases/${PHASE}/reports/*.md; do
  [ -f "$report" ] || continue
  echo "--- $(basename $report) ---"
  head -5 "$report"
done
```

---

## Step 3 — Write Session State

Create the session directory and write the pause snapshot.

```bash
SESSION_DIR="agent_state/sessions/${THREAD}"
mkdir -p "$SESSION_DIR"
```

Write `agent_state/sessions/${THREAD}/${TIMESTAMP}-pause.md`:

```markdown
# Pause Snapshot
- **Timestamp:** ${TIMESTAMP_ISO}
- **Thread:** ${THREAD}
- **Reason:** ${REASON}

## Work Context
- **Phase:** ${PHASE}
- **Active command:** ${ACTIVE_COMMAND}
- **Current step:** ${ACTIVE_STEP}
- **Pipeline stage:** ${PIPELINE_STAGE}

## Git State
- **Branch:** ${GIT_BRANCH}
- **SHA:** ${GIT_SHA}
- **Uncommitted changes:** ${N} modified, ${N} staged, ${N} untracked
- **Stashes:** ${GIT_STASH_COUNT}
- **Modified files:**
${list of modified files with one-line change descriptions}
- **Staged files:**
${list of staged files}
- **Untracked files:**
${list of untracked files}

## Completed
${numbered list of completed items from Step 1}

## In Progress
${list of in-progress agents or tasks from Step 1}
(or: "None — paused between steps")

## Blocked
${list of blockers from Step 1}
(or: "None")

## Decisions Made
${list of decision titles and one-line summaries from Step 2}
(or: "None recorded")

## Open Questions
${list of unresolved debates or escalations from Step 2}
(or: "None")

## Key Findings
${summary findings from reports, if any exist}
(or: "No reports generated yet")

## Next Steps
1. ${primary next action — the step that should execute next}
2. ${secondary actions — cleanup, fixes, etc.}
3. ${optional — things to investigate or verify}

## Resume Command
${exact command to run to continue, e.g.:}
/resume --thread=${THREAD}
${which will route to:}
${ACTIVE_COMMAND} --phase=${PHASE}
```

Write or overwrite `agent_state/sessions/${THREAD}/LATEST.md` as a copy (not symlink — portability):

```bash
cp "agent_state/sessions/${THREAD}/${TIMESTAMP}-pause.md" "agent_state/sessions/${THREAD}/LATEST.md"
```

### Execution log entry

If an execution log exists for the phase, append a pause event:

```bash
if [ -f "$EXECUTION_LOG" ]; then
  echo "{\"ts\":\"${TIMESTAMP_ISO}\",\"event\":\"session_paused\",\"phase\":${PHASE},\"thread\":\"${THREAD}\",\"reason\":\"${REASON}\",\"pipeline_stage\":\"${PIPELINE_STAGE}\"}" >> "$EXECUTION_LOG"
fi
```

---

## Step 4 — Recommend Next Steps

Analyze the saved state and provide actionable guidance.

### Uncommitted changes advisory

```bash
if [ -n "$GIT_DIRTY" ]; then
  DIRTY_COUNT=$(echo "$GIT_DIRTY" | wc -l | tr -d ' ')
  echo "⚠ ${DIRTY_COUNT} uncommitted changes detected."
  echo "  Recommend: commit or stash before ending the session."
  echo ""
  echo "  To commit:  git add <files> && git commit -m 'WIP: ${ACTIVE_STEP}'"
  echo "  To stash:   git stash push -m 'pause: ${THREAD} ${TIMESTAMP}'"
fi
```

### Time-sensitive items

```bash
# Check for active locks that should be released
if [ "$HAS_LOCK" = "true" ]; then
  echo "⚠ Phase ${PHASE} lock is still held: ${LOCK_FILE}"
  echo "  Other developers cannot run /develop on this phase."
  echo "  Remove the lock if you won't be resuming soon: rm ${LOCK_FILE}"
fi

# Check for in-progress agents that may have been interrupted
if [ -n "$STARTED_AGENTS" ]; then
  echo "⚠ Agents were mid-execution when session paused:"
  echo "$STARTED_AGENTS" | while read agent; do echo "  - $agent"; done
  echo "  These agents will need to be re-run on /resume."
fi
```

---

## Output

Primary output: `agent_state/sessions/${THREAD}/${TIMESTAMP}-pause.md`
Latest pointer: `agent_state/sessions/${THREAD}/LATEST.md`

```
✅ Session paused → wrote agent_state/sessions/${THREAD}/${TIMESTAMP}-pause.md

  Phase:     ${PHASE}
  Command:   ${ACTIVE_COMMAND}
  Step:      ${ACTIVE_STEP}
  Stage:     ${PIPELINE_STAGE}
  Reason:    ${REASON}
  Thread:    ${THREAD}

  Completed: ${N} items
  Blocked:   ${N} items (or: none)
  Uncommitted: ${N} files (or: clean)

  ▶ Resume with: /resume --thread=${THREAD}
```

---

## Rules

- `/pause` is read-only against source code — it never modifies implementation files
- `/pause` ALWAYS writes state — even if the session appears "clean," write the snapshot for audit trail
- Every section of the pause file MUST be explicit — write "none" rather than omitting a section
- Git diff summaries use `--stat` format (file name + change counts), never full diffs — the pause file must stay under 500 lines
- Uncommitted changes are NOTED, not committed — `/pause` does not make git commits
- The LATEST.md file is always a full copy, never a symlink — ensures portability across environments
- Thread names must be filesystem-safe — alphanumeric, hyphens, and underscores only
- Multiple paused threads can coexist — each thread has its own directory under `agent_state/sessions/`
- The pause file is the SOURCE OF TRUTH for `/resume` — it must contain enough context to resume without reading any other file
