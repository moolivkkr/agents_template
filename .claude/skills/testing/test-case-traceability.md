# Test Case ID Traceability — Spec-to-Test Inventory Enforcement

## Purpose

Ensures that EVERY test case defined in spec documents is implemented as an actual test. Prevents the failure mode where a spec defines 153 test cases but only 34 get implemented (22% coverage) and the phase gate still passes.

This skill introduces:
1. **TC-* ID convention** — unique identifiers for every test case in specs
2. **Test inventory extraction** — automated enumeration of all TC-* IDs from spec documents
3. **Test annotation protocol** — how test files declare which TC-* IDs they cover
4. **Quantitative reconciliation** — spec inventory vs implemented inventory = gap report
5. **Hard gate enforcement** — phase CANNOT pass with unimplemented TC-* IDs

---

## TC-* ID Convention

### Format

```
TC-{CATEGORY}-{NNN}
```

Where:
- `TC` = Test Case (fixed prefix)
- `CATEGORY` = 2-5 character category code (uppercase)
- `NNN` = Zero-padded sequential number within category

### Standard Categories

| Code | Category | Example |
|------|----------|---------|
| `E` | Entity/model tests | TC-E-001 |
| `S` | Scope/filter tests | TC-S-001 |
| `CH` | Channel/routing tests | TC-CH-001 |
| `MODE` | Mode/behavior tests | TC-MODE-001 |
| `E2E` | End-to-end scenarios | TC-E2E-001 |
| `ENT` | Entity metadata | TC-ENT-001 |
| `PIPE` | Pipeline/processing | TC-PIPE-001 |
| `COMP` | Compiler/builder | TC-COMP-001 |
| `API` | API endpoint tests | TC-API-001 |
| `DB` | Database/persistence | TC-DB-001 |
| `AUTH` | Authentication/authorization | TC-AUTH-001 |
| `UI` | UI component tests | TC-UI-001 |
| `FORM` | Form/validation tests | TC-FORM-001 |
| `SEC` | Security tests | TC-SEC-001 |
| `PERF` | Performance tests | TC-PERF-001 |
| `ACC` | Accessibility tests | TC-ACC-001 |
| `WASM` | WASM parity tests | TC-WASM-001 |

Projects MAY define custom categories in their TEST-SUITE.md. The category code must be unique within the project.

### Range Assignments

Specs SHOULD assign contiguous ID ranges per entity/component:

```markdown
## Entity: Pattern
TC-E-106 to TC-E-110 — Pattern struct field tests
TC-E-111 to TC-E-115 — Pattern validation tests
```

This allows bulk tracking: "TC-E-106 to TC-E-115: 10 IDs, 8 implemented, 2 missing."

---

## How Specs Define Test Inventories

### In TRD Specs (spec_writer output)

Every spec's "Test Coverage Required" section MUST include a test inventory table with explicit TC-* IDs:

```markdown
## Test Coverage Required

### Test Inventory

| TC ID | Category | Test Description | Priority | Tier |
|-------|----------|-----------------|----------|------|
| TC-E-001 | Entity | Pattern struct has all required fields | HIGH | unit |
| TC-E-002 | Entity | Pattern validation rejects empty name | HIGH | unit |
| TC-E-003 | Entity | Pattern regex compilation succeeds for valid patterns | HIGH | unit |
| TC-E-004 | Entity | Pattern regex compilation fails for invalid patterns | HIGH | unit |
| TC-S-001 | Scope | User scope include evaluates correctly | HIGH | unit |
| TC-S-002 | Scope | User scope exclude evaluates correctly | HIGH | unit |
| TC-E2E-001 | E2E | PCI detection across 17 channels | HIGH | e2e |
| TC-UI-001 | UI | Pattern editor form renders all fields | MEDIUM | component |
```

### In Standalone TEST-SUITE.md Documents

Large test suites MAY be defined in a separate `TEST-SUITE.md` file organized into parts:

```markdown
# TEST-SUITE.md

## Part 1 — Entity Tests (TC-E-001 to TC-E-340)
### Category 1: User Entity (TC-E-001 to TC-E-015)
| TC ID | Description | Input | Expected Output |
|-------|------------|-------|-----------------|
| TC-E-001 | User struct has id field | ... | ... |

## Part 2 — Scope Tests (TC-S-001 to TC-S-026)
...

## Part 3 — Channel Tests (TC-CH-001 to TC-CH-022)
...
```

### Priority Classification

