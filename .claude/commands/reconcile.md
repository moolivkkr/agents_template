---
command: reconcile
description: Full-chain requirements↔BRD↔TRD↔implementation reconciliation with an as-built-wins doc-update mode and a per-product completion action plan. Runs on one repo or fans out across the whole Vertix estate.
arguments:
  - name: product
    required: false
    description: "Reconcile a single named product (e.g. --product=cert-manager). Resolves under ~/development/vertix/<name> then ~/development/<name>. Omit to use the current repo."
  - name: all
    required: false
    default: false
    description: "Fan out across the whole estate (12 products + 3 base SDKs) in parallel and write an estate roll-up. Requires the multi-agent workflow engine."
  - name: apply
    required: false
    default: false
    description: "Write doc updates (DRIFT-DOC + UNSPEC backfill) to requirement/BRD/TRD files and commit per repo. Without it, the command is propose-only: it emits patch proposals but changes nothing."
  - name: plane
    required: false
    description: "Restrict to one reconciliation plane: req-brd | brd-trd | trd-impl | trd-test. Omit to run all four."
  - name: since
    required: false
    description: "Only reconcile capabilities touched since a git ref (e.g. --since=HEAD~50), for incremental re-runs."
---

# /reconcile — Full-Chain Docs↔Code Reconciliation + Completion Planning

> **Alias of `/recon --fix=docs`** (as-built-wins). `/recon` is the canonical two-way entry point;
> this command remains as a direct alias and carries the full-chain, estate `--all`/`--product`
> fan-out and the detailed as-built doc-update procedure below.

Reconciles what a product **claims** (requirements → BRD → TRD) against what it **is** (the
implemented code + tests), in both directions, then does three things the four existing
reconciler agents do *not*:

1. **As-built-wins doc update** — when the code intentionally diverges from the docs
   (architecture you improvised), it rewrites the docs to match the code (with `--apply`).
2. **Documented-never-built capture** — rolls forward-gaps into a prioritized completion
   backlog per product.
3. **Estate fan-out** — sweeps all products and produces a cross-product roll-up.

This command **reuses** the existing reconciler agents where a product follows the startup
pipeline layout, and falls back to inline equivalents where it does not. It never assumes a
uniform layout — every product is discovered and normalized first.

---

## Modes

| Invocation | Scope |
|---|---|
| `/reconcile` | current repo (cwd) |
| `/reconcile --product=cert-manager` | one named product |
| `/reconcile --all` | whole estate, parallel, + roll-up |
| add `--apply` | write doc updates + commit per repo (default: propose-only) |
| add `--plane=trd-impl` | run only one plane |
| add `--since=HEAD~50` | only capabilities touched since a ref |

**Default is propose-only and non-destructive.** Reports and patch proposals are always
written; docs are edited only under `--apply`.

---

## Canonical product registry (for `--all`)

Resolve each unit's repo root by trying `~/development/vertix/<path>` first, then
`~/development/<name>`. Skip any that don't exist and note it.

```
# name              path (under vertix/)        kind
cert-manager        cert-manager                product
zero-trust          zero-trust                  product
entitlements        entitlements                product
secrets-manager     secrets-manager             product
dlp                 dlp                          product
control-plane       control-plane               product
portal              portal                       product   # includes modules/*
dspm                dspm_engine                  product
kspm                kspm_engine                  product
cspm                cspm_engine                  product
threatmatrix        threatmatrix                 product
base-agent          base/base-agent              sdk
base-detector-sdk   base/detector-sdk            sdk
base-responder-sdk  base/responder-sdk           sdk
```

> `portal` modules live under `portal/` (and possibly `portal/modules/*` or per-product
> plugin dirs) — treat each portal module as a sub-unit of the portal report, not a
> separate product.

---

## Rule-pack products (dspm, cspm, kspm, edr, siem, nspm, certificates)

These products are **cross-repo**: their detection content (rules, facts, research,
compliance) is authored in **composer** while their runtime is in `<product>_engine`. For
them, reconciliation is not single-repo — resolve ownership via the **rule-pack manifest**
and add the fact-contract plane. See `vertix/RULEPACK-FEDERATION-DESIGN.md`.

**Source resolution (manifest-driven, with fallback):**
1. If `<product>_engine/rulepack.yaml` exists → use its `content`/`fact_contract`/`spec`
   paths as the authoritative sources (rules, facts, research, BRD — wherever they point).
