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

Runs tests outside of `/develop`. Useful after hotfixes, on-demand e2e, or pre-release regression testing.

---

## Step 0 — Orient

```bash
if [ -n "$ARG_PHASE" ]; then PHASES=($ARG_PHASE)
else PHASES=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n); fi
# No tier flags = run all tiers
```

Start infrastructure if running integration/e2e/acceptance/performance tests.

---

## Step 1 — Unit Tests
**Agent:** `unit_test_agent` | **When:** `--unit` or no tier flags
Reads IMPLEMENTATION_GUIDELINES for test commands. Reports pass/fail per component.

## Step 2 — Integration Tests
**Agent:** `integration_test_agent` | **When:** `--integration` or no tier flags
Requires infra. Uses isolated test database — never touches production data.

## Step 3 — E2E Tests
**Agent:** `e2e_orchestrator` + `ui_test_agent` | **When:** `--e2e` or no tier flags
Reads manifests for `e2e_workflows_unlocked`. `--workflow` → specific workflow only. Full stack required. **Iteration:** diagnose → fix → rerun (max 2 attempts).
Results: `agent_state/e2e/results.md`

## Step 3b — Acceptance Tests
**Agent:** `acceptance_test_agent` | **When:** `--acceptance` or no tier flags
Reads BRD personas + use cases for targeted phase(s). Checks `requirements/test-data/` for seed data, generates if absent. Iterates on failures (max 2 rounds).
Results: `agent_state/phases/N/reports/acceptance_report.md`

## Step 3c — Performance Tests
**Agent:** `performance_agent` | **When:** `--performance`
Reads NFR-* targets from BRD. Validates p95 latency + throughput per endpoint.
Results: `agent_state/phases/N/reports/performance_report.md`

## Step 3d — System Tests
**Agent:** `system_test_agent` | **When:** `--system`
Smoke tests across all phase boundaries — validates end-to-end data flow without UI.
Results: `agent_state/reports/system_tests.md`

## Step 3e — Manual Test Plan
**Agent:** `manual_test_agent` | **When:** `--manual`
Generates human-executable QA checklist from BRD personas + FR-*.
Output: `agent_state/phases/N/reports/manual_test_plan.md`

---

## Step 4 — Report

```
Test Results — Phase(s): N
  Unit: X/X | Integration: X/X | E2E: X/X | Acceptance: X/X
  Failures: ❌ <test> — <reason> (reproduction steps)
  Reports: agent_state/e2e/results.md, agent_state/phases/N/reports/...
  ▶ After all phases: /accept (global acceptance)
```
