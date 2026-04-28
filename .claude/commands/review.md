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
---

# /review — Code Review

Runs the three-layer review pipeline: style/idioms → architecture compliance → security.

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

## Step 1 — Style & Idioms (`code_reviewer_I`)

**Agent:** `code_reviewer_I`
**Reads:** Active language skill pack (`.claude/skills/languages/{{LANG}}.md`)

Checks:
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
- Repository pattern respected (no direct DB in handlers)
- API versioning convention followed
- Service layer has no framework-specific types
- Dependency direction (domain ← service ← handler, never reversed)
- No circular dependencies
- Component boundaries respected (from component inventory)

Writes: `agent_state/review/code_review_II.md`

---

## Step 3 — Security (`security_reviewer`)

**Agent:** `security_reviewer`
**Reads:** `.claude/skills/core/security-owasp.md`, IMPLEMENTATION_GUIDELINES

Checks (OWASP Top 10 + project-specific):
- Input validation at all API boundaries
- Parameterized queries (no string concatenation with user input)
- Auth checks on all protected routes
- Secrets not hardcoded
- Dependency vulnerabilities (flag any known CVEs in use)
- CORS policy correct
- JWT validation complete (expiry, signature, claims)

Severity: HIGH (blocking), MEDIUM (should fix), LOW (informational)

Writes: `agent_state/review/security_review.md`

---

## Step 4 — Report

```
Code Review Results

  Style & Idioms:       PASS / N warnings / N blocking
  Architecture:         PASS / N violations
  Security:             PASS / N HIGH / N MEDIUM / N LOW

  Blocking issues (must fix before merge):
    ❌ [file:line] <issue> — <recommendation>

  Warnings (should fix):
    ⚠  [file:line] <issue> — <recommendation>

  Reports:
    agent_state/review/code_review_I.md
    agent_state/review/code_review_II.md
    agent_state/review/security_review.md
```

HIGH security findings and BLOCKING style issues must be resolved before `/develop` gate can pass or before merging.
