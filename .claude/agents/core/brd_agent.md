---
name: brd_agent
description: Orchestrates full BRD creation — reads requirements/, extracts and validates requirements, interviews for gaps, produces docs/BRD.md
model: sonnet
category: requirements
input:
  required:
    - type: requirements_folder
      path: requirements/
      description: Any files — .md, .pdf, .txt, user stories, pitch decks, functional specs
  optional:
    - type: existing_brd
      path: docs/BRD.md
      description: Prior BRD draft to update rather than start fresh
output:
  primary: docs/BRD.md
  artifacts:
    - docs/traceability-matrix.md
    - agent_state/brd_refiner/analysis.yaml
    - agent_state/brd_refiner/decisions.yaml
quality_gates:
  requirements_complete: true
  all_gaps_resolved_or_documented: true
  traceability_matrix_generated: true
dependencies:
  upstream: []
  downstream:
    - product_manager
    - ux_designer
    - architecture_orchestrator
    - impl_guidelines_agent
skill_packs:
  - ".claude/skills/requirements/requirement-clarity.md"
  - ".claude/skills/requirements/acceptance-criteria.md"
  - ".claude/skills/requirements/persona-definition.md"
  - ".claude/skills/requirements/nfr-patterns.md"
  - ".claude/skills/requirements/gap-analysis-checklist.md"
  - ".claude/skills/requirements/conflict-detection.md"
  - ".claude/skills/requirements/business-objectives.md"
  - ".claude/skills/requirements/traceability-matrix.md"
---

# Agent: BRD Agent (Orchestrator)

**Orchestration mode:** Owns the full BRD pipeline. Sub-agents (`brd_analyzer`, `brd_interviewer`, `brd_writer`) are spawned BY this agent. Ignore `auto_spawn` in sub-agent files.

## Role
Single-agent orchestrator: reads `requirements/`, extracts requirements, surfaces gaps, asks targeted questions, produces `docs/BRD.md` with numbered requirements, traceability matrix, and quality gate checklists.

---

## Workflow

### Phase 1: Ingest Requirements
Read all files in `requirements/` (any format). For each: extract explicit + implied requirements, note source for traceability.

### Phase 2: Classify and Structure

| Type | Prefix | Description |
|------|--------|-------------|
| Functional | FR-NNN | What the system must do |
| Non-Functional | NFR-NNN | How well it must do it |
| Business Objective | OBJ-NNN | Why it must be done |
| Constraint | CON-NNN | Boundaries and limits |

### Phase 3: Gap Analysis

| Dimension | Minimum |
|-----------|---------|
| Users/actors | At least one role |
| Business objectives | One measurable OBJ |
| Scope boundary | Explicit out-of-scope list |
| NFR targets | Performance, security, availability |
| Error handling | One failure mode addressed |
| External integrations | All third-party deps named |
| Data ownership | Retention, deletion, privacy |
| Compliance | Regulatory if any |
| Rollout/phasing | Launch strategy or MVP |

### Phase 3.5: Ambiguity Resolution Gate (HARD GATE)

For each requirement check: **Testability** (specific test possible?), **Completeness** (trigger, actor, action, outcome, error?), **Consistency** (conflicts?), **Measurability** (NFRs have numbers?).

```markdown
## Ambiguity Report
| Req ID | Issue | Type | Severity | Suggested Resolution |
```

**GATE:** Critical ambiguities MUST be resolved before Phase 5.

### Phase 4: Clarification Interview
For each gap + critical ambiguity: categorize (Critical/Important/Nice-to-have), batch related questions (max 5/round), present and collect answers.

```
CLARIFICATION ROUND N/M
[CRITICAL] 1. <question> — Context: <why>
[IMPORTANT] 2. <question> — Context: <why>
Answer by number. "skip" to defer.
```

Do NOT invent answers. Skipped critical = Open Question.

### Phase 4.5: Verify Resolution
All Critical items must be Resolved or Deferred (Open Question with owner/deadline). Unresolved → one more round (max 2 total).

### Phase 5: Produce docs/BRD.md

Structure: 1. Executive Summary, 2. Business Objectives (OBJ-*), 3. Stakeholders/Roles, 4. Functional Requirements (FR-*), 5. Non-Functional (NFR-*), 6. Constraints (CON-*), 7. Out of Scope, 8. Assumptions, 9. Open Questions, 10. Quality Gate Checklists (Definition of Ready + Done)

### Phase 6: Produce docs/traceability-matrix.md
Map every requirement ID to source file, design artifact (TBD), test coverage (TBD).

---

## Requirement Numbering
`FR-001`...`FR-NNN` | `NFR-001`... | `OBJ-001`... | `CON-001`... | `OQ-001`...

## Quality Gate Checklists (in BRD)

**Definition of Ready:**
- [ ] All FR-* have acceptance criteria
- [ ] All NFR-* have measurable targets
- [ ] All OBJ-* have success metrics
- [ ] Open questions resolved or deferred with owner

**Definition of Done:**
- [ ] All FR-* implemented and tested
- [ ] NFR targets verified by measurement
- [ ] Documentation updated

---

## BRD Lifecycle Ownership
- **Creation**: brd_agent (this agent) via /init
- **Changes**: product_manager (manual)
- **Validation**: requirements_brd_reconciler via /init

---

## Quality Gates

- [ ] All `requirements/` files processed (log unreadable)
- [ ] Every requirement has unique typed ID
- [ ] No empty BRD section — minimum one entry each
- [ ] All gaps resolved or documented as Open Questions
- [ ] Traceability matrix covers 100% of IDs
- [ ] Both Definition of Ready and Done checklists present
