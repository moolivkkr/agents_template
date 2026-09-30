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
  - name: candidates
    required: false
    default: 1
    description: "Test-time compute scaling: generate N (2–3) independent candidate implementations in isolated worktrees, then select the winner by model-test voting + solution_selector. EXPENSIVE (~N× Wave-2 cost) — opt-in for hard phases. Also auto-triggers for PLATFORM class / high complexity / prev-phase failure. See ~/.claude/skills/core/candidate-selection.md."
---

# /develop — Autonomous Phase Implementation

> **Auto mode.** `--auto` is set, OR `agent_state/autonomous/run.json` has `"status":"running"` (this
> command was invoked by `/autonomous`). In auto mode, never wait for the user: every "surface to
> user" / "escalate to user" / STOP-for-input point below instead auto-resolves with the recommended
> option, is logged to `agent_state/autonomous/auto-resolved.jsonl` (full question, options, choice,
> rationale, category; `"category":"security","security_flag":true` for security topics), and is
> carried forward to the next human checkpoint. The exception is a security decision with no
> hardened default, which sets `run.json` `status` to `awaiting_human`. The closing "▶ Next: …" line
> is for standalone use only; under `/autonomous`, return control to it without ending the turn.

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

> Full protocol: `~/.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

`/develop` is a long-running pipeline. Follow these rules to stay within the conversation context window:

**Agent result discipline — return summaries, not content:**
Every agent ends with the short final message its operating contract defines (status, files written, gate counts, blockers), or with the command-specific return format where a command defines one. The full output is in the file; the parent conversation receives only that summary.
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

**Run this pipeline through `/develop-orchestrator`, not by delegating this whole file to one agent.** The orchestrator launches a separate agent per wave and verifies each wave's outputs before the next; a single agent running the whole pipeline drops the review and acceptance steps.

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
           acceptance_report}.md + reconciliation/phase-N/{specs_vs_impl,specs_vs_tests}.md all exist
           (+ accessibility_audit / mobile_platform_audit / migration_safety / breaking_change_review
           for each conditional reviewer in roster.json)
   ⛔ DO NOT PROCEED WITHOUT THESE FILES — a missing one means an agent was dropped

5. PARENT reads all Wave 3+4 reports → builds collective feedback → Wave 5: ITERATE
   Verify: agent_state/phases/${PHASE}/reports/collective_feedback.md exists
   If fixes needed: spawn fix agents → re-run failed checks

6. PARENT evaluates gate → Wave 6: GATE
   Verify: ALL report files exist before writing gate.passed
```

### Gate File Precondition Check (HARD GATE)

**`.claude/hooks/verify-gate.sh` is the single source of truth for the gate contract** (shared with
`/develop-orchestrator` Wave 6 — do NOT maintain a parallel gate here; that drift is exactly how
reviews got dropped). It deterministically enforces: (a) roster completeness, (a2) the mandatory
review FLOOR, (b) report integrity — existence + non-stub + JSON-sidecar/BLOCKING checks, (c) no
dangling failures, (d) gate.passed honesty, and (e) execution-grounded test/lint/typecheck when a
`verify-commands.json` config exists. Call it and honor its exit code — it OWNS report validation, so
this file no longer re-lists reports (that duplication is removed):

```bash
if [ -f ".claude/hooks/verify-gate.sh" ]; then
  bash .claude/hooks/verify-gate.sh "${PHASE}" || {
    echo "⛔ GATE BLOCKED by verify-gate.sh — fix every item it names, then re-run. Do NOT write gate.passed."
    exit 1
  }
else
  echo "⛔ verify-gate.sh missing — the deterministic gate cannot run. Restore .claude/hooks/verify-gate.sh."
  exit 1
fi

# ⛔ FULL REGRESSION TEST (not just current phase) — additive to the hook.
# If a verify-commands.json config exists, the hook's check (e) ALREADY ran the suite above, so skip
# this block (no double-run). Otherwise fall back to the test commands in IMPLEMENTATION_GUIDELINES.
if [ -f sdlc-verify.json ] || [ -f "agent_state/phases/${PHASE}/verify-commands.json" ] || [ -f agent_state/config/verify-commands.json ]; then
  echo "✓ Full regression already executed by verify-gate.sh check (e) from verify-commands.json."
else
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
  local label="${1}" file="docs/IMPLEMENTATION_GUIDELINES.md"
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
fi

# NOTE: report EXISTENCE, STUB detection, and unresolved-BLOCKING checks are intentionally NOT
# duplicated here — verify-gate.sh check (b) owns them (existence + non-stub + JSON-sidecar/BLOCKING,
# for the reviewers, reconcilers, and acceptance reports named in roster.required). One place, no drift.
```

