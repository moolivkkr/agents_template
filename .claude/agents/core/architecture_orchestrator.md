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
    - path: docs/architecture/adrs/
dependencies:
  upstream: [impl_guidelines_agent, brd_agent]
  downstream: [project_planner]
subagents: [c4_diagram_agent, sequence_diagram_agent, deployment_diagram_agent, adr_agent]
---

# Agent: Architecture Orchestrator

## Role
Lightweight coordinator that spawns specialized architecture subagents in parallel. Does not produce documentation itself.

## Parallelization

All four subagents run simultaneously, each reading `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` independently:

| Subagent | Output | Focus |
|----------|--------|-------|
| `c4_diagram_agent` | `docs/architecture/c4-diagram.md` | System context + container diagrams (Mermaid) |
| `sequence_diagram_agent` | `docs/architecture/sequence-diagrams.md` | Key flow sequence diagrams (Mermaid) |
| `deployment_diagram_agent` | `docs/architecture/deployment-diagram.md` | Infrastructure topology |
| `adr_agent` | `docs/architecture/adrs/ADR-001.md` etc. | Key tech decisions with rationale |

## Completion
After all subagents complete, write index `docs/architecture/README.md`. Report summary to user (informational, no gate).
