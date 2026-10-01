# Test Case Generation — Exhaustive Enumeration for All Tiers

## Purpose

Specs must enumerate test cases for EVERY tier, not just list edge cases for unit tests: unit,
integration, security abuse cases, failure modes, E2E, UI, acceptance and performance. Otherwise the
TC ID system tracks IDs that were never generated in the first place.

`spec_writer` and `ux_designer` apply the matrices below during `/plan`. Every generated row goes into
the spec's inventory table, `| TC ID | Category | Description | Priority | Tier |`. IDs are allocated
with the project-unique numbering in `test-case-traceability.md` (`P·10000 + k·100 + i`). The
`{N+…}` offsets below are placeholders for that sequence.

Status codes and error codes follow the one envelope, `api/response-envelope.md`:
- 400 `VALIDATION_FAILED`
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`, also for another tenant's or owner's object
- 409 `CONFLICT`
- 422 `BUSINESS_RULE_VIOLATION`
- 429 `RATE_LIMITED`
- 503 `UNAVAILABLE`

---

## Tier 0: EARS-Derived Test Cases (spec_writer generates FIRST)

Before applying the per-tier matrices below, walk every EARS clause in the spec's requirements and
acceptance criteria. Each EARS clause deterministically yields **exactly one TC ID**. See
[../requirements/ears-notation.md](../requirements/ears-notation.md).

### The Deterministic Split

```text
WHEN <trigger>  THE SYSTEM SHALL <response>
     └─ precondition ─┘         └─ assertion ─┘

→ TC-<CAT>-<n>
    Precondition: <trigger>   (the WHEN / WHILE / IF / WHERE part)
    Assertion:    <response>  (the SHALL part)
```

For Ubiquitous clauses (no trigger) the precondition is the default/steady state.

### Worked Example

```text
FR-007:  WHEN an Admin submits the invite form with a valid email
         THE SYSTEM SHALL create a pending member and send an invite email within 5s.
FR-007b: IF the invite email is already registered
         THEN THE SYSTEM SHALL reject with 409 CONFLICT.

→ TC-API-20114: Given Admin POSTs valid invite → assert 201 + pending row + email < 5s
→ TC-API-20115: Given invite email already registered → assert 409 CONFLICT
```

### Rules

- **One EARS clause → one TC ID.** Reviewers verify by counting: clause count must equal the
  Tier-0 count.
- The Tier-0 row names the FR-*/NFR-* ID it derives from, so BRD traceability is direct.
- Tier 0 is the **floor**, not the ceiling. The per-tier matrices below still add the auth,
  validation, abuse, failure-mode and state variations a single EARS clause doesn't spell out. When a
  Tier-0 row is the same test as a matrix row, reuse the ID rather than duplicating it.
- Split compound requirements into one EARS clause each BEFORE mapping (see ears-notation.md). Never
  map a multi-SHALL sentence to one TC ID.
- **Expected values come from the spec.** Each row states the literal expected outcome: the status,
  the code, the number. Tests assert that literal. A test that derives its expected value from the
  implementation proves nothing.

---

## Tier 1: Unit Test Cases (spec_writer generates)

Minimum 10 per spec, from the edge-case taxonomy. For every function-level behaviour in the spec,
enumerate:

```text
TC-UNIT-{N+0}: happy path — the literal expected output from the spec
TC-UNIT-{N+1}: boundary — min, max, just outside (off-by-one) values
TC-UNIT-{N+2}: invalid input — the documented validation error
TC-UNIT-{N+3}: domain error — not found / conflict / invalid state transition
TC-UNIT-{N+4}: dependency error — the port returns timeout / connection refused / 503 →
               the mapped error, and the retry/breaker behaviour the spec states
```

Row `{N+4}` covers the resilience code (timeouts, retries, fallbacks). It is business logic, not
"infrastructure glue". Test it through the port interface with a fake that returns the error.

---

## Tier 2: Integration Test Cases (spec_writer generates)

### Per-Endpoint Matrix

```text
For endpoint: METHOD /api/v1/resource

