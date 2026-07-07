---
command: develop
description: Implement a phase end-to-end. Audit → implement → test (unit + integration + e2e) → review → gate. Auto-detects current phase. Zero required inputs.
arguments:
  - name: phase
    required: false
    description: "Override phase number. Omit to auto-detect from gate state."
  - name: audit_only
    required: false
    default: false
    description: "Produce gap report only — no implementation, no code changes"
  - name: test_only
    required: false
    default: false
    description: "Run tests only — no implementation changes"
  - name: force_gate
    required: false
    default: false
    description: "Force gate to pass even with failures (e.g. known test flakes). Writes gate.passed with ⚠ FORCED flag. Use with caution."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode — all escalations use recommended defaults. Gate failures auto-fix (max 3 cycles) then force-gate with logging. No user prompts."
---

# /develop — Autonomous Phase Implementation

Fully autonomous phase implementation. Detects where you are, implements all specs, tests, reviews, and writes the phase gate.

**One decision point:** at the end — advance to the next phase or not.

**⚠ Concurrent access:** This command assumes a single developer per phase. If two developers run `/develop --phase=2` simultaneously, file conflicts will occur in `agent_state/phases/2/` and git commits may conflict. To coordinate: use separate phases, or ensure only one developer runs `/develop` at a time for a given phase number.

---

## Agent Execution Logging Protocol

Every agent spawned during /develop MUST append execution entries to:
`agent_state/phases/${PHASE}/execution.jsonl`

This file is append-only. Agents write entries during the pipeline; the file is only read at the end (Step 7) for the execution summary.

**On agent start:**
```json
{"ts":"<ISO>","agent":"<agent_name>","phase":N,"step":"<step_id>","status":"started"}
```

**On agent completion:** (`agent` MUST be the REAL agent name, matching a `roster.required` entry;
`report` MUST be the relative path to the agent's primary output, or `null` if it produces none —
`.claude/hooks/verify-gate.sh` checks that this file exists and is non-stub)
```json
{"agent":"<agent_name>","phase":N,"status":"completed","report":"<relative-path-or-null>","ts":"<ISO>","step":"<step_id>","duration_s":<N>,"findings":{"blocking":<N>,"warning":<N>}}
```

**On agent failure:**
```json
{"ts":"<ISO>","agent":"<agent_name>","phase":N,"step":"<step_id>","status":"failed","error":"<one_line_reason>","attempt":<N>}
```

**Pipeline completion:**
```json
{"ts":"<ISO>","event":"pipeline_complete","phase":N,"status":"gate_passed|gate_failed|gate_forced","total_duration_s":<N>,"agents_run":<N>,"agents_failed":<N>}
```

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

`/develop` is a long-running pipeline. Follow these rules to stay within the conversation context window:

**Agent result discipline — return summaries, not content:**
Every agent (subagent or inline) must end with this exact pattern:
```
✅ <agent-name> complete → wrote <output-file-path>
   Summary: <3 lines max of what was done>
   Issues: none | <count + severity>
```
The full output is in the file. The parent conversation receives only the summary above.
**Never echo file contents back to the parent conversation.**

**Read discipline — load-then-act, don't accumulate:**
- Read a file → act on it → do not re-read the same file in the same step
- Never load the same document twice in one step
- `phase_context.md` is read once at Step 0 and referenced from memory for the rest of the step

**Step isolation:**
Each step (Audit, Implement, Test, Review, Gate) is a complete unit. After a step writes its output files, the conversation for that step is finished. If the conversation window fills mid-step, the step can be resumed by reading the output files already written — all state is in `agent_state/phases/${PHASE}/`.

**Per-step context budget targets:**
| Step | Target input tokens | What to load |
|------|--------------------|----|
| Step 0 Orient | ~10K | phase_context.md (6-8K) + gate files |
| Step 1 Audit | ~20K | phase_context.md + per-spec file (one at a time) + prev manifest |
| Step 2 Implement (per agent) | ~25K | phase_context.md + own component spec + prev manifest |
| Step 3 Test | ~20K | phase_context.md + new code only (git diff this phase) + spec edge cases section |
| Step 3d Reconcile C | ~25K | all phase specs + agent implementation summaries (from manifests, not full code) |
| Step 3e Reconcile D | ~20K | spec test-coverage sections + test file list from unit/integration reports |
| Step 3f Optimize (per agent) | ~20K | phase_context.md + git diff for this phase only + skill pack §patterns |
| Step 3g Re-test | ~10K | test commands only — no new code reading needed |
| Step 4 Review | ~20K | code diff this phase only (not full src/) + skill pack §patterns section |
| Step 5 Acceptance | ~15K | phase_context.md §requirements + acceptance criteria + seed data |
| Step 6 Gate | ~8K | report file first 20 lines each (summary rows) — not full report content |

Note: `phase_context.md` is 6-8K but replaces 30-70K of BRD + IMPL_GUIDELINES. Loading it in every step is intentional and correct.

---

## Orchestration Protocol (HOW to execute this pipeline)

**⛔ HARD RULE: Use `/develop-orchestrator` instead of delegating this entire file to a single agent. The orchestrator script spawns separate agents per wave with verification between each. A single agent WILL drop review and acceptance steps — proven in Phase 1, 2, and 4 of the calculator project. This is NOT advisory — it is a structural requirement.**

**If you are a subagent reading this:** You should be executing ONE wave, not the entire pipeline. If your prompt says "run all 6 waves" — STOP. Tell the parent to use `/develop-orchestrator` instead.

### Mandatory Execution Pattern

The PARENT session (the one running /develop) MUST spawn separate agents for each wave and WAIT for completion before proceeding. DO NOT delegate the entire pipeline to a single subagent.

```
PARENT SESSION executes this sequence (not delegated):

1. Spawn Agent → Wave 1: ORIENT + AUDIT → wait for completion
   Verify: agent_state/phases/${PHASE}/audit_report.md exists

2. Spawn Agent(s) → Wave 2: IMPLEMENT → wait for completion
   Verify: source code committed, git diff shows new files

3. Spawn Agent(s) → Wave 3: TEST → wait for completion
   Verify: agent_state/phases/${PHASE}/reports/unit_tests.md exists
   Verify: agent_state/phases/${PHASE}/reports/e2e_results.md exists

4. Spawn Agent(s) → Wave 4: REVIEW + RECONCILE + ACCEPTANCE → wait for completion
   Spawn SEPARATE named agents (never one bundled "code quality" agent):
     code_reviewer_I, code_reviewer_II, security_reviewer, dependency_scanner,
     code_quality_verifier, tenant_isolation_verifier (if multi-tenant),
     spec_impl_reconciler, spec_test_reconciler, acceptance_test_agent
   Verify: reports/{code_review_I,code_review_II,security_review,dependency_scan,quality_gate,
           specs_vs_impl,spec_test_coverage,acceptance_report}.md all exist
   ⛔ DO NOT PROCEED WITHOUT THESE FILES — a missing one means an agent was dropped

5. PARENT reads all Wave 3+4 reports → builds collective feedback → Wave 5: ITERATE
   Verify: agent_state/phases/${PHASE}/reports/collective_feedback.md exists
   If fixes needed: spawn fix agents → re-run failed checks

6. PARENT evaluates gate → Wave 6: GATE
   Verify: ALL report files exist before writing gate.passed
```

### Gate File Precondition Check (HARD GATE)

Before writing `gate.passed`, the parent MUST verify these files exist:

