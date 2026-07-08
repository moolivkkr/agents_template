---
skill: procedural-memory
description: The procedural memory tier — how a recurring, high-confidence lesson is PROMOTED into an enforced rule or reusable skill routine instead of staying as prose agents may skip
version: "1.0"
tags:
  - memory
  - procedural
  - promotion
  - lessons
  - enforcement
  - core
---

# Procedural Memory — Turning Recurring Lessons into Enforced Routines

> **Read Tier 0 first.** `docs/PROJECT_FACTS.md` (ground-truth invariants) is always loaded whole.
> This skill is the **write side of promotion**: it governs how Tier 1 episodic memory graduates into
> durable procedural artifacts. Retrieval discipline lives in [[memory-as-tools]]; the tier model lives
> in [[shared-context-protocol]]; the lesson schema/confidence model lives in [[structured-lessons]].

## The missing quadrant (CoALA)

The framework already keeps three of the four CoALA memory quadrants:

| Quadrant | Question it answers | Where it lives |
|---|---|---|
| **Semantic** | "What is true?" | Tier 0 facts (`PROJECT_FACTS.md`), Tier 0.5 decisions (`DECISIONS.md`) |
| **Episodic** | "What happened, and what did we learn?" | Tier 1 lessons/patterns (`agent_state/`, see [[structured-lessons]]) |
| **Procedural** | "How do we reliably DO the right thing?" | **← this tier (Tier 1.5)** |

Episodic memory records *"tests kept missing the empty-state case in phases 2, 4, and 5."* That prose
is only useful if an agent happens to retrieve and read it. **Procedural memory** is the mechanism that
converts a recurring, validated lesson into something the process **executes or enforces** — a checklist
item, a hard fact, or a gate/reviewer rule. The slogan: **"we always forget X" becomes "the process now
enforces X."**

Procedural artifacts are **generative, not descriptive.** A lesson says what went wrong once; a
procedural artifact is a routine future agents run every time, whether or not they read the lesson.

---

## Promotion criteria — when a lesson qualifies

A Tier 1 lesson is a **promotion candidate** only when ALL of the following hold. This gate is
deliberately strict: promotion adds process weight, so it must be earned.

1. **Recurrence ≥ N.** The same underlying lesson (matched by `(category, tags)` cluster and summary,
   per [[structured-lessons]]) has appeared in **≥ 3 distinct phases** — i.e. its `patterns.md` evidence
   line cites 3+ phases, or 3+ `L-*` entries collapse to it during the `/consolidate` dedup sweep.
   Default **N = 3**; a security-category lesson may promote at **N = 2** (higher stakes, lower bar).
2. **Confidence ≥ HIGH.** The pattern is `Confidence: HIGH` in `patterns.md` (validated across 2+ phases
   with consistent results, per the [[structured-lessons]] confidence table). `DEPRECATED` never
   promotes — it stays as an anti-pattern signal.
3. **Actionable as a check or routine.** The lesson can be phrased as a concrete, verifiable step —
   *"assert the empty-state renders"* — not a vague aspiration (*"write better tests"*). If you cannot
   phrase it as a checklist line or a pass/fail rule, it is not yet procedural.
4. **Not already enforced.** No existing skill checklist item, Tier 0 fact, or gate rule already covers
   it (avoid duplicate procedure). Check before promoting.

A lesson meeting (1)+(2)+(3)+(4) is promoted. One meeting (1)+(2) but failing (3) stays episodic and is
noted as "recurring but not yet actionable" for a human to sharpen.

---

## The three promotion targets

Choose the target by the *nature* of the lesson, not by convenience:

| Target | Choose when | Artifact touched | Enforced by |
|---|---|---|---|
| **A — Skill checklist** | The lesson is a *routine* an agent should run every time (a repeatable procedure or verification step) | Add/append a checklist item to the relevant `.claude/skills/**/*.md` (e.g. a testing or UX skill) | The agent that reads that skill runs the step |
| **B — Tier 0 fact** | The lesson has hardened into an *inviolable constraint* — a thing that must never happen, environment-wide | A fact via `/remember` (see [[shared-context-protocol]]) | Loaded into every session + subagent (3 layers) |
| **C — Gate/reviewer rule candidate** | The lesson should *block the gate* or drive a reviewer if violated — mechanical, checkable at gate time | An entry in `agent_state/procedural_candidates.md` (a proposal list; wiring is a separate human/framework step) | verify-gate hook or a named reviewer, once wired |

**Target selection heuristic**
- Is it a step someone *does*? → **A** (checklist).
- Is it a truth that must *never be violated*? → **B** (fact).
- Is it a condition a machine could *check and fail*? → **C** (gate candidate).

A single lesson may warrant more than one target (e.g. a hard security constraint → both a Tier 0 fact
**and** a gate-rule candidate). Promote to each that applies.