2. Else fall back to discovery: rules = `composer/policies/<slug>/` (per composer's
   `pluginOwnedDirs` map in `pkg/server/manifest_handler.go`), facts =
   `composer/policies/<slug>/facts/posture_facts.json`, research =
   `composer/research/<slug>/`, BRD = `<product>_engine/docs/BRD.md`.
3. A **missing** rulepack.yaml, BRD, or research index is itself a COMPLETION action item.

The product's requirements = **BRD (engine) + rule catalog + fact contract + compliance
mappings + research parity (composer)**. A rule authored in composer is a *requirement* the
engine must be able to evaluate.

---

## Step 0 — Discover & normalize (per product)

Never assume `docs/BRD.md` + `docs/design/phases/`. Discover, in priority order, and record
what exists in a normalized recon manifest. Missing artifacts are findings, not errors.

```bash
ROOT="$1"   # repo root
# --- BRD (may be multiple / root-level / absent) ---
BRD=$(ls "$ROOT"/docs/BRD.md "$ROOT"/BRD.md "$ROOT"/brd*.md "$ROOT"/*BRD*.md 2>/dev/null)
# --- Requirements (recursive; may be absent) ---
REQ=$(find "$ROOT/requirements" -name '*.md' 2>/dev/null)
# --- TRDs / specs (phases layout OR flat design docs OR absent) ---
TRD=$(ls "$ROOT"/docs/design/phases/*/specs/*.md 2>/dev/null || ls "$ROOT"/docs/design/*.md 2>/dev/null)
PHASE_PLANS=$(ls "$ROOT"/docs/design/phases/*/PHASE_PLAN.md 2>/dev/null)
# --- Code roots & tests (language-agnostic) ---
#   Go: **/*.go (exclude _test.go), tests: *_test.go
#   Python: **/*.py, tests: test_*.py / *_test.py / tests/
#   TS/React (portal): src/**/*.ts(x), tests: *.test.ts(x) / *.spec.ts(x) / e2e/
# --- Prior recon / trackers to update ---
TRACKERS=$(ls "$ROOT"/TRACKER.md "$ROOT"/PRODUCT_STATUS.md "$ROOT"/agent_state/reconciliation/* 2>/dev/null)
```

Write `agent_state/reconciliation/00-recon-manifest.md` capturing: which artifacts were
found, which are **absent** (absent BRD / absent requirements / absent TRD are themselves
COMPLETION action items), the code roots, the test roots, and the detected stack.

**Graceful degradation matrix:**

| Missing | What the plane does instead |
|---|---|
| requirements/ | Skip req↔BRD; note "no source requirements — BRD is unsourced" as a warning, not a gap |
| BRD | Synthesize a **capability inventory from code** as the reconciliation baseline; #1 action item = "author BRD from as-built" |
| TRD/specs | Reconcile BRD↔impl directly; #1 action item = "backfill TRDs for as-built architecture" |
| tests | trd-test plane reports 0% coverage as a completion gap |
| agent_state/ | create it (`mkdir -p agent_state/reconciliation`) |

---

## Step 1 — Build the as-built capability inventory (code = ground truth)

Spawn a **codebase_mapper** (or backend_audit_agent for pipeline-layout repos) focused on
*capabilities*, not files. For each capability, record the four-level implementation state
— this is the same rigor spec_impl_reconciler uses:

- **Level 1 Exists** — symbol/file present
- **Level 2 Real** — has real logic (not `TODO`/`panic("not implemented")`/`return nil`/`throw "TODO"`/`NotImplementedError`)
- **Level 3 Wired** — imported and called from a live path (handler → service → store)
- **Level 4 Flows** — data actually flows end-to-end (route reachable, persisted, returned)

Output `agent_state/reconciliation/10-capability-inventory.md`:

| Capability | Where | L1 | L2 | L3 | L4 | Notes |
|---|---|:--:|:--:|:--:|:--:|---|

A capability at L1/L2 only is a **stub** — it counts as *not implemented* for GAP
classification, regardless of what the docs say.

---

## Step 2 — Run the four reconciliation planes

For each plane, prefer the existing agent when the repo has the matching layout; otherwise
run the inline equivalent against the normalized artifacts from Step 0. Planes are
independent — run them in parallel (or restrict with `--plane`).

