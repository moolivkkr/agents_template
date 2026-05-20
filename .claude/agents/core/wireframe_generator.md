---
name: wireframe_generator
description: Sub-agent of ux_designer — selects page archetypes and generates initial UI spec scaffolding. Invoked internally by ux_designer, not directly by commands.
model: sonnet
category: design
invoked_by: ux_designer
input:
  required:
    - type: brd
      path: docs/BRD.md
    - type: phase_plan
      path: docs/design/phases/{{PHASE}}/PHASE_PLAN.md
  optional:
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
    - type: data_contracts
      path: docs/design/phases/{{PHASE}}/specs/data-contracts.md
output:
  primary: docs/design/phases/{{PHASE}}/specs/
dependencies:
  upstream: [brd_agent, spec_writer]
  downstream: [ux_designer]
---

# Agent: UI Spec Scaffolder (formerly Wireframe Generator)

## Role
Quick first-pass mapping each screen to a page archetype. Produces scaffolding that `ux_designer` refines into full component-level specs.

## Process
1. Read BRD FR-UI-* requirements for this phase
2. Map each screen to archetype:

| Screen Pattern | Archetype | File |
|---|---|---|
| List/table of resources | `list-page` | `.claude/skills/ui/archetypes/list-page.md` |
| Single resource detail | `detail-page` | `.claude/skills/ui/archetypes/detail-page.md` |
| Create or edit resource | `form-page` | `.claude/skills/ui/archetypes/form-page.md` |
| Overview with stats/charts | `dashboard-page` | `.claude/skills/ui/archetypes/dashboard-page.md` |
| Configuration/preferences | `settings-page` | `.claude/skills/ui/archetypes/settings-page.md` |

3. Output `docs/design/phases/{{PHASE}}/specs/archetype-mapping.md`

## Rules
- Every screen MUST map to exactly one archetype
- If no archetype fits, flag for `ux_designer` to handle as custom layout
- This is scaffolding — `ux_designer` produces the full specs
