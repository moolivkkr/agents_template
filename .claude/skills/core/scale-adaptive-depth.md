# Scale-Adaptive Workflow Depth Protocol

> **Read Tier 0 first.** Before applying this protocol, load `docs/PROJECT_FACTS.md` (ground-truth
> invariants) and honor any retired/renamed facts. A fact that retires a component removes it from
> the "components in scope" count below.

The pipeline currently runs the **same wave depth for every task** — a one-line copy fix goes through
the same 1-6 wave machinery as a new platform subsystem. Complexity today only feeds `model-routing.md`
(which model to use). It does **not** scale the *workflow* itself.

This protocol adds a **complexity classifier** consulted by `/plan` and `/develop` that maps a task to
a **workflow depth**, so trivial work skips ceremony and platform work gets extra rigor. It is the
workflow-depth complement to `model-routing.md`'s model-depth decision.

---

## When to Use

| Command | Where | What it decides |
|---|---|---|
| `/plan --phase=N` | Before spec generation | Whether a full TRD is needed or a light spec / no spec |
| `/develop --phase=N` | Before Wave 1 | Which waves run (and whether extra ADR/architecture waves are added) |
| `/hotfix`, `/diagnose --fix` | Scope check | Confirms the fast-track class (usually TRIVIAL/SMALL) is appropriate |

This is **advisory scaffolding, not a bypass**. It never skips the phase gate's TC-* inventory check
or the security review for any class above TRIVIAL. It reduces *ceremony*, not *correctness*.

---

## The Classifier

Score the task on four signals, then take the **highest** class any signal reaches (the task is only
as simple as its heaviest dimension).

| Signal | Trivial | Small | Standard | Platform |
|---|---|---|---|---|
| **#components in scope** | 0 (copy/config only) | 1 | 2-4 | 5+ or a new component |
| **Shared layer touched?** (auth, middleware, DB schema, config, shared/common/utils) | No | No | Maybe (leaf usage) | Yes (definition changed) |
| **New vs brownfield** | Edit existing line | Edit existing behavior | New feature in existing area | New subsystem / greenfield area |
| **#FR-\* in phase scope** | 0 (no FR — cosmetic) | 1 | 2-5 | 6+ |

**Rule:** any single Platform-column hit → PLATFORM. Any Standard hit (and no Platform) → STANDARD.
Shared-layer **definition** change is always at least STANDARD, and if it changes a contract other
components depend on, it is PLATFORM. Schema/migration changes are never below STANDARD.

---

## Depth Map

| Class | Spec depth | Waves that run | Extra rigor |
|---|---|---|---|
| **TRIVIAL** | None (skip TRD). Record intent as a one-line note in the phase manifest. | Skip full waves. Scoped **implement + scoped test** only (touch-only tests + lint). | Reviewer runs style/security on the diff only. |
| **SMALL** | Light spec — a short bullet TRD, no wireframe unless UI. TC-* enumerated only for the changed surface. | **Waves 2, 3, 6** (implement → test → gate). Skip Wave 1 audit and Wave 4 acceptance unless a persona-facing FR is touched. | Change-impact test selection (`change-impact-analysis.md`). |
| **STANDARD** | Full spec per `/plan` (TRD + UI spec + data contracts + full TC-* matrices). | **Full Waves 1-6.** | Normal review + tenant-isolation + full per-phase regression. |
| **PLATFORM** | Full spec **plus an ADR** (architecture decision record) in `docs/adr/`. Component inventory updated. | Full Waves 1-6 **plus a pre-Wave-1 architecture wave** (software-architecture.md review) and a post-gate `/map` refresh. | Full regression (no change-impact shortcut), security review mandatory, ADR reviewed by architecture reviewer. |

**Never downgrade below the gate.** TRIVIAL is the only class that skips the wave gate, and it is
restricted to **zero-FR, zero-shared-layer** changes (typos, copy, doc, config-value tweaks). If a
"trivial" change breaks a test, it is reclassified SMALL and re-run with waves.

---

## Decision Record

`/plan` and `/develop` log the classification so the choice is auditable:

```json
{
  "complexity_class": "small",
  "signals": {
    "components_in_scope": 1,
    "shared_layer_touched": false,
    "greenfield": false,
    "fr_count": 1
  },
  "workflow_depth": "waves 2,3,6",
  "spec_depth": "light",
  "downgrade_from": null,
  "reclassified_reason": null
}
```

Written to `agent_state/phases/${PHASE}/complexity.json`. If a task is reclassified upward mid-run
(e.g. a "small" change turned out to touch the shared layer), record `reclassified_reason` and
re-enter the deeper depth — **upgrades are always allowed, downgrades never are** once a wave finds
scope the classifier missed.

---

## Interaction with model-routing

| Concern | Skill | Question answered |
|---|---|---|
| Which **model** per agent | `model-routing.md` | haiku / sonnet / opus |
| Which **workflow depth** | this skill | skip / light / full / full+ADR |

They compose: a PLATFORM class typically routes opus for spec + review agents; a TRIVIAL class routes
haiku and skips most agents entirely. Consult **both** — one picks the engine, the other picks how
far the car drives.
