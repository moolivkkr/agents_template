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
  - name: force_gate
    required: false
    default: false
    description: "Force gate to pass even with failures (e.g. known test flakes). Writes gate.passed with ⚠ FORCED flag. Use with caution."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode — all escalations use recommended defaults. Gate failures auto-fix (max 3 cycles) then force-gate with logging. No user prompts."
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
| Step 3f Optimize (per agent) | ~20K | phase_context.md + git diff for this phase only + skill pack §patterns |
| Step 3g Re-test | ~10K | test commands only — no new code reading needed |
| Step 4 Review | ~20K | code diff this phase only (not full src/) + skill pack §patterns section |
| Step 5 Acceptance | ~15K | phase_context.md §requirements + acceptance criteria + seed data |
| Step 6 Gate | ~8K | report file first 20 lines each (summary rows) — not full report content |

Note: `phase_context.md` is 6-8K but replaces 30-70K of BRD + IMPL_GUIDELINES. Loading it in every step is intentional and correct.

---

## Pipeline Anti-Rationalization Guard

Before skipping ANY step, shortcutting ANY gate, or accepting partial results, review this table.

| Your Internal Reasoning | Correct Response |
|---|---|
| "Tests pass, so the implementation is correct" | Tests verify what the test author thought to check. Specs define what MUST exist. Run reconciliation. |
| "This is a simple phase, I can skip the audit step" | Simple phases are where assumptions hide. Run the audit. |
| "The gate has only one minor blocker, I'll pass it" | A blocker is a blocker. Fix it or use `--force_gate` with explicit user approval. |
| "I already reviewed this code when I wrote it" | You are the author. Authors don't find their own bugs. The reviewers are separate agents for a reason. |
| "Optimization isn't needed this phase — there's barely any code" | Optimization runs every phase. Even 5 lines of dead code compound over 10 phases. |
| "The previous phase tests still pass, no need for regression check" | Run them anyway. Silent import breakage is the #1 cross-phase regression. |
| "I'll skip the acceptance tests — unit and integration tests cover everything" | Unit/integration test code paths. Acceptance tests verify USER EXPERIENCE. They catch different bugs. |
| "I can combine the review stages to save time" | Review stages are separated for a reason. Spec compliance and code quality are DIFFERENT concerns. |

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

### Decision Log Protocol

All agents MUST log significant decisions to `agent_state/phases/${PHASE}/decision-log.md` (append-only):

```markdown
## Decision: <short title>
- **Agent:** <agent name>
- **Context:** <what prompted this decision>
- **Options considered:** <what alternatives existed>
- **Decision:** <what was chosen>
- **Rationale:** <why>
- **Impact:** <what this affects downstream>
```

Log when:
- Choosing between alternative implementations
- Deviating from spec (even slightly)
- Making an assumption not in the spec
- Choosing a library, pattern, or approach not prescribed

**Why:** Decisions made by agents in session 3 are invisible in session 7. The decision log creates persistent memory with accountability.

### Mid-Execution Escalation Protocol

When an agent encounters uncertainty that is NOT a full blocker but needs user input:

```json
{
  "type": "escalation",
  "agent": "<agent name>",
  "question": "<what needs clarification>",
  "options": [
    {"label": "A", "description": "...", "tradeoff": "..."},
    {"label": "B", "description": "...", "tradeoff": "..."}
  ],
  "recommendation": "A",
  "continueWithDefault": true
}
```

Write to `agent_state/phases/${PHASE}/escalations/<agent>-<N>.json`.

If `continueWithDefault: true`: proceed with the recommended option. The user can review and override later — the correction injects into the next task's carry-forward context.

If `continueWithDefault: false`: STOP and surface to user immediately.

**This replaces the binary "guess or block" with structured uncertainty handling.**

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

### Analysis Paralysis Guard (applies to ALL agents spawned by this command)

If an agent makes **5+ consecutive read-only tool calls** (Read, Grep, Glob, Bash with read-only commands) without any write action (Edit, Write, Bash with write commands), the agent MUST:

1. **Stop exploring** — do not make another read call
2. **State the blocker** — write a 1-line summary of what's preventing action:
   - "Blocker: can't find the file X expected by spec Y"
   - "Blocker: interface mismatch between service and handler"
3. **Take action** — either:
   - Write code to resolve the blocker
   - Write the blocker to the output file and return to the parent with `status: blocked`

**Why:** Agents get stuck in read-loops, consuming context tokens without making progress. 5 consecutive reads without a write is a strong signal of analysis paralysis.

**Exception:** `backend_audit_agent` and `ui_audit_agent` are read-only by design — this guard does NOT apply to audit agents.

---

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
| `docs/design/phases/${PHASE}/specs/data-contracts.md` | ~3-5K | Typed TypeScript interfaces for ALL API endpoints — ARRAY vs OBJECT explicit. Source of truth for response shapes. |
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

## Step 0.5 — Implementation Readiness Gate (HARD GATE)

**Before ANY implementation starts, verify these prerequisites.** This prevents wasted implementation cycles when specs are incomplete or misaligned.

```bash
# Check 1: Specs exist for this phase
SPECS_DIR="docs/design/phases/${PHASE}/specs"
SPEC_COUNT=$(ls ${SPECS_DIR}/*.md 2>/dev/null | wc -l)
if [ "$SPEC_COUNT" -eq 0 ]; then
  echo "⛔ BLOCKED: No specs found at ${SPECS_DIR}/. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 2: phase_context.md exists and is non-trivial
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
if [ ! -f "$CONTEXT_FILE" ] || [ $(wc -l < "$CONTEXT_FILE") -lt 20 ]; then
  echo "⛔ BLOCKED: phase_context.md missing or too short. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 3: VERIFICATION_REPORT.md exists (specs were verified against BRD)
VERIFY_FILE="docs/design/phases/${PHASE}/VERIFICATION_REPORT.md"
if [ ! -f "$VERIFY_FILE" ]; then
  echo "⛔ BLOCKED: No verification report. Run /plan --phase=${PHASE} to verify specs against BRD."
  exit 1
fi

# Check 4: BRD↔Spec reconciliation passed (no unresolved MISSING coverage)
RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
if [ -f "$RECON_FILE" ] && grep -q "MISSING" "$RECON_FILE"; then
  echo "⚠ WARNING: BRD↔Spec reconciliation has MISSING coverage. Review before implementing."
fi

# Check 5: data-contracts.md exists (typed API response shapes)
CONTRACTS_FILE="docs/design/phases/${PHASE}/specs/data-contracts.md"
if [ ! -f "$CONTRACTS_FILE" ]; then
  echo "⚠ WARNING: data-contracts.md missing. API↔UI binding errors likely. Run /plan --phase=${PHASE} Step 2b."
fi
```

**If any check fails:** STOP. Do not proceed to Step 1. Surface the specific failure and recommend `/plan --phase=${PHASE}`.

**Anti-rationalization:** "The specs are good enough to start" → No. Incomplete specs produce incomplete implementations that fail at acceptance tests. Fix the specs first.

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

Wave 1.5 (sequential gate — validates migrations before applying):
  └─ Migration Validation → dry-run migrations against test DB
      Checks:
      1. Migration files parse without syntax errors
      2. UP migration applies cleanly to empty test DB
      3. DOWN migration reverses the UP cleanly
      4. UP re-applies after DOWN (idempotency)
      If validation fails → block Wave 2, surface error to migration_agent for fix (max 1 retry)

Wave 2a (sequential — api_developer depends on backend service interfaces):
  └─ backend_developer  → domain models, services, repositories
       ↓ writes manifest with service method return types (list/single/none)

Wave 2a.5 (BUILD CHECK — catches type errors before api_developer starts):
  └─ Build verification: compile/typecheck the codebase
       go build ./... | tsc --noEmit | python -m py_compile (per tech stack)
       If FAILS → route back to backend_developer for fix (max 1 retry)

