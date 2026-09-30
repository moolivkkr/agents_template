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
  - name: auto
    required: false
    default: false
    description: "Auto-assign FR-* to phases by dependency analysis. No user prompts for scope decisions."
  - name: as_built
    required: false
    default: false
    description: "Baseline an EXISTING codebase (after /init --from-code): the phase's scope is the BRD's as-built FR-*, specs describe the code as it is, and /develop's job is the test + acceptance baseline, not new features."
---

# /plan — Phase Specification Generation

> **Auto mode.** `--auto` is set, OR `agent_state/autonomous/run.json` has `"status":"running"` (this
> command was invoked by `/autonomous`). In auto mode, never wait for the user: every "surface to
> user" / "escalate to user" / STOP-for-input point below instead auto-resolves with the recommended
> option, is logged to `agent_state/autonomous/auto-resolved.jsonl` (full question, options, choice,
> rationale, category; `"category":"security","security_flag":true` for security topics), and is
> carried forward to the next human checkpoint. The exception is a security decision with no
> hardened default, which sets `run.json` `status` to `awaiting_human`. The closing "▶ Next: …" line
> is for standalone use only; under `/autonomous`, return control to it without ending the turn.

Generates detailed technical specifications (TRDs), typed data contracts, and component-level UI specs for a phase. The output of `/plan` is the contract that `/develop` implements.

**Prerequisites:** `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` must exist (run `/init` first).

## Session Context Budget

> Full protocol: `~/.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

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
| Step 4b Plan check | ~15K (PHASE_PLAN.md + all specs + BRD objectives) |

**Agent return protocol:** Every agent returns 3 lines to the parent:
```
✅ <agent> complete → wrote docs/design/phases/N/specs/<file>.md
   Covered: FR-NNN, FR-NNN
   Issues: none | <N>
```

---

## Pipeline Anti-Rationalization Guard

**One rule:** Never skip a step, shortcut a gate, or accept partial results — even if it "seems fine." If you're tempted to skip, that's exactly when the step matters most. The table below lists specific temptations and their correct responses.

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
HAS_PLAN_CHECK=$([ -f "agent_state/phases/${PHASE}/plan_check.md" ] && echo true || echo false)
```

**Resume rules:**
- If `PHASE_PLAN.md` + `phase_context.md` exist → skip Step 1 + 1b
- If backend specs exist in `specs/` → skip Step 2 for those components
- If `data-contracts.md` exists → skip Step 2b
- If UI specs exist in `specs/` → skip Step 3 for those screens
- If `VERIFICATION_REPORT.md` exists → skip Step 4
- If `plan_check.md` exists with PASS or WARN verdict → skip Step 4b, proceed to Step 5
- If `plan_check.md` exists with BLOCK verdict → re-run Step 4b (specs may have been amended)
- **Always re-run Step 1b (phase_context validation)** on resume — cheap and catches stale context

### Agent Context Protocol — ALL agents read these before producing output

**REQUIRED READS (all agents):**
- `docs/BRD.md` — objectives (OBJ-*), functional requirements (FR-*), NFRs, gate checklists
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, component inventory, design constraints
- `agent_state/phases/$((PHASE-1))/manifest.json` — what previous phase built (when PHASE > 1)
- `agent_state/agent_registry.json` — active agents and skill packs for this project
- `agent_state/codebase/*.md` — persistent codebase knowledge (if `/map` was run and `agent_state/codebase/.last-mapped` exists). `project_planner` loads ALL focus docs. `spec_writer` loads `architecture.md` + `tech.md`. `spec_verifier` loads `quality.md` + `concerns.md`. Skip if directory does not exist.

---

## As-built mode (`--as-built`): baselining an existing codebase

Run once, right after `/init --from-code`, for the first phase. It turns "code with no specs" into
specs + a test and acceptance baseline, so `/recon` and `/accept` have something to check against.
What changes in the steps below:

- **Step 1:** `project_planner` scopes the phase to every BRD FR-* whose `Source` is `as-built`, plus
  the NFR-* the code already meets. PHASE_PLAN.md carries `Mode: as-built` under its title. Its
  implementation waves list only the FR-* the BRD marks `Status: gap` (stubs the code has, L1/L2 in
  the capability inventory); every other FR is "exists — tests only".
- **Step 2:** each `spec_writer` prompt starts with `MODE: as-built`. Document the component **as
  implemented**: read the code the BRD `Source` cites and `agent_state/codebase/*`; write the
  contracts and the edge-case behaviour the code actually has, and EARS criteria matching the BRD.
  Write the full TC inventory (unit, integration, e2e, TC-ACC); it's the baseline the tests are written
  to. Where the code does something that looks wrong, specify what it does and list it under
  `## As-built observations` (suspected bugs, for the user), rather than "fixing" it in the spec.
