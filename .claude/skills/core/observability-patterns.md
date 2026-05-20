---
skill: observability-patterns
description: Structured logging, OpenTelemetry metrics/traces, tenant-aware observability, error taxonomy, SLA metrics, correlation IDs
version: "1.0"
tags:
  - observability
  - logging
  - metrics
  - tracing
  - opentelemetry
  - monitoring
---

# Observability Patterns

Every service must be observable from day one. Logging, metrics, and tracing are first-class requirements.

## tenant_id on EVERY Log/Metric/Trace

Non-negotiable. Every log line, metric label, and trace span must include `tenant_id`.

```go
// Middleware extracts tenant_id into context
func TenantMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        tenantID := r.Header.Get("X-Tenant-ID")
        if tenantID == "" {
            http.Error(w, "missing tenant ID", http.StatusBadRequest)
            return
        }
        ctx := context.WithValue(r.Context(), tenantIDKey, tenantID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Log with tenant_id
s.logger.InfoContext(ctx, "processing order",
    "tenant_id", TenantFromContext(ctx),
    "order_id", order.ID,
)

// Metric with tenant_id
requestCount.Add(ctx, 1, metric.WithAttributes(
    attribute.String("tenant_id", TenantFromContext(ctx)),
    attribute.String("endpoint", "/api/v1/orders"),
))

// Trace with tenant_id
ctx, span := tracer.Start(ctx, "OrderService.ProcessOrder",
    trace.WithAttributes(attribute.String("tenant_id", TenantFromContext(ctx))),
)
defer span.End()
```

```typescript
// Middleware
function tenantMiddleware(req: Request, res: Response, next: NextFunction) {
  const tenantId = req.headers['x-tenant-id'] as string;
  if (!tenantId) return res.status(400).json({ error: 'missing tenant ID' });
  req.tenantId = tenantId;
  req.logger = logger.child({ tenant_id: tenantId, request_id: req.id });
  next();
}
```

## Structured Logging

No `fmt.Println` or `console.log` with string interpolation in production.

### Go — slog

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
serviceLogger := logger.With("service", "order-service", "version", buildVersion)

serviceLogger.InfoContext(ctx, "order created",
    "tenant_id", tenantID, "order_id", order.ID,
    "request_id", RequestIDFromContext(ctx), "trace_id", TraceIDFromContext(ctx),
)
```

### TypeScript — pino

```typescript
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  base: { service: 'order-service', version: process.env.APP_VERSION },
  timestamp: pino.stdTimeFunctions.isoTime,
});

const reqLogger = logger.child({ tenant_id: req.tenantId, request_id: req.id });
reqLogger.info({ order_id: order.id }, 'order created');
```

### Required log fields

| Field | Source | Purpose |
|-------|--------|---------|
| `timestamp` | Auto | When |
| `level` | Logger | Severity |
| `msg` | Developer | What happened |
| `tenant_id` | Context | Whose request |
| `request_id` | Edge-generated | Correlate within request |
| `trace_id` | OpenTelemetry | Correlate across services |
| `service` | Config | Which service |

## OpenTelemetry Metrics

Instrument every boundary: HTTP handlers, service methods, repository calls, external API calls.

```go
var (
    meter = otel.Meter("order-service")
    requestCount metric.Int64Counter
    requestDuration metric.Float64Histogram
    activeRequests metric.Int64UpDownCounter
    orderTotal metric.Float64Counter
)

func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        attrs := metric.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(r.Context())),
            attribute.String("method", r.Method),
            attribute.String("endpoint", r.URL.Path),
        )
        activeRequests.Add(r.Context(), 1, attrs)
        defer activeRequests.Add(r.Context(), -1, attrs)

        wrapped := &statusRecorder{ResponseWriter: w, statusCode: 200}
        next.ServeHTTP(wrapped, r)

        statusAttrs := metric.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(r.Context())),
            attribute.String("method", r.Method),
            attribute.String("endpoint", r.URL.Path),
            attribute.Int("status_code", wrapped.statusCode),
        )
        requestCount.Add(r.Context(), 1, statusAttrs)
        requestDuration.Record(r.Context(), time.Since(start).Seconds(), statusAttrs)
    })
}
```

### Key metrics

| Metric | Type | Labels |
|--------|------|--------|
| `http.server.request.total` | Counter | tenant_id, method, endpoint, status_code |
| `http.server.request.duration` | Histogram | tenant_id, method, endpoint |
| `http.server.active_requests` | UpDownCounter | tenant_id, endpoint |
| `db.query.duration` | Histogram | tenant_id, operation, table |
| `external.request.duration` | Histogram | tenant_id, service, endpoint |
| `business.<event>.total` | Counter | tenant_id, type |

## Distributed Tracing

Create a span for every significant operation. Propagate trace context across boundaries.

```go
var tracer = otel.Tracer("order-service")

