---
command: stitch
description: "Google Stitch, the core designer: set up the product's Stitch project and house style, bootstrap it from the existing app (import every page, or adopt screenshots uploaded in Stitch), request new screens or changes through the owner-approval loop, sync accepted code deviations back, and normalize approved renders into the wireframe contract — web (DESKTOP) and React Native (MOBILE)."
arguments:
  - name: action
    required: true
    description: "init | import | adopt | request | sync-back | generate | variants | edit | theme | sync | status"
  - name: screen
    required: false
    description: "Screen key (<slug>.<desktop|mobile|tablet>, e.g. orders-list.desktop) or wireframe base name. request: the screen to create or change. Omit on generate/sync to process every in-scope screen."
  - name: prompt
    required: false
    description: "request: the new-screen description or the change, in plain words. edit / variants: the change or direction. For edit after a design-gate BLOCK, omit it to use the reviewer's fix list."
  - name: route
    required: false
    description: "request (new screen): the route it will live at (e.g. /invoices). import: restrict to these routes (comma-separated)."
  - name: phase
    required: false
    description: "Phase the work belongs to (generate / variants / edit / sync / request). Default: current phase."
  - name: device
    required: false
    description: "DESKTOP | MOBILE | TABLET. Default: from tech profile — MOBILE for React Native screens, DESKTOP for web (stitch-design.md §4)."
  - name: count
    required: false
    description: "variants: number of variants 1-5 (default 3)."
  - name: range
    required: false
    description: "variants: REFINE | EXPLORE | REIMAGINE (default EXPLORE)."
  - name: threshold
    required: false
    description: "import: fidelity threshold 0-1 (default 0.75; stitch-design.md §3.4)."
  - name: auto
    required: false
    default: false
    description: "No owner prompts: design_quality_reviewer approves and every approval joins the owner-review list (set automatically under /autonomous)."
---

# /stitch — Google Stitch, the core designer

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

Stitch is where every new or changed screen is designed: a prompt goes to Stitch, the render comes
back, it's approved, and only then is it implemented. `/design` drives this for a whole phase;
`/stitch` is the direct workbench: bootstrap a product, request one screen or change, push accepted
code deviations back, explore, restyle, and report.

**Every call sequence, parameter rule and timeout rule is in `~/.claude/skills/ui/stitch-design.md`.
Read it first.** This command orders those steps and records the results through
`.claude/hooks/stitch-state.py` (never by editing `docs/design/stitch.json` by hand).

**Ground truth:** read `docs/PROJECT_FACTS.md` and `docs/DECISIONS.md` first. A screen that
references anything RETIRED is not generated.

**Outbound calls:** every action except `status` calls Google's Stitch service with screen
descriptions (and, for `import`, page text from seeded demo data). Running `/stitch` is the owner's
request to do so. The only thing never done without explicit confirmation is `delete_project`, and
this command has no delete action.

**Auto mode** (`--auto`, or `agent_state/autonomous/run.json` has `"status":"running"`): no owner
prompts. `design_quality_reviewer` approves (stitch-design.md §6.4), every such approval joins the
owner-review list, and a Stitch outage defers the screen instead of stopping (§1).

---

## Step 0 — Probe and load state (every action)

1. Probe (an MCP call, not a shell function): `mcp__stitch__get_project` on the stored `projectId`,
   else `mcp__stitch__list_projects` (read only name and title from the saved result with `jq`; it's
   large).
   - **Unavailable** (error, timeout, missing tool):
     - interactive: stop with
       `NEEDS_INPUT: connect Stitch — the "stitch" MCP server is not reachable (<error>). Connect it in /mcp and re-run.`
       (`status` still works offline);
     - `--auto`: for `request`/`generate`, run `stitch-state.py defer <key> --detail "<error>"` per
       screen, log `{"category":"ux","reason":"stitch unavailable"}` to
       `agent_state/autonomous/auto-resolved.jsonl`, and return. Nothing else runs without Stitch.
2. `python3 .claude/hooks/stitch-state.py validate` (if `docs/design/stitch.json` exists). A v1 file
   (no `schema`) is migrated first per stitch-design.md §2. If there is no stored project and the
   action isn't `init`, `import` or `adopt`, stop with `▶ Run /stitch init (new product) or /stitch import (existing app) first`.
