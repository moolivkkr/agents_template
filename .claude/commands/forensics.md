---
command: forensics
description: "Post-mortem investigation for failed pipeline runs. Analyzes git history, agent_state artifacts, and execution logs to diagnose what went wrong."
arguments:
  - name: phase
    required: false
    description: "Phase to investigate. Omit to investigate the most recently failed phase."
  - name: command
    required: false
    description: "Which command failed: 'plan', 'develop', 'test', 'review', 'deploy'"
  - name: depth
    required: false
    default: "standard"
    description: "Investigation depth: 'quick' (execution logs only), 'standard' (logs + git + files), 'deep' (full reconstruction)"
---

# /forensics — Post-Mortem Investigation

Reconstructs what happened during a failed pipeline run. Builds a timeline, identifies the point of failure, classifies the root cause, assesses impact, and recommends recovery steps.

**Use when:** A pipeline run failed and you need to understand WHY before retrying. Retrying without understanding the failure repeats the failure.

**What it does NOT do:** It does not fix code, re-run pipelines, or modify state. It investigates and writes a report. For state repair, use `/health --fix`. For code bugs, use `/diagnose`. For retrying, use `/develop`.

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "The error message is clear, I don't need a full investigation" | NO. Error messages explain WHAT failed. Forensics explains WHY and what else was affected. The cascade matters. |
| "I can see the failed agent in the log, just re-run it" | NO. Understand why it failed first. Was it a flaky environment? Missing dependency? Context exhaustion? The fix is different for each. |
| "The failure is in the test step, so the implementation is fine" | MAYBE NOT. Test failures often expose implementation bugs. Read the test output before absolving the implementation. |
| "Quick depth is enough, I don't need to check git history" | For transient failures, yes. For persistent failures, git history reveals whether the problem was introduced by code changes or state corruption. Use standard or deep. |
| "I'll just look at the last entry in execution.jsonl" | NO. The last entry is where the pipeline STOPPED, not necessarily where the problem STARTED. Read the full timeline. |
| "The phase ran before and worked, so the framework must be the problem" | Don't blame the framework without evidence. Check what changed: code, specs, state, environment. Forensics investigates — it doesn't assume. |

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Read discipline:** Start with execution.jsonl (small, structured) and expand outward only as needed. Do not load all phase artifacts into context.

**Depth-dependent budget:**

| Step | Quick | Standard | Deep |
|------|-------|----------|------|
| Step 0 Identify | ~3K | ~3K | ~3K |
| Step 1 Timeline | ~5K | ~5K | ~10K |
| Step 2 Context | skip | ~10K | ~20K |
| Step 3 Root cause | ~3K | ~8K | ~15K |
| Step 4 Impact | skip | ~5K | ~10K |
| Step 5 Recovery | ~3K | ~5K | ~8K |
| Step 6 Report | ~3K | ~5K | ~8K |
| **Total** | **~17K** | **~41K** | **~74K** |

---

## Step 0 — Identify Failure

### If `--phase` specified
```bash
PHASE="${ARG_PHASE}"
COMMAND="${ARG_COMMAND}"
DEPTH="${ARG_DEPTH:-standard}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
```

### If `--phase` NOT specified — auto-detect

Find the most recently failed phase:

```bash
# Strategy 1: Find phases without gate.passed that have execution.jsonl
for phase_dir in $(ls -d agent_state/phases/*/ 2>/dev/null | sort -t/ -k3 -rn); do
  PHASE_NUM=$(basename "$phase_dir")
  if [ ! -f "${phase_dir}gate.passed" ] && [ -f "${phase_dir}execution.jsonl" ]; then
    PHASE=$PHASE_NUM
    break
  fi
done

# Strategy 2: If no execution.jsonl found, find phases with reports but no gate
if [ -z "$PHASE" ]; then
  for phase_dir in $(ls -d agent_state/phases/*/ 2>/dev/null | sort -t/ -k3 -rn); do
    PHASE_NUM=$(basename "$phase_dir")
    if [ ! -f "${phase_dir}gate.passed" ] && [ -d "${phase_dir}reports" ]; then
      PHASE=$PHASE_NUM
      break
    fi
  done
fi

# Strategy 3: If still nothing, check for gate.failed files
if [ -z "$PHASE" ]; then
  LATEST_FAILED=$(ls -t agent_state/phases/*/gate.failed* 2>/dev/null | head -1)
  PHASE=$(echo "$LATEST_FAILED" | grep -oP 'phases/\K\d+')
fi
```

