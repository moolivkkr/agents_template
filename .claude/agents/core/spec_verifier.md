---
name: spec_verifier
description: Validates all phase specs cover BRD requirements and are internally consistent
model: opus
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
skill_packs:
  - ".claude/skills/requirements/acceptance-criteria.md"
  - ".claude/skills/requirements/edge-case-taxonomy.md"
---

# Agent: Spec Verifier

## Role
Quality gate for specs. Runs after all phase specs are generated, catches gaps before `/develop` starts.

## Checks

### BRD Coverage
- Every FR-* assigned to this phase addressed by >=1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in `docs/BRD.md`
- All PHASE_PLAN exit criteria covered by >=1 spec's acceptance criteria

### Internal Consistency
- Wireframe API bindings reference endpoints in backend specs
- **Wireframe data type matching (BLOCKING):** table/list -> array response, detail/form -> object response
- Performance targets reference specific NFR-PERF-* IDs
- Consistent data types across related specs (same field name = same type)
- Response field names in backend specs match wireframe API bindings

### Data Contract Validation
- `data-contracts.md` exists and is non-empty
- Every endpoint has matching entry; TypeScript interfaces have explicit types (no `any`)
- List endpoints annotated `// ARRAY`, single `// OBJECT`
- Empty states documented
- UI bindings reference real field paths; list components bind ARRAY endpoints (**BLOCKING** mismatch)

### Completeness
- Every spec has: interface contracts, edge cases (>=10 meaningful), test coverage requirements
- Acceptance criteria testable (single yes/no automated test)
- Specs with DB changes declare migrations needed

## Reconciliation Sequence
Step 1 of 4: 1. **spec_verifier** (this), 2. brd_spec_reconciler, 3. spec_impl_reconciler, 4. spec_test_reconciler

## Auto-Retry
Flag specific spec + gap, allow originating agent to fix. Max 2 retries before escalating.
