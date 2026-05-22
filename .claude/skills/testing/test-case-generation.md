# Test Case Generation — Exhaustive Enumeration for All Tiers

## Purpose

Ensures that specs don't just list edge cases for unit tests — they systematically enumerate test cases for EVERY tier: unit, integration, E2E, UI component, and acceptance. Without this, the TC-* ID system tracks IDs that were never generated in the first place.

This skill defines enumeration patterns that spec_writer and ux_designer use to produce exhaustive test case inventories during `/plan`.

---

## Tier 1: Unit Test Cases (spec_writer generates)

Already covered by the edge-case-taxonomy. Minimum 10 edge cases per spec, each mapped to a TC-* ID.

---

## Tier 2: Integration Test Cases (spec_writer generates)

For EACH API endpoint in the spec, generate these TC-* IDs:

### Per-Endpoint Matrix

```
For endpoint: METHOD /api/v1/resource

TC-API-{N+0}: Happy path — valid request → correct status + response shape
TC-API-{N+1}: Auth missing — no token → 401
TC-API-{N+2}: Auth invalid — bad token → 401
TC-API-{N+3}: Auth expired — expired token → 401
TC-API-{N+4}: Forbidden — valid token, wrong role → 403
TC-API-{N+5}: Validation — missing required field → 422 with field error
TC-API-{N+6}: Validation — invalid field format → 422 with specific message
TC-API-{N+7}: Not found — valid request, resource doesn't exist → 404
TC-API-{N+8}: Cross-tenant — valid token, other tenant's resource → 404
TC-API-{N+9}: Response shape — verify envelope matches data-contracts.md exactly
TC-API-{N+10}: Empty state — list endpoint returns [] not null
```

### Per-DB-Entity Matrix

```
For entity: ResourceName

TC-DB-{N+0}: Create → Read round-trip (all fields preserved)
TC-DB-{N+1}: Update → Read (changed fields updated, unchanged preserved)
TC-DB-{N+2}: Delete → Read (returns not found)
TC-DB-{N+3}: List with filter (correct subset returned)
TC-DB-{N+4}: Unique constraint violation (typed error, not 500)
TC-DB-{N+5}: Tenant isolation (tenant2 cannot read tenant1's data)
```

---

## Tier 3: E2E Test Cases (spec_writer generates)

E2E tests verify complete user workflows from start to finish. Enumerate these for EVERY user-facing workflow defined in the BRD.

### Workflow Enumeration Algorithm

1. Read BRD personas and FR-* requirements in scope for this phase
2. For each persona, identify their primary workflows
3. For each workflow, enumerate the full path + error variations

### Per-Workflow Matrix

```
For workflow: "Admin creates a policy"

TC-E2E-{N+0}: Happy path — full workflow start to finish
  Steps: login as Admin → navigate to policies → create new → fill form → save → verify in list
TC-E2E-{N+1}: Form validation — submit with missing required fields → see errors → fix → succeed
TC-E2E-{N+2}: Duplicate — create policy with same name as existing → conflict error → user recovers
TC-E2E-{N+3}: Permission boundary — End User attempts this workflow → gets permission denied
TC-E2E-{N+4}: Error recovery — network failure mid-save → retry → succeeds
TC-E2E-{N+5}: Data persistence — create → refresh page → item still present
TC-E2E-{N+6}: Cross-feature — created item appears in other views (dashboard, reports)
```

### For CLI/Pipeline Products

```
For pipeline: "Compile DLP policy"

TC-E2E-{N+0}: Happy path — valid config → compile → output file correct
TC-E2E-{N+1}: Multi-step — compile → validate → deploy → verify
TC-E2E-{N+2}: Invalid input — malformed config → clear error message + exit code 1
TC-E2E-{N+3}: Missing dependency — config references undefined entity → error with location
TC-E2E-{N+4}: Large input — 100+ rules → compiles within timeout
TC-E2E-{N+5}: Idempotency — compile same input twice → same output
TC-E2E-{N+6}: Flag variations — each CLI flag combination produces expected behavior
```

### For Library/SDK Products

```
For API: "Create and evaluate policy"

TC-E2E-{N+0}: Happy path — import → configure → call → verify return
TC-E2E-{N+1}: Error handling — invalid args → typed error (not panic)
TC-E2E-{N+2}: Concurrent usage — 10 goroutines/threads → no data races
TC-E2E-{N+3}: Configuration — all config options produce expected behavior
TC-E2E-{N+4}: Memory — process 1000 items → no memory leak
```

---

## Tier 4: UI Component Test Cases (ux_designer generates)

For EVERY screen/page in the wireframe, enumerate these TC-* IDs:

### Per-Page Matrix

```
For page: PolicyListPage

TC-UI-{N+0}: Renders without crash (mount, no errors)
TC-UI-{N+1}: Loading state — skeleton/spinner shown while API pending
TC-UI-{N+2}: Error state — API error → error message + retry button
TC-UI-{N+3}: Empty state — no items → empty state illustration + CTA
TC-UI-{N+4}: Data state — items present → correct count, correct content
TC-UI-{N+5}: Pagination — next/prev/page number → correct items shown
TC-UI-{N+6}: Search/filter — type in search → results update
TC-UI-{N+7}: Sort — click column header → order changes
TC-UI-{N+8}: Delete action — click delete → confirm dialog → item removed
TC-UI-{N+9}: Navigation — click item → navigates to detail page
TC-UI-{N+10}: Responsive — renders correctly at 1280px (desktop)
TC-UI-{N+11}: Responsive — renders correctly at 375px (mobile)
TC-UI-{N+12}: Accessibility — keyboard navigation through all interactive elements
TC-UI-{N+13}: Accessibility — screen reader announces page title and item count
```

