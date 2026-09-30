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
  - name: traceability
    required: false
    default: false
    description: "Run TC-* ID inventory reconciliation — checks spec TC-* IDs against implemented test annotations"
  - name: mobile
    required: false
    default: false
    description: "Run the React Native tiers: Jest+RNTL (via test_runner) and device flows on iOS simulator + Android emulator (via mobile_e2e_orchestrator)"
  - name: platform
    required: false
    description: "With --mobile: restrict device flows to one platform (ios | android). Default: both. A single-platform run can never satisfy a phase gate."
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
# Mobile runs when asked, or by default when the project has a React Native app and no tier flag was given
MOBILE_ENABLED=$(jq -r '.tech_profile.mobile.enabled // false' agent_state/agent_registry.json 2>/dev/null)
RUN_MOBILE=$([ "$ARG_MOBILE" = true ] || { [ -z "$ARG_UNIT$ARG_INTEGRATION$ARG_E2E$ARG_MOBILE" ] && [ "$MOBILE_ENABLED" = true ]; } && echo true)
PLATFORMS="${ARG_PLATFORM:-ios android}"
```

Start infrastructure if running integration or e2e tests (read startup commands from `docs/IMPLEMENTATION_GUIDELINES.md`).

---

## Step 1 — Unit Tests

**Agent:** `test_runner` (`subagent_type: test_runner`). It RUNS existing tests. The generated
`unit_test_agent` writes tests and is only used here when `--traceability` shows missing TC-* IDs
and you choose to fill them.
**When:** `RUN_UNIT = true`

Reads: `docs/IMPLEMENTATION_GUIDELINES.md` for test commands, `agent_state/agent_registry.json` for test framework.

Runs all unit tests. Reports pass/fail per component to `agent_state/phases/N/reports/test_results.md`.

---

## Step 2 — Integration Tests

**Agent:** `test_runner` (same spawn as Step 1, integration tier). The generated `integration_test_agent` is the writer, not the runner.
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

## Step 3-M — Mobile (React Native, iOS + Android) — when `RUN_MOBILE = true`

1. **Node tiers** (Jest + RNTL component/integration): `test_runner`, with the mobile app dir as the
   working directory. No device needed.
2. **Device tiers** (TC-ME2E / TC-MPLT / TC-MVIS / TC-MPERF): spawn `mobile_e2e_orchestrator`
   (`subagent_type: mobile_e2e_orchestrator`) with `PLATFORMS=${PLATFORMS}`. It builds release binaries,
   boots the device matrix from IMPLEMENTATION_GUIDELINES §Mobile, runs every flow from every completed
   phase's `mobile_test_agent` manifest, and writes `agent_state/phases/N/reports/mobile_e2e_results.md` (+ `.json`).
   The backend must be up (Android reaches it at `10.0.2.2`).
3. iOS needs a macOS host with Xcode. On any other host the iOS column is `BLOCKED — requires macOS`,
   reported, not skipped silently.

With `--platform=ios|android` only that platform runs. The report header says so, and the result
cannot be used as gate evidence, which needs both platforms.

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

## Step 3f — TC-* ID Traceability Check (when --traceability flag)

**Agent:** `spec_test_reconciler` (inventory mode only)

Runs the TC-* ID inventory reconciliation without running any tests. Useful for checking test coverage gaps before a full test run.

```bash
SPEC_DIR="docs/design/phases/${PHASE}/specs"
SPEC_IDS=$(grep -rhoP 'TC-[A-Z0-9]+-\d+' "$SPEC_DIR" 2>/dev/null | sort -u)
SPEC_COUNT=$(echo "$SPEC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

if [ "$SPEC_COUNT" -eq 0 ]; then
  echo "No TC-* IDs found in phase specs — nothing to check"
  exit 0
fi

IMPL_IDS=$(grep -rhoP 'TC-[A-Z0-9]+-\d+' tests/ src/ test/ e2e/ apps/ mobile/ 2>/dev/null \
  --include="*_test.*" --include="*.test.*" --include="*.spec.*" --include="*.yaml" --include="*.yml" --exclude-dir=node_modules --exclude-dir=Pods --exclude-dir=build | sort -u)
IMPL_COUNT=$(echo "$IMPL_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
MISSING=$(comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
MISSING_COUNT=$(echo "$MISSING" | grep -c 'TC-' 2>/dev/null || echo 0)
COVERAGE_PCT=$(( IMPL_COUNT * 100 / SPEC_COUNT ))

echo "TC-* Inventory — Phase ${PHASE}"
echo "  Spec IDs:        $SPEC_COUNT"
echo "  Implemented:     $IMPL_COUNT"
echo "  Missing:         $MISSING_COUNT"
echo "  Coverage:        ${COVERAGE_PCT}%"

if [ "$MISSING_COUNT" -gt 0 ]; then
  echo ""
  echo "  Missing TC-* IDs:"
  echo "$MISSING" | head -30
  [ "$MISSING_COUNT" -gt 30 ] && echo "  ... and $((MISSING_COUNT - 30)) more"
fi

# Per-category breakdown
echo ""
echo "  Per-Category:"
for CAT in $(echo "$SPEC_IDS" | grep -oP 'TC-\K[A-Z0-9]+' | sort -u); do
  CAT_SPEC=$(echo "$SPEC_IDS" | grep -c "TC-${CAT}-")
  CAT_IMPL=$(echo "$IMPL_IDS" | grep -c "TC-${CAT}-" 2>/dev/null || echo 0)
  CAT_PCT=$(( CAT_IMPL * 100 / CAT_SPEC ))
  echo "    ${CAT}: ${CAT_IMPL}/${CAT_SPEC} (${CAT_PCT}%)"
done
```

Output: `agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md`

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
