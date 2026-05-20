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

- `internal/` enforces package privacy
- `cmd/` packages are thin: parse flags, build deps, call `run()`
- Never put business logic in `main.go`

## Error Handling

> **Canonical reference**: See `backend/archetypes/error-handling.md` for full error taxonomy, HTTP mapping, and middleware.

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

// Custom error types for domain errors carrying data
type ValidationError struct {
    Field   string
    Message string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s — %s", e.Field, e.Message)
}

// Custom error with Unwrap for chain traversal
type ServiceError struct {
    Op   string
    Kind string
    Err  error
}
func (e *ServiceError) Error() string {
    if e.Err != nil { return fmt.Sprintf("%s: %s: %v", e.Op, e.Kind, e.Err) }
    return fmt.Sprintf("%s: %s", e.Op, e.Kind)
}
func (e *ServiceError) Unwrap() error { return e.Err }

// Multi-error (Go 1.20+)
type MultiError struct { Errors []error }
func (e *MultiError) Unwrap() []error { return e.Errors }
```

- Panic only in `main()` for unrecoverable startup failure
- Wrap errors with `fmt.Errorf("context: %w", err)` at every layer boundary
- Sentinel errors for expected cases; typed errors when callers need structured data
- Check with `errors.Is` (sentinel) and `errors.As` (typed)
- Never ignore errors — assign to `_` with comment if intentional
- Wrap at layer boundaries; return directly when error has sufficient context
- Never wrap and then check — check first, then decide

## Interfaces

```go
// Define where consumed, not implemented. Accept interfaces, return structs.
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

// Small interfaces (1-3 methods), compose larger ones
type Reader interface { Read(ctx context.Context, id string) (*Entity, error) }
type Writer interface { Save(ctx context.Context, entity *Entity) error }
type ReadWriter interface { Reader; Writer }

// Verify compliance at compile time
var _ Notifier = (*SlackNotifier)(nil)

// Use stdlib interfaces: io.Reader, io.Writer, fmt.Stringer, error, sort.Interface
func Export(w io.Writer, data []Report) error {
    encoder := json.NewEncoder(w)
    for _, r := range data { if err := encoder.Encode(r); err != nil { return err } }
    return nil
}
```

- Consumers accept smallest interface needed
- >5 methods = split the interface
- Return concrete types from constructors

## Struct Embedding and Composition

```go
type BaseRepository struct {
    db  *sqlx.DB
    log *slog.Logger
}
func (r *BaseRepository) withTx(ctx context.Context, fn func(*sqlx.Tx) error) error {
    tx, err := r.db.BeginTxx(ctx, nil)
    if err != nil { return err }
    if err := fn(tx); err != nil { _ = tx.Rollback(); return err }
    return tx.Commit()
}
type UserRepository struct { BaseRepository }
```

## Context Propagation

```go
// Every I/O function takes ctx as first parameter
func (r *UserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    var user User
    if err := r.db.GetContext(ctx, &user, "SELECT * FROM users WHERE id=$1", id); err != nil {
        return nil, err
    }
    return &user, nil
}

// Context values: request-scoped metadata only (request ID, tenant ID, auth user)
type contextKey string
const requestIDKey contextKey = "request_id"

func RequestIDMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        reqID := r.Header.Get("X-Request-ID")
        if reqID == "" { reqID = uuid.New().String() }
        ctx := context.WithValue(r.Context(), requestIDKey, reqID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

func RequestIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(requestIDKey).(string); ok { return v }
    return "unknown"
}
```

- Always `defer cancel()` after WithTimeout/WithCancel
- Never store DB connections, loggers, mutable objects in context
- Check `ctx.Done()` in long loops/streaming ops
- Check remaining time budget before expensive work
- Unexported key types prevent cross-package collisions

## Concurrency

```go
// errgroup: managed goroutines with error propagation + context cancellation
func fetchAll(ctx context.Context, ids []string) ([]*Item, error) {
    g, ctx := errgroup.WithContext(ctx)
    results := make([]*Item, len(ids))
    for i, id := range ids {
        i, id := i, id
        g.Go(func() error {
            item, err := fetch(ctx, id)
            if err != nil { return fmt.Errorf("fetch %s: %w", id, err) }
            results[i] = item
            return nil
        })
    }
    if err := g.Wait(); err != nil { return nil, err }
    return results, nil
}

// Channels for producer-consumer
func pipeline(ctx context.Context, input <-chan Job) <-chan Result {
    out := make(chan Result)
    go func() {
        defer close(out)
        for job := range input {
            select {
            case <-ctx.Done(): return
            case out <- process(job):
            }
        }
    }()
    return out
}

// Channel direction: <-chan T (receive), chan<- T (send) — prevents misuse at compile time
// Producer returns <-chan, consumer accepts <-chan, pipeline stage: <-chan in, <-chan out

