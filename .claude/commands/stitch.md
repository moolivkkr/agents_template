---
command: stitch
description: "Work with Google Stitch directly: set up the product's Stitch project and house-style design system, generate/edit/explore screens for web (DESKTOP) or React Native (MOBILE), and sync renders into a phase's wireframe contract behind the design gate."
arguments:
  - name: action
    required: true
    description: "init | generate | variants | edit | theme | sync | status"
  - name: phase
    required: false
    description: "Phase whose screens to work on (generate / variants / edit / sync). Default: current phase."
  - name: screen
    required: false
    description: "Screen name (wireframe base name, e.g. orders-list). Omit on generate/sync to process every in-scope screen."
  - name: device
    required: false
    description: "DESKTOP | MOBILE | TABLET. Default: from tech profile — MOBILE for React Native screens, DESKTOP for web (see stitch-design.md §3)."
  - name: prompt
    required: false
    description: "edit / variants: the change or direction, in plain words. For edit after a design-gate BLOCK, omit it to use the reviewer's fix list."
  - name: count
    required: false
    description: "variants: number of variants 1-5 (default 3)."
  - name: range
    required: false
    description: "variants: REFINE | EXPLORE | REIMAGINE (default EXPLORE)."
---

# /stitch — Google Stitch design workbench

`/design --source=stitch` uses Stitch inside the pipeline. `/stitch` is for working with Stitch on
its own: setting it up once, exploring layouts, fixing a blocked screen, restyling after a theme
change, and pulling renders into the contract.

**Every call sequence, parameter rule and timeout rule is in `~/.claude/skills/ui/stitch-design.md`.
Read it first.** This command orders those steps and records the results.

**Ground truth:** read `docs/PROJECT_FACTS.md` and `docs/DECISIONS.md` first. A screen that
references anything RETIRED is not generated.

**Outbound calls:** every action except `status` calls Google's Stitch service with screen
descriptions derived from the specs. Running `/stitch` is the user's request to do so. The only
thing never done without explicit confirmation is `delete_project`, and this command has no delete action.

---

## Step 0 — Probe and load state (every action)

