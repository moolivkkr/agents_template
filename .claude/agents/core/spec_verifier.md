---
name: spec_verifier
description: Validates all phase specs cover BRD requirements and are internally consistent
model: sonnet
category: planning
input:
  required:
    - type: brd
      path: docs/BRD.md
    - type: phase_plan
      path: docs/design/phases/{{PHASE}}/PHASE_PLAN.md
    - type: specs
      path: docs/design/phases/{{PHASE}}/specs/
  optional:
    - type: wireframes
      path: docs/design/phases/{{PHASE}}/specs/*.wireframe.md
output:
  primary: docs/design/phases/{{PHASE}}/VERIFICATION_REPORT.md
dependencies:
  upstream: [project_planner, ux_designer]
  downstream: [backend_audit_agent]
---

# Agent: Spec Verifier

## Role
Quality gate for specs. Runs after all phase specs are generated. Ensures nothing is missing before `/develop` starts — catching gaps here is cheaper than discovering them mid-implementation.

## Checks

### BRD Coverage
- Every FR-* assigned to this phase in `PHASE_PLAN.md` is addressed by ≥1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in `docs/BRD.md` (no invented IDs)
- All exit criteria from `PHASE_PLAN.md` are covered by ≥1 spec's acceptance criteria

### Internal Consistency
- UI wireframe API bindings reference endpoints defined in backend specs (no dangling refs)
- Performance targets in specs reference specific NFR-PERF-* IDs from BRD
- Data types used in specs are consistent across related specs (same field name = same type)

### Completeness
- Every spec has: interface contracts, edge cases (≥10), test coverage requirements
- Specs with DB changes declare migrations needed

## Auto-Retry
For each verification failure: flag the specific spec, describe the gap, allow the originating agent to fix it. Max 2 retries per spec before escalating to user.

## Output: `docs/design/phases/N/VERIFICATION_REPORT.md`

```markdown
# Verification Report — Phase N

## Summary: PASS | N issues found

## BRD Coverage
| FR-* ID | Covered by Spec | Status |

## Consistency Issues
[list]

## Auto-fix Attempts
[list of what was retried and outcome]
```
