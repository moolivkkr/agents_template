---
command: develop-orchestrator
description: "Wave-by-wave orchestration for /develop. The PARENT session follows this script, spawning separate agents per wave. This prevents the single-agent problem where reviews get dropped."
arguments:
  - name: phase
    required: false
    description: "Phase number. Omit to auto-detect."
---

# /develop Orchestrator — Wave-by-Wave Execution

**⛔ THIS command is executed by the PARENT session directly — NOT delegated to a subagent.**

The parent reads this script and executes each wave as a separate Agent tool call, verifying outputs between waves. This is the structural enforcement that prevents review/acceptance steps from being dropped.

---

## Auto-Checkpoint Protocol (inspired by agentmemory hook patterns)

Between EVERY wave boundary, the parent session automatically captures a lightweight checkpoint. This eliminates the need for explicit `/pause` — if context resets mid-pipeline, `/resume` can reconstruct state from the last checkpoint.

**Checkpoint format:** `agent_state/phases/${PHASE}/checkpoints/wave-${N}.json`

```json
{
  "ts": "<ISO timestamp>",
  "phase": N,
  "wave_completed": N,
  "wave_next": N+1,
  "git_sha": "<short SHA>",
  "artifacts_produced": ["<paths written this wave>"],
  "findings_summary": "<1-2 lines from wave output>",
  "tests_passing": true|false|null,
  "blocking_issues": []
}
```

**Write checkpoint AFTER each wave verification passes:**
```bash
mkdir -p "agent_state/phases/${PHASE}/checkpoints"
cat > "agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json" << EOF
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "phase": ${PHASE},
  "wave_completed": ${WAVE_NUM},
  "wave_next": $((WAVE_NUM + 1)),
  "git_sha": "$(git rev-parse --short HEAD)",
  "artifacts_produced": [<list files created this wave>],
  "findings_summary": "<extract from agent result>",
  "tests_passing": null,
  "blocking_issues": []
}
EOF
```

**On `/resume` detection:** If `checkpoints/wave-N.json` exists but `wave-$((N+1)).json` does not, resume from Wave N+1 without re-running earlier waves.

**Key difference from agentmemory:** These are deterministic structural checkpoints (known paths, known schema), not semantic observations. No retrieval search needed — the resume logic reads the latest checkpoint file directly.

---

## Context Pressure Check — MANDATORY Between Every Wave

**⛔ After writing each wave checkpoint, BEFORE starting the next wave, check context usage.**

Performance degrades sharply at ~80% context utilization. The 75% threshold gives a 5% safety margin.

### Protocol

**At every wave boundary (after checkpoint, before next wave):**

1. **Check context usage** — if at or above 75% of context window capacity:

2. **Write compact context summary:**
   ```bash
   cat > "agent_state/phases/${PHASE}/checkpoints/compact-context.md" << EOF
   # Compact Context — Phase ${PHASE} (post-Wave ${WAVE_NUM})
   Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
   Reason: context window at 75% — auto-compacted before Wave $((WAVE_NUM + 1))

   ## Phase Goal
   <1 line from phase_context.md>

   ## Completed Waves
   <for each completed wave: summary + artifacts from checkpoint JSON>

   ## Key Decisions Made This Session
   <any architectural decisions, deviations, or patterns noted>

   ## Current State
   - Last git SHA: $(git rev-parse --short HEAD)
   - Tests passing: <yes/no/not-yet-run>
   - Blocking issues: <none or list>

   ## Next Steps
   - Wave $((WAVE_NUM + 1)): <what needs to happen>
   - Remaining waves: <list>
   EOF
   ```

3. **Add compaction marker to checkpoint:**
   Update the latest `wave-${WAVE_NUM}.json` to include `"compacted_before_next": true`.

4. **Run `/compact`** — invoke Claude Code's built-in context compression.

5. **After compaction — reload and continue:**
   - Read `agent_state/phases/${PHASE}/checkpoints/compact-context.md`
   - Read `docs/design/phases/${PHASE}/phase_context.md`
   - Continue to Wave $((WAVE_NUM + 1)) — do NOT restart earlier waves.

### Key rules
- **Never compact mid-wave** — only at wave boundaries after the checkpoint is written
- **Never skip this check** — the 5% gap before 80% is your safety margin
- **Compact inline, don't break the session** — compaction is a mid-session refresh, not a reason to stop and `/resume`
- **If compaction happens, say so:** `"⚡ Context at 75% — compacting before Wave N. Resuming inline."`

---

## Wave 1: ORIENT + AUDIT

Spawn a single agent:

```
Agent prompt: "You are running Wave 1 (Orient + Audit) for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}
Read: docs/design/phases/${PHASE}/phase_context.md, IMPLEMENTATION_GUIDELINES.md
Produce: agent_state/phases/${PHASE}/audit_report.md
Identify gaps, existing code, what needs to be built."
```

