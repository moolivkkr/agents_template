---
command: plan
description: Generate specifications (TRDs, wireframes) for a phase. Reads BRD + IMPLEMENTATION_GUIDELINES + previous phase manifest. Produces docs/design/phases/N/specs/.
arguments:
  - name: phase
    required: false
    description: "Phase number to plan (e.g. 1, 2, 3). Omit to auto-detect next unplanned phase."
  - name: ui_only
    required: false
    default: false
    description: "Regenerate wireframes only — skip backend specs (use after API contract changes)"
  - name: verify_only
    required: false
    default: false
    description: "Only verify existing specs against BRD — no new generation"
---

# /plan — Phase Specification Generation

Generates detailed technical specifications (TRDs) and wireframes for a phase. The output of `/plan` is the contract that `/develop` implements.

**Prerequisites:** `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` must exist (run `/init` first).

## Session Context Budget

**Agent result discipline:** Every agent returns a 3-line summary to the parent. Full spec content is in files — never echoed back to the conversation.

**Read discipline for spec_writer agents (parallel):** Each instance reads only its own component's requirements from the BRD (the specific FR-* rows assigned to it), not the full document. The `phase_context.md` written by `project_planner` is the primary context for all downstream agents in this command.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1 Scope | ~15K (BRD §FR + IMPL §components) |
| Step 2 Spec per agent | ~10K (phase_context + assigned FR-* rows only) |
| Step 3 Wireframes | ~15K (phase_context + backend spec API contracts) |
| Step 4 Verify | ~20K (all specs + BRD FR-* list) |

**Agent return protocol:** Every agent returns 3 lines to the parent:
```
✅ <agent> complete → wrote docs/design/phases/N/specs/<file>.md
   Covered: FR-NNN, FR-NNN
   Issues: none | <N>
```

---

## Step 0 — Orient

### Detect phase
```bash
# Auto-detect next unplanned phase
LAST_PLANNED=$(ls docs/design/phases/ 2>/dev/null | grep -oP '\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PLANNED:-0} + 1 ))}
echo "▶ Planning Phase $PHASE"
```

### Gate check
If PHASE > 1: verify `agent_state/phases/$((PHASE-1))/gate.passed` exists.
If missing: **STOP** — `Phase $((PHASE-1)) has not completed. Run /develop --phase=$((PHASE-1)) first.`

### Create output directory
```bash
mkdir -p docs/design/phases/${PHASE}/specs
```

### Resume detection

Check what already exists from a previous interrupted run:
```bash
HAS_PHASE_PLAN=$([ -f "docs/design/phases/${PHASE}/PHASE_PLAN.md" ] && echo true || echo false)
HAS_PHASE_CONTEXT=$([ -f "docs/design/phases/${PHASE}/phase_context.md" ] && echo true || echo false)
HAS_SPECS=$(ls docs/design/phases/${PHASE}/specs/*.md 2>/dev/null | head -1 && echo true || echo false)
HAS_VERIFICATION=$([ -f "docs/design/phases/${PHASE}/VERIFICATION_REPORT.md" ] && echo true || echo false)
```

**Resume rules:**
- If `PHASE_PLAN.md` exists → skip Step 1 (scope already defined)
- If `phase_context.md` exists → skip Step 1 (context already extracted)
- If backend specs exist in `specs/` → skip Step 2 for those components (check each spec file individually)
- If wireframes exist in `specs/` → skip Step 3 for those screens
- If `VERIFICATION_REPORT.md` exists → skip to Step 5 (already verified)
- **Always re-run Step 3c (phase_context validation)** on resume — cheap and catches stale context

### Agent Context Protocol — ALL agents in this command read ALL of these before producing output

**REQUIRED READS (all agents):**
- `docs/BRD.md` — objectives (OBJ-*), functional requirements (FR-*), NFRs, gate checklists
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, component inventory, design constraints
- `agent_state/phases/$((PHASE-1))/manifest.json` — what previous phase built (when PHASE > 1)
- `agent_state/agent_registry.json` — active agents and skill packs for this project

