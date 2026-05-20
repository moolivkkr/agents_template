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

Systematic investigation that traces a symptom to its root cause by comparing spec (expected behavior) against implementation (actual behavior). Produces a diagnosis report with root cause, affected components, and recommended fix.

**Use when:** You know WHAT is wrong but not WHY. `/diagnose` finds the why. `/hotfix` fixes it.

---

## Step 0 — Parse Symptom and Identify Scope

```bash
SYMPTOM="${ARG_SYMPTOM}"
PHASE="${ARG_PHASE}"
COMPONENT="${ARG_COMPONENT}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
```

Parse the symptom to identify:
- **Route/endpoint** — if the symptom mentions an API route, extract it
- **Error type** — HTTP status code, exception type, unexpected behavior
- **Affected entity** — which domain object or feature is involved

If `--phase` was not provided:
1. Search all phase manifests for a component owning the route/feature
2. Match the symptom against `api_routes[]`, component names, and BRD requirement IDs
3. If ambiguous, list candidates and ask the user to disambiguate

If `--component` was not provided:
1. From the identified phase manifest, find the component that owns the affected route/feature
2. Match against component `api_routes[]`, `source_files[]`, and spec descriptions

```
Investigation scope:
  Symptom:   ${SYMPTOM}
  Phase:     ${PHASE} (auto-detected | specified)
  Component: ${COMPONENT} (auto-detected | specified)
```

---

## Step 1 — Read Phase Manifest

```bash
MANIFEST="agent_state/phases/${PHASE}/manifest.json"
```

Extract from manifest:
- Component entry for `${COMPONENT}` — source files, test files, routes
- Related components — any component that imports from or is imported by `${COMPONENT}`
- Data contracts referenced by this component
- BRD requirements mapped to this component

Build the investigation context:
```
Component: ${COMPONENT}
  Source files:    [list]
  Test files:      [list]
  Routes:          [list]
  Data contracts:  [list]
  BRD reqs:        [list]
  Dependencies:    [list of other components this one touches]
```

---

## Step 2 — Read Spec (Expected Behavior)

Read the component's spec file (from `docs/design/phases/${PHASE}/`):

Extract:
- **Expected behavior** for the affected route/feature
- **Input validation rules** — what inputs are accepted, what is rejected
- **Response shape** — expected status codes, response body structure
- **Error handling** — how errors should be surfaced
- **Edge cases** — documented edge cases and their expected outcomes
- **Data contract** — TypeScript interface or schema for request/response

```
Expected behavior:
  Route:      ${ROUTE}
  Method:     ${METHOD}
  Input:      ${INPUT_SHAPE}
  Success:    ${SUCCESS_STATUS} → ${RESPONSE_SHAPE}
  Errors:     ${ERROR_CASES}
  Validation: ${VALIDATION_RULES}
```

---

## Step 3 — Read Implementation (Actual Behavior)

Read the source files for `${COMPONENT}`:
- Route handler / controller
- Service layer
- Repository / data access layer
- Middleware (auth, validation)

Trace the request flow from entry point to response:
1. Route registration → handler function
2. Input parsing / validation
3. Business logic
4. Database query / external call
5. Response serialization
6. Error handling at each layer

```
Actual behavior:
  Handler:     ${HANDLER_FILE}:${LINE}
  Validation:  ${WHAT_IS_ACTUALLY_VALIDATED}
  Logic:       ${WHAT_THE_CODE_ACTUALLY_DOES}
  Query:       ${ACTUAL_DB_QUERY}
  Response:    ${ACTUAL_RESPONSE_SHAPE}
  Errors:      ${ACTUAL_ERROR_HANDLING}
```

---

## Step 4 — Diff Expected vs Actual

Compare spec and implementation to identify the mismatch. Classify the root cause:

| Category | Description | Example |
|----------|-------------|---------|
| **SPEC_DEVIATION** | Implementation doesn't match spec | Spec says 201, code returns 200 |
| **MISSING_ERROR_HANDLING** | Error path not implemented | No handler for invalid input → unhandled exception → 500 |
| **DATA_CONTRACT_VIOLATION** | Response shape doesn't match contract | Contract says `{ items: [] }`, code returns `{ data: [] }` |
| **RACE_CONDITION** | Timing-dependent failure | Concurrent writes corrupt shared state |
| **MISSING_VALIDATION** | Input not validated per spec | Spec requires email format, code accepts any string |
| **AUTH_BYPASS** | Auth/authz not enforced | Endpoint accessible without token |
| **DEPENDENCY_MISMATCH** | Cross-component interface mismatch | Component A sends `user_id`, component B expects `userId` |
| **MIGRATION_GAP** | Schema doesn't match what code expects | Code references column that doesn't exist |
| **CONFIGURATION** | Environment/config issue | Missing env var, wrong port, stale cache |