```bash
REQUIRED_REPORTS=(
  "agent_state/phases/${PHASE}/reports/unit_tests.md"
  "agent_state/phases/${PHASE}/reports/integration_tests.md"
  "agent_state/phases/${PHASE}/reports/e2e_results.md"
  # Review dimensions — each a SEPARATE named agent (never bundled). Previously only a single
  # code_quality_review.md was required, which let security review + both reconcilers be skipped.
  "agent_state/phases/${PHASE}/reports/code_review_I.md"
  "agent_state/phases/${PHASE}/reports/code_review_II.md"
  "agent_state/phases/${PHASE}/reports/security_review.md"
  "agent_state/phases/${PHASE}/reports/dependency_scan.md"
  "agent_state/phases/${PHASE}/reports/quality_gate.md"
  # Reconciliation — spec↔impl and spec↔test. BLOCKING findings must be 0 to gate.
  "agent_state/phases/${PHASE}/reports/specs_vs_impl.md"
  "agent_state/phases/${PHASE}/reports/spec_test_coverage.md"
  "agent_state/phases/${PHASE}/reports/acceptance_report.md"
  "agent_state/phases/${PHASE}/reports/collective_feedback.md"
  "agent_state/phases/${PHASE}/manifest.json"
)
# tenant_isolation.md is required too, UNLESS the project is single-tenant (roster marks it
# not_applicable). Add it conditionally:
if grep -q '"tenant_isolation_verifier"[^}]*"status": *"required"' \
     "agent_state/phases/${PHASE}/roster.json" 2>/dev/null; then
  REQUIRED_REPORTS+=("agent_state/phases/${PHASE}/reports/tenant_isolation.md")
fi

# ⛔ AGENT-ROSTER COMPLETENESS — the execution guarantee (see develop-orchestrator Wave 0b/6).
# A missing report catches a dropped agent only if we remembered to list the report. The roster
# check is the backstop: it proves every REQUIRED agent has a "completed" entry in execution.jsonl.
# The single source of truth is .claude/hooks/verify-gate.sh — defer to it (it also checks that each
# completed line's report exists and is non-stub, and that no "failed" lacks a later "completed").
if [ -f ".claude/hooks/verify-gate.sh" ]; then
  bash .claude/hooks/verify-gate.sh "${PHASE}" || {
    echo "⛔ GATE BLOCKED by verify-gate.sh (roster.required vs execution.jsonl)."
    echo "   Re-spawn any missing/failed agents before gating."
    exit 1
  }
else
  # Fallback membership check (hook is authoritative — roster uses a flat "required" array of REAL
  # agent names, matching the "agent" field each writes to execution.jsonl).
  ROSTER="agent_state/phases/${PHASE}/roster.json"
  EXEC="agent_state/phases/${PHASE}/execution.jsonl"
  if [ -f "$ROSTER" ]; then
    python3 - "$ROSTER" "$EXEC" << 'PY' || exit 1
import json, sys, os
roster = json.load(open(sys.argv[1]))
required = roster.get("required", [])
completed = set()
if os.path.exists(sys.argv[2]):
    for line in open(sys.argv[2]):
        line = line.strip()
        if not line: continue
        try:
            e = json.loads(line)
            if e.get("status") == "completed": completed.add(e.get("agent"))
        except Exception: pass
missing = [a for a in required if a not in completed]
if missing:
    print("⛔ GATE BLOCKED — required agents never completed:", ", ".join(missing))
    sys.exit(1)
print("✓ Roster complete — every required agent ran.")
PY
  fi
fi

# Content validation — file existence is necessary but NOT sufficient.
# A report that says "0 tests" or "SKIPPED" must not pass the gate.
# This was added after dlp_composer shipped with ZERO E2E, ZERO component,
# ZERO acceptance, and ZERO pipeline tests despite report files existing.
TEST_REPORTS=("unit_tests.md" "integration_tests.md" "e2e_results.md" "acceptance_report.md")
for REPORT in "${TEST_REPORTS[@]}"; do
  FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
  if [ -f "$FILE" ]; then
    # Check for zero-test reports (file exists but no tests were actually run)
    if grep -qiP '(total.*:\s*0\b|0\s+tests?\s+(run|found|written|executed)|no tests|SKIPPED.*all|not applicable)' "$FILE" 2>/dev/null; then
      echo "⛔ GATE BLOCKED: ${REPORT} reports ZERO tests — this tier was skipped"
      echo "   Every test tier (unit, integration, e2e, acceptance) must produce >= 1 test."
      echo "   If a tier genuinely doesn't apply (e.g., no browser for a CLI tool),"
      echo "   the spec must declare this and the E2E report must contain CLI/pipeline tests instead."
    fi
  fi
done

# ⛔ FULL REGRESSION TEST (not just current phase)
# Run the ENTIRE test suite — ALL tiers, ALL phases — before writing gate.passed.
# This catches regressions where Phase N changes break Phase 1-N-1 tests.
# This was added after Phase 4 broke 6 Phase 1/2 E2E tests and gate.passed was written anyway.
#
# IMPORTANT: Read test commands from docs/IMPLEMENTATION_GUIDELINES.md — do NOT hardcode
# framework-specific commands. The commands below are EXAMPLES; adapt to the project's stack.

echo "Running full regression test suite (all phases, all tiers)..."

# ⛔ NO SILENT LANGUAGE DEFAULT. The test commands are read from the project's
# docs/IMPLEMENTATION_GUIDELINES.md ("## Common Tasks" table or a "Testing" section). If a command
# cannot be found there, the gate FAILS LOUDLY — it does NOT fall back to `go test ./...` (a Python /
# Node / Rust project would then "pass" by running a Go command that finds nothing). This was a real
# latent footgun: the old `read_from_guidelines "..." || echo "go test ./..."` fallback made the
# whole regression gate green on any non-Go project.
#
# read_cmd_from_guidelines <label-regex> — greps the guidelines for a labelled command and echoes it.
# Prints nothing (and returns non-zero) if not found. It invents NO default.
read_cmd_from_guidelines() {
  local label="$1" file="docs/IMPLEMENTATION_GUIDELINES.md"
  [ -f "$file" ] || return 1
  # Accept either a table row  | Run unit tests | `<cmd>` |  or a line  unit_test_command: <cmd>
  # Extract the first backtick-quoted command on a line matching the label.
  grep -iE "$label" "$file" | grep -oE '`[^`]+`' | head -1 | tr -d '`'
}

MISSING_CMDS=()
UNIT_CMD=$(read_cmd_from_guidelines 'unit[ _-]?test');           [ -z "$UNIT_CMD" ]  && MISSING_CMDS+=("unit")
INTEG_CMD=$(read_cmd_from_guidelines 'integration[ _-]?test');   [ -z "$INTEG_CMD" ] && MISSING_CMDS+=("integration")
E2E_CMD=$(read_cmd_from_guidelines 'e2e|end[ _-]?to[ _-]?end');  [ -z "$E2E_CMD" ]   && MISSING_CMDS+=("e2e")

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
  echo "⛔ GATE BLOCKED: could not determine the ${MISSING_CMDS[*]} test command(s) from"
  echo "   docs/IMPLEMENTATION_GUIDELINES.md. Add them under '## Common Tasks' (as \`backtick\` commands)"
  echo "   e.g.  | Run unit tests | \`pytest\` |  /  | Run e2e tests | \`npx playwright test\` |"
  echo "   Refusing to run a silent default — a wrong-language default would pass the gate by testing"
  echo "   nothing. Fix the guidelines, then re-run the gate."
  exit 1
fi

# Tier 1: Unit tests (all phases)
eval "$UNIT_CMD" 2>&1 | tee /tmp/gate-unit-results.txt
UNIT_EXIT=$?

# Tier 2: Integration tests (all phases — requires infra running)
eval "$INTEG_CMD" 2>&1 | tee /tmp/gate-integ-results.txt
INTEG_EXIT=$?

# Tier 3: E2E tests (all phases — project-type-aware: browser for web, CLI/pipeline for CLI/libs)
eval "$E2E_CMD" 2>&1 | tee /tmp/gate-e2e-results.txt
E2E_EXIT=$?

if [ $UNIT_EXIT -ne 0 ] || [ $INTEG_EXIT -ne 0 ] || [ $E2E_EXIT -ne 0 ]; then
    echo "⛔ GATE BLOCKED: Full regression test suite has failures"
    echo "   Unit tests:        $([ $UNIT_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
    echo "   Integration tests: $([ $INTEG_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
    echo "   E2E tests:         $([ $E2E_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
    echo "   Fix regressions before gating. Route failures to Wave 5 feedback loop."
    exit 1
fi
echo "✅ Full regression: all tiers pass (unit + integration + e2e)"

for f in "${REQUIRED_REPORTS[@]}"; do
  if [ ! -f "$f" ]; then
    echo "⛔ GATE BLOCKED: Missing required report: $f"
    echo "   Wave 4 (review + reconcile + acceptance) was likely skipped."
    echo "   Re-run the missing wave before gating."
    exit 1
  fi
done

# Review/reconcile reports must be real, not stubs.
for REPORT in code_review_I.md code_review_II.md security_review.md dependency_scan.md \
              quality_gate.md specs_vs_impl.md spec_test_coverage.md; do
  FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
  if [ -f "$FILE" ] && [ "$(wc -l < "$FILE")" -lt 3 ]; then
    echo "⛔ GATE BLOCKED: ${REPORT} is a stub — its agent did not actually run"
    exit 1
  fi
done

# Reconciliation must have zero unresolved BLOCKING findings.
for REPORT in specs_vs_impl.md spec_test_coverage.md; do
  FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
  if [ -f "$FILE" ] && grep -qiP '\bBLOCKING\b' "$FILE"; then
    echo "⛔ GATE BLOCKED: ${REPORT} has BLOCKING reconciliation findings — resolve or carry forward with a documented reason"
    exit 1
  fi
done
```

**If ANY required report is missing, gate.passed MUST NOT be written.** This prevents the exact failure mode we observed: implementation + tests pass, gate written, but no reviews or acceptance tests ever ran.

### Wave Details

**Wave 1: ORIENT + AUDIT**
- Single agent: read phase_context.md, audit existing code, produce gap report
- Output: `agent_state/phases/${PHASE}/audit_report.md`

**Wave 2: IMPLEMENT** (parallel agents per spec)
- database_agent → schema + migrations
- backend_developer → services + repositories
- api_developer → handlers + middleware + OTEL + OpenAPI
- ui_developer → components + hooks + engine + styles
- Output: source code committed

**Wave 3: TEST** (parallel)
- unit_test_agent → write + run unit tests
- integration_test_agent → write + run integration tests
- ui_test_agent → write + run Playwright E2E tests (MANDATORY)
- Output: test reports in `agent_state/phases/${PHASE}/reports/`

**Wave 4: REVIEW + ACCEPTANCE** (parallel tracks — ⛔ CANNOT BE SKIPPED)
- Track A: code review (style + architecture + security)
- Track B: acceptance tests (persona-based, per FR-*)
- Track C: code quality verification (TODOs, stubs, secrets, dead code)
- Track D: spec↔implementation reconciliation
- Output: review reports in `agent_state/phases/${PHASE}/reports/`

**Wave 5: COLLECTIVE FEEDBACK → ITERATE**
- Parent collects ALL findings from Waves 3+4 into single feedback document
- Categorize: A (code fix) / B (test fix) / C (spec ambiguity) / D (architectural)
- Fix all A+B+C items
- **Re-run protocol after fixes:**
  - If ANY code was changed: re-run ALL test tiers (unit + integration + E2E) — not just the failed tier
  - If E2E or acceptance failed: re-run E2E AND acceptance after fix (both test the user-facing surface)
  - If only tests were fixed (B category): re-run only the fixed test tier
- Max 3 cycles → D items escalate to debate_moderator
- Output: `agent_state/phases/${PHASE}/reports/collective_feedback.md`

**Wave 6: GATE**
- Verify ALL required reports exist (hard precondition)
- Evaluate pass/fail per gate item
- Write gate.passed + manifest.json
- Git tag `phase-N-complete`

### Why This Matters

In A/B testing, a single subagent executing /develop:
- Phase 1: Skipped code review, security review, acceptance tests, E2E tests entirely
- Phase 2: Skipped code review, acceptance tests, collective feedback — only fixed unicode escapes
- Both phases wrote gate.passed without review evidence

The multi-agent execution model is the ONLY way to guarantee all waves execute. The gate precondition check is the safety net — even if an orchestrator bug skips a wave, the gate won't pass without evidence files.

---

## Pipeline Anti-Rationalization Guard

**One rule:** Never skip a step, shortcut a gate, or accept partial results — even if it "seems fine." If you're tempted to skip, that's exactly when the step matters most. The table below lists specific temptations and their correct responses.

Before skipping ANY step, shortcutting ANY gate, or accepting partial results, review this table.

| Your Internal Reasoning | Correct Response |
|---|---|
| "Tests pass, so the implementation is correct" | Tests verify what the test author thought to check. Specs define what MUST exist. Run reconciliation. |
| "This is a simple phase, I can skip the audit step" | Simple phases are where assumptions hide. Run the audit. |
| "The gate has only one minor blocker, I'll pass it" | A blocker is a blocker. Fix it or use `--force_gate` with explicit user approval. |
| "I already reviewed this code when I wrote it" | You are the author. Authors don't find their own bugs. The reviewers are separate agents for a reason. |
| "Optimization isn't needed this phase — there's barely any code" | Optimization runs every phase. Even 5 lines of dead code compound over 10 phases. |
| "The previous phase tests still pass, no need for regression check" | Run them anyway. Silent import breakage is the #1 cross-phase regression. |
| "I'll skip the acceptance tests — unit and integration tests cover everything" | Unit/integration test code paths. Acceptance tests verify USER EXPERIENCE. They catch different bugs. |
| "I can combine the review stages to save time" | Review stages are separated for a reason. Spec compliance and code quality are DIFFERENT concerns. |
| "I've written enough tests — the important ones are covered" | Check the TC-* inventory. If spec defines 153 TC-* IDs and you implemented 34, that's 22% — not "enough". Every TC-* ID must have a test. |
| "Those TC-* IDs are for a different category, I'll skip them" | Process ALL categories in document order. Part 1 before Part 2. Never cherry-pick the easy tests. |
| "E2E tests don't apply — this isn't a web app" | EVERY product has an end-to-end flow. CLI tools have CLI E2E. Libraries have API E2E. Compilers have pipeline E2E. Adapt the strategy, don't skip the tier. |
| "Integration tests aren't needed — unit tests cover the logic" | Unit tests mock dependencies. Integration tests prove the mocks were correct. Without integration tests, you're testing your assumptions about external systems. |
| "A test tier produced 0 tests and that's fine" | Zero tests in ANY tier = gate blocker. Each tier catches different bugs. If a tier seems inapplicable, the spec or project type classification is wrong — fix that. |

---

## Phase Re-Development Protocol

When re-developing a phase (e.g., `gate.passed` was removed, or `/reset-phase` was run):

### 1. Before re-running

- Git tag current state: `git tag "phase-${PHASE}-attempt-${ATTEMPT}" -m "Phase ${PHASE} attempt ${ATTEMPT}: $(date)"`
  - `ATTEMPT` is determined by counting existing `phase-${PHASE}-attempt-*` tags + 1
- Archive previous reports: `mv agent_state/phases/${PHASE}/reports agent_state/phases/${PHASE}/reports.attempt-${ATTEMPT}`
- Clear ready signals: `rm -f agent_state/phases/${PHASE}/.*_ready`

```bash
# Detect attempt number
ATTEMPT=$(git tag -l "phase-${PHASE}-attempt-*" | wc -l | tr -d ' ')
ATTEMPT=$((ATTEMPT + 1))

# Tag current state
git tag "phase-${PHASE}-attempt-${ATTEMPT}" -m "Phase ${PHASE} attempt ${ATTEMPT}: $(date)"

# Archive previous reports (if they exist)
if [ -d "agent_state/phases/${PHASE}/reports" ]; then
  mv "agent_state/phases/${PHASE}/reports" "agent_state/phases/${PHASE}/reports.attempt-${ATTEMPT}"
fi

# Clear ready signals
rm -f agent_state/phases/${PHASE}/.*_ready
```

### 2. During re-run

- All agents run fresh (no caching from previous attempt)
- Previous attempt's code is NOT automatically reverted (agents build on existing code)
- If clean slate needed: user should `git reset` to the phase tag first (use `/reset-phase --hard`)

### 3. After completion

- Manifest includes: `"attempt": N, "previous_attempts": ["phase-N-attempt-1", "phase-N-attempt-2"]`
- Gate report includes diff from previous attempt:
  ```
  ## Changes from Previous Attempt
  - Attempt 1: 3 blockers (auth flow, CORS, migration order)
  - Attempt 2: 1 blocker (migration order — fixed by reordering)
  - Attempt 3: PASSED ✅
  ```

### Detection

At the start of Step 0, detect if this is a re-run:
```bash
if [ -d "agent_state/phases/${PHASE}/reports" ] || [ -d "agent_state/phases/${PHASE}/reports.attempt-1" ]; then
  echo "⚠ Phase ${PHASE} re-development detected — archiving previous attempt"
  # Execute pre-run archival steps above
fi
```

---

## Step 0 — Orient

### Detect current phase
```bash
LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}
echo "▶ Running Phase $PHASE"
```

### Initialize Execution Log

```bash
mkdir -p agent_state/phases/${PHASE}
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_start\",\"phase\":${PHASE},\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

### Failure Pattern Detection

Check if previous attempts at this phase failed at specific steps:

```bash
# Check for previous gate.failed files
PREV_FAILURES=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null)
if [ -n "$PREV_FAILURES" ]; then
  echo "⚠ Phase ${PHASE} has previous failure(s):"
  for f in $PREV_FAILURES; do
    BLOCKERS=$(python3 -c "import json; d=json.load(open('$f')); print(', '.join(b.get('gate_item','?') for b in d.get('blockers',[])))" 2>/dev/null)
    echo "  - $(basename $f): blocked by $BLOCKERS"
  done
  echo "  → Extra scrutiny will be applied to previously-failing steps"
fi
```

When a step that previously failed is reached:
- Log: `⚠ Step ${STEP} failed in previous attempt — applying extra verification`
- For test steps: run tests TWICE (once normally, once with verbose output)
- For review steps: lower the threshold for BLOCKING (MEDIUM → BLOCKING for previously-failing areas)
- For gate: explicitly verify previously-blocking items are resolved before checking new items

### Phase Lock (Advisory)

Before starting implementation, check for and create a lock:

```bash
LOCK_FILE="agent_state/phases/${PHASE}/.lock"
if [ -f "$LOCK_FILE" ]; then
  LOCK_OWNER=$(cat "$LOCK_FILE" | head -1)
  LOCK_TIME=$(cat "$LOCK_FILE" | tail -1)
  echo "⚠ Phase ${PHASE} is locked by ${LOCK_OWNER} since ${LOCK_TIME}"
  echo "  If this is stale, remove with: rm ${LOCK_FILE}"
  echo "  Proceeding may cause file conflicts in agent_state/phases/${PHASE}/"
  # In --auto mode: STOP. In interactive mode: ask user to confirm.
fi

# Create lock
echo "$(whoami)@$(hostname)" > "$LOCK_FILE"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOCK_FILE"
```

Release lock at the end of Step 6 (gate write):
```bash
rm -f "agent_state/phases/${PHASE}/.lock"
```

This is advisory — it warns but doesn't prevent. Two developers CAN override, but they're warned.

### Gate check
If PHASE > 1 and `agent_state/phases/$((PHASE-1))/gate.passed` is missing:
**STOP** — `Phase $((PHASE-1)) gate not found. Run /develop --phase=$((PHASE-1)) first.`

If `docs/design/phases/${PHASE}/INDEX.md` is missing:
**Auto-run `/plan --phase=${PHASE}` first**, then continue.

### Load previous phase context
Read `agent_state/phases/$((PHASE-1))/manifest.json` (if PHASE > 1):
- Surface `carried_forward[]` issues at the top of the Step 1 audit report
- Note existing code paths, API routes, DB schema from previous phases

### Cross-Phase Contract Validation (Phase > 1)

Before starting Phase N implementation, validate that data contracts are consistent with the previous phase's actual outputs:

1. Read `docs/design/phases/${PHASE}/specs/data-contracts.md`
2. Compare against Phase N-1 manifest's `api_routes` and `artifacts.code` to identify endpoints/fields that changed
3. If `data-contracts.md` references endpoints or fields that were modified, renamed, or removed in Phase N-1:
   - **BLOCKING** — data contracts may be stale. Re-run `/plan --phase=${PHASE}` or manually update `data-contracts.md`.
4. If Phase N specs extend an endpoint from Phase N-1 (e.g., adding fields to an existing response):
   - Verify the existing fields in `data-contracts.md` match what Phase N-1 actually implemented (check the code, not just the spec)
   - If mismatch: surface as `⚠ STALE CONTRACT: data-contracts.md says X, but Phase N-1 code returns Y`
5. **Schema evolution validation** — for endpoints that exist in BOTH Phase N-1 and Phase N contracts:
   - Phase N-1 response shape must be a **subset** of Phase N response shape (additive changes only)
   - If Phase N removes or renames a field from Phase N-1: **BLOCKING** — this breaks Phase N-1 consumers
   - If Phase N changes a field type (e.g., `string` → `number`): **BLOCKING** — type mismatch
   - If Phase N adds new required fields to a request: **WARNING** — Phase N-1 callers won't send them
   - Compare actual TypeScript interfaces from both `data-contracts.md` files, not just endpoint names
   - Surface any breaking changes: `⛔ BREAKING CHANGE: GET /users/:id field 'role' changed from string to enum — Phase N-1 code returns string`

### Breaking Change Detection (HARD BLOCK — not warning)

When comparing Phase N data-contracts.md against Phase N-1 actual implementation:

- **Field REMOVED from response** → ⛔ HARD BLOCK: `Field '${field}' was in Phase ${N-1} response but missing in Phase ${N} contract. This breaks Phase ${N-1} consumers.`
- **Field RENAMED** → ⛔ HARD BLOCK: `Field '${oldName}' renamed to '${newName}'. Phase ${N-1} consumers reference the old name.`
- **Field TYPE CHANGED** → ⛔ HARD BLOCK: `Field '${field}' changed from ${oldType} to ${newType}. Type mismatch.`
- **Field ADDED (optional)** → ✅ OK (additive, backward-compatible)
- **Field ADDED (required to request)** → ⚠ WARNING: Phase ${N-1} callers won't send this field

Hard blocks CANNOT be force-gated. Fix the contract or provide a migration path (deprecated field alias).

```bash
# Quick staleness check
if [ $PHASE -gt 1 ]; then
  PREV_MANIFEST="agent_state/phases/$((PHASE-1))/manifest.json"
  CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$PREV_MANIFEST" ] && [ -f "$CONTRACTS" ]; then
    echo "Validating data contracts against Phase $((PHASE-1)) manifest..."
    # Extract api_routes from previous manifest and verify they still exist in contracts
    python3 -c "
import json, sys
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
contracts = open('$CONTRACTS').read()
stale = [r for r in routes if r.split()[-1] not in contracts]
if stale:
    print('⚠ STALE CONTRACTS — routes in previous manifest not found in data-contracts.md:')
    for r in stale: print(f'  - {r}')
    sys.exit(1)
print('✅ Data contracts consistent with Phase $((PHASE-1)) manifest')
" || echo "⚠ Contract validation failed — review data-contracts.md before proceeding"
  fi
