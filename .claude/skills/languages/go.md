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

---

## Context Patterns

### `context.Context` as First Parameter

```go
// Every function that touches I/O, crosses a layer boundary, or could be
// cancelled MUST accept context.Context as its first parameter.
// This is not a guideline — it is the standard convention enforced by linters.

// ✅ Correct — context is first, named ctx
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error)
func (r *OrderRepo) FindByID(ctx context.Context, id string) (*Order, error)

// ❌ Wrong — context buried in the middle or missing
func (s *OrderService) CreateOrder(req CreateOrderRequest, ctx context.Context) (*Order, error)
func (r *OrderRepo) FindByID(id string) (*Order, error) // missing context entirely
```

### Context Propagation Through Layers

```go
// Context flows: HTTP handler → service → repository → database driver
// Each layer may add timeouts or values, but NEVER replaces context wholesale.

// Handler layer — receives context from the HTTP framework
func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context() // framework-provided context with request deadline
    order, err := h.service.CreateOrder(ctx, req)
    // ...
}

// Service layer — passes context through, may add business-level timeout
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    // Optionally tighten the deadline for downstream calls
    ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
    defer cancel()

    order := &Order{ID: uuid.New().String(), Status: "pending"}
    if err := s.repo.Save(ctx, order); err != nil {
        return nil, fmt.Errorf("create order: %w", err)
    }
    if err := s.events.Publish(ctx, "order.created", order); err != nil {
        return nil, fmt.Errorf("publish order event: %w", err)
    }
    return order, nil
}

// Repository layer — passes context to the database driver
func (r *OrderRepo) Save(ctx context.Context, order *Order) error {
    _, err := r.db.ExecContext(ctx,
        "INSERT INTO orders (id, status) VALUES ($1, $2)",
        order.ID, order.Status,
    )
    return err
}
```

### Context Values — When to Use, When NOT to Use

```go
// Context values are for request-scoped metadata that crosses API boundaries.
// They are NOT a replacement for function parameters or dependency injection.

// ✅ Good context value candidates:
//   - Request ID / Trace ID (for logging and distributed tracing)
//   - Tenant ID (for multi-tenant isolation)
//   - Authenticated user (for authorization checks)
//   - Deadline/timeout (built into context already)

type contextKey string

const (
    requestIDKey contextKey = "request_id"
    tenantIDKey  contextKey = "tenant_id"
    authUserKey  contextKey = "auth_user"
)

// Setting values (in middleware)
func RequestIDMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        reqID := r.Header.Get("X-Request-ID")
        if reqID == "" {
            reqID = uuid.New().String()
        }
        ctx := context.WithValue(r.Context(), requestIDKey, reqID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Reading values (type-safe helper functions — never cast directly)
func RequestIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(requestIDKey).(string); ok {
        return v
    }
    return "unknown"
}

// ❌ NEVER store in context:
//   - Database connections, loggers, service instances (use struct fields)
//   - Mutable objects (context values should be immutable)
//   - Large data structures (context is copied on WithValue)
//   - Configuration (use explicit parameters or config structs)
```

### Timeout and Deadline Propagation

```go
// Timeouts compose: an outer timeout constrains all inner ones.
// If the HTTP handler has a 30s deadline, a 60s repo timeout is meaningless.

func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    // HTTP server sets an overall request deadline (e.g., 30s)
    ctx := r.Context()

    // Service adds a tighter timeout for just the DB + event operations
    order, err := h.service.CreateOrder(ctx, req) // inherits 30s deadline
    // ...
}

func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    // Check remaining budget before starting expensive work
    if deadline, ok := ctx.Deadline(); ok {
        remaining := time.Until(deadline)
        if remaining < 2*time.Second {
            return nil, fmt.Errorf("insufficient time budget: %v remaining", remaining)
        }
    }

    // Tighten the timeout for downstream — leave room for cleanup
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    // ... perform work ...
    return order, nil
}
```

### Cancellation Handling

