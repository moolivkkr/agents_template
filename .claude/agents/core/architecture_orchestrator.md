---
name: architecture_orchestrator
description: Spawns parallel architecture subagents to produce system design documentation
model: opus
category: design
input:
  required:
    - type: brd
      path: docs/BRD.md
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
output:
  primary: docs/architecture/
  artifacts:
    - path: docs/architecture/c4-diagram.md
    - path: docs/architecture/sequence-diagrams.md
    - path: docs/architecture/deployment-diagram.md
    - path: docs/adr/
dependencies:
  upstream: [impl_guidelines_agent, brd_agent]
  downstream: [project_planner]
subagents: [c4_diagram_agent, sequence_diagram_agent, deployment_diagram_agent, adr_agent, eagle_diagram_agent]
---

# Agent: Architecture Orchestrator

## Role
Lightweight coordinator that spawns specialized architecture subagents in parallel for maximum efficiency. Does not produce documentation itself — delegates to subagents.

## Required Reading

- **`docs/PROJECT_FACTS.md` — GROUND TRUTH.** Read before anything else. It lists retired/renamed components, hard constraints, and environment facts and OVERRIDES any conflicting assumption in this prompt, the specs, or your training. If your task references anything marked RETIRED/superseded there, STOP and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)

---

## Parallelization

```
architecture_orchestrator
        │
  ┌─────┼──────┬──────┬──────┐
  ▼     ▼      ▼      ▼      ▼
 c4  sequence deploy  adr   eagle
```

All five subagents run simultaneously. Each reads `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` independently.

## Subagent Assignments

| Subagent | Output | Focus |
|----------|--------|-------|
| `c4_diagram_agent` | `docs/architecture/c4-diagram.md` | System context + container diagrams (Mermaid) |
| `sequence_diagram_agent` | `docs/architecture/sequence-diagrams.md` | Key flow sequence diagrams (Mermaid) |
| `deployment_diagram_agent` | `docs/architecture/deployment-diagram.md` | Infrastructure topology |
| `adr_agent` | `docs/adr/ADR-001.md` etc. | Key tech decisions with rationale (also promotes each to `docs/DECISIONS.md`) |
| `eagle_diagram_agent` | `docs/architecture/eagle-overview.md` | 10,000-foot strategic architecture overview |

## Completion

After all subagents complete, write index `docs/architecture/README.md` listing all produced documents.
Report summary to user — no gate, just informational.
