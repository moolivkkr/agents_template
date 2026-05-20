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

**⚠ Concurrent access:** This command assumes a single developer per phase. If two developers run `/develop --phase=2` simultaneously, file conflicts will occur in `agent_state/phases/2/` and git commits may conflict. To coordinate: use separate phases, or ensure only one developer runs `/develop` at a time for a given phase number.

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

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

**One rule:** Never skip a step, shortcut a gate, or accept partial results — even if it "seems fine." If you're tempted to skip, that's exactly when the step matters most. The table below lists specific temptations and their correct responses.

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

## Phase Re-Development Protocol

When re-developing a phase (e.g., `gate.passed` was removed, or `/reset-phase` was run):

### 1. Before re-running

- Git tag current state: `git tag "phase-${PHASE}-attempt-${ATTEMPT}" -m "Phase ${PHASE} attempt ${ATTEMPT}: $(date)"`
  - `ATTEMPT` is determined by counting existing `phase-${PHASE}-attempt-*` tags + 1
- Archive previous reports: `mv agent_state/phases/${PHASE}/reports agent_state/phases/${PHASE}/reports.attempt-${ATTEMPT}`
- Clear ready signals: `rm -f agent_state/phases/${PHASE}/.*_ready`

```bash
# Detect attempt number
ATTEMPT=$(git tag -l "phase-${PHASE}-attempt-*" | wc -l | tr -d ' ')
ATTEMPT=$((ATTEMPT + 1))

# Tag current state
git tag "phase-${PHASE}-attempt-${ATTEMPT}" -m "Phase ${PHASE} attempt ${ATTEMPT}: $(date)"

# Archive previous reports (if they exist)
if [ -d "agent_state/phases/${PHASE}/reports" ]; then
  mv "agent_state/phases/${PHASE}/reports" "agent_state/phases/${PHASE}/reports.attempt-${ATTEMPT}"
fi

# Clear ready signals
rm -f agent_state/phases/${PHASE}/.*_ready
```

### 2. During re-run

- All agents run fresh (no caching from previous attempt)
- Previous attempt's code is NOT automatically reverted (agents build on existing code)
- If clean slate needed: user should `git reset` to the phase tag first (use `/reset-phase --hard`)

### 3. After completion

- Manifest includes: `"attempt": N, "previous_attempts": ["phase-N-attempt-1", "phase-N-attempt-2"]`
- Gate report includes diff from previous attempt:
  ```
  ## Changes from Previous Attempt
  - Attempt 1: 3 blockers (auth flow, CORS, migration order)
  - Attempt 2: 1 blocker (migration order — fixed by reordering)
  - Attempt 3: PASSED ✅
  ```

### Detection

At the start of Step 0, detect if this is a re-run:
```bash
if [ -d "agent_state/phases/${PHASE}/reports" ] || [ -d "agent_state/phases/${PHASE}/reports.attempt-1" ]; then
  echo "⚠ Phase ${PHASE} re-development detected — archiving previous attempt"
  # Execute pre-run archival steps above
fi
```

---

## Step 0 — Orient

### Detect current phase
```bash
LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}
echo "▶ Running Phase $PHASE"
```

### Failure Pattern Detection

Check if previous attempts at this phase failed at specific steps:

```bash
# Check for previous gate.failed files
PREV_FAILURES=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null)
if [ -n "$PREV_FAILURES" ]; then
  echo "⚠ Phase ${PHASE} has previous failure(s):"
  for f in $PREV_FAILURES; do
    BLOCKERS=$(python3 -c "import json; d=json.load(open('$f')); print(', '.join(b.get('gate_item','?') for b in d.get('blockers',[])))" 2>/dev/null)
    echo "  - $(basename $f): blocked by $BLOCKERS"
  done
  echo "  → Extra scrutiny will be applied to previously-failing steps"
fi
```

When a step that previously failed is reached:
- Log: `⚠ Step ${STEP} failed in previous attempt — applying extra verification`
- For test steps: run tests TWICE (once normally, once with verbose output)
- For review steps: lower the threshold for BLOCKING (MEDIUM → BLOCKING for previously-failing areas)
- For gate: explicitly verify previously-blocking items are resolved before checking new items

### Phase Lock (Advisory)

Before starting implementation, check for and create a lock:

