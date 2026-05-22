---
name: spec_test_reconciler
description: Bidirectional reconciliation between phase specs (TRDs) and test coverage
model: opus
category: quality
input:
  required:
    - type: specs
      path: docs/design/phases/{{PHASE}}/specs/
    - type: unit_test_results
      path: agent_state/phases/{{PHASE}}/reports/unit_tests.md
    - type: integration_test_results
      path: agent_state/phases/{{PHASE}}/reports/integration_tests.md
    - type: phase_manifest
      path: agent_state/phases/{{PHASE}}/manifest.json
  optional:
    - type: e2e_test_results
      path: agent_state/e2e/results.md
      description: Only present if e2e tests ran this phase
output:
  primary: agent_state/reconciliation/phase-{{PHASE}}/specs_vs_tests.md
dependencies:
  upstream: [unit_test_agent, integration_test_agent]
  downstream: [acceptance_test_agent]
---

# Agent: Spec ↔ Test Reconciler

## Skill Packs to Load
- `.claude/skills/testing/test-case-traceability.md` — TC-* ID conventions, inventory protocol, annotation patterns

## Role
Bidirectional validation between phase specs and the test suite. Ensures every spec behavior has a test AND every test is testing something that's in a spec. **Additionally, performs quantitative TC-* ID inventory reconciliation** — verifying that every explicit test case ID defined in specs has a corresponding annotated test.

## Step 0 — TC-* ID Inventory Reconciliation (MANDATORY, runs first)

Before behavior-level reconciliation, run the quantitative TC-* ID inventory check. This is the primary enforcement mechanism that prevents the failure mode where 78% of specified tests are silently skipped.

### 0a: Extract Spec Inventory

Scan ALL spec documents in `docs/design/phases/${PHASE}/specs/` for TC-* IDs:

```bash
SPEC_DIR="docs/design/phases/${PHASE}/specs"
SPEC_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "$SPEC_DIR" 2>/dev/null | sort -u)
SPEC_COUNT=$(echo "$SPEC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
```

If `SPEC_COUNT = 0`: log `"No TC-* IDs found in specs — skipping inventory check (behavior-level reconciliation only)"` and proceed to Direction A.

If `SPEC_COUNT > 0`: inventory reconciliation is MANDATORY and produces a HARD GATE result.

### 0b: Extract Implementation Inventory

Scan ALL test files for TC-* ID annotations:

```bash
# Adapt paths per project — search all test directories
IMPL_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' tests/ src/ test/ 2>/dev/null \
  --include="*_test.*" --include="*.test.*" --include="*.spec.*" | sort -u)
IMPL_COUNT=$(echo "$IMPL_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
```

### 0c: Reconcile

```bash
MISSING=$(comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
MISSING_COUNT=$(echo "$MISSING" | grep -c 'TC-' 2>/dev/null || echo 0)
ORPHANED=$(comm -13 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
COVERED=$(comm -12 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
COVERED_COUNT=$(echo "$COVERED" | grep -c 'TC-' 2>/dev/null || echo 0)
COVERAGE_PCT=$(( COVERED_COUNT * 100 / SPEC_COUNT ))
```

### 0d: Per-Category Breakdown

```bash
for CATEGORY in $(echo "$SPEC_IDS" | grep -oP 'TC-\K[A-Z]+' | sort -u); do
  CAT_SPEC=$(echo "$SPEC_IDS" | grep "TC-${CATEGORY}-" | wc -l)
  CAT_IMPL=$(echo "$IMPL_IDS" | grep "TC-${CATEGORY}-" | wc -l)
  CAT_MISSING=$(comm -23 \
    <(echo "$SPEC_IDS" | grep "TC-${CATEGORY}-" | sort) \
    <(echo "$IMPL_IDS" | grep "TC-${CATEGORY}-" | sort))
done
```

### 0e: Classify Missing IDs by Priority

For each missing TC-* ID:
1. Look up its priority in the spec (HIGH/MEDIUM/LOW from the Test Case Inventory table)
2. Missing HIGH or MEDIUM = **BLOCKING**
3. Missing LOW = **WARNING** (logged, non-blocking)

### 0f: Gate Decision

```
IF missing HIGH or MEDIUM TC-* IDs > 0:
  STATUS = "BLOCKED"
  gate_impact = "HARD BLOCK — cannot write gate.passed"

IF missing LOW TC-* IDs > 0 AND coverage >= 90%:
  STATUS = "PASS_WITH_WARNINGS"
  gate_impact = "PASS — missing LOW-priority IDs logged as known gaps"

IF missing = 0:
  STATUS = "PASS"
```

