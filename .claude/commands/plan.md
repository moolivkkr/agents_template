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
---

# /plan — Phase Specification Generation

Generates TRDs, typed data contracts, and component-level UI specs for a phase. Output is the contract `/develop` implements.

**Prerequisites:** `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` must exist (run `/init` first).

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`

**Agent result discipline:** Every agent returns a 3-line summary. Full spec content stays in files — never echoed back.

**Read discipline for spec_writer agents:** Each instance reads only its assigned FR-* rows from BRD, not the full document. `phase_context.md` is primary context for all downstream agents.

| Step | Target input tokens |
|------|---------------------|
| Step 1 Scope | ~15K |
| Step 1b Context validation | ~5K |
| Step 2 Spec per agent | ~10K |
| Step 2b Data contracts | ~8K |
| Step 3 UI specs | ~15K |
| Step 4 Verify | ~20K |

**Agent return format:**
```
✅ <agent> complete → wrote docs/design/phases/N/specs/<file>.md
   Covered: FR-NNN, FR-NNN
   Issues: none | <N>
```

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "Spec is detailed enough without typed interfaces" | Every endpoint MUST have TypeScript interfaces in data-contracts.md. No exceptions. |
| "ASCII layout is sufficient" | Component-level specs with exact shadcn names. ASCII art banned. |
| "Edge cases can be figured out during implementation" | Spec must have >=10 edge cases with expected behavior. |
| "Mobile wireframe isn't needed for this screen" | Every screen needs desktop + mobile layout. BLOCK if missing. |
| "The API bindings are obvious" | Every binding must reference exact field path from data-contracts.md with type. |
| "This page is simple, no archetype needed" | Always start from a page archetype. |
| "I'll skip the data contracts" | Data contracts are the #1 source of UI bugs. Produce them or phase fails. |
| "Developer can figure out array vs object" | Explicit `// ARRAY` and `// OBJECT` annotations required. |

---

## Step 0 — Orient

### Detect phase
```bash
LAST_PLANNED=$(ls docs/design/phases/ 2>/dev/null | grep -oP '\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PLANNED:-0} + 1 ))}
echo "▶ Planning Phase $PHASE"
```

### Gate check
If PHASE > 1: verify `agent_state/phases/$((PHASE-1))/gate.passed` exists. If missing: **STOP**.

### Create output directory
```bash
mkdir -p docs/design/phases/${PHASE}/specs
```

### Resume detection
```bash
HAS_PHASE_PLAN=$([ -f "docs/design/phases/${PHASE}/PHASE_PLAN.md" ] && echo true || echo false)
HAS_PHASE_CONTEXT=$([ -f "docs/design/phases/${PHASE}/phase_context.md" ] && echo true || echo false)
HAS_DATA_CONTRACTS=$([ -f "docs/design/phases/${PHASE}/specs/data-contracts.md" ] && echo true || echo false)
HAS_SPECS=$(ls docs/design/phases/${PHASE}/specs/*.md 2>/dev/null | head -1 && echo true || echo false)
HAS_VERIFICATION=$([ -f "docs/design/phases/${PHASE}/VERIFICATION_REPORT.md" ] && echo true || echo false)
```

**Resume rules:**
- `PHASE_PLAN.md` + `phase_context.md` exist → skip Step 1 + 1b
- Backend specs exist → skip Step 2 for those components
- `data-contracts.md` exists → skip Step 2b
- UI specs exist → skip Step 3 for those screens
- `VERIFICATION_REPORT.md` exists → skip to Step 5
- **Always re-run Step 1b on resume** — cheap, catches stale context

### Agent Context Protocol — ALL agents read before producing output
- `docs/BRD.md` — OBJ-*, FR-*, NFRs, gate checklists
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, components, constraints
- `agent_state/phases/$((PHASE-1))/manifest.json` — previous phase output (PHASE > 1)
- `agent_state/agent_registry.json` — active agents and skill packs

---

## Step 1 — Phase Scope Definition

**Agent:** `project_planner`

Reads BRD + previous manifests. Determines: which FR-* belong to this phase, which components are touched, exit criteria, wave structure (parallel vs sequential).

Writes **`docs/design/phases/${PHASE}/PHASE_PLAN.md`** (scope, exit criteria, waves, e2e workflows unlocked) and **`docs/design/phases/${PHASE}/phase_context.md`** (~6-8K tokens structured context for all implementation agents).

---

## Step 1b — Phase Context Validation (inline)

