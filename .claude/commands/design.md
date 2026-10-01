---
command: design
description: Generate the UI/design contract for a phase — wireframe specs, component/API bindings, design tokens, and TC-UI-* test cases — gated by design_quality_reviewer before UI implementation. Produces docs/design/phases/N/specs/*.wireframe.{html,md}.
arguments:
  - name: phase
    required: false
    description: "Phase number to design (e.g. 1, 2, 3). Omit to auto-detect the current phase from docs/design/phases/."
  - name: source
    required: false
    description: "Design source. Omit (default) = Google Stitch, the core designer, whenever the stitch MCP is configured: each new or changed screen is designed in Stitch, approved (owner; design_quality_reviewer under --auto), then normalized into the wireframe pair. --source=wireframe = the text-wireframe-only path (wireframe_generator + ux_designer), used only when Stitch is unavailable or the owner explicitly chooses it. --source=stitch is accepted as an alias of the default."
  - name: screen
    required: false
    description: "Restrict to a single screen name (regenerate one wireframe instead of the whole phase)."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode — no user prompts. BLOCK verdicts trigger auto-fix (max 2 cycles); if still blocked, downgrade to WARN, log, and surface at the next human checkpoint rather than halting."
---

# /design — Phase UI Design Contract

> **Before this command finishes:** run `~/.claude/skills/core/child-returns.md` § "Before a command finishes", so every debate this phase raised is decided before `/develop` builds on it.
>
> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

> **Auto mode.** `--auto` is set, OR `agent_state/autonomous/run.json` has `"status":"running"` (this
> command was invoked by `/autonomous`). In auto mode, never wait for the user: every "surface to
> user" / "escalate to user" / STOP-for-input point below instead auto-resolves with the recommended
> option, is logged to `agent_state/autonomous/auto-resolved.jsonl` (full question, options, choice,
> rationale, category; `"category":"security","security_flag":true` for security topics), and is
> carried forward to the next human checkpoint. The exception is a security decision with no
> hardened default, which sets `run.json` `status` to `awaiting_human`. The closing "▶ Next: …" line
> is for standalone use only; under `/autonomous`, return control to it without ending the turn.

Generates the **UI design contract** for a phase: per-screen wireframes (visual + behavioral), typed API bindings, design tokens, and the `TC-UI-*` test-case inventory. The output of `/design` is the contract that `ui_developer` implements during `/develop` — it stands to the frontend exactly as `/plan`'s TRDs stand to the backend.

**Google Stitch is the designer by default** (`~/.claude/skills/ui/stitch-design.md`). Whenever the
`stitch` MCP is configured, every new or changed screen of the phase (web `DESKTOP`, React Native
`MOBILE`) is designed in Stitch first, approved (owner interactively, `design_quality_reviewer` under
`--auto`), stored under `docs/design/stitch/<key>/`, and only then normalized into the wireframe
pair. Developers build against both the approved render and the wireframe. `--source=wireframe` is
the text-only path, for when Stitch is unavailable or the owner chooses it.

`/design` is a **first-class, standalone command**. It is invoked directly, by `/plan` Step 3 for UI phases, and by `/autonomous` (Step 2a.5 / Step 5) before implementation begins. Running it standalone lets you regenerate the design contract after a data-contract change without re-running the whole plan.

**Prerequisites:**
- `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` exist (run `/init` first).
- `docs/design/phases/${PHASE}/specs/data-contracts.md` exists (run `/plan` Step 2b first). **API bindings cannot be produced without it — hard stop if missing.**

**Not a UI phase?** If `IMPLEMENTATION_GUIDELINES.md` shows `frontend.enabled = false`, or the phase scope has no UI screens, `/design` is a no-op that prints `▶ Phase N has no UI screens — skipping design.` and exits 0. It never blocks a backend-only phase.

---

## Ground Truth & Decisions (read before generating)

- `docs/PROJECT_FACTS.md` — **GROUND TRUTH (Tier 0).** Read FIRST. Retired/renamed components, hard constraints, environment facts. OVERRIDES any conflicting assumption in this prompt, the specs, or agent training. If a screen references anything marked RETIRED/superseded, STOP and flag it. (Protocol: `~/.claude/skills/core/shared-context-protocol.md`)
- `docs/DECISIONS.md` — settled decisions (Tier 0.5). Do not re-litigate an active UI/design decision without new evidence.

Every agent this command spawns inherits Required-Reading item 0/0b via `~/.claude/skills/core/agent-common.md` and the orchestrator ground-truth injection line. Do not skip it because "it's just a wireframe."

---

## Session Context Budget

> Full protocol: `~/.claude/skills/core/context-budget-protocol.md`. Per-step targets below are specific to this command.

**Agent result discipline:** Every agent returns a 3-line summary to the parent. Full wireframe content lives in files — never echoed back to the conversation.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1 Archetype scaffold | ~8K (PHASE_PLAN §UI scope + BRD §FR-UI-*) |
| Step 2 Wireframe per screen | ~15K (phase_context + data-contracts + archetype + design system) |
| Step 2s Stitch design (default) | ~10K per screen (design brief + approved render + payload file) |
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
| "Stitch isn't available, so skip the whole design step" | NO. Interactive: stop with NEEDS_INPUT "connect Stitch" (or the owner answers "wireframe"). `--auto`: defer each screen in `stitch.json` (`no_baseline` + queue), design it on the wireframe path, continue. Never skip the design. |
| "The render looks right, I'll normalize it before anyone approves" | Nothing is normalized or implemented from an unapproved render. Owner approves (interactive); `design_quality_reviewer` approves under `--auto` and the screen joins the owner-review list. |
| "This screen only changed a little, edit the wireframe directly" | A change to a Stitch-designed screen goes to Stitch first (`edit_screens`), is approved, then re-normalized. Editing only the wireframe makes Stitch disagree with the shipped UI. |
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
# a web frontend OR a React Native app must be enabled AND the phase must have UI-flavored scope
FRONTEND=$(jq -r '(.tech_profile.frontend.enabled // false) or (.tech_profile.mobile.enabled // false)' agent_state/agent_registry.json 2>/dev/null | grep -x true \
  || grep -iE "frontend.*enabled|frontend:.*true|Section 24: Mobile|React Native" docs/IMPLEMENTATION_GUIDELINES.md 2>/dev/null | head -1)
HAS_UI_SCOPE=$(grep -iE "FR-UI-|UI|interface|screen|dashboard|component|widget|chat|graph|form|page" \
  "docs/design/phases/${PHASE}/PHASE_PLAN.md" 2>/dev/null | head -1)
```
If neither a web frontend nor a mobile app is enabled, OR there is no UI scope:
```
▶ Phase ${PHASE} has no UI screens — skipping design.
```
Exit 0. This is the graceful no-op for backend-only phases.

### Design source and the Stitch probe (Stitch is the default)

`--source=wireframe` → `STITCH_MODE=wireframe`: Stitch is not contacted; record
`Design source: wireframe (owner choice)` in `DESIGN_INDEX.md` and a D-NNN in `docs/DECISIONS.md`
if it isn't already there.

Otherwise (no `--source`, or the alias `--source=stitch`) probe Stitch. The probe is an **MCP call
made by this session**, not a shell function: `get_project` on the `projectId` stored in
`docs/design/stitch.json`, or `mcp__stitch__list_projects` when there is none (`list_projects`
returns every project's theme and screens, so extract only name and title with `jq`; never echo it).
- It returns → `STITCH_MODE=stitch`, print `✅ Stitch is the designer — every in-scope screen is designed and approved in Stitch first.`
  No stored project yet: an app with existing pages runs `/stitch import` first (every page gets a
  baseline); a greenfield app runs `/stitch init`.
- It errors, times out, or the tool doesn't exist:
  - **interactive** → stop:
    `NEEDS_INPUT: connect Stitch — the "stitch" MCP server is not reachable (<error>). Connect it in /mcp and re-run /design, or answer "wireframe" to design this phase on the text-wireframe path.`
    "wireframe" → `STITCH_MODE=wireframe` with the owner's choice recorded.
  - **`--auto`** → `STITCH_MODE=deferred`: for every in-scope screen run
    `python3 .claude/hooks/stitch-state.py defer <key> --detail "<probe error>" --device <D> --app <web|mobile> --route <route>`
    (status `no_baseline`, a `deferred` record, a queue entry), design on the wireframe path, and
    append `{"category":"ux","would_block":false,"reason":"stitch unavailable — screens queued for Stitch"}`
    to `agent_state/autonomous/auto-resolved.jsonl`. The phase gate passes those screens with a
    WARNING; the queue is drained the next time Stitch is reachable.

> **Judgment call — headless safety:** `/autonomous` never blocks on the external MCP (it defers and
> continues on the wireframe path, and the deferral is visible in `stitch.json`, the gate output and
> the final report). Interactive runs stop instead, because designing silently without Stitch is
> exactly the drift this pipeline exists to prevent.

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
- Design skills (precedence per `~/.claude/skills/ui/README.md`):
  - `~/.claude/skills/ui/professional-ui-standards.md` — spacing, typography, z-index, state discipline
  - The project design system — **only if the project names one** (`agent_state/agent_registry.json` → `tech_profile.frontend.design_system`). Its semantic tokens and component library override the generic standards on color/tokens/components. None named → the generic standards rule; never load another product's pack from `~/.claude/skills/ui/`.
  - `~/.claude/skills/ui/structured-wireframe-format.md` — wireframe file format
  - `~/.claude/skills/ui/stitch-design.md` — **always read it** (Stitch is the default designer): the lifecycle, call sequences, device types, the approval loop, render → wireframe normalization
  - React Native screens (`mobile.enabled`): `~/.claude/skills/frameworks/react-native-app-patterns.md` + `~/.claude/skills/testing/mobile-testing-strategy.md` §4 (testIDs); wireframes use a phone frame (and tablet if in BRD) instead of the 375/1280 web breakpoints
  - `~/.claude/skills/ui/accessibility-patterns.md` — heading hierarchy, landmarks, focus order, ARIA
  - `~/.claude/skills/ui/archetypes/` — page archetypes
  - `~/.claude/skills/testing/test-case-generation.md` + `test-case-traceability.md` — TC-UI-* matrices

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

**Order.** In Stitch mode (the default) **Step 2s runs first**: each new or changed screen is
generated or edited in Stitch and approved, and Step 2 then normalizes the pair from the approved
render (stitch-design.md §6.5). Only in `wireframe` or `deferred` mode does `ux_designer` design the
screen from the archetype alone.

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

### Step 2s — Stitch design (default: `STITCH_MODE=stitch`)

This runs **before** the wireframes are written: in Stitch mode the wireframe pair is normalized
from the approved render. This session makes the MCP calls directly and records every result
through `.claude/hooks/stitch-state.py`. **Every call sequence and rule is in
`~/.claude/skills/ui/stitch-design.md`; follow it. The steps below are the order.**

1. **Project + design system** (§2, §5): load `docs/design/stitch.json` (`stitch-state.py validate`),
   reuse the stored project (verify with `get_project`), or match it by title in `list_projects`,
   else `create_project` titled `"<PROJECT_NAME> — UI"`. One project per product, not per phase.
   If no design-system asset is stored, resolve the source (`docs/design/DESIGN.md` →
   IMPLEMENTATION_GUIDELINES design tokens → a project design-system skill → none) and create it.
   Use Path A (`create_design_system`, then `update_design_system`) or Path B (`upload_design_md`,
   then `get_project` for the uploaded screen instance, then `create_design_system_from_design_md`
   with `selectedScreenInstance`). Store the asset id.
2. **Per screen — new or changed only** (§4, §6.1–6.3). Key `<screen>.<desktop|mobile>`; `deviceType`
   from the platform (`MOBILE` for React Native screens, `DESKTOP` for web).
   - **New screen:** prompt from the archetype, the `data-contracts.md` fields and the FR-* acceptance
     criteria → `mcp__stitch__generate_screen_from_text` with `projectId`, `prompt`, `deviceType`,
     `designSystem: "assets/<id>"`.
   - **Changed screen** (an existing key this phase's scope changes): an edit prompt naming the change
     and its FR / CR → `mcp__stitch__edit_screens` on the stored `screenId`. It returns a **new** id.
   - **Unchanged screen** with an approved, current render: nothing to send.
   **Do not retry** on timeout: poll `get_screen` every ~30s up to 10 times (`list_screens` finds the
   id if the call returned none). Then `stitch-state.py revise …` and fetch + `stitch-state.py render …`.
3. **Approve** (§6.4, the approval loop in `/stitch`):
   - interactive → the **owner** sees the local screenshot path and approves, or gives an edit
     prompt that loops through `edit_screens` until approved (`stitch-state.py approve <key> --by owner`);
   - `--auto` → `design_quality_reviewer` in render-approval mode approves
     (`approve <key> --by design_quality_reviewer`), BLOCK fix lists go back as edits (max 2 cycles),
     and every such screen is on the owner-review list (`stitch-state.py review-list`).
4. **Normalize** (§6.5): spawn `ux_designer` with the approved renders
   (`docs/design/stitch/<key>/screenshot.png` + `screen.html`) and their payload files. It writes the
   SAME two-file contract as Step 2: layout and spacing from the render, colours and fonts as semantic
   tokens, bindings/states/a11y/TC IDs from the contracts, the render path + rev + sha in the header,
   a `Render ref` column in the Data Element Inventory, plus testIDs and Tier 4M TCs for mobile.

If a Stitch call fails mid-run: interactive → report that screen and stop for the owner;
`--auto` → `stitch-state.py defer` that screen and finish it on the wireframe path. Never leave a
screen without a wireframe, and never record a screen as approved that wasn't.

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
2. `ux_designer` revises the specific wireframe(s). If the screen came from Stitch
   (`STITCH_MODE=stitch`) and the BLOCK is visual (contrast, density, missing label, layout), first
   send the reviewer's fix list verbatim to `mcp__stitch__edit_screens` for that screen (same
   `deviceType`; poll, don't retry). The edit returns a **new** screen id and a new revision that
   goes through the approval loop again (Step 2s.3) before re-normalizing (stitch-design.md §6).
   Binding, state and contract BLOCKs are fixed in the wireframe directly; Stitch doesn't own those.
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
Design source: <stitch (approved renders, normalized) | wireframe (owner choice) | deferred (Stitch unavailable, queued)>
Stitch: <screen key → rev, approved by owner|design_quality_reviewer, render docs/design/stitch/<key>/>
Owner review pending: <keys approved autonomously, or none>

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

  Source: <stitch → approved → normalized | wireframe (owner choice) | deferred (Stitch unavailable)>
  Stitch: N new · N changed · N unchanged · approved by owner N / design_quality_reviewer N · deferred N
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
- [ ] `DESIGN_INDEX.md` written; source (stitch / wireframe / deferred), approvals and any owner-review items recorded.
- [ ] A backend-only phase exits cleanly as a no-op (no empty artifacts left behind).
- [ ] Stitch unavailable: interactive runs stopped with NEEDS_INPUT (or the owner chose "wireframe", recorded); `--auto` runs deferred every in-scope screen in `stitch.json` and completed the contract on the wireframe path.
- [ ] In Stitch mode: every new or changed screen has an approved latest revision whose render is stored under `docs/design/stitch/<key>/`; `stitch-state.py validate --check-files` passes; every generation set `deviceType` + `designSystem`; no timed-out call was retried.
- [ ] Every wireframe of a Stitch screen was normalized from its approved render and names it (path, rev, sha).

**Anti-rationalization:** a present-but-empty `DESIGN_REVIEW.md` passes a file-exists check but ships an unreviewed design. Run the checklist — a stub is a failure, not a completion.
