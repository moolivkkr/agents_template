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

Every service must be observable from day one. Logging, metrics, and tracing are not afterthoughts — they are first-class requirements.

## tenant_id on EVERY Log/Metric/Trace

Non-negotiable. Every log line, every metric label, every trace span must include `tenant_id`. This is how you debug multi-tenant systems.

```go
// Middleware extracts tenant_id and injects it into context
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

func TenantFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(tenantIDKey).(string); ok {
        return v
    }
    return "unknown"
}

// Every log line includes tenant_id
func (s *Service) ProcessOrder(ctx context.Context, order *Order) error {
    s.logger.InfoContext(ctx, "processing order",
        "tenant_id", TenantFromContext(ctx),
        "order_id", order.ID,
        "amount", order.Total,
    )
    // ...
}

// Every metric includes tenant_id label
requestCount.Add(ctx, 1,
    metric.WithAttributes(
        attribute.String("tenant_id", TenantFromContext(ctx)),
        attribute.String("endpoint", "/api/v1/orders"),
        attribute.String("method", "POST"),
        attribute.Int("status_code", 201),
    ),
)

// Every trace span includes tenant_id
ctx, span := tracer.Start(ctx, "OrderService.ProcessOrder",
    trace.WithAttributes(
        attribute.String("tenant_id", TenantFromContext(ctx)),
        attribute.String("order_id", order.ID),
    ),
)
defer span.End()
```

```typescript
// Middleware injects tenant_id into request context and logger
function tenantMiddleware(req: Request, res: Response, next: NextFunction) {
  const tenantId = req.headers['x-tenant-id'] as string;
  if (!tenantId) {
    return res.status(400).json({ error: 'missing tenant ID' });
  }
  req.tenantId = tenantId;
  req.logger = logger.child({ tenant_id: tenantId, request_id: req.id });
  next();
}

// Every log line
req.logger.info({ order_id: order.id, amount: order.total }, 'processing order');

// Every metric
requestCounter.add(1, {
  tenant_id: req.tenantId,
  endpoint: req.path,
  method: req.method,
  status_code: res.statusCode,
});
```

## Structured Logging

Use structured logging in every service. No `fmt.Println` or `console.log` with string interpolation in production code.

### Go — use slog

```go
// Setup — JSON handler for production
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))
slog.SetDefault(logger)

// Create child loggers with common fields
serviceLogger := logger.With(
    "service", "order-service",
    "version", buildVersion,
)

// Structured log output
serviceLogger.InfoContext(ctx, "order created",
    "tenant_id", tenantID,
    "order_id", order.ID,
    "item_count", len(order.Items),
    "total", order.Total.String(),
    "request_id", RequestIDFromContext(ctx),
    "trace_id", TraceIDFromContext(ctx),
)

// Output (JSON):
// {
//   "time": "2024-01-15T10:30:00Z",
//   "level": "INFO",
//   "msg": "order created",
//   "service": "order-service",
//   "version": "1.2.3",
//   "tenant_id": "tenant_abc",
//   "order_id": "ord_123",
//   "item_count": 3,
//   "total": "99.99",
//   "request_id": "req_xyz",
//   "trace_id": "abc123def456"
// }
```

### TypeScript — use pino

```typescript
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  base: {
    service: 'order-service',
    version: process.env.APP_VERSION,
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

// Child logger per request
const reqLogger = logger.child({
  tenant_id: req.tenantId,
  request_id: req.id,
  trace_id: getTraceId(req),
});

reqLogger.info({
  order_id: order.id,
  item_count: order.items.length,
  total: order.total,
}, 'order created');

// Output (JSON):
// {
//   "level": "info",
//   "time": "2024-01-15T10:30:00.000Z",
//   "service": "order-service",
//   "version": "1.2.3",
//   "tenant_id": "tenant_abc",
//   "request_id": "req_xyz",
//   "trace_id": "abc123def456",
//   "order_id": "ord_123",
//   "item_count": 3,
//   "total": 99.99,
//   "msg": "order created"
// }
```

### Required fields on every log line

| Field | Source | Purpose |
|-------|--------|---------|
| `timestamp` | Logger auto-generates | When it happened |
| `level` | Logger | Severity |
| `msg` | Developer | What happened |
| `tenant_id` | Context/middleware | Whose request |
| `request_id` | Generated at edge | Correlate within a request |
| `trace_id` | OpenTelemetry | Correlate across services |
| `service` | Config | Which service |
| `component` | Logger child | Which module (optional, useful for large services) |