| Plane | Agent (if layout fits) | Inline fallback | Direction |
|---|---|---|---|
| **req-brd** | `requirements_brd_reconciler` | compare requirements/*.md ↔ BRD sections | requirements ↔ BRD |
| **brd-trd** | `brd_spec_reconciler` (per phase) | BRD FR/NFR ↔ design docs | BRD ↔ TRD |
| **trd-impl** | `spec_impl_reconciler` (per phase) | TRD/BRD capability ↔ inventory (Step 1) | specs ↔ code |
| **trd-test** | `spec_test_reconciler` (per phase) | TRD behavior ↔ test inventory | specs ↔ tests |
| **rules-facts-engine** *(rule-pack products only)* | — | see below | composer rules ↔ fact contract ↔ engine |

**rules-facts-engine plane** (dspm/cspm/kspm/edr/siem/nspm/certs) — the cross-repo check the
single-repo chain misses:
1. **Rule → fact:** every `field_path`/`value_type`/`op` referenced by a rule in
   `policies/<slug>/*.json` must exist (compatible type + allowed op) in the fact contract
   (`posture_facts.json` or `<engine>/contracts/*.contract.json`). A rule referencing an
   unproduced fact = **detection dead-spot** → **GAP-IMPL**.
2. **Fact → producer:** every produced fact must be emitted by an engine symbol (grep the
   scanner/crawler). A contract fact with no producer = broken contract → GAP-IMPL.
3. **Coverage:** facts no rule consumes (dead facts → UNSPEC/cleanup); rule families with no
   engine support (→ GAP-IMPL). Report the rules-count vs facts-count delta explicitly
   (e.g. cspm 460 rules / 379-line fact registry).
Writes `planes/rules_facts_engine.md`.

Each plane writes its raw findings under `agent_state/reconciliation/planes/`. Do **not**
let planes edit docs — they only produce findings. Classification (Step 3) decides edits.

---

## Step 3 — Classify every discrepancy (the core judgment)

Fold all plane findings + the capability inventory into a single classified ledger. Every
discrepancy lands in exactly one bucket:

| Bucket | Definition | Default action |
|---|---|---|
| **DRIFT-DOC** | Capability **is implemented (L3+)** but the docs describe it differently — different tech, shape, flow, or naming. The code is the intended reality. | **Update docs to match code** (with `--apply`) |
| **UNSPEC** | Capability **is implemented (L3+)** but **absent from the docs** entirely. | **Backfill doc** for it (with `--apply`) |
| **GAP-IMPL** | Capability is **documented** (BRD/TRD/requirements) but **not implemented** (absent, or stub at L1/L2). | **Completion backlog item** — never silently deleted from docs |
| **INVENTED** | Capability is in the **BRD/TRD** but traces to **no source requirement** *and* is **not implemented**. | Flag for human decision (drop from docs, or promote to a real requirement) |

**Judgment rules (be strict, be honest):**
- A **stub is not an implementation.** L1/L2-only → GAP-IMPL, even if a handler exists.
- Code wins on **architecture/structure/tech choices** (how it's built) → DRIFT-DOC.
- Docs win on **intended capability** (what it must do) → a missing capability is a GAP,
  never "resolved" by editing the doc to stop asking for it.
- Distinguish **intentional improvisation** (DRIFT-DOC — code is coherent and wired) from a
  **bug/regression** (flag separately under `## Suspected regressions`, do not touch docs).
- When unsure whether drift is intentional, **do not auto-edit** — list it under
  `## Needs human ruling` even in `--apply` mode.

---

## Step 4 — Apply doc updates (only with `--apply`)

For **DRIFT-DOC** and **UNSPEC** items only:

1. Edit the specific requirement/BRD/TRD file to match as-built. Preserve the doc's own
   ID scheme (FR-*/NFR-*/section numbering) and voice. For UNSPEC, add a new FR-*/section.
2. Keep edits **surgical** — change the drifted statement, don't rewrite whole documents.
3. Leave a dated reconciliation note in each edited doc's changelog/amendment section if it
   has one (many products have `docs/*-AMENDMENT-*.md` — append there when present).
