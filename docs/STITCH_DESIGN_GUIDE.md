# Stitch Design Guide — Google Stitch as the core designer (`/stitch`, `/design`, `/ui-audit`)

Google Stitch is where this framework designs UI. Every new or changed screen, web (`DESKTOP`) and
React Native (`MOBILE`), is designed in Stitch first: a prompt goes to Stitch, the render comes back,
someone approves it, and only then is it built. Changes flow both ways. A requirement change reaches
Stitch before it reaches code, and a justified change made in code is synced back to Stitch, so
Stitch never silently disagrees with the shipped UI. The phase gate checks all of this.

Developers build against two things for every screen:
- **the approved render** (`docs/design/stitch/<key>/screenshot.png` + `screen.html`), the visual target;
- **the wireframe pair** normalized from it (`<screen>.wireframe.html` + `.wireframe.md`), the
  contract for bindings, states, testIDs and TC IDs.

They rebuild the render with the project's own components and tokens and never paste Stitch's HTML.

Source of truth for every call sequence and rule: `.claude/skills/ui/stitch-design.md`.

---

## 1. Prerequisites and consent

- The Google Stitch MCP server connected to Claude Code as `stitch` (check with `/mcp`). When it's
  configured, Stitch is the default designer: `/design` needs no flag.
- Stitch calls send screen descriptions (and, for `import`, page text from seeded demo data) to
  Google's service. Configuring Stitch as the designer, or running a Stitch command, is the consent.
  Never put secrets or real customer data in a prompt.
- MCP tools are called by the session running the command (the parent), never by a subagent.
- The pipeline never calls `delete_project`.

**When Stitch is unreachable:**

| Run | What happens |
|---|---|
| Interactive (`/design`, `/stitch`, a CR, `/hotfix`) | Stops with `NEEDS_INPUT: connect Stitch …`. You can answer "wireframe" to design that change on the text-wireframe path (`--source=wireframe`), which is recorded. |
| `/autonomous` | Each screen is recorded as `no_baseline` with a `deferred` record and queued; the run continues on the wireframe path. The gate shows a WARNING, the final report lists the queue, and the next run with Stitch drains it. |

## 2. Bootstrapping an existing app (once)

A product with pages but no Stitch project gets a Stitch baseline for **every** page first.

**`/startup:stitch import`** (hands-off). The MCP can't upload a screenshot, so each page is
recreated from a description and scored:
1. `stitch-capture.mjs` (Playwright) captures every route at desktop and mobile size: screenshot, an
   outline (landmarks, headings, buttons, links, fields with labels, table columns, regions), the ARIA
   snapshot, visible text and computed design tokens. It also drafts a `DESIGN.md` from the tokens.
2. You review `DESIGN.md`; it becomes the Stitch design system (`upload_design_md` →
   `create_design_system_from_design_md`).
3. Each page is generated from a "recreate this page exactly" prompt built from its capture.
4. `stitch-fidelity.py` scores the result against the real page: 0.4 × visual (SSIM on a 64-px grid
   with a small vertical-shift search, plus a colour histogram) + 0.6 × structural (the share of the
   real page's landmarks, headings, controls and columns found in Stitch's HTML). Below the threshold
   (default 0.75), the missing items go back to Stitch as a correction, at most 3 times.
5. Each page's fidelity is recorded. Pages still below threshold are `import_low_fidelity` and wait
   for you: approve as-is, give an edit, or switch that page to `adopt`.

Why not a pixel diff? A recreation is never pixel-aligned (Stitch renders at 2× in its own fonts, and
one extra line shifts everything below it), so a pixel diff can't tell a faithful recreation from a
different page. The 0.75 threshold was tuned on fixture pages, not live Stitch output; the first real
import records every score so it can be calibrated.

**`/startup:stitch adopt`** (exact pixels). You upload screenshots of your pages in Stitch's web app
(Experimental Mode), then `adopt` lists the project's screens and maps them to routes, by title
(`/orders desktop`) or by asking you.

## 3. Designing — `/startup:design` and `/startup:stitch request`

`/design --phase=N` (run by `/plan` for UI phases) sends every screen the phase adds or changes to
Stitch: `generate_screen_from_text` for new screens, `edit_screens` for changed ones (naming the FR).
`/stitch request <screen> "<change or new-screen prompt>"` does the same for one screen at any time:
an idea, a change request, a recon finding, a hotfix.

**Approval.**
- **Interactive:** you approve every new or changed design. You see the local screenshot path, the
  prompt, Stitch's summary and anything it invented that the API doesn't return. Answer `approve`, or
  type an edit prompt; it loops through `edit_screens` until you approve.