| Priority | Gate Impact | Definition |
|----------|-----------|------------|
| HIGH | BLOCKING | Core functionality, security, data integrity |
| MEDIUM | BLOCKING | Standard feature behavior, error handling |
| LOW | WARNING | Edge cases, cosmetic, nice-to-have validation |

**All HIGH and MEDIUM priority TC-* IDs MUST be implemented. LOW is tracked but non-blocking.**

### Test Tier Assignment

Each TC-* ID must declare which test tier it belongs to:

| Tier | Agent Responsible |
|------|------------------|
| `unit` | unit_test_agent |
| `integration` | integration_test_agent |
| `e2e` | ui_test_agent / e2e_orchestrator |
| `component` | ui_test_agent (Tier 1) |
| `acceptance` | acceptance_test_agent |

---

## How Test Files Annotate TC-* IDs

### Go Tests

```go
// TC-E-001: Pattern struct has all required fields
func TestPattern_HasRequiredFields(t *testing.T) { ... }

// TC-E-002, TC-E-003: Pattern validation (multiple IDs per test allowed)
func TestPattern_Validation(t *testing.T) {
    tests := []struct {
        name string
        tcID string // TC ID for traceability
        ...
    }{
        {name: "rejects empty name", tcID: "TC-E-002", ...},
        {name: "valid regex compiles", tcID: "TC-E-003", ...},
    }
}
```

### TypeScript/JavaScript Tests

```typescript
// TC-UI-001: Pattern editor form renders all fields
describe('PatternEditor', () => {
  it('TC-UI-001: renders all form fields', () => { ... });
  it('TC-UI-002: validates required fields on submit', () => { ... });
});

// TC-E2E-001: PCI detection across 17 channels
test('TC-E2E-001: PCI detection end-to-end', async ({ page }) => { ... });
```

### Python Tests

```python
# TC-E-001: Pattern struct has all required fields
def test_pattern_has_required_fields():  # TC-E-001
    ...

# TC-E-002, TC-E-003: Pattern validation
@pytest.mark.parametrize("tc_id,input,expected", [
    ("TC-E-002", "", "error"),
    ("TC-E-003", "valid.*", "ok"),
])
def test_pattern_validation(tc_id, input, expected):
    ...
```

### Annotation Rules

