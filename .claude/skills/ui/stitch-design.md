# Google Stitch — driving the Stitch MCP from the design pipeline

How `/design --source=stitch` and `/stitch` use Google Stitch to render screens, and how a Stitch
render becomes the framework's canonical design contract (`<screen>.wireframe.html` + `.wireframe.md`).
**Stitch output is a visual aid. The wireframe pair is the contract.** `ui_developer`,
`mobile_developer` and every test agent consume the wireframe pair, never a Stitch screen directly.

> **Tool surface verified 2026-09-29 against the connected `stitch` MCP** (`https://stitch.googleapis.com/mcp`):
> `list_projects`, `create_project`, `get_project`, `delete_project`, `list_screens`, `get_screen`,
> `generate_screen_from_text`, `edit_screens`, `generate_variants`, `create_design_system`,
> `update_design_system`, `list_design_systems`, `apply_design_system`, `upload_design_md`,
> `create_design_system_from_design_md`. The parameter names below come from the tool schemas.
> **Response field names were not verified** (e.g. exactly where `get_screen` puts the generated
> HTML or screenshot). Inspect the first real response and follow what it returns.
> `tests/dependency-graph.test.sh` fails if a command or skill names a Stitch tool outside this list.
>
> **Live smoke test 2026-09-29** (scratch project, one MOBILE screen). Verified:
> - project creation;
> - design system Path A;
> - `generate_screen_from_text` → `get_screen` → HTML download;
> - `edit_screens`.
>
> The response shapes below come from that run. **Not exercised:** Path B (`upload_design_md`),
> `generate_variants`, `apply_design_system`, and the timeout/polling path (generation returned
> synchronously in about a minute).

---

## 1. Who calls Stitch

- MCP tools are called by the **session running the command**, the parent. Do not delegate Stitch
  calls to a subagent, and never pretend a bash function does it: there is no `mcp_stitch_probe`,
  so probe by calling `mcp__stitch__list_projects`.
- **Availability probe:**
  - If `stitch.json` has a `projectId`, call `get_project` on it.
  - Otherwise call `list_projects`.
  - Success means Stitch mode. An error, timeout or missing tool means log the fallback and continue on
    the pure-agent path. Never block a pipeline on Stitch.
  - **`list_projects` is heavy:** it returns every project with its full theme and every screen
    instance, about 83K characters for 6 projects in the smoke test. Never echo it. Extract only
    `name` and `title` with `jq` from the saved tool-result file.
- These calls reach Google's service with project screen descriptions. Only run them when the user
  (or `--source=stitch`) asked for Stitch.
- **`delete_project` is never called by the pipeline.** Only on an explicit user request, confirmed in the same turn.

## 2. State file: `docs/design/stitch.json`

Stitch IDs have to survive across sessions, or every run creates a new project and loses the link
from a wireframe to its render. Read the file first, write it after every change:

```json
{
  "projectId": "4044680601076201931",
  "projectTitle": "<project> — UI",
  "designSystem": { "assetId": "15996705518239280238", "source": "docs/design/DESIGN.md", "updated": "2026-09-29" },
  "screens": {
    "3/orders-list/DESKTOP": { "screenId": "98b50e2d...", "prompt_hash": "sha1:…", "synced_to": "docs/design/phases/3/specs/orders-list.wireframe.html", "updated": "2026-09-29" },
    "3/orders-list/MOBILE":  { "screenId": "…", "synced_to": null }
  },
  "log": [ { "ts": "…", "op": "generate", "key": "3/orders-list/DESKTOP", "result": "ok" } ]
}
```

- **One Stitch project per product**, not per phase: design systems and screen consistency are
  project-scoped. Key screens by `<phase>/<screen>/<deviceType>`.
- Reuse the stored `projectId`, and verify it with `get_project`. If it is missing, `list_projects`
  and match the title before `create_project`, so a reinstall doesn't create duplicates.
- Commit `stitch.json`. It contains IDs only, no secrets.

## 3. Device type (web vs React Native)

`generate_screen_from_text`, `edit_screens` and `generate_variants` take `deviceType`
(`MOBILE | DESKTOP | TABLET | AGNOSTIC`). Always set it; never leave it unspecified.

| Target (from `agent_registry.json` tech_profile) | deviceType per screen |
|---|---|
| Web UI (`frontend.enabled`) | `DESKTOP` (the 1280px canonical layout); add `MOBILE` only when the screen spec has a distinct 375px layout worth rendering |
| React Native (`mobile.enabled`) | `MOBILE`; add `TABLET` only if the BRD lists tablet support |
| Both, same screen in both apps | Two keys: `…/DESKTOP` for web and `…/MOBILE` for the app. They are different designs; don't reuse one for the other |