```go
// Check ctx.Done() in long-running loops, streaming operations, and retry logic.

func (w *Worker) ProcessBatch(ctx context.Context, items []Item) error {
    for i, item := range items {
        // Check for cancellation between items
        select {
        case <-ctx.Done():
            return fmt.Errorf("cancelled after processing %d/%d items: %w", i, len(items), ctx.Err())
        default:
        }

        if err := w.process(ctx, item); err != nil {
            return fmt.Errorf("process item %d: %w", i, err)
        }
    }
    return nil
}

// In streaming/long-poll operations
func (s *Stream) Read(ctx context.Context) (<-chan Event, error) {
    out := make(chan Event)
    go func() {
        defer close(out)
        for {
            select {
            case <-ctx.Done():
                return // caller cancelled — stop reading
            case event := <-s.source:
                select {
                case out <- event:
                case <-ctx.Done():
                    return
                }
            }
        }
    }()
    return out, nil
}
```

- Always `defer cancel()` immediately after `context.WithTimeout` or `context.WithCancel`
- Context values use unexported key types to prevent collisions across packages
- Provide typed accessor functions (`RequestIDFromContext`) — never cast `ctx.Value()` directly
- Check `ctx.Done()` between iterations in long loops and in select statements for channels
- A cancelled context returns `context.Canceled`; a deadline exceeded returns `context.DeadlineExceeded`

---

## Structured Logging with slog

### Logger Setup

```go
// slog is in the standard library since Go 1.21 — no third-party dependency needed.

import (
    "log/slog"
    "os"
)

// JSON handler for production — structured, machine-parseable
func NewProductionLogger() *slog.Logger {
    opts := &slog.HandlerOptions{
        Level:     slog.LevelInfo,
        AddSource: true, // include file:line in every log entry
    }
    handler := slog.NewJSONHandler(os.Stdout, opts)
    return slog.New(handler)
}

// Text handler for local development — human-readable
func NewDevelopmentLogger() *slog.Logger {
    opts := &slog.HandlerOptions{
        Level:     slog.LevelDebug,
        AddSource: false,
    }
    handler := slog.NewTextHandler(os.Stderr, opts)
    return slog.New(handler)
}

// Choose based on environment
func NewLogger(env string) *slog.Logger {
    if env == "production" || env == "staging" {
        return NewProductionLogger()
    }
    return NewDevelopmentLogger()
}
```

### Adding Attributes

```go
// Use typed attribute constructors — they avoid allocations for common types.

log.Info("order created",
    slog.String("order_id", order.ID),
    slog.String("tenant_id", tenantID),
    slog.Int("item_count", len(order.Items)),
    slog.Float64("total", order.Total),
    slog.Bool("express", order.IsExpress),
    slog.Time("created_at", order.CreatedAt),
    slog.Duration("processing_time", elapsed),
    slog.Any("metadata", order.Metadata), // fallback for complex types
)

// Output (JSON handler):
// {"time":"2024-01-15T10:30:00Z","level":"INFO","msg":"order created",
//  "order_id":"abc-123","tenant_id":"tenant-1","item_count":3,"total":99.99}
```

### Logger Groups and Child Loggers

```go
// Child loggers carry common attributes — add them once, log them everywhere.

// Base logger with service identity
baseLog := slog.New(handler).With(
    slog.String("service", "order-service"),
    slog.String("version", buildVersion),
)

// Create scoped child loggers for subsystems
repoLog := baseLog.WithGroup("repository")
repoLog.Info("query executed",
    slog.String("table", "orders"),
    slog.Duration("latency", elapsed),
)
// Output: {"msg":"query executed","repository":{"table":"orders","latency":"2.3ms"}}

// Per-request child logger with request-scoped attributes
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    reqLog := h.log.With(
        slog.String("request_id", RequestIDFromContext(r.Context())),
        slog.String("method", r.Method),
        slog.String("path", r.URL.Path),
    )
    reqLog.Info("request started")
    // Pass reqLog to service layer or store in context
}
```

### Request-Scoped Logging via Context

```go
// Store the logger in context so every layer can log with request attributes.
// This is one of the FEW cases where putting something in context is acceptable,
// because the logger is immutable and request-scoped.

type loggerKey struct{}

func ContextWithLogger(ctx context.Context, log *slog.Logger) context.Context {
    return context.WithValue(ctx, loggerKey{}, log)
}

func LoggerFromContext(ctx context.Context) *slog.Logger {
    if log, ok := ctx.Value(loggerKey{}).(*slog.Logger); ok {
        return log
    }
    return slog.Default() // fallback to global logger
}

// Middleware sets the contextual logger
func LoggingMiddleware(baseLog *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            reqLog := baseLog.With(
                slog.String("request_id", RequestIDFromContext(r.Context())),
                slog.String("remote_addr", r.RemoteAddr),
            )
            ctx := ContextWithLogger(r.Context(), reqLog)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// Service uses contextual logger
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    log := LoggerFromContext(ctx)
    log.Info("creating order", slog.String("customer_id", req.CustomerID))
    // ...
}
```

