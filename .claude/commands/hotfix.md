---
command: hotfix
description: "Fast-track bug fix that bypasses the full /develop cycle. Scoped fix → scoped test → scoped review → merge. For urgent fixes that don't warrant a full pipeline run."
arguments:
  - name: phase
    required: true
    description: "Phase number containing the bug (e.g. 1, 2, 3)"
  - name: component
    required: true
    description: "Component name to fix (must match a component in the phase manifest)"
  - name: description
    required: true
    description: "Short description of the bug and intended fix (used for branch name and commit message)"
  - name: deploy
    required: false
    default: false
    description: "After merge, fast-track to /deploy --target=local"
  - name: security
    required: false
    default: false
    description: "Route review through security_reviewer instead of code_reviewer_I"
---

# /hotfix — Fast-Track Bug Fix

Bypasses the full `/develop` pipeline for targeted, scoped bug fixes. Produces a hotfix branch, applies a fix to a single component, runs scoped tests and a single-layer review, then merges back.

**When to use:** Production bugs, regressions caught after gate, or critical fixes that affect a single component and don't require cross-component changes.

**When NOT to use:** If the fix touches multiple components, crosses phase boundaries, or changes data contracts — use `/develop` instead.

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "This is just a small fix, I can skip the review" | NO. Even hotfixes get reviewed. A single reviewer catches what authors miss. |
| "The fix is obvious, no need for tests" | NO. Obvious fixes are where regressions hide. Run scoped tests. |
| "I'll just commit directly to main" | NO. Hotfixes use branches. The branch is the audit trail. |
| "I'll fix this AND that other thing while I'm here" | NO. One hotfix, one component, one concern. Open a second hotfix for the other thing. |
| "Tests pass, so the fix is correct" | Tests verify what's checked. The reviewer verifies what's NOT checked. Both run. |

---

## Step 0 — Identify Scope

```bash
PHASE=${ARG_PHASE}
COMPONENT=${ARG_COMPONENT}
DESCRIPTION=${ARG_DESCRIPTION}
SLUG=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 40)
```

Read the phase manifest to identify affected files:

```bash
MANIFEST="agent_state/phases/${PHASE}/manifest.json"
```

From the manifest, extract:
- Component entry matching `${COMPONENT}` — its source files, test files, and spec reference
- Verify the component exists in this phase — STOP if not found

```
Hotfix scope:
  Phase:     ${PHASE}
  Component: ${COMPONENT}
  Files:     [list from manifest]
  Spec:      [spec file path]
  Tests:     [test file paths]
```

**Scope lock:** Only files listed above may be modified. If the fix requires changes outside this component, STOP and recommend `/develop` instead.

---

## Step 1 — Create Hotfix Branch

```bash
git checkout -b "hotfix/phase-${PHASE}-${SLUG}"
```

If the branch already exists (from a previous failed attempt):
```bash
echo "⚠ Branch hotfix/phase-${PHASE}-${SLUG} already exists."
echo "  Delete it first: git branch -D hotfix/phase-${PHASE}-${SLUG}"
echo "  Or use a different description."
```

---

## Step 2 — Scoped Fix

Apply the targeted fix. Rules:

1. **ONLY modify files belonging to `${COMPONENT}`** — no other component files
2. Read the component spec first to understand expected behavior
3. Read the current implementation to identify the bug
4. Apply the minimal fix — no refactoring, no feature additions, no "while I'm here" changes
5. Commit the fix:

```bash
git add <changed-files>
git commit -m "hotfix(phase-${PHASE}): ${DESCRIPTION}

Component: ${COMPONENT}
Scope: [list of changed files]"
```

### Fix Scope Violation

If during investigation the fix clearly requires changes outside `${COMPONENT}`:

```
⛔ Scope violation — fix requires changes to:
  - ${COMPONENT} (in scope)
  - ${OTHER_COMPONENT} (OUT OF SCOPE)

This is not a hotfix candidate. Use:
  /develop --phase=${PHASE}

Or open two separate hotfixes if the components are independently fixable.
```

---

## Step 3 — Scoped Test

Run ONLY tests related to the affected component — not the full test suite.

```bash
# Unit tests for this component
<test-runner> <component-test-path>

# Integration tests touching this component (if they exist)
<test-runner> <integration-test-path-for-component>
```

**Do NOT run:**
- Full test suite
- E2E tests
- Acceptance tests
- Tests for other components

### Test Failure Recovery