// sync.Mutex for shared state
type Counter struct { mu sync.Mutex; count int }
func (c *Counter) Increment() { c.mu.Lock(); defer c.mu.Unlock(); c.count++ }
```

- Use `errgroup` for parallel ops with error collection; `SetLimit(n)` for bounded concurrency
- Channels for communication, mutexes for shared state
- Never start goroutine without clear lifecycle (who stops it, when, how)
- Close channels from producer, never consumer

### Worker Pool Pattern

```go
type WorkerPool[T any] struct {
    workers int
    jobs    chan T
    handler func(context.Context, T) error
    log     *slog.Logger
}

func (p *WorkerPool[T]) Run(ctx context.Context) error {
    g, ctx := errgroup.WithContext(ctx)
    for i := 0; i < p.workers; i++ {
        workerID := i
        g.Go(func() error {
            for { select {
            case <-ctx.Done(): return ctx.Err()
            case job, ok := <-p.jobs:
                if !ok { return nil }
                if err := p.handler(ctx, job); err != nil {
                    p.log.Error("job failed", slog.Int("worker", workerID), slog.String("error", err.Error()))
                }
            }}
        })
    }
    return g.Wait()
}
```

### Fan-Out/Fan-In

```go
func FanOutFanIn[T, R any](ctx context.Context, items []T, workers int, process func(context.Context, T) (R, error)) ([]R, error) {
    jobs := make(chan T, len(items))
    results := make(chan Result[R], len(items))
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() { defer wg.Done(); for job := range jobs { r, err := process(ctx, job); results <- Result[R]{value: r, err: err} } }()
    }
    for _, item := range items { jobs <- item }
    close(jobs)
    go func() { wg.Wait(); close(results) }()
    var collected []R
    for r := range results { if r.err != nil { return nil, r.err }; collected = append(collected, r.value) }
    return collected, nil
}
```

### sync.Once, sync.Map

```go
// sync.Once for lazy init
var connectDB = sync.OnceValues(func() (*sqlx.DB, error) {
    return sqlx.Connect("pgx", os.Getenv("DATABASE_URL"))
})

// sync.Map: write-once/read-many cache; for everything else use RWMutex + map
type SafeCounter struct {
    mu       sync.RWMutex
    counters map[string]int64
}
func (c *SafeCounter) Increment(key string) { c.mu.Lock(); defer c.mu.Unlock(); c.counters[key]++ }
func (c *SafeCounter) Get(key string) int64  { c.mu.RLock(); defer c.mu.RUnlock(); return c.counters[key] }
```

## Testing Patterns

```go
// Table-driven tests with subtests
func TestParseAmount(t *testing.T) {
    t.Parallel()
    tests := []struct {
        name string; input string; want int64; wantErr bool
    }{
        {"valid cents", "12.34", 1234, false},
        {"negative", "-5.00", -500, false},
        {"invalid", "abc", 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got, err := ParseAmount(tt.input)
            if tt.wantErr { require.Error(t, err); return }
            require.NoError(t, err)
            assert.Equal(t, tt.want, got)
        })
    }
}

// Test helpers with t.Helper() — failures report caller's line
func createTestUser(t *testing.T, db *sqlx.DB) *User {
    t.Helper()
    user := &User{ID: uuid.New().String(), Email: "test@example.com"}
    _, err := db.Exec("INSERT INTO users (id, email) VALUES ($1, $2)", user.ID, user.Email)
    require.NoError(t, err)
    t.Cleanup(func() { _, _ = db.Exec("DELETE FROM users WHERE id = $1", user.ID) })
    return user
}

// Integration tests with testcontainers
func TestUserRepo_Integration(t *testing.T) {
    if testing.Short() { t.Skip("skipping integration test") }
    ctx := context.Background()
    pgContainer, err := postgres.RunContainer(ctx, testcontainers.WithImage("postgres:16-alpine"), postgres.WithDatabase("testdb"))
    require.NoError(t, err)
    t.Cleanup(func() { _ = pgContainer.Terminate(ctx) })
    connStr, _ := pgContainer.ConnectionString(ctx, "sslmode=disable")
    db := sqlx.MustConnect("pgx", connStr)
    // ... test against real PostgreSQL
}

// Golden files for snapshot testing
func TestRenderTemplate(t *testing.T) {
    got := renderTemplate(data)
    golden := filepath.Join("testdata", t.Name()+".golden")
    if *update { os.WriteFile(golden, []byte(got), 0644) }
    want, _ := os.ReadFile(golden)
    assert.Equal(t, string(want), got)
}