1. **Every test function/case MUST include its TC-* ID** in a comment, test name, or metadata field
2. **One TC-* ID per test case** (a table-driven test may cover multiple IDs, one per row)
3. **TC-* IDs are grep-able** — the pattern `TC-[A-Z]+-\d+` must match in the test file
4. **Cross-file mapping is allowed** — a TC-* ID can appear in unit OR integration OR e2e (wherever it's implemented)

---

## Test Inventory Extraction Algorithm

### Phase 1: Extract Spec Inventory

Scan all spec documents for TC-* IDs:

```bash
# Extract all TC-* IDs from spec documents
SPEC_DIR="docs/design/phases/${PHASE}/specs"
TEST_SUITE="${SPEC_DIR}/TEST-SUITE.md"

# Sources: individual specs + standalone TEST-SUITE.md
SPEC_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "$SPEC_DIR" | sort -u)
SPEC_COUNT=$(echo "$SPEC_IDS" | wc -l | tr -d ' ')

echo "Spec inventory: $SPEC_COUNT unique TC-* IDs"
```

### Phase 2: Extract Implementation Inventory

Scan all test files for TC-* ID annotations:

```bash
# Extract all TC-* IDs from test files
TEST_DIRS=("tests/" "src/" "test/")  # adapt per project
IMPL_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "${TEST_DIRS[@]}" --include="*_test.*" --include="*.test.*" --include="*.spec.*" | sort -u)
IMPL_COUNT=$(echo "$IMPL_IDS" | wc -l | tr -d ' ')

echo "Implementation inventory: $IMPL_COUNT unique TC-* IDs"
```

### Phase 3: Reconcile

```bash
# IDs in spec but NOT in tests = MISSING
MISSING=$(comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
MISSING_COUNT=$(echo "$MISSING" | grep -c 'TC-' || echo 0)

# IDs in tests but NOT in spec = ORPHANED
ORPHANED=$(comm -13 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
ORPHANED_COUNT=$(echo "$ORPHANED" | grep -c 'TC-' || echo 0)

# IDs in both = COVERED
COVERED=$(comm -12 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS"))
COVERED_COUNT=$(echo "$COVERED" | grep -c 'TC-' || echo 0)

COVERAGE_PCT=$(( COVERED_COUNT * 100 / SPEC_COUNT ))
echo "Coverage: $COVERAGE_PCT% ($COVERED_COUNT / $SPEC_COUNT)"
```

### Phase 4: Per-Category Breakdown

```bash
# Group by category for granular tracking
for CATEGORY in $(echo "$SPEC_IDS" | grep -oP 'TC-\K[A-Z]+' | sort -u); do
  CAT_SPEC=$(echo "$SPEC_IDS" | grep "TC-${CATEGORY}-" | wc -l | tr -d ' ')
  CAT_IMPL=$(echo "$IMPL_IDS" | grep "TC-${CATEGORY}-" | wc -l | tr -d ' ')
  CAT_PCT=$(( CAT_IMPL * 100 / CAT_SPEC ))
  echo "  ${CATEGORY}: ${CAT_IMPL}/${CAT_SPEC} (${CAT_PCT}%)"
done
```

---

## Reconciliation Report Format

Output: `agent_state/reconciliation/phase-N/test_case_inventory.md`

```markdown
# Test Case Inventory Reconciliation — Phase N

## Summary

| Metric | Value |
|--------|-------|
| Spec TC-* IDs | 153 |
| Implemented TC-* IDs | 153 |
| Missing TC-* IDs | 0 |
| Orphaned TC-* IDs | 0 |
| Coverage | 100% |
| Status | PASS |

## Per-Category Breakdown

| Category | Spec Count | Implemented | Missing | Coverage |
|----------|-----------|-------------|---------|----------|
| E (Entity) | 66 | 66 | 0 | 100% |
| S (Scope) | 26 | 26 | 0 | 100% |
| CH (Channel) | 22 | 22 | 0 | 100% |
| MODE (Mode) | 10 | 10 | 0 | 100% |
| E2E | 6 | 6 | 0 | 100% |
| ENT (Meta) | 7 | 7 | 0 | 100% |
| PIPE | 6 | 6 | 0 | 100% |
| COMP | 10 | 10 | 0 | 100% |

## Per-Part Breakdown (if TEST-SUITE.md has parts)

| Part | Description | IDs | Implemented | Coverage |
|------|------------|-----|-------------|----------|
| Part 1 | Entity tests | TC-E-001 to TC-E-340 | 66/66 | 100% |
| Part 2 | Scope tests | TC-S-001 to TC-S-026 | 26/26 | 100% |
| Part 3 | Channel tests | TC-CH-001 to TC-CH-022 | 22/22 | 100% |
| Part 4 | Mode tests | TC-MODE-001 to TC-MODE-010 | 10/10 | 100% |
| Part 5 | E2E tests | TC-E2E-001 to TC-E2E-006 | 6/6 | 100% |

## Missing TC-* IDs (BLOCKING)

| TC ID | Category | Priority | Description | Spec Source |
|-------|----------|----------|-------------|-------------|
| (none) | | | | |

## Orphaned TC-* IDs (WARNING)

| TC ID | Test File | Action Needed |
|-------|-----------|---------------|
| (none) | | |

## TC-* to Test File Mapping

| TC ID | Test File | Test Function/Case |
|-------|-----------|-------------------|
| TC-E-001 | tests/unit/pattern_test.go | TestPattern_HasRequiredFields |
| TC-E-002 | tests/unit/pattern_test.go | TestPattern_Validation/rejects_empty_name |
| ... | ... | ... |
```

---

## Gate Enforcement Rules

### Per-Phase Gate (Step 6 of /develop)

**Test case inventory is a HARD GATE item.**

```
Gate Item                          Pass Condition
────────────────────────────────────────────────────────────────────
Test case inventory (TC-* IDs)     Coverage = 100% for HIGH+MEDIUM priority
                                   Coverage >= 90% for LOW priority
                                   Zero missing HIGH or MEDIUM TC-* IDs
```

If coverage < 100% for HIGH+MEDIUM:
- `gate.passed` MUST NOT be written
- List every missing TC-* ID with its category and description
- Surface as: `GATE BLOCKED: N TC-* IDs not implemented (see test_case_inventory.md)`

### Cross-Phase Gate (/accept)

After all phases complete:
1. Merge all per-phase `test_case_inventory.md` files
2. Produce global inventory: all TC-* IDs across all phases
3. Verify zero gaps in the global inventory
4. Report global coverage per category

### Phased Test Implementation

When a spec defines TC-* IDs that span multiple phases (e.g., entities in Phase 1, scopes in Phase 2):
1. Each phase's spec declares which TC-* IDs are **in scope** for that phase
2. Out-of-scope IDs are listed as `DEFERRED: Phase N` (not counted as missing)
3. The deferred IDs MUST appear in the target phase's spec
4. `/accept` verifies ALL deferred IDs are eventually covered

```markdown
## Phase Scope

### In Scope (must implement this phase)
TC-E-001 to TC-E-340, TC-ENT-001 to TC-ENT-007

### Deferred to Phase 2
TC-S-001 to TC-S-026 (Scope tests — depends on scope engine in Phase 2)
TC-CH-001 to TC-CH-022 (Channel tests — depends on channel registry in Phase 2)
```

---

## Manifest Integration

The phase manifest MUST include a `test_case_inventory` field:

```json
{
  "test_case_inventory": {
    "spec_count": 153,
    "implemented_count": 153,
    "missing_count": 0,
    "orphaned_count": 0,
    "coverage_pct": 100,
    "by_category": {
      "E": { "spec": 66, "impl": 66, "missing": 0 },
      "S": { "spec": 26, "impl": 26, "missing": 0 },
      "CH": { "spec": 22, "impl": 22, "missing": 0 }
    },
    "missing_ids": [],
    "deferred_ids": [],
    "report": "agent_state/reconciliation/phase-N/test_case_inventory.md"
  }
}
```

---

## Agent Responsibilities

| Agent | Responsibility |
|-------|---------------|
| `spec_writer` | Assign TC-* IDs to all test cases in "Test Coverage Required" section |
| `unit_test_agent` | Annotate test functions with TC-* IDs; cover all `tier: unit` TC-* IDs |
| `integration_test_agent` | Annotate test functions with TC-* IDs; cover all `tier: integration` TC-* IDs |
| `ui_test_agent` | Annotate test functions with TC-* IDs; cover all `tier: component` and `tier: e2e` TC-* IDs |
| `acceptance_test_agent` | Cover all `tier: acceptance` TC-* IDs |
| `spec_test_reconciler` | Extract inventories, reconcile, produce gap report, enforce gate |

---

## Processing Order Protocol

When a spec defines TC-* IDs organized into Parts or Categories, test agents MUST process them **in document order** — Part 1 before Part 2, Category 1 before Category 2. This prevents the failure mode where agents cherry-pick the "easy" tests and run out of context before reaching later categories.

### Chunked Processing for Large Test Suites

If the spec defines more than 50 TC-* IDs:

1. **Inventory all IDs first** — extract the full list before writing any tests
2. **Process in chunks of 20-30** — write tests for a batch, commit, then proceed to the next batch
3. **Track progress** — maintain a running count in the test report:
   ```
   Progress: 34/153 TC-* IDs implemented (22%) — processing Part 2: Scope Tests
   ```
4. **Never stop early** — if context is running low, save progress and surface remaining IDs as `INCOMPLETE: N remaining`
5. **Resume protocol** — on re-entry, read the test report to determine where to continue

### Self-Check Before Completion

Before any test agent marks its task as complete, it MUST run this self-check:

```bash
# Count TC-* IDs this agent was responsible for (from spec)
RESPONSIBLE_IDS=$(grep -oP 'TC-[A-Z]+-\d+' spec_files | sort -u)
RESPONSIBLE_COUNT=$(echo "$RESPONSIBLE_IDS" | wc -l)

# Count TC-* IDs in test files this agent wrote
IMPLEMENTED_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' test_files | sort -u)
IMPLEMENTED_COUNT=$(echo "$IMPLEMENTED_IDS" | wc -l)

# Compare
MISSING=$(comm -23 <(echo "$RESPONSIBLE_IDS") <(echo "$IMPLEMENTED_IDS"))
if [ -n "$MISSING" ]; then
  echo "INCOMPLETE: $IMPLEMENTED_COUNT / $RESPONSIBLE_COUNT TC-* IDs implemented"
  echo "Missing: $MISSING"
  # DO NOT mark task as complete — continue writing tests
fi
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Correct Approach |
|-------------|---------|-----------------|
| Spec defines test cases without TC-* IDs | No way to track implementation | Every test case gets a unique TC-* ID |
| Test file covers TC-* ID but doesn't annotate | Reconciler can't detect coverage | Always include TC-* ID in comment or test name |
| Agent implements 30% of TC-* IDs and stops | Massive coverage gap | Process in order, track progress, never stop early |
| TC-* IDs reused across phases | Ambiguous ownership | Each TC-* ID belongs to exactly one phase |
| Gate passes with "most tests pass" | Missing tests never get written | Gate requires 100% coverage for HIGH+MEDIUM |
| Spec defines TC-* range but test skips IDs in the middle | Silent gaps | Reconciler detects per-ID, not per-range |
| Test annotates wrong TC-* ID | False coverage | Reconciler cross-checks description match |
