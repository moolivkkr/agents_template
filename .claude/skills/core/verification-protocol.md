---
skill: verification-protocol
description: Systematic verification checklist — 4-level depth, assignment-delivery audit, anti-rationalization rules for ensuring implementations are complete and correct
version: "1.0"
tags:
  - verification
  - quality
  - checklist
  - review
  - completeness
---

# Verification Protocol

Systematic process for verifying that implementations are complete, correct, and production-ready. Every task completion claim must pass this protocol.

## Assignment-Delivery Checklist

Before marking **any** implementation task as done, verify every item. No exceptions.

### 1. Requirement Coverage

```
For each requirement in the spec:
  [ ] Corresponding code exists
  [ ] Code implements the full requirement, not a subset
  [ ] Edge cases mentioned in the spec are handled
  [ ] Acceptance criteria can be demonstrated
```

**How to verify:**
```bash
# Extract all requirement IDs from spec
grep -E "^(FR|NFR|OBJ)-[0-9]+" docs/BRD.md | sort > /tmp/spec_reqs.txt

# Search codebase for each requirement reference
while read -r req; do
  count=$(grep -r "$req" src/ --include="*.go" --include="*.ts" -l | wc -l)
  if [ "$count" -eq 0 ]; then
    echo "MISSING: $req has no implementation reference"
  fi
done < /tmp/spec_reqs.txt
```

### 2. API Completeness

```
For each endpoint in the API spec:
  [ ] Route is registered in the router
  [ ] Handler function exists and has real logic
  [ ] Request validation is implemented
  [ ] Response matches the documented schema
  [ ] Error cases return documented error codes
  [ ] Authentication/authorization checks are in place
```

**How to verify:**
```bash
# List all routes defined in OpenAPI spec
grep -E "^\s+/(api|v[0-9])" openapi.yaml | sort > /tmp/spec_routes.txt

# List all routes registered in code
grep -rE "(GET|POST|PUT|PATCH|DELETE)\s+\"/" src/ --include="*.go" | sort > /tmp/code_routes.txt

# Compare
diff /tmp/spec_routes.txt /tmp/code_routes.txt
```

### 3. Data Model Completeness

```
For each model/entity in the spec:
  [ ] Database migration exists with all fields
  [ ] Go/TS struct has all fields with correct types
  [ ] Validation rules match spec constraints
  [ ] Indexes exist for queried fields
  [ ] Foreign keys and constraints are defined
```

**How to verify:**
```go
// Compare struct fields to migration columns
// In tests:
func TestUserModelMatchesMigration(t *testing.T) {
    // Query information_schema for table columns
    rows, _ := db.Query(`
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position
    `)
    // Compare against struct fields
    // Flag any mismatches
}
```

### 4. Error Handling Completeness

```
For each error case documented in the spec:
  [ ] Error is caught/handled in code
  [ ] Correct HTTP status code is returned
  [ ] Error response includes machine-readable code
  [ ] Error is logged with appropriate level
  [ ] User-facing message is helpful, not exposing internals
```

### 5. UI Completeness

```
For each component in the wireframe:
  [ ] Component file exists
  [ ] Component renders all specified elements
  [ ] Interactive elements have event handlers
  [ ] Loading states are implemented
  [ ] Error states are implemented
  [ ] Empty states are implemented
  [ ] Responsive behavior matches spec
  [ ] Accessibility attributes are present (aria-*, roles)
```

### 6. Code Hygiene

```
[ ] No TODO/FIXME/HACK comments left behind
[ ] No placeholder/mock data in production code paths
[ ] All imports are used — no dead imports
[ ] No dead code (unreachable functions, unused variables)
[ ] No hardcoded secrets, URLs, or environment-specific values
[ ] No console.log / fmt.Println debugging left behind
[ ] Tests pass — zero failures
[ ] Coverage meets project threshold
```