### Log Levels Best Practices

```go
// DEBUG — developer-only details, never enable in production by default
log.Debug("cache lookup", slog.String("key", key), slog.Bool("hit", hit))

// INFO — normal operations, business events, state transitions
log.Info("order created", slog.String("order_id", id))
log.Info("payment processed", slog.Float64("amount", 99.99))

// WARN — recoverable issues, degraded behavior, approaching limits
log.Warn("cache miss, falling back to database", slog.String("key", key))
log.Warn("rate limit approaching", slog.Int("current", count), slog.Int("limit", maxCount))

// ERROR — failures that need investigation, but the process continues
log.Error("failed to send notification",
    slog.String("order_id", id),
    slog.String("error", err.Error()),
)

// Rules:
// - Log at the POINT OF HANDLING, not at every layer (avoid duplicate log lines)
// - Include enough context to debug without reproducing (IDs, counts, durations)
// - Never log sensitive data (passwords, tokens, PII) — redact or omit
// - Use structured fields, never fmt.Sprintf in log messages
// - Production: INFO level; Debug via dynamic level change or per-request flag
```

---

## Generics (Go 1.18+)

### Type Parameters on Functions and Types

```go
// Generic function — works with any slice type
func Filter[T any](items []T, predicate func(T) bool) []T {
    result := make([]T, 0, len(items)/2) // estimate half will match
    for _, item := range items {
        if predicate(item) {
            result = append(result, item)
        }
    }
    return result
}

// Usage — type is inferred
activeUsers := Filter(users, func(u User) bool { return u.IsActive })
recentOrders := Filter(orders, func(o Order) bool { return o.CreatedAt.After(cutoff) })

// Generic type — a type-safe set
type Set[T comparable] struct {
    items map[T]struct{}
}

func NewSet[T comparable](items ...T) *Set[T] {
    s := &Set[T]{items: make(map[T]struct{}, len(items))}
    for _, item := range items {
        s.items[item] = struct{}{}
    }
    return s
}

func (s *Set[T]) Add(item T)           { s.items[item] = struct{}{} }
func (s *Set[T]) Contains(item T) bool { _, ok := s.items[item]; return ok }
func (s *Set[T]) Len() int             { return len(s.items) }
```

### Constraints

```go
// Built-in constraints
// - any             — no restriction (equivalent to interface{})
// - comparable      — supports == and != (required for map keys)
// - Custom interface constraints for method requirements

// Custom constraint: types that can be ordered
type Ordered interface {
    ~int | ~int8 | ~int16 | ~int32 | ~int64 |
    ~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 |
    ~float32 | ~float64 |
    ~string
}

func Max[T Ordered](a, b T) T {
    if a > b {
        return a
    }
    return b
}

// Method constraint — any type that has an ID() method
type Identifiable interface {
    ID() string
}

func IndexByID[T Identifiable](items []T) map[string]T {
    m := make(map[string]T, len(items))
    for _, item := range items {
        m[item.ID()] = item
    }
    return m
}

// Use golang.org/x/exp/constraints for standard numeric/ordered constraints
// or the built-in cmp.Ordered (Go 1.21+)
import "cmp"

func Clamp[T cmp.Ordered](val, minVal, maxVal T) T {
    return max(minVal, min(val, maxVal))
}
```

### Generic Repository Pattern

```go
// Generic CRUD repository — eliminates boilerplate across entity types
type Repository[T any] struct {
    db        *sqlx.DB
    tableName string
    log       *slog.Logger
}

func NewRepository[T any](db *sqlx.DB, tableName string, log *slog.Logger) *Repository[T] {
    return &Repository[T]{db: db, tableName: tableName, log: log}
}

func (r *Repository[T]) FindByID(ctx context.Context, id string) (*T, error) {
    var entity T
    query := fmt.Sprintf("SELECT * FROM %s WHERE id = $1 AND deleted_at IS NULL", r.tableName)
    if err := r.db.GetContext(ctx, &entity, query, id); err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, ErrNotFound
        }
        return nil, fmt.Errorf("find %s by id: %w", r.tableName, err)
    }
    return &entity, nil
}

func (r *Repository[T]) FindAll(ctx context.Context, limit, offset int) ([]T, error) {
    var entities []T
    query := fmt.Sprintf("SELECT * FROM %s WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2", r.tableName)
    if err := r.db.SelectContext(ctx, &entities, query, limit, offset); err != nil {
        return nil, fmt.Errorf("find all %s: %w", r.tableName, err)
    }
    return entities, nil
}

// Usage
type UserRepo = Repository[User]
userRepo := NewRepository[User](db, "users", log)
user, err := userRepo.FindByID(ctx, "abc-123")
```

