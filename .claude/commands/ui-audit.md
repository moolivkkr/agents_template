---
command: ui-audit
description: "Audit every page of the running web + React Native UI against the design standards and each page's Google Stitch baseline; keep Stitch holding the design for all pages. Report-only by default; --fix=design runs Stitch generate/edit for pages with no baseline or a flawed one, --fix=code sends drift to ui_developer/mobile_developer; --fix=all does both and re-audits."
arguments:
  - name: fix
    required: false
    description: "none (default: report only) | design (Stitch baselines + wireframes + design gate) | code (developers fix drift from trusted baselines) | all"
  - name: app
    required: false
    description: "web | mobile | all (default: every enabled app)"
  - name: page
    required: false
    description: "Restrict to one route (e.g. /orders). Default: every page — the point is whole-app coverage."
  - name: approve
    required: false
    description: "Comma-separated page keys whose 'reconstructed' Stitch baselines you approve; recorded in docs/DECISIONS.md so code may be fixed to match them."
---

# /ui-audit — Design standards + Stitch baseline audit for every page

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

**Why this exists.** The design gate (`design_quality_reviewer`) checks wireframes before code.
Nothing checked the **built** pages against the standards afterwards, and nothing kept Stitch
holding the design for **every** page. Pages built outside `/design`, or touched by shared-component
and theme changes, drifted unseen. `/ui-audit` closes that loop across the whole app.

Read first: `~/.claude/skills/ui/stitch-design.md` (§1 who calls Stitch, §5–§7 generate/edit/normalize,
§8 the all-pages baseline). Then `docs/PROJECT_FACTS.md` and `docs/DECISIONS.md`.

---

## Step 0 — Orient

```bash
PHASE="$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oE 'phases/[0-9]+' | grep -oE '[0-9]+' | sort -n | tail -1)"
PHASE="${PHASE:-1}"   # the audit covers the whole app; PHASE only names where reports are filed
mkdir -p "agent_state/phases/${PHASE}/reports" "agent_state/ui-audit/phase-${PHASE}"
```
- **The app must be running:** the web app for web pages (the same compose/dev command as
  `/develop` Wave 3.5); mobile binaries on a booted simulator and emulator for mobile pages. If
  it isn't running, start it, or accept a static-only audit, which the report marks explicitly.
- **Stitch:** if `docs/design/stitch.json` is missing and `--fix` includes `design`, run
  `/stitch init` first; there is no baseline to write into without it. Probe per skill §1 (never
  `list_projects` output into context).
- **`--approve`:** append a DECISIONS.md entry *"Approved reconstructed Stitch baselines: <keys>"*
  and set those pages' `baseline` to `"approved"` in `stitch.json`.

## Step 1 — Audit  (`subagent_type: ui_standards_auditor`)

```
Agent prompt (subagent_type: ui_standards_auditor): "[GROUND TRUTH line] You are ui_standards_auditor. Audit EVERY page of the running app
(app scope: ${ARG_APP:-all}${ARG_PAGE:+, page: $ARG_PAGE}) against the design standards and each
page's Stitch baseline, per your agent file and ~/.claude/skills/ui/stitch-design.md §8.
Write reports/ui_standards_audit.md + .json and reports/ui_standards_stitch_requests.json under
agent_state/phases/${PHASE}/. Do not call Stitch."
```
Without `--fix`, stop here. Print the page coverage matrix summary, the count line, and the number
of Stitch requests waiting, then suggest the next `--fix` step.

## Step 2 — Design fixes in Stitch  (`--fix=design|all`)

The **parent** executes `ui_standards_stitch_requests.json`, following the skill exactly:
- `generate`: `generate_screen_from_text` with the request's `prompt`, `deviceType` and `designSystem`. Don't retry; poll `get_screen`.
- `edit`: `edit_screens` on `screenId`. **It returns a new screen id:** store it, and keep the old one as `previous`.
- `apply_design_system`: `apply_design_system` with `assetId` and the listed instances, then mark every affected page `stale`.
- `refresh`: `get_screen` to renew the download URLs.

After each request, update `stitch.json` (`screens` plus `pages[key]` with `screenKey`, `baseline`
type and status `pending_sync`) and append a log entry. Run at most 3 generations in flight. A
failed request is reported for that page, and the others continue.

Then normalize (skill §7): spawn `ux_designer` once over the new or changed renders, to write or
update each page's wireframe pair (mobile pages get testIDs and Tier 4M TCs). Run the design gate
exactly as `/design` Step 3 does (`design_quality_reviewer`, max 2 cycles; a visual BLOCK goes back
to `edit_screens`). Only pages whose wireframe passes the gate move to `baseline` = `spec` /
`reconstructed` in `stitch.json`.

## Step 3 — Code fixes  (`--fix=code|all`)

For every `drift` finding whose baseline is `spec` or `approved`:
- web pages → `ui_developer` (`subagent_type: ui_developer`);
- React Native pages → `mobile_developer` (`subagent_type: mobile_developer`).

Each developer gets its findings (page, `file:line`, fix) plus the page's wireframe pair. Findings
against **`reconstructed`** baselines are **not** code-fixed: list them with
`▶ approve with /ui-audit --approve=<keys>`. Then run `test_runner` for the affected Node tiers,
so a visual fix can't silently break behaviour.

## Step 4 — Re-audit and report

Re-spawn `ui_standards_auditor` scoped to the pages that changed in Steps 2–3. Repeat at most 2
rounds while BLOCKING findings remain. Then report:

```
UI audit — <app scope> — N pages
  Stitch baseline coverage: before NN% → after NN%
  conformant N · drift N · design_gap N · no_baseline N · orphan N
  Stitch: N generated · N edited · N theme-applied   Code fixes: N files
  Awaiting approval (reconstructed baselines): <keys>
  BLOCKING:N WARNING:N INFO:N   → agent_state/phases/N/reports/ui_standards_audit.md
```

## Definition of Done
- [ ] The audit covered every page in the inventory (or the single `--page`), and anything not rendered is marked SKIPPED with the reason.
- [ ] Every Stitch mutation is recorded in `stitch.json` (the new id after each edit), and none is left only in the conversation.
- [ ] No page's code was changed to match an unapproved `reconstructed` baseline.
- [ ] Wireframes created or changed from Stitch passed the design gate before becoming a baseline.
- [ ] Coverage is reported before and after; failures are reported per page, never summarized away.