**How to verify:**
```bash
# Scan for leftover markers
grep -rn "TODO\|FIXME\|HACK\|XXX\|PLACEHOLDER\|TEMP\|mock.*data" src/ \
  --include="*.go" --include="*.ts" --include="*.tsx" --include="*.py"

# Scan for hardcoded values
grep -rn "localhost\|127\.0\.0\.1\|password.*=.*\"" src/ \
  --include="*.go" --include="*.ts" --include="*.py" | \
  grep -v "_test\." | grep -v "test_" | grep -v "\.test\."

# Scan for debugging leftovers
grep -rn "console\.log\|fmt\.Print\|print(" src/ \
  --include="*.go" --include="*.ts" --include="*.tsx" --include="*.py" | \
  grep -v "_test\." | grep -v "logger\." | grep -v "log\."
```

## 4-Level Verification

Each level builds on the previous. All four must pass.

### Level 1: Existence

> "Do all the files, functions, and endpoints exist?"

```
Check:
  - Every file mentioned in the design doc exists on disk
  - Every function/method in the spec has a corresponding implementation
  - Every route is registered in the router
  - Every database table has a migration
  - Every UI page/component has a file

How to detect failures:
  - File not found
  - Function signature missing
  - Route returns 404 (not registered)
  - Table doesn't exist in schema
```

```bash
# Automated existence check example
check_file_exists() {
  if [ ! -f "$1" ]; then
    echo "FAIL Level 1: Missing file: $1"
    return 1
  fi
  echo "PASS: $1 exists"
}

# Check all expected files
check_file_exists "internal/handler/user_handler.go"
check_file_exists "internal/service/user_service.go"
check_file_exists "internal/repository/user_repository.go"
check_file_exists "migrations/001_create_users.sql"
```

### Level 2: Substance

> "Do implementations have real logic, not stubs?"

```
Check:
  - Functions contain more than `return nil` or `// TODO`
  - Database queries actually query the database (not return empty results)
  - Business logic performs real calculations/transformations
  - Validation actually validates (not always returns true)
  - Error handling returns meaningful errors (not swallows them)

How to detect failures:
  - Function body is < 3 lines for complex operations
  - Only `return nil, nil` or `return []T{}, nil`
  - Contains `// TODO`, `// FIXME`, `panic("not implemented")`
  - Tests pass but only because they test happy path with stubs
```

```go
// FAILS Level 2 — stub implementation
func (s *OrderService) CalculateTotal(items []LineItem) (float64, error) {
    return 0, nil // stub
}

// PASSES Level 2 — real implementation
func (s *OrderService) CalculateTotal(items []LineItem) (float64, error) {
    if len(items) == 0 {
        return 0, ErrEmptyOrder
    }
    var total float64
    for _, item := range items {
        if item.Quantity <= 0 {
            return 0, &ValidationError{Field: "quantity", Message: "must be positive"}
        }
        total += item.Price * float64(item.Quantity)
    }
    return math.Round(total*100) / 100, nil // round to cents
}
```

### Level 3: Wiring

> "Are components connected? Can data flow end-to-end?"

```
Check:
  - HTTP handler calls service, service calls repository, repository calls DB
  - Dependencies are injected — not nil, not mocked in production
  - Middleware is registered in the correct order
  - Frontend components call actual API endpoints (not mock data)
  - Environment variables are read and passed to the right components

How to detect failures:
  - Handler instantiated but not registered on router
  - Service has nil repository (dependency not injected)
  - Middleware registered after routes (never executes)
  - Frontend fetches from hardcoded localhost URL
  - Config struct has zero values for required fields