**Verify before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/audit_report.md || echo "⛔ BLOCKED: audit_report.md missing"
```

**Auto-checkpoint:** Write `checkpoints/wave-1.json` with `artifacts_produced: ["audit_report.md"]`.

---

## Wave 2: IMPLEMENT

Spawn implementation agent(s):

```
Agent prompt: "You are running Wave 2 (Implementation) for Phase ${PHASE}.
Read: phase specs in docs/design/phases/${PHASE}/specs/
Read: IMPLEMENTATION_GUIDELINES.md for coding conventions
HARDENING RULES: interfaces not concrete types, repository pattern, wired metrics,
literal Unicode, table-driven Go tests, document spec deviations.
Implement all components. Commit after each logical unit."
```

**Verify before proceeding:**
```bash
# New source files exist
git diff --name-only HEAD~1 | grep -E '\.(ts|tsx|go)$' | head -5
```

**Auto-checkpoint:** Write `checkpoints/wave-2.json` with `artifacts_produced: [<new source files>]`.

---

## Wave 3: TEST

Spawn test agent(s):

```
Agent prompt: "You are running Wave 3 (Testing) for Phase ${PHASE}.
Write and run: unit tests, integration tests, Playwright E2E tests.
E2E tests are MANDATORY — generate if they don't exist.
Coverage target: 80% per package.
Run: vitest, playwright test, go test ./...
Produce: agent_state/phases/${PHASE}/reports/unit_tests.md
         agent_state/phases/${PHASE}/reports/e2e_results.md"
```

**Verify before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/reports/unit_tests.md || echo "⛔ BLOCKED"
test -f agent_state/phases/${PHASE}/reports/e2e_results.md || echo "⛔ BLOCKED"
```

**Auto-checkpoint:** Write `checkpoints/wave-3.json` with `tests_passing: true|false`, `artifacts_produced: ["reports/unit_tests.md", "reports/e2e_results.md"]`.

### Test Failure Recovery Guardrails

When tests fail and the test agent or a subsequent fix agent attempts auto-remediation, these guardrails are **absolute constraints** — they cannot be overridden by any agent:

**NEVER do these to make tests pass:**
- Delete, `.skip`, or comment out an existing test assertion or test function
- Reduce test coverage threshold to pass a gate
- Downgrade a dependency version to fix a build (may reintroduce CVEs)
- Modify test expectations to match buggy behavior instead of fixing the bug
- Remove a test file to reduce failure count
- Add `// @ts-ignore`, `//nolint`, or equivalent to suppress test-adjacent type errors

**Confidence-based escalation:**
- If root cause is clear (missing import, typo, wrong return type, obvious logic error) → auto-fix
- If root cause is unclear after reading the full failure output → escalate to user: "Test failure in [component] — root cause unclear. Options: [A] [B] [C]"
- Maximum 3 auto-fix attempts per failing test → then escalate (do NOT loop indefinitely)

**CI log sanitization (before feeding test output to any agent):**
Strip these patterns from test/build output before including in any agent prompt:
- Environment variables (`KEY=value`, `export VAR=`)
- Connection strings (`postgres://`, `redis://`, `mongodb://`, `mysql://`)
- Token-like strings (`sk-*`, `ghp_*`, `gho_*`, `Bearer *`, `token=*`)
- File paths containing `/secrets/`, `/.env`, `/credentials`, `/private/`
- Stack traces that include home directory paths (`/Users/`, `/home/`)

---

## Wave 4: REVIEW + ACCEPTANCE (parallel)

Spawn TWO agents in parallel:

**Agent A — Code Quality Review:**
```
Agent prompt: "You are running Wave 4 Track A (Code Quality Review) for Phase ${PHASE}.
Review ALL source code against IMPLEMENTATION_GUIDELINES.
Check: style, architecture, security, quality gates, spec reconciliation.
Produce: agent_state/phases/${PHASE}/reports/code_quality_review.md"
```

**Agent B — Acceptance Tests:**
```
Agent prompt: "You are running Wave 4 Track B (Acceptance Tests) for Phase ${PHASE}.
Test against LIVE running app. Validate every FR-* acceptance criterion.
Test per persona. Verify OTEL traces, API contracts, accessibility.
Produce: agent_state/phases/${PHASE}/reports/acceptance_report.md"
```

