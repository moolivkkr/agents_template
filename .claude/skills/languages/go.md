---
skill: go
description: Go patterns — error handling, interfaces, context, goroutines, table-driven tests, module conventions, DI without frameworks
version: "1.0"
tags:
  - go
  - golang
  - patterns
  - concurrency
  - testing
---

# Go Language Patterns

Idiomatic Go for production services. Prioritize clarity, explicit error handling, and composability.

## Project Structure

```
cmd/
  server/       # main.go — wire dependencies, start server
  worker/       # main.go — wire dependencies, start worker
internal/
  domain/       # business entities, no external dependencies
  service/      # business logic, depends on repository interfaces
  repository/   # DB access implementations
  handler/      # HTTP handlers, wire service in
  middleware/   # HTTP middleware
pkg/            # importable by other modules
  config/
  logger/
```

- `internal/` enforces package privacy — nothing outside this module can import it
- `cmd/` packages are thin: parse flags, build deps, call `run()`
- Never put business logic in `main.go`

## Error Handling

```go
// Return errors explicitly — never panic in library/service code
func (s *UserService) GetUser(ctx context.Context, id string) (*User, error) {
    user, err := s.repo.FindByID(ctx, id)
    if err != nil {
        if errors.Is(err, ErrNotFound) {
            return nil, fmt.Errorf("user %s: %w", id, ErrNotFound)
        }
        return nil, fmt.Errorf("get user %s: %w", id, err)
    }
    return user, nil
}

// Sentinel errors
var (
    ErrNotFound   = errors.New("not found")
    ErrConflict   = errors.New("conflict")
    ErrForbidden  = errors.New("forbidden")
)

// Wrap with context, unwrap with errors.Is / errors.As
if errors.Is(err, ErrNotFound) { ... }
```

- Panic only in `main()` for unrecoverable startup failure; never in library code
- Wrap errors with `fmt.Errorf("context: %w", err)` to preserve the chain
- Define sentinel errors in the package they originate from

## Interfaces

```go
// Small, composable interfaces — one or two methods
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

type Mailer interface {
    Send(ctx context.Context, msg Message) error
}

// Larger aggregate interfaces in the service layer
type OrderService interface {
    CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error)
    CancelOrder(ctx context.Context, id string) error
}
```

- Define interfaces where they are consumed, not where they are implemented
- Accept interfaces, return concrete types
- Interfaces with >5 methods are usually doing too much — split them

## Struct Embedding and Composition

```go
// Embed for shared behavior, not for inheritance
type BaseRepository struct {
    db  *sqlx.DB
    log *slog.Logger
}

func (r *BaseRepository) withTx(ctx context.Context, fn func(*sqlx.Tx) error) error {
    tx, err := r.db.BeginTxx(ctx, nil)
    if err != nil {
        return err
    }
    if err := fn(tx); err != nil {
        _ = tx.Rollback()
        return err
    }
    return tx.Commit()
}

type UserRepository struct {
    BaseRepository
}
```

## Context Propagation

```go
// Every function that does I/O takes ctx as the first parameter
func (r *UserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel() // always defer cancel

    var user User
    if err := r.db.GetContext(ctx, &user, "SELECT * FROM users WHERE id=$1", id); err != nil {
        return nil, err
    }
    return &user, nil
}

// Store request-scoped values (request ID, trace ID) — not dependencies
type contextKey string
const requestIDKey contextKey = "request_id"
```

- Always `defer cancel()` immediately after `context.WithTimeout` or `context.WithCancel`
- Never store mutable objects (loggers, DB connections) in context — use struct fields
- Check `ctx.Done()` in long loops or streaming operations

## Goroutines and Channels

```go
// Bounded worker pool
func processItems(ctx context.Context, items []Item, concurrency int) error {
    sem := make(chan struct{}, concurrency)
    errs := make(chan error, len(items))
    var wg sync.WaitGroup

    for _, item := range items {
        item := item // capture loop variable (Go <1.22)
        sem <- struct{}{}
        wg.Add(1)
        go func() {
            defer wg.Done()
            defer func() { <-sem }()
            if err := process(ctx, item); err != nil {
                select {
                case errs <- err:
                default:
                }
            }
        }()
    }
    wg.Wait()
    close(errs)
    return <-errs // first error or nil
}
```

- Always have a way to stop goroutines — use context cancellation
- Prefer `errgroup.Group` from `golang.org/x/sync/errgroup` for goroutine error collection
- Close channels from the producer (sender), never the consumer

## Table-Driven Tests

```go
func TestApplyDiscount(t *testing.T) {
    tests := []struct {
        name     string
        subtotal float64
        percent  int
        want     float64
    }{
        {"10% off 100", 100, 10, 90},
        {"zero discount", 100, 0, 100},
        {"100% off", 50, 100, 0},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := ApplyDiscount(tt.subtotal, tt.percent)
            assert.Equal(t, tt.want, got)
        })
    }
}
```

- Use `testify/assert` for non-fatal assertions, `testify/require` for fatal ones
- Use `httptest.NewRecorder()` and `httptest.NewServer()` for HTTP handler tests
- Use `t.Cleanup()` instead of `defer` in test helpers to avoid closure issues

## Dependency Injection

```go
// Wire dependencies manually in cmd/server/main.go — no DI framework needed
func main() {
    cfg := config.Load()
    db := postgres.Connect(cfg.DSN)
    log := logger.New(cfg.Env)

    userRepo := repository.NewUserRepository(db, log)
    mailer   := smtp.NewMailer(cfg.SMTPAddr)
    userSvc  := service.NewUserService(userRepo, mailer, log)
    handler  := handler.NewUserHandler(userSvc, log)

    srv := server.New(handler, cfg.Port)
    srv.Run()
}
```

## Module Conventions

- Module path: `github.com/org/repo` (use real import path, not `example.com`)
- One `go.mod` per service or per monorepo workspace
- Run `go mod tidy` before every commit
- Pin indirect dependencies to avoid supply chain surprises

## golangci-lint Rules

Enable at minimum: `errcheck`, `govet`, `staticcheck`, `revive`, `gosec`, `exhaustive`

```yaml
# .golangci.yml
linters:
  enable:
    - errcheck
    - govet
    - staticcheck
    - gosec
    - exhaustive
    - godot
    - misspell
```

## Critical Rules

- Always handle errors — `errcheck` lint rule enforces this
- Never use `init()` for anything side-effectful — inject dependencies explicitly
- Use `slog` (stdlib) for structured logging; pass logger via struct, not global
- Use `any` not `interface{}` (Go 1.18+)
- Run `go vet` and `staticcheck` in CI — fix all findings before merge