// Service span
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    ctx, span := tracer.Start(ctx, "OrderService.CreateOrder")
    defer span.End()
    // On error: span.RecordError(err); span.SetStatus(codes.Error, err.Error())
    // On success: span.SetAttributes(attribute.String("order_id", order.ID))
}

// Repository span
func (r *postgresOrderRepo) Save(ctx context.Context, order *Order) error {
    ctx, span := tracer.Start(ctx, "postgres.orders.insert",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.operation", "INSERT"),
        ),
    )
    defer span.End()
}
```

**Span naming:** HTTP: `HTTP {METHOD} {path}` | Service: `{Service}.{Method}` | Repo: `{system}.{table}.{op}` | External: `{service}.{endpoint}`

## Domain Error Taxonomy

```go
type DomainError struct {
    Category  ErrorCategory
    Code      string // "ORDER_NOT_FOUND", "INSUFFICIENT_STOCK"
    Message   string
    Details   map[string]interface{}
    Cause     error
}

type ErrorCategory int
const (
    ErrCategoryValidation   ErrorCategory = iota // 400
    ErrCategoryNotFound                           // 404
    ErrCategoryConflict                           // 409
    ErrCategoryUnauthorized                       // 401
    ErrCategoryForbidden                          // 403
    ErrCategoryInternal                           // 500
    ErrCategoryUpstream                           // 502/503
)
```

```typescript
class DomainError extends Error {
  constructor(
    public readonly category: ErrorCategory,
    public readonly code: string,
    message: string,
    public readonly details?: Record<string, unknown>,
    public readonly cause?: Error,
  ) { super(message); }

  get httpStatus(): number {
    const map: Record<ErrorCategory, number> = {
      VALIDATION: 400, NOT_FOUND: 404, CONFLICT: 409,
      UNAUTHORIZED: 401, FORBIDDEN: 403, INTERNAL: 500, UPSTREAM: 502,
    };
    return map[this.category] || 500;
  }
}
```

## SLA Metrics

Define and measure SLOs per service. Dashboard must include:
- Availability over rolling 30-day window
- P50, P95, P99 latency
- Error rate (5xx / total)
- Error budget remaining + breach alerts

## Log Levels

| Level | When | Action |
|-------|------|--------|
| **ERROR** | Something broke needing investigation | Alert on-call |
| **WARN** | Concerning but handled (circuit breaker, retry) | Daily ops review |
| **INFO** | Normal business events | Audit trail |
| **DEBUG** | Troubleshooting detail (off in prod) | Enable per-service |

Rules: ERROR = "wake someone up"; WARN = handled degradation; INFO = one per state transition; never log PII/tokens at any level.

## Correlation IDs

Generate request ID at edge, propagate through all services.

```go
func RequestIDMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestID := r.Header.Get("X-Request-ID")
        if requestID == "" { requestID = "req_" + uuid.New().String() }
        ctx := context.WithValue(r.Context(), requestIDKey, requestID)
        w.Header().Set("X-Request-ID", requestID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Propagate to downstream services
func (c *httpClient) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
    if reqID := RequestIDFromContext(ctx); reqID != "" {
        req.Header.Set("X-Request-ID", reqID)
    }
    otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
    return c.client.Do(req)
}
```

**Flow:** `Client → Gateway (gen req_abc) → Service A → Service B → DB` — all queryable via `request_id = "req_abc"`

## Critical Rules

- `tenant_id` on every log, metric, trace — zero exceptions
- Structured JSON logging only — no string concatenation
- Request ID + trace ID on every log line
- ERROR = actionable alarm; never for expected conditions
- Never log PII/tokens/secrets
- Metrics at every boundary; every span records errors
- SLA dashboards per service with alerting