TC-API-{N+0}: Happy path — valid request → documented status + envelope (data of the documented type, meta.request_id)
TC-API-{N+1}: Auth missing — no credentials → 401 UNAUTHENTICATED
TC-API-{N+2}: Validation — missing required field → 400 VALIDATION_FAILED, details[] names the field
TC-API-{N+3}: Validation — invalid format / out of range → 400 VALIDATION_FAILED with the field's code
TC-API-{N+4}: Not found — resource doesn't exist → 404 NOT_FOUND
TC-API-{N+5}: Response shape — no extra top-level keys; success has no "error", error has no "data"
TC-API-{N+6}: Empty state — list endpoint returns data: [] (never null) + meta.pagination
TC-API-{N+7}: Pagination — follow next_cursor → next page, no duplicates or gaps (list endpoints)
TC-API-{N+8}: Idempotency — POST replayed with the same Idempotency-Key → one side effect, same response
TC-API-{N+9}: Business rule — valid shape rejected by a domain rule → 422 BUSINESS_RULE_VIOLATION (where one exists)
```

Authorization, token and injection cases live in the **abuse-case matrix** (next section), as
`TC-SEC` rows.

### Per-DB-Entity Matrix

```text
For entity: ResourceName

TC-DB-{N+0}: Create → Read round-trip (all fields preserved, types exact)
TC-DB-{N+1}: Update → Read (changed fields updated, unchanged preserved)
TC-DB-{N+2}: Delete → Read (returns not found)
TC-DB-{N+3}: List with filter (correct subset returned)
TC-DB-{N+4}: Unique constraint violation (typed error, not 500)
TC-DB-{N+5}: Tenant filter (tenant2 query never returns tenant1 rows)
```

---

## Abuse cases

One matrix per endpoint, and per screen for the UI rows. The row names are the ones
`security/secure-coding.md` cites as each rule's **Proof**, so a coder reading a rule knows which test
will check it. Every applicable row becomes a `TC-SEC` inventory row, priority **HIGH**, with the row
name at the start of its description (`AUTHZ-OBJ: GET /orders/{id} of another user → 404`).

| Row | Applies to | What the test does and asserts | Tier (writer) |
|---|---|---|---|
| `AUTHZ-OBJ` | every endpoint taking an object ID (path, query, body, header) | user B, same tenant, sends user A's ID → **404 NOT_FOUND**, body reveals nothing of A's object; A's object is unchanged afterwards. Skip only where the spec says same-tenant users share the object. | integration |
| `AUTHZ-TENANT` | every endpoint taking an object ID, and every list / search / export / bulk endpoint | a tenant-2 token sends a tenant-1 ID → **404**; list/search/export as tenant 2 returns **no** tenant-1 rows (seed both tenants, assert by ID) | integration |
| `AUTHZ-FN` | every privileged operation (admin, role-gated) | lowest role that must not do it → **403 FORBIDDEN**; state unchanged | integration |
| `MASS-ASSIGN` | every create/update endpoint | body adds server-owned fields (`role`, `tenant_id`, `owner_id`, `is_admin`, price, status) → ignored (the read-back shows the server value) or **400**; never persisted | integration |
| `INJ` | every endpoint with string input that reaches a query, command, path or template | payload set: `' OR 1=1--`, `"; DROP TABLE x;--`, `$(id)`, `../../etc/passwd`, `%00`, `{{7*7}}` → 400 or stored inert and read back verbatim; **never 500**; no extra rows returned | integration |
| `SSRF` | every endpoint that fetches a user-supplied URL | `http://169.254.169.254/latest/meta-data/`, `http://127.0.0.1:<port>/`, `http://[::1]/`, a redirect to a private IP → rejected (400), no outbound request made (assert on the fake target) | integration |
| `UPLOAD` | every upload endpoint | oversized file → **413**/400; wrong content type or extension, polyglot (image header + script) → **400**; stored file is not served with an executable type | integration |
| `TOKEN-TAMPER` | every authenticated endpoint (one representative per auth mechanism) | signature byte flipped → **401**; `alg: none` → **401**; token signed with another key → **401**; wrong audience/issuer → **401** | integration |
| `TOKEN-EXPIRED` | same | expired token (`exp` in the past; use a fixed clock, not sleep) → **401 UNAUTHENTICATED** | integration |
| `RATE-LIMIT` | login, password reset, OTP, and any expensive or enumerable endpoint | N allowed attempts succeed or fail normally; attempt N+1 → **429 RATE_LIMITED** with `Retry-After` | integration |
| `SESSION-STORAGE` | every web screen after login | after sign-in and a page reload: `localStorage` and `sessionStorage` hold no token/JWT-shaped value; no token in any request URL or query string; session cookie is `HttpOnly`, `Secure`, `SameSite` | component (storage), e2e (cookie flags, URLs) |
| `XSS-RENDER` | every screen that renders user-controlled text, and every `href`/`src` built from user data | seed the field with `<img src=x onerror="window.__xss=1">` and `javascript:window.__xss=1` → rendered as text / link rejected; `window.__xss` stays undefined; no CSP violation event | component (render), e2e (stored → rendered page) |
| `CORS` | the API | preflight and request from a foreign `Origin` → no `Access-Control-Allow-Origin`, never `*` with credentials, never the reflected origin | integration |
| `ERR-LEAK` | the API (one forced-500 path, plus every documented error) | forced 500 → body is the envelope error with `request_id`; body contains no `stack`, `SELECT `, file paths, or upstream error text | integration |
| `SECRET-FAILCLOSED` | each service | start with `APP_ENV=qa` (and unset) and a required secret missing → process exits non-zero before serving; `APP_ENV=test` with the secret missing may start | integration (process-level test) |

