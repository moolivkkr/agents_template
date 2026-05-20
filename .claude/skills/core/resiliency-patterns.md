---
skill: resiliency-patterns
description: Circuit breakers, retries, timeouts, graceful degradation, health checks, bulkhead, rate limiting, graceful shutdown — production resilience patterns
version: "1.0"
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

## Retry with Exponential Backoff

Only retry transient errors. Never retry client errors.

```go
type RetryConfig struct {
    MaxRetries int
    BaseDelay  time.Duration
    MaxDelay   time.Duration
    Jitter     bool
}

var DefaultRetryConfig = RetryConfig{
    MaxRetries: 3,
    BaseDelay:  100 * time.Millisecond,
    MaxDelay:   5 * time.Second,
    Jitter:     true,
}

func Retry(ctx context.Context, cfg RetryConfig, fn func() error) error {
    var lastErr error
    for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
        lastErr = fn()
        if lastErr == nil {
            return nil
        }

        // Don't retry non-transient errors
        if !isTransient(lastErr) {
            return lastErr
        }

        if attempt == cfg.MaxRetries {
            break
        }

        delay := cfg.BaseDelay * time.Duration(1<<uint(attempt))
        if delay > cfg.MaxDelay {
            delay = cfg.MaxDelay
        }
        if cfg.Jitter {
            delay = delay/2 + time.Duration(rand.Int63n(int64(delay/2)))
        }

        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(delay):
        }
    }
    return fmt.Errorf("exhausted %d retries: %w", cfg.MaxRetries, lastErr)
}

func isTransient(err error) bool {
    // 5xx, timeout, connection refused = transient
    // 4xx = permanent, never retry
    var httpErr *HTTPError
    if errors.As(err, &httpErr) {
        return httpErr.StatusCode >= 500
    }
    return errors.Is(err, context.DeadlineExceeded) ||
        errors.Is(err, syscall.ECONNREFUSED) ||
        errors.Is(err, syscall.ECONNRESET)
}
```

```typescript
interface RetryConfig {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
  jitter: boolean;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelayMs: 100,
  maxDelayMs: 5000,
  jitter: true,
};

async function retry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = DEFAULT_RETRY_CONFIG,
  signal?: AbortSignal,
): Promise<T> {
  let lastError: Error;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err as Error;

      if (!isTransientError(err)) throw err;
      if (attempt === config.maxRetries) break;
      if (signal?.aborted) throw new AbortError();

      let delay = config.baseDelayMs * Math.pow(2, attempt);
      delay = Math.min(delay, config.maxDelayMs);
      if (config.jitter) delay = delay / 2 + Math.random() * (delay / 2);

      await sleep(delay);
    }
  }
  throw lastError!;
}

function isTransientError(err: unknown): boolean {
  if (err instanceof HttpError) return err.status >= 500;
  if (err instanceof Error && err.message.includes('ECONNREFUSED')) return true;
  if (err instanceof Error && err.message.includes('ETIMEDOUT')) return true;
  return false;
}
```

**Rules:**
- Retry: 5xx, timeout, connection refused, connection reset
- Never retry: 400, 401, 403, 404, 409, 422 — these are permanent failures
- Always add jitter to prevent thundering herd
- Always respect context cancellation during backoff

## Timeouts at Every Boundary

Every external call must have a timeout. No unbounded waits.

```go
// HTTP client — always set timeouts
httpClient := &http.Client{
    Timeout: 5 * time.Second,
    Transport: &http.Transport{
        DialContext:           (&net.Dialer{Timeout: 2 * time.Second}).DialContext,
        TLSHandshakeTimeout:  2 * time.Second,
        ResponseHeaderTimeout: 3 * time.Second,
        IdleConnTimeout:      90 * time.Second,
        MaxIdleConns:         100,
        MaxIdleConnsPerHost:  10,
    },
}

// Database queries — always pass context with deadline
func (r *repo) FindByID(ctx context.Context, id string) (*Entity, error) {
    ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()
    return r.pool.QueryRow(ctx, "SELECT * FROM entities WHERE id = $1", id).Scan(...)
}

// Cache — short timeouts
func (c *redisCache) Get(ctx context.Context, key string) (string, error) {
    ctx, cancel := context.WithTimeout(ctx, 1*time.Second)
    defer cancel()
    return c.client.Get(ctx, key).Result()
}
```

**Default timeouts:**
| Boundary | Timeout | Notes |
|----------|---------|-------|
| HTTP client (external API) | 5s | Adjust per endpoint if needed |
| Database query | 3s | Long reports might need 30s with separate pool |
| Cache (Redis) | 1s | If cache is slow, treat as miss |
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

