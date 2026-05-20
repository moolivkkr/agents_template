> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

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

## Performance Optimization

```go
// sync.Pool for frequent short-lived allocations (buffers, temp structs)
var bufPool = sync.Pool{
    New: func() any { return new(bytes.Buffer) },
}

func processRequest(data []byte) string {
    buf := bufPool.Get().(*bytes.Buffer)
    defer func() {
        buf.Reset()
        bufPool.Put(buf)
    }()
    buf.Write(data)
    return buf.String()
}

// Pre-allocate slices when size is known or estimable
func collectIDs(users []User) []string {
    ids := make([]string, 0, len(users)) // pre-allocate capacity
    for _, u := range users {
        ids = append(ids, u.ID)
    }
    return ids
}

// strings.Builder for concatenation — never use + in loops
func buildQuery(fields []string) string {
    var b strings.Builder
    b.Grow(len(fields) * 20) // estimate capacity
    for i, f := range fields {
        if i > 0 {
            b.WriteString(", ")
        }
        b.WriteString(f)
    }
    return b.String()
}
```

- Avoid `reflect` in hot paths — it is 10-100x slower than direct access
- Use `sync.Pool` for buffers, temp structs, and encoder/decoder instances
- Pre-allocate maps too: `make(map[K]V, expectedSize)`
- Profile with `pprof` before optimizing — measure, don't guess
- Reuse `http.Client` and `*sql.DB` — they manage connection pools internally

## Interface Patterns

```go
// Accept interfaces, return structs
// The consumer defines the interface — not the implementor
type Notifier interface {
    Notify(ctx context.Context, msg string) error
}

// Small interfaces: 1-3 methods — compose larger behaviors
type Reader interface {
    Read(ctx context.Context, id string) (*Entity, error)
}

type Writer interface {
    Write(ctx context.Context, entity *Entity) error
}

type ReadWriter interface {
    Reader
    Writer
}

// Use standard library interfaces wherever possible
// io.Reader, io.Writer, io.Closer, fmt.Stringer, error, sort.Interface
type Renderer interface {
    Render(w io.Writer) error // accept io.Writer, not *bytes.Buffer
}

// Verify interface compliance at compile time
var _ Notifier = (*SlackNotifier)(nil)
var _ Notifier = (*EmailNotifier)(nil)
```

- Define interfaces where they are **consumed**, not where they are implemented
- Prefer many small interfaces over one large one — Go's implicit satisfaction makes this natural
- Composition over inheritance: embed small interfaces into larger ones
- Return concrete types from constructors — let callers decide what interface they need

## Error Patterns

> **Canonical reference**: For the full error type taxonomy, HTTP status mapping, error middleware, and structured error response format, see `backend/archetypes/error-handling.md`.

```go
// Sentinel errors for expected, recoverable cases
var (
    ErrNotFound    = errors.New("not found")
    ErrConflict    = errors.New("conflict")
    ErrRateLimited = errors.New("rate limited")
)

// Custom error types for domain errors that carry data
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s — %s", e.Field, e.Message)
}

// Wrapping preserves the chain — always add operation context
func (s *OrderService) GetOrder(ctx context.Context, id string) (*Order, error) {
    order, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("get order %s: %w", id, err)
    }
    return order, nil
}

// Checking wrapped errors
if errors.Is(err, ErrNotFound) {
    // handle not found
}

var valErr *ValidationError
if errors.As(err, &valErr) {
    // access valErr.Field, valErr.Message
}
```

- Sentinel errors (`var Err... = errors.New(...)`) for expected cases callers can handle
- Custom error types (implementing `error` interface) when callers need structured data
- Wrap with `fmt.Errorf("context: %w", err)` to preserve the chain at every layer
- Check with `errors.Is` for sentinel errors, `errors.As` for typed errors
- Never ignore errors — if truly intentional, assign to `_` with a comment explaining why

## Concurrency