3. Resolve the platform from `agent_state/agent_registry.json` (`frontend.enabled`, `mobile.enabled`)
   and set the default `--device`.
4. **Drain the queue** (interactive and auto alike, once Stitch is reachable): list `queue[]` entries
   (screens deferred while Stitch was down, pending sync-backs) and offer to process them first.

## The approval loop (used by import, adopt, request, sync-back, generate, edit, variants)

For each new revision (stitch-design.md §6.2–6.4):
1. `stitch-state.py revise <key> --op <op> --screen-id <new id> --prompt "<prompt>" --source <source> --phase <N>`
   (plus `--device --app --route` for a new key). `edit_screens` returns a **new** screen id: always
   the one from the response. **Version label** (stitch-design.md §2.1): `revise` labels the revision
   with the next minor automatically (`v0.1` for the first). When several small `edit_screens` calls make
   up ONE reviewable change, pass `--no-version` on every edit except the last (those archive as
   `rev-<n>`), or `--no-version` on all of them and run `stitch-state.py label <key>` once the result is
   final; `stitch-state.py versions <key>` shows the unlabelled edits collapsed under the label they
   lead to.
2. Fetch: `mcp__stitch__get_screen`, save the payload to `agent_state/stitch/<key>/rev-<n>.json`,
   download `screenshot.downloadUrl` and `htmlCode.downloadUrl` (`curl -sL`), then
   `stitch-state.py render <key> --screenshot <png> --html <html>` (archives it under
   `docs/design/stitch/<key>/<version or rev-n>/` and copies it to `docs/design/stitch/<key>/`). Use
   `${screenshot.downloadUrl}=w2560` for the full-size screenshot (the bare URL is a 512 px thumbnail).
   **Placeholder check (every edit, before showing the render):** scan the downloaded HTML for
   `\[[^]]*Chart`, `[Donut`, `placeholder` and `lorem`. If a chart or block was left as a text
   placeholder, re-edit that one concern with `modelId: GEMINI_3_8_FLASH` (the lighter
   `GEMINI_3_5_FLASH_LITE` sometimes leaves them) as a new `--no-version` revision, then fetch again.
   Build a screen with one small generate and several small single-concern edits, never one 40-line
   prompt (stitch-design.md §6.7).
3. **Interactive — the owner approves.** Print the local path
   `docs/design/stitch/<key>/screenshot.png`, Read the image and describe it in two lines, show the
   prompt, Stitch's summary, and any content not in `data-contracts.md`. Ask:
   `Approve <key> rev <n>?  [approve] or type an edit prompt`.
   An edit prompt → `mcp__stitch__edit_screens` (`selectedScreenIds: [screenId]`, same `deviceType`;
   poll, never retry) → back to step 1 with `--op edit --source owner`. Loop until approved.
   Approve → `stitch-state.py approve <key> --by owner` (add `--promote` when the owner is releasing
   it: the approved revision becomes `v1.0`, or the next major if `v1.0` is taken).
4. **Auto — design_quality_reviewer approves.** Spawn `design_quality_reviewer`
   (`subagent_type: design_quality_reviewer`) in render-approval mode:
   ```
   [GROUND TRUTH line] You are design_quality_reviewer in RENDER-APPROVAL mode (autonomous run).
   Approve or block Stitch render docs/design/stitch/<key>/screenshot.png (rev <n>; HTML screen.html)
   against: the prompt (agent_state/stitch/<key>/rev-<n>.json), data-contracts.md, the house style
   (docs/design/DESIGN.md or the named design system), professional-ui-standards.md and the screen's
   archetype. First line: APPROVE or BLOCK, then a numbered fix list usable verbatim as an edit_screens prompt.
   ```
   APPROVE → `stitch-state.py approve <key> --by design_quality_reviewer` (joins the owner-review
   list). BLOCK → the fix list is the next `edit_screens` prompt (`--source design_review`); max 2
   cycles, then approve with the open issues written to `auto-resolved.jsonl` for the checkpoint.
   A low-fidelity import is never approved here: it waits for the owner.
5. After approval the screen is normalized (`sync`) before anyone implements it.