**verify-gate.sh must exit 0 before `gate.passed` is written.** It proves every required agent ran
(roster completeness + review FLOOR), every report is real (existence + non-stub + no unresolved
BLOCKING), and — when configured — the tests actually pass (execution-grounded). This prevents the
exact failure mode we observed: implementation + tests pass, gate written, but no reviews or
acceptance tests ever ran.

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
- **Candidate-selection (conditional):** for hard phases (PLATFORM class / high complexity /
  prev-phase failure / `--candidates=N`), Wave 2 instead generates N (2–3) independent candidate
  implementations in isolated git worktrees, each with its own tests, and `solution_selector` picks
  the winner via model-test voting + rubric. The winner merges back and Wave 3 runs on it as usual.
  Gated because it costs ≈N× Wave-2 tokens — see `~/.claude/skills/core/candidate-selection.md` and
  `/develop-orchestrator` Wave 2B for the mechanism.

**Wave 3: TEST** (parallel)
- unit_test_agent → write + run unit tests
- integration_test_agent → write + run integration tests
- ui_test_agent → write + run Playwright E2E tests (MANDATORY)
- Output: test reports in `agent_state/phases/${PHASE}/reports/`

**Wave 4: REVIEW + ACCEPTANCE** (parallel tracks — never skipped)
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
| "The gate has only one minor blocker, I'll pass it" | A blocker is a blocker. Fix it or use `--force_gate` with explicit user approval. Under `/autonomous`, that approval is `agent_state/autonomous/approved.json` `"force_gate_policy":"approved"` (given at its human checkpoint), and it applies only after 3 fix cycles, with every remaining blocker written to `gate.forced`. |
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

## Pipeline steps (read each file when you reach that step)

The detailed procedure for each step lives in its own file so a session - or a wave agent - loads only the step it is executing. Read a step's file in full when you reach it; don't pre-load the others. Wave agents launched by `/develop-orchestrator` should be given the path of their step's file.

| Step | File |
|---|---|
| Step 0 — Orient | `~/.claude/skills/core/develop-steps/step-0-orient.md` |
| Step 0.5 — Implementation Readiness Gate (HARD GATE) | `~/.claude/skills/core/develop-steps/step-0-5-implementation-readiness-gate.md` |
| Step 1 — Audit | `~/.claude/skills/core/develop-steps/step-1-audit.md` |
| Step 2 — Implementation (Build-step Parallel Execution) | `~/.claude/skills/core/develop-steps/step-2-implementation.md` |
| Step 2.5 — API Contract Validation (UI phases only) | `~/.claude/skills/core/develop-steps/step-2-5-api-contract-validation.md` |
| Step 3 — Tests | `~/.claude/skills/core/develop-steps/step-3-tests.md` |
| Step 3d + 3e — Reconciliation (SEQUENTIAL — 3d before 3e) | `~/.claude/skills/core/develop-steps/step-3d-3e-reconciliation.md` |
| Step 3f — Code Optimization (MANDATORY) | `~/.claude/skills/core/develop-steps/step-3f-code-optimization.md` |
| Step 3g — Post-Optimization Test Re-run (CONDITIONAL SAFETY GATE) | `~/.claude/skills/core/develop-steps/step-3g-post-optimization-test-re-run.md` |
| Step 4 — Code Review + Acceptance Tests (PARALLEL TRACKS) | `~/.claude/skills/core/develop-steps/step-4-code-review-acceptance-tests.md` |
| Step 6 — Phase Gate | `~/.claude/skills/core/develop-steps/step-6-phase-gate.md` |
| Step 6b — Documentation (runs in parallel with gate file writes) | `~/.claude/skills/core/develop-steps/step-6b-documentation.md` |
| Step 7 — Report | `~/.claude/skills/core/develop-steps/step-7-report.md` |
| Step 7b — Phase Post-Mortem (ALWAYS runs, even on forced gates) | `~/.claude/skills/core/develop-steps/step-7b-phase-post-mortem.md` |
