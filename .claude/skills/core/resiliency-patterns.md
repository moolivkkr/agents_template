---
skill: resiliency-patterns
description: Circuit breakers, idempotent-only retries with jitter and budgets, deadlines, graceful degradation, liveness vs readiness, per-tenant concurrency bulkheads, connection-pool budget, rate limiting, graceful shutdown with preStop drain — production resilience patterns
version: "1.1"
tags:
  - resiliency
  - circuit-breaker
  - retry
  - timeout
  - health-check
  - rate-limiting
  - graceful-shutdown
---

# Resiliency Patterns

Every production service must implement these patterns. External dependencies fail — plan for it.

## Circuit Breakers on ALL External Calls

Every HTTP client, database connection, cache, and message queue call must be wrapped in a circuit breaker. No exceptions.

**States:**
- **Closed** — normal operation, requests pass through. Track failures.
- **Open** — too many failures. Reject requests immediately without calling the dependency. Return fallback or error.
- **Half-Open** — after a timeout, allow one probe request. If it succeeds, close the circuit. If it fails, reopen.

```go
type CircuitState int

const (
    CircuitClosed CircuitState = iota
    CircuitOpen
    CircuitHalfOpen
)

type CircuitBreaker struct {
    name         string
    maxFailures  int
    resetTimeout time.Duration
    state        CircuitState
    failures     int
    lastFailure  time.Time
    mu           sync.RWMutex
    logger       *slog.Logger
}

func NewCircuitBreaker(name string, maxFailures int, resetTimeout time.Duration, logger *slog.Logger) *CircuitBreaker {
    return &CircuitBreaker{
        name:         name,
        maxFailures:  maxFailures,
        resetTimeout: resetTimeout,
        state:        CircuitClosed,
        logger:       logger,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    switch cb.state {
    case CircuitOpen:
        if time.Since(cb.lastFailure) > cb.resetTimeout {
            cb.state = CircuitHalfOpen
            cb.logger.Info("circuit half-open", "name", cb.name)
        } else {
            return fmt.Errorf("circuit breaker %s is open", cb.name)
        }
    }

    cb.mu.Unlock()
    err := fn()
    cb.mu.Lock()

    if err != nil {
        cb.failures++
        cb.lastFailure = time.Now()
        if cb.failures >= cb.maxFailures {
            cb.state = CircuitOpen
            cb.logger.Warn("circuit opened", "name", cb.name, "failures", cb.failures)
        }
        return err
    }

    cb.failures = 0
    cb.state = CircuitClosed
    return nil
}
```

```typescript
enum CircuitState { Closed, Open, HalfOpen }

class CircuitBreaker {
  private state = CircuitState.Closed;
  private failures = 0;
  private lastFailure = 0;

  constructor(
    private readonly name: string,
    private readonly maxFailures: number,
    private readonly resetTimeoutMs: number,
    private readonly logger: Logger,
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.Open) {
      if (Date.now() - this.lastFailure > this.resetTimeoutMs) {
        this.state = CircuitState.HalfOpen;
        this.logger.info(`circuit half-open: ${this.name}`);
      } else {
        throw new CircuitOpenError(this.name);
      }
    }

    try {
      const result = await fn();
      this.failures = 0;
      this.state = CircuitState.Closed;
      return result;
    } catch (err) {
      this.failures++;
      this.lastFailure = Date.now();
      if (this.failures >= this.maxFailures) {
        this.state = CircuitState.Open;
        this.logger.warn(`circuit opened: ${this.name}`, { failures: this.failures });
      }
      throw err;
    }
  }
}
```

**Typical thresholds:**
- `maxFailures`: 5 consecutive failures
- `resetTimeout`: 30 seconds
- Adjust per dependency — database might be 3 failures / 10s, external API might be 5 failures / 60s
- Count only dependency failures (timeouts, 5xx, connection errors) — not 4xx and not the caller's own cancellation
- Allow one probe at a time in half-open; an open breaker returns 503 `UNAVAILABLE` (retryable) fast

## Retry with Exponential Backoff

**Idempotency decides WHETHER a call may be retried; the error decides WHEN.** A timeout or a reset
after the request was sent means the outcome is *unknown*. The payment provider may already have
charged the card. Retrying that POST blind charges it twice (board review 2026-09-30, SRE-03).