### Generic Result/Option Types

```go
// Result type — encapsulates value or error
type Result[T any] struct {
    value T
    err   error
}

func Ok[T any](value T) Result[T]    { return Result[T]{value: value} }
func Err[T any](err error) Result[T] { return Result[T]{err: err} }

func (r Result[T]) Unwrap() (T, error) { return r.value, r.err }
func (r Result[T]) IsOk() bool         { return r.err == nil }

func (r Result[T]) Map(fn func(T) T) Result[T] {
    if r.err != nil {
        return r
    }
    return Ok(fn(r.value))
}

// Pair type — useful for returning two values from generic functions
type Pair[A, B any] struct {
    First  A
    Second B
}

// Map/Reduce helpers
func Map[T, U any](items []T, fn func(T) U) []U {
    result := make([]U, len(items))
    for i, item := range items {
        result[i] = fn(item)
    }
    return result
}

func Reduce[T, U any](items []T, initial U, fn func(U, T) U) U {
    acc := initial
    for _, item := range items {
        acc = fn(acc, item)
    }
    return acc
}

// Usage
ids := Map(users, func(u User) string { return u.ID })
total := Reduce(orders, 0.0, func(sum float64, o Order) float64 { return sum + o.Total })
```

### When to Use Generics vs Interfaces

```go
// USE GENERICS when:
// 1. The operation is identical across types (collections, utilities)
// 2. You need type safety without runtime type assertions
// 3. The function works on the VALUE of the type parameter

func Contains[T comparable](slice []T, target T) bool {
    for _, item := range slice {
        if item == target {
            return true
        }
    }
    return false
}

// USE INTERFACES when:
// 1. Different types need different BEHAVIOR (polymorphism)
// 2. You need to abstract over implementations (dependency injection)
// 3. The function calls METHODS on the parameter

type Validator interface {
    Validate() error
}

func ValidateAll(items []Validator) error {
    for _, item := range items {
        if err := item.Validate(); err != nil {
            return err
        }
    }
    return nil
}

// DON'T use generics just because you can — if `any` is your only constraint,
// an interface{} parameter or a concrete type is often clearer.
```

---

## Error Wrapping (Go 1.13+)

### fmt.Errorf Wrapping with %w

```go
// Wrap errors with context at every layer boundary using %w.
// This preserves the original error for inspection while adding context.

func (s *OrderService) GetOrder(ctx context.Context, id string) (*Order, error) {
    order, err := s.repo.FindByID(ctx, id)
    if err != nil {
        // Add operation context — the %w verb wraps the original error
        return nil, fmt.Errorf("get order %s: %w", id, err)
    }
    return order, nil
}

// The resulting error chain:
// "get order abc-123: find by id: sql: no rows in result set"
// Each layer adds its context without losing the original cause.

// Multiple wraps create a chain:
// handler: "handle get order: get order abc-123: find by id: not found"
//   → service: "get order abc-123: find by id: not found"
//     → repo: "find by id: not found"
//       → sentinel: "not found"
```

### errors.Is() and errors.As() for Unwrapping

```go
// errors.Is walks the entire error chain looking for a match.
// Use it for sentinel errors (specific error values).

if errors.Is(err, ErrNotFound) {
    // Handle not found — works even if err is wrapped multiple times
    http.Error(w, "not found", http.StatusNotFound)
    return
}

if errors.Is(err, context.DeadlineExceeded) {
    // The request timed out somewhere in the chain
    http.Error(w, "request timed out", http.StatusGatewayTimeout)
    return
}

// errors.As walks the chain looking for a matching TYPE.
// Use it for custom error types that carry structured data.

var valErr *ValidationError
if errors.As(err, &valErr) {
    // Access the typed error's fields
    log.Warn("validation failed",
        slog.String("field", valErr.Field),
        slog.String("message", valErr.Message),
    )
    respondJSON(w, http.StatusBadRequest, valErr)
    return
}
```