## 4. Design system (house style) — resolve the source, then create once

**Source, first match wins:**
1. `docs/design/DESIGN.md` (project-owned design system markdown)
2. `docs/IMPLEMENTATION_GUIDELINES.md` §Design / design tokens
3. A project design-system skill named in IMPLEMENTATION_GUIDELINES (e.g. `ui/vertix-portal-design-system.md` for Vertix portal projects)
4. None → use Stitch's default; `DESIGN_INDEX.md` records "no house style"

**Path A (preferred): structured tokens.** Use this when the source gives a primary colour, fonts, roundness and mode:
1. `create_design_system` with `projectId` and `designSystem: { displayName, theme }`.
   - `theme` requires `colorMode`, `headlineFont`, `bodyFont`, `roundness` and `customColor` (hex).
   - It optionally takes `designMd` (free-form rules), override colours, `typography` and `spacing`.
   - Fonts must be one of the enum values in the schema. If the house font isn't listed, pick the
     closest one and record the substitution.
2. Then `update_design_system` with the returned asset `name` (`assets/<id>`), `projectId` and the
   same `designSystem`, as the tool description requires. This applies it to the project.
   - Verified: create returns `{designSystem, name: "assets/<id>", version: "1"}`.
   - Update returns a `projects/<p>/sessions/<s>` name, not the asset. Keep the asset id from create.
   - Stitch expands the theme into a full Material-style `namedColors` palette (`primary`,
     `on_surface`, `surface_container_*`, …) and picks a `labelFont` if you gave none. It bumps the
     asset `version` on first use.
3. Store `assetId` in `stitch.json`.

**Path B: a DESIGN.md file only.**
1. `upload_design_md` with `projectId` and `designMdBase64`. On macOS: `base64 -i docs/design/DESIGN.md | tr -d '\n'`.
2. `get_project` to find the **screen instance** the upload created: its instance `id` and `sourceScreen` (`projects/<p>/screens/<s>`).
3. `create_design_system_from_design_md` with `projectId` and `selectedScreenInstance: { id, sourceScreen }`, plus `deviceType`.
4. `list_design_systems(projectId)` to read the resulting asset id, then store it.

Skipping step 2 is why the old `/design` Step 2s could never create a design system.

Pass `designSystem: "assets/<assetId>"` on **every** `generate_screen_from_text` call. To restyle
existing screens after a theme change, call `apply_design_system` with `projectId`, `assetId` and
`selectedScreenInstances` (instance ids from `get_project`).

## 5. Generating a screen

Build the prompt from the contract, not from memory, so the render matches what will be built:

```
<Screen name> — <archetype> for <persona> (<FR-ids>).
Platform: <web desktop 1280px | iOS/Android phone app (React Native)>.
Purpose: <one-sentence user story>.
Data shown (from data-contracts.md): <entity>: <field list with types>; list endpoint returns an ARRAY.
Primary actions: <buttons/gestures>. Navigation: <from → to>.
Show the POPULATED state with realistic content (no lorem ipsum).
Constraints: <house-style rules: semantic tokens, component library>, touch targets ≥44pt (mobile),
WCAG AA contrast, visible labels on every input.
```

Call `generate_screen_from_text` with `projectId`, `prompt`, `deviceType` and `designSystem`.
Leave `modelId` unset unless DECISIONS.md picks one. The enum currently lists
`GEMINI_3_8_FLASH` and `GEMINI_3_5_FLASH_LITE`; don't hard-code either.

**Timeouts (from the tool contract):**
- Generation can take minutes. **Do not retry** a timed-out or connection-failed call; the
  generation may still succeed.
- Poll `get_screen` (`projects/<p>/screens/<s>`) every ~30s, up to 10 times.
- If the failed call returned no screen id, use `list_screens(projectId)` and take the new id
  that isn't in `stitch.json`.
- After 10 polls with nothing, finish that screen on the pure-agent path and log it.

**Verified response shape** (`generate_screen_from_text` and `edit_screens`):
```
outputComponents[0].design.screens[0] = {
  id, name: "projects/<p>/screens/<id>", title, deviceType, width, height,   // width/height are 2× (780×1768 for a 390pt phone)
  prompt,                      // Stitch's EXPANDED prompt; store it, it shows what Stitch assumed
  htmlCode:   { downloadUrl, mimeType: "text/html", name },
  screenshot: { downloadUrl, name },
  theme: { …namedColors… }, screenMetadata: { status: "COMPLETE" }
}
outputComponents[1].text        // Stitch's summary
outputComponents[2..].suggestion
```
`get_screen` returns the compact form: `name, title, deviceType, width, height, htmlCode,
screenshot`, with **no status field**. When polling, the screen is ready once
`htmlCode.downloadUrl` is present. Both download URLs are plain HTTPS; `curl -sL` fetches them
without auth.