---

## Step 1 — Phase Scope Definition

**Agent:** `project_planner`

Reads BRD requirements and previous manifests. Determines scope for this phase:
- Which FR-* requirements belong to this phase (from BRD traceability matrix or by assignment)
- Which components from IMPLEMENTATION_GUIDELINES are touched
- Exit criteria (what must be true for this phase to be "done")
- Wave structure (parallel vs sequential implementation tasks)

Writes two files:

**`docs/design/phases/${PHASE}/PHASE_PLAN.md`** — full planning detail for humans and reconcilers:
```markdown
# Phase N — <Goal Title>

## Scope
- FR-* requirements: [list with one-line description each]
- NFR-* requirements: [list]
- Components: [list from component inventory]

## Exit Criteria
- [ ] All FR-* in scope have passing integration tests
- [ ] NFR targets met (performance, security)
- [ ] Gate checklist items satisfied

## Implementation Waves
Wave 1 (parallel): [tasks]
Wave 2 (parallel): [tasks]
Wave 3 (sequential): [tasks]

## E2E Workflows Unlocked
[user workflows first completable after this phase — triggers e2e tests]
```

**`docs/design/phases/${PHASE}/phase_context.md`** — structured context extract (~6-8K tokens) loaded by ALL implementation agents instead of the full BRD + IMPLEMENTATION_GUIDELINES. Must be thorough enough that no agent needs to escalate to the full documents:
```markdown
# Phase N Context — <Goal Title>
(Auto-generated by /plan. Do not edit manually.)

## In-Scope Requirements
| ID | Title | Acceptance Criteria (one line) |
|----|-------|-------------------------------|
| FR-001 | User can register | Email + password, verification email sent |
| NFR-SEC-01 | Passwords hashed | bcrypt min cost 12 |

## Components This Phase
- UserService (new), AuthHandler (new), users migration (new)

## Key Tech Constraints
- Lang: Go 1.22 / Gin / PostgreSQL / goose migrations
- Auth: JWT (HS256), tokens in Authorization header
- API version: /api/v1/
- Test framework: testify + mockery

## What Already Exists (from Phase N-1)
- [summary from previous manifest — key routes, schema, services]
- Nothing yet (Phase 1)

## Gate Checklist
- [ ] FR-001 integration test passing
- [ ] NFR-SEC-01 verified by security reviewer
```

---

## Step 2 — Backend Specifications (PARALLEL)

**Agents:** `spec_writer` (one per component in scope)
**Skip if:** `--ui_only` flag

Each agent reads: ALL Step 0 context + `docs/design/phases/${PHASE}/PHASE_PLAN.md`

Produces one spec file per component/flow in `docs/design/phases/${PHASE}/specs/`:

```markdown
# Spec: <Component/Flow Name>

## BRD Traceability
- FR-* satisfied: [IDs]
- NFR-* satisfied: [IDs]
- Gate criteria covered: [which gate items]

## Interface Contracts
- Function/method signatures with types
- Request/response shapes
- Error types

## Data Model
- Entities created/modified
- DB schema changes (migration needed: yes/no)

## Flow Description
Step-by-step logic for the happy path and key error paths

## Edge Cases (≥10)
[Enumerated edge cases with expected behavior]

## Test Coverage Required
- Unit: [which functions, which cases]
- Integration: [which service↔infra interactions]
- E2E trigger: [if this spec completes a user workflow]

## Performance Targets
- p95 latency: Xms
- Throughput: X req/s
```

---

## Step 3 — UI Wireframes (PARALLEL with Step 2, UI phases only)

**Agent:** `ux_designer`
**Run when:** `docs/IMPLEMENTATION_GUIDELINES.md` shows `frontend.enabled = true` AND phase scope includes UI screens

Reads: ALL Step 0 context + backend specs from Step 2 (waits for Step 2 if `--ui_only` not set)

Produces wireframe files in `docs/design/phases/${PHASE}/specs/`:

Each wireframe contains:
- Purpose and user story
- ASCII layout grid
- Component list (mapped to UI component library)
- API bindings (every displayed field → endpoint + field name)
- Interaction flows (user action → result)
- Accessibility requirements
- Empty / loading / error states

**Design quality gate:** `design_quality_reviewer` validates each wireframe against:
1. No "TBD" API bindings
2. All components map to the project's component library
3. Loading / error / empty states present
4. Accessibility annotations present

BLOCK → `ux_designer` revises (max 2 retries) → escalate to user if still blocked.

---

## Step 3b — Reconciliation Point B: BRD ↔ Specs

**Agent:** `brd_spec_reconciler` (runs in parallel with Step 3 completion, before Step 4)

Validates both directions:
- **Forward:** BRD FR-* requirements assigned to this phase with no spec coverage
- **Reverse:** Spec behaviors with no BRD source (gold-plating, scope creep, undocumented decisions)

Output: `agent_state/reconciliation/phase-N/brd_vs_specs.md`

If MISSING coverage: blocks `/develop` — gaps must be closed.
If INVENTED behaviors: surface to user — may be valid technical decisions or may be scope creep.

---

## Step 3c — Phase Context Validation (inline — no separate agent)

**Runs after:** `project_planner` writes `phase_context.md` (Step 1)
**Purpose:** Verify `phase_context.md` is complete before spec writers consume it

**Checks:**
1. Every FR-* listed in `PHASE_PLAN.md` §Scope appears in `phase_context.md` §In-Scope Requirements
2. Tech stack section is non-empty (language, framework, DB, auth all populated)
3. Coding conventions section is non-empty
4. Security requirements section includes ALL NFR-SEC-* from BRD (not just this phase's)
5. "What Already Exists" section matches previous manifest (if PHASE > 1)
6. Escalation pointers section present

**On failure:** Re-run `project_planner` with specific gap identified. Max 1 retry → surface to user.

---

## Step 4 — Spec Verification

**Agent:** `spec_verifier`

Reads ALL specs produced in Steps 2-3 and verifies:
- Every FR-* assigned to this phase in BRD traceability matrix is covered by ≥1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in `docs/BRD.md` (no invented IDs)
- All exit criteria in `PHASE_PLAN.md` are covered by ≥1 spec
- UI wireframe API bindings reference endpoints defined in backend specs (no dangling refs)
- Performance targets reference specific NFR-* IDs

Auto-retry failed specs (max 2 retries). Surface unresolvable issues to user.

Writes `docs/design/phases/${PHASE}/VERIFICATION_REPORT.md`.

---

## Step 4b — Architecture Decision Records (parallel with Step 4)

**Agent:** `adr_agent`
**When:** Any spec introduces a significant architectural decision (new pattern, library, integration approach, or deviation from IMPLEMENTATION_GUIDELINES)

Reads all specs from Steps 2-3. For each significant architectural decision detected:
- Writes an ADR in `docs/adr/` using the format: `ADR-NNN-<decision-slug>.md`
- Captures: decision, context, options considered, rationale, consequences

Output directory: `docs/adr/`
Summary: listed in the phase INDEX.md under "Architecture Decisions"

Does NOT block `/develop`. Runs in parallel with spec verification.

---

## Step 5 — Output Index

Write `docs/design/phases/${PHASE}/INDEX.md`:
```markdown
# Phase N Specs Index

## Phase Plan
- PHASE_PLAN.md

## Backend Specs
- specs/<component>.md — <one-line description>
- ...

## Wireframes (if UI phase)
- specs/<screen>.wireframe.md — <screen name>
- ...

## Verification
- VERIFICATION_REPORT.md — spec coverage against BRD
```

Print summary:
```
✅ Phase N planned

  Scope: N FR-* requirements, N components
  Backend specs: N files
  Wireframes: N files (or: not a UI phase)
  Verification: PASSED

  ▶ Next: /develop --phase=N
```