**Verify BOTH before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/reports/code_quality_review.md || echo "⛔ BLOCKED: review missing"
test -f agent_state/phases/${PHASE}/reports/acceptance_report.md || echo "⛔ BLOCKED: acceptance missing"
```

**⛔ DO NOT PROCEED TO WAVE 5 WITHOUT BOTH FILES.**

---

## Wave 5: COLLECTIVE FEEDBACK + ITERATE

The PARENT session (not an agent) reads all Wave 3+4 reports and builds the feedback document:

1. Read `unit_tests.md` — any failures?
2. Read `e2e_results.md` — any failures?
3. Read `code_quality_review.md` — any HIGH/CRITICAL findings?
4. Read `acceptance_report.md` — any FAIL/PARTIAL?

Build: `agent_state/phases/${PHASE}/reports/collective_feedback.md`

If fixes needed, spawn fix agent:
```
Agent prompt: "Fix these items from collective feedback: [list items].
After fixing, re-run: vitest, playwright test, go test.
Verify all tests pass."
```

Max 3 iterations. If architectural issue → invoke debate_moderator.

**Verify:**
```bash
test -f agent_state/phases/${PHASE}/reports/collective_feedback.md || echo "⛔ BLOCKED"
```

---

## Wave 6: GATE

The PARENT session runs the gate check:

1. Verify ALL required files exist:
   - audit_report.md ✓
   - unit_tests.md ✓
   - e2e_results.md ✓
   - code_quality_review.md ✓
   - acceptance_report.md ✓
   - collective_feedback.md ✓

2. Run FULL regression test suite (all phases, not just current):
   ```bash
   cd frontend && npx vitest run && npx playwright test
   cd backend && go test ./...
   ```

3. If all pass → write gate.passed + manifest.json + git tag

4. If any fail → DO NOT write gate.passed. Route failures back to Wave 5.

**Auto-checkpoint:** Write `checkpoints/wave-6.json` with `tests_passing: true`, `artifacts_produced: ["gate.passed", "manifest.json"]`.

---

## Post-Gate: CONSOLIDATE + LEARN (inspired by agentmemory's consolidation pipeline)

**Runs ONLY after gate.passed is written.** This step extracts reusable knowledge from the phase execution for future phases. It's the equivalent of agentmemory's `consolidate` → `crystallize` → `lessons` pipeline, but deterministic and structural.

The PARENT session (inline, no subagent) reads all phase artifacts and writes `agent_state/phases/${PHASE}/lessons.md`:

### 1. Extract Lessons

Read:
- `reports/collective_feedback.md` — what bugs were found and how they were fixed
- `reports/code_quality_review.md` — what patterns were flagged
- `execution.jsonl` — which agents failed/retried and why
- `checkpoints/` — how long each wave took

Write `agent_state/phases/${PHASE}/lessons.md`:

```markdown
# Phase ${PHASE} Lessons Learned
Generated: <timestamp>

## Patterns That Worked
- <pattern observed that should be repeated>
- <e.g., "Repository pattern with interface DI eliminated all mocking issues">

## Issues Encountered
- <issue>: <root cause> → <fix applied>
- <e.g., "E2E tests flaky on CI: race condition in DB seeding → added transaction isolation">

## Agent Performance
- Slowest agent: <name> (<duration>s) — reason: <why>
- Failed agents: <name> (attempt <N>) — root cause: <why>
- Retried: <count> total retries across all agents

## Recommendations for Phase ${PHASE+1}
- <actionable recommendation based on this phase's experience>
- <e.g., "Add DB seeding helper to test setup — 3 test agents re-implemented the same pattern">

## Patterns to Avoid
- <anti-pattern observed> — <why it's bad> — <what to do instead>
```

### 2. Update Cross-Phase Patterns (append-only)

If `agent_state/patterns.md` exists, append new patterns. If not, create it.

```markdown
# Accumulated Patterns (auto-updated after each phase gate)

## Phase 1 (2026-MM-DD)
- <patterns extracted>

## Phase 2 (2026-MM-DD)
- <patterns extracted>
```

This file is read by `project_planner` when planning Phase N+1 — it provides historical context about what works and what doesn't for THIS specific project.

### 3. Confidence Metadata for Codebase Knowledge

If `agent_state/codebase/` exists, update `.last-mapped` with a confidence indicator:

```bash
# After gate passes, codebase knowledge confidence increases
# (the mapping was validated by successful implementation + tests)
echo "sha:$(git rev-parse --short HEAD)" > agent_state/codebase/.last-mapped
echo "confidence:high" >> agent_state/codebase/.last-mapped
echo "validated_by:phase-${PHASE}-gate" >> agent_state/codebase/.last-mapped
echo "ts:$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> agent_state/codebase/.last-mapped
```

If the gate FAILS, confidence degrades:
```bash
echo "confidence:degraded" >> agent_state/codebase/.last-mapped
echo "reason:phase-${PHASE}-gate-failed" >> agent_state/codebase/.last-mapped
```

**Key insight from agentmemory:** Memory isn't just stored — it has a lifecycle. Knowledge that was validated by a passing gate is HIGH confidence. Knowledge that predates a failed gate is DEGRADED (the codebase changed in ways the mapping didn't predict). This drives the `/map --incremental` recommendation in `/health`.
