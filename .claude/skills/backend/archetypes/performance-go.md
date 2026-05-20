---
skill: performance-go
description: Go performance patterns — connection pooling, memory management, concurrency tuning, profiling (pprof), hot path optimization, database performance, benchmarking
version: "1.0"
tags:
  - go
  - performance
  - profiling
  - pprof
  - connection-pooling
  - concurrency
  - benchmarking
  - archetype
  - backend
---

# Go Performance Archetype

> **CANONICAL REFERENCE**: This file is the single source of truth for Go performance patterns. Every generated Go service MUST follow these patterns for connection pooling, memory management, concurrency, and profiling.

---

## 1. Connection Pooling

### 1.1 database/sql Pool Settings

```go
package database

import (
    "database/sql"
    "fmt"
    "time"

    _ "github.com/jackc/pgx/v5/stdlib" // pgx via database/sql
)

// OpenDB opens a connection pool with production-tuned settings.
// Rule of thumb for MaxOpenConns:
//   - Start with (2 * CPU cores) + effective_io_concurrency
//   - For a 4-core container with SSD: (2 * 4) + 4 = 12
//   - Monitor db.pool.wait_count; if non-zero under normal load, increase
//   - Never exceed PostgreSQL max_connections / number_of_app_instances
func OpenDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("pgx", dsn)
    if err != nil {
        return nil, fmt.Errorf("opening database: %w", err)
    }

    // Pool sizing — tune based on workload and instance count
    db.SetMaxOpenConns(25)               // Max simultaneous connections
    db.SetMaxIdleConns(10)               // Keep warm connections ready (40% of max)
    db.SetConnMaxLifetime(5 * time.Minute) // Recycle connections (catches DNS/failover changes)
    db.SetConnMaxIdleTime(1 * time.Minute) // Close idle connections sooner to free DB slots

    // Verify the connection works
    if err := db.PingContext(context.Background()); err != nil {
        db.Close()
        return nil, fmt.Errorf("pinging database: %w", err)
    }

    return db, nil
}

// Monitoring: expose db.Stats() as metrics (see observability-go.md section 2.4)
//   db.Stats().OpenConnections  → db.pool.open_connections
//   db.Stats().InUse            → db.pool.in_use
//   db.Stats().Idle             → db.pool.idle
//   db.Stats().WaitCount        → db.pool.wait_count (non-zero = pool exhaustion)
//   db.Stats().WaitDuration     → db.pool.wait_duration
```

### 1.2 pgx Pool Configuration (Direct)

```go
package database

import (
    "context"
    "fmt"
    "time"

    "github.com/jackc/pgx/v5/pgxpool"
)

// NewPgxPool creates a pgx connection pool with fine-grained control.
// Prefer pgxpool over database/sql when you need:
//   - COPY protocol (bulk inserts)
//   - LISTEN/NOTIFY
//   - Custom type registration
//   - Explicit prepared statement caching
func NewPgxPool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
    cfg, err := pgxpool.ParseConfig(dsn)
    if err != nil {
        return nil, fmt.Errorf("parsing pool config: %w", err)
    }

    cfg.MaxConns = 25
    cfg.MinConns = 5                           // Keep at least 5 warm connections
    cfg.MaxConnLifetime = 5 * time.Minute
    cfg.MaxConnIdleTime = 1 * time.Minute
    cfg.HealthCheckPeriod = 30 * time.Second   // Periodic connection health check

    // Connection-level settings
    cfg.ConnConfig.ConnectTimeout = 5 * time.Second

    // Prepared statement cache — avoids re-parsing on every query
    // pgx uses LRU by default with 512 entries — usually sufficient
    // cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeCacheDescribe

    pool, err := pgxpool.NewWithConfig(ctx, cfg)
    if err != nil {
        return nil, fmt.Errorf("creating pool: %w", err)
    }

    if err := pool.Ping(ctx); err != nil {
        pool.Close()
        return nil, fmt.Errorf("pinging pool: %w", err)
    }

    return pool, nil
}
```

### 1.3 Redis Pool (go-redis)

```go
package cache

import (
    "context"
    "time"

    "github.com/redis/go-redis/v9"
)

// NewRedisClient creates a Redis client with production pool settings.
func NewRedisClient(addr, password string) *redis.Client {
    return redis.NewClient(&redis.Options{
        Addr:     addr,
        Password: password,
        DB:       0,

        // Pool settings
        PoolSize:     20,                  // Max connections (10 * GOMAXPROCS is a good start)
        MinIdleConns: 5,                   // Keep warm connections
        MaxIdleConns: 10,                  // Max idle connections before cleanup
        PoolTimeout:  4 * time.Second,     // Wait for a pool slot before failing
        ConnMaxIdleTime: 5 * time.Minute,  // Close idle connections

        // Timeouts
        DialTimeout:  5 * time.Second,
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,

        // Retry
        MaxRetries:      3,
        MinRetryBackoff: 8 * time.Millisecond,
        MaxRetryBackoff: 512 * time.Millisecond,
    })
}

// For Redis Cluster:
func NewRedisClusterClient(addrs []string) *redis.ClusterClient {
    return redis.NewClusterClient(&redis.ClusterOptions{
        Addrs:        addrs,
        PoolSize:     20,
        MinIdleConns: 5,
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,
        MaxRetries:   3,
        RouteByLatency: true, // Route reads to the closest node
    })
}
```