### Per-Form Matrix

```
For form: CreatePolicyForm

TC-FORM-{N+0}: All fields render with correct types (text, select, checkbox, etc.)
TC-FORM-{N+1}: Required field validation — submit empty → error on each required field
TC-FORM-{N+2}: Field-specific validation — email format, min/max length, pattern
TC-FORM-{N+3}: Server error mapping — API returns 422 → errors shown on correct fields
TC-FORM-{N+4}: Successful submit — valid data → API called with correct payload → success feedback
TC-FORM-{N+5}: Dirty state — change field → navigate away → confirm dialog
TC-FORM-{N+6}: Reset/cancel — click cancel → form clears or navigates back
TC-FORM-{N+7}: Multi-step form — step 1 → step 2 → back → data preserved
TC-FORM-{N+8}: Disabled submit — button disabled while API in flight (no double-submit)
```

### Per-Component Matrix (for reusable components)

```
For component: DataTable

TC-COMP-{N+0}: Renders with provided data
TC-COMP-{N+1}: Props variation — with/without pagination, sorting, selection
TC-COMP-{N+2}: Callback — row click fires onRowClick with correct item
TC-COMP-{N+3}: Selection — checkbox selects/deselects, bulk select works
TC-COMP-{N+4}: Accessibility — table has proper ARIA roles and labels
```

---

## Tier 5: Acceptance Test Cases (spec_writer generates)

Acceptance tests validate that the system delivers what the BRD promised, from each persona's perspective.

### Persona x Capability Matrix

For EVERY persona in the BRD and EVERY FR-* in scope, generate a test case:

```
For persona: Admin User
For capability: FR-007 (Manage policies)

TC-ACC-{N+0}: Admin can create a new policy (happy path)
TC-ACC-{N+1}: Admin can view the policy list (sees all tenants' policies if super-admin, own tenant only if tenant-admin)
TC-ACC-{N+2}: Admin can edit an existing policy
TC-ACC-{N+3}: Admin can delete a policy (with confirmation)
TC-ACC-{N+4}: Admin sees correct count in dashboard after CRUD operations
```

### Permission Boundary Matrix (CRITICAL — test what each persona CANNOT do)

```
TC-ACC-{N+5}: End User CANNOT create policies (gets permission denied)
TC-ACC-{N+6}: End User CANNOT delete policies
TC-ACC-{N+7}: Viewer CANNOT edit policies
TC-ACC-{N+8}: Tenant-A admin CANNOT see Tenant-B's policies
```

### Cross-Persona Flow Matrix

```
TC-ACC-{N+9}: Admin creates policy → End User sees it in their view
TC-ACC-{N+10}: Admin disables policy → End User's behavior changes accordingly
TC-ACC-{N+11}: End User triggers alert → Admin sees it in dashboard
```

### Data Lifecycle Matrix

For each major entity, verify the full lifecycle as the primary persona:

```
TC-ACC-{N+12}: Create → List (appears) → View (all fields) → Edit → Verify edit → Delete → Verify gone
```

---

## Enumeration Checklist for spec_writer

Before finalizing the Test Case Inventory, verify:

- [ ] **Every API endpoint** has at least 10 integration TC-* IDs (happy + auth + validation + IDOR + shape)
- [ ] **Every DB entity** has at least 6 integration TC-* IDs (CRUD + constraint + isolation)
- [ ] **Every user workflow** has at least 5 E2E TC-* IDs (happy + validation + error + permission + persistence)
- [ ] **Every FR-* in scope** has at least 1 acceptance TC-* ID per persona that uses it
- [ ] **Permission boundaries** have negative test TC-* IDs (each persona tested for what they CANNOT do)
- [ ] **Cross-persona flows** have TC-* IDs for every interaction between personas

## Enumeration Checklist for ux_designer

Before finalizing the wireframe, verify:

- [ ] **Every page** has at least 10 UI TC-* IDs (render + 4 states + interactions + responsive + accessibility)
- [ ] **Every form** has at least 8 UI TC-* IDs (fields + validation + submit + errors + dirty state + cancel)
- [ ] **Every reusable component** has at least 4 UI TC-* IDs (render + props + callbacks + accessibility)
- [ ] **Navigation** has TC-* IDs for every route transition

---

## Minimum TC-* ID Counts by Project Type

| Project Type | Unit | Integration | E2E | UI | Acceptance | Total Min |
|---|---|---|---|---|---|---|
| Web API + UI | 10/spec | 10/endpoint + 6/entity | 5/workflow | 10/page + 8/form | 5/persona-FR | ~100+ per phase |
| CLI tool | 10/spec | 6/entity | 7/pipeline | N/A | 3/use-case | ~50+ per phase |
| Library/SDK | 10/spec | 6/entity | 5/API-surface | N/A | 3/consumer-scenario | ~40+ per phase |
| Full-stack SaaS | 10/spec | 10/endpoint + 6/entity | 7/workflow | 13/page + 9/form | 5/persona-FR | ~150+ per phase |

---

## How Specs Reference This Skill

spec_writer and ux_designer load this skill pack and use the matrices above to systematically generate TC-* IDs for their output. The process is:

1. **spec_writer Phase 1:** Identify all API endpoints, DB entities, and user workflows in scope
2. **spec_writer Phase 2:** Apply per-endpoint, per-entity, per-workflow matrices → generate TC-* IDs for unit + integration + E2E + acceptance tiers
3. **ux_designer Phase 1:** Identify all pages, forms, and reusable components
4. **ux_designer Phase 2:** Apply per-page, per-form, per-component matrices → generate TC-* IDs for UI tier
5. **Both:** Write the TC-* IDs into the "Test Case Inventory" table with priority and tier
