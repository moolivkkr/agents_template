---
command: develop
description: Implement a phase end-to-end. Audit → implement → test (unit + integration + e2e) → review → gate. Auto-detects current phase. Zero required inputs.
arguments:
  - name: phase
    required: false
    description: "Override phase number. Omit to auto-detect from gate state."
  - name: audit_only
    required: false
    default: false
    description: "Produce gap report only — no implementation, no code changes"
  - name: test_only
    required: false
    default: false
    description: "Run tests only — no implementation changes"
---

# /develop — Autonomous Phase Implementation

Fully autonomous phase implementation. Detects where you are, implements all specs, tests, reviews, and writes the phase gate.

**One decision point:** at the end — advance to the next phase or not.

---

## Session Context Budget

`/develop` is a long-running pipeline. Follow these rules to stay within the conversation context window:

**Agent result discipline — return summaries, not content:**
Every agent (subagent or inline) must end with this exact pattern:
```
✅ <agent-name> complete → wrote <output-file-path>
   Summary: <3 lines max of what was done>
   Issues: none | <count + severity>
```
The full output is in the file. The parent conversation receives only the summary above.
**Never echo file contents back to the parent conversation.**

**Read discipline — load-then-act, don't accumulate:**
- Read a file → act on it → do not re-read the same file in the same step
- Never load the same document twice in one step
- `phase_context.md` is read once at Step 0 and referenced from memory for the rest of the step

**Step isolation:**
Each step (Audit, Implement, Test, Review, Gate) is a complete unit. After a step writes its output files, the conversation for that step is finished. If the conversation window fills mid-step, the step can be resumed by reading the output files already written — all state is in `agent_state/phases/${PHASE}/`.

**Per-step context budget targets:**
| Step | Target input tokens | What to load |
|------|--------------------|----|
| Step 0 Orient | ~10K | phase_context.md (6-8K) + gate files |
| Step 1 Audit | ~20K | phase_context.md + per-spec file (one at a time) + prev manifest |
| Step 2 Implement (per agent) | ~25K | phase_context.md + own component spec + prev manifest |
| Step 3 Test | ~20K | phase_context.md + new code only (git diff this phase) + spec edge cases section |
| Step 3d Reconcile C | ~25K | all phase specs + agent implementation summaries (from manifests, not full code) |
| Step 3e Reconcile D | ~20K | spec test-coverage sections + test file list from unit/integration reports |
| Step 4 Review | ~20K | code diff this phase only (not full src/) + skill pack §patterns section |
| Step 5 Acceptance | ~15K | phase_context.md §requirements + acceptance criteria + seed data |
| Step 6 Gate | ~8K | report file first 20 lines each (summary rows) — not full report content |

Note: `phase_context.md` is 6-8K but replaces 30-70K of BRD + IMPL_GUIDELINES. Loading it in every step is intentional and correct.

---

## Step 0 — Orient

### Detect current phase
```bash
LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}
echo "▶ Running Phase $PHASE"
```

### Gate check
If PHASE > 1 and `agent_state/phases/$((PHASE-1))/gate.passed` is missing:
**STOP** — `Phase $((PHASE-1)) gate not found. Run /develop --phase=$((PHASE-1)) first.`

If `docs/design/phases/${PHASE}/INDEX.md` is missing:
**Auto-run `/plan --phase=${PHASE}` first**, then continue.

### Load previous phase context
Read `agent_state/phases/$((PHASE-1))/manifest.json` (if PHASE > 1):
- Surface `carried_forward[]` issues at the top of the Step 1 audit report
- Note existing code paths, API routes, DB schema from previous phases

### Start infrastructure
```bash
# Bring up local dev stack from IMPLEMENTATION_GUIDELINES Section 5
# Commands vary per project — read docs/IMPLEMENTATION_GUIDELINES.md for exact commands
docker compose up -d  # (or equivalent from project setup)

# Wait for DB readiness (up to 60s)
# Health check command from IMPLEMENTATION_GUIDELINES
```

### Universal Agent Return Protocol

Every agent spawned during this command MUST end by returning this exact format — nothing more — to the parent conversation:

```
✅ <agent-name> — <status: complete | blocked | partial>
   Wrote: <output file path>
   Done:  <what was implemented in one line>
   Issues: none | <N blocking / N warning>
```

If the agent encountered blockers, append:
```
   Blocker: <one-line description> → see <file path> for details
```

