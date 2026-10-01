# Google Stitch — the core, two-way designer

Google Stitch is where this framework designs UI. **Every new or changed screen, web (`DESKTOP`) and
React Native (`MOBILE`), is designed in Stitch first:** a prompt goes to Stitch, the render comes
back, someone approves it, and only then is it implemented. Changes flow both ways: a requirement
change reaches Stitch before it reaches code, and a justified change made in code is synced back to
Stitch, so Stitch never silently disagrees with the shipped UI.

Two artifacts come out of every approved design, and developers use both:
- **the approved render** (`docs/design/stitch/<screenKey>/screenshot.png` + `screen.html`, hashed in
  `stitch.json`): the visual target (layout, spacing, hierarchy, density);
- **the normalized wireframe pair** (`<screen>.wireframe.html` + `.wireframe.md`): the contract for
  bindings, the four states, interactions, accessibility, testIDs and TC IDs.

Stitch's HTML is never pasted into the product. Developers rebuild the render with the project's own
components and tokens.

> **Tool surface verified 2026-09-29 against the connected `stitch` MCP** (`https://stitch.googleapis.com/mcp`):
> `list_projects`, `create_project`, `get_project`, `delete_project`, `list_screens`, `get_screen`,
> `generate_screen_from_text`, `edit_screens`, `generate_variants`, `create_design_system`,
> `update_design_system`, `list_design_systems`, `apply_design_system`, `upload_design_md`,
> `create_design_system_from_design_md`. There is **no image or screenshot upload tool**: Stitch's
> web app can import screenshots (Experimental Mode), but only through its UI. The parameter names
> below come from the tool schemas. `tests/dependency-graph.test.sh` fails if a command or skill
> names a Stitch tool outside this list.
>
> **Live smoke test 2026-09-29** (scratch project, one MOBILE screen) verified project creation,
> design system Path A, `generate_screen_from_text` → `get_screen` → HTML download, and
> `edit_screens` returning a new screen id. The response shapes in §6.3 come from that one run.
> **Not exercised yet**, so inspect the first real response and follow what it returns:
> Path B (`upload_design_md` and the screen instance it creates), `generate_variants`,
> `apply_design_system`, `list_screens` titles and order (needed by `/stitch adopt`), the
> timeout/polling path (generation returned synchronously in about a minute), how long the
> `downloadUrl`s stay valid, and whether `screenshot.downloadUrl` is always a PNG at 2× scale.
> §12 lists exactly what the first live `/stitch import` must confirm.

---

## 0. The lifecycle at a glance

```text
            ┌───────────── bootstrap (once per product, §3) ─────────────┐
 no Stitch  │ /stitch import: capture every page → DESIGN.md → design    │
 project ──▶│ system → recreate each page → score fidelity → approve     │──▶ baseline for EVERY page
            │ /stitch adopt: owner uploads screenshots in Stitch's UI,   │
            │ adopt maps list_screens → routes                           │
            └────────────────────────────────────────────────────────────┘

 forward (design → code, §6)
   requirement / phase scope / owner idea
     → prompt → generate_screen_from_text | edit_screens → get_screen → store render (+hash)
     → APPROVE (owner interactively · design_quality_reviewer under /autonomous)   ◀─┐ edit prompt
     → ux_designer normalizes → design gate → ui_developer / mobile_developer build   │ (loop until
       against render + wireframe                                                     │  approved)
                                                                                      ┘
 reverse (code / requirements → Stitch, §7)
   CR, /recon, /hotfix, later-phase /plan  → edit_screens FIRST, approve, then implement
   developer deviation (manifest stitch_deviations[]) → ui_standards_auditor
     → drift: code fixed to match the render
     → accepted: /stitch sync-back → edit_screens (as-built prompt) → re-fetch → approve → new baseline

 gate (§10): verify-gate.sh (g) — every UI route the phase changed has an approved, current,
             hash-matching render; nothing pending_approval / sync_back_pending / drift
```

## 1. Who calls Stitch, and when it isn't there

- MCP tools are called by **the session running the command**, the parent. Subagents never call
  Stitch (`ui_standards_auditor`, `ux_designer` and `design_quality_reviewer` read files the parent
  saved). There is no `mcp_stitch_probe` bash function: probe by calling the tool.
- **Default.** Stitch is the designer whenever the `stitch` MCP server is configured. `/design` uses
  it without a flag. The text-wireframe-only path is `--source=wireframe`, used only when Stitch is
  unavailable or the owner explicitly chooses it (recorded in `docs/DECISIONS.md`).
- **Availability probe:** `get_project` on the stored `projectId`; with no project, `list_projects`.
  `list_projects` is heavy (every project's theme and every screen instance, about 83K characters for
  6 projects): never echo it; extract `name` and `title` with `jq` from the saved result.