- **Threat-model rows.** Every testable mitigation in
  `agent_state/phases/<P>/reports/threat_model.md` has a `TC-SEC` ID. `spec_writer` merges those rows
  into the phase inventory, with a tier and a priority (HIGH for any threat rated HIGH), so they are
  gated like any other row.
- **Fixed security findings.** A BLOCKING finding from `security_reviewer` that gets fixed also gets a
  `TC-SEC` row whose test fails before the fix and passes after (red first — `reproduction-first.md`).

---

## Failure modes

Every service dependency (DB, cache, queue, external API) gets these rows, category `TC-REL`,
priority MEDIUM unless an availability NFR makes them HIGH. They prove the timeouts, retries,
fallbacks and readiness behaviour the code claims.

| Row | What the test does and asserts | How to inject | Tier |
|---|---|---|---|
| `DEP-DOWN` | dependency unreachable → the documented error (usually **503 UNAVAILABLE**, `retryable: true`) within the request deadline, no hang; readiness reports not-ready if and only if the dependency is a hard one | stop/pause the container (`docker pause`, Testcontainers stop), or point at a closed port | integration |
| `DEP-SLOW` | dependency answers slower than the configured timeout → the call is cut at the timeout (assert elapsed ≤ timeout + margin), the documented error or fallback is returned | Toxiproxy `latency` toxic (Testcontainers Toxiproxy module: Go, Java, Node) | integration |
| `TIMEOUT` | an outbound call's timeout actually fires; retries happen only for idempotent operations (or with an `Idempotency-Key`), with the configured count and backoff | Toxiproxy `timeout` toxic, or a fake server that never answers; count requests at the fake | integration |
| `SOFT-DEP` | an optional dependency (cache) down → requests still succeed (degraded) and readiness stays ready | stop the cache container | integration |
| `RECOVERY` | dependency comes back → the service recovers without a restart (pool reconnects) | unpause the container, then assert a normal request succeeds | integration |
| `SIGTERM-DRAIN` | on SIGTERM the service stops accepting new work, finishes in-flight requests within the grace period and exits 0 | start the server as a process, send a slow request, send SIGTERM, assert the slow request completes and the process exits 0 | integration (process) · system (rollout under load on qa) |

A dependency being down during an integration test that is **not** one of these rows is still a
test result: report the failing tests with the error. Only a harness that cannot start at all (the
container runtime is missing) is an environment prerequisite error, and it is reported as `ERROR`,
never as a pass.

---

## Tier 3: E2E Test Cases (spec_writer generates)

E2E tests verify complete user workflows from start to finish. Enumerate them for EVERY user-facing
workflow in the phase's scope.

### Workflow Enumeration Algorithm

1. Read BRD personas and FR-* requirements in scope for this phase
2. For each persona, identify their primary workflows
3. For each workflow, enumerate the full path + error variations

### Per-Workflow Matrix

```text
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

```text
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

```text
For API: "Create and evaluate policy"

TC-E2E-{N+0}: Happy path — import → configure → call → verify return
TC-E2E-{N+1}: Error handling — invalid args → typed error (not panic)
TC-E2E-{N+2}: Concurrent usage — 10 goroutines/threads → no data races (run with the race detector)
TC-E2E-{N+3}: Configuration — all config options produce expected behavior
TC-E2E-{N+4}: Memory — process 1000 items → no memory leak
```

