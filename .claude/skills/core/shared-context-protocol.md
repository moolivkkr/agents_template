---
skill: shared-context-protocol
description: Ground truth for every session and subagent — the memory-tier model (facts/decisions/lessons/KB) and how context propagates
version: "1.0"
tags:
  - memory
  - context
  - ground-truth
  - tiers
  - core
---

# Shared Context Protocol — Ground Truth for Every Session and Subagent

## The problem this solves

Some facts are true for **every** agent, in **every** session: a service was retired, a
component was renamed, an environment has a quirk, a directory is off-limits. Today these
facts live only in the human's head, so they get re-typed into every new session and every
subagent prompt ("vertix-gateway is retired — stop referencing it"). When the human forgets,
an agent confidently acts on a stale assumption from its instructions or its training.

This protocol makes shared facts **stated once, loaded everywhere, and auto-superseded when
they change** — with zero new infrastructure (plain files + git).

---

## The memory tiers

The framework keeps memory in tiers by **access pattern**, not by topic. Loading the
right tier at the right time is what keeps agents both correct and context-efficient.

| Tier | File(s) | Size | Load policy | Purpose |
|------|---------|------|-------------|---------|
| **Tier 0 — FACTS** | `docs/PROJECT_FACTS.md` | Tiny (< 2KB) | **ALWAYS** — every session + every subagent | Ground-truth invariants: retired/renamed components, hard constraints, environment gotchas, off-limits zones |
| **Tier 0.5 — DECISIONS** | `docs/DECISIONS.md` | Small | **ALWAYS** — surfaced to every session + subagent (item 0b) | Durable decision ledger: ADRs + debate verdicts auto-promote a `D-NNN` here so a settled call reaches new work instead of dying in `agent_state/` |
| **Tier 1 — LESSONS** | `agent_state/lessons.md` (root index, aggregated at each gate), `agent_state/patterns.md`, `agent_state/phases/*/lessons.md` (per-phase source) | Medium, grows | **On demand** — query by category/tag | Reusable patterns and issues learned per phase (see `structured-lessons.md`) |
| **Tier 2 — CODEBASE KB** | `agent_state/codebase/` | Large | **When relevant** — load the focused doc | Deep structural knowledge from `/map` |