```
Root cause analysis:
  Category:     ${CATEGORY}
  Location:     ${FILE}:${LINE_RANGE}
  Expected:     ${WHAT_SPEC_SAYS}
  Actual:       ${WHAT_CODE_DOES}
  Why:          ${EXPLANATION}
```

---

## Step 5 — Produce Diagnosis Report

Write `agent_state/diagnose/${TIMESTAMP}-diagnosis.md`:

```markdown
# Diagnosis Report
Timestamp: ${TIMESTAMP}
Symptom: ${SYMPTOM}

## Scope
- Phase: ${PHASE}
- Component: ${COMPONENT}
- Affected files: [list]

## Root Cause
**Category:** ${CATEGORY}

**Summary:** <1-2 sentence explanation>

**Detail:**
- Expected (from spec): <what should happen>
- Actual (from code): <what actually happens>
- Location: ${FILE}:${LINE_RANGE}
- Why: <explanation of how the bug was introduced>

## Affected Components
- **Primary:** ${COMPONENT} — contains the bug
- **Secondary:** [list of components that may exhibit symptoms due to this bug]

## Recommended Fix
1. <specific change 1 — file, line, what to change>
2. <specific change 2 — if needed>

**Estimated scope:** N files, N lines changed

## Verification Test
To confirm the fix works:
```
<specific test command or curl command that reproduces the symptom>
<expected output after fix>
```

## Risk Assessment
- **Fix risk:** LOW | MEDIUM | HIGH
- **Regression risk:** LOW | MEDIUM | HIGH
- **Recommended approach:** /hotfix | /develop
```

---

## Step 6 — Auto-Fix (if `--fix` flag)

If `--fix` was provided:

1. **Apply fix** — use the appropriate implementation agent for the component's language/framework
2. **Scoped test** — run only tests for the affected component
3. **Verify** — re-run the reproduction command from the diagnosis report

```bash
# Run the verification test
<reproduction-command>
# Expected: <expected output>
# Actual: <observed output>
```

If fix succeeds:
```
✅ Auto-fix applied and verified

  Fix:     ${FIX_SUMMARY}
  Tests:   N/N passed
  Verify:  Symptom resolved

  Changes are uncommitted. Next steps:
    /hotfix --phase=${PHASE} --component=${COMPONENT} --description="${DESCRIPTION}"
    (to properly branch, review, and merge the fix)

    Or: git add <files> && git commit (if you prefer manual flow)
```

If fix fails:
```
⚠ Auto-fix attempted but verification failed

  Applied: ${FIX_SUMMARY}
  Tests:   N/N passed | N failed
  Verify:  Symptom still present

  Diagnosis report: agent_state/diagnose/${TIMESTAMP}-diagnosis.md
  Changes are uncommitted and may be reverted.

  Recommend: manual investigation starting from the diagnosis report
```

---

## Output

Primary output: `agent_state/diagnose/${TIMESTAMP}-diagnosis.md`

```
✅ Diagnosis complete → wrote agent_state/diagnose/${TIMESTAMP}-diagnosis.md

  Symptom:    ${SYMPTOM}
  Root cause: ${CATEGORY} — ${ONE_LINE_SUMMARY}
  Location:   ${FILE}:${LINE_RANGE}
  Fix:        ${RECOMMENDED_APPROACH}
```

---

## Rules

- `/diagnose` is read-only by default — it investigates, it does not change code (unless `--fix`)
- Always read the spec BEFORE the implementation — avoid anchoring on what the code does
- Every diagnosis must have a specific file and line range — "somewhere in the auth middleware" is not a diagnosis
- If the root cause is ambiguous, list multiple hypotheses ranked by likelihood
- Cross-component symptoms must trace back to a single root component — find the source, not the symptom
- The verification test in the report must be concrete and runnable — not "check if it works"
