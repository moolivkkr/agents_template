---
skill: change-impact-analysis
description: Git-diff-based test selection — map changed files to the minimal set of tests/phases to re-run for per-phase regression
version: "1.0"
tags:
  - regression
  - test-selection
  - git
  - impact-analysis
  - core
---

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
# Files changed in this phase: since the commit it started from (base_sha, written at Wave 0c).
# No usable base means the scope is unknown → FULL regression (Safety Guarantee 4). Never guess:
# merge-base with main is HEAD itself on main (zero changes → "skip"), and HEAD~20 is not the phase.
BASE="$(cat "agent_state/phases/${PHASE:?}/base_sha" 2>/dev/null)"
if [ -n "$BASE" ] && CHANGED_FILES="$(git diff --name-only "$BASE" HEAD)"; then
  printf '%s\n' "$CHANGED_FILES" | sed '/^$/d' > /tmp/changed_files.txt
  CHANGED_COUNT=$(wc -l < /tmp/changed_files.txt | tr -d ' ')
  echo "Phase $PHASE changed $CHANGED_COUNT files since ${BASE}"
else
  echo "⚠ No usable base commit for Phase $PHASE — run the FULL regression (fallback_reason: no_base)"
  exit 1   # the caller runs everything; impact selection stops here
fi
```

### Step 2 — Map Files to Packages/Modules

```bash
# Extract unique packages/directories from changed files (one per line; "." for root files)
while IFS= read -r f; do dirname "$f"; done < /tmp/changed_files.txt | sort -u > /tmp/changed_packages.txt
CHANGED_PACKAGES=$(cat /tmp/changed_packages.txt)
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
# For Go projects: a package is affected when it changed or imports a changed package (test imports
# included). go list resolves the real import paths; grepping test files for "./internal/x" never
# matches a Go import (they are module paths), so dependents were silently left out.
MOD="$(go list -m)" || exit 1
go list -f '{{.ImportPath}} {{join .Imports " "}} {{join .TestImports " "}} {{join .XTestImports " "}}' ./... \
  > /tmp/go_imports.txt || exit 1
AFFECTED_GO_PKGS="$(awk -v mod="$MOD" '
  FILENAME == ARGV[1] { changed[($0 == ".") ? mod : mod "/" $0] = 1; next }
  { for (i = 1; i <= NF; i++) if ($i in changed) { print $1; next } }' /tmp/changed_packages.txt /tmp/go_imports.txt | sort -u)"
AFFECTED_COUNT=$(printf '%s\n' "$AFFECTED_GO_PKGS" | sed '/^$/d' | wc -l | tr -d ' ')
TOTAL_PKGS=$(wc -l < /tmp/go_imports.txt | tr -d ' ')
echo "Affected: $AFFECTED_COUNT / $TOTAL_PKGS packages ($(( TOTAL_PKGS > 0 ? AFFECTED_COUNT * 100 / TOTAL_PKGS : 0 ))%)"

# For TypeScript/React projects: let the runner walk the import graph. A grep for the directory name
# misses relative ("../x") and aliased ("@/x") imports.
#   npx vitest related --run $(cat /tmp/changed_files.txt)      # Jest: npx jest --findRelatedTests …
```

### Step 5 — Apply Selection or Fallback

```bash
SELECTION_THRESHOLD=80  # If > 80% affected, just run all (no savings)

if [ "$AFFECTED_COUNT" -eq 0 ]; then
  echo "No tests affected — skip regression (test-only or docs change)"
  REGRESSION_CMD="echo 'No regression needed'"

elif [ "$(( AFFECTED_COUNT * 100 / TOTAL_PKGS ))" -gt "$SELECTION_THRESHOLD" ]; then
  echo ">${SELECTION_THRESHOLD}% packages affected — running full regression"
  REGRESSION_CMD="$FULL_TEST_CMD"

else
  echo "Running targeted regression: $AFFECTED_COUNT packages"
  # For Go: exactly the affected packages (a trailing ./... would run every package again)
  REGRESSION_CMD="go test $(printf '%s\n' "$AFFECTED_GO_PKGS" | tr '\n' ' ')"
  # For TS: REGRESSION_CMD="npx vitest related --run $(tr '\n' ' ' < /tmp/changed_files.txt)"
fi
echo "regression: $REGRESSION_CMD"
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

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 4 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 2 run in fixture scenarios on macOS bash 3.2.57; 1 JSON block parsed.