```bash
LOCK_FILE="agent_state/phases/${PHASE}/.lock"
if [ -f "$LOCK_FILE" ]; then
  LOCK_OWNER=$(cat "$LOCK_FILE" | head -1)
  LOCK_TIME=$(cat "$LOCK_FILE" | tail -1)
  echo "⚠ Phase ${PHASE} is locked by ${LOCK_OWNER} since ${LOCK_TIME}"
  echo "  If this is stale, remove with: rm ${LOCK_FILE}"
  echo "  Proceeding may cause file conflicts in agent_state/phases/${PHASE}/"
  # In --auto mode: STOP. In interactive mode: ask user to confirm.
fi

# Create lock
echo "$(whoami)@$(hostname)" > "$LOCK_FILE"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOCK_FILE"
```

Release lock at the end of Step 6 (gate write):
```bash
rm -f "agent_state/phases/${PHASE}/.lock"
```

This is advisory — it warns but doesn't prevent. Two developers CAN override, but they're warned.

### Gate check
If PHASE > 1 and `agent_state/phases/$((PHASE-1))/gate.passed` is missing:
**STOP** — `Phase $((PHASE-1)) gate not found. Run /develop --phase=$((PHASE-1)) first.`

If `docs/design/phases/${PHASE}/INDEX.md` is missing:
**Auto-run `/plan --phase=${PHASE}` first**, then continue.

### Load previous phase context
Read `agent_state/phases/$((PHASE-1))/manifest.json` (if PHASE > 1):
- Surface `carried_forward[]` issues at the top of the Step 1 audit report
- Note existing code paths, API routes, DB schema from previous phases

### Cross-Phase Contract Validation (Phase > 1)

Before starting Phase N implementation, validate that data contracts are consistent with the previous phase's actual outputs:

1. Read `docs/design/phases/${PHASE}/specs/data-contracts.md`
2. Compare against Phase N-1 manifest's `api_routes` and `artifacts.code` to identify endpoints/fields that changed
3. If `data-contracts.md` references endpoints or fields that were modified, renamed, or removed in Phase N-1:
   - **BLOCKING** — data contracts may be stale. Re-run `/plan --phase=${PHASE}` or manually update `data-contracts.md`.
4. If Phase N specs extend an endpoint from Phase N-1 (e.g., adding fields to an existing response):
   - Verify the existing fields in `data-contracts.md` match what Phase N-1 actually implemented (check the code, not just the spec)
   - If mismatch: surface as `⚠ STALE CONTRACT: data-contracts.md says X, but Phase N-1 code returns Y`
5. **Schema evolution validation** — for endpoints that exist in BOTH Phase N-1 and Phase N contracts:
   - Phase N-1 response shape must be a **subset** of Phase N response shape (additive changes only)
   - If Phase N removes or renames a field from Phase N-1: **BLOCKING** — this breaks Phase N-1 consumers
   - If Phase N changes a field type (e.g., `string` → `number`): **BLOCKING** — type mismatch
   - If Phase N adds new required fields to a request: **WARNING** — Phase N-1 callers won't send them
   - Compare actual TypeScript interfaces from both `data-contracts.md` files, not just endpoint names
   - Surface any breaking changes: `⛔ BREAKING CHANGE: GET /users/:id field 'role' changed from string to enum — Phase N-1 code returns string`

### Breaking Change Detection (HARD BLOCK — not warning)

When comparing Phase N data-contracts.md against Phase N-1 actual implementation:

- **Field REMOVED from response** → ⛔ HARD BLOCK: `Field '${field}' was in Phase ${N-1} response but missing in Phase ${N} contract. This breaks Phase ${N-1} consumers.`
- **Field RENAMED** → ⛔ HARD BLOCK: `Field '${oldName}' renamed to '${newName}'. Phase ${N-1} consumers reference the old name.`
- **Field TYPE CHANGED** → ⛔ HARD BLOCK: `Field '${field}' changed from ${oldType} to ${newType}. Type mismatch.`
- **Field ADDED (optional)** → ✅ OK (additive, backward-compatible)
- **Field ADDED (required to request)** → ⚠ WARNING: Phase ${N-1} callers won't send this field

Hard blocks CANNOT be force-gated. Fix the contract or provide a migration path (deprecated field alias).

