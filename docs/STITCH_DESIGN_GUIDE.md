# Stitch Design Guide — `/stitch`, `/design --source=stitch`, `/ui-audit`

How the framework uses Google Stitch to render screens for web and React Native, turns those renders
into the design contract that developers build from, and keeps every built page checked against its
Stitch baseline.

**The rule to remember:** a Stitch render is a visual aid. The **wireframe pair**
(`<screen>.wireframe.html` + `<screen>.wireframe.md`) is the contract. `ui_developer`,
`mobile_developer` and every test agent consume the wireframe pair, never a Stitch screen directly.

Source of truth for every call sequence and rule: `.claude/skills/ui/stitch-design.md`.

---

## 1. Prerequisites

- The Google Stitch MCP server connected to Claude Code as `stitch` (check with `/mcp`).
- Stitch calls send screen descriptions derived from your specs to Google's service. They only run
  when you ask for Stitch: `/startup:stitch`, `/startup:ui-audit --fix=design|all`, or
  `/startup:design --source=stitch` (which `/startup:autonomous` passes for UI phases).
- MCP tools are called by the session running the command (the parent), never by a subagent.
- The pipeline never calls `delete_project`.

**Never blocks a pipeline.** `/design --source=stitch` probes the MCP first (`get_project` on the
stored project, or `list_projects` when there is none). If the probe errors, times out or the tool
is missing, `/design` falls back to the pure-agent path (`ux_designer` + `wireframe_generator`) and
logs the fallback. `/stitch`, being interactive, reports `⛔ Stitch MCP unavailable` and stops.

## 2. State file: `docs/design/stitch.json`

Stitch ids must survive across sessions, so every command reads this file first and writes it
after every Stitch change. Commit it; it holds ids, not secrets.

| Key | Holds |
|-----|-------|
| `projectId`, `projectTitle` | One Stitch project per product (not per phase), titled `"<PROJECT_NAME> — UI"` |
| `designSystem` | `assetId`, the source it was built from, date |
| `screens` | Keyed `<phase>/<screen>/<deviceType>`: `screenId` (and `previous` after an edit), expanded prompt, `synced_to` wireframe path |
| `pages` | The all-pages baseline map, keyed `<app>:<route>\|<deviceType>`: `screenKey`, `baseline` type, `status`, `last_audit` |
| `log` | Every operation and its result |

## 3. Device type — web vs React Native

Every generate / edit / variants call sets `deviceType`:

| Target | deviceType |
|--------|------------|
| Web UI (`frontend.enabled`) | `DESKTOP` (1280px canonical); add `MOBILE` only for a distinct 375px layout |
| React Native (`mobile.enabled`) | `MOBILE`; `TABLET` only if the BRD lists tablet support |
| Same screen in both apps | Two keys, `…/DESKTOP` and `…/MOBILE` — they are different designs |

Mobile-only projects (no web frontend) are included: `/design`'s UI-phase check accepts either a web
frontend or a React Native app.

## 4. Setting up — `/startup:stitch init`

1. Reuse the stored project (verified with `get_project`), else find one by title in
   `list_projects`, else `create_project`.
2. Create the house-style design system once. Source, first match wins: `docs/design/DESIGN.md` →
   IMPLEMENTATION_GUIDELINES design tokens → a project design-system skill → Stitch's default.
   - **Path A (preferred), structured tokens:** `create_design_system`, then
     `update_design_system` with the returned asset. Fonts must be from Stitch's enum; substitutions
     are recorded.
   - **Path B, a DESIGN.md only:** `upload_design_md`, then `get_project` to find the screen
     instance the upload created, then `create_design_system_from_design_md` with that
     `selectedScreenInstance`, then `list_design_systems` for the asset id.
3. Write `stitch.json` and append a decision to `docs/DECISIONS.md`: *"Stitch holds the design
   baseline for every page."* It then suggests `/startup:ui-audit --fix=design` to baseline the
   pages that already exist.

## 5. Designing a phase — `/startup:design --source=stitch`

Runs after `/startup:plan` (it needs `PHASE_PLAN.md` and `specs/data-contracts.md`).

```
wireframe_generator   → maps screens to page archetypes (specs/archetype-mapping.md)
Step 2s (Stitch)      → project + design system; per screen generate_screen_from_text
                        (prompt from archetype + data-contracts fields + FR-* criteria,
                         deviceType, designSystem); no retry on timeout — poll get_screen
ux_designer           → normalizes each render into the wireframe pair
design_quality_reviewer → BLOCKING 11-dimension gate → DESIGN_REVIEW.md
```

**Normalization** (`ux_designer`):
- Stitch HTML is not self-contained (it loads the Tailwind CDN, Google Fonts and Material Symbols).
  The wireframe `.html` inlines the CSS, maps Stitch's colour names to the project's semantic tokens,
  and replaces icon fonts.
- Stitch invents content (the smoke test added fields, cards and navigation the contract never
  listed). Any field with no `data-contracts.md` counterpart is removed or flagged; bindings,
  states, accessibility and TC-* ids come from the contracts.