| The call is… | Retry on… | Never retry… |
|---|---|---|
| **Idempotent**: GET, HEAD, OPTIONS, PUT, DELETE, or a POST/PATCH that sends an `Idempotency-Key` the callee honours (the **same key** on every attempt) | 429 (honour `Retry-After`), 502, 503, 504, a timeout, connection reset, and "not sent" errors | other 4xx; 500 (usually a bug: retrying repeats it) |
| **Not idempotent** (a POST without a key: charge, email, order, webhook) | only "not sent" errors: connection refused, DNS failure, dial timeout | a timeout or reset after sending, any 5xx. Reconcile instead: look the operation up by its key or reference, or surface `UNAVAILABLE` |

```go
type RetryConfig struct {
    MaxAttempts    int           // total attempts including the first: 3
    BaseDelay      time.Duration // 100ms
    MaxDelay       time.Duration // 2s
    AttemptTimeout time.Duration // per-attempt cap; never longer than what's left of the caller's deadline
}

// Operation describes the call being retried.
type Operation struct {
    Name       string // bounded metric/log label: "payments.charge"
    Idempotent bool   // see the table above
}

func Retry(ctx context.Context, cfg RetryConfig, op Operation, budget *RetryBudget, fn func(ctx context.Context) error) error {
    for attempt := 1; ; attempt++ {
        attemptCtx, cancel := context.WithTimeout(ctx, cfg.AttemptTimeout) // inherits the tighter parent deadline
        err := fn(attemptCtx)
        cancel()
        if err == nil {
            budget.RecordSuccess()
            return nil
        }
        if ctx.Err() != nil || attempt >= cfg.MaxAttempts || !retryable(op, err) {
            return err
        }
        if !budget.TryRetry() { // a brownout must not be multiplied by every caller
            return fmt.Errorf("%s: retry budget exhausted: %w", op.Name, err)
        }
        delay := backoff(cfg, attempt, err)
        if dl, ok := ctx.Deadline(); ok && time.Until(dl) < delay+cfg.AttemptTimeout/4 {
            return err // not enough time left for a useful attempt
        }
        slog.WarnContext(ctx, "retrying", "op", op.Name, "attempt", attempt+1, "delay", delay, "error", err)
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(delay):
        }
    }
}

// retryable: a non-idempotent call is retried only when the request provably never left this process.
func retryable(op Operation, err error) bool {
    if notSent(err) {
        return true
    }
    if !op.Idempotent {
        return false // sent, outcome unknown: a retry can duplicate the side effect
    }
    var he *HTTPError
    if errors.As(err, &he) {
        switch he.StatusCode {
        case http.StatusTooManyRequests, http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
            return true
        }
        return false
    }
    return errors.Is(err, context.DeadlineExceeded) || errors.Is(err, syscall.ECONNRESET)
}

func notSent(err error) bool {
    var dnsErr *net.DNSError
    var opErr *net.OpError
    return errors.Is(err, syscall.ECONNREFUSED) || errors.As(err, &dnsErr) ||
        (errors.As(err, &opErr) && opErr.Op == "dial")
}

// backoff: exponential with FULL jitter, or the server's Retry-After when it sent one.
func backoff(cfg RetryConfig, attempt int, err error) time.Duration {
    ceiling := cfg.BaseDelay << (attempt - 1)
    if ceiling > cfg.MaxDelay || ceiling <= 0 {
        ceiling = cfg.MaxDelay
    }
    d := time.Duration(rand.Int63n(int64(ceiling) + 1))
    var he *HTTPError
    if errors.As(err, &he) && he.RetryAfter > d {
        d = min(he.RetryAfter, cfg.MaxDelay*4)
    }
    return d
}

// RetryBudget allows retries only while they stay under ~10% of successful calls per dependency.
type RetryBudget struct {
    mu                  sync.Mutex
    tokens, max, ratio  float64
}

func NewRetryBudget() *RetryBudget { return &RetryBudget{tokens: 10, max: 10, ratio: 0.1} }

func (b *RetryBudget) RecordSuccess() {
    b.mu.Lock()
    b.tokens = math.Min(b.max, b.tokens+b.ratio)
    b.mu.Unlock()
}

func (b *RetryBudget) TryRetry() bool {
    b.mu.Lock()
    defer b.mu.Unlock()
    if b.tokens < 1 {
        return false
    }
    b.tokens--
    return true
}

// Usage — a charge is a POST: retried safely only because it carries a stable Idempotency-Key.
key := order.PaymentIdempotencyKey // generated once when the order was created, stored with it
err := Retry(ctx, cfg, Operation{Name: "payments.charge", Idempotent: key != ""}, paymentsBudget,
    func(ctx context.Context) error { return payments.Charge(ctx, order, key) })
```