### 1.4 HTTP Client with Connection Reuse

```go
package httpclient

import (
    "net"
    "net/http"
    "time"
)

// NewHTTPClient creates an HTTP client with connection pooling tuned
// for making outbound API calls from a backend service.
// NEVER use http.DefaultClient in production — it has no timeouts.
func NewHTTPClient() *http.Client {
    transport := &http.Transport{
        // Connection pool
        MaxIdleConns:        100,              // Total idle connections across all hosts
        MaxIdleConnsPerHost: 20,               // Per-host idle connections (default is only 2!)
        MaxConnsPerHost:     50,               // Per-host concurrent connection limit
        IdleConnTimeout:     90 * time.Second, // Close idle connections after 90s

        // Connection setup
        DialContext: (&net.Dialer{
            Timeout:   5 * time.Second,  // TCP connection timeout
            KeepAlive: 30 * time.Second, // TCP keep-alive interval
        }).DialContext,

        // TLS handshake
        TLSHandshakeTimeout: 5 * time.Second,

        // Response headers
        ResponseHeaderTimeout: 10 * time.Second,
        ExpectContinueTimeout: 1 * time.Second,

        // HTTP/2 — enabled by default when using TLS
        ForceAttemptHTTP2: true,

        // Disable compression to avoid decompression CPU cost if payloads are small
        // DisableCompression: true,
    }

    return &http.Client{
        Transport: transport,
        Timeout:   30 * time.Second, // Overall request timeout (including redirects)
        // Do NOT follow redirects for API clients:
        CheckRedirect: func(req *http.Request, via []*http.Request) error {
            return http.ErrUseLastResponse
        },
    }
}
```

---

## 2. Memory Management

### 2.1 sync.Pool for Hot-Path Allocations

```go
package encoding

import (
    "bytes"
    "encoding/json"
    "sync"
)

// bufferPool reuses byte buffers to avoid per-request allocations.
// Use for any hot path that allocates temporary buffers (JSON encoding,
// template rendering, response building).
var bufferPool = sync.Pool{
    New: func() any {
        return bytes.NewBuffer(make([]byte, 0, 4096)) // pre-allocate 4KB
    },
}

// MarshalJSON encodes v as JSON using a pooled buffer.
func MarshalJSON(v any) ([]byte, error) {
    buf := bufferPool.Get().(*bytes.Buffer)
    buf.Reset()
    defer bufferPool.Put(buf)

    enc := json.NewEncoder(buf)
    enc.SetEscapeHTML(false) // avoid unnecessary escaping overhead
    if err := enc.Encode(v); err != nil {
        return nil, err
    }

    // Copy the buffer contents — the buffer goes back to the pool.
    result := make([]byte, buf.Len())
    copy(result, buf.Bytes())
    return result, nil
}

// For HTTP response writing (avoids the copy):
func WriteJSON(w http.ResponseWriter, status int, v any) error {
    buf := bufferPool.Get().(*bytes.Buffer)
    buf.Reset()
    defer bufferPool.Put(buf)

    enc := json.NewEncoder(buf)
    enc.SetEscapeHTML(false)
    if err := enc.Encode(v); err != nil {
        return err
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    _, err := w.Write(buf.Bytes())
    return err
}
```

### 2.2 Avoid Allocations in Tight Loops

```go
// BAD — allocates a new slice on each iteration
func processItemsBad(items []Item) []Result {
    var results []Result // nil slice, grows dynamically
    for _, item := range items {
        results = append(results, process(item)) // may re-allocate and copy
    }
    return results
}

// GOOD — pre-allocate with known capacity
func processItemsGood(items []Item) []Result {
    results := make([]Result, 0, len(items)) // single allocation
    for _, item := range items {
        results = append(results, process(item)) // no re-allocation
    }
    return results
}

// GOOD — pre-allocate map when size is known
func buildIndexGood(items []Item) map[string]*Item {
    index := make(map[string]*Item, len(items)) // single allocation
    for i := range items {
        index[items[i].ID] = &items[i]
    }
    return index
}

// BAD — string concatenation in a loop
func buildCSVBad(values []string) string {
    result := ""
    for _, v := range values {
        result += v + "," // O(n^2) — allocates new string each time
    }
    return result
}

// GOOD — use strings.Builder
func buildCSVGood(values []string) string {
    var b strings.Builder
    b.Grow(len(values) * 20) // estimate average field length
    for i, v := range values {
        if i > 0 {
            b.WriteByte(',')
        }
        b.WriteString(v)
    }
    return b.String()
}
```