---

## Tier 4: UI Component Test Cases (ux_designer generates)

For EVERY screen/page in the wireframe, enumerate these IDs. The old weak spot was one row saying
"data state → correct content": tests then checked that a table rendered, not what was in it, and wrong,
swapped, unformatted or blank values shipped. The **per-element data matrix** below closes that: every
value a screen shows is its own row.

### Per-Element Data Matrix (TC-DATA) — one row per bound element

Start from the wireframe's API bindings (`api_bindings` / `data_source` / `contract_ref` in the structured
format, or the binding table in the markdown format). **Every element that displays API data is a data
element**: a table column, card field, detail field, badge, KPI tile, chart series, prefilled form
input, select option list, breadcrumb or heading built from data. For each one, write its display rule
in the wireframe (format, empty display, edge behaviour) and generate:

```text
For element: OrdersPage › table column "Total"  (binding: data[].total_cents, contract_ref Order.total_cents)

TC-DATA-{N+0}: Value — fixture total_cents=123456, currency USD → cell text is exactly "$1,234.56" in that row
TC-DATA-{N+1}: Empty/null — total_cents absent or null (if the contract allows it) → the defined placeholder ("—"), never "NaN", "undefined", "null", "$0.00" or a blank cell
TC-DATA-{N+2}: Edge — the element's edge values from the list below render per the display rule
```

Edge values to use, by type (pick the ones the type can carry):

| Type | Edge values the test feeds through the mock |
|---|---|
| text | the longest allowed value (truncates as specified; the full text stays reachable, e.g. title/tooltip); unicode, emoji, RTL; leading/trailing spaces; HTML-looking text (also `XSS-RENDER`) |
| number / money | 0, negative, the largest allowed; money in minor units with the currency's decimals (JPY 0, USD 2, KWD 3) |
| date / time | a fixed clock and a fixed locale + time zone in the test; a value across midnight in that zone; relative text ("2 hours ago") against the fixed clock |
| enum / status | every documented value → its exact label and badge variant; an **unknown** value from a newer server → the defined fallback, never a crash or blank |
| boolean | both values → the exact label or icon (with its accessible name) |
| list / count | 0, 1, many (and the plural form for 1 vs many) |
| link / image | the URL built from the bound id or field; a missing image → the defined fallback (initials, placeholder) |

Rules for these rows:
- **Swap-detecting fixtures.** Every field in a fixture has a distinct, recognisable value
  (`name: "Name-7f3a"`, `email: "email-7f3a@example.test"`, `total_cents: 123456`), never the same string
  or number in two fields. A column bound to the wrong field then fails instead of passing by accident.
- **Assert the exact text in its place.** Scope to the element (`within(row).getByRole("cell", …)`, the
  labelled detail field, the option list) and assert the exact formatted text. `toBeVisible()`,
  `toBeInTheDocument()` on a container, row counts or snapshots alone are not data assertions.
- Priority: **HIGH** for money, dates, status/permission badges and anything the user acts on; MEDIUM
  otherwise. One test may cover several elements of one row only if it asserts each one separately, and
  its name lists every TC-DATA ID it covers.

### Per-Page Matrix

```text
For page: PolicyListPage

TC-UI-{N+0}: Renders without crash (mount, no console errors)
TC-UI-{N+1}: Loading state — skeleton/spinner shown while API pending, and replaced by data (no flash of "empty")
TC-UI-{N+2}: Error state — API error → error message + retry; retry re-requests and then shows data
TC-UI-{N+3}: Empty state — `data: []` → empty state + CTA, and no table header/pager left over
TC-UI-{N+4}: Data state — the fixture's rows in the API's order, each row's elements per its TC-DATA rows
TC-UI-{N+5}: Pagination — "next" sends the cursor; exactly the next items appear (no duplicates or gaps); has_more=false hides "next"
TC-UI-{N+6}: Search/filter — the request carries the parameter; results replace the list; no-match → empty state; clearing restores; the state survives reload (URL)
TC-UI-{N+7}: Sort — each sortable column, both directions: the request carries sort + direction and the rendered order matches
TC-UI-{N+8}: Delete action — confirm → removed; cancel → unchanged; API error → item restored + error shown
TC-UI-{N+9}: Navigation — click item → the detail page for THAT item renders (its own field values)
TC-UI-{N+10}: Mutation reflected — after create/edit/delete, the list and detail show the new values without a manual reload
TC-UI-{N+11}: Responsive — renders correctly at 1280px (desktop): no horizontal scroll, no clipped data   [tier e2e]
TC-UI-{N+12}: Responsive — renders correctly at 375px (mobile): every data element still readable      [tier e2e]
TC-A11Y-{N+0}: axe scan of the rendered page, WCAG 2.2 AA tags — zero violations   [tier e2e]
TC-A11Y-{N+1}: keyboard — every interactive element reachable and operable, focus order logical, no trap   [tier e2e]
TC-A11Y-{N+2}: names — every control has a correct accessible name (component tier, by role)   [tier component]
```