```typescript
interface RetryOptions {
  maxAttempts: number;     // 3
  baseDelayMs: number;     // 100
  maxDelayMs: number;      // 2000
  attemptTimeoutMs: number;
  idempotent: boolean;     // see the table above
  signal?: AbortSignal;    // the caller's deadline
}

const NOT_SENT = new Set(["ECONNREFUSED", "ENOTFOUND", "EAI_AGAIN"]);

function retryable(err: unknown, idempotent: boolean): boolean {
  const code = (err as { code?: string }).code;
  if (code && NOT_SENT.has(code)) return true;          // never reached the server
  if (!idempotent) return false;                        // sent, outcome unknown
  if (err instanceof HttpError) return [429, 502, 503, 504].includes(err.status);
  return code === "ETIMEDOUT" || code === "ECONNRESET" || (err as Error).name === "TimeoutError";
}

async function retry<T>(fn: (signal: AbortSignal) => Promise<T>, o: RetryOptions): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    const attemptSignal = AbortSignal.any([o.signal ?? new AbortController().signal, AbortSignal.timeout(o.attemptTimeoutMs)]);
    try {
      return await fn(attemptSignal);
    } catch (err) {
      if (o.signal?.aborted || attempt >= o.maxAttempts || !retryable(err, o.idempotent)) throw err;
      const ceiling = Math.min(o.maxDelayMs, o.baseDelayMs * 2 ** (attempt - 1));
      const retryAfterMs = err instanceof HttpError ? err.retryAfterMs ?? 0 : 0;
      await sleep(Math.max(Math.random() * ceiling, retryAfterMs), o.signal); // full jitter
    }
  }
}
```

**Rules:**
- Retry only per the table. For a non-idempotent call, send a stable `Idempotency-Key` (generated
  once per business operation and stored with it) or don't retry at all.
- At most 3 attempts, exponential backoff with full jitter, and `Retry-After` honoured.
- Retry in **one** layer only. A client, a service and a gateway each retrying 3 times turns one call
  into 27.
- Keep a retry budget per dependency (about 10% of calls). When it's spent, fail fast and let the
  circuit breaker open.
- Each attempt's timeout fits inside the caller's remaining deadline. Stop when too little time is left.
- Log every retry at WARN. Count retries in a metric labelled by dependency name, which is a bounded set.

## Timeouts at Every Boundary

Every call has a timeout, and **every inbound request has a deadline that its downstream calls
inherit**. Without it, "3 retries × 5 s" compounds at every hop.

```go
// Inbound: server timeouts + a per-request deadline every downstream call inherits
srv := &http.Server{
    Addr:              ":8080",
    Handler:           requestDeadline(10*time.Second, router),
    ReadHeaderTimeout: 5 * time.Second,   // slowloris protection
    ReadTimeout:       15 * time.Second,
    WriteTimeout:      30 * time.Second,  // > the request deadline, so the handler can still write its 503
    IdleTimeout:       120 * time.Second,
}

func requestDeadline(d time.Duration, next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx, cancel := context.WithTimeout(r.Context(), d)
        defer cancel()
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Outbound HTTP client — connection-level timeouts; the per-call deadline comes from ctx
httpClient := &http.Client{
    Timeout: 5 * time.Second, // hard cap; the request ctx is usually tighter
    Transport: &http.Transport{
        DialContext:           (&net.Dialer{Timeout: 2 * time.Second}).DialContext,
        TLSHandshakeTimeout:   2 * time.Second,
        ResponseHeaderTimeout: 3 * time.Second,
        IdleConnTimeout:       90 * time.Second,
        MaxIdleConns:          100,
        MaxIdleConnsPerHost:   10,
    },
}

// Database queries — always pass context with deadline (pool acquisition waits count against it too)
func (r *repo) FindByID(ctx context.Context, id string) (*Entity, error) {
    ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()
    return r.pool.QueryRow(ctx, "SELECT * FROM entities WHERE id = $1", id).Scan(...)
}

// Cache — optional dependency: short timeout, and a timeout is a miss, never a failed request
func (c *redisCache) Get(ctx context.Context, key string) (string, bool) {
    ctx, cancel := context.WithTimeout(ctx, 250*time.Millisecond)
    defer cancel()
    v, err := c.client.Get(ctx, key).Result()
    if err != nil {
        return "", false
    }
    return v, true
}
```

