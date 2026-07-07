---
command: design
description: Generate the UI/design contract for a phase — wireframe specs, component/API bindings, design tokens, and TC-UI-* test cases — gated by design_quality_reviewer before UI implementation. Produces docs/design/phases/N/specs/*.wireframe.{html,md}.
arguments:
  - name: phase
    required: false
    description: "Phase number to design (e.g. 1, 2, 3). Omit to auto-detect the current phase from docs/design/phases/."
  - name: source
    required: false
    description: "Design source. Omit (default) = pure-agent path (ux_designer + wireframe_generator). --source=stitch = enrich with Google Stitch MCP renders, then import/normalize to the same artifacts. Falls back to the pure-agent path automatically if the Stitch MCP is unavailable."
  - name: screen
    required: false
    description: "Restrict to a single screen name (regenerate one wireframe instead of the whole phase)."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode — no user prompts. BLOCK verdicts trigger auto-fix (max 2 cycles); if still blocked, downgrade to WARN, log, and surface at the next human checkpoint rather than halting."
---

# /design — Phase UI Design Contract

Generates the **UI design contract** for a phase: per-screen wireframes (visual + behavioral), typed API bindings, design tokens, and the `TC-UI-*` test-case inventory. The output of `/design` is the contract that `ui_developer` implements during `/develop` — it stands to the frontend exactly as `/plan`'s TRDs stand to the backend.

`/design` is a **first-class, standalone command**. It is invoked directly, by `/plan` Step 3 for UI phases, and by `/autonomous` (Step 2a.5 / Step 5) before implementation begins. Running it standalone lets you regenerate the design contract after a data-contract change without re-running the whole plan.

**Prerequisites:**
- `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` exist (run `/init` first).
- `docs/design/phases/${PHASE}/specs/data-contracts.md` exists (run `/plan` Step 2b first). **API bindings cannot be produced without it — hard stop if missing.**

**Not a UI phase?** If `IMPLEMENTATION_GUIDELINES.md` shows `frontend.enabled = false`, or the phase scope has no UI screens, `/design` is a no-op that prints `▶ Phase N has no UI screens — skipping design.` and exits 0. It never blocks a backend-only phase.

---

## Ground Truth & Decisions (read before generating)

- `docs/PROJECT_FACTS.md` — **GROUND TRUTH (Tier 0).** Read FIRST. Retired/renamed components, hard constraints, environment facts. OVERRIDES any conflicting assumption in this prompt, the specs, or agent training. If a screen references anything marked RETIRED/superseded, STOP and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)
- `docs/DECISIONS.md` — settled decisions (Tier 0.5). Do not re-litigate an active UI/design decision without new evidence.

Every agent this command spawns inherits Required-Reading item 0/0b via `.claude/skills/core/agent-common.md` and the orchestrator ground-truth injection line. Do not skip it because "it's just a wireframe."

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step targets below are specific to this command.

**Agent result discipline:** Every agent returns a 3-line summary to the parent. Full wireframe content lives in files — never echoed back to the conversation.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1 Archetype scaffold | ~8K (PHASE_PLAN §UI scope + BRD §FR-UI-*) |
| Step 2 Wireframe per screen | ~15K (phase_context + data-contracts + archetype + design system) |
| Step 2s Stitch enrich (opt) | ~10K per screen (design brief + rendered screen JSON) |
| Step 3 Design review | ~12K (all wireframes + data-contracts + design system) |

**Agent return protocol:**
```
✅ <agent> complete → wrote docs/design/phases/N/specs/<screen>.wireframe.{html,md}
   Screens: <N> | Archetype: <list-page|detail-page|…>
   TC-UI IDs: TC-UI-NNN..NNN | Issues: none | <N>
```

---

## Anti-Rationalization Guard

**One rule:** Never skip a step, shortcut the design gate, or accept a partial wireframe — even if it "looks fine." A missing state in the wireframe becomes a missing state in the code.

| Your Internal Reasoning | Correct Response |
|---|---|
| "Stitch isn't available, so skip the whole design step" | NO. Stitch is enrichment only. The pure-agent path (`ux_designer`) is the default and is fully sufficient. Fall back, log it, continue. |
| "ASCII layout is enough for the developer" | Produce a self-contained `.wireframe.html` (inline CSS, both themes, both breakpoints). ASCII art is banned. |
| "The API bindings are obvious from the screen name" | Every binding references an exact field path + type from `data-contracts.md`. No "TBD". |
| "This screen is simple, no archetype needed" | Always start from a page archetype — simple pages are just archetypes with fewer customizations. |
| "Empty/error states can be added during implementation" | All 4 states (loading/empty/error/data) must be in the wireframe. `design_quality_reviewer` BLOCKS if any is missing. |
| "I'll skip the design review, the wireframe looks complete" | The gate is mandatory. `ui_developer` does not start on a wireframe that hasn't cleared the 11 dimensions. |
| "TC-UI IDs can be assigned later" | Enumerate TC-UI-*/TC-FORM-*/TC-COMP-* now, from the matrices in `test-case-generation.md`. The phase gate checks their coverage. |

