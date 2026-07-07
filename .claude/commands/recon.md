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

**Non-destructive by default.** Bare `/recon` and both `--fix` modes without `--apply` change
nothing — they only report/propose. Doc edits and code catch-up land only under `--apply`.

## Aliases (kept for muscle memory)
- `/converge` ≡ `/recon --fix=code` (spec-wins catch-up).
- `/reconcile` ≡ `/recon --fix=docs` (as-built doc update; also carries the estate `--all`/`--product`
  fan-out, which `/recon` passes through).

Both still work and hold the detailed procedures; `/recon` is the canonical, self-documenting front
door.