**The parent reads the output file to get details. It does NOT ask the agent to reproduce or summarize the file contents.**

### Placeholder Convention
Throughout all agent files and commands:
- `${PHASE}` — current phase number (bash variable, numeric)
- `$((PHASE-1))` — previous phase number (bash arithmetic)
- `{{PHASE}}` — when used inside agent `.md` files, means "substitute the current phase number here at runtime"
- `{{PHASE-1}}` — when used inside agent `.md` files, means "substitute the previous phase number (current minus 1) here at runtime"

Agents reading `{{PHASE-1}}` in their instructions should resolve this to `PHASE - 1` before looking up any path.

---

### Agent Context Protocol — Minimal, targeted reads

**Primary context — agents load these, nothing more by default:**

| File | Size | Contains |
|------|------|----------|
| `docs/design/phases/${PHASE}/phase_context.md` | ~6-8K | Complete tech stack, all conventions, security NFRs, full acceptance criteria, what already exists, gate checklist |
| `docs/design/phases/${PHASE}/specs/<own-component>.md` | ~5-10K | Interface contracts, data model, edge cases, test requirements for THIS component only |
| `agent_state/phases/$((PHASE-1))/manifest.json` | ~3-5K | Existing routes, schema, services — what NOT to re-implement |

`phase_context.md` is intentionally complete — it contains the full tech stack, all coding conventions, all security requirements, and all acceptance criteria needed for correct implementation. **It is not a 50-line stub — it is a structured 6-8K extract that replaces the need to load the full BRD and IMPLEMENTATION_GUIDELINES.**

**Escalation (only when phase_context.md leaves something unresolved):**
- More detail on a specific requirement → `docs/BRD.md` — read only the specific FR-* row
- Infra setup commands → `docs/IMPLEMENTATION_GUIDELINES.md §Local Development Setup` only
- Adjacent component's interface → `docs/design/phases/${PHASE}/specs/<other-component>.md`

**Never load:**
- The entire `docs/BRD.md` (except: brd_spec_reconciler, requirements_brd_reconciler, acceptance_test_agent)
- The entire `docs/IMPLEMENTATION_GUIDELINES.md` (except: agent_factory, architecture_orchestrator)
- All spec files at once — load your component's spec only

---

## Step 1 — Audit

**Agents (parallel):**
- `backend_audit_agent` — always runs
- `ui_audit_agent` — runs only if `frontend.enabled = true` in `docs/IMPLEMENTATION_GUIDELINES.md`

Both agents read all Step 0 context. `backend_audit_agent` writes `agent_state/phases/${PHASE}/audit_report.md`. `ui_audit_agent` writes `agent_state/phases/${PHASE}/audit_report_ui.md`.

```markdown
# Phase N Audit Report

## Carried Forward Issues (from Phase N-1)
[Issues from previous manifest's carried_forward[] — MUST appear here]

## Gap Analysis
| Component | Expected (from spec) | Found (in codebase) | Gap |
|-----------|---------------------|---------------------|-----|

## Missing Implementations
- [ ] <component/function> — required by spec <file.md>

## Broken/Incomplete Items
- [ ] <item> — reason

## Recommended Implementation Order
1. ...
```

If `--audit_only` flag: stop here and print the report.

---

## Step 2 — Implementation (Wave-based Parallel Execution)

**Agents:** Generated agents from `.claude/agents/generated/` per component type

Run implementation in the waves defined in `PHASE_PLAN.md`. Each wave runs in parallel; waves are sequential.

**Typical wave structure:**
```
Wave 1 (parallel):
  ├─ database_agent     → schema design + docs/design/database.md
  └─ migration_agent    → migration files (up + down)

Wave 2 (parallel):
  ├─ backend_developer  → domain models, services, repositories
  └─ api_developer      → API handlers, routes, middleware

Wave 3 (parallel, UI phases only):
  └─ ui_developer       → screen implementation from wireframes

Wave 4 (parallel):
  ├─ unit_test_agent     → unit tests for all new code
  └─ integration_test_agent → integration tests for service↔infra
```

Each agent:
1. Reads ALL Step 0 context + its specific spec files
2. Reads its activated skill pack (`.claude/skills/languages/{{LANG}}.md` etc.)
3. Implements only what is in scope for this phase (prev manifest shows what exists)
4. Writes an agent-level manifest to `agent_state/phases/${PHASE}/<agent>/manifest.json`