---

## Step 0 — Orient

### Detect phase
```bash
LAST_PLANNED=$(ls docs/design/phases/ 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-${LAST_PLANNED:-1}}
echo "▶ Designing UI for Phase $PHASE"
```

### Prerequisite checks
```bash
DC="docs/design/phases/${PHASE}/specs/data-contracts.md"
[ -f "docs/BRD.md" ] || { echo "⛔ docs/BRD.md missing — run /init first."; exit 1; }
[ -f "docs/design/phases/${PHASE}/PHASE_PLAN.md" ] || { echo "⛔ PHASE_PLAN.md missing — run /plan --phase=${PHASE} first."; exit 1; }
[ -f "$DC" ] || { echo "⛔ ${DC} missing — run /plan Step 2b first. API bindings need the typed contracts."; exit 1; }
mkdir -p "docs/design/phases/${PHASE}/specs"
```

### UI-phase gate
Determine whether this phase actually has UI screens:
```bash
# frontend must be enabled AND the phase must have UI-flavored scope
FRONTEND=$(grep -iE "frontend.*enabled|frontend:.*true" docs/IMPLEMENTATION_GUIDELINES.md 2>/dev/null | head -1)
HAS_UI_SCOPE=$(grep -iE "FR-UI-|UI|interface|screen|dashboard|component|widget|chat|graph|form|page" \
  "docs/design/phases/${PHASE}/PHASE_PLAN.md" 2>/dev/null | head -1)
```
If frontend is disabled OR there is no UI scope:
```
▶ Phase ${PHASE} has no UI screens — skipping design.
```
Exit 0. This is the graceful no-op for backend-only phases.

### `--source=stitch` availability probe (only when the flag is set)
```bash
STITCH_MODE="agent"   # default: pure-agent path
if [ "$ARG_SOURCE" = "stitch" ]; then
  # Probe the Stitch MCP with a cheap read call (list_projects).
  # If the tool is unavailable / errors / times out → fall back, DO NOT block.
  if mcp_stitch_probe; then
    STITCH_MODE="stitch"
    echo "✅ Stitch MCP available — enriching wireframes with Stitch renders."
  else
    STITCH_MODE="agent"
    echo "⚠ Stitch MCP unavailable — falling back to pure-agent design (ux_designer). Logging fallback."
    # In --auto: append to agent_state/autonomous/auto-resolved.jsonl (category: ux, would_block: false)
  fi
fi
```
> **Judgment call — headless safety:** the default path is `agent`. Stitch is only ever probed and used when the caller explicitly passes `--source=stitch`, and even then a missing/failed MCP degrades to the agent path rather than halting. Nothing in this command can block on an unavailable external MCP.

### Resume detection
```bash
HAS_ARCHETYPE=$([ -f "docs/design/phases/${PHASE}/specs/archetype-mapping.md" ] && echo true || echo false)
HAS_WIREFRAMES=$(ls docs/design/phases/${PHASE}/specs/*.wireframe.md 2>/dev/null | head -1 && echo true || echo false)
HAS_REVIEW=$([ -f "docs/design/phases/${PHASE}/DESIGN_REVIEW.md" ] && echo true || echo false)
```
**Resume rules:**
- `archetype-mapping.md` exists → skip Step 1
- `*.wireframe.md` exist for a screen → skip Step 2 for that screen (unless `--screen` targets it)
- `DESIGN_REVIEW.md` exists with PASS/FLAG → skip Step 3
- `DESIGN_REVIEW.md` exists with BLOCK → re-run Step 3 (wireframes may have been revised)

### Required reads — ALL design agents load these before producing output
- `docs/PROJECT_FACTS.md` — ground truth (item 0, above)
- `docs/DECISIONS.md` — settled decisions (item 0b, above)
- `docs/design/phases/${PHASE}/specs/data-contracts.md` — **typed response shapes for every endpoint. Source of truth for API bindings.**
- `docs/BRD.md` §FR-UI-* — screen requirements + acceptance criteria
- `docs/IMPLEMENTATION_GUIDELINES.md` §Tech Stack — UI framework + component library
- `docs/design/phases/${PHASE}/PHASE_PLAN.md` + `phase_context.md` — phase scope
- `docs/design/phases/$((PHASE-1))/specs/` — previous phase wireframes (navigation continuity), when PHASE > 1
- Design skills (precedence per `.claude/skills/ui/README.md`):
  - `.claude/skills/ui/professional-ui-standards.md` — spacing, typography, z-index, state discipline
  - `.claude/skills/ui/vertix-portal-design-system.md` — **house style (if the project uses it).** Semantic tokens + `@portal/components` primitives; overrides the generic standards on color/tokens/components.
  - `.claude/skills/ui/structured-wireframe-format.md` — wireframe file format
  - `.claude/skills/ui/accessibility-patterns.md` — heading hierarchy, landmarks, focus order, ARIA
  - `.claude/skills/ui/archetypes/` — page archetypes
  - `.claude/skills/testing/test-case-generation.md` + `test-case-traceability.md` — TC-UI-* matrices