```go
// errgroup: managed goroutines with error propagation and context cancellation
func fetchAll(ctx context.Context, ids []string) ([]*Item, error) {
    g, ctx := errgroup.WithContext(ctx)
    results := make([]*Item, len(ids))

    for i, id := range ids {
        i, id := i, id // capture (Go <1.22)
        g.Go(func() error {
            item, err := fetch(ctx, id)
            if err != nil {
                return fmt.Errorf("fetch %s: %w", id, err)
            }
            results[i] = item // each goroutine writes to its own index — no mutex needed
            return nil
        })
    }
    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}

// Channels for producer-consumer communication
func pipeline(ctx context.Context, input <-chan Job) <-chan Result {
    out := make(chan Result)
    go func() {
        defer close(out) // producer closes the channel
        for job := range input {
            select {
            case <-ctx.Done():
                return
            case out <- process(job):
            }
        }
    }()
    return out
}

// sync.Mutex for shared state — keep critical sections small
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}
```

- Use `errgroup` (golang.org/x/sync) for parallel operations with error collection
- Use channels for communication between goroutines, mutexes for shared state
- Always pass `context.Context` for cancellation — check `ctx.Done()` in long operations
- Never start a goroutine without a clear lifecycle — who stops it? when? how?
- Use `sync.WaitGroup` only when you don't need error propagation; prefer `errgroup`
- Limit concurrency with semaphore channels or `errgroup.SetLimit(n)`

## Testing Patterns

```go
// Table-driven tests with subtests
func TestParseAmount(t *testing.T) {
    t.Parallel() // mark independent tests as parallel

    tests := []struct {
        name    string
        input   string
        want    int64
        wantErr bool
    }{
        {"valid cents", "12.34", 1234, false},
        {"no decimals", "100", 10000, false},
        {"negative", "-5.00", -500, false},
        {"invalid", "abc", 0, true},
        {"empty", "", 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got, err := ParseAmount(tt.input)
            if tt.wantErr {
                require.Error(t, err)
                return
            }
            require.NoError(t, err)
            assert.Equal(t, tt.want, got)
        })
    }
}

// Test helpers — use t.Helper() so failures report the caller's line number
func createTestUser(t *testing.T, db *sqlx.DB) *User {
    t.Helper()
    user := &User{ID: uuid.New().String(), Email: "test@example.com"}
    _, err := db.Exec("INSERT INTO users (id, email) VALUES ($1, $2)", user.ID, user.Email)
    require.NoError(t, err)
    t.Cleanup(func() {
        _, _ = db.Exec("DELETE FROM users WHERE id = $1", user.ID)
    })
    return user
}

// Integration tests with testcontainers
func TestUserRepo_Integration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }
    ctx := context.Background()
    pgContainer, err := postgres.RunContainer(ctx,
        testcontainers.WithImage("postgres:16-alpine"),
        postgres.WithDatabase("testdb"),
    )
    require.NoError(t, err)
    t.Cleanup(func() { _ = pgContainer.Terminate(ctx) })

    connStr, _ := pgContainer.ConnectionString(ctx, "sslmode=disable")
    db := sqlx.MustConnect("pgx", connStr)
    repo := NewUserRepository(db)

    // ... test against real PostgreSQL
}

// Golden files for complex/snapshot outputs
func TestRenderTemplate(t *testing.T) {
    got := renderTemplate(data)
    golden := filepath.Join("testdata", t.Name()+".golden")

    if *update { // -update flag to regenerate golden files
        os.WriteFile(golden, []byte(got), 0644)
    }
    want, _ := os.ReadFile(golden)
    assert.Equal(t, string(want), got)
}
```

- Use `testify/assert` for non-fatal assertions, `testify/require` for fatal ones
- `t.Helper()` on every test helper function — error reports show the caller's line
- `t.Parallel()` on independent tests — speeds up the suite significantly
- `t.Cleanup()` for teardown — runs even if the test panics, unlike `defer`
- `testcontainers` for integration tests against real databases and services
- Golden files for complex outputs — store expected output in `testdata/` directory
- Use `-short` flag to skip slow integration tests in development

## Critical Rules

- Always handle errors — `errcheck` lint rule enforces this
- Never use `init()` for anything side-effectful — inject dependencies explicitly
- Use `slog` (stdlib) for structured logging; pass logger via struct, not global
- Use `any` not `interface{}` (Go 1.18+)
- Run `go vet` and `staticcheck` in CI — fix all findings before merge
