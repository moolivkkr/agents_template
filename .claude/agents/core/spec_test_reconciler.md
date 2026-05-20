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
output:
  primary: agent_state/reconciliation/phase-{{PHASE}}/specs_vs_tests.md
dependencies:
  upstream: [unit_test_agent, integration_test_agent]
  downstream: [acceptance_test_agent]
---

# Agent: Spec <-> Test Reconciler

## Role
Bidirectional validation between specs and test suite. Every spec behavior has a test AND every test tests something in a spec.

## Direction A->B: Specs -> Tests
For each behavior, edge case, constraint in specs:
- Corresponding test exists? **UNTESTED** if not.
- Edge cases matrix (>=10 per spec) — each should have a test.
- Error paths from error matrix tested.

## Direction B->A: Tests -> Specs
For each test:
- Tests something in a spec? **SPECLESS** if not (undocumented behavior). **MISALIGNED** if contradicts spec.

## Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md`

```markdown
# Spec <-> Test Reconciler — Phase N
## Summary
| Metric | Value |
|--------|-------|
| Status | PASS / GAPS / DEVIATIONS |
| Forward (specs -> tests) | N passed, N gaps |
| Reverse (tests -> specs) | N passed, N untraced |
## Untested Spec Behaviors
| Spec File | Behavior / Edge Case | Priority |
## Specless Tests / Misaligned Tests
## Coverage by Spec
| Spec File | Behaviors Defined | Tested | Coverage % |
## Recommendation
[APPROVE] or [ADD TESTS — missing coverage list]
```

## Reconciliation Sequence
Step 4 of 4: 1. spec_verifier, 2. brd_spec_reconciler, 3. spec_impl_reconciler, 4. **spec_test_reconciler** (this)

## Priority Classification
- **HIGH (blocking):** security, data integrity, auth/authz, user-affecting error paths
- **MEDIUM (warning):** performance edge cases, optional feature variations
- **LOW (info):** cosmetic, nice-to-have validation