Three types of health checks, each with its own endpoint.

```go
// Liveness — am I running? (for container orchestrators to restart if stuck)
// GET /healthz — should ALWAYS return 200 unless the process is deadlocked
func (h *HealthHandler) Liveness(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "alive"})
}

// Readiness — can I serve traffic? (for load balancers to route traffic)
// GET /readyz — returns 200 only if dependencies are reachable
func (h *HealthHandler) Readiness(w http.ResponseWriter, r *http.Request) {
    checks := map[string]string{}
    healthy := true

    if err := h.db.PingContext(r.Context()); err != nil {
        checks["database"] = err.Error()
        healthy = false
    } else {
        checks["database"] = "ok"
    }

    if err := h.cache.Ping(r.Context()); err != nil {
        checks["cache"] = err.Error()
        healthy = false
    } else {
        checks["cache"] = "ok"
    }

    status := http.StatusOK
    if !healthy {
        status = http.StatusServiceUnavailable
    }
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(map[string]interface{}{
        "status": boolToStatus(healthy),
        "checks": checks,
    })
}

// Deep health — detailed dependency status (for ops dashboards, not for LB)
// GET /health/deep — returns status of every dependency with latency
func (h *HealthHandler) DeepHealth(w http.ResponseWriter, r *http.Request) {
    type CheckResult struct {
        Status  string `json:"status"`
        Latency string `json:"latency"`
        Error   string `json:"error,omitempty"`
    }
    results := map[string]CheckResult{}

    start := time.Now()
    if err := h.db.PingContext(r.Context()); err != nil {
        results["database"] = CheckResult{Status: "unhealthy", Latency: time.Since(start).String(), Error: err.Error()}
    } else {
        results["database"] = CheckResult{Status: "healthy", Latency: time.Since(start).String()}
    }

    // repeat for cache, message queue, external services...

    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(results)
}
```

```typescript
// Express health routes
app.get('/healthz', (req, res) => {
  res.status(200).json({ status: 'alive' });
});

app.get('/readyz', async (req, res) => {
  const checks: Record<string, string> = {};
  let healthy = true;

  try {
    await pool.query('SELECT 1');
    checks.database = 'ok';
  } catch (err) {
    checks.database = (err as Error).message;
    healthy = false;
  }

  try {
    await redis.ping();
    checks.cache = 'ok';
  } catch (err) {
    checks.cache = (err as Error).message;
    healthy = false;
  }

  res.status(healthy ? 200 : 503).json({ status: healthy ? 'ready' : 'not_ready', checks });
});
```

**Rules:**
- Liveness check: never check dependencies — only check if the process is responsive
- Readiness check: check all required dependencies (DB, cache)
- Deep health: check everything including optional dependencies, include latency
- Never cache health check results — always check live

## Bulkhead Pattern

Isolate resources so one failing tenant or component doesn't exhaust resources for others.

```go
// Per-tenant connection pool isolation
type TenantPoolManager struct {
    pools   map[string]*pgxpool.Pool
    maxConn int32
    mu      sync.RWMutex
}

func (m *TenantPoolManager) GetPool(tenantID string) (*pgxpool.Pool, error) {
    m.mu.RLock()
    pool, ok := m.pools[tenantID]
    m.mu.RUnlock()
    if ok {
        return pool, nil
    }

    m.mu.Lock()
    defer m.mu.Unlock()
    // Double-check after acquiring write lock
    if pool, ok := m.pools[tenantID]; ok {
        return pool, nil
    }

    config, err := pgxpool.ParseConfig(m.dsn)
    if err != nil {
        return nil, err
    }
    config.MaxConns = m.maxConn // isolated pool per tenant
    pool, err = pgxpool.NewWithConfig(context.Background(), config)
    if err != nil {
        return nil, err
    }
    m.pools[tenantID] = pool
    return pool, nil
}

// Semaphore-based bulkhead for concurrent operations
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
      throw new BulkheadFullError(this.name, this.maxConcurrent);
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
- Separate connection pools per tenant for multi-tenant systems
- Separate thread/goroutine pools for CPU-intensive vs. IO operations
- Set max concurrency per operation type to prevent resource exhaustion
- Return 503 or 429 when bulkhead is full — don't queue indefinitely

## Rate Limiting

Protect services from abuse and ensure fair resource allocation.

```go
// Token bucket rate limiter
type RateLimiter struct {
    limiters map[string]*rate.Limiter
    mu       sync.RWMutex
    rate     rate.Limit
    burst    int
}

func NewRateLimiter(rps float64, burst int) *RateLimiter {
    return &RateLimiter{
        limiters: make(map[string]*rate.Limiter),
        rate:     rate.Limit(rps),
        burst:    burst,
    }
}

