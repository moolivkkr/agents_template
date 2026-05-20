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

Runs the four-layer review pipeline: style/idioms → architecture compliance → tenant isolation → security.

---

## Step 0 — Determine Scope

```bash
if [ -n "$ARG_PHASE" ]; then
  # Review all code produced in the specified phase (from manifest artifacts)
  SCOPE=$(cat agent_state/phases/${ARG_PHASE}/manifest.json | jq -r '.artifacts.code[]')
else
  # Review uncommitted changes
  SCOPE=$(git diff --name-only HEAD)
fi
echo "Review scope: $SCOPE"
```

Load context:
- `docs/BRD.md`
- `docs/IMPLEMENTATION_GUIDELINES.md`
- `agent_state/agent_registry.json` (for active skill packs)

---

## Step 0.5 — Spec Compliance (if phase specified)

**Runs when:** `$ARG_PHASE` is set (reviewing a phase, not just uncommitted changes)
**Skip when:** reviewing uncommitted changes (no specs to compare against)

Independently verify the implementation matches the phase specs. Uses explicit distrust:
> "The implementer's manifest reports success. Verify everything independently by reading the actual code."

Checks:
- Every interface contract in specs has a matching implementation
- Every behavior described in spec flow sections is implemented (not stubbed)
- Every edge case in specs has handling code
- API contracts match wireframe API bindings (if UI phase)

On mismatch: log as `spec_deviation` with file, expected, actual.

Writes: `agent_state/review/spec_compliance_review.md`

---

## Step 1 — Style & Idioms (`code_reviewer_I`)

**Agent:** `code_reviewer_I`
**Reads:** Active language skill pack (`.claude/skills/languages/{{LANG}}.md`)

Checks:
- **Security-adjacent idioms (checked first, BLOCKING):**
  - Auth context extracted but actor discarded (`_, ok` pattern; result thrown away)
  - Unsafe double-cast (`as unknown as` in TypeScript; bare type assertion without comma-ok in Go)
  - Raw error messages (`err.Error()`, `exception.message`) in HTTP responses
  - Placeholder values in privileged actions (approve, reject)
- Language idioms and conventions from skill pack
- Naming conventions (from IMPLEMENTATION_GUIDELINES)
- Error handling patterns
- Code complexity (functions > 50 lines flagged)
- Dead code, unused variables
- Comment quality (missing on non-obvious logic)

Severity: BLOCKING (must fix) / WARNING (should fix) / INFO (consider)

Writes: `agent_state/review/code_review_I.md`

---

## Step 2 — Architecture Compliance (`code_reviewer_II`)

**Agent:** `code_reviewer_II`
**Reads:** `docs/IMPLEMENTATION_GUIDELINES.md`, previous `code_review_I.md`

Checks:
- **Authorization chain integrity (checked first, VIOLATION):**
  - Every service method with resource ID has tenantID in signature
  - tenantID forwarded from handler through service into every data access call
  - In-memory stores for multi-tenant data have ownership check on every read
  - In-memory stores have concurrency protection (mutex/lock)
- Repository pattern respected (no direct DB in handlers)
- API versioning convention followed
- Service layer has no framework-specific types
- Dependency direction (domain ← service ← handler, never reversed)
- No circular dependencies
- Component boundaries respected (from component inventory)

Writes: `agent_state/review/code_review_II.md`

---

## Step 2.5 — Tenant Isolation Verification (`tenant_isolation_verifier`)

**Agent:** `tenant_isolation_verifier`
**Runs:** In parallel with Step 2, or immediately after if sequential

This is a single-purpose mechanical tracer. For every route that accepts a resource ID parameter:

1. Confirms auth context extraction result is NOT discarded
2. Traces tenantID from auth context into every service call
3. Traces tenantID from service signature into every data access call
4. Confirms data access WHERE clause includes ownership predicate
5. For in-memory stores: confirms ownership check before returning data

Produces a per-route PASS/FAIL table.

**CRITICAL findings block the phase gate immediately.** Do not proceed to Step 3 if any route fails.

Writes: `agent_state/review/tenant_isolation.md`

---

## Step 3 — Security (`security_reviewer`)

**Agent:** `security_reviewer`
**Reads:** `.claude/skills/core/security-owasp.md`, IMPLEMENTATION_GUIDELINES, `agent_state/review/tenant_isolation.md`

Checks (adversarial property verification + OWASP Top 10):
- **IDOR chain trace** — for every ID-based route, tenantID flows from auth context through every data access (references tenant_isolation.md)
- **In-memory store audit** — multi-tenant stores have ownership check and concurrency protection
- **Response leakage** — no `err.Error()` or internal details in API error responses
- **Frontend/backend limit drift** — query param names and value ranges match between frontend client and backend handler
- **Unsafe casts** — `as unknown as` (TypeScript), unguarded type assertions
- **Query validation completeness** — if project has SQL builder: allowlist wired into validation, UNION/INTO/RETURNING in blocklist
- Input validation at all API boundaries
- Auth checks on all protected routes; token validated (expiry + signature + claims)
- No secrets in code; PII not logged
- CORS policy explicitly configured; not wildcard
- CSRF protection on state-changing endpoints
- Rate limiting on auth endpoints

Severity: HIGH (blocking), MEDIUM (should fix), LOW (informational)

Writes: `agent_state/review/security_review.md`

---

## Step 4 — Report

```
Code Review Results

  Style & Idioms:       PASS / N warnings / N blocking
  Architecture:         PASS / N violations
  Tenant Isolation:     PASS / N CRITICAL (gate blocked if any)
  Security:             PASS / N HIGH / N MEDIUM / N LOW

  Blocking issues (must fix before merge):
    ❌ [file:line] <issue> — <recommendation>

  Warnings (should fix):
    ⚠  [file:line] <issue> — <recommendation>

  Reports:
    agent_state/review/code_review_I.md
    agent_state/review/code_review_II.md
    agent_state/review/tenant_isolation.md
    agent_state/review/security_review.md
```

**Gate policy:**
- CRITICAL tenant isolation findings → phase gate BLOCKED immediately; fix before proceeding
- HIGH security findings → phase gate BLOCKED; must fix before merge
- BLOCKING style issues → phase gate BLOCKED; must fix before merge
- VIOLATION architecture findings → phase gate BLOCKED; must fix before merge