- **`/autonomous`:** `design_quality_reviewer` approves each render (or blocks it with a fix list that
  goes back to Stitch). Every autonomously approved screen is on your review list
  (`stitch-state.py review-list`), shown at the human checkpoint and in the final report. Low-fidelity
  imports are never approved autonomously.

After approval, `ux_designer` normalizes the render into the wireframe pair (semantic tokens, the
project's components, bindings from `data-contracts.md`, all four states, testIDs, and a `Render ref`
per data element), then the design gate (`design_quality_reviewer`, 11 dimensions) runs.

`/develop` won't start UI implementation (Wave 2A.5 / 2A.6) until every screen the phase touches has an
approved render at its latest revision (`stitch-state.py ready --phase N`).

## 4. Code → Stitch: deviations and sync-back

When a developer can't or shouldn't match the render (accessibility, a component constraint, real
data), they build the better thing and record it in their manifest:
`stitch_deviations: [{ id: "DEV-3-001", screen: "orders-list.desktop", what, why }]`.

`ui_standards_auditor` judges each one in `/develop` Wave 4:
- **fixed:** the reason doesn't hold; the code is changed to match the render (drift);
- **accepted:** the reason holds; the screen becomes `sync_back_pending`, and `/stitch sync-back` sends
  an as-built prompt to Stitch, you (or `design_quality_reviewer` under `/autonomous`) approve the new
  render, and it becomes the baseline.

An unrecorded difference between the page and its render is drift.

## 5. State — `docs/design/stitch.json`

One file holds the project, the design system, and one entry per screen (`<slug>.<desktop|mobile>`):
its Stitch screen id, device, app, route, status, who approved which revision and when, the render's
paths and sha256 hashes, the fidelity record for imports, recorded deviations, and the full history of
prompts sent to Stitch. Schema: `.claude/skills/ui/stitch-state.schema.json`. Only
`.claude/hooks/stitch-state.py` writes it (`revise`, `render`, `label`, `approve`, `owner-review`, `defer`,
`deviation`, `status-set`) and checks it (`validate --check-files`, `ready`, `gate`, `review-list`,
`versions`, `diff`). Commit it and `docs/design/stitch/`.

### Versions: keep "as it was" next to "as improved"

Each revision can carry a version label, and each version keeps its own render on disk:
`docs/design/stitch/<key>/v0.1/screenshot.png|screen.html`, `.../v0.2/...` (the latest is also copied to
`docs/design/stitch/<key>/` so the old paths keep working). Convention:

- **`v0.1` = the as-is baseline.** `/stitch import` and `/stitch adopt` record the existing design as
  `v0.1`; for a new screen, the first generation is `v0.1`.
- **`v0.2`, `v0.3` ... = improvements** before approval, one label per reviewable result. When one
  improvement takes several small Stitch edits, only the last is labelled; the rest are `rev-N`.
- **`v1.0` = approved:** `stitch-state.py approve <key> --by owner --promote` relabels the approved
  revision `v1.0` (or the next major).
- Labels are `v<major>.<minor>`, unique per screen and increasing in revision order; the tool refuses
  anything else.

```
python3 .claude/hooks/stitch-state.py versions orders-list.desktop          # table (add --json)
python3 .claude/hooks/stitch-state.py diff orders-list.desktop v0.1 v0.2    # screenIds, prompts between, hashes, % pixels
```

The gate also re-hashes every archived version, so editing an older render blocks it. A `stitch.json`
from before versions keeps working; its next revision becomes `v0.1`.

| Status | Meaning |
|---|---|
| `pending_approval` | a new revision waits for approval |
| `approved` | the latest revision is approved (by `owner` or `design_quality_reviewer`) |
| `conformant` | the built page matches its approved render |
| `drift` | the built page differs from its render without an accepted reason |
| `design_gap` | the approved render itself breaks a standard |
| `sync_back_pending` | an accepted code deviation hasn't reached Stitch yet |
| `no_baseline` | no Stitch screen (with a `deferred` record when Stitch was down) |
| `import_low_fidelity` | an import below the fidelity threshold, waiting for you |
| `orphan` | a Stitch screen with no route in code |

## 6. The gate

`verify-gate.sh` check (g), when `docs/design/stitch.json` exists: every UI route in the phase's
`ui_developer` / `mobile_developer` manifests has a Stitch screen that is approved or conformant at its
latest revision, whose stored render still matches its hash; nothing is `pending_approval`,
`sync_back_pending` or `drift`; every recorded deviation is fixed, or accepted and synced back. A
screen deferred because Stitch was down passes with a WARNING.

