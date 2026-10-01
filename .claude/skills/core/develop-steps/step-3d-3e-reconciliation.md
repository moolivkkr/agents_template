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
# Deterministic TC inventory — names of tests that ran and passed, not grep (board review TEST-02):
# The weakening check needs the commit the phase started from. tc-inventory skips it on an empty
# --diff-base, and a HEAD~20 guess is not the phase, so no base_sha = BLOCKED.
BASE="$(cat "agent_state/phases/${PHASE:?}/base_sha" 2>/dev/null)"
[ -n "$BASE" ] || { echo "⛔ BLOCKED: no agent_state/phases/${PHASE}/base_sha (written at Wave 0c)"; exit 1; }
python3 .claude/hooks/tc-inventory.py --phase "${PHASE}" \
  --results "agent_state/phases/${PHASE}/reports/test_results.json" \
  --diff-base "$BASE" \
  --out "agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.json"
# exit 1 = a HIGH/MEDIUM ID is missing/failing, an ID is defined by two phases, a range annotation,
# or unacknowledged test weakening — each listed in the JSON. The gate reads this file.
```

Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md` + `agent_state/reconciliation/phase-N/test_case_inventory.md`

HIGH-priority untested behaviors = blocker.
Missing HIGH/MEDIUM TC-* IDs = blocker.
MEDIUM/LOW behavior gaps = logged as known gaps.

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 run in fixture scenarios on macOS bash 3.2.57 (1 also on Linux bash 5.2.37 with GNU tools).
