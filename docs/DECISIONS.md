# DECISIONS — Durable Decision Ledger (Tier 0.5)

> **Why this file exists.** Runtime decisions — debate verdicts, ADRs, reconciler resolutions,
> gray-area picks — used to die inside a run's artifacts (`agent_state/debates/*.json`,
> `docs/adr/`, gate files). A new session or subagent never saw them, so it would re-litigate or
> contradict a settled call. This ledger is the **one durable, always-surfaced place** where every
> significant decision and its rationale lives. It sits between Tier 0 facts (immutable ground
> truth) and Tier 1 lessons (queried on demand): decisions are loaded/surfaced like facts but can
> be reversed like lessons.
>
> **Relationship to Tier 0.** A decision that hardens into an inviolable constraint (e.g. "graph DB
> is NebulaGraph, never Neo4j") should be promoted to `docs/PROJECT_FACTS.md` via `/remember`. Most
> decisions stay here: they are contextual ("we chose X for phase 2 because Y"), not universal laws.
>
> **How it's populated (automatic — no manual bookkeeping):**
> - `adr_agent` appends a `D-NNN` line when it writes an ADR (links to the ADR file).
> - `debate_arbitrator` appends a `D-NNN` line when it renders a verdict (links to the verdict JSON).
> - `/develop-orchestrator` Post-Gate appends decisions captured in `decision-log.md` for the phase.
> - Humans/agents may append directly for a notable gray-area pick.
>
> **How it reaches new work:**
> - The `SessionStart` hook (`inject-ground-truth.sh`) surfaces active decision titles into every
>   new session alongside Tier 0 facts.
> - The orchestrator ground-truth injection line names this file, so every spawned subagent reads it.
> - It is Required-Reading item 0b in every agent (after `PROJECT_FACTS.md`).

## How to read this file
- Act on decisions with `status: active`. Treat them as settled — do not re-open without cause.
- `reversed` decisions are kept for history; ignore them for current work (but they explain *why*
  the current active decision exists — useful context).
- If new evidence contradicts an `active` decision, don't silently diverge: append a reversing
  decision (`reverses: D-NNN`) with rationale, or escalate to `debate_moderator`.

## Entry format
(Real entries live under "Active Decisions" below. This is the shape — note the placeholder status
so this example is not parsed as a live entry by the SessionStart hook.)
```
### D-<NNN> — <one-line decision title>
- status: <active | reversed>
- scope: <global | phase-N | component:name>
- date: <YYYY-MM-DD>
- source: <debate | adr | reconciler | human | planner>
- reverses: —            # or D-MMM if this overturns a prior decision
- reversed_by: —         # set when a later decision overturns this one
- link: <artifact path — ADR file, verdict JSON, decision-log anchor>
- decision: >
    <what was decided>
- rationale: >
    <why — the tradeoff, the alternatives rejected, the evidence>
```

---

## Active Decisions

_None yet. The first `/plan` (ADR) or `/develop` (debate) run will populate this._

---

## Reversed Decisions (history — do not act on these)

_None yet._