Colour contrast can't be checked in a component test: jsdom has no layout, and `jest-axe` turns the
`color-contrast` rule off. Contrast belongs to the `e2e` tier (axe in a real browser) and to
`accessibility_auditor`.

### Per-Form Matrix

```text
For form: CreatePolicyForm

TC-FORM-{N+0}: All fields render with correct types (text, select, checkbox, etc.), labels and defaults
TC-FORM-{N+1}: Required field validation — submit empty → error on each required field, focus on the first
TC-FORM-{N+2}: Field-specific validation — every rule in the spec per field (format, min/max length, range, pattern), with the spec's message
TC-FORM-{N+3}: Server error mapping — API returns 400 VALIDATION_FAILED → each details[] entry on its own field; unknown field → form-level message
TC-FORM-{N+4}: Successful submit — the request body equals the expected payload exactly (types: numbers as numbers; omitted vs null as the contract says; trimmed text) → success feedback
TC-FORM-{N+5}: Dirty state — change field → navigate away → confirm dialog
TC-FORM-{N+6}: Reset/cancel — click cancel → form clears or navigates back
TC-FORM-{N+7}: Multi-step form — step 1 → step 2 → back → data preserved
TC-FORM-{N+8}: Disabled submit — button disabled while API in flight (no double-submit)
TC-FORM-{N+9}: Edit prefill — every field shows the existing record's value (selects, dates, checkboxes, multi-selects included); an unchanged submit sends no spurious changes
TC-FORM-{N+10}: Options from the API — each select/radio/autocomplete shows exactly the options the API returned (label and value), its empty state, and its load error
TC-FORM-{N+11}: Dependent fields — changing a controlling field updates, enables or clears the dependent ones as specified
```

### Per-Component Matrix (for reusable components)

```text
For component: DataTable

TC-COMP-{N+0}: Renders with provided data — every column shows its row's own value (swap-detecting fixture)
TC-COMP-{N+1}: Props variation — with/without pagination, sorting, selection
TC-COMP-{N+2}: Callback — row click fires onRowClick with correct item
TC-COMP-{N+3}: Selection — checkbox selects/deselects, bulk select works, selection clears on page change if specified
TC-A11Y-{N+0}: Table exposes proper roles and labels (component tier, by role)
```

Every screen that shows user-controlled text also gets the `XSS-RENDER` row, and the signed-in shell
gets `SESSION-STORAGE` (abuse-case matrix above).

---

## Tier 4M: Mobile Test Cases — React Native iOS + Android (ux_designer generates; only when mobile.enabled)

A web page matrix doesn't cover a native app: there is no DOM, and platform behaviour diverges.
For every mobile screen and every mobile workflow, enumerate the IDs below. Each device-tier ID
(`TC-ME2E`, `TC-MPLT`, `TC-MVIS`) is executed on BOTH platforms. The inventory row gives one ID, and
the results carry separate iOS and Android cases. Strategy: `mobile-testing-strategy.md`.

### Per-Mobile-Screen Matrix

