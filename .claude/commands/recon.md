---
command: recon
description: "Reconcile requirements↔BRD↔TRD↔code↔tests, in BOTH directions. Default reports drift and changes nothing; --fix=code makes code match the spec (spec wins); --fix=docs makes docs match the code (as-built wins)."
arguments:
  - name: fix
    required: false
    description: "Resolution mode: omit = report-only audit (change nothing); code = specs/BRD win → generate code+test catch-up; docs = code wins → update BRD/TRD to as-built."
  - name: phase
    required: false
    description: "Limit to one phase. Omit to assess the whole project."
  - name: plane
    required: false
    description: "Restrict to one reconciliation link: req-brd | brd-trd | trd-impl | trd-test. Omit to run all four."
  - name: apply
    required: false
    default: false
    description: "For --fix modes: actually write the changes (code catch-up into /develop, or doc edits). Without it, --fix modes are propose-only."
  - name: product
    required: false
    description: "Reconcile a single named product (estate layout). Omit to use the current repo."
  - name: all
    required: false
    default: false
    description: "Fan out across the whole estate and write a roll-up (requires the multi-agent workflow engine)."
  - name: since
    required: false
    description: "Only reconcile capabilities touched since a git ref (e.g. --since=HEAD~50)."
---

# /recon — Two-Way Reconciliation (the single entry point)

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

> **Read Tier 0 first.** Load `docs/PROJECT_FACTS.md` (ground truth) and `docs/DECISIONS.md` before
> assessing. A retired/renamed fact means a spec item that references it is *retired*, not *missing* —
> do not raise it as drift or generate catch-up work for it.

`/recon` is the one command for checking that **code matches the requirements (BRD → TRD → code →
tests) and that the code traces back to a requirement** — in **both directions**. Every underlying
reconciler agent already detects drift both ways; the **`--fix` flag only decides who wins when you
resolve it**, i.e. *what changes*.

## The `--fix` axis — pick by what changes

| Invocation | Who wins | What it does | Use when |
|---|---|---|---|
| **`/recon`** (no `--fix`) | nobody | **Report only** — lists every MISSING (spec'd, not built/tested) and every EXTRA (built, not spec'd), both directions. Changes nothing. | You want an honest drift audit before deciding. **Safe default.** |
| **`/recon --fix=code`** | **spec / BRD** | Generates a code+test **catch-up task list** (feedable into `/develop` with `--apply`). Code ← Spec. | "The code is behind what we agreed to build." (= `/converge`) |
| **`/recon --fix=docs`** | **code (as-built)** | Rewrites BRD/TRD/requirements to match the implemented reality (writes only with `--apply`). Docs ← Code. | "The docs are stale; the implementation is right." (= `/reconcile`) |

**Rule of thumb:** *code is incomplete* → `--fix=code`. *docs are wrong* → `--fix=docs`. *not sure
yet* → run bare `/recon` and read the report first.

## The four planes (both directions are checked in every mode)

`/recon` runs all four reconciliation links (restrict with `--plane`). Each is bidirectional —
forward = "requirement/spec has an implementation?", backward = "code/test traces to a requirement?":

| Plane | Link | Agent | Forward (MISSING) | Backward (EXTRA) |
|---|---|---|---|---|
| `req-brd`  | requirements ↔ BRD | `requirements_brd_reconciler` | requirement dropped from BRD | BRD item with no source |
| `brd-trd`  | BRD ↔ TRD/spec | `brd_spec_reconciler` | FR-* with no spec | spec behavior with no BRD parent |
| `trd-impl` | TRD/spec ↔ code | `spec_impl_reconciler` | spec'd behavior not built | code with no spec (gold-plating) |
| `trd-test` | TRD/spec ↔ tests | `spec_test_reconciler` | spec'd behavior untested | test with no spec |

The full-chain capstone (`pipeline_completeness_agent`, run by `/accept`) closes the loop end-to-end:
every requirement traces forward to code+tests+acceptance, and every code artifact traces back to a
requirement.

## How it runs

1. **Discover + normalize** the target (current repo, `--product`, or `--all` estate fan-out).
2. **Detect (all modes):** run the reconciler agents for the selected planes in report-only mode and
   assemble a two-way drift report (`agent_state/reconciliation/recon-report.md`): MISSING list,
   EXTRA list, per-plane counts.
