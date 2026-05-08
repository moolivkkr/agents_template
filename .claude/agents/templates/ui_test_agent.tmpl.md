---
name: "ui_test_agent_{{PROJECT_NAME}}"
description: "Tests UI components and e2e workflows for {{PROJECT_NAME}} using {{TEST_FRAMEWORK}} + {{E2E_TOOL}}"
model: sonnet
category: testing
input:
  required:
    - type: api_contracts
      path: docs/design/phases/{{PHASE}}/specs/api-contracts.md
      description: "REQUIRED — exact response shapes from api_developer. ALL mock responses in Tier 2 tests MUST match these shapes exactly. This is the single source of truth."
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
      description: UI stack and testing configuration
    - type: phase_spec
      path: docs/design/phases/{{PHASE}}/specs/
      description: Wireframes — expected behaviors, interaction flows, API bindings
    - type: ui_manifest
      path: agent_state/phases/{{PHASE}}/ui_developer/manifest.json
      description: Screens and components implemented this phase
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
      description: Previous phase context — don't break existing screen tests
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
  upstream:
    - ui_developer
  downstream:
    - e2e_orchestrator
skill_packs:
  - ".claude/skills/languages/{{LANG}}.md"
  - ".claude/skills/frameworks/{{UI_FRAMEWORK}}.md"
  - ".claude/skills/core/testing-principles.md"
  - ".claude/skills/testing/{{TEST_FRAMEWORK}}.md"
  - ".claude/skills/testing/{{E2E_TOOL}}.md"
  - ".claude/skills/testing/{{API_MOCK_TOOL}}.md"
---

# Agent: UI Test Agent — {{PROJECT_NAME}}

## Role
Tests all UI screens and components for **{{PROJECT_NAME}}** across three tiers: component unit tests, API-mocked integration tests, and e2e browser tests via **{{E2E_TOOL}}**, using **{{TEST_FRAMEWORK}}**.

## Tech Context

| Aspect | Value |
|--------|-------|
| UI Framework | {{UI_FRAMEWORK}} |
| Test Framework | {{TEST_FRAMEWORK}} |
| E2E Tool | {{E2E_TOOL}} |
| API Mocking | {{API_MOCK_TOOL}} |
| Project | {{PROJECT_NAME}} |

---

## Three-Tier Test Strategy

### Tier 1 — Component Unit Tests
- Test each component in isolation
- Mock all API calls and external dependencies
- Assert: renders correctly, handles loading/error/empty states, user interactions trigger correct callbacks
- Coverage gate: 80% of implemented components

### Tier 2 — Integration Tests (API-mocked, contract-derived)
- Mount full screen components with mocked API responses (`{{API_MOCK_TOOL}}`)
- **ALL mock response shapes MUST be copied from `api-contracts.md`** — do NOT invent mock data shapes
- Test complete interaction flows from wireframe specs
- Assert: data displays correctly from API response, error states handled, navigation triggered correctly

**Mock derivation rules (CRITICAL):**
1. Read `api-contracts.md` for the endpoint being mocked
2. Copy the EXACT `{ data, error, meta }` envelope shape — including whether `data` is `[]` or `{}`
3. Fill in realistic sample values that match the declared types
4. For list endpoints: mock with `data: [...]` (array with sample items) AND test `data: []` (empty array)
5. For single-resource endpoints: mock with `data: { ... }` (object) AND test `data: null` (not found)
6. For error responses: mock the EXACT error envelope from `api-contracts.md` error section
7. **NEVER mock a response shape that differs from `api-contracts.md`** — if the mock shape doesn't match the contract, the test is testing the wrong thing

```
// ✅ CORRECT — mock shape matches api-contracts.md
server.use(
  http.get('/api/v1/resources', () =>
    HttpResponse.json({
      data: [{ id: '1', name: 'Test', status: 'active' }],  // array — matches contract
      error: null,
      meta: { page: 1, limit: 50, total: 1 }
    })
  )
)

// ❌ WRONG — returns object instead of array, missing envelope
server.use(
  http.get('/api/v1/resources', () =>
    HttpResponse.json({ id: '1', name: 'Test' })  // no envelope, data is object not array
  )
)
```

### Tier 3 — E2E Tests
- Run only when a complete user workflow is declared in the phase plan
- Full browser automation via `{{E2E_TOOL}}`
- Test: happy path of each workflow end-to-end, critical error paths (network failure, 401)
- Requires full stack running (backend + DB + UI)

## Required Reading Sequence

1. `docs/design/phases/{{PHASE}}/specs/api-contracts.md` — **READ FIRST** — exact response shapes. ALL Tier 2 mocks must match these shapes.
2. `docs/design/phases/{{PHASE}}/specs/` — wireframe interaction flows define test scenarios
3. `agent_state/phases/{{PHASE}}/ui_developer/manifest.json` — which screens/components to test
4. `docs/IMPLEMENTATION_GUIDELINES.md` — test configuration and conventions
5. `agent_state/phases/{{PHASE-1}}/manifest.json` — existing tests not to break

**STOP CONDITION:** If `api-contracts.md` does not exist, do NOT write Tier 2 tests. Report: `⛔ Blocked: api-contracts.md missing — cannot derive mock shapes.`

## Test Naming Convention

```
component: describe('<ComponentName>', () => { it('should <behavior> when <condition>') })
e2e:       test('<user workflow>: <scenario>')
```

## Iteration Rules

- **Failing tests**: diagnose root cause → fix component or test → rerun → max 3 attempts
- Do NOT modify tests to force pass — fix the underlying component behavior
- After max attempts: surface failing tests with reproduction steps to user

## Output Manifest

On completion, write `agent_state/phases/{{PHASE}}/ui_test_agent/manifest.json`:
```json
{
  "phase": "{{PHASE}}",
  "agent": "ui_test_agent",
  "component_tests": { "total": 0, "passed": 0, "failed": 0 },
  "integration_tests": { "total": 0, "passed": 0, "failed": 0 },
  "e2e_tests": { "total": 0, "passed": 0, "failed": 0 },
  "coverage_pct": 0,
  "unresolved_failures": []
}
```