**Default timeouts:**
| Boundary | Timeout | Notes |
|----------|---------|-------|
| Inbound request deadline | 10s | Less than the client's/ingress timeout; downstream calls inherit it |
| HTTP server `ReadHeaderTimeout` | 5s | Slowloris protection |
| HTTP client (external API) | 5s | Adjust per endpoint if needed |
| Database query | 3s | Long reports get their own pool and deadline (counted in the pool budget) |
| DB pool acquire | ≤ 1s | Shorter than the request deadline; a full pool fails fast with 503 |
| Cache (Redis) | 250ms | Optional: on timeout treat as a miss |
| Message queue publish | 2s | Fail fast, buffer locally |
| Internal service call | 3s | Should be fast; if not, investigate |
| gRPC call | 5s | Deadline propagation via context |

**Rules:**
- Always propagate context — never create a new background context inside a request handler
- Always `defer cancel()` after creating a timeout context
- If parent context has a shorter deadline, the parent wins

## Graceful Degradation

When a dependency fails, degrade gracefully — don't crash. Partial data is better than no data.

```go
func (s *ProductService) GetProduct(ctx context.Context, id string) (*Product, error) {
    product, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, err // primary store failure is not degradable
    }

    // Degrade: pricing service down → use cached price
    price, err := s.pricingService.GetPrice(ctx, product.ID)
    if err != nil {
        s.logger.WarnContext(ctx, "pricing service degraded, using cached price",
            "product_id", id, "error", err)
        price = product.CachedPrice // stale but functional
        product.PriceStale = true   // flag for client
    }

    // Degrade: reviews service down → omit reviews
    reviews, err := s.reviewsService.GetReviews(ctx, product.ID)
    if err != nil {
        s.logger.WarnContext(ctx, "reviews service degraded, omitting reviews",
            "product_id", id, "error", err)
        reviews = nil // partial response
    }

    product.Price = price
    product.Reviews = reviews
    return product, nil
}
```

```typescript
async function getProductPage(productId: string): Promise<ProductPage> {
  const product = await productRepo.findById(productId); // required — fail if missing

  // Optional enrichment — degrade gracefully
  const [recommendations, reviews] = await Promise.allSettled([
    recommendationService.getFor(productId),
    reviewService.getFor(productId),
  ]);

  return {
    product,
    recommendations: recommendations.status === 'fulfilled' ? recommendations.value : [],
    reviews: reviews.status === 'fulfilled' ? reviews.value : [],
    degraded: recommendations.status === 'rejected' || reviews.status === 'rejected',
  };
}
```

**Rules:**
- Classify dependencies as required vs. optional
- Required dependency down → return error with appropriate status
- Optional dependency down → return partial response, flag as degraded
- Always log degradation events at WARN level

## Health Checks

Three endpoints with different jobs. One path convention everywhere: `/healthz` (liveness) and
`/readyz` (readiness), which is what the k8s templates probe.

| Endpoint | Question it answers | Checks | Who calls it |
|---|---|---|---|
| `GET /healthz` | Is the process alive and not wedged? | **Nothing external.** Answering proves the event loop or HTTP server works | liveness probe (a failure restarts the pod) |
| `GET /readyz` | Should traffic come here now? | Only **hard** dependencies without which *no* request can succeed (the primary DB), each with its own short timeout, plus the schema version; returns 503 while draining | readiness probe (a failure removes the pod from endpoints) |
| `GET /health/deep` | What is the state of every dependency? | Everything, optional ones included, with latency | dashboards and humans only; internal port or authenticated |