## OpenTelemetry Metrics at Every Boundary

Instrument every boundary: HTTP handlers, service methods, repository calls, external API calls.

```go
import (
    "go.opentelemetry.io/otel/metric"
)

// Define meters at package level
var (
    meter = otel.Meter("order-service")

    requestCount metric.Int64Counter
    requestDuration metric.Float64Histogram
    activeRequests metric.Int64UpDownCounter
    orderTotal metric.Float64Counter
)

func initMetrics() {
    var err error

    requestCount, err = meter.Int64Counter("http.server.request.total",
        metric.WithDescription("Total HTTP requests"),
        metric.WithUnit("{request}"),
    )

    requestDuration, err = meter.Float64Histogram("http.server.request.duration",
        metric.WithDescription("HTTP request duration in seconds"),
        metric.WithUnit("s"),
        metric.WithExplicitBucketBoundaries(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )

    activeRequests, err = meter.Int64UpDownCounter("http.server.active_requests",
        metric.WithDescription("Currently active requests"),
        metric.WithUnit("{request}"),
    )

    // Business metric
    orderTotal, err = meter.Float64Counter("business.order.total",
        metric.WithDescription("Total order value processed"),
        metric.WithUnit("USD"),
    )
}

// Metrics middleware
func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        tenantID := TenantFromContext(r.Context())

        attrs := metric.WithAttributes(
            attribute.String("tenant_id", tenantID),
            attribute.String("method", r.Method),
            attribute.String("endpoint", r.URL.Path),
        )

        activeRequests.Add(r.Context(), 1, attrs)
        defer activeRequests.Add(r.Context(), -1, attrs)

        wrapped := &statusRecorder{ResponseWriter: w, statusCode: 200}
        next.ServeHTTP(wrapped, r)

        duration := time.Since(start).Seconds()
        statusAttrs := metric.WithAttributes(
            attribute.String("tenant_id", tenantID),
            attribute.String("method", r.Method),
            attribute.String("endpoint", r.URL.Path),
            attribute.Int("status_code", wrapped.statusCode),
        )

        requestCount.Add(r.Context(), 1, statusAttrs)
        requestDuration.Record(r.Context(), duration, statusAttrs)
    })
}

// Business event metrics
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    order, err := s.processOrder(ctx, req)
    if err != nil {
        return nil, err
    }

    // Record business metric
    orderTotal.Add(ctx, order.Total.InexactFloat64(),
        metric.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(ctx)),
            attribute.String("payment_method", order.PaymentMethod),
        ),
    )
    return order, nil
}
```

```typescript
import { metrics } from '@opentelemetry/api';

const meter = metrics.getMeter('order-service');

const requestCount = meter.createCounter('http.server.request.total', {
  description: 'Total HTTP requests',
  unit: '{request}',
});

const requestDuration = meter.createHistogram('http.server.request.duration', {
  description: 'HTTP request duration in seconds',
  unit: 's',
  advice: { explicitBucketBoundaries: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10] },
});

const orderTotal = meter.createCounter('business.order.total', {
  description: 'Total order value processed',
  unit: 'USD',
});

// Middleware
function metricsMiddleware(req: Request, res: Response, next: NextFunction) {
  const start = process.hrtime.bigint();

  res.on('finish', () => {
    const durationNs = Number(process.hrtime.bigint() - start);
    const durationSec = durationNs / 1e9;

    const attrs = {
      tenant_id: req.tenantId,
      method: req.method,
      endpoint: req.route?.path || req.path,
      status_code: res.statusCode,
    };

    requestCount.add(1, attrs);
    requestDuration.record(durationSec, attrs);
  });

  next();
}
```