### 2.3 Pointer vs Value Receivers — When It Matters

```go
// Use VALUE receivers when:
//   - The type is small (< 64 bytes, fits in a few registers)
//   - The method does not modify the receiver
//   - The type is a primitive wrapper (time.Time, net.IP)

type Point struct {
    X, Y float64 // 16 bytes — small, use value receiver
}

func (p Point) Distance(other Point) float64 {
    dx := p.X - other.X
    dy := p.Y - other.Y
    return math.Sqrt(dx*dx + dy*dy)
}

// Use POINTER receivers when:
//   - The method modifies the receiver
//   - The type is large (contains slices, maps, or many fields)
//   - The type is used in sync.Pool, interfaces, or needs identity
//   - Consistency: if ANY method needs a pointer receiver, use pointer for ALL methods

type Order struct {
    ID        string
    TenantID  string
    Items     []OrderItem // slice header = 24 bytes, but data can be large
    Total     decimal.Decimal
    Status    string
    CreatedAt time.Time
    // 100+ bytes — use pointer receiver
}

func (o *Order) AddItem(item OrderItem) {
    o.Items = append(o.Items, item)
    o.recalculateTotal()
}
```

### 2.4 Escape Analysis Awareness

```go
// The Go compiler decides whether to allocate on stack or heap.
// Stack allocation is free (no GC pressure). Heap allocation costs GC time.
// Run: go build -gcflags='-m' ./... to see escape analysis decisions.
// Common escape causes:
//   1. Returning a pointer to a local variable
//   2. Storing in an interface{}/any
//   3. Slice/map grows beyond initial capacity
//   4. Closures capturing variables
//   5. Sending to a channel

// ESCAPES (heap allocated) — pointer returned to caller
func newOrderBad() *Order {
    o := Order{ID: "123"} // escapes to heap because we return &o
    return &o
}

// DOES NOT ESCAPE if inlined — value returned
func newOrderGood() Order {
    return Order{ID: "123"} // stays on stack if caller doesn't take address
}

// ESCAPES — stored in interface
func logBad(v any) { // any = interface{}, forces heap allocation of v
    fmt.Println(v)
}

// Tip: slog avoids this by using slog.Attr which is a concrete type.
// Prefer slog over fmt.Sprintf or interface{}-based loggers in hot paths.
```

---

## 3. Concurrency Performance

### 3.1 GOMAXPROCS Tuning for Containers

```go
package main

import (
    _ "go.uber.org/automaxprocs" // Automatically sets GOMAXPROCS to match cgroup CPU quota
)

// Container CPU limits use cgroups. By default, GOMAXPROCS = host CPU count,
// which is wrong in containers. For example:
//   Host: 64 cores, Container limit: 2 CPUs
//   Default GOMAXPROCS: 64 (too many threads, cache thrashing, scheduling overhead)
//   With automaxprocs: 2 (correct)
// Simply importing go.uber.org/automaxprocs fixes this automatically.
// The import init() reads /sys/fs/cgroup and adjusts.
// Manual override if needed:
//   runtime.GOMAXPROCS(2)
//   or: GOMAXPROCS=2 environment variable
```

### 3.2 Worker Pool Pattern

```go
package worker

import (
    "context"
    "sync"
)

// Pool manages a fixed number of goroutines processing tasks from a channel.
// Sizing guidelines:
//   CPU-bound work:  workers = GOMAXPROCS (number of available CPUs)
//   IO-bound work:   workers = 10 * GOMAXPROCS (goroutines spend most time waiting)
//   Mixed:           Start with 2-5 * GOMAXPROCS, benchmark to tune
type Pool[T any] struct {
    workers int
    tasks   chan T
    handler func(context.Context, T) error
    wg      sync.WaitGroup
}

func NewPool[T any](workers, bufferSize int, handler func(context.Context, T) error) *Pool[T] {
    return &Pool[T]{
        workers: workers,
        tasks:   make(chan T, bufferSize), // buffered channel prevents producer blocking
        handler: handler,
    }
}

// Start launches worker goroutines. They run until ctx is cancelled or Stop is called.
func (p *Pool[T]) Start(ctx context.Context) {
    for i := 0; i < p.workers; i++ {
        p.wg.Add(1)
        go func(workerID int) {
            defer p.wg.Done()
            for {
                select {
                case task, ok := <-p.tasks:
                    if !ok {
                        return // channel closed
                    }
                    if err := p.handler(ctx, task); err != nil {
                        // Log error but continue processing
                        slog.ErrorContext(ctx, "worker task failed",
                            "worker_id", workerID,
                            "error", err,
                        )
                    }
                case <-ctx.Done():
                    return
                }
            }
        }(i)
    }
}

// Submit sends a task to the pool. Blocks if the buffer is full.
func (p *Pool[T]) Submit(task T) {
    p.tasks <- task
}

// Stop closes the task channel and waits for all workers to finish.
func (p *Pool[T]) Stop() {
    close(p.tasks)
    p.wg.Wait()
}

// Usage:
//   pool := NewPool[Order](runtime.GOMAXPROCS(0)*10, 1000, processOrder)
//   pool.Start(ctx)
//   for _, order := range orders {
//       pool.Submit(order)
//   }
//   pool.Stop()
```

