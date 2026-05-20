---
command: optimize
description: "Standalone code optimization — dead code removal, code reduction, performance improvements. Runs tests + review before AND after, shows comparison. Works on backend + UI in parallel."
arguments:
  - name: phase
    required: false
    description: "Target phase (default: auto-detect latest completed phase). Scopes optimization to files changed in that phase."
  - name: backend_only
    required: false
    default: false
    description: "Optimize backend code only — skip UI"
  - name: ui_only
    required: false
    default: false
    description: "Optimize UI code only — skip backend"
  - name: dry_run
    required: false
    default: false
    description: "Report what WOULD be optimized without making changes"
  - name: aggressive
    required: false
    default: false
    description: "Include MEDIUM-confidence dead code removal and suggested optimizations (default: only CERTAIN/HIGH)"
---

# /optimize — Standalone Code Optimization

Clean code, no dead code, optimized code, effective code. Runs the full optimization pipeline outside of `/develop` — with before/after comparison of tests, review findings, and code metrics.

**Can run at any time** — not limited to phase boundaries. Use after a hotfix, after manual refactoring, or periodically for codebase hygiene.

---

## How it works

```
Step 0  Scope & Snapshot      Determine files, tag pre-optimize state
Step 1  BEFORE baseline       Run tests + review + capture metrics
Step 2  Optimize              Dead code removal + code optimization (backend ∥ UI)
Step 3  AFTER measurement     Re-run tests + review + capture metrics
Step 4  Compare               Show before/after delta — tests, review findings, metrics
Step 5  Verdict               CLEAN / PARTIAL / REVERTED + commit or rollback
```

---

## Step 0 — Scope & Snapshot

### Determine scope
```bash
if [ -n "$ARG_PHASE" ]; then
  PHASE=$ARG_PHASE
  SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..agent_state/phases/${PHASE}/gate.passed 2>/dev/null)
else
  # Auto-detect: latest completed phase, or all tracked files if no phases
  LAST_PHASE=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
  if [ -n "$LAST_PHASE" ]; then
    PHASE=$LAST_PHASE
    SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null)
  else
    SCOPE_FILES=$(git ls-files 'src/' 'internal/' 'pkg/' 'web/src/' 'tests/')
  fi
fi

# Split into backend and UI scope
BACKEND_FILES=$(echo "$SCOPE_FILES" | grep -E '^(src/|internal/|pkg/|tests/)' | grep -v '^(src/ui/|web/)')
UI_FILES=$(echo "$SCOPE_FILES" | grep -E '^(web/src/|src/ui/|src/components/|src/hooks/|src/pages/)')

echo "Scope: Phase ${PHASE:-all}"
echo "  Backend files: $(echo "$BACKEND_FILES" | wc -l | tr -d ' ')"
echo "  UI files: $(echo "$UI_FILES" | wc -l | tr -d ' ')"
```

### Pre-optimization snapshot
```bash
git tag "optimize-before-$(date +%Y%m%d-%H%M%S)" HEAD
PRE_TAG=$(git describe --tags --abbrev=0)
```

### Load context
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, test commands
- `agent_state/agent_registry.json` — active skill packs
- `docs/design/phases/${PHASE}/specs/api-contracts.md` — for UI data-fetching safety check

---

## Step 1 — BEFORE Baseline

Capture the current state **before** any optimization. This is the baseline for comparison.

### 1a — Run full test suite
```bash
# Backend tests
${BACKEND_TEST_CMD}  # from IMPLEMENTATION_GUIDELINES (e.g., go test ./... -count=1)
# UI tests (if not --backend_only)
${UI_TEST_CMD}       # from IMPLEMENTATION_GUIDELINES (e.g., cd web && npm test)
```

Capture results:
```yaml
before:
  tests:
    backend_unit: { total: N, passed: N, failed: N }
    backend_integration: { total: N, passed: N, failed: N }
    ui_component: { total: N, passed: N, failed: N }
    ui_e2e: { total: N, passed: N, failed: N }
```

### 1b — Run code review (style pass only — quick)
**Agent:** `code_reviewer_I` (style/idioms only — skip architecture and security for speed)

Capture findings count:
```yaml
before:
  review:
    dead_code_findings: N
    complexity_findings: N
    style_findings: N
    total_findings: N
```

### 1c — Capture code metrics
```bash
# Lines of code
BEFORE_BACKEND_LINES=$(find ${BACKEND_DIRS} -name "*.${EXT}" | xargs wc -l | tail -1)
BEFORE_UI_LINES=$(find ${UI_DIRS} -name "*.${UI_EXT}" | xargs wc -l | tail -1)

# Function count
BEFORE_FUNCTIONS=$(grep -r "${FUNC_PATTERN}" ${BACKEND_DIRS} | wc -l)
BEFORE_COMPONENTS=$(grep -r "export.*function\|export default" ${UI_DIRS} | wc -l)

# Test coverage
BEFORE_COVERAGE=$(${COVERAGE_CMD})

# Bundle size (UI only)
BEFORE_BUNDLE=$(${BUILD_CMD} 2>&1 | grep -E 'size|chunk|bundle' || du -sh ${BUILD_DIR})
```