## 7. Auditing built pages — `/startup:ui-audit`

`ui_standards_auditor` checks the **built** pages across the whole app, in `/develop` Wave 4 whenever
web UI or mobile screens changed, and on demand through `/ui-audit`.

**Page inventory** = routes in code (Next.js / React Router / Vue Router; Expo Router or registered
navigators for React Native) ∪ wireframes ∪ Stitch screens. Anything in only one source is a finding.
The app must be running; otherwise the audit is marked static-only.

**Checks** (S1–S10): tokens only, type scale, spacing scale, four states, library primitives reused,
no overflow at 375px / safe areas, archetype consistency, only contract fields, the page matches its
approved render, and every recorded deviation resolved. WCAG and native-platform issues are left to
`accessibility_auditor` and `mobile_platform_auditor`. The auditor never calls Stitch; it writes
`ui_standards_stitch_requests.json` (`generate`, `edit`, `import`, `sync_back`, `apply_design_system`,
`refresh`) and the parent executes them through the approval loop.

```
/startup:ui-audit                        # report only: coverage matrix, findings, pending Stitch requests
/startup:ui-audit --fix=design           # parent runs the Stitch requests → approval → ux_designer → design gate
/startup:ui-audit --fix=code             # drift against approved renders → developers → test_runner
/startup:ui-audit --fix=all              # both, then re-audit changed pages (max 2 rounds)
/startup:ui-audit --approve=settings.desktop,orders-list.mobile
                                         # approve pending renders / accept autonomous approvals
/startup:ui-audit --app=mobile --page=/orders
```

## 8. Command reference

```
/startup:stitch init                     # project + house-style design system (greenfield)
/startup:stitch import [--route=/a,/b]   # bootstrap every existing page: capture → recreate → score → approve
/startup:stitch adopt                    # map screenshots you uploaded in Stitch's web UI to routes
/startup:stitch request orders-list.desktop "Add a Refund action to paid rows (FR-012, CR-4)"
/startup:stitch request refunds.desktop "Refund list for finance admins …" --route=/refunds
/startup:stitch sync-back                # push accepted code deviations to Stitch, approve, re-baseline
/startup:stitch generate|variants|edit|theme|sync --phase=N
/startup:stitch status                   # offline: statuses, coverage, owner-review list, queue
python3 .claude/hooks/stitch-state.py versions|diff|label ...   # version history (see Versions in section 5)
/startup:design --phase=N                # Stitch designs the phase (default); --source=wireframe without it
```

## 9. What was verified, and what wasn't

**Verified against the real Stitch API (2026-10-01)** — observed in one live session:
`generate_screen_from_text` / `edit_screens` return the screen inline when done (download URLs, `width` /
`height` at 2×, `screenMetadata.status: COMPLETE`); a large single-shot dashboard prompt timed out twice and
produced no screen while a small prompt on `GEMINI_3_5_FLASH_LITE` returned at once, so build a screen as
one small generate plus small single-concern edits; the lighter model can leave "[Line Chart: …]"
placeholders where `GEMINI_3_8_FLASH` renders charts (scan the HTML after each edit); `edit_screens` returns
a new id and the old screen stays; `screenshot.downloadUrl` is a 512 px thumbnail unless `=w2560` is appended;
Stitch rewrites prompts and invents content (say "do not add content not listed", and use an as-is design
system for recreations); `create_design_system` expands `designMd`, `update_design_system` needs the full
object; `list_screens` returns `{}` until a screen completes. **Still unverified:** download URL lifetime,
polling timing for slow generations, `generate_variants`, `apply_design_system`.

Verified against the connected Stitch MCP on 2026-09-29 (one scratch project, one MOBILE screen): the
tool list, project creation, design system Path A, `generate_screen_from_text` → `get_screen` → HTML
download, and `edit_screens` returning a new screen id. **Not exercised live yet:** Path B
(`upload_design_md`), `generate_variants`, `apply_design_system`, `list_screens` ordering and the
titles of screens uploaded in the web UI, the polling path, how long download URLs stay valid, the
screenshot's format and scale, and real fidelity scores. `stitch-design.md` §12 lists what the first
live import must confirm.

Verified offline (`tests/stitch-core.test.sh`): `stitch-capture.mjs` against local fixture pages in a
real browser, the fidelity scorer on known images and pages, the `stitch.json` validator on good and
bad fixtures, and the gate's PASS and BLOCK cases. `tests/dependency-graph.test.sh` fails if any
command, agent or skill names a Stitch tool outside the verified list.