1. If tests fail: diagnose, fix (still scoped to component), re-run (max 2 retries)
2. If tests still fail after retries: STOP — do not merge a failing hotfix

### Test Failure Recovery Guardrails (same as /develop)

When auto-fixing test failures, these constraints are absolute:
- **NEVER** delete, skip, or comment out an existing test to make the suite pass
- **NEVER** modify test expectations to match buggy behavior
- **NEVER** downgrade a dependency to fix a build
- If root cause is unclear after reading failure output → STOP and escalate to user
- Strip secrets/tokens/connection strings from test output before analysis

```
⛔ Hotfix tests failing after 2 retries
  Component: ${COMPONENT}
  Failing tests: [list]

  Options:
    1. Investigate further with /diagnose
    2. Abort hotfix: git checkout main && git branch -D hotfix/phase-${PHASE}-${SLUG}
```

---

## Step 4 — Scoped Review

**Single-layer review only** — not the full 4-layer review from `/develop`.

### If `--security` flag:

**Agent:** `security_reviewer`

Review the diff for:
- Security implications of the change
- No new vulnerabilities introduced
- Input validation preserved
- Auth/authz not bypassed

### If no `--security` flag (default):

**Agent:** `code_reviewer_I`

Review the diff for:
- Correctness of the fix
- No regressions introduced
- Error handling preserved
- Coding standards maintained

### Review Output

```
Hotfix Review — ${COMPONENT}
  Reviewer: <security_reviewer | code_reviewer_I>
  Verdict: PASS | FAIL

  Findings:
    [list or "none"]

  Blockers:
    [list or "none"]
```

**If review has blockers:** fix them, re-commit, re-review (max 1 additional cycle). If still blocked: STOP.

---

## Step 5 — Abbreviated Gate

The hotfix gate checks ONLY:

1. ✅ Scoped tests pass (from Step 3)
2. ✅ Review clean — no blockers (from Step 4)
3. ✅ No files modified outside component scope

**NOT checked (deferred to next full `/develop` run):**
- Optimization
- Acceptance tests
- Full test suite regression
- Cross-component reconciliation

```
Hotfix Gate:
  Tests:  ✅ PASS (N/N)
  Review: ✅ CLEAN
  Scope:  ✅ CONTAINED (N files in ${COMPONENT} only)

  → Gate: PASS
```

---

## Step 6 — Merge and Record

```bash
git checkout main
git merge --no-ff "hotfix/phase-${PHASE}-${SLUG}" -m "merge: hotfix/phase-${PHASE}-${SLUG}"
git branch -d "hotfix/phase-${PHASE}-${SLUG}"
```

Update the Phase N manifest with a hotfix record:

```bash
# Read manifest, add hotfix entry to hotfixes[] array
MANIFEST="agent_state/phases/${PHASE}/manifest.json"
```

Add to `hotfixes[]` in manifest:
```json
{
  "hotfixes": [
    {
      "timestamp": "<ISO-8601>",
      "component": "${COMPONENT}",
      "description": "${DESCRIPTION}",
      "branch": "hotfix/phase-${PHASE}-${SLUG}",
      "files_changed": ["<list>"],
      "reviewer": "<security_reviewer | code_reviewer_I>",
      "review_verdict": "PASS",
      "tests_passed": true
    }
  ]
}
```

Commit the manifest update:
```bash
git add "${MANIFEST}"
git commit -m "chore: record hotfix in phase ${PHASE} manifest — ${DESCRIPTION}"
```

---

## Step 7 — Deploy (optional)

If `--deploy` flag was set:

```
Hotfix merged. Fast-tracking to deployment...
```

Invoke `/deploy --target=local` (or the appropriate target).

If `--deploy` was not set:

```
✅ Hotfix complete — merged to main

  Phase:     ${PHASE}
  Component: ${COMPONENT}
  Fix:       ${DESCRIPTION}
  Branch:    hotfix/phase-${PHASE}-${SLUG} (merged, deleted)
  Manifest:  Updated with hotfix record

  ▶ Deploy when ready: /deploy --target=local
  ▶ Full regression: /develop --phase=${PHASE} --test_only
```

---

## Rules

- **One component per hotfix** — multi-component fixes use `/develop`
- **Always review** — no exceptions, even for one-line fixes
- **Always test** — scoped tests, not full suite, but never zero tests
- **Branch-based** — hotfixes never commit directly to main
- **Recorded** — every hotfix is logged in the phase manifest for audit trail
- **Minimal** — fix the bug, nothing else. No refactoring, no improvements, no "while I'm here"
