---
command: plan
description: Generate specifications (TRDs, UI specs, data contracts) for a phase. Reads BRD + IMPLEMENTATION_GUIDELINES + previous phase manifest. Produces docs/design/phases/N/specs/.
arguments:
  - name: phase
    required: false
    description: "Phase number to plan (e.g. 1, 2, 3). Omit to auto-detect next unplanned phase."
  - name: ui_only
    required: false
    default: false
    description: "Regenerate UI specs only — skip backend specs (use after API contract changes)"
  - name: verify_only
    required: false
    default: false
    description: "Only verify existing specs against BRD — no new generation"
---

# /plan — Phase Specification Generation

Generates detailed technical specifications (TRDs), typed data contracts, and component-level UI specs for a phase. The output of `/plan` is the contract that `/develop` implements.

**Prerequisites:** `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` must exist (run `/init` first).

## Session Context Budget

**Agent result discipline:** Every agent returns a 3-line summary to the parent. Full spec content is in files — never echoed back to the conversation.

**Read discipline for spec_writer agents (parallel):** Each instance reads only its own component's requirements from the BRD (the specific FR-* rows assigned to it), not the full document. The `phase_context.md` written by `project_planner` is the primary context for all downstream agents in this command.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1 Scope | ~15K (BRD §FR + IMPL §components) |
| Step 1b Context validation | ~5K (phase_context.md + PHASE_PLAN.md) |
| Step 2 Spec per agent | ~10K (phase_context + assigned FR-* rows only) |
| Step 2b Data contracts | ~8K (extract from backend specs only) |
| Step 3 UI specs | ~15K (phase_context + data-contracts.md + archetype reference) |
| Step 4 Verify | ~20K (all specs + data-contracts.md + BRD FR-* list) |

**Agent return protocol:** Every agent returns 3 lines to the parent:
```
✅ <agent> complete → wrote docs/design/phases/N/specs/<file>.md
   Covered: FR-NNN, FR-NNN
   Issues: none | <N>
```

---

## Pipeline Anti-Rationalization Guard

Before skipping ANY step or accepting incomplete spec output, review this table.