**Optional dependencies never go in readiness.** A cache, a search index, a third-party API or an
analytics sink degrades instead (§Graceful Degradation). Every pod shares those dependencies, so if
Redis blips and readiness checks it, **every pod goes unready at once** and the Service has no
endpoints: a 503 for all traffic, including requests that never touch Redis (SRE-05). For the same
reason liveness never checks the DB: a DB outage would turn into a restart storm.

```go
type HealthHandler struct {
    db       *pgxpool.Pool
    draining atomic.Bool // set on SIGTERM (§Graceful Shutdown)
    logger   *slog.Logger
}

// Liveness — cheap, dependency-free, never blocks on a lock the request path holds.
func (h *HealthHandler) Liveness(w http.ResponseWriter, r *http.Request) {
    writeHealth(w, http.StatusOK, "alive")
}

// Readiness — hard dependencies only, each with its own timeout well under the probe's timeoutSeconds.
func (h *HealthHandler) Readiness(w http.ResponseWriter, r *http.Request) {
    if h.draining.Load() {
        writeHealth(w, http.StatusServiceUnavailable, "draining")
        return
    }
    ctx, cancel := context.WithTimeout(r.Context(), 500*time.Millisecond)
    defer cancel()
    if err := h.db.Ping(ctx); err != nil {
        h.logger.WarnContext(ctx, "readiness: database unreachable", "error", err) // detail in logs only
        writeHealth(w, http.StatusServiceUnavailable, "database_unavailable")
        return
    }
    if v, err := schemaVersion(ctx, h.db); err != nil || v < RequiredSchemaVersion {
        writeHealth(w, http.StatusServiceUnavailable, "schema_not_ready") // new code waits for its migration
        return
    }
    writeHealth(w, http.StatusOK, "ready") // the cache is deliberately NOT checked
}

func writeHealth(w http.ResponseWriter, status int, state string) {
    w.Header().Set("Content-Type", "application/json")
    w.Header().Set("Cache-Control", "no-store")
    w.WriteHeader(status)
    _ = json.NewEncoder(w).Encode(map[string]string{"status": state}) // never err.Error(): it leaks hosts/users
}
```

```typescript
let draining = false; // set on SIGTERM

app.get("/healthz", (_req, res) => res.status(200).json({ status: "alive" }));

app.get("/readyz", async (_req, res) => {
  if (draining) return res.status(503).json({ status: "draining" });
  try {
    await withTimeout(pool.query("SELECT 1"), 500);          // hard dependency only
    res.status(200).json({ status: "ready" });                 // redis is NOT checked here
  } catch (err) {
    logger.warn({ err }, "readiness: database unreachable");  // detail in logs only
    res.status(503).json({ status: "database_unavailable" });
  }
});
```

**Startup:** start the HTTP server first and connect to the DB in the background with bounded backoff
(about 60 s). Until the DB answers, `/readyz` is 503 and `/healthz` is 200. Exiting when the first
connect fails turns a DB restart or a 5-second network blip into a CrashLoopBackOff. Fail fast only on
configuration or credential errors (Postgres SQLSTATE class `28`, a missing secret).

**Probe settings (k8s):** set every field explicitly. Liveness is *more* tolerant than readiness.

```yaml
readinessProbe: { httpGet: { path: /readyz, port: http }, periodSeconds: 5,  timeoutSeconds: 2, failureThreshold: 3 }
livenessProbe:  { httpGet: { path: /healthz, port: http }, periodSeconds: 10, timeoutSeconds: 2, failureThreshold: 6 }
startupProbe:   { httpGet: { path: /healthz, port: http }, periodSeconds: 2,  failureThreshold: 30 }  # slow starts
```

**Rules:**
- Liveness never checks dependencies. It only shows the process is responsive.
- Readiness checks hard dependencies only, each with its own sub-second timeout, and never an optional
  dependency. It returns 503 while draining.
- Health responses carry a status word. Error text goes to the logs, never to the response.
- Never cache health check results.

## Bulkhead Pattern