fi
```

### Schema Evolution Validation (PHASE > 1)

Before implementation begins, validate schema compatibility across phases:

1. Load ALL previous phases' `data-contracts.md` files (not just N-1 — schema evolution can span multiple phases)
2. Load current phase's `data-contracts.md`
3. For each interface/type that exists in BOTH current and previous phases:
   a. **Field additions:** ALLOWED (backward compatible) — log as INFO
   b. **Field removals:** ⛔ BREAKING CHANGE — route to user for decision:
      - Option A: Add field back (preserve compatibility)
      - Option B: Version the endpoint (create /v2/ route)
      - Option C: Confirm removal (document in manifest as `breaking_changes[]`)
   c. **Type changes:** ⛔ BREAKING CHANGE — same routing as removals
   d. **Array↔Object changes:** ⛔ CRITICAL BREAKING CHANGE — must version endpoint
4. Output: `agent_state/phases/${PHASE}/reports/schema_evolution.md`
5. Add to manifest: `"breaking_changes": [{"field": "...", "action": "removed|type_changed", "resolution": "versioned|confirmed|restored"}]`

```bash
# Schema evolution validation
if [ $PHASE -gt 1 ]; then
  echo "Validating schema evolution across all previous phases..."
  CURRENT_CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$CURRENT_CONTRACTS" ]; then
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_CONTRACTS="docs/design/phases/${PREV_PHASE}/specs/data-contracts.md"
      if [ -f "$PREV_CONTRACTS" ]; then
        echo "  Comparing Phase ${PHASE} contracts against Phase ${PREV_PHASE}..."
        # Compare interfaces — field removals and type changes are breaking
        python3 -c "
import re, sys

def parse_interfaces(text):
    interfaces = {}
    current = None
    for line in text.split('\n'):
        m = re.match(r'(?:export\s+)?interface\s+(\w+)', line)
        if m:
            current = m.group(1)
            interfaces[current] = {}
            continue
        if current and re.match(r'\s*}', line):
            current = None
            continue
        if current:
            fm = re.match(r'\s+(\w+)\??\s*:\s*(.+);', line)
            if fm:
                interfaces[current][fm.group(1)] = fm.group(2).strip()
    return interfaces

prev = parse_interfaces(open('$PREV_CONTRACTS').read())
curr = parse_interfaces(open('$CURRENT_CONTRACTS').read())
breaking = []

for iface in prev:
    if iface not in curr:
        continue
    for field, ftype in prev[iface].items():
        if field not in curr[iface]:
            breaking.append(f'⛔ BREAKING: {iface}.{field} REMOVED (was {ftype})')
        elif curr[iface][field] != ftype:
            breaking.append(f'⛔ BREAKING: {iface}.{field} TYPE CHANGED: {ftype} → {curr[iface][field]}')

if breaking:
    print('Schema evolution issues found (Phase ${PREV_PHASE} → Phase ${PHASE}):')
    for b in breaking: print(f'  {b}')
    sys.exit(1)
else:
    print('✅ Schema evolution clean: Phase ${PREV_PHASE} → Phase ${PHASE}')
" || echo "⚠ Schema evolution validation failed — review before proceeding"
      fi
    done
  fi
fi
```

### Breaking Change Propagation

When a breaking change is confirmed (not restored):
1. Identify all previous phases that consume the affected endpoint (check their manifests' `artifacts.api_routes`)
2. For each consuming phase:
   a. Check if consuming phase's tests still pass with the new contract
   b. If tests fail → the breaking change MUST be resolved before proceeding:
      - Version the endpoint (original route stays, new route added)
      - OR update consuming phase's code (cross-phase fix)
3. Log propagation results in `schema_evolution.md`

```bash
# Breaking change propagation — check all consuming phases
if [ $PHASE -gt 1 ] && [ -f "agent_state/phases/${PHASE}/reports/schema_evolution.md" ]; then
  BREAKING_COUNT=$(grep -c "⛔ BREAKING" "agent_state/phases/${PHASE}/reports/schema_evolution.md" 2>/dev/null || echo 0)
  if [ "$BREAKING_COUNT" -gt 0 ]; then
    echo "⚠ ${BREAKING_COUNT} breaking change(s) detected — checking consuming phases..."
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_MANIFEST="agent_state/phases/${PREV_PHASE}/manifest.json"
      if [ -f "$PREV_MANIFEST" ]; then
        python3 -c "
import json
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
if routes:
    print(f'  Phase ${PREV_PHASE} consumes {len(routes)} API routes — verify compatibility')
    for r in routes:
        print(f'    - {r}')
"
      fi
    done
    echo "  → Breaking changes MUST be resolved (version endpoint or update consumers) before proceeding."
    echo "  → Results logged to agent_state/phases/${PHASE}/reports/schema_evolution.md"
  fi
fi
```

### Phase Context Staleness Detection

Before loading `phase_context.md`, verify it's not stale relative to the BRD:

```bash
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
BRD_FILE="docs/BRD.md"
if [ -f "$CONTEXT_FILE" ] && [ -f "$BRD_FILE" ]; then
  CONTEXT_MTIME=$(stat -f %m "$CONTEXT_FILE" 2>/dev/null || stat -c %Y "$CONTEXT_FILE")
  BRD_MTIME=$(stat -f %m "$BRD_FILE" 2>/dev/null || stat -c %Y "$BRD_FILE")
  if [ "$BRD_MTIME" -gt "$CONTEXT_MTIME" ]; then
    echo "⚠ WARNING: BRD was modified AFTER phase_context.md was generated."
    echo "  BRD modified:     $(date -r $BRD_MTIME 2>/dev/null || date -d @$BRD_MTIME)"
    echo "  Context generated: $(date -r $CONTEXT_MTIME 2>/dev/null || date -d @$CONTEXT_MTIME)"
    echo "  Consider re-running /plan --phase=${PHASE} to refresh phase_context.md"
    echo "  Or proceed with caution — new BRD requirements may be missing from this phase."
  fi