- **Step 2b:** data-contracts.md is extracted from the real handlers and response types.
- **Step 3 (UI):** `ux_designer` documents the existing screens (component tree, bindings, states)
  instead of designing new ones. `design_quality_reviewer` findings on existing screens are WARN
  (they go to the backlog), not BLOCK.
- **Steps 3b–4b:** unchanged.

Then `/develop --phase=N` runs audit → gap work only → every test tier → acceptance → gate. When the
gate passes, every as-built FR has passing, committed acceptance tests.

---

## Step 1 — Phase Scope Definition

**Agent:** `project_planner`

**First, what the acceptance suite doesn't cover yet** (deterministic; pass the output to `project_planner`):
```bash
python3 .claude/hooks/acceptance-map.py --out agent_state/accept/acceptance_map.json || true
jq -r '.unplanned[] | "\(.fr) \(.priority)\(if .as_built then " as-built" else "" end)"' agent_state/accept/acceptance_map.json
```
- **Unplanned as-built FR-*** (BRD `Source` says `as-built` — added by `/init --from-code` or
  `/recon --fix=docs --apply`): the code exists but no acceptance test proves it. Put them in THIS
  phase's scope as **acceptance-only** items (spec rows + tests, no implementation task), unless the
  user assigns them elsewhere.
- **Unplanned FR-* that are not as-built** (e.g. added by a `product_manager` change request): assign
  them to this phase or a later one, as for any FR.
- **CHANGED FR-* from delivered phases** are not re-planned here; `/develop`'s Wave 4 pre-step and
  `/accept` Step 1a update their TC-ACC rows and tests in the phase that owns them.

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

**On failure:** Re-run `project_planner` with specific gap identified. Max 1 retry → surface to user (auto mode: proceed with the best plan, log the gap as `category: planning`).

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

Reads: ALL Step 0 context + `data-contracts.md` + page archetypes from `~/.claude/skills/ui/archetypes/`

Produces component-level UI spec files in `docs/design/phases/${PHASE}/specs/`:

Each UI spec contains:
- Page archetype reference (list-page, detail-page, form-page, dashboard-page, settings-page)
- Exact shadcn component tree (NOT ASCII art)
- Data bindings referencing exact TypeScript interfaces from `data-contracts.md`
- Desktop (1280px) + Mobile (375px) layout with component changes
- All 4 states (loading skeleton, empty with Lucide icon + CTA, error + retry, populated)
- Interaction flows with API calls and UI responses
- Accessibility annotations (heading hierarchy, landmarks, focus order, ARIA labels)

**Design quality gate:** `design_quality_reviewer` validates each UI spec against 11 dimensions:
1. API Coverage — all fields bound, no "TBD"
2. Component Mapping — all widgets are named component-library primitives
3. 4-State Coverage — loading skeleton + empty + error + data defined
4. Interactions — every action has defined outcome
5. Accessibility — headings, landmarks, ARIA, focus order
6. Responsive — mobile + desktop layouts present
7. Touch Targets — ≥44px annotated for mobile
8. Consistency — matches previous phase screens
9. Data Contract Binding — every field references real type in data-contracts.md, array/object matches component type
10. Data Contract Cross-Reference — every wireframe field verified against the contract field map
11. Design-System Adherence — semantic tokens (not hardcoded colors) + reuse of the shared component library (if a project design system exists, e.g. `~/.claude/skills/ui/vertix-portal-design-system.md`)

BLOCK → `ux_designer` revises (max 2 retries) → escalate to user if still blocked (auto mode: downgrade to WARN, log `category: ux`, carry to the checkpoint).

---

## Step 3b — Design-Time Security & Reliability (conditional, parallel)

Design-time review that feeds `spec_writer` (mitigations and SLOs become spec requirements), distinct
from the code-level reviewers that run later in `/develop`. Both are conditional — run when applicable
and add them to the phase roster so the gate proves they ran; otherwise record the skip + reason.

**Agent:** `threat_model_agent` — **Run when** the phase touches auth, PII/sensitive data, external
input, payments, multi-tenant boundaries, or a new trust boundary. Produces STRIDE-per-element threat
model with each threat mapped to a mitigation and (where testable) a `TC-SEC-*` id →
`agent_state/phases/${PHASE}/reports/threat_model.md` (+ `.json`). BLOCKING threats with no mitigation
block `/develop`.

**Agent:** `reliability_agent` — **Run when** the phase adds/changes a service with an NFR-PERF-* or
availability target. Defines SLIs/SLOs + error budgets tied to NFR-* IDs, reviews health-check and
timeout/retry/circuit-breaker design, and generates runbook stubs →
`agent_state/phases/${PHASE}/reports/reliability_review.md` (+ `.json`). It also runs again in
`/deploy` (Step 4d) to validate the deployed system against the SLOs it defined here.

