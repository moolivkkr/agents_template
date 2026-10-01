# Test Case ID Traceability — Spec-to-Test Inventory Enforcement

> Code samples compile-checked: the UI test example (TypeScript): type-checked, and its 2 tests ran in Vitest 5.0.3 + MSW 3.0.1 + jsdom (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Purpose

Every test case a spec defines must exist as a test that **ran and passed**. Without that, a spec can
define 153 cases, 34 get written, and the phase gate still passes.

Coverage is computed by `.claude/hooks/tc-inventory.py`, never by grep:
- an ID counts only when it is in the **name** of a test case that is not skipped;
- with `--results`, only when that test also **ran and passed** in a runner-produced sidecar
  (`testing/test-results-sidecar.md`).

A comment, a TODO, a skipped test, a range ("TC-E-106 to TC-E-115") or an ID reused from another phase
covers nothing. The board review of 2026-09-30 reproduced every one of those passing the old grep
inventory (TEST-02, DEV-13, TEST-17).

---

## TC ID format

```text
TC-<CATEGORY>-<NUMBER>
```

- `CATEGORY` is one uppercase alphanumeric segment, 1–6 characters (`API`, `E2E`, `A11Y`, `ME2E`).
  No inner hyphen: `TC-SEC-REG-001` is not an ID. Use a category instead (`TC-SECREG-…`).
- `NUMBER` is decimal and **unique across the whole project** for that category (next section).
- Scanners match `TC[-_]<CATEGORY>[-_]<NUMBER>`. The `_` form exists only for names that can't hold
  `-` (Python function names, some JVM method names): `test_TC_API_20101_creates_order`.

### Numbering: project-unique, collision-free for parallel spec writers

`/plan` runs one `spec_writer` per component in parallel, so "take the next free number" races. The
number encodes who allocated it instead:

```text
NUMBER = P·10000 + k·100 + i
  P = phase number        k = the component's position in PHASE_PLAN.md's component list (01–99;
                              00 = the phase's threat model / cross-cutting security rows)
  i = sequence within that component and category (01–99)
```

Example: phase 2, third component, 14th API case → `TC-API-20314`. Phase 1's first component's first
unit case → `TC-UNIT-10101`.

- No two phases or components can produce the same number, so no coordination is needed.
- A component that needs more than 99 IDs in one category continues in the first spare index after
  the last component (count + 1, + 2, …) and says so in its spec header.
- IDs written before this scheme (`TC-API-001`) keep their numbers. They can't collide with the new
  five-digit-plus numbers.
- `tc-inventory.py` flags any ID defined by more than one phase (`duplicate_ids`), and those fail the
  inventory. `spec_verifier` checks uniqueness within a phase.

### Categories

| Code | Category | Tier (usual) |
|------|----------|--------------|
| `UNIT` | Unit behaviour (domain logic, validation, mapping) | unit |
| `E` / `ENT` | Entity/model rules | unit |
| `API` | API endpoint behaviour (status, envelope, validation) | integration |
| `DB` | Persistence, constraints, tenant filter | integration |
| `SEC` | Security: abuse-case matrix rows and threat-model tests | integration, component, e2e |
| `REL` | Failure modes: dependency down/slow, timeouts, drain | integration, system |
| `E2E` | End-to-end workflow | e2e |
| `UI` | UI component / page behaviour | component |
| `DATA` | **UI data element**: one bound value (column, field, badge, KPI, prefilled input, option list) rendered exactly as specified, including empty and edge values | component (round trip: e2e) |
| `FORM` | Form behaviour | component |
| `COMP` | Reusable component | component |
| `A11Y` | **Accessibility** (axe, keyboard, focus, names) | component, e2e |
| `ACC` | **Acceptance**: one FR acceptance criterion as a persona | acceptance |
| `PERF` | Performance: one NFR-PERF target measured under load | performance |
| `SYS` | Whole-system checks on the deployed environment | system |
| `MCMP` / `MINT` | Mobile component / integration (Jest + RNTL + MSW) | mobile |
| `ME2E` / `MPLT` / `MVIS` / `MPERF` | Mobile device flows, platform behaviour, visual, performance | device |
| `MA11Y` | Mobile accessibility | mobile, device |
| `PIPE` / `COMP` / `WASM` | CLI pipelines, compilers, WASM parity | e2e |

`TC-ACC` always means **acceptance**. Accessibility is `TC-A11Y` (web) and `TC-MA11Y` (mobile).
Before 2026-09-30 one skill used `TC-ACC` for accessibility; any spec still doing that is a bug to fix.

Projects may add categories. A category code is unique within the project.

### Tiers and owners

The inventory's **Tier** column tells each test agent which rows are its own:

| Tier | Written by | Run (evidence) by | Sidecar |
|------|-----------|-------------------|---------|
| `unit` | unit_test_agent | unit_test_agent, re-run by test_runner | `unit_tests.json` |
| `integration` | integration_test_agent | integration_test_agent, test_runner | `integration_tests.json` |
| `component` | ui_test_agent (Part A) | ui_test_agent, test_runner | `ui_test_results.json` |
| `e2e` | ui_test_agent (Part B, web) · e2e_orchestrator (CLI/pipeline) | e2e_orchestrator, test_runner | `e2e_results.json` |
| `acceptance` | acceptance_test_agent | acceptance_test_agent | `acceptance_report.json` |
| `performance` | performance_agent | performance_agent | `performance_results.json` |
| `mobile` | mobile_test_agent | mobile_test_agent, test_runner | `mobile_test_results.json` |
| `device` | mobile_test_agent | mobile_e2e_orchestrator (iOS + Android) | `mobile_e2e_results.json` |
| `system` | system_test_agent | system_test_agent | `system_test_results.json` |
| `manual` | manual_test_agent | a human | none — so **LOW priority only** |

HIGH and MEDIUM rows must be automatable. Something only a human can judge goes to `manual` at LOW
priority, alongside an automated HIGH/MEDIUM row for the part a machine can check.

---

## How specs define the inventory

Every spec's **Test Coverage Required** section has one inventory table. `tc-inventory.py` reads every
markdown table under `docs/design/phases/<P>/` whose row has a TC ID cell. It takes the `Priority`
and `Tier` columns by header name. A priority other than HIGH/MEDIUM/LOW counts as MEDIUM, which is
blocking.

<!-- BEGIN example-inventory -->
| TC ID | Category | Description | Priority | Tier |
|-------|----------|-------------|----------|------|
| TC-UNIT-20101 | UNIT | order total = sum of line totals, in integer cents | HIGH | unit |
| TC-UNIT-20102 | UNIT | a line with quantity 0 is rejected with VALIDATION_FAILED | HIGH | unit |
| TC-API-20101 | API | POST /orders valid body → 201, envelope data object + meta.request_id | HIGH | integration |
| TC-API-20102 | API | POST /orders without a token → 401 UNAUTHENTICATED | HIGH | integration |
| TC-SEC-20101 | SEC | AUTHZ-OBJ: GET /orders/{id} of another user in the same tenant → 404 | HIGH | integration |
| TC-SEC-20102 | SEC | XSS-RENDER: a stored `<img src=x onerror=…>` note renders as text | HIGH | component |
| TC-REL-20101 | REL | DEP-DOWN: DB unavailable → 503 UNAVAILABLE within the request deadline | MEDIUM | integration |
| TC-E2E-20101 | E2E | buyer places an order and sees it in Order history | HIGH | e2e |
| TC-ACC-20101 | ACC | FR-012 SHALL 1 — as Buyer, a placed order appears with status "open" | HIGH | acceptance |
| TC-PERF-20101 | PERF | NFR-PERF-003: GET /orders p95 < 300 ms at 50 req/s | HIGH | performance |
| TC-A11Y-20101 | A11Y | order form: every input has a programmatic label (axe, WCAG 2.2 AA) | MEDIUM | e2e |
| TC-UI-20107 | UI | order list shows a skeleton while loading | LOW | component |
<!-- END example-inventory -->

- **One ID per row, every row listed.** Don't write ranges ("TC-E-106 to TC-E-115"): the middle IDs
  never enter the inventory, and a range annotation in a test file fails the inventory.
- **Only the inventory table holds bare IDs.** `tc-inventory.py` reads any table cell that is exactly
  an ID, and the first occurrence wins. Other tables (EARS criteria, edge cases) reference IDs with a
  prefix, `→ TC-API-20301`, so they aren't read as a second, priority-less row.
- **Priority:** HIGH = core behaviour, security, data integrity; MEDIUM = standard behaviour and error
  handling; LOW = cosmetic and nice-to-have. HIGH and MEDIUM block the gate; LOW is reported.
- **Out of scope for this phase?** Don't list the row here. List it in the target phase's spec, and
  name it under `### Deferred` in this one, as prose rather than a table row.

`python3 .claude/hooks/tc-inventory.py --phase <P> --spec-only --out <file>` prints the phase's ID
count and writes `{id: priority}`. The orchestrator runs it in Wave 0c to produce
`tc_priorities.json`, which the results converters use.

---

## How tests carry TC IDs: in the test NAME

The ID goes where the **runner reports it**: the test title, subtest name, parametrize id or flow name.
JUnit carries names, so the sidecar and the inventory can match the ID to a result. Comments never
count.

| Stack | Where the ID goes | Example |
|---|---|---|
| Go | `t.Run` name, or the `name:` field of a table-driven case | `{name: "TC-UNIT-20101 total is the sum of lines", …}` |
| Jest / Vitest / Playwright | `it` / `test` title | `it('TC-UI-20107 shows a skeleton while loading', …)` |
| pytest | function name with `_` separators, or parametrize `id=` / `ids=` | `pytest.param(…, id="TC-API-20102")` |
| JUnit 5 / Kotlin | `@DisplayName` or the method name | `@DisplayName("TC-API-20101 creates an order")` |
| Rust | test function name, upper-case ID (scanners are case-sensitive) | `#[test] #[allow(non_snake_case)] fn TC_UNIT_20101_total_is_sum()` |
| Maestro | the **flow file name** starts with the ID | `.maestro/TC-ME2E-20101-login.yaml` |
| Detox / Appium | `it` title | `it('TC-ME2E-20101 signs in', …)` |

<!-- BEGIN example-tests-go -->
> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1 (tests/archetype-compile/go/run.sh).

```go
func TestOrderTotal(t *testing.T) {
	tests := []struct {
		name    string
		lines   []Line
		want    int64
		wantErr error
	}{
		{name: "TC-UNIT-20101 total is the sum of line totals", lines: []Line{{Qty: 2, UnitCents: 1250}, {Qty: 1, UnitCents: 99}}, want: 2599},
		{name: "TC-UNIT-20102 zero quantity is rejected", lines: []Line{{Qty: 0, UnitCents: 1250}}, wantErr: ErrValidation},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := OrderTotal(tt.lines)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("err = %v, want %v", err, tt.wantErr)
			}
			if got != tt.want {
				t.Fatalf("total = %d, want %d", got, tt.want)
			}
		})
	}
}
```
<!-- END example-tests-go -->

<!-- BEGIN example-tests-ts -->
```typescript
describe('OrderList', () => {
  it('TC-UI-20107 shows a skeleton while loading', async () => {
    renderWithProviders(<OrderList />)   // QueryClientProvider, retries off (msw.md)
    expect(screen.getByTestId('orders.skeleton')).toBeVisible()
  })
  it('TC-SEC-20102 renders a stored script payload as text', async () => {
    server.use(ordersHandler([order({ note: '<img src=x onerror="window.__xss=1">' })]))
    renderWithProviders(<OrderList />)
    expect(await screen.findByText('<img src=x onerror="window.__xss=1">')).toBeVisible()
    expect((window as any).__xss).toBeUndefined()
  })
})
```
<!-- END example-tests-ts -->

<!-- BEGIN example-tests-py -->
```python
@pytest.mark.parametrize("token,status", [
    pytest.param(None, 401, id="TC-API-20102 missing token"),
])
def test_create_order_auth(client, token, status):
    assert client.post("/orders", json=VALID_ORDER, headers=auth(token)).status_code == status


def test_TC_SEC_20101_other_users_order_is_not_found(client, alice, bob_order):
    assert client.get(f"/orders/{bob_order.id}", headers=auth(alice)).status_code == 404
```
<!-- END example-tests-py -->

### Naming rules

1. **Every test case carries exactly the IDs it proves, in its name.** A table-driven test has one ID
   per row. A test may carry two IDs only when one assertion genuinely proves both.
2. **Never an ID in a skipped, `.only`, `todo` or `fixme` test.** Skipped tests don't count, and
   `.only` silences its siblings.
3. **Never an ID from another phase** for new behaviour. Allocate a new one (see Numbering). Earlier
   phases' tests keep their own IDs, and their suites keep running as regression.
4. **Describe the behaviour after the ID** (`TC-API-20102 missing token → 401`), so a failing name
   reads as the broken requirement.

---

## Computing the inventory

```bash
P="${PHASE:?}"
# Source mode (while writing tests): does a non-skipped test NAMED with each ID exist?
python3 .claude/hooks/tc-inventory.py --phase "$P" --out /tmp/tc_source.json
# Results mode (the evidence): did that test run and PASS? Pass every runner sidecar that exists.
SIDECARS=()
for s in test_results e2e_results mobile_e2e_results acceptance_report performance_results system_test_results; do
  if [ -f "agent_state/phases/$P/reports/$s.json" ]; then SIDECARS+=("agent_state/phases/$P/reports/$s.json"); fi
done
# No sidecar would quietly turn this into source mode (no proof anything ran), and an empty
# --diff-base makes tc-inventory skip the test-weakening check: either one stops here.
[ ${#SIDECARS[@]} -gt 0 ] || { echo "⛔ no runner sidecars in agent_state/phases/$P/reports"; exit 1; }
BASE="$(cat "agent_state/phases/$P/base_sha" 2>/dev/null)"
[ -n "$BASE" ] || { echo "⛔ no agent_state/phases/$P/base_sha"; exit 1; }
python3 .claude/hooks/tc-inventory.py --phase "$P" \
  --results "${SIDECARS[@]}" \
  --diff-base "$BASE" \
  --out "agent_state/reconciliation/phase-$P/specs_vs_tests.json"
```

The output is an `sdlc.test-results/v1` sidecar (`tier: tc-inventory`). It FAILs on any of:
- a HIGH/MEDIUM ID that is missing, failing, skipped-only or comment-only;
- an ID that another phase also defines;
- a range annotation in a test file;
- unacknowledged **test weakening** since the phase's base commit: a removed assertion line, a new
  skip or `.only`, or a deleted test file.

### Changing an existing test: TEST-CHANGE comments (why and when)

A test that existed before this phase changes only for a reason you can name, and that reason goes
into the test, on one line directly above the change, in the file's comment syntax:

```go
// TEST-CHANGE 2026-09-30 phase 3: totals now include tax per the revised pricing rule (spec: FR-012)
if Total(order) != 107 { t.Fatalf("want 107, got %d", Total(order)) }
```
```python
# TEST-CHANGE 2026-09-30 phase 3: envelope checks moved into a shared helper, same assertions (moved: tests/helpers.py:40)
assert_order_envelope(resp)
```

- **When:** the date you made the change (`YYYY-MM-DD`), and the current phase number.
- **Why:** why the NEW expectation is right. "Test was failing", "fix test" and "make it pass" are not
  reasons.
- **A changed or removed assertion** must cite `spec:` (the FR-/NFR-/TC- ID or spec path:line that
  changed the behaviour) or `moved:` (where the same check lives now). The comment goes within 3 lines
  of the change. One comment per changed spot, not one per file.
- **A new skip or `.only`** needs a comment within 3 lines. A skip is still not a quarantine
  (`test-results-sidecar.md` §Flakes).
- **Any other edit** to a pre-existing test (a selector, setup, fixture data) needs at least one
  TEST-CHANGE comment in that file.
- **Nothing needed:** formatting-only changes, and tests created in this phase.
- **A deleted test file** has nowhere to comment. Add `{"file": ..., "kind": "deleted_test_file",
  "reason": ...}` to `agent_state/phases/<P>/test-changes.json`. Baseline images and `.snap` files are
  recorded there too, with their approval reference.

Who may change an existing test:
- **Coders** (backend, API, UI, mobile developers) only when this phase's spec changed the behaviour
  the test asserts, so `spec:` is mandatory. A coder never deletes, skips or loosens a test.
- **Test agents** fix a test that is wrong (a selector, setup, or an expectation that contradicts the
  spec), never to match buggy behaviour.

`tc-inventory.py --diff-base` enforces this: each unacknowledged change is a `weakening_unacknowledged`
entry, which fails `specs_vs_tests.json` and the gate. Valid comments are listed in `test_changes`
(the why-and-when ledger that `spec_test_reconciler` copies into its report); malformed ones (bad date,
another phase, no real reason) are listed in `test_change_invalid` and acknowledge nothing.

`spec_test_reconciler` runs this in Wave 4 and again in Wave 5v, and writes
`specs_vs_tests.md` around the JSON. `/test --traceability` runs it standalone.

---

## Gate rules

| Item | Pass condition |
|------|----------------|
| TC inventory (`specs_vs_tests.json`) | verdict PASS: every HIGH+MEDIUM ID ran and passed; no duplicates, ranges or unacknowledged weakening |
| Each tier sidecar | verdict PASS; no HIGH/MEDIUM case FAIL/BLOCKED/UNTESTED/FLAKY (`test-results-sidecar.md`) |
| LOW IDs | reported as known gaps; non-blocking |

`/accept` runs the inventory for every completed phase. Each phase's IDs must still pass there, which
is how a later phase's change to an earlier phase's behaviour is caught.

---

## Agent responsibilities

| Agent | Responsibility |
|-------|---------------|
| `spec_writer` | Allocates project-unique IDs (Numbering), fills the inventory table with Priority and Tier, merges threat-model `TC-SEC` rows, one `TC-ACC` per FR acceptance criterion |
| `ux_designer` | UI, FORM, COMP, A11Y and mobile rows for the screens it specifies |
| Each test agent | Writes a named test for every row of its tier, runs it, and produces its sidecar |
| `test_runner` | Re-runs every tier; its sidecars are what the inventory reads |
| `spec_test_reconciler` | Runs `tc-inventory.py` (source and results mode) and explains the result |

---

## Working through a large inventory

With more than 50 rows for your tier:
1. Read every row of your tier first, in document order.
2. Write tests in batches of 20–30. Commit each batch.
3. After each batch, run the source-mode inventory and read its `missing` list for your tier.
4. If you run out of context, stop at a batch boundary and report `PARTIAL` with the IDs remaining.
   Never report COMPLETE with rows of your tier missing.

---

## Anti-patterns

| Anti-pattern | Why it fails | Instead |
|-------------|---------|-----------------|
| The ID only in a comment above the test | Runners don't report comments; tc-inventory lists it as `comment_only` | Put it in the test name |
| A range in a spec or test ("TC-E-106 to TC-E-115") | Middle IDs vanish; a range in a test file fails the inventory | One row, one named test, per ID |
| Reusing a phase-1 ID for phase-2 behaviour | Old tests "cover" new requirements | Allocate from your own phase block |
| `t.Skip` / `it.skip` on a TC test to get green | Skipped tests don't count, and the weakening check flags the new skip | Fix the test or the code; quarantine only with an issue and an expiry |
| Gate passes on "most tests pass" | Missing tests never get written | HIGH+MEDIUM must all pass |
| A test named with an ID that tests something else | False coverage | Name states the behaviour; `spec_test_reconciler` reads HIGH-priority tests against their rows |

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 run in fixture scenarios on macOS bash 3.2.57 (1 also on Linux bash 5.2.37 with GNU tools).
