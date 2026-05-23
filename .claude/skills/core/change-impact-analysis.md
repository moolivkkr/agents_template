# Change-Impact Test Selection Protocol

Per-phase regression currently runs ALL tests across ALL phases before writing gate.passed.
For a 10-phase project with 1000+ tests, this wastes time when Phase 8 only changed 3 files.

This protocol determines which tests are **affected by the current phase's changes** and runs
only those for the per-phase gate. Full regression still runs at `/accept` (global acceptance).

---

## When to Use

| Context | Strategy |
|---|---|
| `/develop` Wave 6 (gate regression) | Change-impact selection (this protocol) |
| `/accept` Step 0b (global regression) | Full regression (ALL tests, ALL phases) |
| Wave 5 (fix iteration) | Adaptive replan scope (see `adaptive-replan.md`) |

## Algorithm

### Step 1 — Identify Changed Files

```bash
# Files changed in this phase (since phase branch or last gate)
LAST_GATE_SHA=$(git log --format=%H -1 -- agent_state/phases/$((PHASE-1))/gate.passed 2>/dev/null)
if [ -z "$LAST_GATE_SHA" ]; then
  LAST_GATE_SHA=$(git merge-base HEAD main 2>/dev/null || echo "HEAD~20")
fi

CHANGED_FILES=$(git diff --name-only "$LAST_GATE_SHA" HEAD)
echo "$CHANGED_FILES" > /tmp/changed_files.txt
CHANGED_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
echo "Phase $PHASE changed $CHANGED_COUNT files"
```

### Step 2 — Map Files to Packages/Modules

```bash
# Extract unique packages/directories from changed files
CHANGED_PACKAGES=$(echo "$CHANGED_FILES" | xargs -I{} dirname {} | sort -u)
echo "$CHANGED_PACKAGES" > /tmp/changed_packages.txt
```

### Step 3 — Classify Change Scope

| Changed Files Pattern | Scope | Regression Strategy |
|---|---|---|
| Only `*_test.go`, `*.test.ts`, `*.spec.ts` | Test-only change | Run changed tests only |
| Only files in ONE package/directory | Single package | Run that package's tests + direct dependents |
| Files across 2-3 packages | Multi-package | Run affected packages + shared dependency tests |
| Files in shared/common/utils/middleware | Shared layer | Run ALL tests (shared changes affect everything) |
| Migration files, schema changes | Schema change | Run ALL tests |
| Config files (docker-compose, .env, CI) | Infrastructure | Run integration + E2E + acceptance |
| > 50% of source files changed | Broad change | Run ALL tests (optimization not worth it) |

### Step 4 — Determine Affected Tests

```bash
# For Go projects:
# Find test files in changed packages
AFFECTED_TESTS=""
for PKG in $(cat /tmp/changed_packages.txt); do
  # Direct tests in the changed package
  TESTS=$(find "$PKG" -name '*_test.go' 2>/dev/null)
  AFFECTED_TESTS="$AFFECTED_TESTS $TESTS"

  # Tests that import the changed package (direct dependents)
  PKG_IMPORT=$(echo "$PKG" | sed 's|^|./|')
  DEPENDENT_TESTS=$(grep -rl "$PKG_IMPORT" --include='*_test.go' . 2>/dev/null)
  AFFECTED_TESTS="$AFFECTED_TESTS $DEPENDENT_TESTS"
done

# For TypeScript/React projects:
# Find test files that import from changed directories
for DIR in $(cat /tmp/changed_packages.txt); do
  TESTS=$(grep -rl "from.*['\"].*${DIR}" --include='*.test.*' --include='*.spec.*' . 2>/dev/null)
  AFFECTED_TESTS="$AFFECTED_TESTS $TESTS"
done

AFFECTED_COUNT=$(echo "$AFFECTED_TESTS" | tr ' ' '\n' | sort -u | wc -l | tr -d ' ')
TOTAL_TESTS=$(find . -name '*_test.go' -o -name '*.test.*' -o -name '*.spec.*' 2>/dev/null | wc -l | tr -d ' ')
echo "Affected: $AFFECTED_COUNT / $TOTAL_TESTS tests ($(( AFFECTED_COUNT * 100 / TOTAL_TESTS ))%)"
```

### Step 5 — Apply Selection or Fallback

```bash
SELECTION_THRESHOLD=80  # If > 80% affected, just run all (no savings)

if [ "$AFFECTED_COUNT" -eq 0 ]; then
  echo "No tests affected — skip regression (test-only or docs change)"
  REGRESSION_CMD="echo 'No regression needed'"

elif [ "$(( AFFECTED_COUNT * 100 / TOTAL_TESTS ))" -gt "$SELECTION_THRESHOLD" ]; then
  echo ">${SELECTION_THRESHOLD}% tests affected — running full regression"
  REGRESSION_CMD="$FULL_TEST_CMD"

else
  echo "Running targeted regression: $AFFECTED_COUNT tests"
  # For Go: run specific packages
  REGRESSION_CMD="go test $(echo "$CHANGED_PACKAGES" | sed 's|^|./|' | tr '\n' ' ') ./..."
  # For TS: run with path filter
  # REGRESSION_CMD="npx vitest run $(echo "$AFFECTED_TESTS" | tr ' ' '\n' | sort -u | tr '\n' ' ')"
fi
```

## Safety Guarantees

1. **Always run current phase's tests:** All tests written in this phase run regardless of impact analysis
2. **Always run E2E:** E2E tests exercise full workflows — they catch integration issues that unit-level impact analysis misses
3. **Shared layer = full regression:** Changes to auth, middleware, config, or DB schema trigger full regression
4. **Fallback to full:** If impact analysis can't determine scope (new test framework, monorepo restructure), run everything
5. **`/accept` always runs full:** This is the FINAL gate — no shortcuts

## Output Format

Log the selection decision in the gate checkpoint:

```json
{
  "regression_strategy": "change-impact | full | skip",
  "changed_files": 12,
  "changed_packages": 3,
  "affected_tests": 45,
  "total_tests": 380,
  "selection_pct": 12,
  "shared_layer_changed": false,
  "fallback_reason": null
}
```

## When NOT to Use

- First phase (Phase 1): no previous tests exist — run everything you've got
- After a forced gate: trust is low — run full regression
- After `--reset-phase`: clean slate — run full regression
- During `/accept`: always full regression (global acceptance)
