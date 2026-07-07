---
command: converge
description: Assess the codebase against specs/plan and generate the remaining delta as catch-up tasks (as-spec-wins). Inverse of reconcile.
arguments:
  - name: phase
    required: false
    description: "Phase to converge. Omit to assess the whole project against all specs."
  - name: apply
    required: false
    default: false
    description: "Immediately feed the generated delta into /develop after writing it."
---

# /converge — Generate the Spec→Code Catch-Up Delta

> **Alias of `/recon --fix=code`** (spec-wins). `/recon` is the canonical two-way entry point; this
> command remains as a direct alias and holds the detailed spec-wins procedure below.

> **Read Tier 0 first.** Load `docs/PROJECT_FACTS.md` (ground-truth invariants) before assessing.
> A retired/renamed fact means the spec item it references is *not* a missing feature — it is a
> retired one; do not generate catch-up work for retired components.

`/converge` compares the **specs/plan** (BRD, TRDs, data contracts, UI specs, TC-* inventory) against
the **actual code** and produces a task list of everything the spec requires that the code does not yet
have. Output is feedable straight into `/develop`.

---

## Direction: converge vs reconcile

The framework has **two directions** for closing the spec↔code gap. Pick by which artifact is the
source of truth:

| | **reconcile** (existing) | **/converge** (this command) |
|---|---|---|
| Winner | **As-built wins** | **As-spec wins** |
| Action | Update *docs* to match the *code* | Generate *tasks* to bring the *code* up to the *spec* |
| Output | Corrected BRD/TRD + completion notes | A delta task list of missing implementation |
| Use when | Code drifted ahead / docs are stale and you trust the implementation | Spec is the contract and code is behind — you want to *build the gap*, not document around it |
| Direction of change | Docs ← Code | Code ← Spec (planned as tasks, built by `/develop`) |

**Rule of thumb:** if you'd say *"the docs are wrong, the code is right"* → run reconcile. If you'd say
*"the code is incomplete against what we agreed to build"* → run `/converge`.

---

## Step 0 — Scope & Load

```bash
if [ -n "$ARG_PHASE" ]; then
  SPEC_DIR="docs/design/phases/${ARG_PHASE}/specs"
  SCOPE_LABEL="phase ${ARG_PHASE}"
else
  SPEC_DIR="docs/design/phases"        # all phases
  SCOPE_LABEL="whole project"
fi
echo "Converge scope: $SCOPE_LABEL"
```

Load:
- `docs/PROJECT_FACTS.md` (Tier 0 — always)
- `docs/BRD.md` (FR-*, NFR-*, OBJ-*)
- The TRDs / UI specs / data contracts in `$SPEC_DIR`
- The TC-* inventory for the scope
- Tier 2 codebase KB via `memory-as-tools.md` (focused reads, not whole-dir)

---

## Step 1 — Enumerate what the spec REQUIRES

Extract, per phase in scope, the checklist of concrete deliverables:

- Every **FR-\*** mapped to the spec item(s) that satisfy it
- Every **interface contract** in the TRD (endpoints, methods, signatures)
- Every **data contract** (entities, fields, migrations)
- Every **UI spec** screen/component and its API bindings
- Every **TC-\*** id declared for the scope

## Step 2 — Verify what the code HAS (independent, distrustful)

For each required item, confirm it actually exists in code — do not trust the manifest:
> "A manifest reporting completion is a claim. Verify by reading the code and grepping for the symbol."

Classify each item:

| Status | Meaning |
|---|---|
| `present` | Implemented and matches the contract |
| `partial` | Exists but incomplete (stub, missing field, missing edge case, TODO) |
| `missing` | No implementation found |
| `divergent` | Implemented but does **not** match the spec contract (candidate for reconcile, not converge — flag it) |

`divergent` items are **not** put in the delta blindly — they are flagged, because "as-spec-wins" here
might mean the spec is stale. Surface them for a human/`reconcile` decision.

## Step 3 — Generate the Delta

For every `missing` or `partial` item, emit a task sized and ordered for `/develop`:

```markdown
### DELTA-${PHASE}-001
- **Satisfies:** FR-012, TC-INT-034
- **Status found:** missing
- **Required by spec:** POST /api/v1/orders/{id}/cancel — idempotent, returns 409 on already-cancelled
- **Evidence of gap:** no handler for cancel route; grep 'cancel' in internal/orders returns 0
- **Task:** Implement cancel handler + service method + repo update + idempotency guard
- **Tests owed:** TC-INT-034, TC-E2E-009
- **Complexity class:** small   # per scale-adaptive-depth.md
```

Order tasks by dependency (data layer before service before handler before UI), and tag each with a
complexity class per `scale-adaptive-depth.md` so `/develop` picks the right wave depth.

## Step 4 — Write the delta file

```bash
mkdir -p agent_state/convergence
OUT="agent_state/convergence/${ARG_PHASE:-all}-delta.md"
```

Write to `agent_state/convergence/<phase>-delta.md`:

```markdown
# Convergence Delta — <scope> — <timestamp>
Direction: as-spec-wins (generate catch-up work)

## Summary
- Required items: 42   present: 30   partial: 5   missing: 6   divergent: 1

## Catch-up tasks (feed to /develop)
DELTA-... (as above, dependency-ordered)

## Divergent (needs decision — reconcile candidate)
- FR-018: code returns 200 where spec says 202 — spec stale? confirm before building.
```

## Step 5 — Report / Apply

```
Convergence Delta — <scope>

  Required: 42   Present: 30   Partial: 5   Missing: 6   Divergent: 1
  Catch-up tasks generated: 11   (agent_state/convergence/<phase>-delta.md)
  Divergent items needing decision: 1

  Next:
    /develop --phase=N   (implements the delta tasks for that phase)
```

If `--apply` is set, hand the delta task list to `/develop` for the scoped phase(s) instead of stopping
at the report. Divergent items are **never** auto-applied — they always require a decision first.
