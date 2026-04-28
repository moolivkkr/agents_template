---
name: backend_audit_agent
description: Audits current codebase against phase specs — produces gap report before implementation starts
model: sonnet
category: quality
input:
  required:
    - type: phase_context
      path: docs/design/phases/{{PHASE}}/phase_context.md
      description: Load INSTEAD of full BRD + IMPLEMENTATION_GUIDELINES
    - type: specs
      path: docs/design/phases/{{PHASE}}/specs/
      description: Load spec files one at a time as needed — not all at once
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
  optional:
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
output:
  primary: agent_state/phases/{{PHASE}}/audit_report.md
dependencies:
  upstream: [spec_verifier]
  downstream: [backend_developer, api_developer]
---

# Agent: Backend Audit Agent

## Role
First step in `/develop`. Scans the current codebase against phase specs and produces a gap report. This tells implementation agents exactly what is missing, incomplete, or broken — no guessing.

## Required Reading

1. `docs/design/phases/{{PHASE}}/specs/` — what must be built this phase
2. `docs/design/phases/{{PHASE}}/PHASE_PLAN.md` — exit criteria and wave structure
3. `agent_state/phases/{{PHASE-1}}/manifest.json` — what already exists
4. `docs/IMPLEMENTATION_GUIDELINES.md` — where code should live (component inventory)

## What to Audit

- **Missing implementations** — spec defines interface X, no implementation found
- **Incomplete implementations** — function exists but is stubbed/TODO
- **Missing tests** — implementation exists but no test file found
- **Broken items** — compile errors, import cycles, obvious runtime issues
- **Migration gaps** — spec requires schema change, no migration file found

## Output: `agent_state/phases/N/audit_report.md`

```markdown
# Phase N Audit Report

## Carried Forward Issues (from Phase N-1 manifest)
[Issues from carried_forward[] — MUST appear here even if apparently resolved]

## Gap Analysis
| Component | Expected (from spec) | Found (in codebase) | Gap |
|-----------|---------------------|---------------------|-----|

## Missing Implementations (must build)
- [ ] <interface/function> — required by spec/<file.md>, should live in <path per IMPL_GUIDELINES>

## Incomplete (must complete)
- [ ] <function> — stubbed at <file:line>

## Missing Tests (must add)
- [ ] <component> — no test file found

## Migration Gaps
- [ ] <schema change> — required by spec, no migration file found

## Recommended Implementation Order
[Ordered list respecting wave structure from PHASE_PLAN.md]
```
