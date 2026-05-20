---
command: review
description: Run code review on current changes or a specific phase. Style + architecture + security.
arguments:
  - name: phase
    required: false
    description: "Phase to review. Omit to review uncommitted changes."
  - name: security_only
    required: false
    default: false
    description: "Run security review only"
  - name: arch_only
    required: false
    default: false
    description: "Run architecture review only"
  - name: isolation_only
    required: false
    default: false
    description: "Run tenant isolation verification only"
---

# /review — Code Review

Four-layer review pipeline: style/idioms → architecture compliance → tenant isolation → security.

---

## Step 0 — Determine Scope

```bash
if [ -n "$ARG_PHASE" ]; then
  SCOPE=$(cat agent_state/phases/${ARG_PHASE}/manifest.json | jq -r '.artifacts.code[]')
else
  SCOPE=$(git diff --name-only HEAD)
fi
```

Load: `docs/BRD.md`, `docs/IMPLEMENTATION_GUIDELINES.md`, `agent_state/agent_registry.json`

---

## Step 0.5 — Spec Compliance (phase reviews only)

**Skip when:** reviewing uncommitted changes

Independently verify implementation matches specs with explicit distrust: "The implementer's manifest reports success. Verify everything independently."

Checks: interface contracts implemented, behaviors not stubbed, edge cases handled, API contracts match wireframe bindings.

Writes: `agent_state/review/spec_compliance_review.md`

---

## Step 1 — Style & Idioms (`code_reviewer_I`)

**Reads:** Active language skill pack

**Security-adjacent idioms (checked first, BLOCKING):** auth context result discarded, unsafe double-cast, raw error messages in responses, placeholder values in privileged actions.

**Also checks:** language idioms, naming conventions, error handling, complexity (>50 lines flagged), dead code, comment quality.

Severity: BLOCKING / WARNING / INFO. Writes: `agent_state/review/code_review_I.md`

---

## Step 2 — Architecture Compliance (`code_reviewer_II`)

**Authorization chain integrity (checked first, VIOLATION):** every service method with resource ID has tenantID, tenantID forwarded through all layers, in-memory stores have ownership check + concurrency protection.

**Also checks:** repository pattern, API versioning, service layer purity, dependency direction, no circular deps, component boundaries.

Writes: `agent_state/review/code_review_II.md`

---

## Step 2.5 — Tenant Isolation Verification (`tenant_isolation_verifier`)

Single-purpose mechanical tracer. For every route with resource ID parameter:
1. Auth context extraction result NOT discarded
2. tenantID traced from auth → service → data access
3. Data access WHERE clause includes ownership predicate
4. In-memory stores: ownership check before returning data

Per-route PASS/FAIL table. **CRITICAL findings block gate immediately.**

Writes: `agent_state/review/tenant_isolation.md`

---

## Step 3 — Security (`security_reviewer`)

**Reads:** `.claude/skills/core/security-owasp.md`, IMPLEMENTATION_GUIDELINES, `tenant_isolation.md`

Checks: IDOR chain trace, in-memory store audit, response leakage, frontend/backend limit drift, unsafe casts, query validation completeness, input validation, auth/token validation, no secrets in code, PII not logged, CORS not wildcard, CSRF protection, rate limiting on auth.

Severity: HIGH (blocking) / MEDIUM / LOW. Writes: `agent_state/review/security_review.md`

---

## Step 4 — Report

```
Code Review Results
  Style & Idioms:       PASS / N warnings / N blocking
  Architecture:         PASS / N violations
  Tenant Isolation:     PASS / N CRITICAL
  Security:             PASS / N HIGH / N MEDIUM / N LOW
  Blocking issues: ❌ [file:line] <issue>
  Warnings: ⚠ [file:line] <issue>
```

**Gate policy:** CRITICAL/HIGH/BLOCKING/VIOLATION → phase gate BLOCKED, must fix.

---

## Step 5 — Fix and Re-Verify Loop

**When:** ANY BLOCKING/VIOLATION/CRITICAL/HIGH findings exist

```
For each finding:
  1. Route to appropriate implementation agent
  2. Agent applies targeted fix
  3. Re-run ONLY the reviewer that found it
  4. RESOLVED or retry (max 2 rounds per finding)
  5. After 2 rounds: log as unresolved
```

**Limits:** 2 rounds per finding, 10 total cycles per session.

Updated report shows fixed items + remaining blockers.

**Anti-rationalization:** "The fix looks right, no need to re-run the reviewer" → Wrong. Reviewer must independently verify.
