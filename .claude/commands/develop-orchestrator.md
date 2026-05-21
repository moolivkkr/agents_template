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