```

```go
// Wiring verification test — the "smoke test"
func TestServerWiring(t *testing.T) {
    // Build the full dependency graph
    cfg := config.LoadTest()
    db := postgres.ConnectTest(t, cfg.DSN)

    userRepo := repository.NewUserRepository(db)
    userSvc := service.NewUserService(userRepo)
    handler := handler.NewUserHandler(userSvc)

    router := server.NewRouter(handler)

    // Hit every endpoint — verify non-500 response
    endpoints := []struct {
        method string
        path   string
        want   int // expected status (or range)
    }{
        {"GET", "/api/v1/users", 200},
        {"POST", "/api/v1/users", 422}, // missing body = validation error, not 500
        {"GET", "/api/v1/users/nonexistent", 404},
    }
    for _, ep := range endpoints {
        t.Run(ep.method+" "+ep.path, func(t *testing.T) {
            req := httptest.NewRequest(ep.method, ep.path, nil)
            rec := httptest.NewRecorder()
            router.ServeHTTP(rec, req)
            assert.Equal(t, ep.want, rec.Code, "unexpected status for %s %s", ep.method, ep.path)
        })
    }
}
```

### Level 4: Data Flow

> "Does actual data move correctly through the system?"

```
Check:
  - POST creates a record that GET can retrieve
  - Mutations are persisted to the database (not just in memory)
  - Computed fields are calculated correctly with real data
  - Pagination returns correct pages with correct cursors
  - Filters actually filter (not return everything)
  - Sorting actually sorts (not random order)

How to detect failures:
  - POST returns 201 but GET returns 404 (data not persisted)
  - Update changes response but database still has old value
  - Pagination cursor always returns the same page
  - Filter parameter is accepted but ignored in query
```

```go
// Data flow integration test
func TestUserDataFlow(t *testing.T) {
    // 1. Create
    createResp := httpPost(t, "/api/v1/users", `{"email":"test@example.com","name":"Test"}`)
    assert.Equal(t, 201, createResp.StatusCode)

    var created struct{ Data User }
    json.NewDecoder(createResp.Body).Decode(&created)
    userID := created.Data.ID
    assert.NotEmpty(t, userID)

    // 2. Read back — verify persistence
    getResp := httpGet(t, "/api/v1/users/"+userID)
    assert.Equal(t, 200, getResp.StatusCode)

    var fetched struct{ Data User }
    json.NewDecoder(getResp.Body).Decode(&fetched)
    assert.Equal(t, "test@example.com", fetched.Data.Email)
    assert.Equal(t, "Test", fetched.Data.Name)

    // 3. Update — verify mutation persists
    patchResp := httpPatch(t, "/api/v1/users/"+userID, `{"name":"Updated"}`)
    assert.Equal(t, 200, patchResp.StatusCode)

    getResp2 := httpGet(t, "/api/v1/users/"+userID)
    var updated struct{ Data User }
    json.NewDecoder(getResp2.Body).Decode(&updated)
    assert.Equal(t, "Updated", updated.Data.Name)

    // 4. List — verify appears in collection
    listResp := httpGet(t, "/api/v1/users")
    var list struct{ Data []User; Meta ListMeta }
    json.NewDecoder(listResp.Body).Decode(&list)
    assert.True(t, containsID(list.Data, userID))

    // 5. Delete — verify removal
    deleteResp := httpDelete(t, "/api/v1/users/"+userID)
    assert.Equal(t, 204, deleteResp.StatusCode)

    getResp3 := httpGet(t, "/api/v1/users/"+userID)
    assert.Equal(t, 404, getResp3.StatusCode)
}
```

## Anti-Rationalization Rules

The most dangerous verification failures are the ones you talk yourself out of checking.

### Don't Accept "It Works" Without Evidence

```
BAD:  "The endpoint works" (never tested it)
GOOD: "GET /api/v1/users returns 200 with correct JSON shape — here's the curl output"

BAD:  "Tests pass" (ran tests that test mocks, not real behavior)
GOOD: "Integration tests pass against real PostgreSQL — here's the test output"

BAD:  "Error handling is implemented" (caught one error type)
GOOD: "Tested all 5 error paths: not found, validation, conflict, auth, server error"
```

### Don't Skip Edge Cases

```
Always test:
  - Empty collections (no data yet)
  - Single item collections
  - Boundary values (0, -1, max_int, empty string)
  - Concurrent operations (two users create same resource)
  - Large payloads (10MB body, 10000 items)
  - Invalid UTF-8, special characters, SQL injection attempts
  - Expired tokens, missing headers, wrong content type
```

### Don't Assume Tests Cover What They Claim

```
Read the test body, not just the test name:

BAD test:
  func TestCreateUser(t *testing.T) {
      user := createUser()  // calls the function
      assert.NotNil(t, user) // only checks it returns something
  }