---

## Step 3 — Tests

### Step 3a — Unit Tests
**Agent:** Generated `unit_test_agent`

Runs unit tests. On failure:
- Diagnoses root cause
- Fixes implementation (not the tests)
- Reruns
- **Max 3 attempts** → then surfaces unresolved failures with reproduction steps

### Step 3b — Integration Tests
**Agent:** Generated `integration_test_agent`

Requires infra running (started in Step 0). Tests service↔DB and service↔cache interactions.

Same iteration rules: fix → retry → max 3 attempts.

### Step 3c — E2E Tests (conditional)
**Trigger:** `PHASE_PLAN.md` has non-empty `e2e_workflows_unlocked` list

**Agent:** `e2e_orchestrator` + generated `ui_test_agent` (if UI phase)

Runs complete user workflow tests. Same iteration rules: fix → retry → max 2 attempts.

**All three tiers must pass before the reconciliation steps.**

---

## Step 3d — Reconciliation Point C: Specs ↔ Implementation

**Agent:** `spec_impl_reconciler`

Validates both directions:
- **Forward:** spec-defined behaviors missing from the implementation
- **Reverse:** unspecced implementation (behaviors added without spec justification)

Output: `agent_state/reconciliation/phase-N/specs_vs_impl.md`

Missing implementations = blocker (fix before acceptance tests).
Unspecced implementations = flagged for human review (not always wrong).

---

## Step 3e — Reconciliation Point D: Specs ↔ Tests

**Agent:** `spec_test_reconciler`