---

## Step 1 — Archetype Scaffold

**Agent:** `wireframe_generator` (sub-agent — quick first pass)

Maps each in-scope screen to exactly one page archetype (list-page / detail-page / form-page / dashboard-page / settings-page) and records customizations.

Writes `docs/design/phases/${PHASE}/specs/archetype-mapping.md`:
```markdown
# UI Archetype Mapping — Phase N
| Screen | FR-* | Archetype | Customizations |
|--------|------|-----------|----------------|
| Users List | FR-010 | list-page | Role filter, bulk invite |
| User Detail | FR-011 | detail-page | Activity tab, team section |
```
If no archetype fits a screen, flag it for `ux_designer` to handle as a custom layout.

---

## Step 2 — Wireframe Specifications (per screen)

**Agent:** `ux_designer` (one pass per screen, or the whole phase in one invocation)

For each screen in the archetype mapping (or the single `--screen` target), `ux_designer` produces the **two-file wireframe contract**:

1. `docs/design/phases/${PHASE}/specs/<screen>.wireframe.html` — **PRIMARY visual reference.** Self-contained (inline CSS, no CDN/build), pixel-accurate, both themes via `data-theme`, both breakpoints (375px + 1280px), all 4 states visible, real content (no Lorem ipsum).
2. `docs/design/phases/${PHASE}/specs/<screen>.wireframe.md` — behavior, data bindings, accessibility, and the TC-UI-* inventory.

The `.wireframe.md` MUST contain (per the `ux_designer` agent definition):
- **Purpose** — user story + `FR-*` reference
- **Components** table — every widget mapped to a named library primitive (shadcn or `@portal/components`), with mobile touch-target size
- **API Bindings** table — each component → endpoint → exact field path from `data-contracts.md` → ARRAY/OBJECT
- **Design tokens** — colors/surfaces/text/severity via semantic tokens (`bg-panel`, `text-ink`, `text-crit`…), never hardcoded hex, when the project has a design system
- **4 States** — loading skeleton (matching layout, not a bare spinner), empty (icon + title + description + CTA), error (icon + friendly message + retry), populated
- **Error Boundary Specification** — scope + recovery per data-fetching component
- **Interaction Flows** — action → API call → UI response, including error/loading flows
- **Accessibility Annotations** — heading hierarchy, landmarks, focus order, ARIA
- **UI Test Case Inventory** — real sequential `TC-UI-*` / `TC-FORM-*` / `TC-COMP-*` IDs from the matrices in `test-case-generation.md` (coordinate ranges with `spec_writer`; every interaction flow and every state gets ≥1 TC ID)

**Hard stop (inherited from `ux_designer`):** if `data-contracts.md` is missing, do not proceed — Step 0 already guards this.

### Step 2s — Stitch Enrichment (only when `STITCH_MODE=stitch`)

When and only when the flag resolved to Stitch-available, enrich each wireframe with a Google Stitch render. This runs the Stitch MCP tools **directly from this command** (there is no separate stitch agent):

1. `mcp__stitch__list_projects` / `mcp__stitch__create_project` (title = "`<project> — Phase N`") — reuse or create the phase's Stitch project.
2. If the project has a design system (`.claude/skills/ui/vertix-portal-design-system.md`): `mcp__stitch__upload_design_md` → `mcp__stitch__create_design_system_from_design_md` so Stitch renders in the house style; pass the resulting `designSystem` id to generation.
3. Per screen: `mcp__stitch__generate_screen_from_text` with a prompt derived from the archetype + `data-contracts.md` bindings + BRD acceptance criteria. Generation can take minutes — **do not retry on timeout**; poll `mcp__stitch__get_screen` every ~30s (up to ~10 times).
4. **Import/normalize:** feed the rendered screen back to `ux_designer`, which reconciles the Stitch output into the SAME two-file contract — extracting exact tokens/spacing into the `.wireframe.html` and keeping bindings/states/a11y/TC-IDs in the `.wireframe.md`. Stitch renders are a visual aid; the canonical artifact is always the wireframe pair, so downstream `ui_developer` consumes one format regardless of source.