**Stitch invents content.** From a contract listing 5 fields, the smoke test added line-item
counts, carriers, a pending-total card, search, a bottom nav and 2023 dates. Treat every render as
unverified against `data-contracts.md`. §7 strips anything that isn't in the contract, and
`edit_screens` fixes it cleanly when asked (verified).

If the response's `outputComponents` contains suggestions, record them in the log. In a pipeline
run, don't act on them; in an interactive `/stitch` session, show them to the user.

Render one state per call (populated). Loading/empty/error states are specified in the
`.wireframe.md` and drawn in the `.wireframe.html` by `ux_designer`. Rendering four Stitch screens
per screen costs 4× for little value.

## 6. Revising and exploring

| Need | Tool | Key params |
|---|---|---|
| `design_quality_reviewer` BLOCKed a screen (e.g. contrast, missing label, wrong density) | `edit_screens` | `projectId`, `selectedScreenIds: [id]`, `prompt` = the reviewer's exact fix list, `deviceType` |
| Explore layout alternatives before committing | `generate_variants` | `selectedScreenIds`, `prompt`, `variantOptions: { variantCount: 1-5, creativeRange: REFINE\|EXPLORE\|REIMAGINE, aspects: [LAYOUT, COLOR_SCHEME, …] }` |
| Theme changed | `apply_design_system` | as in §4 |

**`edit_screens` creates a NEW screen; it does not edit in place (verified).** The response carries
a new `id`. Replace `screenId` in `stitch.json` with it, keep the old id under `previous`, and sync
from the new one. Syncing the stored old id would silently pull the unfixed render.

`edit_screens` and `generate_variants` follow the same no-retry and polling rules. After an edit,
re-sync (§7) and re-run the design gate; an edited render doesn't count until the wireframe pair
is updated.

## 7. Syncing a render into the wireframe contract (normalization)

`ux_designer` does this, reading the `get_screen` payload plus the screen's contract inputs:

1. **`.wireframe.html`** (verified input: Stitch HTML is **not** self-contained)
   - It loads `cdn.tailwindcss.com`, Google Fonts and Material Symbols, and styles through Tailwind
     classes bound to Stitch's Material colour names (`bg-surface`, `text-on-surface-variant`).
   - Produce a self-contained file with inline CSS and no CDN. Map Stitch's `namedColors` to the
     project's semantic tokens and record the mapping. Replace icon-font glyphs with inline SVG or the
     component library's icons.
   - MOBILE renders are HTML inside a 390×844 phone frame, a visual reference for React Native, not code.
   - Take layout, spacing, hierarchy and composition from the render.
   - Replace raw colours and fonts with the project's **semantic tokens** (the design gate BLOCKs hardcoded hex when a design system exists).
   - Map each visual element to a named component-library primitive (web) or RN component (mobile).
   - Add the missing states and both themes. The render shows only the populated state.
2. **`.wireframe.md`**
   - Keep bindings, states, interactions, accessibility and TC-* IDs from the data contracts and the test-case matrices.
   - Stitch never decides a binding. A render field with no `data-contracts.md` counterpart is removed or flagged, not invented.
3. **Mobile screens**
   - Stitch adds some `aria-label`s but **no test IDs** (verified).
   - Add the `testID` for every interactive element and assertion target (`<screen>.<element>`, per `../testing/mobile-testing-strategy.md` §4).
   - Use the Tier 4M TC matrix.
4. Record `synced_to` and the date in `stitch.json`, and set `Source: stitch → normalized` in `DESIGN_INDEX.md`.

A render that contradicts the data contracts (e.g. shows a field the API doesn't return) loses: the
wireframe follows the contract, and the discrepancy goes in the log.

## 8. Anti-patterns

- Creating a new Stitch project on every run (duplicates, lost design system). Use `stitch.json`.
- Generating without `designSystem`, which gives off-brand renders that then fail design-gate dimension 11.
- Retrying a timed-out generation, which produces duplicate screens and wasted quota. Poll instead.
- Treating a Stitch render as the spec, so `ui_developer` builds from a screenshot and skips states and bindings.
- `DEVICE_TYPE_UNSPECIFIED` for a React Native screen, which renders a web layout that the mobile app can't match.
- Calling `delete_project` to "clean up".