### 3.3 Channel Buffer Sizing

```go
// Unbuffered (capacity 0):
//   ch := make(chan T)
//   Use when: synchronization is needed, producer waits for consumer.
//   Example: signal channels, done channels, request-response patterns.

// Small buffer (1-10):
//   ch := make(chan T, 1)
//   Use when: slight decoupling, producer occasionally faster than consumer.
//   Example: result channels from goroutines.

// Medium buffer (100-1000):
//   ch := make(chan T, 500)
//   Use when: known burst patterns, fan-in from multiple producers.
//   Example: event bus, log aggregation.

// Large buffer (1000+):
//   ch := make(chan T, 10000)
//   Use when: high-throughput pipelines with tolerance for backpressure delay.
//   Example: message queue consumer, metric aggregation.
//   Warning: large buffers hide backpressure problems. Monitor queue depth.
```

### 3.4 Mutex Contention Reduction

```go
package cache

import (
    "sync"
    "sync/atomic"
    "hash/fnv"
)

// --- Approach 1: Atomic operations (lock-free, fastest) ---

type AtomicCounter struct {
    value atomic.Int64
}

func (c *AtomicCounter) Increment() int64 { return c.value.Add(1) }
func (c *AtomicCounter) Get() int64       { return c.value.Load() }

// --- Approach 2: RWMutex for read-heavy workloads ---

type ReadHeavyCache[V any] struct {
    mu    sync.RWMutex
    items map[string]V
}

func (c *ReadHeavyCache[V]) Get(key string) (V, bool) {
    c.mu.RLock() // multiple readers can hold RLock simultaneously
    defer c.mu.RUnlock()
    v, ok := c.items[key]
    return v, ok
}

func (c *ReadHeavyCache[V]) Set(key string, value V) {
    c.mu.Lock() // exclusive lock only for writes
    defer c.mu.Unlock()
    c.items[key] = value
}

// --- Approach 3: Sharded map (reduces contention under high write load) ---

const shardCount = 32

type ShardedMap[V any] struct {
    shards [shardCount]struct {
        mu    sync.RWMutex
        items map[string]V
    }
}

func NewShardedMap[V any]() *ShardedMap[V] {
    sm := &ShardedMap[V]{}
    for i := range sm.shards {
        sm.shards[i].items = make(map[string]V)
    }
    return sm
}

func (sm *ShardedMap[V]) shard(key string) uint32 {
    h := fnv.New32a()
    h.Write([]byte(key))
    return h.Sum32() % shardCount
}

func (sm *ShardedMap[V]) Get(key string) (V, bool) {
    s := &sm.shards[sm.shard(key)]
    s.mu.RLock()
    defer s.mu.RUnlock()
    v, ok := s.items[key]
    return v, ok
}

func (sm *ShardedMap[V]) Set(key string, value V) {
    s := &sm.shards[sm.shard(key)]
    s.mu.Lock()
    defer s.mu.Unlock()
    s.items[key] = value
}

// --- Approach 4: sync.Map (read-heavy with stable key set) ---
// Use sync.Map when:
//   - Keys are mostly read after an initial write phase
//   - Many goroutines read/write disjoint key sets
// Do NOT use sync.Map for general-purpose caching (sharded map is better).
```

---

## 4. Profiling

### 4.1 pprof Setup

```go
package main

import (
    "net/http"
    _ "net/http/pprof" // registers /debug/pprof/* handlers
)

// servePprof starts the pprof server on a separate port.
// NEVER expose pprof on the public-facing port.
func servePprof(addr string) *http.Server {
    mux := http.DefaultServeMux // pprof registers on DefaultServeMux

    srv := &http.Server{Addr: addr, Handler: mux}
    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("pprof server failed", "error", err)
        }
    }()
    return srv
}

// In main.go:
//   pprofSrv := servePprof(":6060")
//   defer pprofSrv.Shutdown(context.Background())
```

### 4.2 CPU Profile Analysis