- **Stitch unavailable** (error, timeout, missing tool):
  | Run | Behaviour |
  |---|---|
  | Interactive (`/design`, `/stitch`, `/plan`, `/hotfix`, a CR) | Stop with `NEEDS_INPUT: connect Stitch — the "stitch" MCP server is not reachable (<error>). Connect it in /mcp and re-run, or answer "wireframe" to design this change on the text-wireframe path.` Nothing is designed silently without Stitch. |
  | `/autonomous` (or `--auto`) | For each screen: `stitch-state.py defer <key> --detail "<probe error>"` → status `no_baseline` with a `deferred` record and a `queue` entry. Continue on the wireframe path. Log to `auto-resolved.jsonl` (`category: ux`). The final report lists the queue; the next run with Stitch drains it (generate → approve → compare with the built page). |
- These calls send screen descriptions (and, for imports, page text) to Google. Running a Stitch
  command, or having Stitch configured as the designer, is the owner's consent for that. Never put
  secrets, credentials or real customer PII in a prompt: imports use the seeded demo data (§3.2).
- **`delete_project` is never called by the pipeline.** Only on an explicit owner request, confirmed in the same turn.

## 2. State: `docs/design/stitch.json` (sdlc.stitch-state/v2)

Stitch IDs, approvals and render hashes have to survive across sessions, or every run creates a new
project and nobody can prove what was approved. The schema is
`~/.claude/skills/ui/stitch-state.schema.json`; **`.claude/hooks/stitch-state.py` is the only writer
and the authority** (it also enforces the cross-field rules a JSON Schema can't express). Don't edit
the file by hand: use its subcommands, then `stitch-state.py validate --check-files`.

```json
{
  "schema": "sdlc.stitch-state/v2",
  "projectId": "4044680601076201931",
  "projectTitle": "Acme — UI",
  "designSystem": { "assetId": "15996705518239280238", "source": "docs/design/DESIGN.md", "updated": "2026-10-01" },
  "bootstrap": { "method": "import", "at": "2026-10-01T09:00:00Z", "app_base_url": "http://acme.localhost",
                 "pages_total": 14, "pages_imported": 14, "low_fidelity": 1, "threshold": 0.75 },
  "screens": {
    "orders-list.desktop": {
      "screenKey": "orders-list.desktop", "screenId": "98b50e2d11", "deviceType": "DESKTOP", "app": "web",
      "route": "/orders", "title": "Orders", "origin": "imported", "status": "approved",
      "approved_by": "owner", "approved_at": "2026-10-01T10:00:00Z", "approved_rev": 2, "phase": 3,
      "render": { "dir": "docs/design/stitch/orders-list.desktop",
                  "screenshot": "docs/design/stitch/orders-list.desktop/screenshot.png",
                  "html": "docs/design/stitch/orders-list.desktop/screen.html",
                  "screenshot_sha256": "9f2c8a51e6b0c4d3a7f1e2b5c8d9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7",
                  "html_sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
                  "rev": 2, "fetched_at": "2026-10-01T09:58:00Z" },
      "wireframe": "docs/design/phases/3/specs/orders-list.wireframe.md",
      "fidelity": { "score": 0.86, "visual": 0.74, "structural": 0.94, "threshold": 0.75, "attempts": 2,
                    "method": "stitch-fidelity.py/v1 (0.4 visual[ssim64+hist] + 0.6 structural)",
                    "capture": "agent_state/stitch/import/orders/desktop/capture.json" },
      "deviations": [],
      "history": [
        { "rev": 1, "ts": "2026-10-01T09:20:00Z", "op": "import", "screenId": "5521aa", "by": "/stitch import",
          "prompt": "Recreate the Orders page exactly: header with …", "prompt_source": "import_capture", "fidelity": 0.69 },
        { "rev": 2, "ts": "2026-10-01T09:50:00Z", "op": "import_correction", "screenId": "98b50e2d11", "by": "/stitch import",
          "prompt": "Add the 'Export CSV' button left of 'New order'; the table has 4 columns …",
          "prompt_source": "import_correction", "previous_screenId": "5521aa", "fidelity": 0.86 }
      ]
    },
    "orders-list.mobile": {
      "screenKey": "orders-list.mobile", "screenId": null, "deviceType": "MOBILE", "app": "mobile",
      "route": "/orders", "status": "no_baseline", "origin": "pending",
      "deferred": { "reason": "stitch_unavailable", "at": "2026-10-01T11:00:00Z",
                    "detail": "get_project: MCP server 'stitch' not connected", "run": "autonomous" }
    }
  },
  "queue": [ { "screenKey": "orders-list.mobile", "op": "generate", "reason": "stitch_unavailable: MCP not connected",
               "ts": "2026-10-01T11:00:00Z" } ],
  "log": [ { "ts": "2026-10-01T10:00:00Z", "op": "approve", "key": "orders-list.desktop", "result": "rev 2 by owner" } ]
}
```

- **One Stitch project per product**, not per phase: design systems and screen consistency are
  project-scoped. A screen lives across phases; `phase` records the last phase that changed it.
- **`screenKey` = `<screen-slug>.<desktop|mobile|tablet>`**, filesystem-safe; the render lives in
  `docs/design/stitch/<screenKey>/`. Web and React Native versions of one screen are two keys
  (`orders-list.desktop`, `orders-list.mobile`): different designs, never one reused for the other.
- **Every screen has `route` and `app`** (only an `orphan` may lack a route). This is the all-pages
  baseline map: the gate finds a changed route's screen through it, and `/ui-audit` measures coverage.
- **Render + hash.** `stitch-state.py render <key> --screenshot <png> --html <html>` copies both
  downloads into `docs/design/stitch/<key>/` and records their sha256. Commit them (they're small,
  and `ui_developer` reads them). The gate re-hashes them: a render changed after approval blocks.
- **`approved_rev` must be the latest revision.** A newer revision (an edit, a sync-back) puts the
  screen back to `pending_approval` until it's approved.
- **`history`** records every prompt sent to Stitch with its source (`owner`, `requirement`,
  `change_request`, `design_review`, `deviation`, `import_capture`, `import_correction`, `audit`,
  `hotfix`, `recon`, `theme`) and the screen id it produced.
- Reuse the stored `projectId` (verify with `get_project`). If it's missing, `list_projects` and match
  the title before `create_project`, so a reinstall doesn't create duplicates.

**Statuses**

| status | meaning | who sets it | next step |
|---|---|---|---|
| `pending_approval` | a new revision (generate / edit / sync-back / import) is stored, not yet approved | `stitch-state.py revise` | the approval loop (§6.4) |
| `approved` | the latest revision is approved (`approved_by`: `owner` or `design_quality_reviewer`) | `stitch-state.py approve` | normalize → implement |
| `conformant` | the built page matches its approved render and the standards | `ui_standards_auditor` | none |
| `drift` | the built page deviates from an approved render without an accepted reason | `ui_standards_auditor` | code fix (`ui_developer` / `mobile_developer`) |
| `design_gap` | the approved render itself breaks a standard or the data contract | `ui_standards_auditor` | `edit_screens` → approval → re-normalize |
| `sync_back_pending` | a developer deviation was accepted; Stitch doesn't show it yet | `stitch-state.py deviation --resolution accepted` | `/stitch sync-back` |
| `no_baseline` | the page has no Stitch screen (a `deferred` record says Stitch was down) | `defer`, the auditor | generate / import |
| `import_low_fidelity` | an imported recreation scored below the threshold after 3 corrections | `/stitch import` | owner review (approve as-is, edit, or adopt a screenshot) |
| `orphan` | a Stitch screen with no route in code | `ui_standards_auditor` | report: unbuilt page or stale design |

**Migrating a v1 file** (no `schema` field, keys `<phase>/<screen>/<DEVICE>`, a separate `pages`
map): re-key each screen to `<screen>.<device>`, take `route`/`app` from its `pages` entry, set
`status` from the page status (`spec` baselines → `approved` by `owner` only if `docs/DECISIONS.md`
records the owner's approval, else `pending_approval`), fetch each render with `get_screen` into
`docs/design/stitch/<key>/`, and add one `history` entry (`op: generate`, the stored prompt). Then
`validate --check-files`.

## 3. Bootstrap: a product with no Stitch project

Run once, by `/stitch import` (default) or `/stitch adopt`. Both end with a Stitch screen for
**every** existing page, so later changes are edits of a known baseline rather than guesses.

### 3.1 Choose

| Situation | Use |
|---|---|
| The app runs (APP_BASE_URL reachable), owner wants it hands-off | `/stitch import`: recreate every page from a capture, scored |
| Owner prefers exact pixels and will upload screenshots in Stitch's web UI (Experimental Mode) | `/stitch adopt`: map the uploaded screens to routes |
| Greenfield (no pages yet) | `/stitch init` only; screens come from `/design` |

### 3.2 `/stitch import`

1. **Inventory every page.** Routes from code (Next.js `app/**/page.tsx` / `pages/**`, React Router
   config, Vue Router; Expo Router `app/**/*.tsx` minus `_layout`/`+` files for React Native), plus
   every phase's `ui_developer` / `mobile_developer` manifest. Parameterized routes need a seeded id
   (`--param id=<seeded id>`). Pages behind login need a `storageState` from a seeded demo user.
2. **Capture** with `.claude/hooks/stitch-capture.mjs` (Playwright, both viewports):
   ```bash
   # PHASE / SEEDED_ORDER_ID come from the import step; add --storage-state agent_state/stitch/auth.json for logged-in pages
   node .claude/hooks/stitch-capture.mjs --base-url "$APP_BASE_URL" --out agent_state/stitch/import \
     --manifest "agent_state/phases/${PHASE}/ui_developer/manifest.json" --routes /,/settings \
     --viewports desktop,mobile --param "id=${SEEDED_ORDER_ID}"
   ```
   Per route and viewport it writes `screenshot.png` and `capture.json`: the outline (landmarks,
   headings, buttons/links/fields with their labels, table columns, lists, images, top-level regions
   with boxes), the ARIA snapshot, the visible text, and computed design tokens (colours, fonts,
   sizes, weights, radii, spacing, shadows, counted). Across pages it writes `design-tokens.json` and
   a draft `DESIGN.md`. Use seeded demo data only: page text goes into Stitch prompts.
   React Native screens: capture from the simulator (`maestro hierarchy` + `takeScreenshot`, or the
   latest `mobile_e2e_results` screenshots) into the same layout; the capture script covers web.
3. **Design system.** Review the draft `DESIGN.md` (rename tokens, fix the primary colour), save it as
   `docs/design/DESIGN.md`, then Path B (§5): `upload_design_md` → `get_project` for the uploaded
   screen instance → `create_design_system_from_design_md` → `list_design_systems` for the asset id.
4. **Recreate each page** with `generate_screen_from_text` (`deviceType` per §4, `designSystem`) and
   a recreate prompt built from the capture, not from memory:
   ```text
   Recreate this existing page exactly as it is today (do not redesign, add or remove anything).
   Page: <title> at <route> — <app> <desktop 1280px | phone 390pt>.
   Layout regions, top to bottom (with approximate size): <regions + landmarks with boxes>.
   Headings: <h1 …, h2 …>. Buttons (left to right): <labels>. Links / nav items: <labels>.
   Form fields (label → type): <…>. Tables: <columns>, <n> rows such as: <2 sample rows from the text>.
   Visible text to keep verbatim: <the first ~40 lines of capture.text>.
   Style: the project design system; colours <top 4>, font <family>, radius <px>, spacing <scale>.
   ```
5. **Fetch and score.** `get_screen` (poll per §6.2), download `screenshot.downloadUrl` and
   `htmlCode.downloadUrl`, then
   `python3 .claude/hooks/stitch-fidelity.py score --real <capture>/screenshot.png --stitch <stitch.png>
   --capture <capture>/capture.json --html <stitch.html> --json`.
   The score is `0.4 × visual + 0.6 × structural`: visual is SSIM over a 64-px-wide grid at the best
   of ±6 rows of vertical offset plus a colour-histogram intersection; structural is the share of the
   capture's landmarks, headings, controls and table columns found in Stitch's HTML. A pixel diff
   (pixelmatch) isn't used: a faithful recreation is never pixel-aligned (Stitch renders at 2× in its
   own fonts, and one extra line shifts everything below), so a pixel diff can't tell a good
   recreation from a wrong page. The scorer returns the **missing items** by label.
6. **Correct, at most 3 times.** Below the threshold (default 0.75), `edit_screens` with a correction
   prompt naming the missing items and the visible layout differences ("add the 'Export CSV' button
   left of 'New order'; the sidebar is on the left, 220px"). Each edit returns a **new** screen id:
   `stitch-state.py revise <key> --op import_correction --screen-id <new> --prompt …`. Re-fetch and
   re-score after each.
7. **Record.** `revise` (op `import`, prompt source `import_capture`) for the first generation,
   `render` for the stored files, and the fidelity record (score, visual, structural, threshold,
   attempts, method, capture path). At or above threshold the screen is `pending_approval` and goes
   through the approval loop (§6.4). Below threshold after 3 corrections it is
   **`import_low_fidelity`** and only the owner can approve it (as-is, with another edit, or by
   switching that page to `/stitch adopt`). Under `/autonomous`, `design_quality_reviewer` approves
   imports at or above threshold; low-fidelity ones wait for the owner.
8. Write `bootstrap` (method, time, base URL, pages total / imported / low-fidelity, threshold) and the
   DECISIONS.md entry *"Stitch is the core designer (project <id>, design system assets/<id>);
   every page has a Stitch baseline."*

### 3.3 `/stitch adopt`

The owner uploads screenshots of the current pages in Stitch's web UI (Experimental Mode → import
screenshots) into the product's project. Then `/stitch adopt`:
1. `list_screens(projectId)` and save the result to a file; read only id, title and deviceType.
2. Map each screen to a route: by title convention first (`<route> <device>`, e.g. `/orders desktop`,
   or a title equal to the page title in a capture), then ask the owner for the rest (one table:
   screen title → route? / skip). Under `--auto`, only exact title matches are adopted; the rest are listed.
3. Per mapped screen: `get_screen`, store the render, `revise --op adopt` (no prompt needed),
   `approve --by owner` (the owner uploaded it). Pages with no adopted screen stay `no_baseline` and
   are offered to `/stitch import`.

### 3.4 Calibrating the threshold

The 0.75 threshold and the weights were tuned on the fixture pages in `tests/fixtures/stitch/site`
(a recreation with its own markup, font, spacing and colours scores ≈0.96 desktop / ≈0.81 mobile; a
different page with the same header ≈0.71 / ≈0.64), **not on live Stitch output**. The first live
import records every score; if good recreations score below 0.75 (or wrong ones above), change the
threshold in `bootstrap.threshold`, record why in DECISIONS.md, and re-classify.

## 4. Device type (web vs React Native)

`generate_screen_from_text`, `edit_screens` and `generate_variants` take `deviceType`
(`MOBILE | DESKTOP | TABLET | AGNOSTIC`). Always set it; never leave it unspecified.

| Target (from `agent_registry.json` tech_profile) | deviceType per screen |
|---|---|
| Web UI (`frontend.enabled`) | `DESKTOP` (the 1280px canonical layout); add a `.mobile` web key only when the screen spec has a distinct 375px layout worth rendering |
| React Native (`mobile.enabled`) | `MOBILE`; add `TABLET` only if the BRD lists tablet support |
| Both, same screen in both apps | Two keys (`<screen>.desktop` with `app: web`, `<screen>.mobile` with `app: mobile`). Different designs; don't reuse one for the other |

## 5. Design system (house style) — resolve the source, then create once

**Source, first match wins:**
1. `docs/design/DESIGN.md` (project-owned design system markdown; `/stitch import` drafts it from the capture)
2. `docs/IMPLEMENTATION_GUIDELINES.md` §Design / design tokens
3. The project design-system pack named in IMPLEMENTATION_GUIDELINES (`agent_registry.json` → `tech_profile.frontend.design_system`); never a pack that merely exists in `~/.claude/skills/ui/`
4. None → use Stitch's default; `DESIGN_INDEX.md` records "no house style"

**Path A (preferred): structured tokens.** Use this when the source gives a primary colour, fonts, roundness and mode:
1. `create_design_system` with `projectId` and `designSystem: { displayName, theme }`.
   - `theme` requires `colorMode`, `headlineFont`, `bodyFont`, `roundness` and `customColor` (hex).
   - It optionally takes `designMd` (free-form rules), override colours, `typography` and `spacing`.
   - Fonts must be one of the enum values in the schema. If the house font isn't listed, pick the
     closest one and record the substitution (`designSystem.font_substitutions`).
2. Then `update_design_system` with the returned asset `name` (`assets/<id>`), `projectId` and the
   same `designSystem`, as the tool description requires. This applies it to the project.
   - Verified: create returns `{designSystem, name: "assets/<id>", version: "1"}`.
   - Update returns a `projects/<p>/sessions/<s>` name, not the asset. Keep the asset id from create.
   - Stitch expands the theme into a full Material-style `namedColors` palette (`primary`,
     `on_surface`, `surface_container_*`, …) and picks a `labelFont` if you gave none. It bumps the
     asset `version` on first use.
3. Store `assetId` in `stitch.json`.

**Path B: a DESIGN.md file only** (not yet exercised live; inspect each response).
1. `upload_design_md` with `projectId` and `designMdBase64`. On macOS: `base64 -i docs/design/DESIGN.md | tr -d '\n'`.
2. `get_project` to find the **screen instance** the upload created: its instance `id` and `sourceScreen` (`projects/<p>/screens/<s>`).
3. `create_design_system_from_design_md` with `projectId` and `selectedScreenInstance: { id, sourceScreen }`, plus `deviceType`.
4. `list_design_systems(projectId)` to read the resulting asset id, then store it.

Pass `designSystem: "assets/<assetId>"` on **every** `generate_screen_from_text` call. To restyle
existing screens after a theme change, call `apply_design_system` with `projectId`, `assetId` and
`selectedScreenInstances` (instance ids from `get_project`).

## 6. Forward: request → approve → normalize → implement

Used by `/design` (every in-scope screen of a phase), `/stitch request` (one screen or change), and
every reverse-direction trigger in §7.

### 6.1 Build the prompt from the contract

New screen:
```text
<Screen name> — <archetype> for <persona> (<FR-ids>).
Platform: <web desktop 1280px | iOS/Android phone app (React Native)>.
Purpose: <one-sentence user story>.
Data shown (from data-contracts.md): <entity>: <field list with types>; list endpoint returns an ARRAY.
Primary actions: <buttons/gestures>. Navigation: <from → to>.
Show the POPULATED state with realistic content (no lorem ipsum).
Constraints: <house-style rules: semantic tokens, component library>, touch targets ≥44pt (mobile),
WCAG AA contrast, visible labels on every input.
```
Change to an existing screen (`edit_screens`): say what changes and what must stay, citing the
source ("FR-012 amended by CR-4: add a 'Refund' action to each paid order row; keep every other
element"). One concern per edit keeps the history readable.

### 6.2 Generate, poll, store the revision

`generate_screen_from_text` with `projectId`, `prompt`, `deviceType`, `designSystem`; or
`edit_screens` with `projectId`, `selectedScreenIds: [screenId]`, `prompt`, `deviceType`. Leave
`modelId` unset unless DECISIONS.md picks one (the enum listed `GEMINI_3_8_FLASH` and
`GEMINI_3_5_FLASH_LITE`; don't hard-code either).

**Timeouts (from the tool contract):**
- Generation can take minutes. **Do not retry** a timed-out or connection-failed call; the
  generation may still succeed.
- Poll `get_screen` (`projects/<p>/screens/<s>`) every ~30s, up to 10 times.
- If the failed call returned no screen id, `list_screens(projectId)` and take the new id that isn't
  in `stitch.json` (unverified: whether `list_screens` orders by creation time).
- After 10 polls with nothing: interactive runs report it and stop that screen; `/autonomous` defers it (§1).

Then `stitch-state.py revise <key> --op generate|edit --screen-id <id> --prompt "<prompt>" --source <s>
--phase <N>` (plus `--device --app --route` for a new key). **`edit_screens` creates a NEW screen
(verified)**: the response carries a new `id`; `revise` stores it and keeps the old one as
`previous_screenId`. Using the old id would silently pull the unfixed render.

### 6.3 Fetch the render

**Verified response shape** (`generate_screen_from_text` and `edit_screens`, 2026-09-29):
```text
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
`htmlCode.downloadUrl` is present. Both download URLs were plain HTTPS fetched with `curl -sL`
without auth. Save the payload to `agent_state/stitch/<key>/rev-<n>.json` (never echo it), download
both files, and `stitch-state.py render <key> --screenshot <png> --html <html>`.

**Stitch invents content.** From a contract listing 5 fields, the smoke test added line-item counts,
carriers, a pending-total card, search, a bottom nav and 2023 dates. Treat every render as
unverified against `data-contracts.md`: the approver checks it (§6.4), and normalization strips
anything not in the contract (§6.5). `edit_screens` fixes it cleanly when asked (verified).
Suggestions in `outputComponents` are logged; in an interactive session they're shown to the owner.

Render one state per call (populated). Loading/empty/error states are specified in the
`.wireframe.md` and drawn in the `.wireframe.html` by `ux_designer`.

### 6.4 Approve (the loop)

**Interactive runs — the owner approves every new or changed design.**
1. Show the render: print the local path `docs/design/stitch/<key>/screenshot.png` (and Read the
   image so the session can describe it), the prompt that produced it, Stitch's summary, and any
   content it invented that isn't in `data-contracts.md`.
2. Ask: **approve**, or **an edit prompt** (free text).
3. An edit prompt → `edit_screens` (§6.2) → new revision → fetch (§6.3) → back to step 1. Repeat until
   approved. The owner may also pick a variant (`generate_variants`, then `revise --op variant_pick`).
4. Approve → `stitch-state.py approve <key> --by owner`.

**`/autonomous` (and `--auto`) — `design_quality_reviewer` approves.** The parent saves the render
and the screen's contract inputs, spawns `design_quality_reviewer` in render-approval mode, and on
APPROVE runs `stitch-state.py approve <key> --by design_quality_reviewer`, which puts the screen on
the **owner-review list** (`owner_review.status: pending`). On a BLOCK, the reviewer's fix list is the
next `edit_screens` prompt (max 2 cycles; then the screen is approved with the open issues carried to
the human checkpoint, never silently). `stitch-state.py review-list` prints the list for the
checkpoint and the final report; the owner later accepts (`owner-review <key> --decision accepted`) or
requests changes (a new `/stitch request`). Low-fidelity imports are never approved autonomously.

Nothing is normalized or implemented from a render that isn't the approved latest revision.

### 6.5 Normalize the approved render into the wireframe contract

`ux_designer` does this from the saved payload, the stored render and the screen's contract inputs:
1. **`.wireframe.html`** (Stitch HTML is **not** self-contained: verified)
   - It loads `cdn.tailwindcss.com`, Google Fonts and Material Symbols, and styles through Tailwind
     classes bound to Stitch's Material colour names (`bg-surface`, `text-on-surface-variant`).
   - Produce a self-contained file with inline CSS and no CDN. Map Stitch's `namedColors` to the
     project's semantic tokens and record the mapping. Replace icon-font glyphs with inline SVG or the
     component library's icons.
   - MOBILE renders are HTML inside a 390×844 phone frame: a visual reference for React Native, not code.
   - Take layout, spacing, hierarchy and composition from the render; replace raw colours and fonts
     with the project's **semantic tokens**; map each visual element to a named component-library
     primitive (web) or RN component (mobile); add the missing states and both themes.
2. **`.wireframe.md`**
   - Header: `Stitch render: docs/design/stitch/<key>/screenshot.png (rev <n>, sha256 <first 12>)`.
   - Bindings, states, interactions, accessibility and TC-* IDs come from the data contracts and the
     test-case matrices. Stitch never decides a binding: a render field with no `data-contracts.md`
     counterpart is removed or flagged, not invented.
   - The **Data Element Inventory** ties each bound element to the render: a `Render ref` column names
     where it appears in the render (region and label, e.g. "table › 4th column 'Total'"), so the
     developer and the auditor can find it on the image.
3. **Mobile screens:** Stitch adds some `aria-label`s but **no test IDs** (verified). Add the `testID`
   for every interactive element and assertion target (`<screen>.<element>`, per
   `../testing/mobile-testing-strategy.md` §4) and use the Tier 4M TC matrix.
4. Set `wireframe` on the screen in `stitch.json` and `Source: stitch (rev <n>, approved by <who>)`
   in `DESIGN_INDEX.md`.

A render that contradicts the data contracts loses: the wireframe follows the contract, and the
difference is listed for the approver.

### 6.6 Implement against both

`ui_developer` / `mobile_developer` read the approved render (`screenshot.png`, and `screen.html` to
inspect structure, spacing and type sizes) and the wireframe pair. The render decides layout,
spacing, hierarchy and density; the wireframe decides bindings, states, testIDs and TC IDs. They build
with the project's own components and tokens and **never paste Stitch's HTML or its Tailwind
classes**. Any deliberate difference from the render (accessibility, a component constraint, real
data) is recorded in their manifest:
```json
{
  "stitch_deviations": [
    { "id": "DEV-3-001", "screen": "orders-list.desktop",
      "what": "Rows are 48px tall instead of the render's 40px",
      "why": "Row actions need 44px touch targets on tablets (WCAG 2.5.8)" }
  ]
}
```
Each screen entry in the manifest also names its `stitch_screen` key and the `stitch_rev` it was built from.

## 7. Reverse: code and requirements → Stitch

**Requirements first, then code.** Whenever a requirement change touches a screen, the change goes to
Stitch as an `edit_screens` prompt FIRST (§6.1–6.4), is approved, re-normalized, and only then
implemented:

| Trigger | Who sends it to Stitch |
|---|---|
| `product_manager` change request that changes UI | the impact report lists each affected screen key + the change; after PROCEED the parent runs `/stitch request <screen> "<change>"` per screen |
| `/plan` for a later phase that changes existing screens | `/design` for that phase: edits for changed screens, generates for new ones |
| `/recon` finds UI drift | `--fix=code`: the approved render wins, code catches up. `--fix=docs`: the as-built page wins, so a sync-back prompt goes to Stitch and is approved before the docs change |
| `/hotfix` that changes what a user sees | `/stitch request` before the fix (owner approves; `--auto`: design_quality_reviewer), unless the fix restores the approved render, which needs no Stitch change |

**Deviations from code.** `ui_standards_auditor` resolves every `stitch_deviations[]` entry
(recording it with `stitch-state.py deviation`):
- **fixed (drift):** the reason doesn't hold (an existing component can match the render, the
  accessibility issue doesn't apply). The developer changes the code to match; the screen returns
  to `conformant` after re-audit.
- **accepted:** the reason holds. The screen becomes `sync_back_pending` and a `sync_back` entry
  joins the queue.

**`/stitch sync-back`** pushes every accepted deviation: an as-built prompt ("Rows are 48px tall;
row actions are 44px icon buttons; keep everything else") → `edit_screens` → new revision
(`revise --op sync_back --source deviation`) → fetch → approval (§6.4) → `deviation --synced-rev <n>`.
The approved sync-back is the new baseline. Until then the screen is `sync_back_pending` and the phase
gate blocks, so Stitch can't silently disagree with the shipped UI.

## 8. Stitch as the design baseline for EVERY page

Every page of every app has a screen in `stitch.json`, not only the pages a phase designed.
`ui_standards_auditor` keeps the map honest each `/ui-audit` and `/develop` Wave 4.

**Page inventory**, the union of three sources (anything in only one of them is a finding):
1. **Routes in code** (web: Next.js `app/**/page.tsx` or `pages/**`, React Router config, Vue Router;
   React Native: Expo Router `app/**/*.tsx` minus `_layout`/`+` files, or the navigators' screens).
2. **Wireframes:** `docs/design/phases/*/specs/*.wireframe.md`.
3. **Stitch:** `stitch.json` screens (each with its `route` and `app`).

A page with no screen is `no_baseline`: a request for `/stitch import` (existing page) or `generate`
(spec'd page). A page whose Stitch screen was never approved is not a baseline: nothing is code-fixed
to match an unapproved render.

**Consistency across pages.** One design-system asset serves every page. After a theme change,
`apply_design_system` to **all** screen instances in the project, re-fetch each render, and put every
screen through approval again (`revise --op apply_design_system --source theme`), so every page is
re-compared. Screens with the same page archetype (list, detail, form, dashboard, settings) share
layout patterns; the auditor flags a page whose render diverges from its archetype siblings.

**Comparing built vs approved render.** Capture the built page at the render's viewport (390pt phone /
1280px desktop) with `stitch-capture.mjs`. Compare the two visually (read both images) for layout,
hierarchy, component choice and density; `stitch-fidelity.py score --real <built> --stitch <render>
--capture <capture.json> --html <screen.html>` gives a number and the missing elements, but the
finding is the specific difference, not the number. Compare tokens programmatically: computed colours
in the token set, font sizes on the type scale, spacing on the spacing scale. Report it as
"`OrdersList` uses a 13px secondary label; scale is 12/14/16 — `src/features/orders/OrderRow.tsx:41`".

## 9. Revising and exploring

| Need | Tool | Key params |
|---|---|---|
| Owner's edit prompt, or `design_quality_reviewer`'s fix list | `edit_screens` | `projectId`, `selectedScreenIds: [id]`, `prompt`, `deviceType` |
| Explore layout alternatives before approving | `generate_variants` | `selectedScreenIds`, `prompt`, `variantOptions: { variantCount: 1-5, creativeRange: REFINE\|EXPLORE\|REIMAGINE, aspects: [LAYOUT, COLOR_SCHEME, …] }` |
| Theme changed | `apply_design_system` | as in §5 (then §8: every screen re-approved) |

`edit_screens` and `generate_variants` follow the same no-retry and polling rules (§6.2). Every
result is a new revision that needs approval and re-normalization before it counts.

## 10. The phase gate (verify-gate.sh check (g))

When `docs/design/stitch.json` exists, `stitch-state.py gate --phase N` (called by `verify-gate.sh`)
blocks unless:
- the file validates (schema, cross-field rules) and **every stored render still matches its sha256**;
- every route in this phase's `ui_developer/manifest.json` and `mobile_developer/manifest.json`
  (`screens[].route`, or the explicit `stitch_screen`) has a Stitch screen whose status is `approved`
  or `conformant` at its latest revision;
- no screen anywhere is `pending_approval`, `sync_back_pending` or `drift`;
- every `stitch_deviations[]` entry in those manifests is resolved: `fixed`, or `accepted` with a
  `synced_rev`.

A `no_baseline` screen with a `deferred` (Stitch-unavailable) record passes with a WARNING, so an
`/autonomous` run without Stitch can finish; it stays queued and in the final report. Autonomous
approvals pass and are listed for the owner. Like other findings, a blocked check can be overridden
only through a user-approved `gate.forced`.

## 11. Anti-patterns

- Implementing a screen whose render isn't approved, or approved at an older revision.
- Building from the wireframe alone when an approved render exists (the layout drifts), or from the
  render alone (states, bindings and testIDs get skipped).
- Pasting Stitch's HTML or Tailwind classes into the product.
- Changing the UI in code for a requirement change before Stitch has it.
- A deliberate deviation not recorded in `stitch_deviations[]`, or an accepted one never synced back.
- Creating a new Stitch project on every run (duplicates, lost design system). Use `stitch.json`.
- Generating without `designSystem`, which gives off-brand renders.
- Retrying a timed-out generation (duplicate screens, wasted quota). Poll instead.
- Syncing the old screen id after an edit (`edit_screens` returns a new one).
- `DEVICE_TYPE_UNSPECIFIED` for a React Native screen, which renders a web layout the app can't match.
- Approving an import below the fidelity threshold autonomously, or treating the fidelity number as
  the finding.
- Calling `delete_project` to "clean up".
- Editing `stitch.json` by hand instead of through `stitch-state.py`.

## 12. What the first live run must confirm

The tooling is built on the 2026-09-29 smoke test plus the tool schemas. The first live
`/stitch import` (or `/stitch request`) must check, and record in `docs/DECISIONS.md` or here:
1. `get_screen` field names: `htmlCode.downloadUrl`, `screenshot.downloadUrl` (and that the screenshot
   is a PNG; its scale; whether it is full-page or viewport-only).
2. How long the download URLs stay valid (decides whether `refresh` is needed before an audit).
3. Whether generation is synchronous or needs polling at normal load; typical durations.
4. Whether `edit_screens` always returns a new screen id (verified once) and whether the old screen
   stays in `list_screens`.
5. `list_screens` ordering and the titles of screens uploaded through the web UI (for `adopt`).
6. Path B: the screen instance `upload_design_md` creates (where `get_project` shows it) and the
   asset `create_design_system_from_design_md` returns.
7. Real fidelity scores for good and bad recreations, to set the threshold (§3.4).

> Config blocks checked 2026-10-01 (`bash tests/archetype-compile/config-packs/run.sh --live`): JSON blocks parsed;
> the sdlc.stitch-state/v2 example validates with `stitch-state.py validate` (tests/stitch-core.test.sh).