func (rl *RateLimiter) Allow(key string) bool {
    rl.mu.Lock()
    limiter, ok := rl.limiters[key]
    if !ok {
        limiter = rate.NewLimiter(rl.rate, rl.burst)
        rl.limiters[key] = limiter
    }
    rl.mu.Unlock()
    return limiter.Allow()
}

// Rate limit middleware
func RateLimitMiddleware(limiter *RateLimiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            tenantID := r.Header.Get("X-Tenant-ID")
            key := tenantID + ":" + r.URL.Path

            if !limiter.Allow(key) {
                w.Header().Set("Retry-After", "1")
                w.Header().Set("X-RateLimit-Limit", fmt.Sprintf("%d", int(limiter.rate)))
                w.Header().Set("X-RateLimit-Remaining", "0")
                http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

```typescript
import { RateLimiterMemory } from 'rate-limiter-flexible';

const rateLimiter = new RateLimiterMemory({
  points: 100,     // 100 requests
  duration: 60,    // per 60 seconds
  blockDuration: 0,
});

async function rateLimitMiddleware(req: Request, res: Response, next: NextFunction) {
  const key = `${req.tenantId}:${req.path}`;
  try {
    const result = await rateLimiter.consume(key);
    res.set('X-RateLimit-Limit', '100');
    res.set('X-RateLimit-Remaining', String(result.remainingPoints));
    res.set('X-RateLimit-Reset', String(Math.ceil(result.msBeforeNext / 1000)));
    next();
  } catch (rateLimiterRes) {
    res.set('Retry-After', String(Math.ceil(rateLimiterRes.msBeforeNext / 1000)));
    res.status(429).json({ error: 'rate limit exceeded' });
  }
}
```

**Rules:**
- Rate limit by tenant_id + endpoint, not just by IP
- Always return 429 with `Retry-After` header
- Include `X-RateLimit-*` headers on every response (not just 429)
- Use sliding window or token bucket — not fixed window (prevents bursts at window boundaries)
- Different limits for read vs. write operations

## Graceful Shutdown

Handle termination signals properly. Drain in-flight requests before exiting.

```go
func main() {
    srv := &http.Server{
        Addr:         ":8080",
        Handler:      router,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 30 * time.Second,
        IdleTimeout:  60 * time.Second,
    }

    // Start server in goroutine
    go func() {
        if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
            slog.Error("server error", "error", err)
            os.Exit(1)
        }
    }()

    // Wait for termination signal
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    sig := <-quit
    slog.Info("shutting down", "signal", sig.String())

    // Graceful shutdown with timeout
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    // Stop accepting new requests, drain in-flight
    if err := srv.Shutdown(ctx); err != nil {
        slog.Error("shutdown error", "error", err)
    }

    // Close other resources
    pool.Close()             // database connections
    redisClient.Close()      // cache connections
    metricsExporter.Flush()  // flush pending metrics
    tracerProvider.Shutdown(ctx) // flush pending traces

    slog.Info("shutdown complete")
}
```

```typescript
const server = app.listen(8080, () => {
  logger.info('server started', { port: 8080 });
});

async function gracefulShutdown(signal: string) {
  logger.info(`received ${signal}, starting graceful shutdown`);

  // Stop accepting new connections
  server.close(async () => {
    logger.info('http server closed');

    // Close dependencies
    await pool.end();          // database
    await redis.quit();        // cache
    await producer.disconnect(); // message queue

    // Flush observability
    await meterProvider.shutdown();
    await tracerProvider.shutdown();

    logger.info('shutdown complete');
    process.exit(0);
  });

  // Force exit after timeout
  setTimeout(() => {
    logger.error('forced shutdown after timeout');
    process.exit(1);
  }, 30_000);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

**Shutdown sequence:**
1. Receive SIGTERM / SIGINT
2. Stop accepting new requests (server.Shutdown / server.close)
3. Wait for in-flight requests to complete (up to 30s timeout)
4. Close database connections, cache connections, message queue producers
5. Flush metrics and traces
6. Exit cleanly

## Critical Rules

- Circuit breaker on every external call — no exceptions
- Never retry 4xx errors — they are permanent failures
- Every network call has a timeout — no unbounded waits
- Propagate context everywhere — never discard parent deadlines
- Liveness check never checks dependencies — only readiness and deep health do
- Rate limit by tenant, not just by IP
- Graceful shutdown drains in-flight requests before closing connections
- Log all resilience events (circuit open, retry attempt, degraded mode) at WARN level
- Partial response with degradation flag is better than no response
