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
  - ".claude/skills/infrastructure/saas-tenancy-models.md"
  - ".claude/skills/testing/test-case-traceability.md"
---

# Agent: UI Test Agent — {{PROJECT_NAME}}

## Role
Tests all UI screens and components for **{{PROJECT_NAME}}** across five tiers: component unit tests, API-mocked integration tests, e2e browser tests, responsive regression, and visual regression via **{{E2E_TOOL}}**, using **{{TEST_FRAMEWORK}}**.

## Tech Context

| Aspect | Value |
|--------|-------|
| UI Framework | {{UI_FRAMEWORK}} |
| Test Framework | {{TEST_FRAMEWORK}} |
| E2E Tool | {{E2E_TOOL}} |
| API Mocking | {{API_MOCK_TOOL}} |
| Project | {{PROJECT_NAME}} |

---

## Five-Tier Test Strategy

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

### Tier 4 — Responsive Regression Tests (MANDATORY for all UI components)

Every component with responsive behavior must be tested at 3 viewports:
- Mobile: 375px width (iPhone SE)
- Tablet: 768px width (iPad)
- Desktop: 1280px width

**Checks per viewport:**
1. No horizontal overflow (document.body.scrollWidth <= viewport width)
2. Touch targets >= 44x44px on mobile (measure computed button/link sizes)
3. Text doesn't truncate unless intentionally designed with ellipsis
4. Grid/flex layouts reflow correctly (1-column on mobile, multi on desktop)
5. Navigation is accessible (hamburger menu on mobile, sidebar on desktop)

**Implementation:**
```typescript
const viewports = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
];

for (const vp of viewports) {
  test(`renders correctly at ${vp.name} (${vp.width}px)`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/path');
    // No horizontal overflow
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(vp.width);
    // Touch targets on mobile
    if (vp.name === 'mobile') {
      const buttons = await page.locator('button, a, [role="button"]').all();
      for (const btn of buttons) {
        const box = await btn.boundingBox();
        if (box) expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(44);
      }
    }
  });
}
```

Responsive tests are NOT optional. Skip only if component has no visual output (utility hooks, context providers).

### Core Web Vitals — Layout Shift Detection

After every page navigation or data load, measure Cumulative Layout Shift:

```typescript
test('page has acceptable CLS', async ({ page }) => {
  // Navigate and wait for data
  await page.goto('/users');
  await page.waitForLoadState('networkidle');

  // Measure CLS
  const cls = await page.evaluate(() => {
    return new Promise<number>((resolve) => {
      let clsValue = 0;
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value;
          }
        }
      });
      observer.observe({ type: 'layout-shift', buffered: true });
      setTimeout(() => { observer.disconnect(); resolve(clsValue); }, 3000);
    });
  });

  expect(cls).toBeLessThan(0.1); // Good CLS score
});
```

CLS > 0.1 = WARNING, CLS > 0.25 = BLOCKING (skeleton doesn't match content layout).

### Accessibility Automated Testing (within Tier 1 + Tier 3)

**Tier 1 addition — Component-level a11y:**
For each component test file, add accessibility assertions:
1. Run axe-core (or equivalent) on the rendered component
2. Assert zero violations at WCAG 2.2 AA level
3. Specifically check:
   - All images have alt text
   - All form inputs have associated labels
   - All interactive elements are keyboard accessible
   - Color contrast ratios meet 4.5:1 (normal text) / 3:1 (large text)
   - No duplicate IDs
   - Heading hierarchy is sequential (no h1 → h3 skip)

**Implementation pattern:**
```typescript
import { axe, toHaveNoViolations } from 'jest-axe'; // or @axe-core/playwright

expect.extend(toHaveNoViolations);

it('should have no accessibility violations', async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

**Tier 3 addition — Page-level a11y:**
For each E2E test, add a11y scan after page load:
```typescript
import { injectAxe, checkA11y } from '@axe-core/playwright';

test('page meets WCAG 2.2 AA', async ({ page }) => {
  await page.goto('/dashboard');
  await injectAxe(page);
  await checkA11y(page, null, {
    detailedReport: true,
    rules: { 'color-contrast': { enabled: true } }
  });
});
```

**Gate impact:**
- WCAG A violations: BLOCKING (critical a11y failure)
- WCAG AA violations: WARNING (should fix, not blocking for MVP)
- WCAG AAA violations: INFO (aspirational)

**Output:** Add to manifest:
```json
"accessibility": {
  "components_scanned": N,
  "pages_scanned": N,
  "violations_a": 0,
  "violations_aa": N,
  "violations_aaa": N
}
```

### Tier 5 — Visual Regression Tests (RECOMMENDED)

**Purpose:** Detect unintended visual changes between implementations.

**When to run:** After Tier 1-4 pass. Skip on first phase with UI (no baseline exists).

**Implementation:**
1. For each page archetype implemented in this phase:
   a. Navigate to the page with populated test data
   b. Capture screenshot at 3 viewports: mobile (375px), tablet (768px), desktop (1280px)
   c. Save to `tests/visual-regression/baseline/<page>-<viewport>.png`

2. **Baseline mode (first run / no existing baseline):**
   - Capture screenshots as new baselines
   - Log: "Visual baseline created for <page> at <viewport>"
   - No comparison — all PASS

3. **Comparison mode (baseline exists):**
   - Capture current screenshots
   - Compare against baseline using pixel diff (threshold: 0.1% pixel difference tolerance)
   - If diff > threshold:
     - Save diff image to `tests/visual-regression/diff/<page>-<viewport>-diff.png`
     - Mark as WARNING (not BLOCKING — visual changes may be intentional)
     - Surface: "⚠ Visual change detected: <page> at <viewport> — X.X% pixel diff"
   - If diff ≤ threshold: PASS

4. **Baseline update:**
   - If visual changes are intentional (confirmed by implementation context):
     - Update baseline: copy current → baseline
     - Log: "Visual baseline updated for <page>"
   - Do NOT auto-update baselines — require explicit confirmation

5. **4-state visual testing:**
   - Capture screenshots for ALL 4 states (loading, empty, error, populated)
   - Each state is a separate baseline image
   - Ensures skeleton screens, empty states, and error states don't regress

**Output:** Add to manifest:
```json
"visual_regression": {
  "baselines_created": N,
  "comparisons_run": N,
  "diffs_detected": N,
  "pages_tested": ["dashboard", "user-list", "user-detail"]
}
```

**Gate impact:** WARNING only (visual changes may be intentional). Never BLOCKING.

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
  "accessibility": {
    "components_scanned": 0,
    "pages_scanned": 0,
    "violations_a": 0,
    "violations_aa": 0,
    "violations_aaa": 0
  },
  "visual_regression": {
    "baselines_created": 0,
    "comparisons_run": 0,
    "diffs_detected": 0,
    "pages_tested": []
  },
  "unresolved_failures": []
}
```
