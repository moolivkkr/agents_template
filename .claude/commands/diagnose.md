---
command: diagnose
description: "Structured bug investigation. Traces a symptom to root cause through spec → implementation comparison. Optionally auto-fixes."
arguments:
  - name: symptom
    required: true
    description: "Description of the observed bug or unexpected behavior (e.g. 'GET /api/users returns 500', 'login form submits but redirects to 404')"
  - name: phase
    required: false
    description: "Phase number to scope investigation. Omit to auto-detect from symptom."
  - name: component
    required: false
    description: "Component name to scope investigation. Omit to auto-detect from symptom."
  - name: fix
    required: false
    default: false
    description: "After diagnosis, automatically apply the recommended fix using the appropriate implementation agent, then run scoped tests."
---

# /diagnose — Structured Bug Investigation

Traces a symptom to root cause by comparing spec (expected) against implementation (actual). Produces diagnosis report with root cause, affected components, and recommended fix.

**Use when:** You know WHAT is wrong but not WHY. `/diagnose` finds the why. `/hotfix` fixes it.

---

## Step 0 — Parse Symptom and Identify Scope

```bash
SYMPTOM="${ARG_SYMPTOM}"
PHASE="${ARG_PHASE}"
COMPONENT="${ARG_COMPONENT}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
```

Parse symptom → extract route/endpoint, error type, affected entity.

Auto-detect phase: search all manifests for component owning the route/feature. Auto-detect component: match against `api_routes[]`, `source_files[]`, spec descriptions. Ambiguous → ask user.

---

## Step 1 — Read Phase Manifest

From `agent_state/phases/${PHASE}/manifest.json`, extract: component source/test files, routes, related components, data contracts, BRD requirements.

---

## Step 2 — Read Spec (Expected Behavior)

From `docs/design/phases/${PHASE}/specs/`, extract: expected behavior for affected route, input validation rules, response shape, error handling, edge cases, data contract.

---

## Step 3 — Read Implementation (Actual Behavior)

Read source files. Trace request flow: route registration → handler → input parsing → business logic → DB query → response serialization → error handling at each layer.

---

## Step 4 — Diff Expected vs Actual

Compare spec and implementation. Classify root cause:

| Category | Example |
|----------|---------|
| **SPEC_DEVIATION** | Spec says 201, code returns 200 |
| **MISSING_ERROR_HANDLING** | No handler for invalid input → 500 |
| **DATA_CONTRACT_VIOLATION** | Contract says `{ items: [] }`, code returns `{ data: [] }` |
| **RACE_CONDITION** | Concurrent writes corrupt shared state |
| **MISSING_VALIDATION** | Spec requires email format, code accepts any string |
| **AUTH_BYPASS** | Endpoint accessible without token |
| **DEPENDENCY_MISMATCH** | Component A sends `user_id`, B expects `userId` |
| **MIGRATION_GAP** | Code references column that doesn't exist |
| **CONFIGURATION** | Missing env var, wrong port, stale cache |

---

## Step 5 — Produce Diagnosis Report

Write `agent_state/diagnose/${TIMESTAMP}-diagnosis.md`: scope, root cause (category + summary + detail + location), affected components (primary + secondary), recommended fix (specific file/line changes), verification test (concrete runnable command + expected output), risk assessment (fix risk + regression risk + recommended approach).

---

## Step 6 — Auto-Fix (if `--fix`)

1. Apply fix using appropriate implementation agent
2. Run scoped tests for affected component
3. Re-run reproduction command from diagnosis report

Fix succeeds → report with uncommitted changes + recommend `/hotfix` for proper branch/review/merge.
Fix fails → report with diagnosis path for manual investigation.

---

## Output

Primary: `agent_state/diagnose/${TIMESTAMP}-diagnosis.md`

```
✅ Diagnosis complete
  Symptom:    ${SYMPTOM}
  Root cause: ${CATEGORY} — ${SUMMARY}
  Location:   ${FILE}:${LINE_RANGE}
  Fix:        ${RECOMMENDED_APPROACH}
```

---

## Rules

- `/diagnose` is read-only by default — no code changes unless `--fix`
- Always read spec BEFORE implementation — avoid anchoring on what code does
- Every diagnosis must have specific file and line range
- Ambiguous root cause → list hypotheses ranked by likelihood
- Cross-component symptoms must trace to single root component
- Verification test must be concrete and runnable