```bash
# Capture 30-second CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Interactive commands inside pprof:
#   top 20          — show top 20 CPU-consuming functions
#   list funcName   — show annotated source code
#   web             — open flame graph in browser (needs graphviz)
#   png > cpu.png   — save flame graph as PNG

# One-liner for flame graph:
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30
# Opens browser at http://localhost:8081 with flame graph, top, source views
```

### 4.3 Memory / Heap Profile

```bash
# Current heap allocation snapshot
go tool pprof http://localhost:6060/debug/pprof/heap

# Interactive commands:
#   top 20 -cum             — top allocating functions (cumulative)
#   top 20 -inuse_space     — what's currently on the heap
#   top 20 -alloc_space     — total bytes allocated over time (includes freed)
#   top 20 -alloc_objects   — total objects allocated (find allocation-heavy code)

# Common investigation flow:
#   1. Check -inuse_space to find what's consuming heap NOW
#   2. Check -alloc_objects to find allocation-heavy hot paths
#   3. Use list funcName to see which lines allocate
#   4. Fix: use sync.Pool, pre-allocate slices, avoid interface{} in hot paths

# Compare two heap snapshots to find leaks:
go tool pprof -base heap1.prof heap2.prof
```

### 4.4 Goroutine Profile (Detect Leaks)

```bash
# See all goroutines and their stack traces
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Or get a plain-text dump:
curl http://localhost:6060/debug/pprof/goroutine?debug=2

# Signs of goroutine leaks:
#   - Goroutine count increasing over time
#   - Many goroutines stuck in the same stack (blocked on channel/mutex)
#   - Goroutines waiting on a channel that nobody will ever send to
# Monitor goroutine count as a metric (see observability-go.md section 2.4).
# Alert if count exceeds a threshold (e.g., > 10000).
```

### 4.5 Trace Profile for Latency Analysis

```bash
# Capture execution trace (not OTel trace — Go runtime trace)
curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5

# Analyze with go tool trace:
go tool trace trace.out

# Opens a browser showing:
#   - Goroutine analysis (scheduling latency, blocking)
#   - Network/syscall blocking
#   - GC pauses (STW events)
#   - Per-goroutine timeline
# Use when pprof CPU profile doesn't explain latency:
#   - The trace shows WHERE goroutines are waiting (scheduler, GC, syscalls)
#   - pprof shows WHERE CPU time is spent
```

### 4.6 Benchmark Tests

```go
package encoding_test

import (
    "encoding/json"
    "testing"
)

// Basic benchmark
func BenchmarkMarshalJSON(b *testing.B) {
    order := Order{ID: "ord_123", Total: 99.99, Items: make([]Item, 10)}

    b.ReportAllocs() // report allocations per operation
    b.ResetTimer()   // exclude setup time
    for i := 0; i < b.N; i++ {
        _, err := json.Marshal(order)
        if err != nil {
            b.Fatal(err)
        }
    }
}

// Compare implementations with sub-benchmarks
func BenchmarkMarshal(b *testing.B) {
    order := Order{ID: "ord_123", Total: 99.99, Items: make([]Item, 10)}

    b.Run("encoding/json", func(b *testing.B) {
        b.ReportAllocs()
        for i := 0; i < b.N; i++ {
            json.Marshal(order)
        }
    })

    b.Run("pooled-buffer", func(b *testing.B) {
        b.ReportAllocs()
        for i := 0; i < b.N; i++ {
            MarshalJSON(order) // our pooled version
        }
    })
}

// Benchmark with varying input sizes
func BenchmarkProcessItems(b *testing.B) {
    for _, size := range []int{10, 100, 1000, 10000} {
        items := generateItems(size)
        b.Run(fmt.Sprintf("size=%d", size), func(b *testing.B) {
            b.ReportAllocs()
            for i := 0; i < b.N; i++ {
                processItemsGood(items)
            }
        })
    }
}
```

```bash
# Run benchmarks
go test -bench=. -benchmem ./internal/encoding/...

# Output:
# BenchmarkMarshal/encoding/json-8    500000   3012 ns/op   1024 B/op   12 allocs/op
# BenchmarkMarshal/pooled-buffer-8    800000   1876 ns/op    512 B/op    3 allocs/op
#                                                          ^^^^^^^^^    ^^^^^^^^^^^
#                                                          less memory   fewer allocs

# Compare before/after:
go test -bench=. -benchmem -count=10 ./... > old.txt
# (make changes)
go test -bench=. -benchmem -count=10 ./... > new.txt
benchstat old.txt new.txt
# Shows: delta %, confidence interval, statistical significance
```

---

## 5. Hot Path Optimization

### 5.1 Avoid Reflection in Hot Paths