- Stitch renders one populated state; `ux_designer` adds loading / empty / error and both themes.
- Mobile screens: Stitch adds no test IDs, so `ux_designer` adds a `testID` for every interactive
  element and the Tier 4M TC inventory.

**Design gate BLOCK loop** (max 2 cycles): a visual BLOCK (contrast, density, missing label, layout)
on a Stitch screen is sent verbatim to `edit_screens`, and the new render is re-normalized;
binding, state and contract BLOCKs are fixed in the wireframe directly. Still blocked after 2
cycles: interactive runs stop and show the gaps; `--auto` runs downgrade to WARN, log it, and surface
it at the next human checkpoint.

## 6. The workbench — `/startup:stitch <action>`

| Action | What it does |
|--------|--------------|
| `init` | Project + design system (§4) |
| `generate` | Renders every in-scope screen of a phase (or `--screen`). Up to 3 generations in flight; no retry, poll `get_screen`. Does not touch the wireframe contract |
| `variants` | `generate_variants` (`--count` 1–5, `--range` REFINE / EXPLORE / REIMAGINE). Nothing syncs until you pick one |
| `edit` | `edit_screens` with `--prompt`, or the reviewer's fix list after a design-gate BLOCK |
| `theme` | Updates the design system, then `apply_design_system` to every stored screen; marks them stale |
| `sync` | Saves `get_screen` payloads to `agent_state/stitch/phase-N/`, `ux_designer` normalizes them, then the design gate runs as in `/design` |
| `status` | No outbound calls. Per-screen render/sync state and page coverage from `pages` |

**`edit_screens` returns a NEW screen id** (it does not edit in place). The commands store the new
id as `screenId` and keep the old one as `previous`; syncing the old id would pull the unfixed
render.

**`list_projects` is heavy** (about 83K characters for 6 projects in the smoke test): the commands
extract only project names and titles with `jq` and never echo the full result.

## 7. Auditing built pages — `/startup:ui-audit`

The design gate checks wireframes before code. `ui_standards_auditor` checks the **built** pages
afterwards, across the whole app, and keeps Stitch holding a baseline for every page. It runs in
`/develop` Wave 4 whenever web UI or mobile screens changed, and on demand through `/ui-audit`.

**Page inventory** = routes in code (Next.js / React Router / Vue Router; Expo Router or registered
navigators for React Native) ∪ wireframes ∪ Stitch screens. Anything in only one source is a
finding. The app must be running (web app, or binaries on a booted simulator and emulator);
otherwise the audit is marked static-only.

**Standards checks** (S1–S9): tokens only, type scale, spacing scale, four states, library
primitives reused, no overflow at 375px / safe areas, archetype consistency, only contract fields,
and the built page matches its baseline. WCAG and native-platform issues are left to
`accessibility_auditor` and `mobile_platform_auditor`.

**Page status:**

| Status | Meaning | Route |
|--------|---------|-------|
| `conformant` | Matches its baseline and the standards | — |
| `drift` | Built page deviates from its baseline | code fix → `ui_developer` / `mobile_developer` |
| `design_gap` | The baseline itself breaks a standard | `edit_screens` → re-normalize → design gate |
| `no_baseline` | Page exists in code, no Stitch screen | generate a baseline from a page description |
| `orphan` | Stitch screen or wireframe with no route | report (unbuilt page or stale design) |

**Baselines for existing pages.** Stitch can't ingest a screenshot, so the auditor captures the
page, writes a text description of it (checked against `data-contracts.md`) plus its standards
corrections, and requests a `generate`. When no wireframe decided the target, the result is marked
`baseline: "reconstructed"` and needs human approval before any code is changed to match it.

The auditor never calls Stitch; it writes `ui_standards_stitch_requests.json`, and the parent
executes those requests.

```
/startup:ui-audit                        # report only: coverage matrix, findings, pending Stitch requests
/startup:ui-audit --fix=design           # parent runs the Stitch requests → ux_designer → design gate
/startup:ui-audit --fix=code             # drift against spec/approved baselines → developers → test_runner
/startup:ui-audit --fix=all              # both, then re-audit changed pages (max 2 rounds)
/startup:ui-audit --approve=web:/orders|DESKTOP,mobile:/orders|MOBILE
                                         # approve reconstructed baselines (recorded in DECISIONS.md)
/startup:ui-audit --app=mobile --page=/orders
```

Reports: `agent_state/phases/N/reports/ui_standards_audit.md` + `.json` and
`ui_standards_stitch_requests.json`, with baseline coverage before and after.

## 8. What was verified, and what wasn't

The skill records a live smoke test against the connected Stitch MCP on 2026-09-29 (one scratch
project, one MOBILE screen). Verified: the tool list, project creation, design system Path A,
`generate_screen_from_text` → `get_screen` → HTML download, and `edit_screens` (new id). **Not
exercised:** Path B (`upload_design_md`), `generate_variants`, `apply_design_system`, and the
timeout/polling path. Response field names beyond that run were not verified; the commands inspect
the first real response. `tests/dependency-graph.test.sh` fails if any command, agent or skill names
a Stitch tool outside the verified list.