If any Stitch call fails mid-run, log it and finish that screen on the pure-agent path — never leave a screen without a wireframe.

---

## Step 3 — Design Quality Gate (BLOCKING)

**Agent:** `design_quality_reviewer`

Validates every wireframe against the **11 dimensions** (API coverage, component mapping, 4-state coverage, interactions, accessibility, responsive, touch targets, consistency, data-contract binding, data-contract cross-reference, design-system adherence — dimension 11 applies when the project has a design system).

Writes `docs/design/phases/${PHASE}/DESIGN_REVIEW.md` with per-screen verdicts and quantitative metrics.

**Verdicts:**
- **PASS** — all dimensions clear → design contract is ready; `ui_developer` may start.
- **FLAG** — minor issues → contract ready, issues logged and carried forward.
- **BLOCK** — critical gaps (missing state, TBD binding, field not in `data-contracts.md`, list component bound to an object endpoint, rebuilt primitive that exists in the shared library, hardcoded colors) → **route back to `ux_designer`** for revision.

**Block loop:**
1. `design_quality_reviewer` lists each BLOCK with location + required fix.
2. `ux_designer` revises the specific wireframe(s).
3. Re-run `design_quality_reviewer`. Max **2** revision cycles.
4. **Interactive mode:** still BLOCK after 2 cycles → STOP and surface to the user with the exact gaps.
   **`--auto` mode:** still BLOCK after 2 cycles → downgrade to WARN, log to `agent_state/autonomous/auto-resolved.jsonl` (`"category":"ux","would_block":false`), and surface at the next human checkpoint. Do NOT halt the pipeline.

**This gate is the hand-off contract:** `/develop`'s `ui_developer` must not begin until `DESIGN_REVIEW.md` exists with a PASS or FLAG (or an `--auto` downgraded WARN). A BLOCK with no downgrade means the design contract is not done.

---

## Step 4 — Design Contract Index

Write `docs/design/phases/${PHASE}/DESIGN_INDEX.md`:
```markdown
# Phase N — UI Design Contract

## Source
Design source: <pure-agent | stitch (with agent-normalized artifacts)>
Stitch fallback: <none | MCP unavailable, used pure-agent>

## Archetype Mapping
- specs/archetype-mapping.md

## Wireframes
- specs/<screen>.wireframe.html — visual reference (open in browser)
- specs/<screen>.wireframe.md   — bindings, states, a11y, TC-UI-* IDs

## Design Review (gate)
- DESIGN_REVIEW.md — 11-dimension verdict per screen

## Test Case Inventory
- TC-UI-* / TC-FORM-* / TC-COMP-* IDs: <ranges>  (tracked to implementation, gated at phase completion)
```

Print summary:
```
✅ Phase N UI design contract ready

  Source: <pure-agent | stitch → normalized>
  Screens: N wireframes (HTML + MD)
  API bindings: all fields resolved against data-contracts.md (0 TBD)
  TC-UI inventory: N IDs (TC-UI-NNN..NNN, TC-FORM-…, TC-COMP-…)
  Design gate: PASS | FLAG (N issues) | WARN (auto-downgraded — review at checkpoint)

  ▶ Next: /plan --phase=N (if not yet planned) → /develop --phase=N
```

---

## Definition of Done (verify before reporting success)

- [ ] A phase with UI scope has, for **every** in-scope screen, both `<screen>.wireframe.html` and `<screen>.wireframe.md` at the exact paths under `docs/design/phases/${PHASE}/specs/`.
- [ ] Every API binding in every `.wireframe.md` references a real field + correct ARRAY/OBJECT shape in `data-contracts.md` — zero "TBD".
- [ ] All 4 states are present in each data-fetching wireframe (not deferred to implementation).
- [ ] `DESIGN_REVIEW.md` exists with a real per-screen verdict (PASS/FLAG, or `--auto` downgraded WARN with a logged reason) — NOT an empty-but-present stub.
- [ ] `TC-UI-*`/`TC-FORM-*`/`TC-COMP-*` IDs are real sequential IDs, coordinated with spec ID ranges — not `NNN` placeholders.
- [ ] `DESIGN_INDEX.md` written; source (agent vs stitch) and any stitch fallback recorded.
- [ ] A backend-only phase exits cleanly as a no-op (no empty artifacts left behind).
- [ ] If `--source=stitch` was requested but the MCP was unavailable, the fallback is logged and the contract is complete on the pure-agent path anyway.

**Anti-rationalization:** a present-but-empty `DESIGN_REVIEW.md` passes a file-exists check but ships an unreviewed design. Run the checklist — a stub is a failure, not a completion.