Write baseline: `agent_state/optimize/before.yaml`

Print:
```
📊 BEFORE baseline captured
   Backend: X lines, Y functions, Z% coverage
   UI: X lines, Y components, Z KB bundle
   Review: N dead code findings, N complexity findings
   Tests: all passing (X backend + Y UI)
```

---

## Step 2 — Optimize + Test + Fix Loop

Optimization runs as an iterative loop: **optimize → test → if broken, diagnose and fix → re-test → only revert as last resort.** This is more effective than blind revert because most optimization-induced failures have simple fixes (missing import, updated caller, adjusted type).

### Dry run mode
If `--dry_run`: both agents report what they WOULD change but make zero modifications. Skip to Step 4 with projected metrics.

### 2a — Backend Optimization (parallel with 2b)
**Agent:** `code_optimizer`
**Skip if:** `--ui_only` flag
**Scope:** `$BACKEND_FILES` only

### 2b — UI Optimization (parallel with 2a)
**Agent:** `ui_code_optimizer`
**Skip if:** `--backend_only` flag or `frontend.enabled = false`
**Scope:** `$UI_FILES` only

### Per-optimization iteration cycle

Each optimization (dead code removal or code change) follows this cycle:

```
FOR each optimization candidate:
  1. APPLY      → make the change, commit with descriptive message
  2. TEST       → run relevant test suite (unit for backend, component for UI)
  3. If PASS    → move to next optimization ✅
  4. If FAIL    → enter fix cycle ↓

  FIX CYCLE (max 3 attempts):
    Attempt 1: DIAGNOSE → FIX → RE-TEST
      - Read the test failure output
      - Identify root cause (missing import? caller not updated? type mismatch?)
      - Apply targeted fix → commit as "fix: resolve <issue> after <optimization>"
      - Re-run the failing test
      - If PASS → continue to next optimization ✅

    Attempt 2: BROADER FIX → RE-TEST
      - If attempt 1 fix didn't work, look at broader impact
      - Check all callers/consumers of the changed code
      - Fix all affected call sites → commit
      - Re-run full test suite (not just failing test)
      - If PASS → continue ✅

    Attempt 3: ALTERNATIVE APPROACH → RE-TEST
      - Revert the original optimization commit AND fix attempts
      - Try a different optimization approach for the same candidate
      - If no alternative exists → skip this candidate, log as "skipped"
      - Re-run tests to confirm clean state
      - If PASS → continue ✅

    If ALL 3 ATTEMPTS FAIL:
      - Revert all commits related to this optimization (original + fix attempts)
      - Log in report: "Optimization X skipped — could not resolve test failure after 3 fix attempts"
      - Continue to next optimization candidate (don't stop the pipeline)
```

### What the fix cycle handles

| Failure Type | Typical Fix | Example |
|-------------|------------|---------|
| Missing import | Add the import back or redirect to new location | Removed unused file that was imported transitively |
| Broken caller | Update the caller to use new function signature | Extracted shared function with different params |
| Type mismatch | Adjust type annotation or cast | Simplified return type doesn't match interface |
| Missing nil check | Add nil guard at call site | Removed defensive code that a caller depended on |
| Test assertion wrong | Update test to match new (correct) behavior | Dead code removal changed error message |
| Broken re-export | Update the barrel export or direct import | Removed file that was re-exported from index |
| CSS/styling change | Restore specific class or adjust new utility | Removed "unused" class that was applied dynamically |
| API shape change | Verify against api-contracts.md, restore if needed | Optimization accidentally changed response field |

### What triggers immediate revert (no fix attempt)

These failures indicate the optimization was fundamentally wrong — fixing would mean reimplementing what was removed:

- **Test coverage drops below threshold** — means removed code was actually tested and needed
- **API contract violation** — optimization changed a response shape that `api-contracts.md` defines
- **Compilation/build fails across multiple files** — change has cascading impact too broad to fix
- **Security test fails** — optimization weakened a security control

---

## Step 3 — AFTER Measurement

### 3a — Re-run FULL test suite
Run the complete test suite (same as Step 1a) across everything — not just tests near optimized code. This catches distant regressions the per-optimization tests might miss.

If failures found at this stage:
1. Identify which optimization commit caused it (check git log since pre-tag)
2. Enter the same fix cycle as Step 2 (diagnose → fix → re-test, max 3 attempts)
3. If unfixable: revert that specific optimization + its fix attempts
4. Re-run full suite to confirm clean
5. Max 5 total reverts at this stage → if exceeded, pause and surface to user:
   ```
   ⚠ 5+ optimizations causing cross-cutting failures.
   Recommend: revert all to pre-optimize tag and run with --dry_run to assess scope.
   Continue? [y/n]
   ```

### 3b — Re-run code review (style pass)
Same `code_reviewer_I` as Step 1b. Capture new findings count.

### 3c — Capture code metrics (same measurements as Step 1c)

Write results: `agent_state/optimize/after.yaml`

---