```go
// reflection (reflect package) is 10-100x slower than direct code.
// JSON encoding/decoding uses reflection internally.

// BAD — reflect in hot path
func getFieldBad(v any, field string) any {
    return reflect.ValueOf(v).FieldByName(field).Interface()
}

// GOOD — direct field access (use code generation if needed)
func getOrderID(o *Order) string {
    return o.ID
}

// For JSON: consider code-generated marshalers for hot-path structs.
// Options:
//   - github.com/goccy/go-json (drop-in replacement, 2-3x faster)
//   - github.com/bytedance/sonic (fastest, requires amd64)
//   - github.com/mailru/easyjson (code-gen, zero reflection)
```

### 5.2 Cache Compiled Regexps

```go
package validation

import "regexp"

// BAD — compiles regexp on every call
func validateEmailBad(email string) bool {
    re := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
    return re.MatchString(email)
}

// GOOD — compile once at package init
var emailRegexp = regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)

func validateEmailGood(email string) bool {
    return emailRegexp.MatchString(email)
}

// Note: regexp.MustCompile panics if the pattern is invalid.
```

### 5.3 sync.Map vs Sharded Map vs Regular Map

```go
// Decision matrix:
// | Scenario                       | Best choice     |
// |-------------------------------|-----------------|
// | Read-heavy, stable keys       | sync.Map        |
// | Write-heavy, many goroutines  | ShardedMap      |
// | Single goroutine access       | Regular map     |
// | Low contention (< 4 cores)    | RWMutex + map   |
// | High contention (16+ cores)   | ShardedMap      |
// Benchmark YOUR workload. Contention patterns vary.
```

### 5.4 Binary Search vs Map Lookup

```go
package lookup

import "sort"

// For SMALL sets (< 20 elements), sorted slice + binary search beats map.
// Reason: no hashing overhead, better cache locality.

// Map lookup — O(1) amortized, but hash + bucket overhead
var statusCodes = map[string]int{
    "OK": 200, "CREATED": 201, "BAD_REQUEST": 400, "NOT_FOUND": 404,
}

// Sorted slice + binary search — O(log n), less memory, better cache
type entry struct {
    key   string
    value int
}

var sortedCodes = []entry{
    {"BAD_REQUEST", 400}, {"CREATED", 201}, {"NOT_FOUND", 404}, {"OK", 200},
}

func lookupSorted(key string) (int, bool) {
    i := sort.Search(len(sortedCodes), func(i int) bool {
        return sortedCodes[i].key >= key
    })
    if i < len(sortedCodes) && sortedCodes[i].key == key {
        return sortedCodes[i].value, true
    }
    return 0, false
}

// For very small sets (< 5), a simple linear scan wins:
func lookupLinear(key string) (int, bool) {
    for _, e := range sortedCodes {
        if e.key == key {
            return e.value, true
        }
    }
    return 0, false
}
```

### 5.5 JSON Encoding — Faster Alternatives

```go
// Standard library: encoding/json
//   Pros: stable, zero dependencies
//   Cons: uses reflection, 2-5x slower than alternatives
//   Use: non-hot paths, config parsing, test code

// goccy/go-json (drop-in replacement):
//   import json "github.com/goccy/go-json"
//   Pros: 2-3x faster, same API as encoding/json
//   Cons: external dependency
//   Use: hot paths where you want minimal code changes

// bytedance/sonic:
//   import "github.com/bytedance/sonic"
//   Pros: fastest (JIT + SIMD), 5-10x faster for large payloads
//   Cons: amd64 only, falls back to encoding/json on arm64
//   Use: high-throughput services on amd64 architecture

// mailru/easyjson (code generation):
//   Pros: zero reflection at runtime, very fast
//   Cons: requires code generation step (easyjson -all types.go)
//   Use: when you control the structs and want maximum performance
```

---

## 6. Database Performance

### 6.1 Prepared Statements

```go
// pgx automatically caches prepared statements per connection.
// For database/sql, explicitly prepare hot queries:

func (r *PostgresOrderRepo) init(ctx context.Context) error {
    var err error
    r.stmtGetByID, err = r.db.PrepareContext(ctx,
        `SELECT id, tenant_id, total, status, created_at
         FROM orders WHERE id = $1 AND tenant_id = $2`)
    if err != nil {
        return fmt.Errorf("preparing get-by-id: %w", err)
    }

    r.stmtListByTenant, err = r.db.PrepareContext(ctx,
        `SELECT id, tenant_id, total, status, created_at
         FROM orders WHERE tenant_id = $1
         ORDER BY created_at DESC LIMIT $2 OFFSET $3`)
    if err != nil {
        return fmt.Errorf("preparing list-by-tenant: %w", err)
    }

    return nil
}

// Usage — avoids parse + plan on every execution:
func (r *PostgresOrderRepo) FindByID(ctx context.Context, tenantID, id string) (*Order, error) {
    row := r.stmtGetByID.QueryRowContext(ctx, id, tenantID)
    // ...scan...
}
```