```bash
# Quick staleness check
if [ $PHASE -gt 1 ]; then
  PREV_MANIFEST="agent_state/phases/$((PHASE-1))/manifest.json"
  CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$PREV_MANIFEST" ] && [ -f "$CONTRACTS" ]; then
    echo "Validating data contracts against Phase $((PHASE-1)) manifest..."
    # Extract api_routes from previous manifest and verify they still exist in contracts
    python3 -c "
import json, sys
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
contracts = open('$CONTRACTS').read()
stale = [r for r in routes if r.split()[-1] not in contracts]
if stale:
    print('⚠ STALE CONTRACTS — routes in previous manifest not found in data-contracts.md:')
    for r in stale: print(f'  - {r}')
    sys.exit(1)
print('✅ Data contracts consistent with Phase $((PHASE-1)) manifest')
" || echo "⚠ Contract validation failed — review data-contracts.md before proceeding"
  fi
fi
```

### Phase Context Staleness Detection

Before loading `phase_context.md`, verify it's not stale relative to the BRD:

```bash
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
BRD_FILE="docs/BRD.md"
if [ -f "$CONTEXT_FILE" ] && [ -f "$BRD_FILE" ]; then
  CONTEXT_MTIME=$(stat -f %m "$CONTEXT_FILE" 2>/dev/null || stat -c %Y "$CONTEXT_FILE")
  BRD_MTIME=$(stat -f %m "$BRD_FILE" 2>/dev/null || stat -c %Y "$BRD_FILE")
  if [ "$BRD_MTIME" -gt "$CONTEXT_MTIME" ]; then
    echo "⚠ WARNING: BRD was modified AFTER phase_context.md was generated."
    echo "  BRD modified:     $(date -r $BRD_MTIME 2>/dev/null || date -d @$BRD_MTIME)"
    echo "  Context generated: $(date -r $CONTEXT_MTIME 2>/dev/null || date -d @$CONTEXT_MTIME)"
    echo "  Consider re-running /plan --phase=${PHASE} to refresh phase_context.md"
    echo "  Or proceed with caution — new BRD requirements may be missing from this phase."
  fi
fi
```

If staleness detected and the BRD diff includes new FR-* IDs not in `phase_context.md`: **BLOCKING** — re-run `/plan --phase=${PHASE}`.
If staleness detected but BRD changes are editorial (no new FR-*): **WARNING** — proceed with caution.

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

### Spec Amendment Protocol (Intentional Deviations)

When an implementation agent intentionally deviates from a spec:

1. **Log the deviation** in decision-log.md:
   ```
   ## Spec Deviation: <component> — <what changed>
   - **Spec says:** <original spec behavior>
   - **Implementation does:** <actual behavior>
   - **Rationale:** <why the deviation was necessary>
   - **Impact:** <what downstream artifacts need updating>
   ```