## Step 4 — Compare (Before vs After)

Read `before.yaml` and `after.yaml`. Compute deltas.

```
╔══════════════════════════════════════════════════════════════════╗
║                    OPTIMIZATION RESULTS                         ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CODE METRICS                Before      After       Delta       ║
║  ─────────────────────────────────────────────────────────────── ║
║  Backend lines               4,230       3,980       -250 ✅     ║
║  Backend functions           186         178         -8   ✅     ║
║  UI lines                    3,100       2,850       -250 ✅     ║
║  UI components               28          25          -3   ✅     ║
║  Bundle size                 420 KB      395 KB      -25 KB ✅   ║
║                                                                  ║
║  TEST RESULTS                Before      After       Delta       ║
║  ─────────────────────────────────────────────────────────────── ║
║  Backend unit tests          124/124     124/124     0    ✅     ║
║  Backend integration         48/48       48/48       0    ✅     ║
║  UI component tests          36/36       36/36       0    ✅     ║
║  Test coverage               82%         84%         +2%  ✅     ║
║                                                                  ║
║  REVIEW FINDINGS             Before      After       Delta       ║
║  ─────────────────────────────────────────────────────────────── ║
║  Dead code findings          12          0           -12  ✅     ║
║  Complexity findings         5           3           -2   ✅     ║
║  Style findings              8           6           -2   ✅     ║
║  Total review findings       25          9           -16  ✅     ║
║                                                                  ║
║  OPTIMIZATION ACTIONS                                            ║
║  ─────────────────────────────────────────────────────────────── ║
║  Dead code removed           15 items                            ║
║  Code optimizations applied  8 items                             ║
║  Optimizations reverted      0                                   ║
║  Items flagged for review    3                                   ║
║                                                                  ║
║  VERDICT: CLEAN ✅                                               ║
║  All tests pass. Zero regressions. 500 lines removed.            ║
╚══════════════════════════════════════════════════════════════════╝
```

**Delta indicators:**
- ✅ = improved or unchanged (lines decreased, coverage increased, findings decreased, tests stable)
- ⚠ = unchanged (no improvement but no regression)
- ❌ = regressed (tests failed, coverage dropped, lines increased)

---

## Step 5 — Verdict & Commit

### CLEAN (all ✅)
All tests pass, no regressions, metrics improved or stable.
```
✅ Optimization complete — CLEAN
   Lines removed: 500 (backend: 250, UI: 250)
   Dead code eliminated: 15 items
   Review findings reduced: 25 → 9
   Bundle size: -25 KB
   All N tests still passing
   Commits: 23 (one per optimization — individually revertible)
```

### PARTIAL (some optimizations reverted)
Some optimizations caused test failures and were reverted. Remaining optimizations kept.
```
⚠ Optimization complete — PARTIAL
   Applied: 18 optimizations
   Reverted: 5 optimizations (caused test regressions)
   See agent_state/optimize/reverted.md for details
```

### REVERTED (all rolled back)
All optimizations caused cascading failures. Full rollback to pre-tag.
```
❌ Optimization rolled back — all changes reverted
   Pre-optimization tag: ${PRE_TAG}
   Reason: N test failures after optimization, unrecoverable after 3 revert cycles
   No code changes persisted
```

### PROJECTED (dry run only)
```
📋 Dry run — projected optimization impact:
   Dead code candidates: 15 (CERTAIN: 8, HIGH: 5, MEDIUM: 2)
   Optimization opportunities: 12
   Estimated lines removable: ~400-600
   Run without --dry_run to apply
```

---

## Output Files

| File | Contents |
|------|----------|
| `agent_state/optimize/before.yaml` | Pre-optimization metrics (tests, review, code metrics) |
| `agent_state/optimize/after.yaml` | Post-optimization metrics |
| `agent_state/optimize/comparison.md` | Side-by-side comparison table |
| `agent_state/optimize/backend_report.md` | Backend optimization details (from `code_optimizer`) |
| `agent_state/optimize/ui_report.md` | UI optimization details (from `ui_code_optimizer`) |
| `agent_state/optimize/reverted.md` | Reverted optimizations with reasons (if any) |

---

## Safety Guarantees

1. **Pre-optimize git tag** — full rollback always possible
2. **One commit per change** — granular revert without losing other optimizations
3. **Full test suite before AND after** — no silent regressions
4. **Code review before AND after** — proves review findings decreased
5. **Auto-revert on test failure** — max 3 cycles, then full rollback
6. **Dry run mode** — see projected impact before committing to changes
7. **API contract integrity** — UI optimizer cross-checks data-fetching code against `api-contracts.md`
8. **Scope lock** — only touches files in the specified phase (or detected scope)

---

## Examples

```bash
# Optimize everything in the latest completed phase
/startup/optimize

# Optimize only backend code in Phase 2
/startup/optimize --phase=2 --backend_only

# See what WOULD be optimized without making changes
/startup/optimize --dry_run

# Include medium-confidence removals (more aggressive)
/startup/optimize --aggressive

# Optimize only UI code
/startup/optimize --ui_only
```