### Key metrics to instrument

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http.server.request.total` | Counter | tenant_id, method, endpoint, status_code | Request volume and error rates |
| `http.server.request.duration` | Histogram | tenant_id, method, endpoint | Latency distribution (p50/p95/p99) |
| `http.server.active_requests` | UpDownCounter | tenant_id, endpoint | Concurrency / saturation |
| `db.query.duration` | Histogram | tenant_id, operation, table | Database performance |
| `external.request.duration` | Histogram | tenant_id, service, endpoint | Upstream latency |
| `business.<event>.total` | Counter | tenant_id, type | Business KPIs |

## Distributed Tracing

Create a span for every significant operation. Propagate trace context across service boundaries.

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
    "go.opentelemetry.io/otel/attribute"
)

var tracer = otel.Tracer("order-service")

// HTTP handler — root span (usually auto-instrumented)
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    ctx, span := tracer.Start(r.Context(), "HTTP POST /api/v1/orders",
        trace.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(r.Context())),
        ),
    )
    defer span.End()

    order, err := h.service.CreateOrder(ctx, parseRequest(r))
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        respondError(w, err)
        return
    }
    span.SetAttributes(attribute.String("order_id", order.ID))
    respondJSON(w, http.StatusCreated, order)
}

// Service — child span
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    ctx, span := tracer.Start(ctx, "OrderService.CreateOrder")
    defer span.End()

    // Validate
    if err := req.Validate(); err != nil {
        span.RecordError(err)
        return nil, err
    }

    // Repository call — another child span
    order := NewOrder(req)
    if err := s.repo.Save(ctx, order); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "save failed")
        return nil, err
    }

    span.SetAttributes(
        attribute.String("order_id", order.ID),
        attribute.Float64("order_total", order.Total.InexactFloat64()),
    )
    return order, nil
}

// Repository — child span
func (r *postgresOrderRepo) Save(ctx context.Context, order *Order) error {
    ctx, span := tracer.Start(ctx, "postgres.orders.insert",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.operation", "INSERT"),
            attribute.String("db.sql.table", "orders"),
        ),
    )
    defer span.End()

    _, err := r.pool.Exec(ctx, `INSERT INTO orders ...`, order.ID, order.TenantID, order.Total)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
    }
    return err
}
```

```typescript
import { trace, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('order-service');

async function createOrder(ctx: Context, req: CreateOrderReq): Promise<Order> {
  return tracer.startActiveSpan('OrderService.createOrder', async (span) => {
    try {
      span.setAttribute('tenant_id', ctx.tenantId);
      const order = await repo.save(ctx, buildOrder(req));
      span.setAttribute('order_id', order.id);
      return order;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: (err as Error).message });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

**Span naming convention:**
- HTTP handlers: `HTTP {METHOD} {path}` (e.g., `HTTP POST /api/v1/orders`)
- Service methods: `{ServiceName}.{MethodName}` (e.g., `OrderService.CreateOrder`)
- Repository calls: `{system}.{table}.{operation}` (e.g., `postgres.orders.insert`)
- External calls: `{service}.{endpoint}` (e.g., `payment-gateway.charge`)

## Domain Error Taxonomy

Categorize all errors. Map them consistently to HTTP status codes and include machine-readable error codes.

```go
type DomainError struct {
    Category  ErrorCategory
    Code      string // machine-readable: "ORDER_NOT_FOUND", "INSUFFICIENT_STOCK"
    Message   string // human-readable
    Details   map[string]interface{}
    Cause     error  // wrapped underlying error
}

type ErrorCategory int

const (
    ErrCategoryValidation   ErrorCategory = iota // 400 — bad input
    ErrCategoryNotFound                           // 404 — resource doesn't exist
    ErrCategoryConflict                           // 409 — duplicate, version mismatch
    ErrCategoryUnauthorized                       // 401 — not authenticated
    ErrCategoryForbidden                          // 403 — authenticated but not allowed
    ErrCategoryInternal                           // 500 — our fault
    ErrCategoryUpstream                           // 502/503 — dependency failure
)

// Constructors
func NewValidationError(code, message string, details map[string]interface{}) *DomainError {
    return &DomainError{Category: ErrCategoryValidation, Code: code, Message: message, Details: details}
}

func NewNotFoundError(resource, id string) *DomainError {
    return &DomainError{
        Category: ErrCategoryNotFound,
        Code:     strings.ToUpper(resource) + "_NOT_FOUND",
        Message:  fmt.Sprintf("%s with id %s not found", resource, id),
    }
}

func NewUpstreamError(service string, cause error) *DomainError {
    return &DomainError{
        Category: ErrCategoryUpstream,
        Code:     "UPSTREAM_" + strings.ToUpper(service) + "_FAILURE",
        Message:  fmt.Sprintf("%s service unavailable", service),
        Cause:    cause,
    }
}

