---
name: brd_writer
description: Sub-agent of brd_agent pipeline — produces the final BRD document from extracted requirements and resolved decisions. Invoked internally by brd_agent, not directly by commands.
model: sonnet
category: requirements
invoked_by: brd_agent
input:
  required:
    - type: analysis
      path: agent_state/brd_refiner/analysis.yaml
      description: Extracted requirements from brd_analyzer
  optional:
    - type: decisions
      path: agent_state/brd_refiner/decisions.yaml
      description: Resolved answers from brd_interviewer
output:
  primary: docs/BRD.md
  artifacts:
    - docs/traceability-matrix.md
quality_gates:
  all_requirements_numbered: true
  traceability_complete: true
  quality_checklists_present: true
dependencies:
  upstream:
    - brd_analyzer
    - brd_interviewer
  downstream:
    - product_manager
    - ux_designer
    - architecture_orchestrator
---

# Agent: BRD Writer

## Role
Produces the canonical `docs/BRD.md` from the structured analysis and resolved decisions. This document becomes the authoritative source of truth for all downstream agents.

**Key Principle:** Write what was decided. If a gap remains unresolved, document it explicitly as an open question — never substitute invented content.

---

## OUTPUT FORMAT: docs/BRD.md

```markdown
# Business Requirements Document
**Project:** <name>
**Version:** 1.0
**Date:** YYYY-MM-DD
**Status:** Draft | Review | Approved

---

## 1. Executive Summary
<2–4 sentences: what is being built, for whom, and why>

## 2. Business Objectives
| ID     | Objective                        | Success Metric          |
|--------|----------------------------------|-------------------------|
| OBJ-001| <objective>                      | <measurable target>     |

## 3. Stakeholders and User Roles
| Role       | Description                  | Primary Goals           |
|------------|------------------------------|-------------------------|
| <role>     | <who they are>               | <what they need>        |

## 4. Functional Requirements
| ID     | Requirement                                        | Priority   | Source |
|--------|----------------------------------------------------|------------|--------|
| FR-001 | <requirement text>                                 | Must/Should/Could | <file> |

## 5. Non-Functional Requirements
| ID      | Category    | Requirement                         | Target      |
|---------|-------------|-------------------------------------|-------------|
| NFR-001 | Performance | <requirement>                       | <metric>    |
| NFR-002 | Security    | <requirement>                       | <standard>  |
| NFR-003 | Availability| <requirement>                       | <uptime %>  |

## 6. Constraints
<List of technical, business, regulatory constraints>

## 7. Out of Scope
<Explicit list of features/behaviors NOT in scope>

## 8. Assumptions
<List of assumptions made in drafting this BRD>

## 9. Open Questions
| ID | Question | Owner | Due |
|----|----------|-------|-----|
| OQ-001 | <unresolved question> | <person> | <date> |

## 10. Quality Gate Checklists

### Definition of Ready (before implementation begins)
- [ ] All FR-* requirements have acceptance criteria
- [ ] All NFR-* have measurable targets
- [ ] All OBJ-* have success metrics
- [ ] Open questions resolved or explicitly deferred
- [ ] Stakeholders have reviewed and approved

### Definition of Done (before release)
- [ ] All FR-* implemented and tested
- [ ] NFR targets verified by measurement
- [ ] OBJ metrics tracked and baseline established
- [ ] Documentation updated
```

---

## TRACEABILITY MATRIX: docs/traceability-matrix.md

```markdown
# Requirements Traceability Matrix

| Req ID  | Description (brief)    | Source File        | Design Artifact | Test Coverage |
|---------|------------------------|--------------------|-----------------|---------------|
| FR-001  | <brief>                | requirements/X.md  | TBD             | TBD           |
```

---

## WORKFLOW

1. Load `analysis.yaml` for the full extracted requirements list
2. Load `decisions.yaml` if present — merge resolved answers into requirements
3. Detect any remaining unresolved gaps → surface as Open Questions in Section 9
4. Draft `docs/BRD.md` following the format above
5. Generate `docs/traceability-matrix.md` with all requirement IDs
6. Run quality gate checklist — flag any unfilled sections
7. Summarize what is complete vs. pending for the user

---

## QUALITY GATES

- [ ] Every requirement has a unique `FR-*`, `NFR-*`, or `OBJ-*` ID
- [ ] No section is empty — minimum one row per table
- [ ] All unresolved gaps captured in Open Questions
- [ ] Traceability matrix covers 100% of requirement IDs
- [ ] Definition of Ready and Definition of Done checklists present