Isolate resources so one failing tenant or component can't exhaust them for everyone else. Isolate
**concurrency, not connection pools**. A pool per tenant multiplies connections by the tenant count and
never shrinks: 2,000 tenants × 5 connections is far past Postgres `max_connections` (SRE-07). Use
one shared, budgeted pool per service instance (§Connection-Pool Budget) and cap each tenant's
concurrent use of it.

```go
// Per-tenant concurrency limit over ONE shared pool. The map is LRU-bounded, so idle tenants are evicted.
// (hashicorp/golang-lru/v2 + golang.org/x/sync/semaphore)
type TenantLimiter struct {
    mu   sync.Mutex
    per  int64
    sems *lru.Cache[string, *semaphore.Weighted]
}

func NewTenantLimiter(perTenant int64, maxTrackedTenants int) (*TenantLimiter, error) {
    c, err := lru.New[string, *semaphore.Weighted](maxTrackedTenants)
    if err != nil {
        return nil, err
    }
    return &TenantLimiter{per: perTenant, sems: c}, nil
}

func (l *TenantLimiter) sem(tenantID string) *semaphore.Weighted {
    l.mu.Lock()
    defer l.mu.Unlock()
    if s, ok := l.sems.Get(tenantID); ok {
        return s
    }
    s := semaphore.NewWeighted(l.per)
    l.sems.Add(tenantID, s)
    return s
}

// Do runs fn when the tenant has a free slot, or fails when ctx (the request deadline) expires.
func (l *TenantLimiter) Do(ctx context.Context, tenantID string, fn func() error) error {
    s := l.sem(tenantID)
    if err := s.Acquire(ctx, 1); err != nil {
        return apperr.NewRateLimitError(1) // 429: this tenant is saturating its share
    }
    defer s.Release(1)
    return fn()
}

// Semaphore-based bulkhead per operation type (reports vs OLTP), sized inside the pool budget
type Bulkhead struct {
    sem chan struct{}
}

func NewBulkhead(maxConcurrent int) *Bulkhead {
    return &Bulkhead{sem: make(chan struct{}, maxConcurrent)}
}

func (b *Bulkhead) Execute(ctx context.Context, fn func() error) error {
    select {
    case b.sem <- struct{}{}:
        defer func() { <-b.sem }()
        return fn()
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

```typescript
class Bulkhead {
  private active = 0;

  constructor(
    private readonly name: string,
    private readonly maxConcurrent: number,
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.active >= this.maxConcurrent) {
      throw new BulkheadFullError(this.name, this.maxConcurrent); // → 503 UNAVAILABLE, retryable
    }
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
    }
  }
}

// Usage — separate bulkheads per concern
const reportBulkhead = new Bulkhead('reports', 5);    // max 5 concurrent reports
const importBulkhead = new Bulkhead('imports', 3);     // max 3 concurrent imports
```

**Rules:**
- One shared pool per service instance. Use per-tenant *concurrency* limits, never per-tenant pools. A
  dedicated database or pool is only for a tenant tier the tenancy model defines
  (`infrastructure/saas-tenancy-models.md`), and it is counted in the budget.
- Separate bulkheads for CPU-heavy and IO work, and for reports and OLTP.
- When a bulkhead is full, return 503 (`UNAVAILABLE`, retryable) or 429. Don't queue past the
  request deadline.

## Connection-Pool Budget

Every process that connects shares one server-side limit. Write the budget down (in the
`database_agent` design) and keep it true as replicas scale:

```
  Σ (max replicas × pools per process × max conns per pool)   for api, workers, cron
