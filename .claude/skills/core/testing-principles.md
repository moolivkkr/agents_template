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

## Test Pyramid

- **Unit (80%+):** milliseconds, no I/O, test business logic in isolation
- **Integration:** cover DB queries, external clients, API handlers
- **E2E:** 5-10 critical user journeys; CI on merge to main only
- Never test implementation details — test behavior and outcomes

## AAA Pattern

Arrange (setup) → Act (execute) → Assert (verify). One logical assertion group per test.

## Test Naming

Format: `test_<what>_<condition>_<expected_outcome>`

```
test_create_user_with_duplicate_email_returns_conflict
test_calculate_tax_for_zero_amount_returns_zero
```

## Test Isolation

- Each test independent — no shared mutable state, no order dependency
- Reset DB between integration tests (transactions, truncate, testcontainers)
- Mock all external deps in unit tests; use DI for testability

## Fixtures

Use factory functions with sensible defaults — override only what matters.

```go
func makeUser(t *testing.T, opts ...func(*User)) *User {
    t.Helper()
    u := &User{ID: uuid.New(), Email: fmt.Sprintf("user-%s@test.com", uuid.New().String()[:8]), Role: "member", Version: 1}
    for _, opt := range opts { opt(u) }
    return u
}
```

```typescript
function makeUser(overrides: Partial<User> = {}): User {
    return { id: crypto.randomUUID(), email: `user-${Math.random().toString(36).slice(2)}@test.com`, role: 'member', ...overrides };
}
```

## Coverage Gates

| Layer | Gate |
|-------|------|
| Unit | 80% line coverage (hard CI gate) |
| Integration | Key paths covered |
| E2E | Critical journeys |

Measure on business logic; exclude generated code and main(). Never lower gate to pass.

## What to Test

Business logic, error paths, edge cases (empty/zero/max/nil), security code, public contracts.

## What NOT to Test

Framework internals, trivial getters, third-party lib internals, config loading, generated code.

## When to Test Private Functions

Only when ALL met: >20 lines complex logic, used by multiple public callers, testing through public API is contrived. Otherwise test through public API.

## Critical Rules

- Tests in CI on every PR — never ship untested code
- Failing test = blocker; never skip/comment out
- Write test before fix for bugs (regression test)
- Flaky tests fixed immediately — worse than no test
- Mock what you don't own, not what you do
