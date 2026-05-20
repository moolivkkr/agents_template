---
command: test
description: Run tests standalone — unit, integration, or e2e. Can target a specific phase or run all.
arguments:
  - name: phase
    required: false
    description: "Target phase (e.g. --phase=2). Omit to run all completed phases."
  - name: unit
    required: false
    default: false
    description: "Run unit tests only"
  - name: integration
    required: false
    default: false
    description: "Run integration tests only (requires infra running)"
  - name: e2e
    required: false
    default: false
    description: "Run e2e tests for all unlocked workflows"
  - name: workflow
    required: false
    description: "Run e2e for a specific workflow name (e.g. --workflow=user-registration)"
  - name: acceptance
    required: false
    default: false
    description: "Run acceptance tests only (use case + persona level)"
  - name: persona
    required: false
    description: "Run acceptance for a specific persona (e.g. --persona='Admin User')"
  - name: performance
    required: false
    default: false
    description: "Run performance tests (load + throughput) against NFR targets from BRD"
  - name: system
    required: false
    default: false
    description: "Run system-level tests (full stack smoke tests across all phase boundaries)"
  - name: manual
    required: false
    default: false
    description: "Generate manual test plan (exploratory test cases for QA team)"
---

# /test — Standalone Test Runner

Runs tests outside of `/develop`. Useful for validating after a hotfix, running e2e on demand, or regression testing before a release.

---

## Step 0 — Orient

```bash
# Determine which phases to test
if [ -n "$ARG_PHASE" ]; then
  PHASES=($ARG_PHASE)
else
  PHASES=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)
fi

# Determine test tiers
RUN_UNIT=$([ "$ARG_UNIT" = true ] || [ -z "$ARG_UNIT$ARG_INTEGRATION$ARG_E2E" ] && echo true)
RUN_INTEGRATION=$([ "$ARG_INTEGRATION" = true ] || [ -z "$ARG_UNIT$ARG_INTEGRATION$ARG_E2E" ] && echo true)
RUN_E2E=$([ "$ARG_E2E" = true ] || [ -z "$ARG_UNIT$ARG_INTEGRATION$ARG_E2E" ] && echo true)
```

Start infrastructure if running integration or e2e tests (read startup commands from `docs/IMPLEMENTATION_GUIDELINES.md`).

---

## Step 1 — Unit Tests

**Agent:** Generated `unit_test_agent`
**When:** `RUN_UNIT = true`

Reads: `docs/IMPLEMENTATION_GUIDELINES.md` for test commands, `agent_state/agent_registry.json` for test framework.

Runs all unit tests. Reports pass/fail per component.

---

## Step 2 — Integration Tests

**Agent:** Generated `integration_test_agent`
**When:** `RUN_INTEGRATION = true`

Requires infra running. Uses isolated test database/namespace — never touches production data.

---

## Step 3 — E2E Tests

**Agent:** `e2e_orchestrator` + generated `ui_test_agent` (if frontend enabled)
**When:** `RUN_E2E = true`

Reads `agent_state/phases/*/manifest.json` to identify all `e2e_workflows_unlocked`.
If `--workflow` specified: runs only that workflow.

Full stack must be running. Writes results to `agent_state/e2e/results.md`.

**Iteration:** On failure, diagnose → fix → rerun (max 2 attempts). Surface unresolved to user.

---

## Step 3b — Acceptance Tests (when --acceptance flag or no tier flags)

**Agent:** `acceptance_test_agent`
**When:** `RUN_ACCEPTANCE = true` (explicit `--acceptance` flag, or no tier flags = run all)

Reads BRD personas and in-scope use cases for the targeted phase(s).
Checks `requirements/test-data/` for user-provided seed data, generates if absent.
Executes use cases as each persona. Iterates on failures (max 2 rounds).

Results: `agent_state/phases/N/reports/acceptance_report.md`
Seed data: `agent_state/phases/N/test-data/generated-seed.yaml`

---

## Step 3c — Performance Tests (when --performance flag)

**Agent:** `performance_agent`

Reads NFR-* performance targets from `docs/BRD.md`. Runs load tests against the running stack.
Validates p95 latency and throughput targets per-endpoint.

Results: `agent_state/phases/N/reports/performance_report.md`

---

## Step 3d — System Tests (when --system flag)

**Agent:** `system_test_agent`

Runs smoke tests across all phase boundaries — validates end-to-end data flow across services without UI interaction. Confirms the full system hangs together as phases accumulate.

Results: `agent_state/reports/system_tests.md`

---

## Step 3e — Manual Test Plan (when --manual flag)

**Agent:** `manual_test_agent`

Generates a structured manual test plan from BRD personas and FR-* requirements. Output is a human-executable QA checklist, not automated tests.

Output: `agent_state/phases/N/reports/manual_test_plan.md`

---

## Step 4 — Report

```
Test Results — Phase(s): N

  Unit Tests:        X/X passed  (or FAILED: N failures)
  Integration Tests: X/X passed  (or FAILED: N failures)
  E2E Tests:         X/X passed  (or FAILED: N failures)
  Acceptance Tests:  X/X use cases passed | N personas exercised

  Failures (if any):
    ❌ <test name / use case> — <failure reason>
       Reproduction: <minimal reproduction steps>

  Reports:
    agent_state/e2e/results.md
    agent_state/phases/N/reports/acceptance_report.md

  ▶ After all phases complete: /accept (global full-product acceptance)
```