+ migrate/seed jobs that can run at the same time as the app
+ admin / monitoring headroom
≤ max_connections − superuser_reserved_connections          (Postgres defaults: 100 − 3 = 97)
```

| Consumer | Replicas (HPA max) | Pools | Max conns | Total |
|---|---|---|---|---|
| api | 10 | 1 | 7 | 70 |
| worker | 2 | 1 | 5 | 10 |
| migrate job (during a rollout) | 1 | 1 | 2 | 2 |
| admin + monitoring | — | — | — | 8 |
| **total** | | | | **90 ≤ 97** |

For contrast, `MaxConns = 50` on two replicas is already 100 connections, before one job or HPA scale-out.

- Put the numbers in config (`DB_MAX_CONNS`), sized from this table and not hard-coded, and log them
  at startup.
- Make the pool-acquire timeout shorter than the request deadline. A full pool returns 503 fast, not a
  hung request.
- If the budget can't fit (large HPA ranges, many services on one DB), put PgBouncer in transaction
  mode in front of Postgres. Don't raise `max_connections` blindly: each connection costs memory.
- Verify under load: `SELECT count(*) FROM pg_stat_activity` stays under the budget.

## Rate Limiting

Protect services from abuse and ensure fair resource allocation.

```go
// Token bucket per (authenticated tenant, route template). The key space is bounded: the tenant ID
// comes from the verified token (never a client header such as X-Tenant-ID), the route is the
// template (r.Pattern), not the raw path, and the map is LRU-bounded.
type RateLimiter struct {
    mu       sync.Mutex
    limiters *lru.Cache[string, *rate.Limiter]
    rate     rate.Limit
    burst    int
}

func (rl *RateLimiter) Allow(key string) bool {
    rl.mu.Lock()
    limiter, ok := rl.limiters.Get(key)
    if !ok {
        limiter = rate.NewLimiter(rl.rate, rl.burst)
        rl.limiters.Add(key, limiter)
    }
    rl.mu.Unlock()
    return limiter.Allow()
}