**Then — security merge (whenever threat_model_agent ran):** re-spawn `spec_writer`
(subagent_type: spec_writer) in **security-merge mode**. It reads `reports/threat_model.md` and writes
the phase's `TC-SEC-*` rows (k=00 block, with tier and priority) into the phase inventory, so they're
in the gated TC inventory. Before this step existed, threat-model tests reached no tester and no gate.

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

If MISSING coverage: **auto-fix loop** before blocking:
1. Identify which FR-* is missing spec coverage
2. Route to `spec_writer` with the specific FR-* as input → agent writes the missing spec
3. Re-run `brd_spec_reconciler` to verify the gap is closed
4. Max 2 auto-fix cycles → if still MISSING after 2 cycles: block `/develop` and surface to user (auto mode: log each MISSING item as `category: architecture` in auto-resolved.jsonl, mark them `deferred` in phase_context.md, and continue; the checkpoint shows them)
5. This prevents the common case where a spec_writer simply forgot one FR-* from its assignment

If INVENTED behaviors: surface to user — may be valid technical decisions or may be scope creep (auto mode: keep them, and log each as `category: architecture` for review at the checkpoint).

---

## Step 4b — Goal-Backward Plan Check

**Agent:** `plan_goal_verifier`
**Runs after:** Step 4a (brd_spec_reconciler complete)
**Runs before:** Step 4c (ADRs) and Step 4d (future phase sketches)

Performs goal-backward verification: starting from the phase goal, traces backward through specs → components → contracts to verify the plan will achieve its stated objective.

This is fundamentally different from spec_verifier (which checks spec completeness) and brd_spec_reconciler (which checks BRD alignment). plan_goal_verifier asks: "If every spec is implemented perfectly, will the phase goal actually be achieved?"

Reads:
- `PHASE_PLAN.md` (goal, exit criteria, E2E workflows unlocked)
- All specs in `docs/design/phases/${PHASE}/specs/`
- BRD objectives and requirements mapped to this phase
- `data-contracts.md` (if exists — validates integration contracts)
- `DISCUSSION.md` (if exists — resolved assumptions and decisions)

Writes: `agent_state/phases/${PHASE}/plan_check.md`

**Analysis:**
1. Traces each exit criterion backward to specs → components → endpoints → data models → integration points
2. Checks component completeness (all required pieces defined)
3. Checks cross-component integration (interfaces match, data flows correctly)
4. Checks NFR coverage (performance, security requirements have actionable spec constraints)
5. Validates E2E workflow feasibility (full user journeys can execute end-to-end)

**Verdicts:**
- **PASS** → continue to Step 4c
- **WARN** → display warnings, continue to Step 4c (warnings carry into phase_context.md)
- **BLOCK** → STOP. Display gaps. Route specific gaps back to spec_writer for amendment (max 1 cycle). If still BLOCK after amendment: surface to user (auto mode: downgrade to WARN, log `category: architecture`, continue; this is the behaviour `/autonomous` Step 2b relies on).

```
plan_goal_verifier → agent_state/phases/${PHASE}/plan_check.md
  Verdict: PASS | WARN | BLOCK
  Gaps: <N> | none
  Coverage: <N>/<N> exit criteria covered
```

---

## Step 4c — Architecture Decisions (parallel with Step 4)

**Agent:** `adr_agent`
**When:** Any spec introduces a significant architectural decision

Optional documents follow the project's docs policy (lean by default — see `/docs`). Define once:
```bash
docs_on() { local s=.claude/hooks/docs-policy.py; [ -f "$s" ] || s="$HOME/.claude/hooks/startup/docs-policy.py"; python3 "$s" is-on "${1}" 2>/dev/null; }   # 0 = produce it; else skip (lean)
```

Reads all specs from Steps 2-3. For each significant architectural decision:
- **Always:** records it in `docs/DECISIONS.md` with `remember.sh decide` (decision + rationale + the
  runner-up rejected). This is the ledger every agent reads, so the decision is never lost.
- **Only if `docs_on adr_files`:** also writes the long-form ADR `docs/adr/ADR-NNN-<decision-slug>.md`
  (context, options considered, consequences). Otherwise spawn it with `MODE: ledger-only` in the prompt.

Does NOT block `/develop`. Runs in parallel with spec verification.

---

## Step 4d — Future Phase Sketches (optional: `docs_on phase_sketches`)

**When:** `docs_on phase_sketches` is on (off in the lean profile) AND the phase being planned is NOT
the last phase in the BRD scope. When off, skip this step: the BRD traceability matrix already says
which FR-* belong to later phases, and `/plan` writes each phase properly when it gets there.
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

## Plan Check
- agent_state/phases/N/plan_check.md — goal-backward verification
```

Print summary:
```
✅ Phase N planned

  Scope: N FR-* requirements, N components
  Backend specs: N files
  Data contracts: N endpoints typed in data-contracts.md
  UI specs: N files (or: not a UI phase)
  Verification: PASSED
  Plan check: PASS | WARN (N warnings) — N/N exit criteria covered

  ▶ Next: /develop --phase=N
```