If no failed phase found:
```
✅ No failed phases detected

  All phases with execution logs have gate.passed.
  No orphaned reports or incomplete runs found.

  If you expected a failure: specify the phase explicitly with --phase=N
```

### Read Execution Log
```bash
EXEC_LOG="agent_state/phases/${PHASE}/execution.jsonl"
```

- Parse the log to find the last entry
- If last entry is `"status":"failed"`: that's the failure point
- If last entry is `"status":"started"` (no completion): agent was interrupted
- If last entry is `"event":"pipeline_complete"` with `"status":"gate_failed"`: gate blocked

### Determine Failed Command
If `--command` not specified:
- `pipeline_start` entry contains the command context
- If no explicit command marker: infer from which agents ran
  - Only `project_planner` + `spec_writer` → `/plan`
  - `backend_developer` + `api_developer` + test agents → `/develop`
  - Only test agents → `/test`
  - Only review agents → `/review`
  - Deploy agents → `/deploy`

```
Failure identified:
  Phase:     ${PHASE}
  Command:   ${COMMAND} (detected | specified)
  Last entry: ${LAST_ENTRY_SUMMARY}
  Log file:  ${EXEC_LOG}
```

---

## Step 1 — Timeline Reconstruction

Parse `execution.jsonl` chronologically. Build a complete timeline of the pipeline run.

### 1a. Parse All Entries
```bash
# Read all entries for the most recent pipeline run
# (entries after the last pipeline_start)
```

For each entry, extract:
- Timestamp
- Agent name
- Status (started, completed, failed)
- Duration (for completed/failed entries)
- Findings count (for completed entries)
- Error message (for failed entries)

### 1b. Build Timeline Display
```
Timeline:
  ${TIME}  pipeline_start                    ▶ Phase ${PHASE}, attempt ${ATTEMPT}
  ${TIME}  backend_audit_agent      12s  ✅  findings: 0 blocking, 2 warning
  ${TIME}  ui_audit_agent           8s   ✅  findings: 0 blocking, 1 warning
  ${TIME}  database_agent           45s  ✅
  ${TIME}  migration_agent          30s  ✅
  ${TIME}  backend_developer       4m2s  ✅
  ${TIME}  api_developer           2m1s  ✅
  ${TIME}  unit_test_agent         1m2s  ✅  42/42 passed
  ${TIME}  integration_test_agent    52s  ❌  8/11 passed, 3 FAILED
  ${TIME}  pipeline stopped — gate requirements not met
```

### 1c. Identify Failure Point
- Which agent failed (or was the last to start without completing)?
- At which step in the pipeline? (audit, implement, test, review, gate)
- How far through the pipeline was execution? (percentage of expected agents)

### 1d. [Deep only] Git Commit Timeline
Overlay git commits onto the execution timeline:
```bash
# Get commits during the pipeline window
git log --oneline --after="${PIPELINE_START}" --before="${PIPELINE_END}" --format="%H %ai %s"
```

Show which commits were made during which agent execution. This reveals if an agent committed code that broke a later agent.

---

## Step 2 — Failure Context

**Skipped in `quick` depth.**

### 2a. Failed Agent's Output
Read the failed agent's report or output file (if partially written):
- If the file exists: read the last section to understand where the agent stopped
- If the file doesn't exist: the agent crashed before writing any output
- If the file exists but is empty: the agent started writing but produced nothing

### 2b. Git Context
```bash
# Commits around the failure timestamp
git log --oneline -10 --before="${FAILURE_TIMESTAMP}" --format="%h %ai %s"

# What changed in the last commit before failure
git diff HEAD~1 --stat
```

- Were source files modified just before the failure?
- Were agent_state files modified?
- Were spec files changed?

### 2c. Pre-Failure Report Analysis
Read reports from agents that ran BEFORE the failure:
- Did any preceding agent report warnings or near-blockers?
- Did the audit agent flag issues related to the failure area?
- Were there escalations that got auto-resolved?

### 2d. Agent-Specific Context

**If the failed agent is a reviewer:**
- What findings did it report before failing?
- Was it stuck on a specific file or issue?
- Read the last complete finding to understand the pattern

**If the failed agent is a test runner:**
- Which tests failed? (from partial test output)
- What were the failure messages?
- Were these tests new or existing (regression vs new-code failure)?