func RateLimitMiddleware(limiter *RateLimiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            key := auth.TenantID(r.Context()) + ":" + r.Pattern
            if !limiter.Allow(key) {
                apperr.ErrorMapper(w, r, apperr.NewRateLimitError(1)) // 429 envelope + Retry-After
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

```typescript
import { RateLimiterMemory } from 'rate-limiter-flexible';

const rateLimiter = new RateLimiterMemory({ points: 100, duration: 60, blockDuration: 0 });

async function rateLimitMiddleware(req: Request, res: Response, next: NextFunction) {
  const key = `${req.user.tenantId}:${req.route?.path ?? "unmatched"}`; // verified tenant + route template
  try {
    const result = await rateLimiter.consume(key);
    res.set('X-RateLimit-Limit', '100');
    res.set('X-RateLimit-Remaining', String(result.remainingPoints));
    res.set('X-RateLimit-Reset', String(Math.ceil(result.msBeforeNext / 1000)));
    next();
  } catch (rateLimiterRes) {
    res.set('Retry-After', String(Math.ceil((rateLimiterRes as { msBeforeNext: number }).msBeforeNext / 1000)));
    res.status(429).json({ error: { code: 'RATE_LIMITED', message: 'Too many requests. Try again shortly.',
      request_id: req.id, retryable: true } });
  }
}
```

**Rules:**
- Rate limit by the **authenticated** tenant plus the route template. Unauthenticated endpoints (login,
  reset) also limit by IP and account identifier.
- Always return 429 in the envelope, with a `Retry-After` header.
- Include `X-RateLimit-*` headers on every response (not just 429)
- Use sliding window or token bucket — not fixed window (prevents bursts at window boundaries)
- An in-memory limiter is per replica. With N replicas, enforce shared limits in Redis or at the gateway.
- Different limits for read vs. write operations

## Graceful Shutdown

A rolling deploy sends SIGTERM to pods that are still receiving traffic. Kubernetes removes a
terminating pod from Service endpoints **asynchronously**, so kube-proxy and the ingress keep routing
to it for a few seconds. An app that closes its listener at once refuses those requests: a burst of
502/connection-refused on every rollout (SRE-06).

**Sequence:**
1. **preStop sleep (k8s):** the kubelet runs it *before* sending SIGTERM, while endpoint removal
   propagates. The native `sleep` action is stable since Kubernetes 1.34 (beta and on by default since
   1.30). On older clusters, or for an image without a shell, use the app-side delay in step 3.
2. **SIGTERM:** mark not-ready (`/readyz` → 503) so non-k8s load balancers stop routing too.
3. Without a preStop sleep (compose, VMs, old clusters), keep serving for the drain delay (5–10 s).
4. **Stop accepting and drain in-flight requests:** `Shutdown(ctx)` with a timeout of
   `terminationGracePeriodSeconds − preStop − flush − margin`.
5. **Stop background work:** consumers stop fetching, then finish and ack in-flight messages; cron jobs stop.
6. **Close pools** (DB, cache, queue producers), after in-flight work is done.
7. **Flush telemetry** with its own short timeout, then exit 0.

```yaml
# deployment: the grace period covers preStop + drain + flush + margin
spec:
  terminationGracePeriodSeconds: 45
  containers:
    - name: api
      lifecycle:
        preStop:
          sleep:
            seconds: 10
```

```go
func main() {
    health := &HealthHandler{db: pool, logger: logger}
    srv := &http.Server{
        Addr:              ":8080",
        Handler:           router,
        ReadHeaderTimeout: 5 * time.Second,
        ReadTimeout:       15 * time.Second,
        WriteTimeout:      30 * time.Second,
        IdleTimeout:       120 * time.Second,
    }

    go func() {
        if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
            slog.Error("server error", "error", err)
            os.Exit(1)
        }
    }()

    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    sig := <-quit
    slog.Info("shutting down", "signal", sig.String())

    health.draining.Store(true)                 // 2. /readyz → 503
    if !preStopSleepConfigured {                // 3. compose/VMs: let routers notice
        time.Sleep(drainDelay)                  //    (config, e.g. 5s)
    }

    ctx, cancel := context.WithTimeout(context.Background(), shutdownTimeout) // 4. e.g. 25s of a 45s grace
    defer cancel()
    if err := srv.Shutdown(ctx); err != nil {   //    stop accepting, wait for in-flight requests
        slog.Error("shutdown: in-flight requests cut off", "error", err)
    }
    workers.Stop(ctx)                           // 5. stop fetching; finish and ack current messages

    pool.Close()                                // 6. after in-flight work, never before
    redisClient.Close()

    flushCtx, cancelFlush := context.WithTimeout(context.Background(), 5*time.Second) // 7.
    defer cancelFlush()
    _ = meterProvider.Shutdown(flushCtx)
    _ = tracerProvider.Shutdown(flushCtx)
    slog.Info("shutdown complete")
}
```

```typescript
const server = app.listen(8080, () => logger.info({ port: 8080 }, "server started"));
server.keepAliveTimeout = 65_000; // longer than the load balancer's idle timeout

async function gracefulShutdown(signal: string) {
  logger.info({ signal }, "graceful shutdown");
  draining = true;                                              // /readyz → 503
  if (!process.env.PRESTOP_SLEEP) await sleep(Number(process.env.DRAIN_DELAY_MS ?? 5000));

  const force = setTimeout(() => { logger.error("forced shutdown"); process.exit(1); }, 30_000);
  force.unref();

  server.close(async () => {                                    // stop accepting; in-flight requests finish
    await consumer.stop();                                      // finish/ack in-flight messages
    await pool.end();                                           // then close pools
    await redis.quit();
    await Promise.allSettled([meterProvider.shutdown(), tracerProvider.shutdown()]);
    process.exit(0);
  });
  server.closeIdleConnections();                                // Node ≥ 18.2: drop idle keep-alives
}

process.on("SIGTERM", () => void gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => void gracefulShutdown("SIGINT"));
```

**Proof:** a rolling restart under constant load (k6 `constant-arrival-rate` during
`kubectl rollout restart`) sees zero non-2xx responses.

## Critical Rules

- Circuit breaker on every external call — no exceptions
- Retry only idempotent operations (or ones carrying an `Idempotency-Key`). A non-idempotent call
  that timed out after sending is **not** retried.
- Never retry 4xx errors other than 429; they are permanent failures.
- Backoff with jitter, a retry budget, and retries in one layer only.
- Every network call has a timeout, and every inbound request has a deadline its calls inherit.
- Propagate context everywhere — never discard parent deadlines
- Liveness never checks dependencies. Readiness checks hard dependencies only, never a cache or
  another optional one.
- One budgeted connection pool per process. Replicas × pool + jobs + admin ≤ `max_connections`.
  Never one pool per tenant.
- Rate limit by the authenticated tenant plus the route template, not a client header and not the
  raw path.
- On SIGTERM: go not-ready, drain (preStop sleep on k8s), stop accepting, finish in-flight work, close
  pools, flush telemetry.
- Log all resilience events (circuit open, retry attempt, degraded mode) at WARN level
- Partial response with degradation flag is better than no response
