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

Bypasses full `/develop` for targeted, scoped bug fixes. Hotfix branch → fix single component → scoped tests → single-layer review → merge.

**Use when:** Production bugs, post-gate regressions, single-component critical fixes.
**NOT for:** Multi-component fixes, cross-phase changes, data contract changes → use `/develop`.

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "Small fix, skip the review" | Even hotfixes get reviewed. |
| "Obvious fix, no need for tests" | Obvious fixes hide regressions. Run scoped tests. |
| "I'll commit directly to main" | Hotfixes use branches — the audit trail. |
| "I'll fix this AND that other thing" | One hotfix, one component. Open a second for the other. |

---

## Step 0 — Identify Scope

```bash
PHASE=${ARG_PHASE}
COMPONENT=${ARG_COMPONENT}
SLUG=$(echo "$ARG_DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 40)
MANIFEST="agent_state/phases/${PHASE}/manifest.json"
```

Extract component's source files, test files, spec reference from manifest. Verify component exists — STOP if not.

**Scope lock:** Only listed files may be modified. Fix requires changes outside component → STOP, recommend `/develop`.

---

## Step 1 — Create Hotfix Branch

```bash
git checkout -b "hotfix/phase-${PHASE}-${SLUG}"
```

---

## Step 2 — Scoped Fix

1. ONLY modify files belonging to `${COMPONENT}`
2. Read component spec for expected behavior
3. Read implementation to identify bug
4. Apply minimal fix — no refactoring, no feature additions
5. Commit:
```bash
git add <changed-files>
git commit -m "hotfix(phase-${PHASE}): ${DESCRIPTION}

Component: ${COMPONENT}
Scope: [changed files]"
```

**Scope violation** → STOP with recommendation for `/develop` or two separate hotfixes.

---

## Step 3 — Scoped Test

Run ONLY component tests (unit + integration). Do NOT run full suite, e2e, acceptance, or other component tests.

**Failure:** diagnose → fix (scoped) → re-run (max 2 retries). Still failing → STOP, do not merge.

---

## Step 4 — Scoped Review

**Single-layer review only** (not full 4-layer from `/develop`).

- `--security` flag → `security_reviewer` (security implications, vuln check, auth/authz)
- Default → `code_reviewer_I` (correctness, regressions, error handling, standards)

**Blockers:** fix → re-commit → re-review (max 1 cycle). Still blocked → STOP.

---

## Step 5 — Abbreviated Gate

Checks ONLY: 1) Scoped tests pass 2) Review clean 3) No files outside component scope.
**NOT checked** (deferred): optimization, acceptance, full suite, cross-component reconciliation.

---

## Step 6 — Merge and Record

```bash
git checkout main
git merge --no-ff "hotfix/phase-${PHASE}-${SLUG}" -m "merge: hotfix/phase-${PHASE}-${SLUG}"
git branch -d "hotfix/phase-${PHASE}-${SLUG}"
```

Add hotfix record to manifest `hotfixes[]`:
```json
{ "timestamp": "<ISO>", "component": "${COMPONENT}", "description": "${DESCRIPTION}", "branch": "hotfix/phase-${PHASE}-${SLUG}", "files_changed": ["..."], "reviewer": "<agent>", "review_verdict": "PASS", "tests_passed": true }
```

Commit manifest update.

---

## Step 7 — Deploy (optional)

`--deploy` → invoke `/deploy --target=local`. Otherwise print summary with next steps.

---

## Rules

- **One component per hotfix** — multi-component → `/develop`
- **Always review** — no exceptions, even one-line fixes
- **Always test** — scoped, never zero
- **Branch-based** — never commit directly to main
- **Recorded** — every hotfix logged in phase manifest
- **Minimal** — fix the bug, nothing else