### Sentinel Errors vs Typed Errors

```go
// SENTINEL ERRORS — simple, named error values for expected conditions.
// Use when the caller only needs to know WHAT happened, not details.

var (
    ErrNotFound    = errors.New("not found")
    ErrConflict    = errors.New("conflict")
    ErrForbidden   = errors.New("forbidden")
    ErrRateLimited = errors.New("rate limited")
)

// TYPED ERRORS — struct types implementing error interface.
// Use when the caller needs structured data about the error.

type ValidationError struct {
    Field   string `json:"field"`
    Message string `json:"message"`
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s — %s", e.Field, e.Message)
}

type ConflictError struct {
    Resource string
    ID       string
    Detail   string
}

func (e *ConflictError) Error() string {
    return fmt.Sprintf("conflict on %s %s: %s", e.Resource, e.ID, e.Detail)
}
```

### Error Chains — When to Wrap vs Return Directly

```go
// WRAP when crossing a layer boundary — add context about what operation failed.
func (s *UserService) GetUser(ctx context.Context, id string) (*User, error) {
    user, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("get user %s: %w", id, err) // ✅ wrap with context
    }
    return user, nil
}

// RETURN DIRECTLY when the error already has sufficient context,
// or when wrapping would add noise without value.
func (r *UserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    var user User
    err := r.db.GetContext(ctx, &user, "SELECT * FROM users WHERE id=$1", id)
    if errors.Is(err, sql.ErrNoRows) {
        return nil, ErrNotFound // ✅ return sentinel directly — no wrapping needed
    }
    if err != nil {
        return nil, fmt.Errorf("query user %s: %w", id, err) // ✅ wrap DB error with context
    }
    return &user, nil
}

// NEVER wrap and then immediately check — handle or wrap, not both.
// ❌ Bad:
//   wrappedErr := fmt.Errorf("...: %w", err)
//   if errors.Is(wrappedErr, ErrNotFound) { ... }
// ✅ Good: check first, then decide whether to wrap or handle.
```

### Custom Error Types with Unwrap()

```go
// Implement Unwrap() to allow errors.Is/errors.As to traverse your error type.

type ServiceError struct {
    Op      string // operation that failed
    Kind    string // category (e.g., "not_found", "conflict", "internal")
    Err     error  // underlying cause
}

func (e *ServiceError) Error() string {
    if e.Err != nil {
        return fmt.Sprintf("%s: %s: %v", e.Op, e.Kind, e.Err)
    }
    return fmt.Sprintf("%s: %s", e.Op, e.Kind)
}

func (e *ServiceError) Unwrap() error {
    return e.Err // allows errors.Is/errors.As to walk through to the cause
}

// Usage
err := &ServiceError{
    Op:   "CreateOrder",
    Kind: "conflict",
    Err:  fmt.Errorf("duplicate order number: %w", ErrConflict),
}

errors.Is(err, ErrConflict) // true — walks through ServiceError.Unwrap() → inner error → ErrConflict

// For errors that wrap multiple causes (Go 1.20+), implement Unwrap() []error
type MultiError struct {
    Errors []error
}

func (e *MultiError) Error() string {
    msgs := make([]string, len(e.Errors))
    for i, err := range e.Errors {
        msgs[i] = err.Error()
    }
    return strings.Join(msgs, "; ")
}

func (e *MultiError) Unwrap() []error {
    return e.Errors
}
```

---

## Interface Design

### Accept Interfaces, Return Structs

```go
// Functions and methods should accept interface parameters and return concrete types.
// This maximizes flexibility for callers while keeping implementations explicit.

// ✅ Good — accepts interface, returns concrete
func NewUserService(repo UserRepository, log *slog.Logger) *UserService {
    return &UserService{repo: repo, log: log}
}

// ✅ Good — parameter is an interface, caller can pass any implementation
func ProcessData(r io.Reader) ([]byte, error) {
    return io.ReadAll(r)
}

// ❌ Bad — returning an interface hides the concrete type and prevents access to
// type-specific methods without type assertion
func NewUserService(repo UserRepository) UserServiceInterface {
    return &UserService{repo: repo}
}
```

### Small Interfaces (1-3 Methods)

