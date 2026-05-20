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

Systematic process for verifying implementations are complete, correct, and production-ready.

## Assignment-Delivery Checklist

### 1. Requirement Coverage

For each spec requirement: code exists, implements FULL requirement, edge cases handled, acceptance criteria demonstrable.

### 2. API Completeness

For each endpoint: route registered, handler has real logic, request validation, response matches schema, error codes correct, auth checks present.

### 3. Data Model Completeness

For each entity: migration exists with all fields, struct has correct types, validation matches constraints, indexes for queried fields, FKs/constraints defined.

### 4. Error Handling Completeness

For each error case: caught/handled, correct HTTP status, machine-readable code, logged at right level, user-facing message safe.

### 5. UI Completeness

For each component: file exists, renders all elements, event handlers wired, loading/error/empty states, responsive, a11y attributes.

### 6. Code Hygiene

No TODO/FIXME/HACK, no placeholder data, no unused imports, no dead code, no hardcoded secrets/URLs, no debug logging, tests pass, coverage meets threshold.

```bash
# Scan for issues
grep -rn "TODO\|FIXME\|HACK\|PLACEHOLDER" src/ --include="*.go" --include="*.ts"
grep -rn "console\.log\|fmt\.Print" src/ --include="*.go" --include="*.ts" | grep -v "_test\." | grep -v "logger\."
```

## 4-Level Verification

All four must pass.

### Level 1: Existence

Do all files, functions, endpoints, migrations, components exist?

### Level 2: Substance

Do implementations have real logic, not stubs? Check for: `return nil`, `// TODO`, `panic("not implemented")`, functions <3 lines for complex ops.

```go
// FAILS — stub
func (s *OrderService) CalculateTotal(items []LineItem) (float64, error) { return 0, nil }

// PASSES — real logic with validation
func (s *OrderService) CalculateTotal(items []LineItem) (float64, error) {
    if len(items) == 0 { return 0, ErrEmptyOrder }
    var total float64
    for _, item := range items {
        if item.Quantity <= 0 { return 0, &ValidationError{Field: "quantity", Message: "must be positive"} }
        total += item.Price * float64(item.Quantity)
    }
    return math.Round(total*100) / 100, nil
}
```

### Level 3: Wiring

Are components connected? Handler→service→repo chain wired, dependencies injected (not nil), middleware registered in correct order, frontend calls real endpoints, config values populated.

```go
// Smoke test — build full dep graph, hit every endpoint
func TestServerWiring(t *testing.T) {
    // Build deps, create router, verify each endpoint returns expected status (not 500)
}
```

### Level 4: Data Flow

Does actual data move correctly? POST creates record GET can retrieve, mutations persist to DB, computed fields correct, pagination/filters/sorting work.

```go
// CRUD data flow test
func TestUserDataFlow(t *testing.T) {
    // 1. POST create → 201 → 2. GET read back → verify fields
    // 3. PATCH update → verify persists → 4. LIST → verify appears
    // 5. DELETE → verify GET returns 404
}
```

## Anti-Rationalization Rules

- Don't accept "it works" without evidence (curl output, test output)
- Don't skip edge cases (empty, boundary, concurrent, large, invalid)
- Don't assume tests cover what they claim — read the test body
- Don't rationalize gaps: "we'll add later" / "won't happen" / "framework handles it"

## Verification Report Template

```markdown
## Verification Report — [Feature/Phase]
### Level 1: Existence — Files: X/Y, Endpoints: X/Y, Models: X/Y
### Level 2: Substance — Stubs: [list], TODOs: [count], Placeholders: [list]
### Level 3: Wiring — DI: verified, Middleware: verified, Routes: verified
### Level 4: Data Flow — CRUD: tested, Pagination: tested, Filters: X/Y
### Score: X/10 | Verdict: PASS / FAIL
```

## Critical Rules

- Never mark done without full checklist
- All four levels must pass — Level 1 alone insufficient
- Actually execute checks — don't just read code and assume
- Produce evidence (test output, curl responses) for each claim
- Fix failures before reporting completion
- If you think "it's probably fine" — verify