Validates both directions:
- **Forward:** spec-defined edge cases and behaviors with no test coverage
- **Reverse:** tests that test behaviors not in any spec

Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md`

HIGH-priority untested behaviors = blocker.
MEDIUM/LOW = logged as known gaps.

---

## Step 4 — Code Review

**Agents:** `code_reviewer_I` (style + idioms) then `code_reviewer_II` (architecture)

Run sequentially — `code_reviewer_II` reads `code_reviewer_I`'s report.

On issues found:
- Implementation agent addresses each comment
- Reviewer re-checks
- **Max 2 rounds** → unresolved issues go to `known_issues` in manifest

`code_reviewer_I` reads the active language skill pack for language-specific idiom checks.
`code_reviewer_II` reads `docs/IMPLEMENTATION_GUIDELINES.md` for architecture compliance.

**Security gate:** `security_reviewer` runs in parallel with code review. Any HIGH severity finding is **blocking** — must be fixed before gate can pass.

Reports written to `agent_state/phases/${PHASE}/reports/`:
- `code_review_I.md`
- `code_review_II.md`
- `security_review.md`

---

## Step 5 — Acceptance Tests

**Agent:** `acceptance_test_agent`

Validates implementation at use case and persona level against BRD FR-* requirements scoped to this phase. Runs after code review — tests the complete, reviewed implementation from the user's perspective.

### Data Seeding
1. Check `requirements/test-data/phase-${PHASE}.yaml` — use if present (user-provided data takes priority)
2. If absent: `acceptance_test_agent` generates realistic seed data from BRD personas + in-scope use cases
3. Seed data applied via API or direct DB (per IMPLEMENTATION_GUIDELINES)

### Execution
- Each in-scope FR-* with user-facing acceptance criteria is executed as its declared persona
- Every BRD persona must be exercised by ≥1 use case this phase (if in scope)
- Results: PASS / PARTIAL (N of M criteria met) / FAIL per use case

### Iteration
- Acceptance failure → implementation agent fixes → re-test → max 2 rounds
- After max rounds: log as unresolved → **phase gate blocked**

### Outputs
- `agent_state/phases/${PHASE}/reports/acceptance_report.md` — full results
- `agent_state/phases/${PHASE}/test-data/generated-seed.yaml` — seed data used
- `agent_state/phases/${PHASE}/test-data/seed-cleanup.md` — how to reset

---

## Step 6 — Phase Gate

Read the output file for each gate item below. Evaluate the specific pass/fail criterion. If the condition is NOT met, record it as a blocker — **do not write gate.passed**.

```
Gate Item                    Source File                                          Pass Condition
─────────────────────────────────────────────────────────────────────────────────────────────────
Unit tests                   agent_state/phases/${PHASE}/reports/unit_tests.md   No FAILED tests
Integration tests            agent_state/phases/${PHASE}/reports/integration_tests.md   No FAILED tests
E2E tests (if unlocked)      agent_state/e2e/results.md                          No FAILED workflows
Reconciliation C (spec↔impl) agent_state/reconciliation/phase-${PHASE}/specs_vs_impl.md   Summary = PASS (no MISSING rows)
Reconciliation D (spec↔tests)agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.md  No HIGH-priority untested behaviors
Code review I                agent_state/phases/${PHASE}/reports/code_review_I.md   No BLOCKING issues
Code review II               agent_state/phases/${PHASE}/reports/code_review_II.md  No architecture violations
Security review              agent_state/phases/${PHASE}/reports/security_review.md  No HIGH severity findings
Acceptance tests             agent_state/phases/${PHASE}/reports/acceptance_report.md   All in-scope use cases: PASS
```

**E2E gate is active only when `PHASE_PLAN.md` has a non-empty `e2e_workflows_unlocked` list.**

If any gate item fails: surface to user with specific blocker text, file location, and the exact failing entry. Do not proceed to Step 7.

### Write gate files

```bash
mkdir -p agent_state/phases/${PHASE}
touch agent_state/phases/${PHASE}/gate.passed
```

Write `agent_state/phases/${PHASE}/manifest.json` — the handshake for the next phase:

```json
{
  "phase": N,
  "goal": "<from PHASE_PLAN.md>",
  "completed_at": "<ISO 8601 timestamp>",
  "brd_requirements_met": ["FR-001", "FR-002", "NFR-PERF-01"],
  "acceptance_tests": {
    "use_cases_total": 5,
    "use_cases_passed": 5,
    "personas_exercised": ["Admin User", "End User"],
    "seed_data": "agent_state/phases/N/test-data/generated-seed.yaml"
  },
  "artifacts": {
    "specs":      ["docs/design/phases/N/specs/auth-flow.md"],
    "code":       ["src/services/auth.go", "src/handlers/auth.go"],
    "migrations": ["migrations/001_add_users.sql"],
    "tests":      ["src/services/auth_test.go", "tests/integration/auth_test.go"],
    "api_routes": ["POST /api/v1/auth/login", "POST /api/v1/auth/logout"]
  },
  "test_results": {
    "unit": {
      "status": "passed",
      "total": 24,
      "passed": 24,
      "failed": 0,
      "report": "agent_state/phases/N/reports/unit_tests.md"
    },
    "integration": {
      "status": "passed",
      "total": 8,
      "passed": 8,
      "failed": 0,
      "report": "agent_state/phases/N/reports/integration_tests.md"
    },
    "e2e": {
      "status": "passed | not_run",
      "total": 3,
      "passed": 3,
      "failed": 0,
      "report": "agent_state/e2e/results.md"
    }
  },
  "known_issues":    [],
  "carried_forward": []
}
```

---

## Step 6b — Documentation (runs in parallel with gate file writes)

**Agent:** `documentation_agent`

Generates or updates developer-facing documentation for all artifacts produced this phase:
- API endpoint docs (OpenAPI/Swagger update or equivalent)
- Updated `README.md` sections for new components
- Any doc annotations from code review comments

Output: `agent_state/phases/${PHASE}/reports/documentation_update.md` — summary of what was added/updated.

Does NOT block gate passage. Runs in parallel with gate file writes.

---

## Step 7 — Report

```
✅ Phase N complete

  Implemented:
    Backend: N services, N repositories, N API routes
    UI:      N screens (or: not a UI phase)
    DB:      N migrations applied

  Tests:
    Unit:        X/X passed
    Integration: X/X passed
    E2E:         X/X passed (or: not run this phase)

  Reconciliation:
    Spec ↔ Impl:   PASS (or: N missing, N unspecced flagged)
    Spec ↔ Tests:  PASS (or: N untested HIGH behaviors)

  Acceptance:
    Use cases:   X/X passed  (FR-001, FR-002, FR-003)
    Personas:    [Admin User, End User]
    Seed data:   agent_state/phases/N/test-data/generated-seed.yaml

  Reviews:
    Code style:    PASS (or: N known issues logged)
    Architecture:  PASS
    Security:      PASS

  Gate: agent_state/phases/N/gate.passed ✅
  Manifest: agent_state/phases/N/manifest.json ✅

  ▶ Next: /plan --phase=N+1
  ▶ After all phases: /accept (global acceptance across full product)
```