// Mock without framework
type MockMailer struct {
    SendFunc func(ctx context.Context, to, subject, body string) error
    Calls    []MailerCall
}
func (m *MockMailer) Send(ctx context.Context, to, subject, body string) error {
    m.Calls = append(m.Calls, MailerCall{To: to, Subject: subject, Body: body})
    if m.SendFunc != nil { return m.SendFunc(ctx, to, subject, body) }
    return nil
}
```

- `testify/assert` non-fatal, `testify/require` fatal
- `t.Parallel()` on independent tests; `t.Cleanup()` for teardown
- `testcontainers` for integration tests; `-short` flag to skip them
- Golden files in `testdata/` for complex outputs

## Structured Logging with slog

```go
// JSON handler for prod, text for dev — stdlib since Go 1.21
func NewLogger(env string) *slog.Logger {
    if env == "production" || env == "staging" {
        return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo, AddSource: true}))
    }
    return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelDebug}))
}

// Typed attributes
log.Info("order created", slog.String("order_id", order.ID), slog.Int("item_count", len(order.Items)), slog.Duration("processing_time", elapsed))

// Child loggers with common attributes
reqLog := baseLog.With(slog.String("request_id", reqID), slog.String("method", r.Method))

// Request-scoped logger via context
type loggerKey struct{}
func ContextWithLogger(ctx context.Context, log *slog.Logger) context.Context { return context.WithValue(ctx, loggerKey{}, log) }
func LoggerFromContext(ctx context.Context) *slog.Logger {
    if log, ok := ctx.Value(loggerKey{}).(*slog.Logger); ok { return log }
    return slog.Default()
}
```

- Log at point of handling, not every layer (avoid duplicates)
- Include IDs, counts, durations for debuggability
- Never log sensitive data (passwords, tokens, PII)
- Use structured fields, never fmt.Sprintf in messages

## Dependency Injection

```go
// Wire manually in cmd/server/main.go — no DI framework
func main() {
    cfg := config.Load()
    db := postgres.Connect(cfg.DSN)
    log := logger.New(cfg.Env)
    userRepo := repository.NewUserRepository(db, log)
    userSvc  := service.NewUserService(userRepo, mailer, log)
    handler  := handler.NewUserHandler(userSvc, log)
    srv := server.New(handler, cfg.Port)
    srv.Run()
}
```

## Generics (Go 1.18+)

```go
// Generic utilities
func Filter[T any](items []T, predicate func(T) bool) []T {
    result := make([]T, 0, len(items)/2)
    for _, item := range items { if predicate(item) { result = append(result, item) } }
    return result
}
func Map[T, U any](items []T, fn func(T) U) []U {
    result := make([]U, len(items))
    for i, item := range items { result[i] = fn(item) }
    return result
}

// Generic repository
type Repository[T any] struct { db *sqlx.DB; tableName string; log *slog.Logger }
func (r *Repository[T]) FindByID(ctx context.Context, id string) (*T, error) {
    var entity T
    query := fmt.Sprintf("SELECT * FROM %s WHERE id = $1 AND deleted_at IS NULL", r.tableName)
    if err := r.db.GetContext(ctx, &entity, query, id); err != nil {
        if errors.Is(err, sql.ErrNoRows) { return nil, ErrNotFound }
        return nil, fmt.Errorf("find %s by id: %w", r.tableName, err)
    }
    return &entity, nil
}

// Result/Option types
type Result[T any] struct { value T; err error }
func Ok[T any](value T) Result[T]    { return Result[T]{value: value} }
func Err[T any](err error) Result[T] { return Result[T]{err: err} }

// Constraints: use cmp.Ordered (Go 1.21+) or custom
type Identifiable interface { ID() string }
func IndexByID[T Identifiable](items []T) map[string]T {
    m := make(map[string]T, len(items))
    for _, item := range items { m[item.ID()] = item }
    return m
}
```

- Use generics for identical operations across types (collections, utilities)
- Use interfaces for different behavior (polymorphism, DI)
- Don't use generics when `any` is the only constraint

## Module & Lint Conventions

- Module path: `github.com/org/repo`
- One `go.mod` per service or per monorepo workspace
- Run `go mod tidy` before every commit
- golangci-lint: enable `errcheck`, `govet`, `staticcheck`, `revive`, `gosec`, `exhaustive`

## Performance

```go
// sync.Pool for frequent short-lived allocations
var bufPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}

// Pre-allocate slices/maps when size known
ids := make([]string, 0, len(users))

// strings.Builder for concatenation — never + in loops
var b strings.Builder
b.Grow(len(fields) * 20)
```

- Avoid `reflect` in hot paths (10-100x slower)
- Profile with `pprof` before optimizing
- Reuse `http.Client` and `*sql.DB` — they manage pools internally
- Pre-allocate maps: `make(map[K]V, expectedSize)`

## Critical Rules

- Always handle errors — `errcheck` lint rule enforces this
- Never use `init()` for side effects — inject dependencies explicitly
- Use `slog` (stdlib) for structured logging; pass logger via struct, not global
- Use `any` not `interface{}` (Go 1.18+)
- Run `go vet` and `staticcheck` in CI
- Use `context.Context` as first parameter for all I/O
- Accept interfaces, return structs
- Prefer `errgroup` over manual WaitGroup+channels
- Channel direction in signatures prevents misuse