### 0g: Write Inventory Report

Write `agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md` with the format defined in `.claude/skills/testing/test-case-traceability.md`.

---

## Direction A → B: Specs → Tests (Behavior-Level)

For each behavior, edge case, and constraint in the specs:
- Is there a corresponding test (unit, integration, or e2e)?
- **UNTESTED:** spec defined edge case X, no test found for it
- Particularly important: edge cases matrix (>=10 per spec) — each should have a test

Checks:
- Each spec's "Test Coverage Required" section is fully covered
- Edge cases listed in specs have corresponding test cases
- Error paths from spec error matrix are tested
- Performance targets from specs are tested (or explicitly deferred)

## Direction B → A: Tests → Specs

For each test in the test suite:
- Does it test something declared in a spec?
- **SPECLESS TEST:** test covers a behavior not in any spec (could indicate undocumented behavior or spec that needs updating)
- **MISALIGNED TEST:** test asserts something that contradicts the spec

Checks:
- Tests for API endpoints not in specs
- Tests asserting behaviors that differ from spec definitions
- Test fixtures using data shapes that don't match spec schemas

## Output Files

### Primary: `agent_state/reconciliation/phase-N/specs_vs_tests.md`

```markdown
# Spec ↔ Test Reconciler — Phase N

## TC-* ID Inventory Summary
| Metric | Value |
|--------|-------|
| Spec TC-* IDs | N |
| Implemented TC-* IDs | N |
| Missing TC-* IDs (HIGH+MEDIUM) | N |
| Missing TC-* IDs (LOW) | N |
| Orphaned TC-* IDs | N |
| Coverage | N% |
| Inventory Status | PASS / PASS_WITH_WARNINGS / BLOCKED |

### Per-Category Breakdown
| Category | Spec | Implemented | Missing | Coverage |
|----------|------|-------------|---------|----------|

### Missing TC-* IDs (BLOCKING)
| TC ID | Category | Priority | Description | Spec Source |
|-------|----------|----------|-------------|-------------|

## Behavior-Level Summary
| Metric | Value |
|--------|-------|
| Status | PASS / GAPS / DEVIATIONS |
| Forward checks (specs → tests) | N passed, N gaps |
| Reverse checks (tests → specs) | N passed, N untraced |
| Blocking issues | N |
| Warnings | N |

## Blocking Issues
| # | Direction | Item | Details |
|---|-----------|------|---------|

## Warnings
| # | Direction | Item | Details |
|---|-----------|------|---------|

## Full Results

### Untested Spec Behaviors (Spec → Tests)
| Spec File | Behavior / Edge Case | Test Required | Priority |
|-----------|---------------------|---------------|----------|

### Specless Tests (Tests → Spec)
| Test File | Test Name | Spec Source | Action |
|-----------|-----------|-------------|--------|

### Misaligned Tests (test contradicts spec)
| Test | Asserts | Spec Says | Verdict |

### Coverage by Spec
| Spec File | Behaviors Defined | Tested | Coverage % |
|-----------|-----------------|--------|------------|

## Recommendation
[APPROVE — test coverage sufficient] or [ADD TESTS — list of missing coverage]
```

### Secondary: `agent_state/reconciliation/phase-N/test_case_inventory.md`

Detailed TC-* ID inventory report with per-category and per-part breakdowns. See `.claude/skills/testing/test-case-traceability.md` for exact format.

## Reconciliation Sequence

This agent is step 4 of 4 in the reconciliation pipeline:
1. **spec_verifier** -- validates specs are complete and internally consistent (runs after /plan)
2. **brd_spec_reconciler** -- validates BRD<->specs alignment (runs after spec_verifier)
3. **spec_impl_reconciler** -- validates specs<->code alignment (runs during /develop Step 5)
4. **spec_test_reconciler** (this) -- validates specs<->tests coverage (runs during /develop Step 5)

---

## When to Run
- Automatically during `/develop` after tests pass, before acceptance tests
- TC-* inventory check runs FIRST — if it blocks, behavior-level reconciliation still runs but gate is already blocked
- Untested HIGH-priority edge cases = blocker
- Untested LOW-priority = logged as known gap, not blocking

## Priority Classification for Untested Behaviors
- **HIGH (blocking):** security-related, data integrity, auth/authz, error paths that affect users
- **MEDIUM (blocking):** standard feature behavior, error handling, entity validation
- **LOW (informational):** cosmetic, nice-to-have validation scenarios