GOOD test:
  func TestCreateUser(t *testing.T) {
      user, err := svc.CreateUser(ctx, CreateUserRequest{
          Email: "test@example.com",
          Name:  "Test User",
      })
      require.NoError(t, err)
      assert.Equal(t, "test@example.com", user.Email)
      assert.Equal(t, "Test User", user.Name)
      assert.NotEmpty(t, user.ID)
      assert.WithinDuration(t, time.Now(), user.CreatedAt, time.Second)

      // Verify persisted
      fetched, err := repo.FindByID(ctx, user.ID)
      require.NoError(t, err)
      assert.Equal(t, user.Email, fetched.Email)
  }
```

### Don't Rationalize Gaps

```
Common rationalizations (all wrong):
  - "We'll add tests later" → Tests exist to verify correctness NOW
  - "That edge case won't happen" → It will, in production, at 3am
  - "The framework handles that" → Verify the framework actually does
  - "It's just a minor feature" → Minor features with bugs erode user trust
  - "We're behind schedule" → Shipping broken code creates more schedule pressure
```

## Verification Report Template

After completing verification, produce this summary:

```markdown
## Verification Report — [Feature/Phase Name]

### Level 1: Existence ✅/❌
- Files: X/Y present
- Endpoints: X/Y registered
- Models: X/Y migrated
- Missing: [list]

### Level 2: Substance ✅/❌
- Stubs found: [list or "none"]
- TODO/FIXME remaining: [count]
- Placeholder data: [list or "none"]

### Level 3: Wiring ✅/❌
- Dependency injection: verified
- Middleware chain: verified
- Route registration: verified
- Gaps: [list or "none"]

### Level 4: Data Flow ✅/❌
- CRUD cycle: tested
- Pagination: tested with N records
- Filters: tested X/Y filters
- Edge cases: [list tested]

### Checklist Score: X/10
### Verdict: PASS / FAIL (with reasons)
```

## No Intrinsic Self-Correction (External Error Signal Required)

An agent may **not** enter a fix→re-check loop on the basis of its own reflection alone. Correction
requires an **external error signal** that names something concrete to fix.

**Prohibited:** "review your own work and improve it," "reflect and self-critique, then revise,"
reflection-only rewrite passes with no failing check driving them. Evidence is clear that this
*lowers* accuracy: with no external signal, a model has no reliable way to tell a correct answer from
an incorrect one, so reflection nudges as many right answers wrong as wrong answers right (Huang et
al., *Large Language Models Cannot Self-Correct Reasoning Yet*, ICLR 2024). Correction only helps when
grounded in an external verifier that points at the actual error (CRITIC, ICLR 2024).

**A fix→re-check loop is allowed ONLY when triggered by one of these external signals:**

```
[ ] A failing test (unit / integration / E2E) — the assertion names the expected vs actual
[ ] A compiler / type-checker / build error — with file:line
[ ] A linter / static-analysis / security-scanner finding — with rule + location
[ ] A SEPARATE reviewer agent (code_reviewer, security_reviewer, a reconciler, etc.) that names
    the error and its location — never the same agent grading itself
[ ] A runtime failure observed by executing the code (curl 500, panic, stack trace, wrong output)
```

If none of these fired, there is nothing to correct — stop and report done. Do not "polish" by
re-reading and guessing. This is why the framework runs review and reconciliation as *separate named
agents* (Wave 4) rather than asking the implementer to self-review: the error signal must come from
outside the agent that wrote the code.

## Critical Rules

- Never mark a task done without running through the full checklist
- No intrinsic self-correction: only loop on a failing test, compiler/linter error, or a separate
  reviewer agent's named finding — reflection-only "improve your own work" passes are prohibited
- All four verification levels must pass — Level 1 alone is not enough
- Actually execute the checks — don't just read the code and assume
- Produce evidence (test output, curl responses, screenshots) for each claim
- If any check fails, fix it before reporting completion
- Anti-rationalization: if you catch yourself saying "it's probably fine," verify