2. **Auto-update the spec** (append, don't overwrite):
   ```markdown
   ## Implementation Notes (auto-generated)
   > ⚠ Deviation from original spec — see decision-log.md
   > - <what changed and why>
   > - Original behavior preserved in section above
   ```

3. **Flag for reconciliation:** spec_impl_reconciler treats documented deviations as ACKNOWLEDGED (not MISSING).

This prevents specs from going stale after implementation while preserving the original design intent.

### Mid-Execution Escalation Protocol

When an agent encounters uncertainty, conflicting options, or missing data:

**LOW impact** (reversible, single-option): continue with `continueWithDefault: true`
```json
{ "type": "escalation", "impact": "LOW", "recommendation": "A", "continueWithDefault": true }
```

**MEDIUM/HIGH impact** (architecture, security, data model): escalate to Debate Team
```json
{
  "type": "debate_request",
  "from_agent": "<agent name>",
  "from_step": "<pipeline step>",
  "decision": "<what needs deciding>",
  "options": [
    { "id": "A", "label": "...", "initial_reasoning": "..." },
    { "id": "B", "label": "...", "initial_reasoning": "..." }
  ],
  "context": "<BRD refs, constraints, what's known>",
  "impact": "HIGH | MEDIUM",
  "domain": "architecture | security | data_model | feature",
  "blocking": true
}
```

Write to `agent_state/debates/<step>-<topic>.json`.

The `debate_moderator` picks it up and runs:
1. **Researchers** (parallel) — gather evidence for each option
2. **Advocates** (parallel, HIGH only) — argue for each option adversarially
3. **Arbitrator** — evaluates all arguments, produces scored verdict

Verdict written to `agent_state/debates/<topic>-verdict.json`. The requesting agent reads it and continues.

**This replaces guessing with researched, debated, scored decisions.**

### Escalation Circuit Breaker

Prevent runaway escalation loops that consume context and time:

- **Max escalations per step:** 3 — if a single step (e.g., Step 2 Implementation) triggers more than 3 debate requests, STOP escalating. Write remaining decisions to `agent_state/debates/unresolved.json` with recommended defaults.
- **In `--auto` mode:** continue with defaults for all unresolved decisions, but flag ALL as `"⚠ AUTO-RESOLVED — may need review"` in the decision log and manifest `known_issues[]`.
- **⛔ SECURITY ESCALATION EXCEPTION:** Escalations with `"domain": "security"` are NEVER auto-resolved. In `--auto` mode, security decisions MUST use the **hardened default** (the option that is MORE restrictive / MORE secure). Log as `"⚠ SECURITY — hardened default applied, review recommended"`. Security escalations include: auth patterns, token storage, IDOR mitigation, encryption, PII handling, CORS/CSRF config, rate limiting. If no clearly hardened default exists → EXIT auto mode for this decision and surface to user.
- **Max total escalations per phase:** 10 — if exceeded, EXIT auto mode entirely. Surface all unresolved decisions to the user with: `"⛔ Phase ${PHASE} exceeded escalation limit (10). Review agent_state/debates/unresolved.json before continuing."`
- **Max escalation depth:** 2 — if a debate triggers another debate (e.g., arbitrator can't decide and re-escalates), the second-level debate auto-resolves with the recommended default (except security — always hardened). A third-level escalation is NEVER allowed.

```json
// agent_state/debates/unresolved.json
{
  "phase": N,
  "unresolved_count": 4,
  "decisions": [
    {
      "topic": "cache_strategy",
      "from_agent": "backend_developer",
      "auto_resolved_with": "A",
      "confidence": "LOW",
      "reason": "escalation_limit_exceeded",
      "needs_review": true
    }
  ]
}
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

### Migration Failure Auto-Recovery

If UP migration fails:
1. Immediately run the DOWN migration for the failed file to restore schema consistency
2. Log the specific error: `⛔ Migration ${FILE} UP failed: ${ERROR}`
3. Log the rollback: `↩ Auto-rolled back ${FILE} DOWN to restore schema`
4. Route back to migration_agent with the specific error for fix (max 1 retry)
5. After fix: re-run UP → validate → proceed if success

If DOWN rollback also fails:
- STOP immediately — schema is now in an unknown state
- Surface: `⛔ CRITICAL: Migration UP failed AND DOWN rollback failed. Manual intervention required.`
- Write to agent_state/phases/${PHASE}/migration_failure.json with full error details
- Do NOT proceed to Wave 2

This prevents the common failure where Phase N migration adds a table, fails partway through,
and Phase N re-development tries to add the same table again.

Wave 2a (sequential — api_developer depends on backend service interfaces):
  └─ backend_developer  → domain models, services, repositories
       ↓ writes manifest with service method return types (list/single/none)

Wave 2a.5 (BUILD CHECK — catches type errors before api_developer starts):
  └─ Build verification: compile/typecheck the codebase
       go build ./... | tsc --noEmit | python -m py_compile (per tech stack)
       If FAILS → route back to backend_developer for fix (max 1 retry)

### Agent Handoff Protocol (Wave 2a → Wave 2b)

After backend_developer completes — **atomic write + verified ready signal:**
1. Write manifest to `.tmp` first: `agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
2. Validate JSON: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
3. If valid: atomic move: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not touch ready signal. Log error and retry manifest write (max 1 retry).
5. Verify report exists: `test -f agent_state/phases/${PHASE}/reports/backend_developer.md`
6. **Only after steps 1-5 succeed:** Touch ready signal: `touch agent_state/phases/${PHASE}/.backend_developer_VERIFIED`

```bash
# Atomic agent handoff — prevents downstream agents from reading partial manifests
MANIFEST_DIR="agent_state/phases/${PHASE}/backend_developer"
python3 -c "import json,sys; json.load(sys.stdin)" < "${MANIFEST_DIR}/manifest.json.tmp" && \
  mv "${MANIFEST_DIR}/manifest.json.tmp" "${MANIFEST_DIR}/manifest.json" && \
  touch "agent_state/phases/${PHASE}/.backend_developer_VERIFIED" || \
  { echo "⛔ backend_developer manifest invalid — blocking handoff"; exit 1; }
```

Before api_developer starts:
1. Check: `test -f agent_state/phases/${PHASE}/.backend_developer_VERIFIED` (**VERIFIED, not just ready**)
2. If missing: WAIT or FAIL — do not proceed with stale/missing data
3. Validate manifest is readable: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json`
4. Read `backend_developer/manifest.json` for service method return types

This pattern applies to ALL wave transitions where one agent depends on another's output. The **atomic write + verified ready signal** prevents race conditions where a downstream agent reads a partial or corrupt manifest.

Wave 2b (depends on 2a passing build + backend_developer ready signal):
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

### Test Attempt Tracking

When a test agent retries (attempt > 1), track ALL retry information for visibility:

1. Log: `"⚠ Test [test_name] required [N] attempts to pass"`
2. Add to manifest under test_results: `"flaky_tests": ["test_name (passed on attempt N)"]`
3. Add to gate report: `"⚠ FLAKY: [count] tests required multiple attempts"`
4. Carry forward: flaky tests appear in next phase's audit as known instability

```json
// In manifest.json test_results section:
"test_results": {
  "unit": {
    "status": "passed",
    "total": 24,
    "passed": 24,
    "failed": 0,
    "flaky_tests": [
      "TestCreateUser (passed on attempt 2)",
      "TestListResources (passed on attempt 3)"
    ],
    "report": "agent_state/phases/N/reports/unit_tests.md"
  }
}
```

**Why track flaky tests?** A test that needs 3 attempts to pass is a signal of non-deterministic behavior (race condition, timing dependency, test isolation failure). If the same test is flaky across 2+ phases, it becomes a reliability risk that compounds.

### Flaky Test Quarantine

When a test appears in `flaky_tests[]` across 2+ consecutive phases:

1. **Detect:** Check previous phase manifest's `flaky_tests[]`. If current phase has the same test name: it's chronically flaky.
2. **Quarantine:** Mark with `@flaky` tag/annotation (language-specific):
   - Go: `t.Skip("QUARANTINED: flaky across phases N-1, N")`
   - Python: `@pytest.mark.skip(reason="QUARANTINED: flaky")`
   - TypeScript: `test.skip('QUARANTINED: flaky')`
   - Java: `@Disabled("QUARANTINED: flaky")`
   - Rust: `#[ignore]`
3. **Log:** Add to manifest: `"quarantined_tests": ["TestName (flaky since phase N-1)"]`
4. **Track:** Quarantined tests appear in gate report as: `⚠ QUARANTINED: N tests skipped (flaky across 2+ phases)`
5. **Escalate:** If quarantined count > 5: surface to user as `⚠ Too many quarantined tests — investigate root cause`
6. **Unquarantine:** If a quarantined test passes 3 consecutive phases: auto-remove quarantine

This prevents flaky tests from blocking every phase while maintaining visibility.

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

### Step 3c.5 — Post-Implementation Re-Audit (CLOSED LOOP)

**Runs after:** All tests pass (Steps 3a-3c)
**Purpose:** Verify that gaps identified in the Step 1 audit were actually addressed by implementation

**Execution:**
1. Read the Step 1 audit report (`agent_state/phases/${PHASE}/audit_report.md`)
2. For each gap listed under "Missing Implementations" and "Broken/Incomplete Items":
   - Check if the gap is now resolved (code exists, tests pass)
   - If still missing: flag as `⚠ AUDIT GAP UNRESOLVED: <item>`
3. For each "Carried Forward Issue" from previous phase:
   - Check if addressed in this phase's implementation
   - If not addressed: flag as `⚠ CARRIED FORWARD STILL OPEN: <item>`

**Output:** `agent_state/phases/${PHASE}/reports/re_audit.md`

**Impact on gate:**
- Unresolved audit gaps are surfaced in the gate report as warnings (not blocking — tests are the real gate)
- Unresolved carried-forward items that are 2+ phases old become **BLOCKING** per the carried-forward policy

**Why this matters:** Without re-audit, the Step 1 audit report becomes "write-only" — gaps are detected but nobody verifies they were closed. This step closes that loop.

---

## Step 3d + 3e — Reconciliation (SEQUENTIAL — 3d before 3e)

Run reconciliation agents **sequentially** — `spec_test_reconciler` depends on `spec_impl_reconciler` output to distinguish "untested" from "unimplemented".

```
Step 3d (first):
  └─ spec_impl_reconciler  → specs ↔ implementation (4-level verification)
       ↓ writes: agent_state/reconciliation/phase-N/specs_vs_impl.md
       ↓ output includes list of MISSING implementations

Step 3e (after 3d completes):
  └─ spec_test_reconciler  → specs ↔ test coverage
       ↓ reads: specs_vs_impl.md to EXCLUDE unimplemented behaviors from "untested" count
       ↓ a behavior can't be untested if it's not implemented yet — that's a MISSING impl, not a test gap
```

**Why sequential:** If `spec_test_reconciler` runs in parallel with `spec_impl_reconciler`, it will flag "no test for behavior X" when behavior X isn't even implemented yet. This creates confusion about whether the gap is a test gap or an implementation gap. Running 3d first gives 3e the context to make accurate assessments.

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

**On mismatch (CLOSED LOOP):**
- Route back to implementation agent for fix (max 2 rounds)
- After fix: **re-run spec compliance check on the changed files** (not full review — targeted re-check)
- If mismatch persists after 2 rounds: log as `spec_deviation` with details → becomes gate blocker
- Log all deviations (fixed and unresolved) in report

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
- `security_review.md` (Stage 4b)
- `dependency_scan.md` (Stage 4b)
- `sast_scan.md` (Stage 4c)

### Stage 4c — Static Application Security Testing (parallel with review)

Run SAST scan on all code changed in this phase:

```bash
# Language-specific SAST (from IMPLEMENTATION_GUIDELINES)
# Go: govulncheck ./...
# Python: bandit -r src/ -f json
# TypeScript/JavaScript: semgrep --config auto src/
# Java: spotbugs or semgrep
# Rust: cargo audit

SAST_CMD=$(detect_sast_command)  # from IMPLEMENTATION_GUIDELINES
$SAST_CMD > agent_state/phases/${PHASE}/reports/sast_scan.md
```

Severity mapping:
- CRITICAL/HIGH → BLOCKING (must fix before gate)
- MEDIUM → WARNING (logged in known_issues)
- LOW → INFO (logged but not blocking)

If no SAST tool is configured in IMPLEMENTATION_GUIDELINES: skip with warning log.

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
SAST scan                    agent_state/phases/${PHASE}/reports/sast_scan.md        No CRITICAL or HIGH findings
Acceptance tests             agent_state/phases/${PHASE}/reports/acceptance_report.md   All in-scope use cases: PASS
```

**E2E gate is active only when `PHASE_PLAN.md` has a non-empty `e2e_workflows_unlocked` list.**

### Bug Severity Classification

All items in `known_issues[]` and `carried_forward[]` MUST have a severity level:

| Severity | Definition | Gate Impact | Carry-Forward Limit |
|----------|-----------|-------------|-------------------|
| `critical` | Data loss, security breach, complete feature broken | BLOCKS gate — must fix | 0 phases (fix immediately) |
| `high` | Major feature broken, significant UX degradation | BLOCKS gate — must fix | 1 phase max |
| `medium` | Minor feature broken, workaround exists | Does not block gate | 3 phases max |
| `low` | Cosmetic, minor inconvenience | Does not block gate | No limit (tracked) |

When severity is not explicitly set, default to `medium`.

Carry-forward enforcement:
- `critical` items that appear in `carried_forward[]` → ⛔ IMMEDIATE BLOCK, cannot proceed
- `high` items carried for >1 phase → becomes `critical` (auto-escalation)
- `medium` items carried for >3 phases → becomes `high` (auto-escalation)

If any gate item fails:
1. Write `gate.failed` with structured failure data (enables next-phase detection of "ran but failed" vs "never ran"):
   ```bash
   cat > agent_state/phases/${PHASE}/gate.failed <<EOF
   {
     "phase": ${PHASE},
     "failed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
     "blockers": [
       // list of failing gate items with details
     ],
     "attempt": ${ATTEMPT:-1}
   }
   EOF
   ```
2. Surface to user with specific blocker text, file location, and the exact failing entry.
3. Do not proceed to Step 7.

**Gate state machine (ternary):**
- `gate.passed` exists → phase completed successfully
- `gate.failed` exists (no `gate.passed`) → phase ran but has unresolved blockers
- Neither exists → phase has not been attempted yet
- Both exist → `gate.passed` wins (gate.failed is from a previous attempt)

When the Gate Failure Recovery Procedure resolves all blockers:
1. Write `gate.passed`
2. Rename `gate.failed` → `gate.failed.resolved` (preserve history, don't delete)

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
2. Write `gate.forced` with structured failure data:
   ```json
   {
     "phase": N,
     "forced_at": "<ISO 8601>",
     "blockers": [
       { "gate_item": "unit_tests", "details": "TestAuthFlow FAILED — flaky", "severity": "gate_override" },
       { "gate_item": "security_review", "details": "HIGH: IDOR in GET /users/:id", "severity": "gate_override" }
     ],
     "user_rationale": "<user's reason for forcing>"
   }
   ```
3. Add overridden failures to manifest `known_issues[]` with `"severity": "gate_override"`
4. Print warning: `⚠ Gate forced with N unresolved blockers — review before release`

### Forced Gate Carry-Forward Enforcement (HARD RULE)

When the NEXT phase starts (Phase N+1 Step 0):
1. Check: `test -f agent_state/phases/$((PHASE-1))/gate.forced`
2. If exists: read `gate.forced` and surface ALL blockers prominently:
   ```
   ⛔ FORCED GATE DETECTED — Phase $((PHASE-1)) passed with N unresolved blockers:
     - [blocker 1 details]
     - [blocker 2 details]
   These MUST be resolved in Phase ${PHASE} or explicitly re-deferred with --force_gate.
   ```
3. Phase N+1 audit (Step 1) MUST list each forced blocker as a **CRITICAL carried-forward item**
4. Phase N+1 gate (Step 6) adds an extra gate check:
   ```
   Forced gate resolution    agent_state/phases/$((PHASE-1))/gate.forced    All blockers resolved OR explicitly re-deferred
   ```
5. If a blocker survives **2 consecutive forced gates**: it becomes **PERMANENTLY BLOCKING** — cannot be force-gated again. Must fix or remove from scope via BRD change request.

**Anti-pattern:** Forcing gates across 3+ phases creates a project where nothing actually works. The 2-force limit prevents this.

### Manifest Write Protocol (Atomic)

All manifest writes MUST use atomic write protocol to prevent corrupt JSON from crashing downstream phases:

1. Write to `agent_state/phases/${PHASE}/manifest.json.tmp`
2. Validate: `cat manifest.json.tmp | python3 -c "import json,sys; json.load(sys.stdin)" && echo "valid" || echo "CORRUPT"`
3. If valid: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not proceed. Log error and retry write.

```bash
# Atomic manifest write
python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/manifest.json.tmp && \
  mv agent_state/phases/${PHASE}/manifest.json.tmp agent_state/phases/${PHASE}/manifest.json || \
  { echo "⛔ CORRUPT manifest — aborting"; exit 1; }
```

This protocol also applies to any agent-level manifest writes in `agent_state/phases/${PHASE}/<agent>/manifest.json` — always write to `.tmp`, validate, then `mv`.

### Schema Validation

After JSON syntax validation, also validate against the manifest schema (`agent_state/manifest_schema.json`):

```bash
python3 -c "
import json, sys
manifest = json.load(sys.stdin)
required = ['phase', 'goal', 'started_at', 'brd_requirements_met', 'test_results', 'artifacts', 'known_issues', 'carried_forward']
missing = [f for f in required if f not in manifest]
if missing:
    print(f'⛔ MANIFEST MISSING FIELDS: {missing}')
    sys.exit(1)
print('✅ Manifest schema valid')
" < agent_state/phases/${PHASE}/manifest.json.tmp
```

### Phase Completion Tagging

After gate passes and manifest is written:
1. `git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"`
2. This tag serves as the rollback point for future phase resets

```bash
git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"
```

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
  "carried_forward_policy": "Items in carried_forward[] MUST be addressed within 1 phase. If an item survives 2 consecutive phases: it becomes a BLOCKING gate item in the 2nd phase — fix or explicitly remove from scope via BRD change request. Forced gate overrides count toward this limit — an item force-gated in Phase N and still unresolved in Phase N+1 is BLOCKING in Phase N+1."
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
