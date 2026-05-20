---
skill: code-quality
description: Code quality enforcement — self-review, function size, naming, KISS, DRY, incremental development, early returns, nesting limits
version: "1.0"
tags:
  - quality
  - clean-code
  - naming
  - refactoring
  - best-practices
---

# Code Quality

Standards for clean, maintainable, production-grade code. Enforce before marking any task complete.

## Self-Review Checkpoint

Before marking ANY task done, re-read every file you touched:

1. **Unused imports** — remove (lint failures)
2. **Dead code** — no commented-out blocks or unreachable branches
3. **TODO/FIXME** — replace with implementation or remove (see policy below)
4. **Hardcoded values** — extract to config/constants/env
5. **Missing error handling** — every error path explicit (see `backend/archetypes/error-handling.md`)
6. **Inconsistent naming** — same convention throughout file
7. **Missing tests** — new public functions need at least one test

## TODO Policy

| Context | Allowed? | Format |
|---------|----------|--------|
| Implementation code (src/) | NO — implement or remove | N/A |
| Test code (*_test.go, *.test.ts) | YES — future test work | `// TODO(author): reason` |
| Documentation (*.md) | YES — planned improvements | `// TODO(author): reason` |
| Optimization reports | YES — future opportunities | Freeform |

## Function Size — 40 Lines Max

Extract helpers when exceeded. Decompose into validate → build → save → notify pattern.

```go
// GOOD — decomposed
func CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    if err := validateCreateUserRequest(req); err != nil { return nil, err }
    user, err := buildUser(req)
    if err != nil { return nil, fmt.Errorf("building user: %w", err) }
    if err := s.repo.Save(ctx, user); err != nil { return nil, fmt.Errorf("saving: %w", err) }
    s.notifyUserCreated(ctx, user)
    return user, nil
}
```

## Parameter Count — 4 Max

Use options struct/object for >4 params.

```go
type SendEmailOptions struct { To, From, Subject, Body string; IsHTML bool; Attachments []string }
func SendEmail(opts SendEmailOptions) error
```

## Nesting Depth — 2 Levels Max

Use early returns and guard clauses.

```go
// GOOD — flat with early returns
func ProcessItem(item *Item) error {
    if item == nil { return ErrNilItem }
    if !item.IsValid() { return ErrInvalidItem }
    if item.Status != Active { return nil }
    return item.Process()
}
```

## Early Returns

Guard → guard → guard → happy path (least-indented).

## KISS Enforcement

- No premature abstraction — interface only with 2+ implementations
- No YAGNI code; no clever tricks; no unnecessary generics
- Prefer stdlib over third-party for simple tasks

## Incremental Development

Build → Test → Commit. Never write >100 lines without testing.

1. Small focused change → 2. Test immediately → 3. If works: commit → 4. If fails: fix now → 5. Repeat

## DRY With Judgment

Extract shared code after 3+ repetitions. Extract immediately for: security logic, business rules that must be consistent, complex error-prone algorithms.

## Naming Conventions

- **Functions:** verb + noun (`GetUser`, `ValidateInput`, `SendNotification`)
- **Booleans:** is/has/can/should prefix (`isActive`, `hasPermission`)
- **No abbreviations** except: `id`, `url`, `http`, `api`, `db`, `ctx`, `err`, `req`, `res`, `msg`, `pkg`, `cmd`, `env`, `src`, `dst`, `max`, `min`, `len`, `num`, `str`, `fmt`

## Unified Severity Model

All pipeline agents map to this for gate decisions:

| Unified | Gate Impact | Agent Mappings |
|---------|------------|----------------|
| **BLOCKING** | Gate fails. Must fix. | code_reviewer: BLOCKING/VIOLATION, security: HIGH, tenant: CRITICAL, spec_impl: MISSING |
| **WARNING** | Should fix. Logged if unresolved after 2 rounds. | code_reviewer: WARNING, security: MEDIUM, spec_impl: UNSPECCED |
| **INFO** | Consider. No gate impact. | code_reviewer: INFO, security: LOW |

## Critical Rules

- Self-review mandatory — run checklist before completing any task
- Functions >40 lines = code smell; >4 params = design problem; >2 nesting = flatten
- Happy path = least-indented code path
- Test every ~100 lines; name for the reader; choose simpler solution when in doubt
