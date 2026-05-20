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

Every production service must implement these. External dependencies fail — plan for it.

## Circuit Breakers on ALL External Calls

Every HTTP client, DB, cache, and queue call wrapped in a circuit breaker.

**States:** Closed (normal, track failures) → Open (reject immediately, return fallback) → Half-Open (probe one request after timeout)

```go
type CircuitBreaker struct {
    name         string
    maxFailures  int
    resetTimeout time.Duration
    state        CircuitState
    failures     int
    lastFailure  time.Time
    mu           sync.RWMutex
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    switch cb.state {
    case CircuitOpen:
        if time.Since(cb.lastFailure) > cb.resetTimeout {
            cb.state = CircuitHalfOpen
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
        if cb.failures >= cb.maxFailures { cb.state = CircuitOpen }
        return err
    }
    cb.failures = 0
    cb.state = CircuitClosed
    return nil
}
```

```typescript
class CircuitBreaker {
  private state = CircuitState.Closed;
  private failures = 0;
  private lastFailure = 0;

  constructor(private name: string, private maxFailures: number, private resetTimeoutMs: number) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.Open) {
      if (Date.now() - this.lastFailure > this.resetTimeoutMs) {
        this.state = CircuitState.HalfOpen;
      } else { throw new CircuitOpenError(this.name); }
    }
    try {
      const result = await fn();
      this.failures = 0; this.state = CircuitState.Closed;
      return result;
    } catch (err) {
      this.failures++; this.lastFailure = Date.now();
      if (this.failures >= this.maxFailures) this.state = CircuitState.Open;
      throw err;
    }
  }
}
```

**Typical thresholds:** `maxFailures`: 5, `resetTimeout`: 30s. Adjust per dependency.

## Retry with Exponential Backoff

Only retry transient errors. Never retry 4xx.

```go
type RetryConfig struct {
    MaxRetries int
    BaseDelay  time.Duration
    MaxDelay   time.Duration
    Jitter     bool
}

var DefaultRetryConfig = RetryConfig{MaxRetries: 3, BaseDelay: 100 * time.Millisecond, MaxDelay: 5 * time.Second, Jitter: true}

func Retry(ctx context.Context, cfg RetryConfig, fn func() error) error {
    var lastErr error
    for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
        lastErr = fn()
        if lastErr == nil { return nil }
        if !isTransient(lastErr) { return lastErr }
        if attempt == cfg.MaxRetries { break }
        delay := cfg.BaseDelay * time.Duration(1<<uint(attempt))
        if delay > cfg.MaxDelay { delay = cfg.MaxDelay }
        if cfg.Jitter { delay = delay/2 + time.Duration(rand.Int63n(int64(delay/2))) }
        select {
        case <-ctx.Done(): return ctx.Err()
        case <-time.After(delay):
        }
    }
    return fmt.Errorf("exhausted %d retries: %w", cfg.MaxRetries, lastErr)
}

// Transient: 5xx, timeout, connection refused/reset. Never retry: 4xx.
```

```typescript
async function retry<T>(fn: () => Promise<T>, config = DEFAULT_RETRY_CONFIG, signal?: AbortSignal): Promise<T> {
  let lastError: Error;
  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try { return await fn(); }
    catch (err) {
      lastError = err as Error;
      if (!isTransientError(err)) throw err;
      if (attempt === config.maxRetries) break;
      if (signal?.aborted) throw new AbortError();
      let delay = Math.min(config.baseDelayMs * 2 ** attempt, config.maxDelayMs);
      if (config.jitter) delay = delay / 2 + Math.random() * (delay / 2);
      await sleep(delay);
    }
  }
  throw lastError!;
}
```

## Timeouts at Every Boundary

No unbounded waits. Always propagate context.

**Default timeouts:**

| Boundary | Timeout |
|----------|---------|
| HTTP client (external) | 5s |
| Database query | 3s |
| Cache (Redis) | 1s |
| Message queue publish | 2s |
| Internal service call | 3s |

```go
// Always pass context with deadline; always defer cancel()
ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
defer cancel()
```

## Graceful Degradation

When optional dependencies fail, return partial data instead of failing entirely.

```go
// Required dep down → return error. Optional dep down → return partial + flag.
price, err := s.pricingService.GetPrice(ctx, product.ID)
if err != nil {
    s.logger.WarnContext(ctx, "pricing degraded, using cached", "error", err)
    price = product.CachedPrice
    product.PriceStale = true
}
```

```typescript
const [recommendations, reviews] = await Promise.allSettled([
  recommendationService.getFor(id),
  reviewService.getFor(id),
]);
return {
  product,
  recommendations: recommendations.status === 'fulfilled' ? recommendations.value : [],
  degraded: recommendations.status === 'rejected',
};
```

## Health Checks

```go
// GET /healthz — Liveness (never check deps, only process responsiveness)
// GET /readyz — Readiness (check required deps: DB, cache)
// GET /health/deep — Deep (all deps with latency, for ops dashboards)

func (h *HealthHandler) Readiness(w http.ResponseWriter, r *http.Request) {
    checks := map[string]string{}
    healthy := true
    if err := h.db.PingContext(r.Context()); err != nil {
        checks["database"] = err.Error(); healthy = false
    } else { checks["database"] = "ok" }
    status := http.StatusOK
    if !healthy { status = http.StatusServiceUnavailable }
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(map[string]interface{}{"status": boolToStatus(healthy), "checks": checks})
}
```

Never cache health check results.

## Bulkhead Pattern

Isolate resources so one failing tenant/component doesn't exhaust resources for others.

```go
// Semaphore-based bulkhead
type Bulkhead struct { sem chan struct{} }

func NewBulkhead(max int) *Bulkhead { return &Bulkhead{sem: make(chan struct{}, max)} }

func (b *Bulkhead) Execute(ctx context.Context, fn func() error) error {
    select {
    case b.sem <- struct{}{}: defer func() { <-b.sem }(); return fn()
    case <-ctx.Done(): return ctx.Err()
    }
}
```

Rules: Separate pools per tenant; separate pools for CPU vs IO; return 503/429 when full.

## Rate Limiting

```go
func RateLimitMiddleware(limiter *RateLimiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            key := r.Header.Get("X-Tenant-ID") + ":" + r.URL.Path
            if !limiter.Allow(key) {
                w.Header().Set("Retry-After", "1")
                http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

Rules: Rate limit by tenant_id + endpoint, not just IP. Return 429 with `Retry-After`. Include `X-RateLimit-*` headers on every response. Use token bucket or sliding window. Different limits for read vs write.

## Graceful Shutdown

**Sequence:** SIGTERM/SIGINT → stop accepting → drain in-flight (30s timeout) → close DB/cache/queue → flush metrics/traces → exit.

```go
quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(ctx)
pool.Close(); redisClient.Close(); tracerProvider.Shutdown(ctx)
```

## Critical Rules

- Circuit breaker on every external call — no exceptions
- Never retry 4xx — permanent failures
- Every network call has a timeout
- Propagate context everywhere — never discard parent deadlines
- Liveness never checks dependencies
- Rate limit by tenant, not just IP
- Graceful shutdown drains before closing connections
- Log all resilience events (circuit open, retry, degraded) at WARN
- Partial response with degradation flag > no response