**If the failed agent is an implementer:**
- What component was it working on?
- What was the last file it modified? (`git log --diff-filter=M --name-only -1`)
- Was it stuck in a read-loop? (check if output file is empty but agent ran for >5 minutes)

**If the failed agent is a planner/spec writer:**
- Were there missing BRD requirements?
- Was the context too large for the spec scope?
- Did a verification check fail?

### 2e. [Deep only] Full Artifact Reconstruction
Read ALL output files from the failed run:
- Every report in `agent_state/phases/${PHASE}/reports/`
- The manifest (if written)
- Decision log entries
- Debate verdicts (if any)
- Escalation records

Build a complete picture of what state the pipeline was in at the moment of failure.

---

## Step 3 — Root Cause Classification

Based on the timeline and context, classify the failure into one of these categories:

| Category | Description | Diagnostic Signals |
|----------|-------------|--------------------|
| **AGENT_FAILURE** | An agent crashed or produced invalid output | Agent started but no output file; output file is empty; output is malformed |
| **GATE_BLOCK** | Gate requirements not met — tests failing, review blockers | `pipeline_complete` with `gate_failed`; test reports show failures |
| **CONTEXT_EXHAUSTION** | Context window ran out mid-step | Agent ran >15 minutes with no output; output truncated mid-sentence |
| **DEPENDENCY_MISSING** | Required input artifact doesn't exist | Agent failed immediately (<5s); error references missing file |
| **SPEC_INCONSISTENCY** | Specs conflict with each other or BRD | Review found spec deviations; reconciliation failures |
| **EXTERNAL_FAILURE** | External system failure — Docker, npm, test infra | Error message references external tool; agent succeeded on previous run with same code |
| **ESCALATION_OVERFLOW** | Too many escalations triggered circuit breaker | `unresolved.json` exists; escalation count in execution log >10 |
| **STATE_CORRUPTION** | agent_state files corrupted or inconsistent | Invalid JSON in manifest; orphaned references; missing directories |

### Classification Process

1. **Check for obvious signals first:**
   - Failed agent + empty output → likely CONTEXT_EXHAUSTION or AGENT_FAILURE
   - Failed agent + error referencing missing file → DEPENDENCY_MISSING
   - Gate failed + test failures → GATE_BLOCK
   - Pipeline never completed + no failed entry → STATE_CORRUPTION or CONTEXT_EXHAUSTION

2. **Cross-reference with git history:**
   - Code changed since last successful run → potential code regression
   - No code changes → environment, state, or flaky failure

3. **Cross-reference with previous attempts:**
   - Same agent failed in previous attempt → systemic issue (not transient)
   - Different agent failed → cascading failures or environmental

4. **Assign confidence:**
   - HIGH: clear signal matches exactly one category
   - MEDIUM: signals point to one category but with some ambiguity
   - LOW: multiple categories possible — list all with likelihood

```
Root cause:
  Category:   ${CATEGORY}
  Confidence: ${HIGH | MEDIUM | LOW}
  Agent:      ${FAILED_AGENT}
  Step:       ${PIPELINE_STEP}
  Evidence:   ${KEY_EVIDENCE_1}
              ${KEY_EVIDENCE_2}
  Detail:     ${EXPLANATION}
```

### [Deep only] Alternative Hypotheses

If confidence is not HIGH, list alternative root causes:
```
Alternative hypotheses:
  1. GATE_BLOCK (70%) — 3 integration tests failing, likely missing error handling
  2. SPEC_INCONSISTENCY (20%) — spec says 409 but no conflict detection in spec
  3. EXTERNAL_FAILURE (10%) — test DB container restarted during run
```

---

## Step 4 — Impact Assessment

**Skipped in `quick` depth.**

### 4a. Completed Work
Enumerate what was successfully completed before the failure:
- Agents that completed successfully (from timeline)
- Files that were written/committed
- Tests that passed
- Reports that were generated

### 4b. Lost Work
Enumerate what was lost or never completed:
- Agents that never ran (downstream of the failure)
- Expected output files that don't exist
- Tests that were never executed
- Reviews that were never performed