```go
// Go's implicit interface satisfaction makes small interfaces extremely powerful.
// A type satisfies an interface simply by having the right methods — no "implements" keyword.

// 1-method interfaces are the sweet spot
type Validator interface {
    Validate() error
}

type Stringer interface {
    String() string
}

type Handler interface {
    Handle(ctx context.Context, msg Message) error
}

// 2-3 method interfaces for closely related behavior
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

type Cache interface {
    Get(ctx context.Context, key string) ([]byte, error)
    Set(ctx context.Context, key string, value []byte, ttl time.Duration) error
}

// ❌ Avoid: interfaces with 5+ methods — they are hard to implement and mock
// Split them into focused interfaces instead.
```

### Interface Composition

```go
// Compose large interfaces from small ones — the Go way.

type Reader interface {
    Read(ctx context.Context, id string) (*Entity, error)
}

type Writer interface {
    Save(ctx context.Context, entity *Entity) error
    Delete(ctx context.Context, id string) error
}

type Lister interface {
    List(ctx context.Context, filter Filter) ([]*Entity, error)
}

// Composed interfaces — use only when a consumer truly needs all methods
type ReadWriter interface {
    Reader
    Writer
}

type Repository interface {
    Reader
    Writer
    Lister
}

// Consumers should accept the SMALLEST interface they need:
// ✅ func generateReport(r Reader) — only needs read access
// ❌ func generateReport(r Repository) — requests write access it doesn't use
```

### Testing with Interfaces (Dependency Injection)

```go
// Interfaces make testing trivial — inject a mock that satisfies the interface.

type Mailer interface {
    Send(ctx context.Context, to string, subject string, body string) error
}

// Production implementation
type SMTPMailer struct {
    host string
    port int
}

func (m *SMTPMailer) Send(ctx context.Context, to, subject, body string) error {
    // ... actual SMTP logic ...
    return nil
}

// Test mock — no framework required
type MockMailer struct {
    SendFunc func(ctx context.Context, to, subject, body string) error
    Calls    []MailerCall
}

type MailerCall struct {
    To, Subject, Body string
}

func (m *MockMailer) Send(ctx context.Context, to, subject, body string) error {
    m.Calls = append(m.Calls, MailerCall{To: to, Subject: subject, Body: body})
    if m.SendFunc != nil {
        return m.SendFunc(ctx, to, subject, body)
    }
    return nil
}

// Test
func TestUserService_WelcomeEmail(t *testing.T) {
    mock := &MockMailer{}
    svc := NewUserService(repo, mock, log)

    _, err := svc.CreateUser(ctx, CreateUserRequest{Email: "new@example.com"})
    require.NoError(t, err)

    require.Len(t, mock.Calls, 1)
    assert.Equal(t, "new@example.com", mock.Calls[0].To)
    assert.Contains(t, mock.Calls[0].Subject, "Welcome")
}

// Compile-time interface compliance check
var _ Mailer = (*SMTPMailer)(nil)
var _ Mailer = (*MockMailer)(nil)
```

### Common Interface Patterns

```go
// Standard library interfaces you should know and use:

// io.Reader / io.Writer — universal byte streaming
// Accept these instead of *bytes.Buffer, *os.File, etc.
func Export(w io.Writer, data []Report) error {
    encoder := json.NewEncoder(w)
    for _, r := range data {
        if err := encoder.Encode(r); err != nil {
            return err
        }
    }
    return nil
}

// io.Closer — resource cleanup
type Connection interface {
    io.Closer
    Execute(ctx context.Context, query string) ([]Row, error)
}

// fmt.Stringer — human-readable string representation
func (o OrderStatus) String() string {
    switch o {
    case OrderPending:
        return "pending"
    case OrderConfirmed:
        return "confirmed"
    default:
        return "unknown"
    }
}

// sort.Interface — custom sorting
type ByCreatedAt []Order

func (a ByCreatedAt) Len() int           { return len(a) }
func (a ByCreatedAt) Less(i, j int) bool { return a[i].CreatedAt.Before(a[j].CreatedAt) }
func (a ByCreatedAt) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }

// http.Handler — the foundation of Go HTTP
type HealthHandler struct{}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    _, _ = w.Write([]byte(`{"status":"ok"}`))
}

// encoding.TextMarshaler / TextUnmarshaler — for custom config parsing
func (s *OrderStatus) UnmarshalText(text []byte) error {
    switch string(text) {
    case "pending":
        *s = OrderPending
    case "confirmed":
        *s = OrderConfirmed
    default:
        return fmt.Errorf("unknown status: %s", text)
    }
    return nil
}
```