// Map to HTTP status in handler layer
func httpStatusFromError(err error) int {
    var domErr *DomainError
    if !errors.As(err, &domErr) {
        return http.StatusInternalServerError
    }
    switch domErr.Category {
    case ErrCategoryValidation:
        return http.StatusBadRequest
    case ErrCategoryNotFound:
        return http.StatusNotFound
    case ErrCategoryConflict:
        return http.StatusConflict
    case ErrCategoryUnauthorized:
        return http.StatusUnauthorized
    case ErrCategoryForbidden:
        return http.StatusForbidden
    case ErrCategoryUpstream:
        return http.StatusBadGateway
    default:
        return http.StatusInternalServerError
    }
}
```

```typescript
enum ErrorCategory {
  Validation = 'VALIDATION',
  NotFound = 'NOT_FOUND',
  Conflict = 'CONFLICT',
  Unauthorized = 'UNAUTHORIZED',
  Forbidden = 'FORBIDDEN',
  Internal = 'INTERNAL',
  Upstream = 'UPSTREAM',
}

class DomainError extends Error {
  constructor(
    public readonly category: ErrorCategory,
    public readonly code: string,
    message: string,
    public readonly details?: Record<string, unknown>,
    public readonly cause?: Error,
  ) {
    super(message);
    this.name = 'DomainError';
  }

  get httpStatus(): number {
    const statusMap: Record<ErrorCategory, number> = {
      [ErrorCategory.Validation]: 400,
      [ErrorCategory.NotFound]: 404,
      [ErrorCategory.Conflict]: 409,
      [ErrorCategory.Unauthorized]: 401,
      [ErrorCategory.Forbidden]: 403,
      [ErrorCategory.Internal]: 500,
      [ErrorCategory.Upstream]: 502,
    };
    return statusMap[this.category] || 500;
  }
}

// Error handler middleware
function errorHandler(err: Error, req: Request, res: Response, next: NextFunction) {
  if (err instanceof DomainError) {
    req.logger.warn({ error_code: err.code, category: err.category }, err.message);
    return res.status(err.httpStatus).json({
      error: { code: err.code, message: err.message, details: err.details },
    });
  }
  req.logger.error({ err }, 'unhandled error');
  return res.status(500).json({
    error: { code: 'INTERNAL_ERROR', message: 'an unexpected error occurred' },
  });
}
```

## SLA Metrics

Define and measure SLOs for every service.

```go
// SLA targets (define in config, not code)
type SLAConfig struct {
    AvailabilityTarget float64       `yaml:"availability_target"` // 99.9%
    LatencyP99Target   time.Duration `yaml:"latency_p99_target"`  // 500ms
    ErrorRateTarget    float64       `yaml:"error_rate_target"`   // 0.1%
}

// SLA metrics
var (
    slaAvailability = meter.Float64ObservableGauge("sla.availability",
        metric.WithDescription("Service availability percentage"),
        metric.WithUnit("%"),
    )

    slaLatencyP99 = meter.Float64ObservableGauge("sla.latency.p99",
        metric.WithDescription("P99 latency in seconds"),
        metric.WithUnit("s"),
    )

    slaErrorRate = meter.Float64ObservableGauge("sla.error_rate",
        metric.WithDescription("Error rate percentage"),
        metric.WithUnit("%"),
    )

    slaBudgetRemaining = meter.Float64ObservableGauge("sla.budget_remaining",
        metric.WithDescription("Remaining error budget percentage"),
        metric.WithUnit("%"),
    )
)
```

**SLA dashboard per service must include:**
- Availability over rolling 30-day window
- P50, P95, P99 latency
- Error rate (5xx / total requests)
- Error budget remaining
- SLO breach alerts

## Log Levels

Use log levels consistently across all services.

| Level | When to use | Example | Action required |
|-------|------------|---------|-----------------|
| **ERROR** | Something broke that needs investigation | Database connection lost, unhandled exception | Alert on-call, investigate immediately |
| **WARN** | Something concerning but handled | Circuit breaker opened, retry succeeded, degraded mode | Review in daily ops check |
| **INFO** | Normal business events | Order created, user signed up, request completed | Audit trail, no action needed |
| **DEBUG** | Troubleshooting detail | SQL query, request/response body, cache hit/miss | Off in production by default |

```go
// ERROR — actionable, needs investigation
logger.ErrorContext(ctx, "failed to process payment",
    "tenant_id", tenantID,
    "order_id", orderID,
    "error", err,
    "payment_method", method,
)