1. Probe: `get_project` on the stored `projectId` if `stitch.json` has one, else `mcp__stitch__list_projects`.
   `list_projects` is large (every project's theme and screens), so read only name and title from
   the saved result with `jq`. If the call fails or the tool is missing, print
   `⛔ Stitch MCP unavailable — check the "stitch" server in /mcp` and stop. (Pipelines fall back
   to the agent path; this interactive command reports instead.)
2. Read `docs/design/stitch.json` (the schema is in stitch-design.md §2). If there is no stored
   project and the action isn't `init`, stop with `▶ Run /stitch init first`.
3. Resolve the platform from `agent_state/agent_registry.json` (`frontend.enabled`, `mobile.enabled`)
   and set the default `--device`.

## init — project + design system

1. Reuse the stored `projectId` (verify it with `get_project`), or find a project titled
   `"<PROJECT_NAME> — UI"` in `list_projects`, or `create_project` with that title.
2. Resolve the design-system source (stitch-design.md §4). Create it with Path A (structured tokens)
   or Path B (DESIGN.md upload, then `get_project` for the screen instance, then
   `create_design_system_from_design_md`). Store `designSystem.assetId`.
3. Write `stitch.json`. Print the project id, the design-system source and asset id, and any font substitutions.
4. Unless it is already present, append to `docs/DECISIONS.md`: *"Stitch holds the design baseline
   for every page (project <id>, design system assets/<id>). `/ui-audit` keeps the page coverage map in
   stitch.json complete; pages with no baseline are BLOCKING findings."* Then suggest
   `/ui-audit --fix=design` to baseline every existing page.

## generate — render screens for a phase

For each in-scope screen (from `docs/design/phases/N/specs/archetype-mapping.md`, or `--screen`):
1. Build the prompt from the screen's archetype, the `data-contracts.md` fields, the FR-* acceptance
   criteria and the platform (stitch-design.md §5).
2. `generate_screen_from_text` with `projectId`, `prompt`, `deviceType` and
   `designSystem: "assets/<assetId>"`. Don't retry on timeout; poll `get_screen` (30s × 10).
3. Store `screens["N/<screen>/<device>"]` (id, the Stitch-expanded `prompt`, `htmlCode` and `screenshot` file names). Up to 3 generations may run in flight; queue the rest.

Report per screen: `generated | pending (still polling) | failed (reason)`. Generation does not
touch the wireframe contract; run `sync` for that.

## variants — explore alternatives

`generate_variants` on the stored screen id with `prompt`, `deviceType` and
`variantOptions: { variantCount: --count, creativeRange: --range, aspects }`. Choose aspects from
the prompt (layout / colour / fonts / content), or leave them empty to vary everything. List the
returned variant screen ids. Nothing is synced until the user picks one: `/stitch sync --screen=X`
with the chosen id stored in `stitch.json`.

## edit — revise a screen

`edit_screens` on the stored screen id. The prompt is `--prompt`, or, when omitted and the phase's
`DESIGN_REVIEW.md` BLOCKed this screen, the reviewer's fix list for it verbatim. Same polling
rules. **The edit returns a NEW screen id:** store it as `screenId`, move the old id to
`previous`, and then run `sync` for the screen.

## theme — change the house style

Update the design system (`update_design_system` with the stored asset, or recreate it via
Path A/B if the source changed). Then `apply_design_system` to every stored screen instance
(instance ids from `get_project`). Mark those screens `synced_to: stale` in `stitch.json`, so the
next `sync` re-normalizes them.

## sync — pull renders into the phase's wireframe contract

1. For each screen with a stored render (or `--screen`), `get_screen` and save the payload under
   `agent_state/stitch/phase-N/<screen>-<device>.json`, so the agent reads a file and the payload
   isn't echoed into this conversation.
2. Spawn `ux_designer` (`subagent_type: ux_designer`) once for the batch:
   ```
   [GROUND TRUTH line] You are ux_designer normalizing Google Stitch renders for Phase N.
   Follow ~/.claude/skills/ui/stitch-design.md §7 exactly. Inputs: agent_state/stitch/phase-N/*.json,
   docs/design/phases/N/specs/data-contracts.md, archetype-mapping.md, existing wireframes.
   Write/update <screen>.wireframe.html + <screen>.wireframe.md for each screen. Semantic tokens only;
   bindings only from data-contracts.md; all 4 states; mobile screens carry testIDs + Tier 4M TC IDs.
   ```
3. Run the design gate exactly as `/design` Step 3 does: `design_quality_reviewer`, then
   `DESIGN_REVIEW.md`. If it BLOCKs, suggest `/stitch edit --screen=X` (Stitch-side fix) or let
   `ux_designer` revise the wireframe directly. Max 2 cycles, as in `/design`.
4. Update `DESIGN_INDEX.md` (`Source: stitch → normalized`) and `synced_to` in `stitch.json`.

## status — no outbound calls

Print from `stitch.json`: project, design system and source, and per phase each screen key with its
render id, sync state (`synced | stale | not synced`) and last update. Then print the **page
coverage** from `pages`: count per status (`conformant | drift | design_gap | no_baseline | orphan |
stale | pending_sync`), coverage %, and the reconstructed baselines awaiting approval. The data is
as fresh as the last `/ui-audit`, and the date of that audit is shown. Flag wireframes that exist
with no render (agent-only screens), and renders that were never synced.

---

## Definition of Done
- [ ] `docs/design/stitch.json` is updated after every Stitch mutation, and no screen id exists only in the conversation.
- [ ] Every generate/edit/variants call set `deviceType` and `designSystem`, and no timed-out call was retried.
- [ ] `sync` left the wireframe pair as the canonical contract, and the design gate ran on the synced screens.
- [ ] Failures and pending renders are reported per screen, never summarized as success.