fi
```

If staleness detected and the BRD diff includes new FR-* IDs not in `phase_context.md`: **BLOCKING** — re-run `/plan --phase=${PHASE}`.
If staleness detected but BRD changes are editorial (no new FR-*): **WARNING** — proceed with caution.

### Spec Staleness Warning

Before starting implementation, check if phase specs are older than 30 days:

```bash
SPEC_DIR="docs/design/phases/${PHASE}/specs"
if [ -d "$SPEC_DIR" ]; then
  NOW=$(date +%s)
  for SPEC in "$SPEC_DIR"/*.md; do
    [ -f "$SPEC" ] || continue
    SPEC_MTIME=$(stat -f %m "$SPEC" 2>/dev/null || stat -c %Y "$SPEC")
    DAYS_OLD=$(( (NOW - SPEC_MTIME) / 86400 ))
    if [ "$DAYS_OLD" -gt 60 ]; then
      echo "⛔ Phase ${PHASE} spec $(basename $SPEC) is ${DAYS_OLD} days old — strongly recommend /plan --refresh before /develop"
    elif [ "$DAYS_OLD" -gt 30 ]; then
      echo "⚠ Phase ${PHASE} spec $(basename $SPEC) is ${DAYS_OLD} days old — consider re-running /plan to refresh"
    fi
  done
fi
```

Neither warning is BLOCKING — user decides whether to proceed. Surface all stale specs together, then continue.

### Start infrastructure
```bash
# Bring up local dev stack from IMPLEMENTATION_GUIDELINES Section 5
# Commands vary per project — read docs/IMPLEMENTATION_GUIDELINES.md for exact commands
docker compose up -d  # (or equivalent from project setup)

# Wait for DB readiness (up to 60s)
# Health check command from IMPLEMENTATION_GUIDELINES
```

### Token/Cost Estimation

Before starting the pipeline, estimate total token usage for this phase. These estimates are **rough order-of-magnitude** — they exist for budgeting and expectation-setting, not precision. Actual usage varies with codebase size, spec complexity, and retry cycles.

**Estimation algorithm:**
1. Count components in phase specs: `NUM_COMPONENTS = count of spec files in docs/design/phases/${PHASE}/specs/` (exclude `data-contracts.md`, `phase_context.md`, and `INDEX.md` from count)
2. Determine if UI phase: `HAS_UI = true if wireframe specs exist`
3. Count previous phases for regression: `PREV_PHASES = PHASE - 1`
4. Base estimates per agent (input + output tokens):

| Agent | Model | Estimated Tokens | When |
|-------|-------|-----------------|------|
| backend_audit_agent | sonnet | ~15K | Always |
| ui_audit_agent | sonnet | ~15K | If HAS_UI |
| database_agent | opus | ~25K x NUM_DB_TABLES | Always |
| migration_agent | opus | ~20K | Always |
| backend_developer | opus | ~40K x NUM_COMPONENTS | Always |
| api_developer | opus | ~35K x NUM_COMPONENTS | Always |
| ui_developer | opus | ~45K x NUM_COMPONENTS | If HAS_UI |
| unit_test_agent | opus | ~30K x NUM_COMPONENTS | Always |
| integration_test_agent | opus | ~25K x NUM_COMPONENTS | Always |
| e2e_orchestrator | sonnet | ~20K | If e2e unlocked |
| acceptance_test_agent | opus | ~30K | Always |
| code_reviewer_I | sonnet | ~15K | Always |
| code_reviewer_II | opus | ~25K | Always |
| security_reviewer | opus | ~30K | Always |
| tenant_isolation_verifier | opus | ~20K | Always |
| code_quality_verifier | sonnet | ~10K | Always |
| spec_impl_reconciler | opus | ~25K | Always |
| spec_test_reconciler | sonnet | ~15K | Always |
| code_optimizer | sonnet | ~20K | Always |
| ui_code_optimizer | sonnet | ~20K | If HAS_UI |
| documentation_agent | sonnet | ~15K | Always |

5. Calculate total:
   ```
   TOTAL_TOKENS = sum of all applicable agent estimates

   Example for 3-component backend-only phase:
     Audit: 15K
     DB + Migration: 25K + 20K = 45K
     Implementation: (40K + 35K) x 3 = 225K
     Testing: (30K + 25K) x 3 + 30K = 195K
     Review: 15K + 25K + 30K + 20K + 10K = 100K
     Reconciliation: 25K + 15K = 40K
     Optimization: 20K
     Documentation: 15K
     TOTAL: ~655K tokens

   Example for 5-component full-stack phase:
     All above + UI agents
     TOTAL: ~1.2M tokens
   ```

6. Display estimate:
   ```
   Phase ${PHASE} Token Estimate
   ──────────────────────────────
   Components: ${NUM_COMPONENTS} (${HAS_UI ? "full-stack" : "backend-only"})
   Agents to run: ${AGENT_COUNT}
   Estimated tokens: ~${TOTAL_TOKENS} (${TOTAL_TOKENS > 1000000 ? "large phase" : "normal"})

   Breakdown:
     Implementation:  ~${IMPL_TOKENS} (${IMPL_PCT}%)
     Testing:         ~${TEST_TOKENS} (${TEST_PCT}%)
     Review:          ~${REVIEW_TOKENS} (${REVIEW_PCT}%)
     Other:           ~${OTHER_TOKENS} (${OTHER_PCT}%)

   Note: These are rough estimates for budgeting. Actual usage depends on
   codebase size, spec complexity, retry cycles, and escalation count.
   ```

7. **Large phase warning:**
   If TOTAL_TOKENS > 1,500,000: surface warning:
   "This phase is estimated at ~${TOTAL_TOKENS} tokens. Consider splitting into smaller phases or running /plan --split to break it down."

8. Add to execution.jsonl:
   ```bash
   echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"estimate\",\"phase\":${PHASE},\"estimated_tokens\":${TOTAL_TOKENS},\"components\":${NUM_COMPONENTS},\"has_ui\":${HAS_UI}}" >> agent_state/phases/${PHASE}/execution.jsonl
   ```

---

### Decision Log Protocol

All agents MUST log significant decisions to `agent_state/phases/${PHASE}/decision-log.md` (append-only):

```markdown
## Decision: <short title>
- **Agent:** <agent name>
- **Context:** <what prompted this decision>
- **Options considered:** <what alternatives existed>
- **Decision:** <what was chosen>
- **Rationale:** <why>
- **Impact:** <what this affects downstream>
```

Log when:
- Choosing between alternative implementations
- Deviating from spec (even slightly)
- Making an assumption not in the spec
- Choosing a library, pattern, or approach not prescribed

**Why:** Decisions made by agents in session 3 are invisible in session 7. The decision log creates persistent memory with accountability.

### Spec Amendment Protocol (Intentional Deviations)

When an implementation agent intentionally deviates from a spec:

1. **Log the deviation** in decision-log.md:
   ```
   ## Spec Deviation: <component> — <what changed>
   - **Spec says:** <original spec behavior>
   - **Implementation does:** <actual behavior>
   - **Rationale:** <why the deviation was necessary>
   - **Impact:** <what downstream artifacts need updating>
   ```

2. **Auto-update the spec** (append, don't overwrite):
   ```markdown
   ## Implementation Notes (auto-generated)
   > ⚠ Deviation from original spec — see decision-log.md
   > - <what changed and why>
   > - Original behavior preserved in section above
   ```

3. **Flag for reconciliation:** spec_impl_reconciler treats documented deviations as ACKNOWLEDGED (not MISSING).

This prevents specs from going stale after implementation while preserving the original design intent.

### Mid-Execution Escalation Protocol

When an agent encounters uncertainty, conflicting options, or missing data:

**LOW impact** (reversible, single-option): continue with `continueWithDefault: true`
```json
{ "type": "escalation", "impact": "LOW", "recommendation": "A", "continueWithDefault": true }
```

**MEDIUM/HIGH impact** (architecture, security, data model): escalate to Debate Team
```json
{
  "type": "debate_request",
  "from_agent": "<agent name>",
  "from_step": "<pipeline step>",
  "decision": "<what needs deciding>",
  "options": [
    { "id": "A", "label": "...", "initial_reasoning": "..." },
    { "id": "B", "label": "...", "initial_reasoning": "..." }
  ],
  "context": "<BRD refs, constraints, what's known>",
  "impact": "HIGH | MEDIUM",
  "domain": "architecture | security | data_model | feature",
  "blocking": true
}
```

Write to `agent_state/debates/<step>-<topic>.json`.

The `debate_moderator` picks it up and runs:
1. **Researchers** (parallel) — gather evidence for each option
2. **Advocates** (parallel, HIGH only) — argue for each option adversarially
3. **Arbitrator** — evaluates all arguments, produces scored verdict

Verdict written to `agent_state/debates/<topic>-verdict.json`. The requesting agent reads it and continues.

**This replaces guessing with researched, debated, scored decisions.**

### Escalation Circuit Breaker

Prevent runaway escalation loops that consume context and time:

- **Max escalations per step:** 3 — if a single step (e.g., Step 2 Implementation) triggers more than 3 debate requests, STOP escalating. Write remaining decisions to `agent_state/debates/unresolved.json` with recommended defaults.
- **In `--auto` mode:** continue with defaults for all unresolved decisions, but flag ALL as `"⚠ AUTO-RESOLVED — may need review"` in the decision log and manifest `known_issues[]`.
- **⛔ SECURITY ESCALATION EXCEPTION:** Escalations with `"domain": "security"` are NEVER auto-resolved. In `--auto` mode, security decisions MUST use the **hardened default** (the option that is MORE restrictive / MORE secure). Log as `"⚠ SECURITY — hardened default applied, review recommended"`. Security escalations include: auth patterns, token storage, IDOR mitigation, encryption, PII handling, CORS/CSRF config, rate limiting. If no clearly hardened default exists → EXIT auto mode for this decision and surface to user.
- **Max total escalations per phase:** 10 — if exceeded, EXIT auto mode entirely. Surface all unresolved decisions to the user with: `"⛔ Phase ${PHASE} exceeded escalation limit (10). Review agent_state/debates/unresolved.json before continuing."`
- **Max escalation depth:** 2 — if a debate triggers another debate (e.g., arbitrator can't decide and re-escalates), the second-level debate auto-resolves with the recommended default (except security — always hardened). A third-level escalation is NEVER allowed.

```json
// agent_state/debates/unresolved.json
{
  "phase": N,
  "unresolved_count": 4,
  "decisions": [
    {
      "topic": "cache_strategy",
      "from_agent": "backend_developer",
      "auto_resolved_with": "A",
      "confidence": "LOW",
      "reason": "escalation_limit_exceeded",
      "needs_review": true
    }
  ]
}
```

### Universal Agent Return Protocol

Every agent spawned during this command MUST end by returning this exact format — nothing more — to the parent conversation:

```
✅ <agent-name> — <status: complete | blocked | partial>
   Wrote: <output file path>
   Done:  <what was implemented in one line>
   Issues: none | <N blocking / N warning>
```

If the agent encountered blockers, append:
```
   Blocker: <one-line description> → see <file path> for details
```

**The parent reads the output file to get details. It does NOT ask the agent to reproduce or summarize the file contents.**

### Analysis Paralysis Guard (applies to ALL agents spawned by this command)

If an agent makes **5+ consecutive read-only tool calls** (Read, Grep, Glob, Bash with read-only commands) without any write action (Edit, Write, Bash with write commands), the agent MUST:

1. **Stop exploring** — do not make another read call
2. **State the blocker** — write a 1-line summary of what's preventing action:
   - "Blocker: can't find the file X expected by spec Y"
   - "Blocker: interface mismatch between service and handler"
3. **Take action** — either:
   - Write code to resolve the blocker
   - Write the blocker to the output file and return to the parent with `status: blocked`

**Why:** Agents get stuck in read-loops, consuming context tokens without making progress. 5 consecutive reads without a write is a strong signal of analysis paralysis.

**Exception:** `backend_audit_agent` and `ui_audit_agent` are read-only by design — this guard does NOT apply to audit agents.

---

### Placeholder Convention
Throughout all agent files and commands:
- `${PHASE}` — current phase number (bash variable, numeric)
- `$((PHASE-1))` — previous phase number (bash arithmetic)
- `{{PHASE}}` — when used inside agent `.md` files, means "substitute the current phase number here at runtime"
- `{{PHASE-1}}` — when used inside agent `.md` files, means "substitute the previous phase number (current minus 1) here at runtime"

Agents reading `{{PHASE-1}}` in their instructions should resolve this to `PHASE - 1` before looking up any path.

---

### Agent Context Protocol — Minimal, targeted reads

**Primary context — agents load these, nothing more by default:**

| File | Size | Contains |
|------|------|----------|
| `docs/design/phases/${PHASE}/phase_context.md` | ~6-8K | Complete tech stack, all conventions, security NFRs, full acceptance criteria, what already exists, gate checklist |
| `docs/design/phases/${PHASE}/specs/<own-component>.md` | ~5-10K | Interface contracts, data model, edge cases, test requirements for THIS component only |
| `docs/design/phases/${PHASE}/specs/data-contracts.md` | ~3-5K | Typed TypeScript interfaces for ALL API endpoints — ARRAY vs OBJECT explicit. Source of truth for response shapes. |
| `agent_state/phases/$((PHASE-1))/manifest.json` | ~3-5K | Existing routes, schema, services — what NOT to re-implement |
| `agent_state/codebase/<relevant-focus>.md` | ~5-10K | Persistent codebase knowledge (if `/map` was run). Load focus area matching your role: `tech.md` for stack decisions, `architecture.md` for structure, `quality.md` for patterns, `concerns.md` for known issues. |

**Codebase knowledge loading rule:** If `agent_state/codebase/` exists and contains `.last-mapped`, agents MUST load the focus document relevant to their role. `backend_developer` and `api_developer` load `architecture.md`. `code_reviewer_I` and `code_optimizer` load `quality.md`. `security_reviewer` loads `concerns.md`. `project_planner` and `backend_audit_agent` load ALL focus documents. If the directory does not exist, skip — `/map` is optional but its output is mandatory reading when present.

`phase_context.md` is intentionally complete — it contains the full tech stack, all coding conventions, all security requirements, and all acceptance criteria needed for correct implementation. **It is not a 50-line stub — it is a structured 6-8K extract that replaces the need to load the full BRD and IMPLEMENTATION_GUIDELINES.**

**Escalation (only when phase_context.md leaves something unresolved):**
- More detail on a specific requirement → `docs/BRD.md` — read only the specific FR-* row
- Infra setup commands → `docs/IMPLEMENTATION_GUIDELINES.md §Local Development Setup` only
- Adjacent component's interface → `docs/design/phases/${PHASE}/specs/<other-component>.md`

**Never load:**
- The entire `docs/BRD.md` (except: brd_spec_reconciler, requirements_brd_reconciler, acceptance_test_agent)
- The entire `docs/IMPLEMENTATION_GUIDELINES.md` (except: agent_factory, architecture_orchestrator)
- All spec files at once — load your component's spec only

---

## Step 0.5 — Implementation Readiness Gate (HARD GATE)

**Before ANY implementation starts, verify these prerequisites.** This prevents wasted implementation cycles when specs are incomplete or misaligned.

```bash
# Check 1: Specs exist for this phase
SPECS_DIR="docs/design/phases/${PHASE}/specs"
SPEC_COUNT=$(ls ${SPECS_DIR}/*.md 2>/dev/null | wc -l)
if [ "$SPEC_COUNT" -eq 0 ]; then
  echo "⛔ BLOCKED: No specs found at ${SPECS_DIR}/. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 2: phase_context.md exists and is non-trivial
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
if [ ! -f "$CONTEXT_FILE" ] || [ $(wc -l < "$CONTEXT_FILE") -lt 20 ]; then
  echo "⛔ BLOCKED: phase_context.md missing or too short. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 3: VERIFICATION_REPORT.md exists (specs were verified against BRD)
VERIFY_FILE="docs/design/phases/${PHASE}/VERIFICATION_REPORT.md"
if [ ! -f "$VERIFY_FILE" ]; then
  echo "⛔ BLOCKED: No verification report. Run /plan --phase=${PHASE} to verify specs against BRD."
  exit 1
fi

# Check 4: BRD↔Spec reconciliation passed (no unresolved MISSING coverage)
RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
if [ -f "$RECON_FILE" ] && grep -q "MISSING" "$RECON_FILE"; then
  echo "⚠ WARNING: BRD↔Spec reconciliation has MISSING coverage. Review before implementing."
fi

# Check 5: data-contracts.md exists (typed API response shapes)
CONTRACTS_FILE="docs/design/phases/${PHASE}/specs/data-contracts.md"
if [ ! -f "$CONTRACTS_FILE" ]; then
  echo "⚠ WARNING: data-contracts.md missing. API↔UI binding errors likely. Run /plan --phase=${PHASE} Step 2b."
fi
```

**If any check fails:** STOP. Do not proceed to Step 1. Surface the specific failure and recommend `/plan --phase=${PHASE}`.

**Anti-rationalization:** "The specs are good enough to start" → No. Incomplete specs produce incomplete implementations that fail at acceptance tests. Fix the specs first.

---

## Step 1 — Audit

**Agents (parallel):**
- `backend_audit_agent` — always runs
- `ui_audit_agent` — runs only if `frontend.enabled = true` in `docs/IMPLEMENTATION_GUIDELINES.md`

Both agents read all Step 0 context. `backend_audit_agent` writes `agent_state/phases/${PHASE}/audit_report.md`. `ui_audit_agent` writes `agent_state/phases/${PHASE}/audit_report_ui.md`.

```markdown
# Phase N Audit Report

## Carried Forward Issues (from Phase N-1)
[Issues from previous manifest's carried_forward[] — MUST appear here]

## Gap Analysis
| Component | Expected (from spec) | Found (in codebase) | Gap |
|-----------|---------------------|---------------------|-----|

## Missing Implementations
- [ ] <component/function> — required by spec <file.md>

## Broken/Incomplete Items
- [ ] <item> — reason

## Recommended Implementation Order
1. ...
```

If `--audit_only` flag: stop here and print the report.

---

## Step 2 — Implementation (Build-step Parallel Execution)

> **⛔ Vocabulary note:** "Wave 1–6" is RESERVED for the six-wave macro model (Orient/Audit,
> Implement, Test, Review, Iterate, Gate) used throughout this file and `/develop-orchestrator`.
> Step 2's internal build order below uses a SEPARATE, non-colliding label — **Build-step B\*** — so
> no "Wave N" ever means two different things. This entire Step 2 tree is the internal decomposition
> of macro Wave 2 (IMPLEMENT).

**Agents:** Generated agents from `.claude/agents/generated/` per component type

Run implementation in the build-steps defined in `PHASE_PLAN.md`. Each build-step runs its agents in
parallel; build-steps are sequential.

**Typical build-step structure:**
```
Build-step B1 (parallel):
  ├─ database_agent     → schema design + docs/design/database.md
  └─ migration_agent    → migration files (up + down)

Build-step B1-gate (sequential gate — validates migrations before applying):
  └─ Migration Validation → dry-run migrations against test DB
      Checks:
      1. Migration files parse without syntax errors
      2. UP migration applies cleanly to empty test DB
      3. DOWN migration reverses the UP cleanly
      4. UP re-applies after DOWN (idempotency)
      If validation fails → block Build-step B2a, surface error to migration_agent for fix (max 1 retry)

### Migration Failure Auto-Recovery

If UP migration fails:
1. Immediately run the DOWN migration for the failed file to restore schema consistency
2. Log the specific error: `⛔ Migration ${FILE} UP failed: ${ERROR}`
3. Log the rollback: `↩ Auto-rolled back ${FILE} DOWN to restore schema`
4. Route back to migration_agent with the specific error for fix (max 1 retry)
5. After fix: re-run UP → validate → proceed if success

If DOWN rollback also fails:
- STOP immediately — schema is now in an unknown state
- Surface: `⛔ CRITICAL: Migration UP failed AND DOWN rollback failed. Manual intervention required.`
- Write to agent_state/phases/${PHASE}/migration_failure.json with full error details
- Do NOT proceed to Build-step B2a

This prevents the common failure where Phase N migration adds a table, fails partway through,
and Phase N re-development tries to add the same table again.

**Migration Safety Gate (BLOCKING):**
- Zero CRITICAL findings in migration_safety.md
- All DOWN migrations exist and are non-empty
- Irreversible migrations explicitly acknowledged in migration metadata
- If any CRITICAL finding: STOP — do not apply migration until resolved

Build-step B2a (sequential — api_developer depends on backend service interfaces):
  └─ backend_developer  → domain models, services, repositories
       ↓ writes manifest with service method return types (list/single/none)

Build-step B2a-check (COMPILE/TYPECHECK GATE — BLOCKING):
  └─ Build verification: compile/typecheck the codebase
       See "Build-step B2a-check — Compile/Typecheck Gate" section below
       If FAILS → route back to backend_developer for fix (max 2 attempts)
       Do NOT proceed to Build-step B2b on broken code

### Build-step B2a-check — Compile/Typecheck Gate (BLOCKING)

**Purpose:** Catch compilation errors before downstream agents build on broken code. This is cheap (seconds to run) but prevents expensive downstream failures where api_developer builds on code that doesn't compile.

**Language-specific commands:**
| Language | Command | Pass Condition |
|----------|---------|---------------|
| Go | `go build ./...` | Exit code 0 |
| TypeScript | `tsc --noEmit` | Exit code 0 |
| Python | `python -m py_compile <changed_files>` + `mypy <changed_files>` (if mypy configured) | Exit code 0 |
| Java | `mvn compile -q` or `gradle compileJava` | Exit code 0 |
| Rust | `cargo check` | Exit code 0 |

**Detection:** Read `docs/IMPLEMENTATION_GUIDELINES.md` to determine the primary backend language, then run the corresponding command.

```bash
# Detect language from IMPLEMENTATION_GUIDELINES and run compile check
# The exact command depends on the project's tech stack
# Examples:
#   Go:         go build ./...
#   TypeScript: npx tsc --noEmit
#   Python:     python -m py_compile $(git diff --name-only --diff-filter=AM HEAD -- '*.py')
#   Java:       mvn compile -q  OR  gradle compileJava
#   Rust:       cargo check
```

**On failure:**
1. Capture compiler error output (first 50 lines)
2. Route back to `backend_developer` with the error output as context
3. Max 2 fix attempts — backend_developer reads compiler errors, fixes, then re-runs compile check
4. If still failing after 2 attempts: **STOP** — surface compiler errors to user
5. Do **NOT** proceed to Build-step B2b (api_developer) on broken code — api_developer will build on a broken foundation

**On success:**
```
✅ Build-step B2a-check — Compile/Typecheck Gate PASSED
   Language: <detected language>
   Command: <command run>
   → Proceeding to Build-step B2b (api_developer)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"B2a-check\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

### Agent Handoff Protocol (Build-step B2a → B2b)

After backend_developer completes — **atomic write + verified ready signal:**
1. Write manifest to `.tmp` first: `agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
2. Validate JSON: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
3. If valid: atomic move: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not touch ready signal. Log error and retry manifest write (max 1 retry).
5. Verify report exists: `test -f agent_state/phases/${PHASE}/reports/backend_developer.md`
6. **Only after steps 1-5 succeed:** Touch ready signal: `touch agent_state/phases/${PHASE}/.backend_developer_VERIFIED`

```bash
# Atomic agent handoff — prevents downstream agents from reading partial manifests
MANIFEST_DIR="agent_state/phases/${PHASE}/backend_developer"
python3 -c "import json,sys; json.load(sys.stdin)" < "${MANIFEST_DIR}/manifest.json.tmp" && \
  mv "${MANIFEST_DIR}/manifest.json.tmp" "${MANIFEST_DIR}/manifest.json" && \
  touch "agent_state/phases/${PHASE}/.backend_developer_VERIFIED" || \
  { echo "⛔ backend_developer manifest invalid — blocking handoff"; exit 1; }
```

Before api_developer starts:
1. Check: `test -f agent_state/phases/${PHASE}/.backend_developer_VERIFIED` (**VERIFIED, not just ready**)
2. If missing: WAIT or FAIL — do not proceed with stale/missing data
3. Validate manifest is readable: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json`
4. Read `backend_developer/manifest.json` for service method return types

This pattern applies to ALL wave transitions where one agent depends on another's output. The **atomic write + verified ready signal** prevents race conditions where a downstream agent reads a partial or corrupt manifest.

Build-step B2b (depends on B2a passing build + backend_developer ready signal):
  └─ api_developer      → API handlers, routes, middleware, DTOs, api-contracts.md
       ↓ reads data-contracts.md from /plan as MANDATORY source of truth for response shapes
       ↓ api-contracts.md is DERIVED from data-contracts.md (validates, doesn't reinvent)
       ↓ if api-contracts.md shapes differ from data-contracts.md → BLOCKER
       ↓ reads backend_developer manifest to pick respondList/respondOne/respondError

Build-step B2b-check (API LAYER COMPILE CHECK — BLOCKING):
  └─ Build verification: compile/typecheck after api_developer's changes
       Same compile/typecheck command as Build-step B2a-check
       Verifies api_developer's changes compile cleanly WITH backend_developer's code
       If FAILS → route back to api_developer for fix (max 2 attempts), then STOP

### Build-step B2b-check — API Layer Compile Check (BLOCKING)

**Purpose:** Verify that api_developer's changes compile cleanly alongside backend_developer's code. API handlers frequently reference service interfaces, DTOs, and error types — type mismatches between layers are the most common inter-agent failure mode.

**Command:** Same language-specific compile/typecheck command as Build-step B2a-check (see table above).

**On failure:**
1. Capture compiler error output (first 50 lines)
2. Route back to `api_developer` with the error output as context
3. Max 2 fix attempts — api_developer reads compiler errors, fixes, then re-runs compile check
4. If still failing after 2 attempts: **STOP** — surface compiler errors to user
5. Do **NOT** proceed to Build-step B2-contract/B2-smoke/B3 on broken code

**On success:**
```
✅ Build-step B2b-check — API Layer Compile Check PASSED
   Language: <detected language>
   Command: <command run>
   → Proceeding to Build-step B2-contract/B2-smoke (contract validation / smoke test)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"B2b-check\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

Build-step B2-contract (sequential gate, UI phases only):
  └─ Contract Validation → verify api-contracts.md exists, all endpoints documented, shapes are unambiguous

Build-step B2-smoke (SMOKE TEST — before expensive UI implementation):
  └─ Quick smoke test: does the app start? Does GET /health respond?
       docker compose up -d && curl -sf http://localhost:PORT/health
       If FAILS → route back to api_developer for fix (max 1 retry)
       This catches catastrophic failures before spending tokens on UI + test agents

Build-step B3 (parallel, UI phases only — BLOCKED until Build-step B2-smoke passes):
  └─ ui_developer       → screen implementation from UI specs + api-contracts.md + data-contracts.md

Build-step B3-check (FRONTEND BUILD CHECK — BLOCKING, UI phases only):
  └─ Build verification: full frontend build after ui_developer's changes
       See "Build-step B3-check — Frontend Build Check" section below
       If FAILS → route back to ui_developer for fix (max 2 attempts), then STOP

### Build-step B3-check — Frontend Build Check (BLOCKING, if UI phase)

**Purpose:** Catch frontend build failures before expensive test agents run. UI code frequently has TypeScript errors, missing imports, or JSX/TSX issues that are invisible until a full build runs.

**Skip if:** `frontend.enabled = false` or this phase has no UI components (no Build-step B3).

**Commands:**
| Framework | Command | Pass Condition |
|-----------|---------|---------------|
| React (CRA) | `npm run build` | Exit code 0 |
| Next.js | `npx next build` | Exit code 0 |
| Vue/Nuxt | `npm run build` | Exit code 0 |
| Vite | `npx vite build` | Exit code 0 |
| Angular | `npx ng build` | Exit code 0 |

**Additional checks (run after build passes):**
- TypeScript strict mode: `tsc --noEmit --strict` (if `tsconfig.json` has `strict: true`)
- ESLint: `npx eslint src/ --max-warnings 0` (zero warnings policy — catches unused imports, type issues)

**Detection:** Read `package.json` to determine the framework and build command. Fall back to `npm run build` if unclear.

```bash
# Detect frontend framework and run build check
# Read package.json for scripts.build or framework-specific dependencies
# Examples:
#   React/CRA:  npm run build
#   Next.js:    npx next build
#   Vue:        npm run build
#   Vite:       npx vite build
#
# Additional TypeScript check (if tsconfig.json exists):
#   npx tsc --noEmit
#
# ESLint check (if .eslintrc exists or eslint in package.json):
#   npx eslint src/ --max-warnings 0
```

**On failure:**
1. Capture build error output (first 50 lines)
2. Route back to `ui_developer` with the error output as context
3. Max 2 fix attempts — ui_developer reads build errors, fixes, then re-runs build check
4. If still failing after 2 attempts: **STOP** — surface build errors to user
5. Do **NOT** proceed to Build-step B4 (test agents) on broken frontend code

**On success:**
```
✅ Build-step B3-check — Frontend Build Check PASSED
   Framework: <detected framework>
   Build command: <command run>
   TypeScript check: PASSED | SKIPPED (no tsconfig)
   ESLint check: PASSED | SKIPPED (no eslint config)
   → Proceeding to Build-step B4 (test agents)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"frontend_build_check\",\"step\":\"B3-check\",\"status\":\"passed|failed\",\"framework\":\"<framework>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

Build-step B4 (parallel — test agents read BOTH specs AND implementation code):
  ├─ unit_test_agent     → unit tests for all new code (reads actual functions, not just specs)
  └─ integration_test_agent → integration tests for service↔infra + contract shape tests
```

> **Note:** Build-step B4 above is the initial unit/integration test authoring that runs INSIDE macro
> Wave 2's implement loop. It does not replace macro **Wave 3 (TEST)**, which spawns the separate
> per-tier test agents (unit / integration / e2e) under `/develop-orchestrator`.

Each agent:
1. Reads ALL Step 0 context + its specific spec files
2. Reads its activated skill pack (`.claude/skills/languages/{{LANG}}.md` etc.)
3. Implements only what is in scope for this phase (prev manifest shows what exists)
4. Writes an agent-level manifest to `agent_state/phases/${PHASE}/<agent>/manifest.json`

---

## Step 2.5 — API Contract Validation (UI phases only)

**When:** `frontend.enabled = true` in IMPLEMENTATION_GUIDELINES AND this phase includes UI screens
**Runs after:** Build-step B2b (backend_developer + api_developer complete) — this IS Build-step B2-contract
**Blocks:** Build-step B3 (ui_developer will NOT start until this passes)

Validate that `api_developer` produced a complete, unambiguous contract artifact:

```bash
CONTRACT_FILE="docs/design/phases/${PHASE}/specs/api-contracts.md"
```

**Checks (inline — no separate agent needed):**

1. **File exists:** `api-contracts.md` must exist and be non-empty
2. **All routes covered:** every route in `agent_state/phases/${PHASE}/api_developer/manifest.json` must have a matching entry in `api-contracts.md`
3. **Shape unambiguity:** for each endpoint entry:
   - Response shows explicit `"data": [...]` (array) or `"data": {...}` (object) — not just `"data": ...`
   - Empty state documented (list: `[]`, single: `null`)
   - All fields have types (no untyped `"field": "object"`)
4. **Data contract compliance:** every endpoint in `api-contracts.md` matches the TypeScript interface in `data-contracts.md` from /plan:
   - Field names match exactly
   - Array vs object matches exactly
   - If mismatch: `⚠ api-contracts.md GET /api/v1/users returns data as object, but data-contracts.md defines it as User[] (array)`
   - Route back to `api_developer` for fix (max 1 retry)
5. **Wireframe cross-reference:** for each wireframe API binding (`| Component | Endpoint | Fields Used |`):
   - The endpoint exists in `api-contracts.md`
   - The fields referenced exist in the contract's response shape
   - List vs single matches what the UI component expects (e.g., a table expects an array, a detail view expects an object)

**If validation fails:**
- Surface specific mismatches: `⚠ Wireframe <screen>.wireframe.md binds <Component> to GET /api/v1/items expecting array, but api-contracts.md shows data as object`
- Route back to `api_developer` for contract fix (max 1 retry)
- After fix: re-validate → then proceed to Build-step B3

**If validation passes:**
```
✅ API Contract Validation — PASS
   Endpoints documented: N/N
   Shape checks: all unambiguous
   Wireframe cross-refs: all matched
   → Proceeding to Build-step B3 (ui_developer)
```

---

## Step 3 — Tests

### Step 3a — Unit Tests
**Agent:** Generated `unit_test_agent`

Runs unit tests. On failure:
- Diagnoses root cause
- Fixes implementation (not the tests)
- Reruns
- **Max 3 attempts** → then surfaces unresolved failures with reproduction steps

### Test Attempt Tracking

When a test agent retries (attempt > 1), track ALL retry information for visibility:

1. Log: `"⚠ Test [test_name] required [N] attempts to pass"`
2. Add to manifest under test_results: `"flaky_tests": ["test_name (passed on attempt N)"]`
3. Add to gate report: `"⚠ FLAKY: [count] tests required multiple attempts"`
4. Carry forward: flaky tests appear in next phase's audit as known instability

```json
// In manifest.json test_results section:
"test_results": {
  "unit": {
    "status": "passed",
    "total": 24,
    "passed": 24,
    "failed": 0,
    "flaky_tests": [
      "TestCreateUser (passed on attempt 2)",
      "TestListResources (passed on attempt 3)"
    ],
    "report": "agent_state/phases/N/reports/unit_tests.md"
  }
}
```

**Why track flaky tests?** A test that needs 3 attempts to pass is a signal of non-deterministic behavior (race condition, timing dependency, test isolation failure). If the same test is flaky across 2+ phases, it becomes a reliability risk that compounds.

### Flaky Test Quarantine

When a test appears in `flaky_tests[]` across 2+ consecutive phases:

1. **Detect:** Check previous phase manifest's `flaky_tests[]`. If current phase has the same test name: it's chronically flaky.
2. **Quarantine:** Mark with `@flaky` tag/annotation (language-specific):
   - Go: `t.Skip("QUARANTINED: flaky across phases N-1, N")`
   - Python: `@pytest.mark.skip(reason="QUARANTINED: flaky")`
   - TypeScript: `test.skip('QUARANTINED: flaky')`
   - Java: `@Disabled("QUARANTINED: flaky")`
   - Rust: `#[ignore]`
3. **Log:** Add to manifest: `"quarantined_tests": ["TestName (flaky since phase N-1)"]`
4. **Track:** Quarantined tests appear in gate report as: `⚠ QUARANTINED: N tests skipped (flaky across 2+ phases)`
5. **Escalate:** If quarantined count > 5: surface to user as `⚠ Too many quarantined tests — investigate root cause`
6. **Unquarantine:** If a quarantined test passes 3 consecutive phases: auto-remove quarantine

This prevents flaky tests from blocking every phase while maintaining visibility.

### Step 3a.5 — Cross-Phase Regression (Smart, if PHASE > 1)

**Purpose:** Detect regressions in previous phases caused by current phase changes.
**Skip if:** PHASE = 1 (nothing to regress against)

**Algorithm — Artifact Overlap Detection:**

1. Read current phase manifest draft: extract `artifacts.api_routes`, `artifacts.schemas` (tables/collections), `artifacts.code` (modified files)

2. For each previous phase P (from 1 to PHASE-1):
   a. Read `agent_state/phases/P/manifest.json`
   b. Extract P's `artifacts.api_routes`, `artifacts.schemas`, `artifacts.code`
   c. Compute overlap:
      - **Schema overlap:** current phase touches a table/collection that phase P created or modified
      - **Route overlap:** current phase modifies an API route that phase P defined
      - **Code overlap:** current phase modifies a file that phase P created
   d. If ANY overlap detected → phase P is "affected"

3. For each affected phase:
   a. Re-run that phase's **unit tests** (from test paths in phase P's manifest)
   b. Re-run that phase's **integration tests** (critical: catches DB schema/query regressions)
   c. Re-run that phase's **E2E tests** (catches user-facing regressions across phases)

   **Why E2E regression is NOT optional:** E2E tests from Phase 1 verify user-facing workflows. If Phase 3 changes a shared API or DB schema, the E2E workflow may silently break even though unit + integration tests pass (because unit tests mock the changed dependency, integration tests test the new behavior, but E2E tests exercise the OLD workflow). This was proven in dlp_composer where cross-phase changes broke end-to-end flows that were never re-validated.

4. For non-affected phases: SKIP (log: "Phase P: no artifact overlap, skipping regression")

5. **Failure handling:**
   - If any previous phase test fails → BLOCKER
   - Surface: "Phase P regression: <test_name> FAILED — current phase changes broke Phase P"
   - Route to implementation agent for fix (max 2 attempts)
   - If unfixable: escalate to user with both phase contexts

6. **Output:** Append to manifest:
   ```json
   "cross_phase_regression": {
     "phases_checked": [1, 2],
     "phases_skipped": [3],
     "overlap_details": {
       "phase_1": {"schemas": ["users"], "routes": ["/api/v1/users"]},
       "phase_2": {"schemas": ["billing"], "routes": []}
     },
     "results": {
       "phase_1": {"unit": "passed", "integration": "passed"},
       "phase_2": {"unit": "passed", "integration": "passed"}
     }
   }
   ```

   Log detailed report: `agent_state/phases/${PHASE}/reports/regression_check.md`

This prevents silent breakage where Phase 3 code compiles and passes its own tests but breaks Phase 1 behavior. The artifact overlap detection avoids wasting time re-running tests for phases with zero overlap.

### Step 3b — Integration Tests
**Agent:** Generated `integration_test_agent`

Requires infra running (started in Step 0). Tests service↔DB and service↔cache interactions.

Same iteration rules: fix → retry → max 3 attempts.

### Step 3c — E2E Tests (MANDATORY every phase)

**CRITICAL CHANGE:** E2E tests are NOT conditional. Every phase ships as a fully baked app. E2E tests validate the app works from a user's perspective in a real browser.

**Agent:** `e2e_orchestrator` + generated `ui_test_agent` (if UI phase)

**Step 3c.1 — Ensure E2E Tests Exist:**
If no E2E test files exist for this phase:
1. `ui_test_agent` writes Playwright E2E tests covering ALL in-scope FR-* acceptance criteria
2. Tests must cover: functional flows, keyboard input, error recovery, accessibility (ARIA), display formatting
3. Every P0 FR-* must have at least one E2E test
4. Tests use `data-testid` attributes for reliable element selection
5. Playwright config must exist — create if missing (chromium, baseURL, webServer)

**Step 3c.2 — Run E2E Tests (Feedback Loop):**
```
Cycle 1: Run all E2E tests
  → All pass? → proceed to Step 3c.3
  → Failures? → diagnose root cause (test bug vs implementation bug)
    → Fix implementation (or test if test is wrong)
    → Re-run ONLY failed tests

Cycle 2: Re-run failed tests
  → All pass? → proceed to Step 3c.3
  → Failures? → deeper diagnosis
    → If same failures: likely architectural issue
    → Fix and re-run

Cycle 3: Final attempt
  → All pass? → proceed
  → Still failing? → ESCALATE to debate_moderator:
    debate_request: {
      topic: "E2E test failure after 3 fix attempts",
      context: "Test: <name>, Error: <error>, Attempts: 3",
      options: [
        "Architectural change to fix root cause",
        "Simplify the feature to make it testable",
        "Mark as known_issue with workaround",
        "The test expectation is wrong — adjust test"
      ]
    }
    → debate_moderator spawns researchers + advocates + arbitrator
    → Arbitrator verdict determines action
    → Implement verdict → re-run E2E → if still fails: BLOCK gate
```

**Step 3c.3 — Visual Validation (if wireframe.html exists):**
If `docs/design/phases/${PHASE}/specs/*.wireframe.html` exists:
1. Open wireframe HTML in Playwright → screenshot at 1280px and 375px
2. Open implementation at localhost → screenshot at same viewports
3. Compare screenshots (perceptual diff)
4. If mismatch > 10%: flag visual discrepancies for ui_developer to fix
5. Max 2 visual fix rounds → remaining discrepancies logged as `known_issues`

**All tiers (unit + integration + E2E + visual) must pass before reconciliation.**

### Step 3c.5 — Post-Implementation Re-Audit (CLOSED LOOP)

**Runs after:** All tests pass (Steps 3a-3c)
**Purpose:** Verify that gaps identified in the Step 1 audit were actually addressed by implementation

**Execution:**
1. Read the Step 1 audit report (`agent_state/phases/${PHASE}/audit_report.md`)
2. For each gap listed under "Missing Implementations" and "Broken/Incomplete Items":
   - Check if the gap is now resolved (code exists, tests pass)
   - If still missing: flag as `⚠ AUDIT GAP UNRESOLVED: <item>`
3. For each "Carried Forward Issue" from previous phase:
   - Check if addressed in this phase's implementation
   - If not addressed: flag as `⚠ CARRIED FORWARD STILL OPEN: <item>`

**Output:** `agent_state/phases/${PHASE}/reports/re_audit.md`

**Impact on gate:**
- Unresolved audit gaps are surfaced in the gate report as warnings (not blocking — tests are the real gate)
- Unresolved carried-forward items that are 2+ phases old become **BLOCKING** per the carried-forward policy

**Why this matters:** Without re-audit, the Step 1 audit report becomes "write-only" — gaps are detected but nobody verifies they were closed. This step closes that loop.

---

## Step 3d + 3e — Reconciliation (SEQUENTIAL — 3d before 3e)

Run reconciliation agents **sequentially** — `spec_test_reconciler` depends on `spec_impl_reconciler` output to distinguish "untested" from "unimplemented".

```
Step 3d (first):
  └─ spec_impl_reconciler  → specs ↔ implementation (4-level verification)
       ↓ writes: agent_state/reconciliation/phase-N/specs_vs_impl.md
       ↓ output includes list of MISSING implementations

Step 3e (after 3d completes):
  └─ spec_test_reconciler  → specs ↔ test coverage
       ↓ reads: specs_vs_impl.md to EXCLUDE unimplemented behaviors from "untested" count
       ↓ a behavior can't be untested if it's not implemented yet — that's a MISSING impl, not a test gap
```

**Why sequential:** If `spec_test_reconciler` runs in parallel with `spec_impl_reconciler`, it will flag "no test for behavior X" when behavior X isn't even implemented yet. This creates confusion about whether the gap is a test gap or an implementation gap. Running 3d first gives 3e the context to make accurate assessments.

### 3d: Specs ↔ Implementation (`spec_impl_reconciler`)

Validates both directions with 4-level verification (Existence → Substantiveness → Wiring → Data Flow):
- **Forward:** spec-defined behaviors missing from the implementation
- **Reverse:** unspecced implementation (behaviors added without spec justification)

Output: `agent_state/reconciliation/phase-N/specs_vs_impl.md`

Missing implementations = **BLOCKER** (fix before acceptance tests).
Unspecced implementations = **LOGGED** with count in gate report. Not auto-blocking, but:
- If unspecced count > 0: gate report surfaces them with: `⚠ N unspecced implementations found — review before next phase`
- Each unspecced item is classified: `technical_necessity` (e.g., error handler), `scope_creep` (feature not in spec), or `test_helper`
- `scope_creep` items surfaced to user with recommendation: add to BRD or remove
- Manifest `carried_forward[]` includes unresolved unspecced items for next phase audit

### 3e: Specs ↔ Tests (`spec_test_reconciler`)

Validates both directions:
- **Forward:** spec-defined edge cases and behaviors with no test coverage
- **Reverse:** tests that test behaviors not in any spec

**TC-* ID Inventory Reconciliation (runs FIRST within this step):**
If specs contain TC-* IDs (pattern `TC-[A-Z]+-\d+`):
1. Extract all TC-* IDs from `docs/design/phases/${PHASE}/specs/` (the spec inventory)
2. Extract all TC-* IDs from test files (the implementation inventory)
3. Compute: missing, orphaned, covered, coverage percentage
4. Per-category breakdown
5. Write `agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md`
6. **GATE DECISION:** missing HIGH or MEDIUM TC-* IDs = HARD BLOCK

```bash
# Quick TC-* inventory check (runs before behavior-level reconciliation)
SPEC_DIR="docs/design/phases/${PHASE}/specs"
SPEC_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "$SPEC_DIR" 2>/dev/null | sort -u)
SPEC_COUNT=$(echo "$SPEC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

if [ "$SPEC_COUNT" -gt 0 ]; then
  IMPL_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' tests/ src/ test/ 2>/dev/null \
    --include="*_test.*" --include="*.test.*" --include="*.spec.*" | sort -u)
  IMPL_COUNT=$(echo "$IMPL_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
  MISSING_COUNT=$(comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS") | grep -c 'TC-' 2>/dev/null || echo 0)
  COVERAGE_PCT=$(( IMPL_COUNT * 100 / SPEC_COUNT ))

  echo "TC-* Inventory: ${IMPL_COUNT}/${SPEC_COUNT} implemented (${COVERAGE_PCT}%)"
  if [ "$MISSING_COUNT" -gt 0 ]; then
    echo "  MISSING: $MISSING_COUNT TC-* IDs not implemented"
    comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS") | head -20
    echo "  Route to Wave 5 feedback loop for remediation"
  fi
fi
```

Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md` + `agent_state/reconciliation/phase-N/test_case_inventory.md`

HIGH-priority untested behaviors = blocker.
Missing HIGH/MEDIUM TC-* IDs = blocker.
MEDIUM/LOW behavior gaps = logged as known gaps.

---

## Step 3f — Code Optimization (MANDATORY)

**Runs after:** All tests pass (Step 3a-3c) AND reconciliation complete (Step 3d-3e)
**Runs before:** Code review (Step 4) — reviewers see clean, optimized code
**Mandatory:** Yes — runs every phase. Produces a report even if zero changes made.

### Why mandatory

Dead code and redundant patterns accumulate across phases. Each agent generates code independently — backend_developer, api_developer, and ui_developer don't coordinate on shared utilities or know what the other has deprecated. Without cleanup at every phase, technical debt compounds and review cycles get longer.

### Scope Lock (CRITICAL SAFETY RULE)

Optimization ONLY touches files that were created or modified in THIS phase. Never modify code from previous phases — it has already passed its own gate.

```bash
# Scope = only files changed since last phase gate
SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null || git diff --name-only HEAD~50..HEAD)
```

### Pre-optimization snapshot

Before any optimization starts, capture the current state:

```bash
# Tag the pre-optimization state for safe rollback
git tag "phase-${PHASE}-pre-optimize" HEAD
```

If ALL optimizations need to be reverted:
```bash
git reset --hard "phase-${PHASE}-pre-optimize"
```

### Execution — parallel backend + UI tracks

```
Step 3f (parallel):
  ├─ code_optimizer         → backend/API dead code removal + optimization
  │                           Scope: src/domain/, src/services/, src/repositories/, src/api/, src/errors/
  │
  └─ ui_code_optimizer      → UI dead code removal + optimization (if frontend.enabled = true)
                              Scope: src/ui/, src/components/, src/hooks/, src/pages/, src/styles/
```

**Agent:** `code_optimizer` — always runs
**Agent:** `ui_code_optimizer` — runs only if `frontend.enabled = true`

Both agents follow the same safety protocol:
1. **Pass 1 — Dead code removal** (safe — removing unused code can't change behavior)
2. **Pass 2 — Code optimization** (risky — changes code paths)
3. Each change committed individually for granular revert
4. Each change must include the files affected and what was changed

**Outputs:**
- `agent_state/phases/${PHASE}/reports/code_optimization.md` — backend/API optimization report
- `agent_state/phases/${PHASE}/reports/ui_code_optimization.md` — UI optimization report (if frontend)

---

## Step 3g — Post-Optimization Test Re-run (CONDITIONAL SAFETY GATE)

**Runs after:** Step 3f optimization completes
**Purpose:** Verify that NO optimization introduced a regression
**Skip if:** Both optimizers report zero changes (no dead code removed, no optimizations applied). Log: "Step 3g skipped — zero optimization changes."

If ANY optimization was applied:

### Execution

Re-run ALL test tiers that passed in Step 3a-3c:

```
Re-run 3g.1: Unit tests           → must still pass
Re-run 3g.2: Integration tests    → must still pass
Re-run 3g.3: E2E tests            → must still pass (if they ran in 3c)
```

### On failure

If ANY test fails after optimization:

1. **Identify which optimization caused the failure** — check git log since `phase-${PHASE}-pre-optimize` tag
2. **Diagnose and fix first** (don't blindly revert):
   - Read test failure output → identify root cause (missing import, broken caller, type mismatch)
   - Apply targeted fix → commit as `fix: resolve <issue> after <optimization>`
   - Re-run failing test → if passes, continue
3. **If fix doesn't work** — try broader fix (check all callers of changed code, fix all affected)
4. **If still failing after 2 fix attempts** — revert the specific optimization commit + fix attempts:
   ```bash
   git revert <commit-hash> --no-edit
   ```
5. **Max 3 revert cycles** — if tests still fail after 3 optimization reverts:
   - Reset to pre-optimization state: `git reset --hard phase-${PHASE}-pre-optimize`
   - Log in report: "⚠ All optimizations reverted — optimization introduced non-recoverable regression"
   - Pipeline continues (optimization failure is NOT a pipeline blocker, but IS logged in gate)
6. **Update the optimization report** with fixed and reverted items

### Output

Updates `agent_state/phases/${PHASE}/reports/code_optimization.md` with:
```markdown
## Post-Optimization Test Re-run
- Unit tests: PASS (X/X)
- Integration tests: PASS (X/X)
- E2E tests: PASS (X/X) | not run
- Reverted optimizations: N (or: none)
- Status: CLEAN | PARTIAL (N optimizations reverted) | REVERTED (all rolled back)
```

### Gate impact

The Phase Gate (Step 6) checks the post-optimization test status:
- `CLEAN` → no issues, all optimizations kept
- `PARTIAL` → some optimizations reverted, remaining tests pass → acceptable
- `REVERTED` → all rolled back, code is at pre-optimization state → acceptable (logged as known issue)
- Tests still failing → **BLOCKER** (should not happen if revert protocol followed)

---

## Step 4 — Code Review + Acceptance Tests (PARALLEL TRACKS)

Review and acceptance testing run as **two parallel tracks** — both read the same code, neither modifies it.

```
Step 4 (PARALLEL TRACKS):
  Track A: Code Review (three stages)
  Track B: Acceptance Tests (persona-based)
```

Both tracks must pass for the gate. Running them in parallel saves a full step.

### Track A: Code Review (Three-Stage Pipeline)

Review runs as three sequential stages. Each stage catches a different class of defect. Stages are NOT combined.

### Stage 4a — Spec Compliance Review (FIRST — catches "clean code, wrong spec")

**Purpose:** Independently verify the implementation matches the specs. This is NOT a code quality check — it's a "did you build the right thing" check.

**Approach:** Read each spec in `docs/design/phases/${PHASE}/specs/`, then verify the implementation delivers what the spec defines. Use explicit distrust:

> "The implementer's manifest reports success. Their report may be incomplete, inaccurate, or optimistic. Verify everything independently by reading the actual code — do NOT trust the manifest alone."

**Checks (per spec):**
- Every interface contract in the spec has a matching implementation (method signatures, route paths, request/response shapes)
- Every behavior described in the spec's flow section is implemented (not just stubbed)
- Every edge case in the spec has handling code (or a documented deviation)
- Every error type in the spec's error matrix has a corresponding error response
- API contracts match the wireframe API bindings (if UI phase)

**On mismatch (CLOSED LOOP):**
- Route back to implementation agent for fix (max 2 rounds)
- After fix: **re-run spec compliance check on the changed files** (not full review — targeted re-check)
- If mismatch persists after 2 rounds: log as `spec_deviation` with details → becomes gate blocker
- Log all deviations (fixed and unresolved) in report

**Output:** `agent_state/phases/${PHASE}/reports/specs_vs_impl.md` — the spec↔impl reconciliation
report. Stage 4a IS the spec-compliance dimension of that reconciliation; write findings here (as
MISSING / DEVIATION entries) rather than to a separate `spec_compliance_review.md`, so the gate reads
one canonical source. (Under `/develop-orchestrator` this is the `spec_impl_reconciler` agent's
report; the two are the same file.)

```markdown
# Spec Compliance Review — Phase N

## Summary
COMPLIANT | N deviations | N missing implementations

## Per-Spec Results
| Spec File | Contracts Verified | Behaviors Verified | Edge Cases | Result |
|-----------|-------------------|--------------------|------------|--------|

## Deviations
| Spec | Expected | Actual | Severity | Action |
|------|----------|--------|----------|--------|

## Missing Implementations
| Spec | What's Missing | Blocking |
|------|---------------|----------|
```

### Stage 4b — All remaining reviews (PARALLEL)

After spec compliance passes, run ALL remaining reviews in parallel to maximize speed:

```
Stage 4b (ALL PARALLEL):
  ├─ code_reviewer_I     → style + idioms (reads language skill pack)
  ├─ code_reviewer_II    → architecture compliance (reads IMPLEMENTATION_GUIDELINES)
  ├─ security_reviewer   → OWASP + adversarial property checks
  └─ dependency_scanner  → CVE + outdated packages
```

On issues found from any reviewer:
- Implementation agent addresses each comment
- Reviewer re-checks
- **Max 2 rounds** → unresolved issues go to `known_issues` in manifest

**Blocking rules:**
- `code_reviewer_I`: BLOCKING issues must fix
- `code_reviewer_II`: VIOLATION findings must fix
- `security_reviewer`: HIGH severity findings must fix
  **Dynamic security checks** (within security_reviewer):
  - Requires application running (from Step 2.75 smoke test)
  - Runs SQL injection, auth bypass, CORS, rate limiting probes
  - Findings appended to security_review.md under "Dynamic Security Findings"
  - BLOCKING/CRITICAL findings from dynamic checks have same gate impact as static findings
- `dependency_scanner`: CRITICAL/HIGH with available fixes must apply. Auto-applies non-breaking fixes (`npm audit fix` etc.). Breaking fixes flagged for user decision.

Reports written to `agent_state/phases/${PHASE}/reports/` (canonical names — same set the gate and
`/develop-orchestrator` require; spec-compliance findings are folded into the spec↔impl reconciliation
report, `specs_vs_impl.md`, rather than a separate `spec_compliance_review.md`):
- `code_review_I.md` (Stage 4b)
- `code_review_II.md` (Stage 4b)
- `security_review.md` (Stage 4b)
- `dependency_scan.md` (Stage 4b)
- `quality_gate.md` (code_quality_verifier)
- `specs_vs_impl.md` · `spec_test_coverage.md` (reconcilers)
- `sast_scan.md` (Stage 4c — CONDITIONAL: only when a SAST command is configured; else a recorded skip)

### Stage 4c — Static Application Security Testing (parallel with review)

Run SAST scan on all code changed in this phase:

```bash
# Language-specific SAST command comes from docs/IMPLEMENTATION_GUIDELINES.md — there is NO silent
# language default (a hardcoded Go govulncheck on a Python project is worse than skipping). Read the
# labelled command; if none is configured, SKIP explicitly (recorded, not silently passed).
# Reference examples (what a guideline might list):
#   Go: govulncheck ./...   Python: bandit -r src/ -f json   TS/JS: semgrep --config auto src/
#   Java: semgrep / spotbugs   Rust: cargo audit

# Same helper as the Step-6 regression gate — reads a backtick-quoted command from the guidelines,
# invents no default, returns empty when not found. (Redefined here because shell state does not
# persist across steps.)
read_cmd_from_guidelines() {
  local label="$1" file="docs/IMPLEMENTATION_GUIDELINES.md"
  [ -f "$file" ] || return 1
  grep -iE "$label" "$file" | grep -oE '`[^`]+`' | head -1 | tr -d '`'
}
SAST_CMD=$(read_cmd_from_guidelines 'sast|govulncheck|bandit|semgrep|cargo audit')
if [ -z "$SAST_CMD" ]; then
  echo "⚠ SAST SKIPPED — no SAST command found in docs/IMPLEMENTATION_GUIDELINES.md." \
    > agent_state/phases/${PHASE}/reports/sast_scan.md
  echo "  Add one under '## Common Tasks' (e.g. \`govulncheck ./...\`, \`semgrep --config auto src/\`)" \
    >> agent_state/phases/${PHASE}/reports/sast_scan.md
  echo "  to enable static security scanning. This is an explicit, recorded skip — not a pass." \
    >> agent_state/phases/${PHASE}/reports/sast_scan.md
else
  eval "$SAST_CMD" > agent_state/phases/${PHASE}/reports/sast_scan.md 2>&1
fi
```

`read_cmd_from_guidelines` is defined in the Step-6 regression block above; it invents no default and
returns empty when nothing matches.

Severity mapping:
- CRITICAL/HIGH → BLOCKING (must fix before gate)
- MEDIUM → WARNING (logged in known_issues)
- LOW → INFO (logged but not blocking)

If no SAST tool is configured in IMPLEMENTATION_GUIDELINES: the scan is SKIPPED with the explicit
warning written to sast_scan.md above (recorded, never a silent green).

---

### Track B: Acceptance Tests (runs in PARALLEL with Track A)

**Agent:** `acceptance_test_agent`

Validates implementation at use case and persona level against BRD FR-* requirements scoped to this phase. Runs in parallel with code review — both read the same code, neither modifies it.

### Data Seeding
1. Check `requirements/test-data/phase-${PHASE}.yaml` — use if present (user-provided data takes priority)
2. If absent: `acceptance_test_agent` generates realistic seed data from BRD personas + in-scope use cases
3. Seed data applied via API or direct DB (per IMPLEMENTATION_GUIDELINES)

### Execution
- Each in-scope FR-* with user-facing acceptance criteria is executed as its declared persona
- Every BRD persona must be exercised by ≥1 use case this phase (if in scope)
- Results: PASS / PARTIAL (N of M criteria met) / FAIL per use case

### Contract Shape Assertions (runs alongside persona tests)
For EVERY API endpoint called during acceptance testing, verify:
- Response matches `data-contracts.md` TypeScript interface (field names, types)
- List endpoints return `data: []` (array), not object
- Single endpoints return `data: {}` (object), not array
- Empty list returns `{ data: [], meta: { total: 0 } }`, not `null` or `{}`
- Log mismatches as `CONTRACT_VIOLATION` — these are the exact bugs that crash the UI

### Iteration (Feedback Loop with Escalation)

Acceptance testing is NOT read-only. Failures drive implementation fixes:

```
Cycle 1: Run all acceptance tests
  → All PASS? → proceed to gate
  → PARTIAL or FAIL? → categorize each failure:
    A) Implementation bug (feature doesn't work) → route to implementation agent
    B) Spec ambiguity (unclear what "correct" means) → route to spec_writer for clarification
    C) Test data issue (seed data wrong) → fix seed data
    D) Architectural limitation (can't be fixed without redesign) → ESCALATE

  → Fix category A/B/C → re-run ONLY failed acceptance tests

Cycle 2: Re-run failed tests
  → All PASS? → proceed
  → Still failing? → deeper analysis
    → If same test keeps failing: likely category D (architectural)
    → ESCALATE to debate_moderator:
      debate_request: {
        topic: "Acceptance test failure: <FR-*> <persona> <use case>",
        context: "BRD says X, implementation does Y, cannot reconcile after 2 attempts",
        options: [
          "Redesign the feature architecture to meet the AC",
          "Amend the BRD acceptance criteria (with justification)",
          "Defer to next phase with documented workaround",
          "The acceptance test interpretation is wrong"
        ]
      }
    → Arbitrator decides → implement → final re-test

Cycle 3: Final acceptance
  → PASS? → proceed to gate
  → FAIL? → BLOCK gate with detailed failure report
```

**Key principle:** Acceptance tests represent the BRD contract. If implementation can't meet the AC, the debate team decides whether to fix the code, amend the BRD, or defer — but it's never silently skipped.

### Outputs
- `agent_state/phases/${PHASE}/reports/acceptance_report.md` — full results
- `agent_state/phases/${PHASE}/test-data/generated-seed.yaml` — seed data used
- `agent_state/phases/${PHASE}/test-data/seed-cleanup.md` — how to reset

---

## Step 6 — Phase Gate

**⛔ SINGLE SOURCE OF TRUTH.** The canonical gate is `/develop-orchestrator` Wave 6, which itself
defers to the shared hook `.claude/hooks/verify-gate.sh` for the execution-guarantee check (roster
completeness + every completed agent's report exists and is non-stub + no unresolved `failed`). This
Step 6 is the equivalent check for anyone running `/develop` directly; **if the required-report set
here ever diverges from the orchestrator's, the orchestrator wins — reconcile back to it.** The two
now share ONE required set (below), with the same report paths (`reports/…`, not a separate
`agent_state/reconciliation/…` path).

**Always-required reports** (a missing/stub one BLOCKS the gate — same list as the orchestrator's
`REQUIRED_REPORTS` and the precondition check in the "Gate File Precondition Check" block above):

```
Gate Item                    Source File                                          Pass Condition
─────────────────────────────────────────────────────────────────────────────────────────────────
Unit tests                   agent_state/phases/${PHASE}/reports/unit_tests.md   No FAILED tests AND total > 0
Integration tests            agent_state/phases/${PHASE}/reports/integration_tests.md   No FAILED tests AND total > 0
E2E tests (MANDATORY)        agent_state/phases/${PHASE}/reports/e2e_results.md    No FAILED tests AND total > 0 (browser OR CLI/pipeline)
Reconciliation (spec↔impl)   agent_state/phases/${PHASE}/reports/specs_vs_impl.md   No BLOCKING findings (MISSING resolved, unspecced acknowledged)
Reconciliation (spec↔tests)  agent_state/phases/${PHASE}/reports/spec_test_coverage.md  No BLOCKING findings; no HIGH-priority untested behaviors
TC-* ID inventory (if specs) agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md  100% coverage for HIGH+MEDIUM TC-* IDs (skip if no TC-* IDs in specs)
Code review I                agent_state/phases/${PHASE}/reports/code_review_I.md   No BLOCKING issues
Code review II               agent_state/phases/${PHASE}/reports/code_review_II.md  No architecture violations
Security review              agent_state/phases/${PHASE}/reports/security_review.md  No HIGH severity findings
Dependency scan              agent_state/phases/${PHASE}/reports/dependency_scan.md  No CRITICAL/HIGH CVE without an applied fix
Code quality                 agent_state/phases/${PHASE}/reports/quality_gate.md    No BLOCKING (TODOs/stubs/secrets/dead code)
Acceptance tests             agent_state/phases/${PHASE}/reports/acceptance_report.md   All in-scope use cases: PASS
Cross-phase regression       manifest.json → cross_phase_regression                    All affected phases PASSED (skip if PHASE == 1)
```

**Conditional reports** — required ONLY when the phase has the relevant surface; otherwise the item is
recorded as `not_applicable` (an explicit, auditable skip — never a silent pass). The condition is
determined from the phase's own code/specs, not guessed:

```
Gate Item (CONDITIONAL)      Source File                                          Required WHEN … / else
─────────────────────────────────────────────────────────────────────────────────────────────────
Security SAST scan           agent_state/phases/${PHASE}/reports/sast_scan.md        WHEN phase has security-relevant code AND a SAST command is configured in IMPLEMENTATION_GUIDELINES → No CRITICAL/HIGH. Else: recorded skip (see Stage 4c).
Migration safety             agent_state/phases/${PHASE}/reports/migration_safety.md   WHEN phase adds/changes DB migrations → Zero CRITICAL findings, DOWN coverage ≥ 90%. Else: not_applicable.
Visual validation            agent_state/phases/${PHASE}/reports/visual_validation.md  WHEN *.wireframe.html files exist for this phase → Mismatch < 10%. Else: not_applicable.
Tenant isolation             agent_state/phases/${PHASE}/reports/tenant_isolation.md   WHEN project is multi-tenant (roster marks tenant_isolation_verifier required) → No cross-tenant leak. Else: not_applicable.
UI code optimization         agent_state/phases/${PHASE}/reports/ui_code_optimization.md  WHEN frontend.enabled → post-optimization tests PASS. Else: not_applicable.
Code optimization            agent_state/phases/${PHASE}/reports/code_optimization.md     Always → post-optimization tests PASS (CLEAN or PARTIAL accepted).
```

> **Spec compliance** is covered by the spec↔impl reconciliation report (`specs_vs_impl.md`) above —
> there is no separate `spec_compliance_review.md` gate item (that was a divergent report name that
> the orchestrator never required). If a phase produces a distinct spec-compliance report, fold its
> findings into `specs_vs_impl.md` so there is one reconciliation source.

**E2E gate is ALWAYS active.** Every phase must have E2E tests — generated during Step 3c.1 if they don't exist. The conditional gates above activate only when their surface is present; each inactive one must be logged `not_applicable`, never omitted silently.

### Gate Item Enforcement (EXECUTABLE — do not eyeball the table)

**⛔ The table above states pass conditions; this block ENFORCES them.** The per-phase gate was
historically honor-system — the parent read a report and judged "looks like it passed." A subagent
report claiming "42 passing, 0 failed" was accepted without re-derivation. Parse the numbers and
block on them (mirrors the counting used in `/accept` and `gate-verification.md` Layer 1):

```bash
GATE_BLOCKED=false
REPORTS_DIR="agent_state/phases/${PHASE}/reports"

# 1. Test tiers — parse totals; block on FAILED>0 or total==0.
python3 - "$REPORTS_DIR" << 'PY' || GATE_BLOCKED=true
import re, sys, os, glob
d = sys.argv[1]
tiers = {"unit_tests.md":"unit","integration_tests.md":"integration",
         "e2e_results.md":"e2e","acceptance_report.md":"acceptance"}
bad = False
for fn, name in tiers.items():
    p = os.path.join(d, fn)
    if not os.path.exists(p):
        print(f"⛔ {name}: report missing"); bad = True; continue
    txt = open(p, encoding="utf-8", errors="ignore").read().lower()
    failed = sum(int(m) for m in re.findall(r'failed[:\s]+(\d+)', txt))
    totals = [int(m) for m in re.findall(r'total[:\s]+(\d+)', txt)]
    total = max(totals) if totals else None
    if failed > 0:
        print(f"⛔ {name}: {failed} FAILED test(s) — gate blocked"); bad = True
    if total == 0:
        print(f"⛔ {name}: total=0 — tier was skipped"); bad = True
if not bad:
    print("✓ All test tiers: 0 failed, non-zero totals")
sys.exit(1 if bad else 0)
PY

# 2. TC-* coverage — HIGH+MEDIUM must be 100% (from spec_test_coverage.md / test_case_inventory).
COV=$(ls "$REPORTS_DIR/spec_test_coverage.md" agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md 2>/dev/null | head -1)
if [ -n "$COV" ] && grep -qiP 'coverage' "$COV"; then
  if grep -qiP '(HIGH|MEDIUM)[^\n]*(UNCOVERED|MISSING|0%|not covered)' "$COV"; then
    echo "⛔ GATE BLOCKED: HIGH/MEDIUM TC-* IDs are uncovered ($COV)"; GATE_BLOCKED=true
  fi
fi

# 3. Review dimensions — block on any BLOCKING / HIGH / CRITICAL that isn't marked resolved.
for R in code_review_I code_review_II security_review; do
  F="$REPORTS_DIR/${R}.md"
  [ -f "$F" ] || continue
  if grep -qiP '\b(BLOCKING|CRITICAL)\b' "$F" && ! grep -qiP '(BLOCKING|CRITICAL)[^\n]*(resolved|fixed|✓)' "$F"; then
    echo "⛔ GATE BLOCKED: ${R} has unresolved BLOCKING/CRITICAL findings"; GATE_BLOCKED=true
  fi
done

if [ "$GATE_BLOCKED" = true ]; then
  echo "⛔ Phase gate NOT passed — route the blockers above to the Wave 5 feedback loop."
  exit 1
fi
echo "✅ Gate item enforcement passed — proceeding to write gate.passed"
```

> **Canonical enforcement lives in `/develop-orchestrator`** (Wave 0b roster + Wave 6 Layers 0–3 +
> `gate-verification.md`). This block is the equivalent executable check for anyone running
> `/develop` directly. If the two ever diverge, the orchestrator wins — reconcile back to it.

### Bug Severity Classification

All items in `known_issues[]` and `carried_forward[]` MUST have a severity level:

| Severity | Definition | Gate Impact | Carry-Forward Limit |
|----------|-----------|-------------|-------------------|
| `critical` | Data loss, security breach, complete feature broken | BLOCKS gate — must fix | 0 phases (fix immediately) |
| `high` | Major feature broken, significant UX degradation | BLOCKS gate — must fix | 1 phase max |
| `medium` | Minor feature broken, workaround exists | Does not block gate | 3 phases max |
| `low` | Cosmetic, minor inconvenience | Does not block gate | No limit (tracked) |

When severity is not explicitly set, default to `medium`.

Carry-forward enforcement:
- `critical` items that appear in `carried_forward[]` → ⛔ IMMEDIATE BLOCK, cannot proceed
- `high` items carried for >1 phase → becomes `critical` (auto-escalation)
- `medium` items carried for >3 phases → becomes `high` (auto-escalation)

If any gate item fails:
1. Write `gate.failed` with structured failure data (enables next-phase detection of "ran but failed" vs "never ran"):
   ```bash
   cat > agent_state/phases/${PHASE}/gate.failed <<EOF
   {
     "phase": ${PHASE},
     "failed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
     "blockers": [
       // list of failing gate items with details
     ],
     "attempt": ${ATTEMPT:-1}
   }
   EOF
   ```
2. Surface to user with specific blocker text, file location, and the exact failing entry.
3. Do not proceed to Step 7.

**Gate state machine (ternary):**
- `gate.passed` exists → phase completed successfully
- `gate.failed` exists (no `gate.passed`) → phase ran but has unresolved blockers
- Neither exists → phase has not been attempted yet
- Both exist → `gate.passed` wins (gate.failed is from a previous attempt)

When the Gate Failure Recovery Procedure resolves all blockers:
1. Write `gate.passed`
2. Rename `gate.failed` → `gate.failed.resolved` (preserve history, don't delete)

### Gate Failure Recovery Procedure

When the gate fails, DO NOT delete any phase files. Follow this sequence:
1. **Identify the blocker** — read the specific report file and find the failing entry
2. **Fix the root cause** — re-run the failing agent (e.g., fix test → re-run unit_test_agent)
3. **Re-run only the failed check** — no need to re-run the entire pipeline
4. **Re-evaluate the gate** — re-read all report files and check conditions again
5. If gate now passes → write `gate.passed` and manifest

**DO NOT:**
- Delete `agent_state/phases/${PHASE}/` — it contains all the work done so far
- Re-run the entire `/develop` pipeline — only re-run the failing step
- Modify tests to force them to pass — fix the implementation instead

### --force-gate Override

**⛔ HARD PRECONDITION — a breaking change can NEVER be force-gated.** The prose in "Breaking Change
Detection" asserts "Hard blocks CANNOT be force-gated"; this is where that claim is ENFORCED, not just
stated. Before writing any forced-gate files, re-read `schema_evolution.md` and REFUSE the override if
any unresolved `⛔ BREAKING` remains:

```bash
SCHEMA_EVO="agent_state/phases/${PHASE}/reports/schema_evolution.md"
if [ -f "$SCHEMA_EVO" ]; then
  # An unresolved breaking change is a ⛔ BREAKING line NOT marked resolved/restored/versioned on the
  # same line. Count them; any >0 hard-blocks the force-gate.
  UNRESOLVED_BREAKING=$(grep '⛔ BREAKING' "$SCHEMA_EVO" 2>/dev/null \
    | grep -viE '(resolved|restored|versioned|deprecated alias|migration path)' | wc -l | tr -d ' ')
  if [ "${UNRESOLVED_BREAKING:-0}" -gt 0 ]; then
    echo "⛔ FORCE-GATE REFUSED: ${UNRESOLVED_BREAKING} unresolved BREAKING change(s) in $SCHEMA_EVO."
    echo "   Breaking changes cannot be force-gated (they silently break earlier phases' consumers)."
    echo "   Resolve each: restore the field, version the endpoint, or provide a deprecated-alias"
    echo "   migration path — then re-run. --force_gate does NOT override this."
    exit 1
  fi
fi
```

If `--force_gate` flag is set AND the gate has failures (and the breaking-change precondition above
passed):
1. Write `gate.passed` with a warning header:
   ```
   ⚠ FORCED GATE — ${N} blockers overridden by user at ${TIMESTAMP}
   Overridden items: [list of failed gate items]
   ```
2. Write `gate.forced` with structured failure data:
   ```json
   {
     "phase": N,
     "forced_at": "<ISO 8601>",
     "blockers": [
       { "gate_item": "unit_tests", "details": "TestAuthFlow FAILED — flaky", "severity": "gate_override" },
       { "gate_item": "security_review", "details": "HIGH: IDOR in GET /users/:id", "severity": "gate_override" }
     ],
     "user_rationale": "<user's reason for forcing>"
   }
   ```
3. Add overridden failures to manifest `known_issues[]` with `"severity": "gate_override"`
4. Print warning: `⚠ Gate forced with N unresolved blockers — review before release`

### Forced Gate Carry-Forward Enforcement (HARD RULE)

When the NEXT phase starts (Phase N+1 Step 0):
1. Check: `test -f agent_state/phases/$((PHASE-1))/gate.forced`
2. If exists: read `gate.forced` and surface ALL blockers prominently:
   ```
   ⛔ FORCED GATE DETECTED — Phase $((PHASE-1)) passed with N unresolved blockers:
     - [blocker 1 details]
     - [blocker 2 details]
   These MUST be resolved in Phase ${PHASE} or explicitly re-deferred with --force_gate.
   ```
3. Phase N+1 audit (Step 1) MUST list each forced blocker as a **CRITICAL carried-forward item**
4. Phase N+1 gate (Step 6) adds an extra gate check:
   ```
   Forced gate resolution    agent_state/phases/$((PHASE-1))/gate.forced    All blockers resolved OR explicitly re-deferred
   ```
5. If a blocker survives **2 consecutive forced gates**: it becomes **PERMANENTLY BLOCKING** — cannot be force-gated again. Must fix or remove from scope via BRD change request.

**Anti-pattern:** Forcing gates across 3+ phases creates a project where nothing actually works. The 2-force limit prevents this.

### Manifest Write Protocol (Atomic)

All manifest writes MUST use atomic write protocol to prevent corrupt JSON from crashing downstream phases:

1. Write to `agent_state/phases/${PHASE}/manifest.json.tmp`
2. Validate: `cat manifest.json.tmp | python3 -c "import json,sys; json.load(sys.stdin)" && echo "valid" || echo "CORRUPT"`
3. If valid: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not proceed. Log error and retry write.

```bash
# Atomic manifest write
python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/manifest.json.tmp && \
  mv agent_state/phases/${PHASE}/manifest.json.tmp agent_state/phases/${PHASE}/manifest.json || \
  { echo "⛔ CORRUPT manifest — aborting"; exit 1; }
```

This protocol also applies to any agent-level manifest writes in `agent_state/phases/${PHASE}/<agent>/manifest.json` — always write to `.tmp`, validate, then `mv`.

### Schema Validation

After JSON syntax validation, also validate against the manifest schema (`agent_state/manifest_schema.json`):

```bash
python3 -c "
import json, sys
manifest = json.load(sys.stdin)
required = ['phase', 'goal', 'started_at', 'brd_requirements_met', 'test_results', 'artifacts', 'known_issues', 'carried_forward']
missing = [f for f in required if f not in manifest]
if missing:
    print(f'⛔ MANIFEST MISSING FIELDS: {missing}')
    sys.exit(1)
print('✅ Manifest schema valid')
" < agent_state/phases/${PHASE}/manifest.json.tmp
```

### Phase Completion Tagging

After gate passes and manifest is written:
1. `git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"`
2. This tag serves as the rollback point for future phase resets

```bash
git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"
```

### Write gate files

```bash
mkdir -p agent_state/phases/${PHASE}
touch agent_state/phases/${PHASE}/gate.passed
```

Write `agent_state/phases/${PHASE}/manifest.json` — the handshake for the next phase:

```json
{
  "phase": N,
  "goal": "<from PHASE_PLAN.md>",
  "completed_at": "<ISO 8601 timestamp>",
  "brd_requirements_met": ["FR-001", "FR-002", "NFR-PERF-01"],
  "acceptance_tests": {
    "use_cases_total": 5,
    "use_cases_passed": 5,
    "personas_exercised": ["Admin User", "End User"],
    "seed_data": "agent_state/phases/N/test-data/generated-seed.yaml"
  },
  "artifacts": {
    "specs":      ["docs/design/phases/N/specs/auth-flow.md"],
    "code":       ["src/services/auth.go", "src/handlers/auth.go"],
    "migrations": ["migrations/001_add_users.sql"],
    "tests":      ["src/services/auth_test.go", "tests/integration/auth_test.go"],
    "api_routes": ["POST /api/v1/auth/login", "POST /api/v1/auth/logout"]
  },
  "test_results": {
    "unit": {
      "status": "passed",
      "total": 24,
      "passed": 24,
      "failed": 0,
      "report": "agent_state/phases/N/reports/unit_tests.md"
    },
    "integration": {
      "status": "passed",
      "total": 8,
      "passed": 8,
      "failed": 0,
      "report": "agent_state/phases/N/reports/integration_tests.md"
    },
    "e2e": {
      "status": "passed | not_run",
      "total": 3,
      "passed": 3,
      "failed": 0,
      "report": "agent_state/e2e/results.md"
    }
  },
  "optimization": {
    "backend": {
      "status": "CLEAN | PARTIAL | REVERTED",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "lines_reduced": 0,
      "report": "agent_state/phases/N/reports/code_optimization.md"
    },
    "ui": {
      "status": "CLEAN | PARTIAL | REVERTED | not_run",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "report": "agent_state/phases/N/reports/ui_code_optimization.md"
    },
    "post_optimization_tests": "PASS | PASS_WITH_REVERTS | not_run"
  },
  "test_case_inventory": {
    "spec_count": 0,
    "implemented_count": 0,
    "missing_count": 0,
    "orphaned_count": 0,
    "coverage_pct": 100,
    "by_category": {},
    "missing_ids": [],
    "deferred_ids": [],
    "report": "agent_state/reconciliation/phase-N/test_case_inventory.md"
  },
  "known_issues":    [],
  "carried_forward": [],
  "carried_forward_policy": "Items in carried_forward[] MUST be addressed within 1 phase. If an item survives 2 consecutive phases: it becomes a BLOCKING gate item in the 2nd phase — fix or explicitly remove from scope via BRD change request. Forced gate overrides count toward this limit — an item force-gated in Phase N and still unresolved in Phase N+1 is BLOCKING in Phase N+1."
}
```

---

## Step 6b — Documentation (runs in parallel with gate file writes)

**Agent:** `documentation_agent`

Generates or updates developer-facing documentation for all artifacts produced this phase:
- API endpoint docs (OpenAPI/Swagger update or equivalent)
- Updated `README.md` sections for new components
- Any doc annotations from code review comments

Output: `agent_state/phases/${PHASE}/reports/documentation_update.md` — summary of what was added/updated.

Does NOT block gate passage. Runs in parallel with gate file writes.

---

## Step 7 — Report

```
✅ Phase N complete

  Implemented:
    Backend: N services, N repositories, N API routes
    UI:      N screens (or: not a UI phase)
    DB:      N migrations applied

  Tests:
    Unit:        X/X passed
    Integration: X/X passed
    E2E:         X/X passed (or: not run this phase)

  Reconciliation:
    Spec ↔ Impl:   PASS (or: N missing, N unspecced flagged)
    Spec ↔ Tests:  PASS (or: N untested HIGH behaviors)

  Optimization:
    Dead code removed: N items (-X lines)
    Optimizations applied: N (code reduction: X, performance: Y, structural: Z)
    Flagged for review: N items

  Acceptance:
    Use cases:   X/X passed  (FR-001, FR-002, FR-003)
    Personas:    [Admin User, End User]
    Seed data:   agent_state/phases/N/test-data/generated-seed.yaml

  Reviews:
    Code style:    PASS (or: N known issues logged)
    Architecture:  PASS
    Security:      PASS

  Gate: agent_state/phases/N/gate.passed ✅
  Manifest: agent_state/phases/N/manifest.json ✅

  ▶ Next: /plan --phase=N+1
  ▶ After all phases: /accept (global acceptance across full product)
```

### Execution Summary

Read `agent_state/phases/${PHASE}/execution.jsonl` and render:

```
Phase ${PHASE} Execution (total: Xm Ys)
  <agent_name>        Xm Ys  ✅|⚠|❌  <findings summary>
  ...

Slowest agent: <name> (Xm Ys)
Total agents: N run, N failed, N retried
```

Write the pipeline_complete entry to the execution log:
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_complete\",\"phase\":${PHASE},\"status\":\"<gate_passed|gate_failed|gate_forced>\",\"total_duration_s\":<N>,\"agents_run\":<N>,\"agents_failed\":<N>}" >> agent_state/phases/${PHASE}/execution.jsonl
```

---

## Step 7b — Phase Post-Mortem (ALWAYS runs, even on forced gates)

**Purpose:** Analyze patterns from this phase's development to improve future phases.

**Gate impact:** NONE — post-mortem is informational only, never blocks.

**Analysis:**

### 1. Failure Pattern Analysis

Read all reports in `agent_state/phases/${PHASE}/reports/`:
- Count total BLOCKING/CRITICAL/HIGH findings across all reviewers
- Group findings by category: security, architecture, style, testing, contract
- Identify repeat patterns: "Did the same type of issue appear in multiple components?"
- Example: "3 of 5 handlers missing tenantID in WHERE clause -> systemic pattern, not one-off"

### 2. Retry Analysis

Read `agent_state/phases/${PHASE}/execution.jsonl`:
- Count agents that required retries
- Identify which steps had the most failures
- Calculate: `retry_rate = agents_retried / agents_run`
- If retry_rate > 30%: flag `"⚠ High retry rate — consider improving specs or skill packs"`

```bash
# Calculate retry rate from execution log
AGENTS_RUN=$(grep '"status":"completed"' agent_state/phases/${PHASE}/execution.jsonl | wc -l)
AGENTS_RETRIED=$(grep '"status":"failed"' agent_state/phases/${PHASE}/execution.jsonl | jq -r '.agent' 2>/dev/null | sort -u | wc -l)
if [ "$AGENTS_RUN" -gt 0 ]; then
  RETRY_RATE=$(( AGENTS_RETRIED * 100 / AGENTS_RUN ))
  echo "Retry rate: ${RETRY_RATE}% (${AGENTS_RETRIED} of ${AGENTS_RUN} agents retried)"
  if [ "$RETRY_RATE" -gt 30 ]; then
    echo "⚠ High retry rate — consider improving specs or skill packs"
  fi
fi
```

### 3. Time Distribution

From `execution.jsonl`, calculate:
- % time in implementation vs testing vs review
- Ideal: ~40% implementation, ~30% testing, ~20% review, ~10% other
- Flag deviations: if review > 40%, suggest "specs may be underspecified"
- Flag: if testing > 50%, suggest "implementation quality may need improvement"

```bash
# Parse execution.jsonl for time distribution
python3 -c "
import json, sys

steps = {'implement': 0, 'test': 0, 'review': 0, 'other': 0}
step_map = {
    'audit': 'other', 'orient': 'other', 'gate': 'other', 'documentation': 'other',
    'implement': 'implement', 'database': 'implement', 'migration': 'implement',
    'backend_developer': 'implement', 'api_developer': 'implement', 'ui_developer': 'implement',
    'unit_test': 'test', 'integration_test': 'test', 'e2e': 'test', 'acceptance': 'test',
    'reconcil': 'test', 'optimiz': 'test',
    'review': 'review', 'security': 'review', 'tenant': 'review', 'quality': 'review'
}

for line in open('agent_state/phases/${PHASE}/execution.jsonl'):
    try:
        entry = json.loads(line.strip())
        if 'duration_s' in entry:
            agent = entry.get('agent', entry.get('step', 'other')).lower()
            category = 'other'
            for key, cat in step_map.items():
                if key in agent:
                    category = cat
                    break
            steps[category] += entry['duration_s']
    except: pass

total = sum(steps.values()) or 1
for cat, secs in steps.items():
    pct = int(secs * 100 / total)
    print(f'  {cat}: {pct}% ({secs:.0f}s)')

if steps['review'] * 100 / total > 40:
    print('⚠ Review time > 40% — specs may be underspecified')
if steps['test'] * 100 / total > 50:
    print('⚠ Test time > 50% — implementation quality may need improvement')
" 2>/dev/null || echo "  (time distribution unavailable — execution.jsonl missing or malformed)"
```

### 4. Carried-Forward Trend

Compare current phase's `known_issues[]` + `carried_forward[]` against previous phase:
- Are issues accumulating or being resolved?
- Severity trend: are issues getting more or less severe?
- If carried_forward count is increasing phase-over-phase: flag `"⚠ Technical debt accumulating"`

```bash
# Carried-forward trend analysis
python3 -c "
import json, os

trend = []
phase = ${PHASE}
for p in range(1, phase + 1):
    manifest_path = f'agent_state/phases/{p}/manifest.json'
    if os.path.exists(manifest_path):
        m = json.load(open(manifest_path))
        cf = len(m.get('carried_forward', []))
        ki = len(m.get('known_issues', []))
        trend.append({'phase': p, 'carried_forward': cf, 'known_issues': ki, 'total': cf + ki})
        print(f'  Phase {p}: {cf + ki} issues ({cf} carried forward, {ki} known issues)')

if len(trend) >= 2:
    prev = trend[-2]['total']
    curr = trend[-1]['total']
    if curr > prev:
        print('  Trend: DEGRADING ⚠ Technical debt accumulating')
    elif curr < prev:
        print('  Trend: IMPROVING')
    else:
        print('  Trend: STABLE')
elif len(trend) == 1:
    print(f'  Trend: BASELINE (first phase tracked)')
" 2>/dev/null || echo "  (trend analysis unavailable)"
```

### 5. Gate Health

- Did the gate pass on first attempt?
- How many gate items required fixes?
- Was the gate forced? If so, what was forced and why?

```bash
# Gate health analysis
GATE_FORCED=$(ls agent_state/phases/${PHASE}/gate.forced 2>/dev/null)
GATE_FAILED=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null | wc -l | tr -d ' ')
if [ -n "$GATE_FORCED" ]; then
  echo "  Gate: FORCED — review agent_state/phases/${PHASE}/gate.forced for details"
elif [ "$GATE_FAILED" -gt 0 ]; then
  echo "  Gate: PASSED on attempt $((GATE_FAILED + 1)) (${GATE_FAILED} previous failure(s))"
else
  echo "  Gate: PASSED on first attempt"
fi
```

### Output

Write the post-mortem report to `agent_state/phases/${PHASE}/reports/postmortem.md`:

```markdown
## Phase ${PHASE} Post-Mortem

### Summary
- Gate: PASSED (attempt ${N}) | FORCED (${N} blockers overridden)
- Total findings: ${N} blocking, ${N} warning, ${N} info
- Retry rate: ${N}% (${N} of ${N} agents retried)
- Time distribution: impl ${N}% | test ${N}% | review ${N}% | other ${N}%

### Systemic Patterns
${patterns found, or "None detected"}

### Recommendations for Next Phase
- ${actionable recommendations based on patterns}

### Carried-Forward Trend
Phase 1: 0 issues -> Phase 2: 2 issues -> Phase 3 (current): 1 issue
Trend: STABLE | IMPROVING | DEGRADING

### Gate Items That Required Fixes
| Gate Item | Fix Rounds | Root Cause |
|-----------|-----------|------------|
| ${item} | ${N} | ${cause} |
```

### Manifest Addition

Add post-mortem data to the phase manifest:

```json
"postmortem": {
  "retry_rate_pct": N,
  "systemic_patterns": N,
  "carried_forward_trend": "stable|improving|degrading",
  "recommendations": ["..."]
}
```

### Execution Log Entry

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"postmortem_complete\",\"phase\":${PHASE},\"retry_rate_pct\":${RETRY_RATE:-0},\"systemic_patterns\":${PATTERN_COUNT:-0},\"carried_forward_trend\":\"${CF_TREND:-baseline}\"}" >> agent_state/phases/${PHASE}/execution.jsonl
```