3. **Resolve (only if `--fix` given):**
   - `--fix=code` → run the **spec-wins catch-up**: emit the delta task list; with `--apply`, feed it
     straight into `/develop`. (Implementation: see [`/converge`](converge.md).)
   - `--fix=docs` → run the **as-built doc update**: propose BRD/TRD/requirement edits; with `--apply`,
     write and commit them per repo. (Implementation: see [`/reconcile`](reconcile.md).)
4. **Report:** always write the drift report; `--fix` modes append what they changed (or proposed).
5. **Acceptance tests follow the requirements (all modes).** Every requirement change recon finds
   has an acceptance consequence: a test to add, update or retire. Recon owns those, not the next
   gate. See [Acceptance changes](#acceptance-changes) below.

## Acceptance changes

Acceptance tests are the executable form of the BRD: one TC-ACC row per EARS SHALL per persona, in the
owning phase's spec, and one committed test per row under `tests/acceptance/`. When recon changes what
the BRD says, those rows and tests change with it.

| Recon finding | Requirement change | Acceptance change |
|---|---|---|
| UNSPEC (built, not in the docs) → FR backfilled, `Source: as-built` | new FR | **add** TC-ACC rows (in the phase whose code implements it) + tests |
| DRIFT-DOC (built differently from the docs) → FR text updated | changed FR | **update** its rows (keep IDs whose SHALL survives, add new ones) + tests; rows for a removed SHALL are deleted only if the working phase owns them |
| New SHALL on an existing FR | changed FR | **add** the missing rows + tests |
| INVENTED, human ruled "drop" → FR removed / marked Won't | removed FR | **retire** its rows and **delete** their tests, **only those the working phase owns**; the rest are listed for a decision |
| Test code whose TC-ACC ID no spec row defines | — (left behind) | **delete** the test **if its ID is from the working phase's block**; else listed for a decision |
| GAP-IMPL (documented, not built; `--fix=code`) | none | **add** rows if the FR has none; the tests come with the `/develop` catch-up |

**Removal is limited to the working phase.** A phase may remove only acceptance rows and tests it
owns: rows in its own spec, test IDs from its own block (TC-ACC-P····), or rows/tests for an FR its
own PHASE_PLAN names (e.g. "Retires FR-010"). Every other candidate (another phase's row for a dropped
FR, another phase's stale test, a legacy-numbered test with no provable owner) lands in
`delta.retire_needs_decision`. It is **left in place**, listed in the report for the owning phase's
work or a human, and blocks nothing. Adding and updating rows or tests is allowed in any phase.

`acceptance-map.py` computes the list from the BRD, every phase's spec rows and the test code:
```bash
# The working phase: the phase in progress (base_sha, no gate.passed), else --phase. If both exist and
# differ, there is none, and removals are reported only.
INPROG=$(for d in agent_state/phases/*/; do [ -f "$d/base_sha" ] && [ ! -f "$d/gate.passed" ] && basename "$d"; done | sort -n | tail -1)
WP="${INPROG:-${ARG_PHASE:-}}"; [ -n "$INPROG" ] && [ -n "${ARG_PHASE:-}" ] && [ "$INPROG" != "$ARG_PHASE" ] && WP=""
PRE_SHA=$(git rev-parse HEAD)
python3 .claude/hooks/acceptance-map.py ${WP:+--working-phase $WP} --out agent_state/reconciliation/acceptance_map.json || true
jq '.delta' agent_state/reconciliation/acceptance_map.json   # add / update / retire_rows / retire_tests / retire_needs_decision
```

**Bare `/recon` (report only):** the drift report gets an `## Acceptance changes` table: the map's
`delta`, plus the changes the doc findings imply once applied (each DRIFT-DOC FR → update, each UNSPEC
→ add, each INVENTED → retire if the human drops it), with each removal marked as either the working
phase's or needing a decision. Nothing is written.

**`--fix=docs --apply`:** after the BRD/TRD edits (`/reconcile` Step 4), apply the acceptance changes
(`/reconcile` Step 4b):
1. `spec_writer` (`MODE: acceptance-amend`, `WORKING_PHASE: $WP`) with the map's add, update and
   `retire_rows` lines (never the `retire_needs_decision` ones): writes or rewrites TC-ACC rows in the
   owning phase's spec and deletes only the working phase's retired rows, with an `## Amendments` line each.
2. `acceptance_test_agent` (`MODE: amend-tests`, `WORKING_PHASE: $WP`) with the same list plus the
   `retire_tests` lines: writes the tests for new rows, updates the tests for changed rows, deletes
   only the listed tests. It writes the test code and doesn't need a deployed build. Running the tests
   is the next gate's or `/accept`'s job.
3. Re-run the map with the guard:
   `acceptance-map.py ${WP:+--working-phase $WP} --diff-base $PRE_SHA`. Done when `add`,
   `retire_rows`, `retire_tests` and `removed_outside_phase` are empty and every `update` entry has
   `rows_amended: true`. Anything in `removed_outside_phase` was deleted outside the working phase:
   restore it before committing. The CHANGED status itself clears when the next green gate or
   `/accept` records the new baseline.
4. Commit the rows and tests with the doc edits:
   `docs(recon): … — acceptance: +N rows, ~N updated, -N retired`.

**`--fix=code --apply`:** the specs win, so the requirements don't change. Recon adds rows for any FR
that has none, and retires the working phase's own rows and tests for FRs the BRD no longer has, both
through steps 1–3 above.
The tests for the catch-up work are written by `/develop`'s acceptance agent when it builds the gap.

## UI drift and Google Stitch (projects with `docs/design/stitch.json`)

Stitch is the core designer (`~/.claude/skills/ui/stitch-design.md` §7), so the design plane is part
of every recon: each screen's approved Stitch render ↔ its wireframe ↔ the built page.
`ui_standards_auditor` (as in `/ui-audit`, report-only) lists each built page that differs from its
approved render, plus pages with no Stitch screen.
- **Bare `/recon`:** the drift report gets a `## Design (Stitch)` table: page, screen key, what
  differs, and which way it would resolve. Nothing is sent to Stitch.
- **`--fix=code`** (spec wins): the approved render is the spec. Each drifted page becomes a catch-up
  task for `ui_developer` / `mobile_developer`, built against the render. A requirement change found
  here that alters a screen goes to Stitch FIRST (`/stitch request <key> "<change, citing the FR>"`,
  approval loop), and the catch-up task is built from the newly approved render.
- **`--fix=docs`** (as-built wins): for each page whose as-built UI is right, Stitch is updated before
  the docs: record the difference as an accepted deviation (`stitch-state.py deviation … --resolution
  accepted`), then `/stitch sync-back` (as-built `edit_screens` prompt → re-fetch → approval →
  `--synced-rev`). Only then are the wireframe and the BRD/TRD rewritten. Stitch never ends a recon
  disagreeing with the shipped UI.
- Stitch unreachable: interactive → `NEEDS_INPUT` "connect Stitch"; `--auto` → each Stitch step is
  queued (`stitch-state.py defer` / the sync-back queue) and listed in the report.

## Where each path starts

| Situation | Start with |
|---|---|
| Code exists, no BRD/specs at all | `/init --from-code` → `/plan --phase=1 --as-built` → `/develop --phase=1` (builds the spec + acceptance baseline) |
| BRD/specs exist; code moved on without them | `/recon --fix=docs --apply` (docs and acceptance tests follow the code) |
| BRD/specs exist; code is behind them | `/recon --fix=code --apply` → `/develop` |
| A requirement changes on purpose | `product_manager` change request → the gate / `/accept` update its acceptance tests |

**Non-destructive by default.** Bare `/recon` and both `--fix` modes without `--apply` change
nothing — they only report/propose. Doc edits and code catch-up land only under `--apply`.

## Aliases (kept for muscle memory)
- `/converge` ≡ `/recon --fix=code` (spec-wins catch-up).
- `/reconcile` ≡ `/recon --fix=docs` (as-built doc update; also carries the estate `--all`/`--product`
  fan-out, which `/recon` passes through).

Both still work and hold the detailed procedures; `/recon` is the canonical, self-documenting front
door.
