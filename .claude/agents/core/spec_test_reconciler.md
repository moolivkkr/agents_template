---
name: spec_test_reconciler
description: Bidirectional reconciliation between phase specs (TRDs) and test coverage
model: sonnet
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

## Role
Bidirectional validation between phase specs and the test suite. Ensures every spec behavior has a test AND every test is testing something that's in a spec.

## Direction A → B: Specs → Tests

For each behavior, edge case, and constraint in the specs:
- Is there a corresponding test (unit, integration, or e2e)?
- **UNTESTED:** spec defined edge case X, no test found for it
- Particularly important: edge cases matrix (≥10 per spec) — each should have a test

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

## Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md`

```markdown
# Spec ↔ Test Reconciliation — Phase N

## Summary
PASS | N untested spec behaviors | N specless tests

## Untested Spec Behaviors (Spec → Tests)
| Spec File | Behavior / Edge Case | Test Required | Priority |
|-----------|---------------------|---------------|----------|

## Specless Tests (Tests → Spec)
| Test File | Test Name | Spec Source | Action |
|-----------|-----------|-------------|--------|

## Misaligned Tests (test contradicts spec)
| Test | Asserts | Spec Says | Verdict |

## Coverage by Spec
| Spec File | Behaviors Defined | Tested | Coverage % |
|-----------|-----------------|--------|------------|

## Recommendation
[APPROVE — test coverage sufficient] or [ADD TESTS — list of missing coverage]
```

## Reconciliation Sequence

This agent is step 4 of 4 in the reconciliation pipeline:
1. **spec_verifier** -- validates specs are complete and internally consistent (runs after /plan)
2. **brd_spec_reconciler** -- validates BRD<->specs alignment (runs after spec_verifier)
3. **spec_impl_reconciler** -- validates specs<->code alignment (runs during /develop Step 5)
4. **spec_test_reconciler** (this) -- validates specs<->tests coverage (runs during /develop Step 5)

---

## When to Run
- Automatically during `/develop` after tests pass, before acceptance tests
- Untested HIGH-priority edge cases = blocker
- Untested LOW-priority = logged as known gap, not blocking

## Priority Classification for Untested Behaviors
- **HIGH (blocking):** security-related, data integrity, auth/authz, error paths that affect users
- **MEDIUM (warning):** performance edge cases, optional feature variations
- **LOW (informational):** cosmetic, nice-to-have validation scenarios