| Your Internal Reasoning | Correct Response |
|---|---|
| "The spec is detailed enough without typed interfaces" | Every endpoint MUST have TypeScript interfaces in data-contracts.md. No exceptions. |
| "ASCII layout is sufficient for the developer" | Produce component-level specs with exact shadcn names. ASCII art is banned. |
| "Edge cases can be figured out during implementation" | Spec must have ≥10 edge cases with expected behavior. Implementation shouldn't guess. |
| "Mobile wireframe isn't needed for this screen" | Every screen needs desktop + mobile layout. BLOCK if missing. |
| "The API bindings are obvious" | Every binding must reference exact field path from data-contracts.md with type. |
| "This page is simple, no archetype needed" | Always start from a page archetype. Simple pages = archetype with fewer customizations. |
| "I'll skip the data contracts, the developer knows the API" | Data contracts are the #1 source of UI bugs. Produce them or the phase will fail at integration. |
| "The developer can figure out array vs object" | Explicit `// ARRAY` and `// OBJECT` annotations. This single issue causes most UI↔API crashes. |

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
HAS_DATA_CONTRACTS=$([ -f "docs/design/phases/${PHASE}/specs/data-contracts.md" ] && echo true || echo false)
HAS_SPECS=$(ls docs/design/phases/${PHASE}/specs/*.md 2>/dev/null | head -1 && echo true || echo false)
HAS_VERIFICATION=$([ -f "docs/design/phases/${PHASE}/VERIFICATION_REPORT.md" ] && echo true || echo false)
```

**Resume rules:**
- If `PHASE_PLAN.md` + `phase_context.md` exist → skip Step 1 + 1b
- If backend specs exist in `specs/` → skip Step 2 for those components
- If `data-contracts.md` exists → skip Step 2b
- If UI specs exist in `specs/` → skip Step 3 for those screens
- If `VERIFICATION_REPORT.md` exists → skip to Step 5
- **Always re-run Step 1b (phase_context validation)** on resume — cheap and catches stale context

### Agent Context Protocol — ALL agents read these before producing output

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

**`docs/design/phases/${PHASE}/PHASE_PLAN.md`** — full planning detail:
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

**`docs/design/phases/${PHASE}/phase_context.md`** — structured context extract (~6-8K tokens) loaded by ALL implementation agents.

---

## Step 1b — Phase Context Validation (inline — no separate agent)

**Runs after:** `project_planner` writes `phase_context.md` (Step 1)
**Runs before:** `spec_writer` agents consume it (Step 2)
**Purpose:** Catch incomplete phase context BEFORE spec writers use it

**Checks:**
1. Every FR-* listed in `PHASE_PLAN.md` §Scope appears in `phase_context.md` §In-Scope Requirements
2. Tech stack section is non-empty (language, framework, DB, auth all populated)
3. Coding conventions section is non-empty
4. Security requirements section includes ALL NFR-SEC-* from BRD (not just this phase's)
5. "What Already Exists" section matches previous manifest (if PHASE > 1)
6. Escalation pointers section present

**On failure:** Re-run `project_planner` with specific gap identified. Max 1 retry → surface to user.

---

## Step 2 — Backend Specifications (PARALLEL)

**Agents:** `spec_writer` (one per component in scope)
**Skip if:** `--ui_only` flag

Each agent reads: ALL Step 0 context + `docs/design/phases/${PHASE}/PHASE_PLAN.md`

Produces one spec file per component/flow in `docs/design/phases/${PHASE}/specs/`.

Every spec MUST include a **Data Contracts** section with exact TypeScript interfaces (see spec_writer agent for format). This is the source material for Step 2b.

---

## Step 2b — Typed Data Contracts (after backend specs, before UI specs)

**Runs after:** Step 2 (all spec_writer agents complete)
**Runs before:** Step 3 (ux_designer needs these for API bindings)
**Output:** `docs/design/phases/${PHASE}/specs/data-contracts.md`

Extract ALL endpoint response shapes from the backend TRDs into a single typed data contracts file. This is the **SINGLE SOURCE OF TRUTH** for data shapes consumed by:
- `ux_designer` (API bindings in UI specs reference these types)
- `api_developer` during `/develop` (must implement these exact shapes)
- `ui_developer` during `/develop` (TypeScript interfaces must match)
- `spec_verifier` (validates cross-references)

### Format

```typescript
// ============================================================
// GET /api/v1/users
// Source: specs/user-management.md §Data Contracts
// ============================================================

interface User {
  id: string;
  name: string;           // min: 2, max: 50
  email: string;          // valid email format
  role: "admin" | "member" | "viewer";
  avatar_url?: string;    // optional
  created_at: string;     // ISO 8601
}

interface ListMeta {
  total: number;
  page: number;
  per_page: number;
}

// List endpoint — RETURNS ARRAY
type GetUsersResponse = {
  data: User[];           // ← ARRAY (UI uses .map(), .length, .filter())
  error: string | null;
  meta: ListMeta | null;  // null if unpaginated
}

// Detail endpoint — RETURNS OBJECT
type GetUserResponse = {
  data: User;             // ← SINGLE OBJECT (UI uses .name, .email)
  error: string | null;
}

// Create request
type CreateUserRequest = {
  name: string;           // min: 2, max: 50
  email: string;          // valid email
  role: "admin" | "member" | "viewer";
}

// Create response
type CreateUserResponse = {
  data: User;             // ← OBJECT (newly created)
  error: string | null;
}

// Empty states:
// GET /users (no results): { data: [], error: null, meta: { total: 0, page: 1, per_page: 20 } }
// GET /users/:id (not found): 404 status
// POST /users (validation fail): { data: null, error: "Validation failed", details: { email: "already taken" } }
```

### Rules
- One file per phase, ALL endpoints consolidated
- ARRAY vs OBJECT must be explicitly annotated with comments
- Empty state documented for every endpoint
- Request types include validation constraints (min, max, format)
- Field types are exact TypeScript (not `any` or `object`)
- Source spec file referenced for each endpoint group

---

## Step 3 — UI Specifications (after data contracts, UI phases only)

**Agent:** `ux_designer`
**Run when:** `docs/IMPLEMENTATION_GUIDELINES.md` shows `frontend.enabled = true` AND phase scope includes UI screens
**Depends on:** Step 2b (data-contracts.md must exist before UI specs)

Reads: ALL Step 0 context + `data-contracts.md` + page archetypes from `.claude/skills/ui/archetypes/`

Produces component-level UI spec files in `docs/design/phases/${PHASE}/specs/`:

Each UI spec contains:
- Page archetype reference (list-page, detail-page, form-page, dashboard-page, settings-page)
- Exact shadcn component tree (NOT ASCII art)
- Data bindings referencing exact TypeScript interfaces from `data-contracts.md`
- Desktop (1280px) + Mobile (375px) layout with component changes
- All 4 states (loading skeleton, empty with Lucide icon + CTA, error + retry, populated)
- Interaction flows with API calls and UI responses
- Accessibility annotations (heading hierarchy, landmarks, focus order, ARIA labels)

**Design quality gate:** `design_quality_reviewer` validates each UI spec against 9 dimensions:
1. API Coverage — all fields bound, no "TBD"
2. Component Mapping — all widgets are named shadcn primitives
3. 4-State Coverage — loading skeleton + empty + error + data defined
4. Interactions — every action has defined outcome
5. Accessibility — headings, landmarks, ARIA, focus order
6. Responsive — mobile + desktop layouts present
7. Touch Targets — ≥44px annotated for mobile
8. Consistency — matches previous phase screens
9. Data Contract Binding — every field references real type in data-contracts.md, array/object matches component type

BLOCK → `ux_designer` revises (max 2 retries) → escalate to user if still blocked.

---

## Step 4 — Spec Verification

**Agent:** `spec_verifier`

Reads ALL specs produced in Steps 2-3 and verifies:
- Every FR-* assigned to this phase in BRD traceability matrix is covered by ≥1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in `docs/BRD.md` (no invented IDs)
- All exit criteria in `PHASE_PLAN.md` are covered by ≥1 spec
- Performance targets reference specific NFR-* IDs

**Data Contract Validation:**
- `data-contracts.md` exists and is non-empty
- Every endpoint in backend specs has a matching entry in `data-contracts.md`
- Every TypeScript interface has explicit field types (no `any`)
- List endpoints annotated `// ARRAY`, single endpoints `// OBJECT`
- Empty states documented for every endpoint
- If UI specs exist: every API binding references a real field in `data-contracts.md`
- If UI specs exist: list components bind to ARRAY endpoints, detail components bind to OBJECT endpoints (**BLOCKING** mismatch)

**Spec Quality:**
- Every spec has interface contracts, edge cases (≥10 meaningful), test coverage requirements
- Edge cases are specific (not generic "invalid input")
- Acceptance criteria are testable (yes/no automated test)
- Specs with DB changes declare migrations

Auto-retry failed specs (max 2 retries). Surface unresolvable issues to user.

Writes `docs/design/phases/${PHASE}/VERIFICATION_REPORT.md`.

---

## Step 4a — Reconciliation Point B: BRD ↔ Specs

**Agent:** `brd_spec_reconciler`
**Runs after:** Step 4 (spec_verifier complete)
**Parallelization:** Can start on backend specs as soon as Step 2 finishes. Adds UI spec checks when Step 3 completes.

Validates both directions:
- **Forward:** BRD FR-* requirements assigned to this phase with no spec coverage
- **Reverse:** Spec behaviors with no BRD source (gold-plating, scope creep, undocumented decisions)

Output: `agent_state/reconciliation/phase-N/brd_vs_specs.md`

If MISSING coverage: blocks `/develop` — gaps must be closed.
If INVENTED behaviors: surface to user — may be valid technical decisions or may be scope creep.

---

## Step 4b — Architecture Decision Records (parallel with Step 4)

**Agent:** `adr_agent`
**When:** Any spec introduces a significant architectural decision

Reads all specs from Steps 2-3. For each significant architectural decision:
- Writes an ADR in `docs/adr/` using the format: `ADR-NNN-<decision-slug>.md`
- Captures: decision, context, options considered, rationale, consequences

Does NOT block `/develop`. Runs in parallel with spec verification.

---

## Step 4c — Future Phase Sketches (Progressive Planning)

**When:** Phase being planned is NOT the last phase in the BRD scope
**Purpose:** Sketch future phases to capture intent without over-planning

For each future phase (N+1, N+2):
```markdown
# Phase N+1 Sketch (auto-generated — will be refined before execution)

## Goal
<one-line goal>

## Rough Scope
- FR-* requirements likely in scope: [IDs only]
- Components likely touched: [list]

## Dependencies on Phase N
- Requires: [what Phase N must deliver for N+1 to work]
- Risk: [what might change between now and N+1 execution]

## Open Questions
- [questions that must be answered before full planning]
```

Write sketches to `docs/design/phases/${FUTURE_PHASE}/SKETCH.md`.

---

## Step 5 — Output Index

Write `docs/design/phases/${PHASE}/INDEX.md`:
```markdown
# Phase N Specs Index

## Phase Plan
- PHASE_PLAN.md
- phase_context.md

## Backend Specs
- specs/<component>.md — <one-line description>

## Data Contracts
- specs/data-contracts.md — typed TypeScript interfaces for ALL endpoints

## UI Specs (if UI phase)
- specs/<screen>.ui-spec.md — component-level UI specification

## Verification
- VERIFICATION_REPORT.md — spec + data contract coverage against BRD
```

Print summary:
```
✅ Phase N planned

  Scope: N FR-* requirements, N components
  Backend specs: N files
  Data contracts: N endpoints typed in data-contracts.md
  UI specs: N files (or: not a UI phase)
  Verification: PASSED

  ▶ Next: /develop --phase=N
```