## init — project + design system (new product)

1. Reuse the stored `projectId` (verify with `get_project`), or find a project titled
   `"<PROJECT_NAME> — UI"` in `list_projects`, or `mcp__stitch__create_project` with that title.
2. Resolve the design-system source (stitch-design.md §5). Create it with Path A
   (`create_design_system`, then `update_design_system`) or Path B (`upload_design_md`, then
   `get_project` for the uploaded screen instance, then `create_design_system_from_design_md` with
   `selectedScreenInstance`, then `list_design_systems`). Store `designSystem.assetId`.
3. Write `stitch.json` (`schema: sdlc.stitch-state/v2`, `bootstrap.method: greenfield` when there are
   no pages yet). Print the project id, the design-system source and asset id, and any font substitutions.
4. Unless present, append to `docs/DECISIONS.md`: *"Stitch is the core designer (project <id>, design
   system assets/<id>): every new or changed screen is designed and approved in Stitch before it is
   implemented; every page has a Stitch baseline."* If the app already has pages, continue with `import`.

## import — bootstrap from the running app (every page)

Follow stitch-design.md §3.2 exactly. The MCP can't upload images, so each page is recreated from a
capture and scored. **The recreation is the as-is baseline: it is recorded as `v0.1`.** Its generation and
corrections use `--no-version`; when the final recreation is accepted or scored, run
`stitch-state.py label <key> --version v0.1`. Say "do not add content not listed" in the prompt and apply
an as-is design system ("recreate faithfully; do not improve"), stitch-design.md §6.7. The next change
becomes `v0.2` (`stitch-state.py versions <key>` / `diff <key> v0.1 v0.2` compare them).
1. **Inventory every page** (routes in code + every phase's UI manifests; `--route` restricts it).
   The app must be running at `APP_BASE_URL` with seeded demo data; parameterized routes get seeded
   ids; logged-in pages get a seeded user's `storageState`.
2. **Capture** both viewports:
   ```bash
   node .claude/hooks/stitch-capture.mjs --base-url "$APP_BASE_URL" --out agent_state/stitch/import \
     --routes "$ROUTES" --viewports desktop,mobile
   ```
   (Playwright from the project; `STITCH_PLAYWRIGHT_DIR` points elsewhere if needed.) React Native
   screens: capture from the simulator into the same layout (§3.2 step 2).
3. **Design system:** review `agent_state/stitch/import/DESIGN.md`, save it as
   `docs/design/DESIGN.md`, then `init` (Path B) if no design system exists yet.
4. **Per page and device** (up to 3 generations in flight): `mcp__stitch__generate_screen_from_text`
   with the recreate prompt built from that page's `capture.json` (§3.2 step 4), `deviceType`,
   `designSystem`. Record with `revise --op import --source import_capture`, fetch + `render`.
5. **Score:** `python3 .claude/hooks/stitch-fidelity.py score --real <capture>/screenshot.png --stitch <render png> --capture <capture.json> --html <render html> --threshold ${ARG_THRESHOLD:-0.75} --json`.
   Below threshold: `mcp__stitch__edit_screens` with a correction prompt naming the scorer's
   `missing` items and the visible layout differences, `revise --op import_correction`, re-fetch,
   re-score. **At most 3 corrections.**
6. **Record fidelity** on the screen (score, visual, structural, threshold, attempts, method, capture)
   and set the status: at/above threshold → `pending_approval` → the approval loop; still below after
   3 corrections → `import_low_fidelity` (owner review: approve as-is, edit, or `adopt` that page).
7. Write `bootstrap` (method `import`, time, base URL, totals, threshold) and the DECISIONS.md entry
   from `init` step 4. Report:
   ```
   Stitch import — N pages × devices
     approved N (owner N · design_quality_reviewer N) · pending owner review N · low fidelity N
     fidelity: median 0.NN, min 0.NN (<key>) — scores recorded for threshold calibration (§3.4)
     failed N (reason per page)
   ```

## adopt — map screens the owner uploaded in Stitch's web UI

stitch-design.md §3.3. The owner uploads screenshots into the product's Stitch project (web app →
Experimental Mode → import screenshot); the MCP can't do that step.
1. `mcp__stitch__list_screens(projectId)` → save to a file; read id, title, deviceType only.
2. Match each screen to a route by title convention (`<route> <device>`, e.g. `/orders desktop`, or
   the page's title); show one table of the rest and ask the owner for each (route / skip). `--auto`:
   exact matches only; the rest are listed.
3. Per mapped screen: `get_screen`, `revise --op adopt --version v0.1` (the adopted screen is the as-is
   baseline), store the render, `approve --by owner` (the owner supplied the image). Pages left without a screen stay `no_baseline` and are offered to `import`.

## request — a new screen or a change, through Stitch first

`/stitch request <screen> "<change or new-screen prompt>" [--route /path] [--device …]`. This is the
entry point every UI change uses: owner ideas, change requests (`product_manager`), `/recon`,
`/hotfix`, a later phase's `/design`.
1. Existing key → **change**: build the edit prompt (what changes, what must stay, the source, e.g.
   "FR-012 amended by CR-4", stitch-design.md §6.1) → `mcp__stitch__edit_screens`.
   Unknown key → **new screen**: build the generate prompt from the contract (§6.1; `--route`
   required) → `mcp__stitch__generate_screen_from_text` with `deviceType` and `designSystem`.
2. The approval loop above (source `owner`, `change_request`, `recon`, `hotfix` or `requirement`). A
   change to an imported/adopted screen keeps its `v0.1` baseline render on disk; the finished
   improvement is labelled the next minor (`v0.2`), the intermediate edits stay unlabelled. A screen with
   no recorded baseline (neither imported nor adopted): record its current Stitch screen first
   (`revise --op adopt --version v0.1`, `render`), then make the change.
3. **Normalize** the approved render: `sync --screen=<key>` (below).
4. **Hand-off:** print what the implementer gets:
   ```
   ✅ <key> rev <n> approved by <who> — ready to implement
     render:    docs/design/stitch/<key>/screenshot.png (+ screen.html)   sha256 <12>
     wireframe: docs/design/phases/<N>/specs/<screen>.wireframe.{html,md}
     ▶ /develop --phase=<N> (ui_developer / mobile_developer build against both), or /hotfix …
   ```

## sync-back — push accepted code deviations to Stitch

For every screen with status `sync_back_pending` (accepted `stitch_deviations[]`, stitch-design.md §7):
1. Build one as-built prompt per screen from its accepted, unsynced deviations ("As built: rows are
   48px tall; row actions are 44px icon buttons. Keep everything else unchanged.") and, where useful,
   a capture of the built page (`stitch-capture.mjs`).
2. `mcp__stitch__edit_screens` → `revise --op sync_back --source deviation` (labelled with the next
   minor automatically) → fetch + `render`.
3. The approval loop (the owner confirms the render now shows what shipped).
4. `stitch-state.py deviation <key> --id <DEV-…> --phase <N> --synced-rev <n>` for each deviation, then
   `sync --screen=<key>` to refresh the wireframe. The screen is `approved` again and the queue entry
   is gone; the gate stops blocking on it.

## generate — render every in-scope screen of a phase

For each in-scope screen (from `docs/design/phases/N/specs/archetype-mapping.md`, or `--screen`):
build the prompt from the archetype, the `data-contracts.md` fields, the FR-* acceptance criteria and
the platform (stitch-design.md §6.1); `mcp__stitch__generate_screen_from_text` with `projectId`,
`prompt`, `deviceType` and `designSystem: "assets/<assetId>"` (don't retry on timeout; poll
`get_screen` 30s × 10); then the approval loop. Up to 3 generations in flight; report each screen as
`approved | pending approval | deferred | failed (reason)`.

## variants — explore alternatives

`mcp__stitch__generate_variants` on the stored screen id with `prompt`, `deviceType` and
`variantOptions: { variantCount: --count, creativeRange: --range, aspects }`. Show every variant's
screenshot path; the owner picks one (`revise --op variant_pick --screen-id <chosen>`), which then goes
through the approval loop. Nothing is normalized until a variant is approved.

## edit — revise a screen

`mcp__stitch__edit_screens` on the stored screen id. The prompt is `--prompt`, or, when omitted and
the phase's `DESIGN_REVIEW.md` BLOCKed this screen, the reviewer's fix list for it verbatim. Same
polling rules, then the approval loop (`--source design_review` or `owner`), then `sync`.

## theme — change the house style

Update the design system (`update_design_system` with the stored asset, or recreate it via Path A/B
if the source changed). Then `apply_design_system` to every stored screen instance (instance ids from
`get_project`), re-fetch every render, and `revise --op apply_design_system --source theme` each one:
every screen goes back through approval and `sync`, so `/ui-audit` re-compares every page.

## sync — normalize approved renders into the phase's wireframe contract

1. Only screens whose **latest revision is approved** are synced (others: `▶ approve first`).
2. Spawn `ux_designer` (`subagent_type: ux_designer`) once for the batch:
   ```
   [GROUND TRUTH line] You are ux_designer normalizing APPROVED Google Stitch renders for Phase N.
   Follow ~/.claude/skills/ui/stitch-design.md §6.5 exactly. Inputs per screen: the approved render
   docs/design/stitch/<key>/screenshot.png + screen.html, its payload agent_state/stitch/<key>/rev-<n>.json,
   docs/design/phases/N/specs/data-contracts.md, archetype-mapping.md, existing wireframes.
   Write/update <screen>.wireframe.html + <screen>.wireframe.md for each screen: render path + rev + sha
   in the header, semantic tokens only, bindings only from data-contracts.md, all 4 states, a Render ref
   column in the Data Element Inventory, mobile screens with testIDs + Tier 4M TC IDs.
   ```
3. Run the design gate exactly as `/design` Step 3 does (`design_quality_reviewer`, then
   `DESIGN_REVIEW.md`). A visual BLOCK goes back to Stitch as an edit (the approval loop again);
   binding/state/contract BLOCKs are fixed in the wireframe. Max 2 cycles, as in `/design`.
4. Record `wireframe` on each screen (stitch.json) and `Source: stitch (rev <n>, approved by <who>)`
   in `DESIGN_INDEX.md`.

## status — no outbound calls

`python3 .claude/hooks/stitch-state.py validate --check-files`, then print from `stitch.json`:
project, design system and source, bootstrap summary, and per screen its key, route, device, status,
approved rev / by / at, render sha (first 12) and wireframe. Then:
- counts per status (`approved | conformant | drift | design_gap | no_baseline | import_low_fidelity |
  pending_approval | sync_back_pending | orphan`) and coverage % (screens with an approved render ÷ pages);
- the **owner-review list** (`stitch-state.py review-list`): autonomous approvals and low-fidelity imports;
- the **queue**: deferred screens (Stitch was down) and pending sync-backs;
- wireframes with no Stitch screen, and approved renders never synced into a wireframe.
The audit-derived statuses are as fresh as the last `/ui-audit`; its date is shown.
For a screen's version history: `stitch-state.py versions <key>` (`--json`), and
`stitch-state.py diff <key> v0.1 v0.2` for what changed between two versions.

---

## Definition of Done
- [ ] Every Stitch mutation is recorded through `stitch-state.py` (new screen id after every edit, prompt and source in `history`), and `stitch-state.py validate --check-files` passes.
- [ ] Every revision that is a reviewable result carries a version label (`v0.1` as-is baseline for imported/adopted screens, then `v0.2`, ...), intermediate edits of one change are unlabelled, and each labelled version has its archived render (`stitch-state.py versions <key>`).
- [ ] After every generate/edit the downloaded HTML was scanned for chart/placeholder text and re-edited when found.
- [ ] Every render that will be implemented is approved at its latest revision: by the owner (interactive) or by `design_quality_reviewer` with the screen on the owner-review list (auto).
- [ ] Every generate/edit/variants call set `deviceType` (and `designSystem` for generation), and no timed-out call was retried.
- [ ] `import` covered every page in the inventory and recorded a fidelity score per page; pages below threshold are `import_low_fidelity`, never approved autonomously.
- [ ] `sync-back` left no `sync_back_pending` screen whose sync-back the owner approved.
- [ ] `sync` left the wireframe pair as the contract, pointing at the approved render, and the design gate ran on the synced screens.
- [ ] Failures, deferrals and pending approvals are reported per screen, never summarized as success.