4. **GAP-IMPL and INVENTED are never applied** — they go to the action plan / human ruling.
5. Commit per repo:
   `docs(reconcile): align <product> docs with as-built architecture (N DRIFT, M UNSPEC)`
   with the Co-Authored-By trailer. Branch first if on the default branch.

Without `--apply`: write `agent_state/reconciliation/30-doc-patches.md` containing the exact
proposed edit for each DRIFT-DOC/UNSPEC item (file → old → new), ready to review.

---

## Step 5 — Per-product outputs

Write two documents per product:

### `agent_state/reconciliation/RECONCILIATION_REPORT.md`
```markdown
# <product> — Reconciliation Report (<date>)
## Summary
| Plane | Status | Forward gaps | Reverse gaps |
|-------|--------|-------------|--------------|
| req↔BRD | PASS/GAPS/DEVIATIONS | n | n |
| BRD↔TRD | ... | | |
| TRD↔impl | ... | | |
| TRD↔test | ... | | |
| Classified | DRIFT n · UNSPEC n · GAP-IMPL n · INVENTED n | | |

## DRIFT-DOC (docs updated to match code) — [applied | proposed]
## UNSPEC (implemented, doc backfilled) — [applied | proposed]
## GAP-IMPL (documented, not built) → see action plan
## INVENTED / Needs human ruling
## Suspected regressions (bugs, not drift)
```

### `agent_state/reconciliation/COMPLETION_ACTION_PLAN.md`
The point of the whole exercise — the ordered steps to reach **capability completion**:
```markdown
# <product> — Completion Action Plan (<date>)
## Capability completeness: X% (implemented L3+ / total documented capabilities)
## P0 — blocks core capability (documented, not built; or stub on hot path)
| # | Capability | State | Evidence | Action | Effort |
## P1 — completes the capability surface
## P2 — polish / coverage / hardening
## Doc debt (missing BRD/TRD/requirements to author)
## Decisions needed (INVENTED items, ambiguous drift)
```

If the repo has a `TRACKER.md` / `PRODUCT_STATUS.md`, update its row for this product with
the new completeness % and a link to the action plan (with `--apply`); otherwise note the
proposed row change in the report.

---

## Step 6 — Estate roll-up (`--all` only)

`--all` fans out one full Step 0–5 pipeline **per unit in the registry, in parallel**, then
aggregates. This is the multi-agent case — drive it with the **Workflow** engine (one
pipeline item per product; `trd-impl` is the slow stage, so pipeline rather than barrier).
Confirm the fan-out with the user before launching if they have not already opted in.

Write `~/development/vertix/RECONCILIATION_ROLLUP.md`:
```markdown
# Vertix Estate Reconciliation Roll-up (<date>)
## Per-product scorecard
| Product | Completeness % | DRIFT | UNSPEC | GAP-IMPL | INVENTED | Doc debt | Top action |
## Cross-cutting gaps (appear in ≥3 products)
  # e.g. "entitlements integration documented, not imported anywhere" (from PRODUCT_STATUS blocker #1)
## Estate-level completion sequence
  # ordered so shared-substrate gaps that unblock multiple products come first
## Links to each product's RECONCILIATION_REPORT + COMPLETION_ACTION_PLAN
```

Cross-check findings against the estate's existing `PRODUCT_STATUS.md` and `TRACKER.md` —
where the roll-up disagrees with a claimed %, surface the delta explicitly (those docs are
also subject to DRIFT-DOC: if code is further along or behind than they claim, update them
under `--apply`).

---

## Guardrails

- **Never delete a documented capability to make a report green.** A capability the code
  doesn't have is a GAP, full stop.
- **As-built wins only for how, never for whether.** Improvised architecture updates the
  doc; a missing feature does not.
- **Propose-only by default.** Doc edits and commits happen only under `--apply`.
- **Honesty over tidiness** (per global rules): if a claimed-shipped capability is actually
  a stub, say so plainly with the file:line evidence. Do not soften.
- **Stubs, mocks, TODOs, and unwired handlers count as not-implemented** at every plane.
- Verify a symbol/flag/file still exists before citing it — inventories can go stale.

## When to run
- After a burst of architectural improvisation, to realign docs and surface the backlog.
- Before a planning cycle, to seed `/plan` with the real remaining scope.
- Periodically across the estate (`--all`) to keep PRODUCT_STATUS/TRACKER honest.