### 6.2 Batch Inserts (COPY Protocol via pgx)

```go
package repository

import (
    "context"

    "github.com/jackc/pgx/v5"
)

// BulkInsertOrders uses PostgreSQL COPY protocol — 10-100x faster than
// individual INSERTs for large batches.
func (r *PgxOrderRepo) BulkInsertOrders(ctx context.Context, orders []Order) (int64, error) {
    ctx, span := tracer.Start(ctx, "postgres.orders.bulk_insert",
        trace.WithAttributes(
            attribute.Int("batch_size", len(orders)),
        ),
    )
    defer span.End()

    rows := make([][]any, len(orders))
    for i, o := range orders {
        rows[i] = []any{o.ID, o.TenantID, o.UserID, o.Total, o.Currency, o.Status, o.CreatedAt}
    }

    copyCount, err := r.pool.CopyFrom(ctx,
        pgx.Identifier{"orders"},
        []string{"id", "tenant_id", "user_id", "total", "currency", "status", "created_at"},
        pgx.CopyFromRows(rows),
    )
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return 0, fmt.Errorf("bulk insert orders: %w", err)
    }

    span.SetAttributes(attribute.Int64("rows_inserted", copyCount))
    return copyCount, nil
}

// For moderate batches (10-100 rows), multi-value INSERT is simpler:
func (r *PgxOrderRepo) BatchInsert(ctx context.Context, orders []Order) error {
    batch := &pgx.Batch{}
    for _, o := range orders {
        batch.Queue(
            `INSERT INTO orders (id, tenant_id, total, status) VALUES ($1, $2, $3, $4)`,
            o.ID, o.TenantID, o.Total, o.Status,
        )
    }
    br := r.pool.SendBatch(ctx, batch)
    defer br.Close()

    for range orders {
        if _, err := br.Exec(); err != nil {
            return fmt.Errorf("batch exec: %w", err)
        }
    }
    return nil
}
```

### 6.3 Read Replicas

```go
package database

import "context"

// DBRouter directs reads to replicas and writes to the primary.
type DBRouter struct {
    primary  *pgxpool.Pool
    replicas []*pgxpool.Pool
    next     atomic.Uint64 // round-robin index
}

func NewDBRouter(primaryDSN string, replicaDSNs []string) (*DBRouter, error) {
    ctx := context.Background()

    primary, err := NewPgxPool(ctx, primaryDSN)
    if err != nil {
        return nil, fmt.Errorf("primary pool: %w", err)
    }

    replicas := make([]*pgxpool.Pool, 0, len(replicaDSNs))
    for _, dsn := range replicaDSNs {
        pool, err := NewPgxPool(ctx, dsn)
        if err != nil {
            return nil, fmt.Errorf("replica pool: %w", err)
        }
        replicas = append(replicas, pool)
    }

    return &DBRouter{primary: primary, replicas: replicas}, nil
}

// Writer returns the primary pool (for INSERT, UPDATE, DELETE).
func (r *DBRouter) Writer() *pgxpool.Pool {
    return r.primary
}

// Reader returns a replica pool via round-robin (for SELECT).
// Falls back to primary if no replicas are configured.
func (r *DBRouter) Reader() *pgxpool.Pool {
    if len(r.replicas) == 0 {
        return r.primary
    }
    idx := r.next.Add(1) % uint64(len(r.replicas))
    return r.replicas[idx]
}

// Usage:
//   db := NewDBRouter(primaryDSN, []string{replica1DSN, replica2DSN})
//   // Reads
//   rows, err := db.Reader().Query(ctx, "SELECT ...")
//   // Writes
//   _, err := db.Writer().Exec(ctx, "INSERT INTO ...")
```

### 6.4 Query Result Caching Strategy

