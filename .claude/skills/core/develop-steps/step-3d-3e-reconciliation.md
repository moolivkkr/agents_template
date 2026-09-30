<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 3d + 3e — Reconciliation (SEQUENTIAL — 3d before 3e)

Run reconciliation agents **sequentially** — `spec_test_reconciler` depends on `spec_impl_reconciler` output to distinguish "untested" from "unimplemented".

```
Step 3d (first):
  └─ spec_impl_reconciler  → specs ↔ implementation (4-level verification)
       ↓ writes: agent_state/reconciliation/phase-N/specs_vs_impl.md
       ↓ output includes list of MISSING implementations

Step 3e (after 3d completes):
  └─ spec_test_reconciler  → specs ↔ test coverage
       ↓ reads: specs_vs_impl.md to EXCLUDE unimplemented behaviors from "untested" count
       ↓ a behavior can't be untested if it's not implemented yet — that's a MISSING impl, not a test gap
```

**Why sequential:** If `spec_test_reconciler` runs in parallel with `spec_impl_reconciler`, it will flag "no test for behavior X" when behavior X isn't even implemented yet. This creates confusion about whether the gap is a test gap or an implementation gap. Running 3d first gives 3e the context to make accurate assessments.

### 3d: Specs ↔ Implementation (`spec_impl_reconciler`)

Validates both directions with 4-level verification (Existence → Substantiveness → Wiring → Data Flow):
- **Forward:** spec-defined behaviors missing from the implementation
- **Reverse:** unspecced implementation (behaviors added without spec justification)

Output: `agent_state/reconciliation/phase-N/specs_vs_impl.md`

Missing implementations = **BLOCKER** (fix before acceptance tests).
Unspecced implementations = **LOGGED** with count in gate report. Not auto-blocking, but:
- If unspecced count > 0: gate report surfaces them with: `⚠ N unspecced implementations found — review before next phase`
- Each unspecced item is classified: `technical_necessity` (e.g., error handler), `scope_creep` (feature not in spec), or `test_helper`
- `scope_creep` items surfaced to user with recommendation: add to BRD or remove
- Manifest `carried_forward[]` includes unresolved unspecced items for next phase audit

### 3e: Specs ↔ Tests (`spec_test_reconciler`)

Validates both directions:
- **Forward:** spec-defined edge cases and behaviors with no test coverage
- **Reverse:** tests that test behaviors not in any spec

**TC-* ID Inventory Reconciliation (runs FIRST within this step):**
If specs contain TC-* IDs (pattern `TC-[A-Z0-9]+-\d+`):
1. Extract all TC-* IDs from `docs/design/phases/${PHASE}/specs/` (the spec inventory)
2. Extract all TC-* IDs from test files (the implementation inventory)
3. Compute: missing, orphaned, covered, coverage percentage
4. Per-category breakdown
5. Write `agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md`
6. **GATE DECISION:** missing HIGH or MEDIUM TC-* IDs = HARD BLOCK

```bash
# Quick TC-* inventory check (runs before behavior-level reconciliation)
SPEC_DIR="docs/design/phases/${PHASE}/specs"
SPEC_IDS=$(grep -rhoP 'TC-[A-Z0-9]+-\d+' "$SPEC_DIR" 2>/dev/null | sort -u)
SPEC_COUNT=$(echo "$SPEC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

if [ "$SPEC_COUNT" -gt 0 ]; then
  IMPL_IDS=$(grep -rhoP 'TC-[A-Z0-9]+-\d+' tests/ src/ test/ e2e/ apps/ mobile/ 2>/dev/null \
    --include="*_test.*" --include="*.test.*" --include="*.spec.*" --include="*.yaml" --include="*.yml" --exclude-dir=node_modules --exclude-dir=Pods --exclude-dir=build | sort -u)
  IMPL_COUNT=$(echo "$IMPL_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)
  MISSING_COUNT=$(comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS") | grep -c 'TC-' 2>/dev/null || echo 0)
  COVERAGE_PCT=$(( IMPL_COUNT * 100 / SPEC_COUNT ))

  echo "TC-* Inventory: ${IMPL_COUNT}/${SPEC_COUNT} implemented (${COVERAGE_PCT}%)"
  if [ "$MISSING_COUNT" -gt 0 ]; then
    echo "  MISSING: $MISSING_COUNT TC-* IDs not implemented"
    comm -23 <(echo "$SPEC_IDS") <(echo "$IMPL_IDS") | head -20
    echo "  Route to Wave 5 feedback loop for remediation"
  fi
fi
```

Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md` + `agent_state/reconciliation/phase-N/test_case_inventory.md`

HIGH-priority untested behaviors = blocker.
Missing HIGH/MEDIUM TC-* IDs = blocker.
MEDIUM/LOW behavior gaps = logged as known gaps.

---