**Checks:**
1. Every FR-* in `PHASE_PLAN.md` §Scope appears in `phase_context.md` §In-Scope Requirements
2. Tech stack section non-empty (language, framework, DB, auth)
3. Coding conventions section non-empty
4. Security requirements include ALL NFR-SEC-* from BRD
5. "What Already Exists" matches previous manifest (PHASE > 1)
6. Escalation pointers section present

**On failure:** Re-run `project_planner` with specific gap. Max 1 retry → surface to user.

---

## Step 2 — Backend Specifications (PARALLEL)

**Agents:** `spec_writer` (one per component in scope)
**Skip if:** `--ui_only` flag

Each agent reads: Step 0 context + `PHASE_PLAN.md`. Produces one spec file per component in `docs/design/phases/${PHASE}/specs/`. Every spec MUST include a **Data Contracts** section with exact TypeScript interfaces.

---

## Step 2b — Typed Data Contracts

**After:** Step 2 | **Before:** Step 3
**Output:** `docs/design/phases/${PHASE}/specs/data-contracts.md`

Extract ALL endpoint response shapes from backend TRDs into a single file. **SINGLE SOURCE OF TRUTH** for `ux_designer`, `api_developer`, `ui_developer`, `spec_verifier`.

### Rules
- One file per phase, ALL endpoints consolidated
- ARRAY vs OBJECT explicitly annotated with comments
- Empty state documented for every endpoint
- Request types include validation constraints (min, max, format)
- Field types are exact TypeScript (not `any` or `object`)
- Source spec file referenced for each endpoint group

---

## Step 3 — UI Specifications (after data contracts)

**Agent:** `ux_designer`
**Run when:** `frontend.enabled = true` AND phase scope includes UI screens
**Depends on:** Step 2b (`data-contracts.md` must exist)

Reads: Step 0 context + `data-contracts.md` + page archetypes from `.claude/skills/ui/archetypes/`

Each UI spec contains: page archetype reference, exact shadcn component tree, data bindings from `data-contracts.md`, desktop (1280px) + mobile (375px) layout, all 4 states (loading/empty/error/populated), interaction flows, accessibility annotations.

**Design quality gate:** `design_quality_reviewer` validates against 9 dimensions: API Coverage, Component Mapping, 4-State Coverage, Interactions, Accessibility, Responsive, Touch Targets (>=44px), Consistency, Data Contract Binding.

BLOCK → `ux_designer` revises (max 2 retries) → escalate to user.

---

## Step 4 — Spec Verification

**Agent:** `spec_verifier`

Verifies:
- Every FR-* assigned to this phase covered by >=1 spec
- All cited FR-*/NFR-*/OBJ-* IDs exist verbatim in BRD (no invented IDs)
- All exit criteria in `PHASE_PLAN.md` covered
- Performance targets reference specific NFR-* IDs
- **Data Contract Validation:** `data-contracts.md` exists/non-empty, every endpoint has matching entry, no `any` types, ARRAY/OBJECT annotations, empty states, UI bindings match real fields, list→ARRAY / detail→OBJECT (**BLOCKING** mismatch)
- **Spec Quality:** interface contracts, >=10 meaningful edge cases, testable acceptance criteria, migration declarations

Auto-retry failed specs (max 2). Writes `docs/design/phases/${PHASE}/VERIFICATION_REPORT.md`.

---

## Step 4a — Reconciliation Point B: BRD ↔ Specs

**Agent:** `brd_spec_reconciler` (after Step 4)

Validates both directions:
- **Forward:** BRD FR-* assigned to this phase with no spec coverage
- **Reverse:** Spec behaviors with no BRD source (gold-plating/scope creep)

Output: `agent_state/reconciliation/phase-N/brd_vs_specs.md`

If MISSING: auto-fix loop — route to `spec_writer` → re-reconcile (max 2 cycles) → block if still missing.
If INVENTED: surface to user.

---

## Step 4b — Architecture Decision Records (parallel with Step 4)

**Agent:** `adr_agent`

Reads all specs. For significant architectural decisions, writes ADRs to `docs/adr/ADR-NNN-<slug>.md`. Does NOT block `/develop`.

---

## Step 4c — Future Phase Sketches (Progressive Planning)

**When:** Phase being planned is NOT the last phase

For each future phase (N+1, N+2): write goal, rough scope (FR-* IDs), dependencies on Phase N, open questions to `docs/design/phases/${FUTURE_PHASE}/SKETCH.md`.

---

## Step 5 — Output Index

Write `docs/design/phases/${PHASE}/INDEX.md` listing all artifacts.

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
