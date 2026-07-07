# T-005 — Reconcile a spec↔code drift (report-only, then --fix=docs)
Surface: reconciliation | Est. cost: ~6 agents | Path: /recon (bare) then /recon --fix=docs

## Setup (the seeded drift)
The TRD for the widgets phase specifies a `status` enum of `{active, archived}`. The as-built code
implements a THIRD value, `draft`, that the spec never mentions — a classic as-built-ahead-of-spec
drift. The BRD requirement **FR-012** ("widgets have a lifecycle status") is satisfied by the code
but the enum values disagree with the TRD.

## Requirement
1. **Bare `/recon`** must DETECT and REPORT the drift without changing any file: it names the extra
   `draft` value, cites the TRD line and the code line, and classifies the direction (code ahead of
   docs). Zero files modified.
2. **`/recon --fix=docs`** (as-built wins) must then update the TRD enum to include `draft` and cite
   FR-012 — docs catch up to code, code untouched.

## Definition of done
- Bare run: a drift report exists that names `draft`, cites both TRD and code locations, and marks
  the direction; `git status` shows NO source/spec file modified by the bare run.
- `--fix=docs` run: the TRD now lists `draft`; the code enum is unchanged; the report records the
  doc update and the FR-012 trace.
- The reconciliation does NOT invent requirements or silently delete the `draft` value (as-built
  wins in `--fix=docs`, it does not erase the implemented behavior).

## Why this task exists (regression class it guards)
Catches two failure modes: a bare `/recon` that mutates files (it must be read-only), and a
`--fix=docs` that "reconciles" by deleting the as-built behavior instead of updating the doc. Both
are silent correctness failures a pass/fail eval would miss.