// WARN — concerning but handled
logger.WarnContext(ctx, "circuit breaker opened for payment service",
    "tenant_id", tenantID,
    "failures", cb.Failures(),
    "reset_timeout", cb.ResetTimeout(),
)

// INFO — business event
logger.InfoContext(ctx, "order placed successfully",
    "tenant_id", tenantID,
    "order_id", order.ID,
    "total", order.Total,
    "item_count", len(order.Items),
)

// DEBUG — troubleshooting (off in prod)
logger.DebugContext(ctx, "executing database query",
    "query", "SELECT * FROM orders WHERE tenant_id = $1",
    "params", []interface{}{tenantID},
)
```

**Rules:**
- ERROR logs trigger alerts — don't use ERROR for expected conditions
- WARN is for handled degradation — circuit breakers, retries, fallbacks
- INFO is for business events — one INFO per significant state transition
- DEBUG is verbose and off in production — enable per-service when troubleshooting
- Never log sensitive data (passwords, tokens, PII) at any level
- Never log request/response bodies at INFO level — use DEBUG

## Correlation IDs

Generate a unique request ID at the edge (API gateway, load balancer, or first service). Propagate it through every service call, log line, and trace span.

```go
// Middleware — generate or extract request ID
func RequestIDMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestID := r.Header.Get("X-Request-ID")
        if requestID == "" {
            requestID = "req_" + uuid.New().String()
        }

        ctx := context.WithValue(r.Context(), requestIDKey, requestID)
        w.Header().Set("X-Request-ID", requestID)

        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Propagate to downstream services
func (c *httpClient) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
    // Forward request ID
    if reqID := RequestIDFromContext(ctx); reqID != "" {
        req.Header.Set("X-Request-ID", reqID)
    }
    // Forward trace context (W3C Trace Context propagation via OTel SDK)
    otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
    return c.client.Do(req)
}

// Every log includes request_id
func RequestIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(requestIDKey).(string); ok {
        return v
    }
    return ""
}

// Logging middleware adds request_id and trace_id to every log
func LoggingMiddleware(logger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := r.Context()
            reqLogger := logger.With(
                "request_id", RequestIDFromContext(ctx),
                "trace_id", TraceIDFromContext(ctx),
                "tenant_id", TenantFromContext(ctx),
                "method", r.Method,
                "path", r.URL.Path,
            )
            ctx = context.WithValue(ctx, loggerKey, reqLogger)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

```typescript
// Middleware
function requestIdMiddleware(req: Request, res: Response, next: NextFunction) {
  const requestId = req.headers['x-request-id'] as string || `req_${randomUUID()}`;
  req.id = requestId;
  res.setHeader('X-Request-ID', requestId);
  next();
}

// Propagate to downstream calls
async function callDownstream(ctx: RequestContext, url: string, body: unknown): Promise<Response> {
  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': ctx.requestId,
      'X-Tenant-ID': ctx.tenantId,
      // trace context propagated automatically by OTel SDK
    },
    body: JSON.stringify(body),
  });
}
```

**Flow:**
```
Client → API Gateway (generates req_abc123)
  → Service A (logs with req_abc123, creates trace span)
    → Service B (receives req_abc123 via header, logs with same ID)
      → Database (span records query with req_abc123 context)
  → Service C (receives req_abc123 via header)
    → External API (propagates req_abc123)
```

All logs across all services for a single request can be queried with: `request_id = "req_abc123"`

## Critical Rules

- `tenant_id` on every log, metric, and trace — zero exceptions
- Structured logging only — no string concatenation or template literals for log messages
- JSON format in production — human-readable format only in local development
- Request ID and trace ID on every log line — for cross-service correlation
- ERROR level means "wake someone up" — don't overuse it
- Never log sensitive data — passwords, tokens, API keys, PII
- Metrics at every boundary — HTTP, service, repository, external calls
- Every span records errors — don't swallow errors silently in spans
- SLA dashboards per service — availability, latency, error rate with alerting
- Log levels are meaningful — follow the table above consistently