---

## Concurrency Deep Patterns

### Worker Pool Pattern

```go
// A worker pool limits concurrency, processes jobs from a queue,
// and shuts down gracefully when the context is cancelled.

type WorkerPool[T any] struct {
    workers int
    jobs    chan T
    handler func(context.Context, T) error
    log     *slog.Logger
}

func NewWorkerPool[T any](workers int, bufferSize int, handler func(context.Context, T) error, log *slog.Logger) *WorkerPool[T] {
    return &WorkerPool[T]{
        workers: workers,
        jobs:    make(chan T, bufferSize),
        handler: handler,
        log:     log,
    }
}

func (p *WorkerPool[T]) Submit(job T) {
    p.jobs <- job
}

func (p *WorkerPool[T]) Run(ctx context.Context) error {
    g, ctx := errgroup.WithContext(ctx)
    for i := 0; i < p.workers; i++ {
        workerID := i
        g.Go(func() error {
            for {
                select {
                case <-ctx.Done():
                    return ctx.Err()
                case job, ok := <-p.jobs:
                    if !ok {
                        return nil // channel closed, worker exits
                    }
                    if err := p.handler(ctx, job); err != nil {
                        p.log.Error("job failed",
                            slog.Int("worker", workerID),
                            slog.String("error", err.Error()),
                        )
                        // Continue processing — don't kill the pool for one bad job
                    }
                }
            }
        })
    }
    return g.Wait()
}

// Usage
pool := NewWorkerPool[Order](10, 100, processOrder, log)
go func() {
    if err := pool.Run(ctx); err != nil {
        log.Error("worker pool stopped", slog.String("error", err.Error()))
    }
}()

for _, order := range orders {
    pool.Submit(order)
}
```

### Fan-Out / Fan-In with Channels

```go
// Fan-out: one producer, multiple consumers processing in parallel.
// Fan-in: multiple producers, one consumer collecting results.

func FanOutFanIn[T, R any](ctx context.Context, items []T, workers int, process func(context.Context, T) (R, error)) ([]R, error) {
    jobs := make(chan T, len(items))
    results := make(chan Result[R], len(items))

    // Fan-out: start workers
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {
                r, err := process(ctx, job)
                results <- Result[R]{value: r, err: err}
            }
        }()
    }

    // Send jobs
    for _, item := range items {
        jobs <- item
    }
    close(jobs) // signal workers no more jobs

    // Close results when all workers finish
    go func() {
        wg.Wait()
        close(results)
    }()

    // Fan-in: collect results
    var collected []R
    for r := range results {
        if r.err != nil {
            return nil, r.err // fail fast on first error
        }
        collected = append(collected, r.value)
    }
    return collected, nil
}
```

### errgroup.Group for Parallel Tasks with Error Propagation

```go
// errgroup is the standard tool for running parallel tasks that may fail.
// It cancels remaining tasks when any one fails.

import "golang.org/x/sync/errgroup"

func (s *DashboardService) GetDashboard(ctx context.Context, userID string) (*Dashboard, error) {
    g, ctx := errgroup.WithContext(ctx)

    var stats *Stats
    var orders []*Order
    var notifications []*Notification

    g.Go(func() error {
        var err error
        stats, err = s.statsRepo.GetByUser(ctx, userID)
        return err
    })

    g.Go(func() error {
        var err error
        orders, err = s.orderRepo.RecentByUser(ctx, userID, 10)
        return err
    })

    g.Go(func() error {
        var err error
        notifications, err = s.notifRepo.UnreadByUser(ctx, userID)
        return err
    })

    if err := g.Wait(); err != nil {
        return nil, fmt.Errorf("build dashboard for %s: %w", userID, err)
    }

    return &Dashboard{Stats: stats, Orders: orders, Notifications: notifications}, nil
}

// With concurrency limit — prevents overwhelming downstream services
func (s *BulkService) ProcessAll(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(20) // max 20 concurrent goroutines

    for _, item := range items {
        item := item // capture (Go <1.22)
        g.Go(func() error {
            return s.process(ctx, item)
        })
    }
    return g.Wait()
}
```

### sync.Once for Lazy Initialization