> **Important — target C is a *candidate*, not a live rule.** Procedural memory PROPOSES gate rules; it
> never edits `verify-gate.sh`, the gate logic, or `remember.sh`, and it never creates agents. Wiring a
> candidate into an actual gate/reviewer is a deliberate downstream step a human or the framework owner
> takes after reviewing `agent_state/procedural_candidates.md`.

---

## Promotion procedure (runs inside `/consolidate`)

Promotion is **strictly additive and non-destructive** — it NEVER deletes, edits, or supersedes the
source lesson. The lesson remains the episodic provenance for the procedural artifact.

For each qualifying lesson:

1. **Confirm the criteria** (recurrence, confidence, actionability, not-already-enforced) against the
   consolidated `patterns.md`/`lessons.md` index.
2. **Select the target(s)** A / B / C per the heuristic above.
3. **Write the procedural artifact:**
   - **A** — append a checklist line to the matching skill, tagged with provenance:
     `<!-- promoted from L-4-002,L-2-005 (recur×3, HIGH) via /consolidate 2026-07-07 -->`
   - **B** — hand off to `/remember` with the constraint phrased as an instruction (do NOT hand-edit
     `PROJECT_FACTS.md`; `/remember`'s script does the deterministic supersession).
   - **C** — append a candidate block to `agent_state/procedural_candidates.md` (schema below).
4. **Backlink, do not move.** Add a one-line `Promoted-to:` note on the source pattern entry
   (e.g. `Promoted-to: skill:testing/ui-testing-checklist#empty-state (2026-07-07)`) so the episodic
   entry now records that it became procedure. The lesson text is otherwise untouched.
5. **Report** each promotion in the `/consolidate` summary (target, source IDs, artifact path).

### `agent_state/procedural_candidates.md` — the gate-rule proposal schema

```markdown
### PC-001 — E2E must assert the empty-state render
- promoted_from: L-2-005, L-4-002, L-5-001   # source lessons (kept, never deleted)
- recurrence: 3 phases
- confidence: HIGH
- category: testing
- proposed_target: verify-gate | reviewer:code_reviewer_II   # suggestion only
- rule: >
    For every list/collection view, the E2E tier must include a TC-* asserting the empty-state
    (zero rows) renders the documented empty component. Fail the gate if a list view ships without one.
- status: proposed        # proposed | wired | rejected
- proposed_on: 2026-07-07
```

`status` starts `proposed`. A human (or a framework-owner pass) flips it to `wired` after adding the
check to the gate/reviewer, or `rejected` with a reason. `/consolidate` never flips it itself and never
touches the gate.

---

## Worked example — the empty-state case

**Episodic signal (Tier 1, already in memory):**
Across phases 2, 4, and 5, `L-*` entries all report the same thing: a list view shipped without handling
the zero-rows case; the bug was caught late in review each time.

**During `/consolidate`:** the dedup sweep collapses the three `L-*` entries onto one pattern:

```
P-014 · Category: testing · Tags: e2e, ui, empty-state
Pattern: List/collection views repeatedly shipped without an empty-state assertion.
Evidence: Phase 2, Phase 4, Phase 5 — each caught the same gap in review.
Confidence: HIGH (validated across 3 phases)
```

**Criteria check:** recurrence = 3 phases ✅ · confidence HIGH ✅ · actionable ("assert empty-state
renders") ✅ · not already enforced ✅ → **qualifies.**

**Target selection:** it is both a step an agent *does* (→ **A**, a UI-testing checklist item) and a
condition a machine could *check and fail* at the gate (→ **C**, a gate-rule candidate). Promote to both:

- **A** — append to the UI/testing checklist skill:
  `- [ ] Every list/collection view has a TC-* asserting the empty-state (zero rows) renders. <!-- promoted from P-014 (recur×3, HIGH) 2026-07-07 -->`
- **C** — append `PC-001` (schema above) to `agent_state/procedural_candidates.md`, `status: proposed`.

**Backlink:** `P-014` gains `Promoted-to: skill:testing UI checklist + PC-001 (2026-07-07)`. Nothing is
deleted. Next phase's UX/test agents now run the empty-state check because it is in their checklist — the
recurring miss is closed by process, not by hoping someone rereads a lesson.

---

## Rules

1. **Additive only.** Promotion never deletes, edits, or supersedes the source lesson — it backlinks.
   History stays in Tier 1 and in git.
2. **Earn the promotion.** Do not promote below N recurrences or below HIGH confidence. Process weight is
   a cost; unearned rules are friction.
3. **Candidates, not edits, for the gate.** Target C writes a *proposal* to
   `agent_state/procedural_candidates.md`. Never touch `verify-gate.sh`, gate logic, `remember.sh`, or
   create agents from here.
4. **Facts go through `/remember`.** Target B never hand-edits `PROJECT_FACTS.md` — it calls `/remember`
   so the deterministic `(subject, relation)` supersession runs.
5. **One source of truth per rule.** Before promoting, confirm the rule is not already a checklist item /
   fact / candidate (criterion 4). No duplicate procedure.