Wave 2b (depends on 2a passing build):
  └─ api_developer      → API handlers, routes, middleware, DTOs, api-contracts.md
       ↓ reads data-contracts.md from /plan as MANDATORY source of truth for response shapes
       ↓ api-contracts.md is DERIVED from data-contracts.md (validates, doesn't reinvent)
       ↓ if api-contracts.md shapes differ from data-contracts.md → BLOCKER
       ↓ reads backend_developer manifest to pick respondList/respondOne/respondError

Wave 2.5 (sequential gate, UI phases only):
  └─ Contract Validation → verify api-contracts.md exists, all endpoints documented, shapes are unambiguous

Wave 2.75 (SMOKE TEST — before expensive UI implementation):
  └─ Quick smoke test: does the app start? Does GET /health respond?
       docker compose up -d && curl -sf http://localhost:PORT/health
       If FAILS → route back to api_developer for fix (max 1 retry)
       This catches catastrophic failures before spending tokens on UI + test agents

Wave 3 (parallel, UI phases only — BLOCKED until Wave 2.75 passes):
  └─ ui_developer       → screen implementation from UI specs + api-contracts.md + data-contracts.md

Wave 4 (parallel — test agents read BOTH specs AND implementation code):
  ├─ unit_test_agent     → unit tests for all new code (reads actual functions, not just specs)
  └─ integration_test_agent → integration tests for service↔infra + contract shape tests
```

Each agent:
1. Reads ALL Step 0 context + its specific spec files
2. Reads its activated skill pack (`.claude/skills/languages/{{LANG}}.md` etc.)
3. Implements only what is in scope for this phase (prev manifest shows what exists)
4. Writes an agent-level manifest to `agent_state/phases/${PHASE}/<agent>/manifest.json`

---

## Step 2.5 — API Contract Validation (UI phases only)

**When:** `frontend.enabled = true` in IMPLEMENTATION_GUIDELINES AND this phase includes UI screens
**Runs after:** Wave 2 (backend_developer + api_developer complete)
**Blocks:** Wave 3 (ui_developer will NOT start until this passes)

Validate that `api_developer` produced a complete, unambiguous contract artifact:

```bash
CONTRACT_FILE="docs/design/phases/${PHASE}/specs/api-contracts.md"
```

**Checks (inline — no separate agent needed):**

1. **File exists:** `api-contracts.md` must exist and be non-empty
2. **All routes covered:** every route in `agent_state/phases/${PHASE}/api_developer/manifest.json` must have a matching entry in `api-contracts.md`
3. **Shape unambiguity:** for each endpoint entry:
   - Response shows explicit `"data": [...]` (array) or `"data": {...}` (object) — not just `"data": ...`
   - Empty state documented (list: `[]`, single: `null`)
   - All fields have types (no untyped `"field": "object"`)
4. **Data contract compliance:** every endpoint in `api-contracts.md` matches the TypeScript interface in `data-contracts.md` from /plan:
   - Field names match exactly
   - Array vs object matches exactly
   - If mismatch: `⚠ api-contracts.md GET /api/v1/users returns data as object, but data-contracts.md defines it as User[] (array)`
   - Route back to `api_developer` for fix (max 1 retry)
5. **Wireframe cross-reference:** for each wireframe API binding (`| Component | Endpoint | Fields Used |`):
   - The endpoint exists in `api-contracts.md`
   - The fields referenced exist in the contract's response shape
   - List vs single matches what the UI component expects (e.g., a table expects an array, a detail view expects an object)

**If validation fails:**
- Surface specific mismatches: `⚠ Wireframe <screen>.wireframe.md binds <Component> to GET /api/v1/items expecting array, but api-contracts.md shows data as object`
- Route back to `api_developer` for contract fix (max 1 retry)
- After fix: re-validate → then proceed to Wave 3

**If validation passes:**
```
✅ API Contract Validation — PASS
   Endpoints documented: N/N
   Shape checks: all unambiguous
   Wireframe cross-refs: all matched
   → Proceeding to Wave 3 (ui_developer)
```

---

## Step 3 — Tests

### Step 3a — Unit Tests
**Agent:** Generated `unit_test_agent`

Runs unit tests. On failure:
- Diagnoses root cause
- Fixes implementation (not the tests)
- Reruns
- **Max 3 attempts** → then surfaces unresolved failures with reproduction steps

### Step 3a.5 — Cross-Phase Regression (PHASE > 1 only)

**When:** PHASE > 1 — verify this phase's code didn't break previous phases
**Skip if:** PHASE = 1 (nothing to regress against)

Run ALL unit tests from previous phases (not just this phase's tests):
```bash
# Run full test suite, not just new tests
<test_command> ./...  # or equivalent full-suite command from IMPLEMENTATION_GUIDELINES
```

If previous-phase tests fail:
- Identify which test broke and which new code caused it
- Fix the regression in this phase's code (do NOT modify previous phase tests)
- Re-run → max 2 attempts → surface to user if unresolvable
- Log in report: `agent_state/phases/${PHASE}/reports/regression_check.md`

This prevents silent breakage where Phase 3 code compiles and passes its own tests but breaks Phase 1 behavior.

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

## Step 3d + 3e — Reconciliation (PARALLEL)

Run BOTH reconciliation agents simultaneously — they read different inputs and don't depend on each other.

```
Step 3d+3e (PARALLEL):
  ├─ spec_impl_reconciler  → specs ↔ implementation (4-level verification)
  └─ spec_test_reconciler  → specs ↔ test coverage
```

### 3d: Specs ↔ Implementation (`spec_impl_reconciler`)

Validates both directions with 4-level verification (Existence → Substantiveness → Wiring → Data Flow):
- **Forward:** spec-defined behaviors missing from the implementation
- **Reverse:** unspecced implementation (behaviors added without spec justification)

Output: `agent_state/reconciliation/phase-N/specs_vs_impl.md`

Missing implementations = **BLOCKER** (fix before acceptance tests).
Unspecced implementations = **LOGGED** with count in gate report. Not auto-blocking, but:
- If unspecced count > 0: gate report surfaces them with: `⚠ N unspecced implementations found — review before next phase`
- Each unspecced item is classified: `technical_necessity` (e.g., error handler), `scope_creep` (feature not in spec), or `test_helper`
- `scope_creep` items surfaced to user with recommendation: add to BRD or remove
- Manifest `carried_forward[]` includes unresolved unspecced items for next phase audit

### 3e: Specs ↔ Tests (`spec_test_reconciler`)

Validates both directions:
- **Forward:** spec-defined edge cases and behaviors with no test coverage
- **Reverse:** tests that test behaviors not in any spec

Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md`

HIGH-priority untested behaviors = blocker.
MEDIUM/LOW = logged as known gaps.

---

## Step 3f — Code Optimization (MANDATORY)

**Runs after:** All tests pass (Step 3a-3c) AND reconciliation complete (Step 3d-3e)
**Runs before:** Code review (Step 4) — reviewers see clean, optimized code
**Mandatory:** Yes — runs every phase. Produces a report even if zero changes made.

### Why mandatory

Dead code and redundant patterns accumulate across phases. Each agent generates code independently — backend_developer, api_developer, and ui_developer don't coordinate on shared utilities or know what the other has deprecated. Without cleanup at every phase, technical debt compounds and review cycles get longer.

### Scope Lock (CRITICAL SAFETY RULE)

Optimization ONLY touches files that were created or modified in THIS phase. Never modify code from previous phases — it has already passed its own gate.

```bash
# Scope = only files changed since last phase gate
SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null || git diff --name-only HEAD~50..HEAD)
```

### Pre-optimization snapshot

Before any optimization starts, capture the current state:

```bash
# Tag the pre-optimization state for safe rollback
git tag "phase-${PHASE}-pre-optimize" HEAD
```

If ALL optimizations need to be reverted:
```bash
git reset --hard "phase-${PHASE}-pre-optimize"
```

### Execution — parallel backend + UI tracks

```
Step 3f (parallel):
  ├─ code_optimizer         → backend/API dead code removal + optimization
  │                           Scope: src/domain/, src/services/, src/repositories/, src/api/, src/errors/
  │
  └─ ui_code_optimizer      → UI dead code removal + optimization (if frontend.enabled = true)
                              Scope: src/ui/, src/components/, src/hooks/, src/pages/, src/styles/
```

**Agent:** `code_optimizer` — always runs
**Agent:** `ui_code_optimizer` — runs only if `frontend.enabled = true`

Both agents follow the same safety protocol:
1. **Pass 1 — Dead code removal** (safe — removing unused code can't change behavior)
2. **Pass 2 — Code optimization** (risky — changes code paths)
3. Each change committed individually for granular revert
4. Each change must include the files affected and what was changed

**Outputs:**
- `agent_state/phases/${PHASE}/reports/code_optimization.md` — backend/API optimization report
- `agent_state/phases/${PHASE}/reports/ui_code_optimization.md` — UI optimization report (if frontend)

---

## Step 3g — Post-Optimization Test Re-run (CONDITIONAL SAFETY GATE)

**Runs after:** Step 3f optimization completes
**Purpose:** Verify that NO optimization introduced a regression
**Skip if:** Both optimizers report zero changes (no dead code removed, no optimizations applied). Log: "Step 3g skipped — zero optimization changes."

If ANY optimization was applied:

### Execution

Re-run ALL test tiers that passed in Step 3a-3c:

```
Re-run 3g.1: Unit tests           → must still pass
Re-run 3g.2: Integration tests    → must still pass
Re-run 3g.3: E2E tests            → must still pass (if they ran in 3c)
```

### On failure

If ANY test fails after optimization:

1. **Identify which optimization caused the failure** — check git log since `phase-${PHASE}-pre-optimize` tag
2. **Diagnose and fix first** (don't blindly revert):
   - Read test failure output → identify root cause (missing import, broken caller, type mismatch)
   - Apply targeted fix → commit as `fix: resolve <issue> after <optimization>`
   - Re-run failing test → if passes, continue
3. **If fix doesn't work** — try broader fix (check all callers of changed code, fix all affected)
4. **If still failing after 2 fix attempts** — revert the specific optimization commit + fix attempts:
   ```bash
   git revert <commit-hash> --no-edit
   ```
5. **Max 3 revert cycles** — if tests still fail after 3 optimization reverts:
   - Reset to pre-optimization state: `git reset --hard phase-${PHASE}-pre-optimize`
   - Log in report: "⚠ All optimizations reverted — optimization introduced non-recoverable regression"
   - Pipeline continues (optimization failure is NOT a pipeline blocker, but IS logged in gate)
6. **Update the optimization report** with fixed and reverted items

### Output

Updates `agent_state/phases/${PHASE}/reports/code_optimization.md` with:
```markdown
## Post-Optimization Test Re-run
- Unit tests: PASS (X/X)
- Integration tests: PASS (X/X)
- E2E tests: PASS (X/X) | not run
- Reverted optimizations: N (or: none)
- Status: CLEAN | PARTIAL (N optimizations reverted) | REVERTED (all rolled back)
```

### Gate impact

The Phase Gate (Step 6) checks the post-optimization test status:
- `CLEAN` → no issues, all optimizations kept
- `PARTIAL` → some optimizations reverted, remaining tests pass → acceptable
- `REVERTED` → all rolled back, code is at pre-optimization state → acceptable (logged as known issue)
- Tests still failing → **BLOCKER** (should not happen if revert protocol followed)

---

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

**On mismatch:**
- Route back to implementation agent for fix (max 1 round)
- Log as `spec_deviation` with details

**Output:** `agent_state/phases/${PHASE}/reports/spec_compliance_review.md`

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
- `dependency_scanner`: CRITICAL/HIGH with available fixes must apply. Auto-applies non-breaking fixes (`npm audit fix` etc.). Breaking fixes flagged for user decision.

Reports written to `agent_state/phases/${PHASE}/reports/`:
- `spec_compliance_review.md` (Stage 4a)
- `code_review_I.md` (Stage 4b)
- `code_review_II.md` (Stage 4b)
- `security_review.md` (Stage 4c)
- `dependency_scan.md` (Stage 4c)

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
Spec compliance              agent_state/phases/${PHASE}/reports/spec_compliance_review.md   COMPLIANT — no missing implementations
Unit tests                   agent_state/phases/${PHASE}/reports/unit_tests.md   No FAILED tests
Integration tests            agent_state/phases/${PHASE}/reports/integration_tests.md   No FAILED tests
E2E tests (if unlocked)      agent_state/e2e/results.md                          No FAILED workflows
Reconciliation C (spec↔impl) agent_state/reconciliation/phase-${PHASE}/specs_vs_impl.md   No MISSING implementations AND unspecced items acknowledged (count logged)
Reconciliation D (spec↔tests)agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.md  No HIGH-priority untested behaviors
Code optimization            agent_state/phases/${PHASE}/reports/code_optimization.md     Post-optimization tests: PASS (CLEAN or PARTIAL accepted)
UI code optimization         agent_state/phases/${PHASE}/reports/ui_code_optimization.md  Post-optimization tests: PASS (if frontend.enabled; skip otherwise)
Code review I                agent_state/phases/${PHASE}/reports/code_review_I.md   No BLOCKING issues
Code review II               agent_state/phases/${PHASE}/reports/code_review_II.md  No architecture violations
Security review              agent_state/phases/${PHASE}/reports/security_review.md  No HIGH severity findings
Acceptance tests             agent_state/phases/${PHASE}/reports/acceptance_report.md   All in-scope use cases: PASS
```

**E2E gate is active only when `PHASE_PLAN.md` has a non-empty `e2e_workflows_unlocked` list.**

If any gate item fails: surface to user with specific blocker text, file location, and the exact failing entry. Do not proceed to Step 7.

### Gate Failure Recovery Procedure

When the gate fails, DO NOT delete any phase files. Follow this sequence:
1. **Identify the blocker** — read the specific report file and find the failing entry
2. **Fix the root cause** — re-run the failing agent (e.g., fix test → re-run unit_test_agent)
3. **Re-run only the failed check** — no need to re-run the entire pipeline
4. **Re-evaluate the gate** — re-read all report files and check conditions again
5. If gate now passes → write `gate.passed` and manifest

**DO NOT:**
- Delete `agent_state/phases/${PHASE}/` — it contains all the work done so far
- Re-run the entire `/develop` pipeline — only re-run the failing step
- Modify tests to force them to pass — fix the implementation instead

### --force-gate Override

If `--force_gate` flag is set AND the gate has failures:
1. Write `gate.passed` with a warning header:
   ```
   ⚠ FORCED GATE — ${N} blockers overridden by user at ${TIMESTAMP}
   Overridden items: [list of failed gate items]
   ```
2. Add overridden failures to manifest `known_issues[]` with `"severity": "gate_override"`
3. Print warning: `⚠ Gate forced with N unresolved blockers — review before release`
4. Next phase will show these in its audit report as critical carried-forward items

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
  "optimization": {
    "backend": {
      "status": "CLEAN | PARTIAL | REVERTED",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "lines_reduced": 0,
      "report": "agent_state/phases/N/reports/code_optimization.md"
    },
    "ui": {
      "status": "CLEAN | PARTIAL | REVERTED | not_run",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "report": "agent_state/phases/N/reports/ui_code_optimization.md"
    },
    "post_optimization_tests": "PASS | PASS_WITH_REVERTS | not_run"
  },
  "known_issues":    [],
  "carried_forward": [],
  "carried_forward_policy": "Items in carried_forward[] MUST be addressed within 2 phases. If an item survives 3 phases: it becomes a BLOCKING gate item in the 3rd phase — fix or explicitly remove from scope via /review --change-request."
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

  Optimization:
    Dead code removed: N items (-X lines)
    Optimizations applied: N (code reduction: X, performance: Y, structural: Z)
    Flagged for review: N items

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