```go
// sync.Once ensures expensive initialization runs exactly once,
// even under concurrent access. Thread-safe by design.

type DBPool struct {
    once sync.Once
    pool *sqlx.DB
    err  error
    dsn  string
}

func (d *DBPool) Get() (*sqlx.DB, error) {
    d.once.Do(func() {
        d.pool, d.err = sqlx.Connect("pgx", d.dsn)
    })
    return d.pool, d.err
}

// sync.OnceValue (Go 1.21+) — cleaner for single-value initialization
var loadConfig = sync.OnceValue(func() *Config {
    cfg, err := parseConfig("config.yaml")
    if err != nil {
        panic(fmt.Sprintf("failed to load config: %v", err))
    }
    return cfg
})

// sync.OnceValues (Go 1.21+) — for value + error
var connectDB = sync.OnceValues(func() (*sqlx.DB, error) {
    return sqlx.Connect("pgx", os.Getenv("DATABASE_URL"))
})
```

### sync.Map vs Mutex-Guarded Map

```go
// sync.Map is optimized for two specific patterns:
// 1. Write-once, read-many (cache-like)
// 2. Disjoint key sets per goroutine (no contention)
// For everything else, use a mutex-guarded map.

// ✅ Good use of sync.Map — stable cache, rarely updated
var templateCache sync.Map

func GetTemplate(name string) (*template.Template, error) {
    if v, ok := templateCache.Load(name); ok {
        return v.(*template.Template), nil
    }
    tmpl, err := template.ParseFiles(name)
    if err != nil {
        return nil, err
    }
    templateCache.Store(name, tmpl)
    return tmpl, nil
}

// ✅ Mutex-guarded map — frequent reads AND writes, need iteration
type SafeCounter struct {
    mu       sync.RWMutex
    counters map[string]int64
}

func (c *SafeCounter) Increment(key string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.counters[key]++
}

func (c *SafeCounter) Get(key string) int64 {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.counters[key]
}

func (c *SafeCounter) Snapshot() map[string]int64 {
    c.mu.RLock()
    defer c.mu.RUnlock()
    snap := make(map[string]int64, len(c.counters))
    for k, v := range c.counters {
        snap[k] = v
    }
    return snap
}

// Rule of thumb:
// - sync.Map: no need to iterate, keys are stable, low write frequency
// - RWMutex + map: need iteration, high write frequency, or complex operations
```

### Channel Direction

```go
// Channel direction in function signatures communicates intent
// and prevents misuse at compile time.

// <-chan T = receive-only (consumer)
// chan<- T = send-only (producer)
// chan T   = bidirectional (avoid in function signatures when possible)

// Producer: returns a send channel (but exposes it as receive-only to the caller)
func Produce(ctx context.Context, items []Item) <-chan Item {
    out := make(chan Item)
    go func() {
        defer close(out) // producer closes the channel
        for _, item := range items {
            select {
            case <-ctx.Done():
                return
            case out <- item:
            }
        }
    }()
    return out // returned as <-chan Item — caller can only receive
}

// Consumer: accepts a receive-only channel
func Consume(ctx context.Context, in <-chan Item) error {
    for item := range in {
        if err := process(item); err != nil {
            return err
        }
    }
    return nil
}

// Pipeline stage: accepts receive-only, returns receive-only
func Transform(ctx context.Context, in <-chan Item) <-chan Result {
    out := make(chan Result)
    go func() {
        defer close(out)
        for item := range in {
            select {
            case <-ctx.Done():
                return
            case out <- transform(item):
            }
        }
    }()
    return out
}

// Composing a pipeline:
// items := Produce(ctx, rawItems)
// transformed := Transform(ctx, items)
// err := Consume(ctx, transformed)
```

---

## Critical Rules

- Always handle errors — `errcheck` lint rule enforces this
- Never use `init()` for anything side-effectful — inject dependencies explicitly
- Use `slog` (stdlib) for structured logging; pass logger via struct, not global
- Use `any` not `interface{}` (Go 1.18+)
- Run `go vet` and `staticcheck` in CI — fix all findings before merge
- Use `context.Context` as the first parameter for all I/O and cross-layer functions
- Wrap errors with `fmt.Errorf("context: %w", err)` at every layer boundary
- Accept interfaces, return structs — define interfaces at the consumer, not the implementor
- Use generics for type-safe collection utilities; use interfaces for behavioral polymorphism
- Prefer `errgroup` over manual `sync.WaitGroup` + channels for parallel tasks with errors
- Channel direction in signatures prevents misuse — always specify `<-chan` or `chan<-` in parameters