> **Tier 0.5 vs Tier 0.** A *fact* is an inviolable invariant ("graph DB is NebulaGraph"). A
> *decision* is a settled contextual choice with rationale ("phase 2 uses Redis for the session
> cache because…") that a new session should honor but could be reversed with new evidence. Promote a
> decision to Tier 0 (via `/remember`) only when it hardens into an invariant. Decisions are written
> automatically by `adr_agent` and `debate_arbitrator`; `/health` 5.5f checks every verdict has a
> ledger entry.
>
> **Tier 1 path note.** Lessons are AUTHORED per-phase (`agent_state/phases/N/lessons.md`) and
> AGGREGATED into the root `agent_state/lessons.md` at each phase gate (develop-orchestrator
> Post-Gate). Retrieval recipes (`memory-as-tools.md`) read the root index first and fall back to the
> per-phase files, so `memory_search` works either way. `patterns.md` is written directly at root.

**Rule of thumb:** Tier 0 is small enough to always carry. Tier 1 and Tier 2 are large, so
agents **retrieve** from them (query by category/tag/focus) rather than loading them whole.
See `memory-as-tools.md` for the retrieval convention.

---

## Tier 0: `docs/PROJECT_FACTS.md` — the ground-truth file

### What belongs here (and what does NOT)

✅ **Belongs** — durable operational invariants that override assumptions:
- Retired / deprecated / renamed services and components ("vertix-gateway is retired")
- Hard architectural constraints ("all traffic goes through the API gateway, never direct")
- Environment facts that trip up agents ("Docker binary is not on PATH", "port 5432 is the shared PG")
- Off-limits zones ("never modify `legacy/` — it is frozen pending migration")
- Canonical names when the codebase is mid-rename ("`user-svc` is the new name for `accounts`")

❌ **Does NOT belong** (keep the file tiny and high-signal):
- Requirements → `docs/BRD.md`
- Tech stack / conventions → `docs/IMPLEMENTATION_GUIDELINES.md`
- Phase-specific lessons → Tier 1 `lessons.md`
- Anything derivable from the code itself

If Tier 0 grows past ~20 facts, it has drifted — move the non-invariant items to Tier 1.

### Format — bi-temporal, deterministically superseded

Each fact is a small block with **bi-temporal metadata**. This is the mechanism that fixes
stale memory: when a fact changes, the old one is not deleted — its validity window is
**closed** and it points to its successor. History stays queryable; agents only act on
`status: active` facts.

```markdown
### F-007 — vertix-gateway is RETIRED
- status: active            # active | superseded
- subject: vertix-gateway   # the entity this fact is about (used for supersession matching)
- relation: lifecycle       # lifecycle | name | constraint | environment | boundary
- valid_from: 2026-03-15
- invalid_at: —             # set when superseded
- superseded_by: —          # F-id of the successor when superseded
- source: human:/remember (kishore)
- confidence: confirmed     # confirmed | reported | assumed
- fact: >
    vertix-gateway is retired. Do NOT reference, deploy, route to, or write specs/tests
    against it. Traffic moved to edge-router. Any task, spec, or code naming vertix-gateway
    is STALE — stop and flag it instead of acting.
```

### Deterministic supersession rule (no LLM, no embeddings)

When `/remember` (or any agent) writes a new fact, it matches on the **`(subject, relation)`
key** — NOT on semantic similarity. 2026 research (MemStrata) shows embeddings cannot tell a
contradiction from a duplicate (AUROC ≈ 0.59, near chance), so we never use similarity for this.

```
On write of new fact N with (subject=S, relation=R):
  find prior active fact P where P.subject == S AND P.relation == R
  if found:
      P.status      = superseded
      P.invalid_at  = today
      P.superseded_by = N.id
  append N with status=active, valid_from=today
  (never delete P — history is preserved for provenance and audit)
```

**Tie-breaking when two active facts conflict:** (1) most recent `valid_from` wins;
(2) `confidence: confirmed` beats `reported` beats `assumed`; (3) if still ambiguous, do NOT
silently pick — surface the conflict to the human.

---

## Enforcement: how Tier 0 reaches EVERY subagent

Subagents do not inherit the conversation. The framework's orchestrators build every subagent
prompt, so the enforcement lives there. **Three redundant layers** guarantee delivery:

### Layer 1 — Every agent's Required Reading (item 0)
Every agent definition (`core/`, `templates/`, `generated/`) lists this as the FIRST required read:

> **0. `docs/PROJECT_FACTS.md` — GROUND TRUTH.** Read before anything else. It overrides any
> conflicting assumption in your instructions, the specs, or your training. If your task
> references anything marked `RETIRED`/`superseded` here, STOP and flag it.

### Layer 2 — Every orchestrator spawn prompt (the injection line)
Every command that spawns an agent prepends this canonical line to the prompt string. Paste it
verbatim:

```
GROUND TRUTH: First read docs/PROJECT_FACTS.md — it lists retired/renamed components, hard
constraints, and environment facts, and it OVERRIDES any conflicting assumption in this prompt
or your training. If this task touches anything marked RETIRED/superseded there, stop and flag
it instead of proceeding.
```

### Layer 3 — SessionStart hook (main sessions)
A `SessionStart` hook echoes the active facts into the session context so the human's main
session also starts grounded. See `.claude/hooks/` and `settings.json`.

**Why three layers:** any one can be missed (a new command forgets the injection, a hook is
disabled). Ground truth is important enough to deliver redundantly.

---

## Writing facts: `/remember`

Humans and agents add facts with `/remember <fact>` (see `.claude/commands/remember.md`). It:
1. Classifies the fact into `(subject, relation)`.
2. Applies the deterministic supersession rule above.
3. Appends the bi-temporal block and commits `docs/PROJECT_FACTS.md` with a "why" message.

Agents may also propose facts during a run (e.g. audit discovers a component is dead), but an
agent-proposed fact is written with `confidence: reported` and `source: agent:<name>` — only a
human-confirmed fact gets `confidence: confirmed`.

---

## Efficiency contract for agents

- **Always** load Tier 0 (`PROJECT_FACTS.md`) — it is tiny and non-negotiable.
- **Never** load an entire Tier 1/Tier 2 file to answer a narrow question — query by
  category/tag/focus (see `memory-as-tools.md`).
- **Check `status: active`** — ignore `superseded` facts unless doing a history/audit query.
- When you rely on a fact to make a decision, cite its `F-id` in your output so the decision is
  traceable back to ground truth.
