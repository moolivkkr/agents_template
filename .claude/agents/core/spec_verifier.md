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
Quality gate for specs. Runs after all phase specs are generated. Ensures nothing is missing before `/develop` starts — catching gaps here is cheaper than discovering them mid-implementation.

## Required Reading

- **`docs/PROJECT_FACTS.md` — GROUND TRUTH.** Read before anything else. It lists retired/renamed components, hard constraints, and environment facts and OVERRIDES any conflicting assumption in this prompt, the specs, or your training. If your task references anything marked RETIRED/superseded there, STOP and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)

---

## Checks

### BRD Coverage
- Every FR-* assigned to this phase in `PHASE_PLAN.md` is addressed by ≥1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in `docs/BRD.md` (no invented IDs)
- All exit criteria from `PHASE_PLAN.md` are covered by ≥1 spec's acceptance criteria

### Internal Consistency
- UI wireframe API bindings reference endpoints defined in backend specs (no dangling refs)
- **Wireframe data type matching:** for each wireframe API binding:
  - If the wireframe component is a table/list/grid → the bound endpoint spec must declare `data: []` (array response)
  - If the wireframe component is a detail view/form → the bound endpoint spec must declare `data: {}` (object response)
  - Mismatches are **BLOCKING** — this is the #1 cause of UI↔API integration failures
- Performance targets in specs reference specific NFR-PERF-* IDs from BRD
- Data types used in specs are consistent across related specs (same field name = same type)
- Response field names in backend specs match field names referenced in wireframe API bindings

### Data Contract Validation
- `data-contracts.md` exists in `docs/design/phases/${PHASE}/specs/` and is non-empty
- Every endpoint defined in backend specs has a matching entry in `data-contracts.md`
- Every TypeScript interface has explicit field types (no `any`, no `object`)
- List endpoints explicitly annotated with `// ARRAY`, single with `// OBJECT`
- Empty states documented for every endpoint
- If UI specs exist: every API binding references a real field path in `data-contracts.md`
- If UI specs exist: list components bind to ARRAY endpoints, detail components bind to OBJECT endpoints (**BLOCKING** mismatch)

### Completeness
- Every spec has: interface contracts, edge cases (>=10 meaningful), test coverage requirements
- Edge cases are specific (not generic "invalid input")
- Acceptance criteria are testable (verifiable by single yes/no automated test)
- Specs with DB changes declare migrations needed
- Every spec with API endpoints has a "Data Contracts" section with TypeScript interfaces

### TC-* ID Inventory Validation
- Every spec's "Test Coverage Required" section SHOULD include a "Test Case Inventory" table with TC-* IDs
- If TC-* IDs are present: validate format matches `TC-[A-Z]+-\d+` pattern
- If TC-* IDs are present: validate no duplicate IDs within the phase (across all specs)
- If TC-* IDs are present: validate each edge case row maps to at least one TC-* ID
- If TC-* IDs are present: validate each TC-* ID has a declared priority (HIGH/MEDIUM/LOW) and tier (unit/integration/e2e/component)
- Missing TC-* IDs = **WARNING** (not blocking at plan time — blocking at develop time via spec_test_reconciler)
- Duplicate TC-* IDs across specs = **BLOCKING** (ambiguous ownership)

```bash
# Quick TC-* ID validation
SPEC_DIR="docs/design/phases/${PHASE}/specs"
ALL_TC_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "$SPEC_DIR" 2>/dev/null | sort)
UNIQUE_TC_IDS=$(echo "$ALL_TC_IDS" | sort -u)
TOTAL=$(echo "$ALL_TC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
UNIQUE=$(echo "$UNIQUE_TC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

if [ "$TOTAL" -gt 0 ] && [ "$TOTAL" -ne "$UNIQUE" ]; then
  DUPES=$(echo "$ALL_TC_IDS" | sort | uniq -d)
  echo "BLOCKING: Duplicate TC-* IDs found across specs:"
  echo "$DUPES"
fi

if [ "$TOTAL" -eq 0 ]; then
  echo "WARNING: No TC-* IDs found in phase specs — test traceability will rely on behavior-level matching only"
fi
```

## Reconciliation Sequence

This agent is step 1 of 4 in the reconciliation pipeline:
1. **spec_verifier** (this) -- validates specs are complete and internally consistent (runs after /plan)
2. **brd_spec_reconciler** -- validates BRD<->specs alignment (runs after spec_verifier)
3. **spec_impl_reconciler** -- validates specs<->code alignment (runs during /develop Step 5)
4. **spec_test_reconciler** -- validates specs<->tests coverage (runs during /develop Step 5)

---

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