```go
package cache

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

// CachedRepo wraps a repository with Redis caching.
// Cache strategy: cache-aside (read-through with manual invalidation on write).
type CachedRepo[T any] struct {
    inner  Repository[T]   // the real database repo
    redis  *redis.Client
    prefix string          // cache key prefix: "orders", "users", etc.
    ttl    time.Duration
}

func NewCachedRepo[T any](inner Repository[T], rdb *redis.Client, prefix string, ttl time.Duration) *CachedRepo[T] {
    return &CachedRepo[T]{inner: inner, redis: rdb, prefix: prefix, ttl: ttl}
}

// FindByID checks cache first, then falls through to DB.
func (c *CachedRepo[T]) FindByID(ctx context.Context, tenantID, id string) (*T, error) {
    key := fmt.Sprintf("%s:%s:%s", c.prefix, tenantID, id)

    // 1. Try cache
    data, err := c.redis.Get(ctx, key).Bytes()
    if err == nil {
        var result T
        if err := json.Unmarshal(data, &result); err == nil {
            return &result, nil // cache hit
        }
        // Unmarshal failed — fall through to DB, delete bad cache entry
        c.redis.Del(ctx, key)
    }

    // 2. Cache miss — query DB
    result, err := c.inner.FindByID(ctx, tenantID, id)
    if err != nil {
        return nil, err
    }

    // 3. Populate cache (fire-and-forget, don't fail the request on cache write error)
    if data, err := json.Marshal(result); err == nil {
        c.redis.Set(ctx, key, data, c.ttl)
    }

    return result, nil
}

// Save writes to DB and invalidates cache.
func (c *CachedRepo[T]) Save(ctx context.Context, tenantID, id string, entity *T) error {
    if err := c.inner.Save(ctx, tenantID, id, entity); err != nil {
        return err
    }

    // Invalidate cache entry (delete, not update — avoids stale data races)
    key := fmt.Sprintf("%s:%s:%s", c.prefix, tenantID, id)
    c.redis.Del(ctx, key)
    return nil
}

// TTL guidelines:
//   - Reference data (categories, config):  5-15 minutes
//   - User profiles:                         1-5 minutes
//   - Search results:                        30-60 seconds
//   - Real-time data (stock, inventory):     Do not cache (or 1-5 seconds)
```

### 6.5 N+1 Query Detection

```go
// N+1 problem: fetching a list, then querying related data per item.

// BAD — N+1: 1 query for orders + N queries for items
func (s *Service) ListOrdersBad(ctx context.Context, tenantID string) ([]OrderWithItems, error) {
    orders, err := s.orderRepo.ListByTenant(ctx, tenantID)
    if err != nil {
        return nil, err
    }

    results := make([]OrderWithItems, len(orders))
    for i, o := range orders {
        items, err := s.itemRepo.ListByOrderID(ctx, o.ID) // N queries!
        if err != nil {
            return nil, err
        }
        results[i] = OrderWithItems{Order: o, Items: items}
    }
    return results, nil
}

// GOOD — Single query with JOIN
func (r *PostgresOrderRepo) ListWithItems(ctx context.Context, tenantID string) ([]OrderWithItems, error) {
    query := `
        SELECT o.id, o.total, o.status, o.created_at,
               i.id AS item_id, i.product_id, i.quantity, i.price
        FROM orders o
        LEFT JOIN order_items i ON i.order_id = o.id
        WHERE o.tenant_id = $1
        ORDER BY o.created_at DESC, i.id`

    rows, err := r.pool.Query(ctx, query, tenantID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    // Group rows by order
    orderMap := make(map[string]*OrderWithItems)
    var result []OrderWithItems
    // ... scan and group ...
    return result, nil
}

// GOOD — Batch lookup with IN clause
func (r *PostgresItemRepo) ListByOrderIDs(ctx context.Context, orderIDs []string) (map[string][]Item, error) {
    query := `SELECT order_id, id, product_id, quantity, price
              FROM order_items WHERE order_id = ANY($1)`

    rows, err := r.pool.Query(ctx, query, orderIDs)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    result := make(map[string][]Item, len(orderIDs))
    for rows.Next() {
        var orderID string
        var item Item
        if err := rows.Scan(&orderID, &item.ID, &item.ProductID, &item.Quantity, &item.Price); err != nil {
            return nil, err
        }
        result[orderID] = append(result[orderID], item)
    }
    return result, nil
}

// Detection: log slow queries (> 50ms) and count queries per request.
// If query count per request > 10, investigate for N+1.
```

---

## Critical Rules

1. **Never use http.DefaultClient** — it has no timeouts. Always configure Transport and Timeout.
2. **Set MaxIdleConnsPerHost** — the default (2) causes connection churn under load. Set to 10-20.
3. **GOMAXPROCS in containers** — import `go.uber.org/automaxprocs` or set manually. Wrong value causes thread contention.
4. **Pre-allocate slices and maps** — use `make([]T, 0, n)` and `make(map[K]V, n)` when size is known.
5. **Profile before optimizing** — use pprof to find actual bottlenecks. Never guess.
6. **Benchmark to validate** — use `testing.B` with `b.ReportAllocs()` to prove improvements.
7. **Monitor connection pools** — export pool stats as metrics. Watch for `WaitCount > 0`.
8. **Cache invalidation on write** — delete cache keys, do not update them. Avoids stale data races.
9. **Batch DB operations** — use COPY for bulk inserts, `ANY($1)` for batch reads. Never loop individual queries.
10. **Avoid reflection in hot paths** — use `slog` (not `fmt.Sprintf`), typed functions (not `any`), and consider go-json or sonic for JSON.