### 4c. Salvageable Artifacts
Identify partial work that can be reused:
- Source code committed by implementation agents (committed = safe)
- Partial reports (may contain useful findings even if incomplete)
- Test results from passing test suites (unit tests pass even if integration failed)
- Audit reports (valuable even if implementation didn't complete)

### 4d. Re-run Scope
Determine what needs to be re-run vs what can be skipped:
- If failure was in testing: implementation is complete, only re-run from test step
- If failure was in review: tests passed, only re-run review + gate
- If failure was in implementation: may need to re-run from implementation step
- If failure was in audit: re-run everything (audit failure means bad assumptions)

```
Impact:
  Completed:   ${N} agents completed successfully
  Lost:        ${N} agents never ran
  Salvageable: ${LIST}
  Re-run from: ${STEP} (${EXPLANATION})
```

---

## Step 5 — Recovery Recommendations

Based on the root cause and impact, provide specific recovery steps.

### AGENT_FAILURE Recovery
```
Recovery — AGENT_FAILURE:
  1. Check if the agent file exists and is well-formed:
     cat .claude/agents/generated/${AGENT}.md | head -20
  2. Re-run: /develop --phase=${PHASE}
     (pipeline will re-run the failed agent)
  3. If agent keeps failing: check the agent's input files for validity
     /health --phase=${PHASE}
```

### GATE_BLOCK Recovery
```
Recovery — GATE_BLOCK:
  1. Fix the failing tests/review items:
     ${SPECIFIC_FILES_TO_FIX}
  2. Re-run: /develop --phase=${PHASE}
     (will resume from Wave 3 if implementation artifacts exist)
  3. Or targeted fix: /hotfix --phase=${PHASE} --component=${COMPONENT} --description="${FIX}"
```

### CONTEXT_EXHAUSTION Recovery
```
Recovery — CONTEXT_EXHAUSTION:
  1. The agent ran out of context window. This usually means:
     - Too many files loaded (simplify the phase scope)
     - Too many retry cycles (reduce component count)
     - Spec is too large (split into sub-components)
  2. Run /health --fix first to clean up interrupted state
  3. Re-run: /develop --phase=${PHASE}
  4. If it happens again: consider splitting the phase
```

### DEPENDENCY_MISSING Recovery
```
Recovery — DEPENDENCY_MISSING:
  1. The missing dependency: ${MISSING_FILE}
  2. This should have been created by: ${EXPECTED_SOURCE}
  3. Run /health --phase=${PHASE} to check state integrity
  4. If the dependency should exist: re-run the step that creates it
     ${SPECIFIC_COMMAND}
  5. If the dependency is from a previous phase: /develop --phase=${PREV_PHASE}
```

### SPEC_INCONSISTENCY Recovery
```
Recovery — SPEC_INCONSISTENCY:
  1. Conflicting specs: ${SPEC_A} vs ${SPEC_B}
  2. Run /plan --phase=${PHASE} --verify_only to identify all inconsistencies
  3. Fix specs manually or re-run /plan --phase=${PHASE}
  4. Then: /develop --phase=${PHASE}
```

### EXTERNAL_FAILURE Recovery
```
Recovery — EXTERNAL_FAILURE:
  1. External system that failed: ${SYSTEM}
  2. Verify it's running: ${HEALTH_CHECK_COMMAND}
  3. Re-run: /develop --phase=${PHASE}
     (transient failures usually resolve on retry)
  4. If persistent: check Docker, network, disk space
```

### ESCALATION_OVERFLOW Recovery
```
Recovery — ESCALATION_OVERFLOW:
  1. Too many decisions were unresolvable (${COUNT} escalations)
  2. Review: agent_state/debates/unresolved.json
  3. Resolve decisions manually or run /discuss --phase=${PHASE}
  4. Then: /develop --phase=${PHASE}
```

### STATE_CORRUPTION Recovery
```
Recovery — STATE_CORRUPTION:
  1. Run /health --fix to repair state
  2. If /health --fix cannot repair: /reset-phase --phase=${PHASE}
  3. Then: /develop --phase=${PHASE}
```

### General Recovery Checklist
Regardless of root cause:
```
Before retrying:
  [ ] Run /health --phase=${PHASE} to verify state integrity
  [ ] Check git status — no uncommitted agent_state changes
  [ ] Verify infrastructure is running (docker ps)
  [ ] Review the forensics report for anything the automated recovery might miss
```

---

## Step 6 — Write Forensics Report

Create a timestamped forensics report:

```bash
mkdir -p agent_state/forensics
REPORT="agent_state/forensics/${TIMESTAMP}-phase-${PHASE}.md"
```

Write the report:

```markdown
# Pipeline Forensics — Phase ${PHASE}
Investigation: ${TIMESTAMP}
Depth: ${DEPTH}

## Summary
- **Command:** /${COMMAND} --phase=${PHASE}
- **Failed at:** Step ${STEP} (${STEP_NAME}) — ${FAILED_AGENT}
- **Duration:** ${TOTAL_DURATION} (${DURATION_BEFORE_FAILURE} before failure)
- **Root cause:** ${CATEGORY} — ${ONE_LINE_SUMMARY}
- **Confidence:** ${HIGH | MEDIUM | LOW}

## Timeline
${FULL_TIMELINE}

## Failure Detail
${WHAT_FAILED_AND_WHY}

## Impact
- **Completed:** ${COMPLETED_COUNT} agents, ${COMMITTED_FILES} files committed
- **Lost:** ${LOST_COUNT} agents never ran
- **Salvageable:** ${SALVAGEABLE_LIST}

## Root Cause Analysis
**Category:** ${CATEGORY}
**Evidence:**
${EVIDENCE_LIST}

**Explanation:**
${DETAILED_EXPLANATION}

${IF_DEEP}
### Alternative Hypotheses
${ALTERNATIVES}
${END_IF}

## Recovery Plan
1. ${IMMEDIATE_FIX}
2. ${COMMAND_TO_RERUN}
3. ${ADDITIONAL_STEPS}

## Prevention
${WHAT_WOULD_PREVENT_THIS_IN_FUTURE}
```

### Console Output

```
Pipeline Forensics — Phase ${PHASE}
═══════════════════════════════════

  Command:    /${COMMAND} --phase=${PHASE}
  Failed at:  Step ${STEP} (${STEP_NAME}) — ${FAILED_AGENT}
  Duration:   ${TOTAL_DURATION} (of which ${BEFORE_FAILURE} before failure)
  Root cause: ${CATEGORY} — ${ONE_LINE_SUMMARY}

  Timeline:
    14:02:01  backend_audit_agent     12s  ✅
    14:02:15  database_agent          45s  ✅
    14:03:01  migration_agent         30s  ✅
    14:03:32  backend_developer      4m2s  ✅
    14:07:35  api_developer          2m1s  ✅
    14:09:37  unit_test_agent        1m2s  ✅ (42/42 passed)
    14:10:40  integration_test_agent   52s  ❌ (8/11 passed, 3 failed)
    14:11:32  pipeline stopped — gate requirements not met

  Failed tests:
    ✗ TestUserCreate_DuplicateEmail — expected 409, got 500
    ✗ TestUserUpdate_NotFound — expected 404, got 200
    ✗ TestUserDelete_Cascade — timeout after 30s

  Impact:
    ✅ 7 agents completed, code committed
    ❌ 4 agents never ran (review, acceptance, optimization, gate)
    ♻ Implementation salvageable — re-run from test step

  Recovery:
    1. Fix failing integration tests (likely missing error handling in user service)
    2. Re-run: /develop --phase=${PHASE}
       (will resume from Wave 3 — implementation artifacts exist)
    3. Alternatively: /hotfix --phase=${PHASE} --component=user-service --description="fix error handling"

  Report: agent_state/forensics/${TIMESTAMP}-phase-${PHASE}.md
```

---

## Rules

- `/forensics` is **strictly read-only** — it investigates, it does not modify code, state, or git history
- Every forensics report must have a **specific root cause category** — "something went wrong" is not a diagnosis
- If confidence is LOW, list all plausible hypotheses with likelihood percentages
- The timeline must show ALL agents that ran, not just the failed one — context matters
- Recovery recommendations must be **specific and actionable** — include exact commands, file paths, and explanations
- Never blame the user — pipeline failures are systemic. Forensics finds the systemic cause.
- Never recommend "just re-run it" without explaining what will be different this time
- The forensics report is append-only — each investigation gets a new timestamped file, never overwriting previous reports
- Quick depth is for fast triage when you already suspect the cause. Standard is the default. Deep is for persistent failures that resist diagnosis.
- If execution.jsonl doesn't exist, state this explicitly — the pipeline may have crashed before logging started (STATE_CORRUPTION or DEPENDENCY_MISSING)
- Cross-reference findings with `/health` results if a health report exists — don't duplicate that analysis
