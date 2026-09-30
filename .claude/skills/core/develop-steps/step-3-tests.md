<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

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

A test that fails and then passes on retry is **FLAKY**. It counts as a failure (`flaky` in the
sidecar, and the gate blocks on it). See `~/.claude/skills/testing/test-results-sidecar.md` §Flakes.
1. **Fix it first.** Look for shared state, time, ordering, unawaited async, or selectors that race
   the UI. Re-run the tier 3× (`-race`, `--repeat-each=3`) to prove the fix.
2. **Quarantine only if the fix outlasts the phase.** Exclude the test from the run and list it in the
   tier sidecar's `quarantined[]` with an `issue` link and an `expires` date ≤ 14 days out. Never use
   a bare `t.Skip` / `test.skip`: the test-diff check (`tc-inventory.py --diff-base`) flags new skips,
   and a skip has no expiry. When `expires` passes, the gate blocks again.

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
