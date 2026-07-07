# PROJECT_FACTS — Ground Truth for startup-agents / Vertix estate

> **Tier 0 memory.** Every session and every subagent reads this file FIRST and treats it as
> ground truth. It overrides conflicting assumptions in prompts, specs, or model training.
> Protocol: `.claude/skills/core/shared-context-protocol.md`. Add facts with `/remember`.
>
> Keep this file TINY and high-signal (< ~20 active facts). Requirements go in the BRD, tech
> conventions in IMPLEMENTATION_GUIDELINES, phase lessons in `agent_state/lessons.md`.

## How to read this file
- Act ONLY on facts with `status: active`.
- `superseded` facts are kept for history/audit — ignore them for decisions.
- If a task references anything marked RETIRED/superseded here, STOP and flag it.

---

## Active Facts

### F-001 — Graph database is NebulaGraph, NOT Neo4j
- status: active
- subject: graph-database
- relation: name
- valid_from: 2026-07-06
- invalid_at: —
- superseded_by: —
- source: human:/remember (kishore)
- confidence: confirmed
- fact: >
    The Vertix graph stack is NebulaGraph 3.x (used by threatmatrix and storage), queried with
    nGQL. Do NOT recommend, research, spec, or generate Neo4j/Cypher-only patterns as the graph
    solution. Use `.claude/skills/databases/nebula.md`. If a task, spec, or agent output proposes
    Neo4j as the graph DB, STOP and flag it as a stale assumption.

---

## Superseded Facts (history — do not act on these)

_None yet._