```text
For screen: OrdersScreen   (testIDs: orders.list, orders.row.<id>, orders.refresh, orders.empty)

TC-MCMP-{N+0}: Renders without crash inside real providers
TC-MCMP-{N+1}: Loading state
TC-MCMP-{N+2}: Error state — API error → message + retry
TC-MCMP-{N+3}: Empty state — data: [] → empty copy + CTA
TC-MCMP-{N+4}: Data state — items render with correct content
TC-MCMP-{N+5}: Primary interaction (press row → detail screen rendered via real navigator)
TC-MCMP-{N+6}: Pull-to-refresh / end-reached pagination (if the screen has a list)
TC-MINT-{N+0}: Screen + MSW mock (typed from the envelope + api-contracts.md) → data displayed
TC-MINT-{N+1}: 401 mid-session → login → returns to this screen
TC-MINT-{N+2}: Network failure (HttpResponse.error) → offline/error state
TC-MA11Y-{N+0}: Every interactive element found by role + accessible name
TC-MA11Y-{N+1}: Touch targets ≥ 44pt / 48dp (device — mobile_platform_auditor)
TC-MA11Y-{N+2}: Largest text scale — nothing clipped, primary action reachable (device)
TC-MVIS-{N+0}: Final-state screenshot per device slot matches baseline
```

### Per-Mobile-Workflow Matrix

```text
For workflow: Place order (FR-012)

TC-ME2E-{N+0}: Happy path — launch → sign in → create → confirmation   [iOS + Android]
TC-ME2E-{N+1}: Validation error surfaces on the field                   [iOS + Android]
TC-ME2E-{N+2}: Server error → recoverable message                        [iOS + Android]
TC-ME2E-{N+3}: Kill mid-flow → relaunch → state/draft behaviour as spec'd [iOS + Android]
TC-ME2E-{N+4}: Android back / iOS swipe-back at each step → no data loss, no unexpected exit
```

### Per-App Platform Matrix (once per app, re-checked each phase that touches it)

```text
TC-MPLT-{N+0}: Cold start → first screen, no red screen / native crash
TC-MPLT-{N+1}: Auth persists across kill + relaunch (token in Keychain/Keystore)
TC-MPLT-{N+2}: Background → foreground preserves state; Android process death restores
TC-MPLT-{N+3..}: One per deep-link route × {cold, warm} × {logged-in, logged-out}
TC-MPLT-{..}:  One per requested permission × {granted, denied, permanently denied}
TC-MPLT-{..}:  Offline → offline state; reconnect → recovery
TC-MPLT-{..}:  Keyboard never hides the focused field or submit on the smallest device
TC-MPLT-{..}:  Push notification tap routes correctly from killed and background (if in scope)
TC-MPERF-{N+0}: Cold start median ≤ NFR-PERF target (per platform)
```

---

## Tier 5: Acceptance Test Cases (spec_writer generates)

Acceptance tests validate what the BRD promised, from each persona's perspective.
`acceptance_test_agent` implements them as **committed, runnable specs** under `tests/acceptance/`, each
named with its TC-ACC ID.

### One TC-ACC per FR acceptance criterion, per persona

Walk every in-scope FR's acceptance criteria. Each EARS SHALL, for each persona the FR names, is one
row. **Priority is HIGH for an FR marked MUST** (MoSCoW in the BRD), MEDIUM for SHOULD, LOW for COULD.

```text
FR-007 (MUST) — Manage policies — persona Admin
  SHALL 1: WHEN Admin saves a valid policy THE SYSTEM SHALL list it with status "active"
  SHALL 2: WHEN Admin deletes a policy THE SYSTEM SHALL ask for confirmation and then remove it

TC-ACC-{N+0}: FR-007 SHALL 1 — Admin saves a valid policy → listed as "active"        HIGH  acceptance
TC-ACC-{N+1}: FR-007 SHALL 2 — Admin deletes a policy → confirm → gone from the list   HIGH  acceptance
```

### Permission Boundary Rows (what each persona CANNOT do)

```text
TC-ACC-{N+2}: FR-007 — End User CANNOT create policies (403 / action absent and blocked server-side)
TC-ACC-{N+3}: FR-007 — Tenant-A admin CANNOT see Tenant-B's policies
```

### Cross-Persona and Lifecycle Rows

```text
TC-ACC-{N+4}: FR-007 → FR-011 — Admin creates policy → End User's view reflects it
TC-ACC-{N+5}: Policy lifecycle as Admin — create → list → view → edit → verify → delete → verify gone
```

---

## Tier 6: Performance Test Cases (spec_writer generates)

One `TC-PERF` row per NFR-PERF target in scope, priority **HIGH**, tier `performance`. The row names
the endpoint or flow, the **arrival rate**, the percentile and its limit, and the error-rate limit, as
the NFR states them. For example:

```text
TC-PERF-{N+0}: NFR-PERF-003 — GET /orders at 50 req/s: p95 < 300 ms, p99 < 800 ms, errors < 0.1 %
```

`performance_agent` turns each row into k6 thresholds on qa (`load-testing.md`). A target with no
rate ("p95 < 300 ms") is incomplete: flag it for the BRD, and don't invent a rate.

---

## Enumeration Checklist for spec_writer

Before finalizing the Test Case Inventory, verify:

- [ ] **Every EARS clause** has exactly one Tier-0 row
- [ ] **Every API endpoint** has the per-endpoint rows plus its applicable abuse-case rows
      (`AUTHZ-OBJ`, `AUTHZ-TENANT`, `AUTHZ-FN`, `MASS-ASSIGN`, `INJ`, `TOKEN-TAMPER`, `TOKEN-EXPIRED`, …)
- [ ] **Every DB entity** has at least 6 integration rows (CRUD + constraint + tenant filter)
- [ ] **Every service dependency** has its failure-mode rows (`DEP-DOWN`, `DEP-SLOW`, `TIMEOUT`, …)
- [ ] **Every user workflow** has at least 5 E2E rows (happy + validation + error + permission + persistence)
- [ ] **Every FR acceptance criterion** has one TC-ACC row per persona, priority from MoSCoW
- [ ] **Every NFR-PERF target** has one TC-PERF row with a rate
- [ ] **Every threat-model TC-SEC** is in the inventory with a tier and priority
- [ ] Every row has a literal expected outcome, a Priority and a Tier

## Enumeration Checklist for ux_designer

Before finalizing the wireframe, verify:

- [ ] **Every page** has at least 10 UI rows (render + 4 states + interactions + responsive) plus its TC-A11Y rows
- [ ] **Every form** has at least 8 FORM rows (fields + validation + submit + errors + dirty state + cancel)
- [ ] **Every reusable component** has at least 4 rows (render + props + callbacks + accessibility)
- [ ] **Every screen showing user text** has an `XSS-RENDER` row; the signed-in shell has `SESSION-STORAGE`
- [ ] **Navigation** has rows for every route transition
- [ ] **Mobile (if mobile.enabled):** every mobile screen has ≥ 14 IDs (7 TC-MCMP + 3 TC-MINT + 3 TC-MA11Y + 1 TC-MVIS), every mobile workflow ≥ 5 TC-ME2E, and the per-app TC-MPLT matrix covers every deep-link route and every requested permission
- [ ] **Mobile:** every screen spec lists the testID of each interactive element and assertion target (the testID contract in `mobile-testing-strategy.md` §4). A TC with no addressable element cannot be automated.

---

## Minimum Counts by Project Type

| Project Type | Unit | Integration | Security + failure modes | E2E | UI | Acceptance | Performance |
|---|---|---|---|---|---|---|---|
| Web API + UI | 10/spec | 10/endpoint + 6/entity | abuse rows per endpoint + failure rows per dependency | 5/workflow | 10/page + 8/form | 1 per FR criterion per persona + boundaries | 1 per NFR-PERF |
| CLI tool | 10/spec | 6/entity | INJ/path rows for file inputs + failure rows | 7/pipeline | N/A | 1 per FR criterion | 1 per NFR-PERF |
| Library/SDK | 10/spec | 6/entity | input-validation rows | 5/API-surface | N/A | 1 per consumer scenario | 1 per NFR-PERF |
| React Native mobile (add to the above) | — | — | SESSION-STORAGE (secure storage) | 5/workflow × 2 platforms | 14/screen + TC-MPLT matrix | device flows for RN-delivered FRs | cold start per platform |

---

## How Specs Reference This Skill

spec_writer and ux_designer load this skill pack and use the matrices above to generate the rows:

1. **spec_writer Phase 1:** Identify all API endpoints, DB entities, dependencies, user workflows, FR criteria and NFR-PERF targets in scope
2. **spec_writer Phase 2:** Apply the matrices → rows for unit, integration, abuse cases, failure modes, E2E, acceptance and performance
3. **ux_designer Phase 1:** Identify all pages, forms and reusable components
4. **ux_designer Phase 2:** Apply the page, form and component matrices → UI, FORM, COMP and A11Y rows
5. **Both:** Write every row into the inventory table with Priority and Tier
