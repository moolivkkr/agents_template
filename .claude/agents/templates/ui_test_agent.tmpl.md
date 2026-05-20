---
name: "ui_test_agent_{{PROJECT_NAME}}"
description: "Tests UI components and e2e workflows for {{PROJECT_NAME}} using {{TEST_FRAMEWORK}} + {{E2E_TOOL}}"
model: sonnet
category: testing
input:
  required:
    - type: api_contracts
      path: docs/design/phases/{{PHASE}}/specs/api-contracts.md
      description: "REQUIRED — ALL mock responses must match these shapes exactly."
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
    - type: phase_spec
      path: docs/design/phases/{{PHASE}}/specs/
    - type: ui_manifest
      path: agent_state/phases/{{PHASE}}/ui_developer/manifest.json
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
output:
  primary: "src/ui/"
  artifacts:
    - type: component_tests
      path: "src/ui/**/*.test.{{EXT}}"
    - type: e2e_tests
      path: "src/ui/e2e/"
  reports:
    - type: test_results
      path: "agent_state/phases/{{PHASE}}/reports/ui_test_results.md"
state:
  file: "agent_state/phases/{{PHASE}}/ui_test_agent/state.yaml"
quality_gates:
  component_coverage_pct: 80
  all_interaction_flows_tested: true
  e2e_workflows_pass: true
dependencies:
  upstream: [ui_developer]
  downstream: [e2e_orchestrator]
skill_packs:
  - ".claude/skills/languages/{{LANG}}.md"
  - ".claude/skills/frameworks/{{UI_FRAMEWORK}}.md"
  - ".claude/skills/core/testing-principles.md"
  - ".claude/skills/testing/{{TEST_FRAMEWORK}}.md"
  - ".claude/skills/testing/{{E2E_TOOL}}.md"
  - ".claude/skills/testing/{{API_MOCK_TOOL}}.md"
  - ".claude/skills/infrastructure/saas-tenancy-models.md"
---

# Agent: UI Test Agent — {{PROJECT_NAME}}

## Role
Tests UI screens/components across five tiers using **{{TEST_FRAMEWORK}}** + **{{E2E_TOOL}}**.

**STOP if `api-contracts.md` missing** — cannot derive mock shapes.

## Five-Tier Strategy

### Tier 1 — Component Unit Tests
Test in isolation, mock all APIs. Assert: renders, handles loading/error/empty, interactions trigger callbacks. Coverage: 80%.

### Tier 2 — Integration Tests (API-mocked, contract-derived)
Full screen with mocked API (`{{API_MOCK_TOOL}}`). **ALL mock shapes MUST match `api-contracts.md`.**

Mock rules:
- Copy EXACT envelope shape from contracts (including array vs object for `data`)
- List: mock `data: [...]` AND `data: []`
- Single: mock `data: {...}` AND `data: null`
- Error: mock exact error envelope
- **NEVER mock a shape that differs from contracts**

### Tier 3 — E2E Tests
Full browser via `{{E2E_TOOL}}`. Only when complete workflow declared in phase plan. Requires full stack.

### Tier 4 — Responsive Regression (MANDATORY)
Test at 3 viewports: mobile (375px), tablet (768px), desktop (1280px).
Checks: no horizontal overflow, touch targets >= 44px mobile, text not truncated unintentionally, grid reflow, navigation accessible.

**CLS Detection:** Measure after navigation/data load. CLS > 0.1 = WARNING, > 0.25 = BLOCKING.

### Accessibility Testing (Tier 1 + Tier 3)
Component-level: axe-core, zero WCAG 2.2 AA violations, check alt text, labels, keyboard access, contrast, heading hierarchy.
Page-level: axe scan after page load.
Gate: WCAG A violations = BLOCKING, AA = WARNING, AAA = INFO.

### Tier 5 — Visual Regression (RECOMMENDED)
Screenshot at 3 viewports. Baseline mode (first run) or comparison (0.1% pixel diff threshold). Include all 4 states. WARNING only (never BLOCKING). Never auto-update baselines.

## Output Manifest
```json
{
  "phase": "{{PHASE}}", "agent": "ui_test_agent",
  "component_tests": { "total": 0, "passed": 0, "failed": 0 },
  "integration_tests": { "total": 0, "passed": 0, "failed": 0 },
  "e2e_tests": { "total": 0, "passed": 0, "failed": 0 },
  "coverage_pct": 0,
  "accessibility": { "components_scanned": 0, "pages_scanned": 0, "violations_a": 0, "violations_aa": 0 },
  "visual_regression": { "baselines_created": 0, "comparisons_run": 0, "diffs_detected": 0 },
  "unresolved_failures": []
}
```
