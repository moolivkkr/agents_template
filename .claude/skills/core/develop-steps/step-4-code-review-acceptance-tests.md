<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 4 — Code Review + Acceptance Tests (PARALLEL TRACKS)

Review and acceptance testing run as **two parallel tracks** — both read the same code, neither modifies it.

```
Step 4 (PARALLEL TRACKS):
  Track A: Code Review (three stages)
  Track B: Acceptance Tests (persona-based)
```

Both tracks must pass for the gate. Running them in parallel saves a full step.

### Track A: Code Review (Three-Stage Pipeline)

Review runs as three sequential stages. Each stage catches a different class of defect. Stages are NOT combined.

### Stage 4a — Spec Compliance Review (FIRST — catches "clean code, wrong spec")

**Purpose:** Independently verify the implementation matches the specs. This is NOT a code quality check — it's a "did you build the right thing" check.

**Approach:** Read each spec in `docs/design/phases/${PHASE}/specs/`, then verify the implementation delivers what the spec defines. Use explicit distrust:

> "The implementer's manifest reports success. Their report may be incomplete, inaccurate, or optimistic. Verify everything independently by reading the actual code — do NOT trust the manifest alone."

**Checks (per spec):**
- Every interface contract in the spec has a matching implementation (method signatures, route paths, request/response shapes)
- Every behavior described in the spec's flow section is implemented (not just stubbed)
- Every edge case in the spec has handling code (or a documented deviation)
- Every error type in the spec's error matrix has a corresponding error response
- API contracts match the wireframe API bindings (if UI phase)

**On mismatch (CLOSED LOOP):**
- Route back to implementation agent for fix (max 2 rounds)
- After fix: **re-run spec compliance check on the changed files** (not full review — targeted re-check)
- If mismatch persists after 2 rounds: log as `spec_deviation` with details → becomes gate blocker
- Log all deviations (fixed and unresolved) in report

**Output:** `agent_state/phases/${PHASE}/reports/specs_vs_impl.md` — the spec↔impl reconciliation
report. Stage 4a IS the spec-compliance dimension of that reconciliation; write findings here (as
MISSING / DEVIATION entries) rather than to a separate `spec_compliance_review.md`, so the gate reads
one canonical source. (Under `/develop-orchestrator` this is the `spec_impl_reconciler` agent's
report; the two are the same file.)

```markdown
# Spec Compliance Review — Phase N

## Summary
COMPLIANT | N deviations | N missing implementations

## Per-Spec Results
| Spec File | Contracts Verified | Behaviors Verified | Edge Cases | Result |
|-----------|-------------------|--------------------|------------|--------|

## Deviations
| Spec | Expected | Actual | Severity | Action |
|------|----------|--------|----------|--------|

## Missing Implementations
| Spec | What's Missing | Blocking |
|------|---------------|----------|
```

### Stage 4b — All remaining reviews (PARALLEL)

After spec compliance passes, run ALL remaining reviews in parallel to maximize speed:

```
Stage 4b (ALL PARALLEL):
  ├─ code_reviewer_I     → style + idioms (reads language skill pack)
  ├─ code_reviewer_II    → architecture compliance (reads IMPLEMENTATION_GUIDELINES)
  ├─ security_reviewer   → OWASP + adversarial property checks
  └─ dependency_scanner  → CVE + outdated packages
```

On issues found from any reviewer:
- Implementation agent addresses each comment
- Reviewer re-checks
- **Max 2 rounds** → unresolved issues go to `known_issues` in manifest

**Blocking rules:**
- `code_reviewer_I`: BLOCKING issues must fix
- `code_reviewer_II`: VIOLATION findings must fix
- `security_reviewer`: HIGH severity findings must fix
  **Dynamic security checks** (within security_reviewer):
  - Requires application running (from Step 2.75 smoke test)
  - Runs SQL injection, auth bypass, CORS, rate limiting probes
  - Findings appended to security_review.md under "Dynamic Security Findings"
  - BLOCKING/CRITICAL findings from dynamic checks have same gate impact as static findings
- `dependency_scanner`: CRITICAL/HIGH with available fixes must apply. Auto-applies non-breaking fixes (`npm audit fix` etc.). Breaking fixes flagged for user decision.

Reports written to `agent_state/phases/${PHASE}/reports/` (canonical names — same set the gate and
`/develop-orchestrator` require; spec-compliance findings are folded into the spec↔impl reconciliation
report, `specs_vs_impl.md`, rather than a separate `spec_compliance_review.md`):
- `code_review_I.md` (Stage 4b)
- `code_review_II.md` (Stage 4b)
- `security_review.md` (Stage 4b)
- `dependency_scan.md` (Stage 4b)
- `quality_gate.md` (code_quality_verifier)
- `specs_vs_impl.md` · `specs_vs_tests.md` (reconcilers — written to `agent_state/reconciliation/phase-N/`)
- `sast_scan.md` (Stage 4c — CONDITIONAL: only when a SAST command is configured; else a recorded skip)

### Stage 4c — Static Application Security Testing (parallel with review)

Run SAST scan on all code changed in this phase:

```bash
# Language-specific SAST command comes from docs/IMPLEMENTATION_GUIDELINES.md — there is NO silent
# language default (a hardcoded Go govulncheck on a Python project is worse than skipping). Read the
# labelled command; if none is configured, SKIP explicitly (recorded, not silently passed).
# Reference examples (what a guideline might list):
#   Go: govulncheck ./...   Python: bandit -r src/ -f json   TS/JS: semgrep --config auto src/
#   Java: semgrep / spotbugs   Rust: cargo audit

# Same helper as the Step-6 regression gate — reads a backtick-quoted command from the guidelines,
# invents no default, returns empty when not found. (Redefined here because shell state does not
# persist across steps.)
read_cmd_from_guidelines() {
  local label="$1" file="docs/IMPLEMENTATION_GUIDELINES.md"
  [ -f "$file" ] || return 1
  grep -iE "$label" "$file" | grep -oE '`[^`]+`' | head -1 | tr -d '`'
}
SAST_CMD=$(read_cmd_from_guidelines 'sast|govulncheck|bandit|semgrep|cargo audit')
if [ -z "$SAST_CMD" ]; then
  echo "⚠ SAST SKIPPED — no SAST command found in docs/IMPLEMENTATION_GUIDELINES.md." \
    > agent_state/phases/${PHASE}/reports/sast_scan.md
  echo "  Add one under '## Common Tasks' (e.g. \`govulncheck ./...\`, \`semgrep --config auto src/\`)" \
    >> agent_state/phases/${PHASE}/reports/sast_scan.md
  echo "  to enable static security scanning. This is an explicit, recorded skip — not a pass." \
    >> agent_state/phases/${PHASE}/reports/sast_scan.md
else
  eval "$SAST_CMD" > agent_state/phases/${PHASE}/reports/sast_scan.md 2>&1
fi
```

`read_cmd_from_guidelines` is defined in the Step-6 regression block above; it invents no default and
returns empty when nothing matches.

Severity mapping:
- CRITICAL/HIGH → BLOCKING (must fix before gate)
- MEDIUM → WARNING (logged in known_issues)
- LOW → INFO (logged but not blocking)

If no SAST tool is configured in IMPLEMENTATION_GUIDELINES: the scan is SKIPPED with the explicit
warning written to sast_scan.md above (recorded, never a silent green).

---

### Track B: Acceptance Tests (runs in PARALLEL with Track A)

**Agent:** `acceptance_test_agent`

Validates implementation at use case and persona level against BRD FR-* requirements scoped to this phase. Runs in parallel with code review — both read the same code, neither modifies it.

### Data Seeding
1. Check `requirements/test-data/phase-${PHASE}.yaml` — use if present (user-provided data takes priority)
2. If absent: `acceptance_test_agent` generates realistic seed data from BRD personas + in-scope use cases
3. Seed data applied via API or direct DB (per IMPLEMENTATION_GUIDELINES)

### Execution
- Each in-scope FR-* with user-facing acceptance criteria is executed as its declared persona
- Every BRD persona must be exercised by ≥1 use case this phase (if in scope)
- Results: PASS / PARTIAL (N of M criteria met) / FAIL per use case

### Contract Shape Assertions (runs alongside persona tests)
For EVERY API endpoint called during acceptance testing, verify:
- Response matches `data-contracts.md` TypeScript interface (field names, types)
- List endpoints return `data: []` (array), not object
- Single endpoints return `data: {}` (object), not array
- Empty list returns `{ data: [], meta: { total: 0 } }`, not `null` or `{}`
- Log mismatches as `CONTRACT_VIOLATION` — these are the exact bugs that crash the UI

### Iteration (Feedback Loop with Escalation)

Acceptance testing is NOT read-only. Failures drive implementation fixes:

```
Cycle 1: Run all acceptance tests
  → All PASS? → proceed to gate
  → PARTIAL or FAIL? → categorize each failure:
    A) Implementation bug (feature doesn't work) → route to implementation agent
    B) Spec ambiguity (unclear what "correct" means) → route to spec_writer for clarification
    C) Test data issue (seed data wrong) → fix seed data
    D) Architectural limitation (can't be fixed without redesign) → ESCALATE

  → Fix category A/B/C → re-run ONLY failed acceptance tests

Cycle 2: Re-run failed tests
  → All PASS? → proceed
  → Still failing? → deeper analysis
    → If same test keeps failing: likely category D (architectural)
    → ESCALATE to debate_moderator:
      debate_request: {
        topic: "Acceptance test failure: <FR-*> <persona> <use case>",
        context: "BRD says X, implementation does Y, cannot reconcile after 2 attempts",
        options: [
          "Redesign the feature architecture to meet the AC",
          "Amend the BRD acceptance criteria (with justification)",
          "Defer to next phase with documented workaround",
          "The acceptance test interpretation is wrong"
        ]
      }
    → Arbitrator decides → implement → final re-test

Cycle 3: Final acceptance
  → PASS? → proceed to gate
  → FAIL? → BLOCK gate with detailed failure report
```

**Key principle:** Acceptance tests represent the BRD contract. If implementation can't meet the AC, the debate team decides whether to fix the code, amend the BRD, or defer — but it's never silently skipped.

### Outputs
- `agent_state/phases/${PHASE}/reports/acceptance_report.md` — full results
- `agent_state/phases/${PHASE}/test-data/generated-seed.yaml` — seed data used
- `agent_state/phases/${PHASE}/test-data/seed-cleanup.md` — how to reset

---
