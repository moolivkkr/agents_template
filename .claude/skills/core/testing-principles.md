---
skill: testing-principles
description: Test pyramid, AAA pattern, naming conventions, test isolation, fixtures, coverage gates, what to test vs skip
version: "1.0"
tags:
  - testing
  - unit
  - integration
  - e2e
  - coverage
---

# Testing Principles

Language-agnostic testing strategy covering structure, naming, isolation, and coverage gates.

## Test Pyramid

```
        /\
       /e2e\        — Few, slow, expensive. Test critical user journeys only.
      /------\
     /integr. \     — Moderate. Test service boundaries, DB queries, API contracts.
    /----------\
   /   unit     \   — Many, fast, cheap. Test business logic in isolation.
  /--------------\
```

- Unit tests: 80%+ of test count; run in milliseconds; no I/O
- Integration tests: cover DB queries, external service clients, API handlers
- E2E tests: cover 5–10 critical user journeys; run in CI on merge to main only
- Never test implementation details — test behavior and outcomes

## AAA Pattern (Arrange / Act / Assert)

```python
def test_apply_discount_reduces_order_total():
    # Arrange
    order = Order(items=[Item(price=100)], subtotal=100)
    discount = Discount(code="SAVE10", percent=10)

    # Act
    result = order.apply_discount(discount)

    # Assert
    assert result.total == 90
    assert result.discount_applied == "SAVE10"
```

- Separate the three phases visually with blank lines or comments
- One logical assertion group per test (multiple assert statements on the same outcome are fine)
- Each test should verify exactly one behavior

## Test Naming

Format: `test_<what>_<condition>_<expected_outcome>`

```
test_create_user_with_duplicate_email_returns_conflict
test_calculate_tax_for_zero_amount_returns_zero
test_authenticate_with_expired_token_raises_unauthorized
test_process_payment_when_card_declined_retries_once
```

- Names must read as a sentence describing the scenario
- Avoid generic names: `test_user`, `test_happy_path`, `test_1`
- Group related tests in a class or describe block by the unit under test

## Test Isolation

- Each test must be independent — no shared mutable state between tests
- Reset database state before/after each integration test (transactions, truncate, or test containers)
- Mock all external dependencies in unit tests: HTTP clients, queues, email services
- Never rely on test execution order
- Use dependency injection to make units testable without real infrastructure

```go
// Inject dependencies to enable mocking
type OrderService struct {
    repo    OrderRepository  // interface, not concrete type
    mailer  Mailer           // interface
    payment PaymentGateway   // interface
}
```

## Fixtures and Test Data

- Use factory functions or builder pattern for test data — not copy-pasted structs
- Keep fixtures minimal: only include fields relevant to the test
- Use realistic but non-PII data (faker libraries are fine)
- Share fixture setup via `beforeEach`/`setUp`/`TestMain`, not global variables

```python
# Factory pattern
def make_user(**overrides):
    defaults = {"email": "alice@example.com", "role": "member", "active": True}
    return User(**{**defaults, **overrides})

def test_admin_can_delete_user():
    admin = make_user(role="admin")
    target = make_user(email="bob@example.com")
    ...
```

## Coverage Gates

| Layer | Coverage Gate | Notes |
|-------|--------------|-------|
| Unit tests | 80% line coverage | Hard gate in CI |
| Integration tests | Key paths covered | No numeric gate |
| E2E tests | Critical journeys | Manual checklist |

- Measure coverage on business logic packages; exclude generated code and `main()`
- Coverage below gate blocks merge; do not lower the gate to pass
- 100% coverage is not the goal — test quality over quantity

## What to Test

- Business logic: calculations, validations, state transitions, decision branches
- Error paths: what happens when a dependency fails or returns unexpected data
- Edge cases: empty input, zero values, maximum bounds, nil/null
- Security-sensitive code: auth checks, permission validation, input sanitization
- Public interfaces/contracts: API response shapes, event schemas

## What Not to Test

- Framework code: routing, ORM internals, standard library behavior
- Trivial getters/setters with no logic
- Third-party library internals
- Configuration loading (test that config is used, not that it loads)
- Generated code (protobuf, ORM models)

## Critical Rules

- Tests must run in CI on every PR — never ship untested code
- A failing test is a blocker; do not skip or comment out failing tests
- Write the test before the fix when resolving bugs (regression test)
- Flaky tests must be fixed immediately — a flaky test is worse than no test
- Do not mock what you own; mock what you do not own (third-party APIs, external services)

## Go Test Factory Pattern

Use functional options to build test entities with sensible defaults. Override only what matters for each test.

```go
func makeUser(t *testing.T, opts ...func(*User)) *User {
    t.Helper()
    u := &User{
        ID:       uuid.New(),
        TenantID: uuid.New(),
        Email:    fmt.Sprintf("user-%s@test.com", uuid.New().String()[:8]),
        Name:     "Test User",
        Role:     "member",
        Version:  1,
    }
    for _, opt := range opts {
        opt(u)
    }
    return u
}

func withTenant(tenantID uuid.UUID) func(*User) {
    return func(u *User) { u.TenantID = tenantID }
}

func withRole(role string) func(*User) {
    return func(u *User) { u.Role = role }
}

func withEmail(email string) func(*User) {
    return func(u *User) { u.Email = email }
}
```

**Why this pattern:**
- Each test only specifies what it cares about — the rest gets safe defaults
- `t.Helper()` ensures test failures point to the calling test, not the factory
- Functional options compose cleanly: `makeUser(t, withTenant(id), withRole("admin"))`
- Unique IDs prevent cross-test data collisions in integration tests

## TypeScript Test Factory Pattern

```typescript
function makeUser(overrides: Partial<User> = {}): User {
    return {
        id: crypto.randomUUID(),
        tenantId: crypto.randomUUID(),
        email: `user-${Math.random().toString(36).slice(2)}@test.com`,
        name: 'Test User',
        role: 'member',
        ...overrides,
    };
}

function makeUsers(count: number, overrides: Partial<User> = {}): User[] {
    return Array.from({ length: count }, () => makeUser(overrides));
}
```

**Why this pattern:**
- Spread operator `...overrides` lets callers override any field inline
- `makeUsers(count)` variant for list/pagination tests
- `crypto.randomUUID()` generates unique IDs to prevent test collisions
- Factory returns a plain object — no class instantiation needed

## When to Test Private Functions

Test private functions **only** when ALL of these conditions are met:
1. The function is complex (>20 lines of logic, not boilerplate)
2. The function is used by multiple public callers (shared internal logic)
3. Testing through the public API would require contrived or fragile setups

**Otherwise, test through the public API.** Private functions are implementation details — testing them directly couples tests to internal structure and makes refactoring harder.

```go
// DO: Test through the public API
func TestCalculateDiscount_AppliesVolumeDiscount(t *testing.T) {
    // applyVolumeRate is private, but we test it through CalculateDiscount
    result := svc.CalculateDiscount(Order{Quantity: 100, UnitPrice: 50})
    assert.Equal(t, 4500.0, result.Total) // 10% volume discount applied
}

// DON'T: Test the private function directly (unless it meets all 3 criteria above)
// func TestApplyVolumeRate(t *testing.T) { ... }  // couples to implementation
```
