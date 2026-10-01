---
skill: observability-patterns
description: Structured logging with enforced redaction, OpenTelemetry metrics with bounded labels (http.route template, no tenant_id), traces with tenant_id, SLIs from histograms and burn-rate alerts, correlation IDs
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

## tenant_id on every log line and span — never on a metric

Every log line and every trace span carries `tenant_id`; that is how you debug a multi-tenant system.
**Metrics are different.** Each distinct label value creates a new time series, multiplied by every
other label and by ~14 histogram buckets. With `tenant_id` × raw URL path, 2,000 tenants and UUIDs in
paths produce millions of series. Prometheus runs out of memory (or the SaaS bill spikes) and the SLO
alerts go blind during the next incident (board review 2026-09-30, SRE-04). So:

| Signal | tenant_id? | Path |
|---|---|---|
| Logs | **yes**, every line | the raw path is fine, **without the query string** (it can carry tokens and PII) |
| Trace spans | **yes**, as a span attribute | `http.route` + `url.path` |
| Metrics | **no**. At most a *bounded* `tenant.tier` (free/pro/enterprise), or a top-N allowlist | **the route template only** (`http.route` = `/api/v1/orders/{id}`) |

For per-tenant questions ("is tenant X slow?"), query traces or logs by `tenant_id`, or use exemplars.
A metric is not the tool for them.

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, OpenTelemetry v1.46.0, against the archetype middleware package (tests/archetype-compile/go/run.sh).

```go
// The tenant comes from the VERIFIED token the auth middleware put in the context — never from a
// client header (X-Tenant-ID is spoofable).
// (middleware.TenantIDFromContext: auth-middleware-go.md)
func TenantFromContext(ctx context.Context) string {
    if id, err := middleware.TenantIDFromContext(ctx); err == nil {
        return id.String()
    }
    return "unknown"
}

func (s *Service) ProcessOrder(ctx context.Context, order *Order) error {
    // Every trace span includes tenant_id
    ctx, span := tracer.Start(ctx, "OrderService.ProcessOrder",
        trace.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(ctx)),
            attribute.String("order_id", order.ID),
        ),
    )
    defer span.End()

    // Every log line includes tenant_id (the logging middleware adds it once; see Correlation IDs)
    s.logger.InfoContext(ctx, "processing order",
        "tenant_id", TenantFromContext(ctx),
        "order_id", order.ID,
        "amount_cents", order.TotalCents,
    )
    // ...
    return nil
}

// Metrics: bounded labels only (see the metrics middleware below)
```

```typescript
// req.auth is set by the auth middleware from the verified token
function contextLogger(req: Request, _res: Response, next: NextFunction) {
  req.logger = logger.child({ tenant_id: req.auth?.tenantId ?? "unknown", request_id: req.id, trace_id: getTraceId(req) });
  next();
}

req.logger.info({ order_id: order.id, amount_cents: order.totalCents }, "processing order");
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
| `tenant_id` | Verified credential, via context | Whose request |
| `request_id` | Generated at edge | Correlate within a request |
| `trace_id` | OpenTelemetry | Correlate across services |
| `service` | Config | Which service |
| `component` | Logger child | Which module (optional, useful for large services) |

## OpenTelemetry Metrics at Every Boundary

Instrument every boundary: HTTP handlers, repository calls, external API calls, queues. HTTP server
metrics follow the **stable OTel HTTP semantic conventions**:
- `http.server.request.duration` is a histogram in seconds. Its attributes are
  `http.request.method`, `http.route`, `http.response.status_code`, `url.scheme` and `error.type`.
- `http.route` is the route **template**. The spec says the URI path can NOT substitute it; when the
  router can't supply the template (an unmatched 404), leave the attribute out.
- A method outside the known set is recorded as `_OTHER`.
- The request count comes from the histogram's count, so don't keep a separate counter.

(Spec: https://opentelemetry.io/docs/specs/semconv/http/http-metrics/.)

```go
import (
    "go.opentelemetry.io/otel/metric"
)

var (
    meter           = otel.Meter("order-service")
    requestDuration metric.Float64Histogram
    ordersPlaced    metric.Int64Counter
)

func initMetrics() error {
    var err error
    requestDuration, err = meter.Float64Histogram("http.server.request.duration",
        metric.WithDescription("Duration of HTTP server requests"),
        metric.WithUnit("s"),
        metric.WithExplicitBucketBoundaries(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10),
    )
    if err != nil {
        return err
    }
    ordersPlaced, err = meter.Int64Counter("business.orders.placed", metric.WithUnit("{order}"))
    return err
}

var knownMethods = map[string]bool{"GET": true, "HEAD": true, "POST": true, "PUT": true, "PATCH": true, "DELETE": true, "OPTIONS": true}

// Metrics middleware — every label is bounded.
func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        rec := &statusRecorder{ResponseWriter: w, statusCode: 200}
        next.ServeHTTP(rec, r)

        method := r.Method
        if !knownMethods[method] {
            method = "_OTHER"
        }
        attrs := []attribute.KeyValue{
            attribute.String("http.request.method", method),
            attribute.Int("http.response.status_code", rec.statusCode),
            attribute.String("url.scheme", scheme(r)),
        }
        // The TEMPLATE, known only after routing: net/http ServeMux exposes it as r.Pattern (go.dev/issue/66405);
        // chi: chi.RouteContext(r.Context()).RoutePattern(). Never r.URL.Path.
        if route := routePattern(r); route != "" {
            attrs = append(attrs, attribute.String("http.route", route))
        }
        if rec.statusCode >= 500 {
            attrs = append(attrs, attribute.String("error.type", strconv.Itoa(rec.statusCode)))
        }
        requestDuration.Record(r.Context(), time.Since(start).Seconds(), metric.WithAttributes(attrs...))
    })
}

// Business event metrics — bounded labels (payment method is a small enum); no tenant_id
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    order, err := s.processOrder(ctx, req)
    if err != nil {
        return nil, err
    }
    ordersPlaced.Add(ctx, 1, metric.WithAttributes(attribute.String("payment_method", string(order.PaymentMethod))))
    return order, nil
}
```

```typescript
import { metrics } from "@opentelemetry/api";

const meter = metrics.getMeter("order-service");
const requestDuration = meter.createHistogram("http.server.request.duration", {
  description: "Duration of HTTP server requests",
  unit: "s",
  advice: { explicitBucketBoundaries: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10] },
});
const KNOWN = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]);

function metricsMiddleware(req: Request, res: Response, next: NextFunction) {
  const start = process.hrtime.bigint();
  res.on("finish", () => {
    const attrs: Record<string, string | number> = {
      "http.request.method": KNOWN.has(req.method) ? req.method : "_OTHER",
      "http.response.status_code": res.statusCode,
      "url.scheme": req.protocol,
    };
    // Express: req.baseUrl + req.route.path is the template ("/api/v1/orders/:id"); an unmatched request
    // has no req.route → no http.route. NEVER fall back to req.path (raw path = unbounded series).
    if (req.route?.path) attrs["http.route"] = `${req.baseUrl}${req.route.path}`;
    if (res.statusCode >= 500) attrs["error.type"] = String(res.statusCode);
    requestDuration.record(Number(process.hrtime.bigint() - start) / 1e9, attrs);
  });
  next();
}
```

### Key metrics to instrument

| Metric | Type | Labels (all bounded) | Purpose |
|--------|------|--------|---------|
| `http.server.request.duration` | Histogram (s) | `http.request.method`, `http.route`, `http.response.status_code`, `url.scheme`, `error.type` | Rate, errors and latency (RED); the count *is* the request count |
| `http.server.active_requests` | UpDownCounter | `http.request.method`, `url.scheme` | Concurrency / saturation (no route: it isn't known when the request starts) |
| `db.client.operation.duration` | Histogram (s) | `db.operation.name`, `db.collection.name` (table) | Database performance |
| `db.client.connection.count` / pool wait | Gauge/Histogram | `state` (idle/used), pool name | Pool saturation against the connection budget |
| `http.client.request.duration` | Histogram (s) | `server.address` (dependency host), `http.request.method`, `http.response.status_code` | Upstream latency and errors |
| `business.<event>` | Counter | a small enum (`type`, `payment_method`); at most a bounded `tenant.tier` | Business KPIs |

**Cardinality rule:** a label value must come from a small, known set. Never use IDs, emails, raw
paths, query strings, error messages or `tenant_id`. A unit test proves the route template is used:
request `/api/v1/orders/123` and `/api/v1/orders/456`, then assert exactly one series with
`http.route="/api/v1/orders/{id}"`.

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

The taxonomy, codes and wire shape are defined once: `~/.claude/skills/api/response-envelope.md` (what
the client sees) and `~/.claude/skills/backend/archetypes/error-handling-{{LANG}}.md` (the AppError type
and middleware). This pack only adds what observability needs from errors:

- Log each failed request **once**, at the top of the stack. Log the full cause chain, the `code`, the
  `request_id` and the `tenant_id`. Use ERROR for 5xx and WARN for handled 4xx that suggest abuse (401
  and 403 bursts, 429).
- Mark the span as an error (`span.RecordError(err)`, `span.SetStatus(codes.Error, code)`) for 5xx
  only. A 404 is not a server error.
- Metrics carry `error.type` (the status code or a small enum), never the error message.

## SLOs and Alerting

SLOs come from the NFR-* targets (`reliability_agent` writes the SLO table). **Compute SLIs at query
time from the request histogram; don't compute them in-process.** Percentiles can't be averaged
across pods, and an in-memory 30-day window resets on every restart, so per-pod `sla.latency.p99` or
`sla.budget_remaining` gauges look healthy while the fleet breaches.

```promql
# Availability SLI (5-minute rate): the share of requests that did not fail server-side
1 - (
  sum(rate(http_server_request_duration_seconds_count{service="order-service", http_response_status_code=~"5.."}[5m]))
/ sum(rate(http_server_request_duration_seconds_count{service="order-service"}[5m]))
)

# Latency SLI: the share of requests faster than the NFR threshold (0.5 s must be a bucket boundary)
  sum(rate(http_server_request_duration_seconds_bucket{service="order-service", le="0.5"}[5m]))
/ sum(rate(http_server_request_duration_seconds_count{service="order-service"}[5m]))
```

(Metric names are as the OTel → Prometheus exporter renders them; check your exporter's naming.)

- **Alert on symptoms with multi-window burn rates,** not on ERROR log lines. These are the Google SRE
  Workbook defaults for a 30-day window:
  - page at 14.4× (the 1 h and 5 m windows both burning);
  - page at 6× (the 6 h and 30 m windows);
  - open a ticket at 1× (the 3 d and 6 h windows).
- Recording rules, alert rules and the dashboard are **code** in the repo (`deploy/observability/`),
  generated from the SLO table.
- **Dashboard per service:** request rate, error ratio and latency percentiles by `http.route`; error
  budget remaining over the SLO window; pool saturation; dependency latency.

## Log Levels

Use log levels consistently across all services.

| Level | When to use | Example | Action required |
|-------|------------|---------|-----------------|
| **ERROR** | Something broke that needs investigation | Database connection lost, unhandled exception | Investigate; alerts come from SLO burn rates, not from this level |
| **WARN** | Something concerning but handled | Circuit breaker opened, retry succeeded, degraded mode | Review in daily ops check |
| **INFO** | Normal business events | Order created, user signed up, request completed | Audit trail, no action needed |
| **DEBUG** | Troubleshooting detail | Query shape, cache hit/miss, timing breakdown | Off in production by default |

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
    "amount_cents", order.TotalCents,
    "item_count", len(order.Items),
)

// DEBUG — troubleshooting (off in prod). The query shape, never the parameter values.
logger.DebugContext(ctx, "executing database query",
    "query", "SELECT * FROM orders WHERE tenant_id = $1",
    "param_count", 1,
)
```

### Redaction is enforced at the logger, not remembered per call site

DEBUG gets switched on in production exactly during incidents, and that is when request bodies with
passwords and tokens get shipped to the log backend (SRE-14). So the handler redacts **by key name**
at every level, and bodies are never logged whole:

```go
var sensitive = regexp.MustCompile(`(?i)(pass(word)?|secret|token|authorization|cookie|api[-_]?key|session|card|cvv|iban|ssn)`)

func NewLogger(logLevel slog.Leveler) *slog.Logger {
    return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: logLevel, // from config; DEBUG stays safe because of the line below
        ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
            if sensitive.MatchString(a.Key) {
                return slog.String(a.Key, "[REDACTED]")
            }
            return a
        },
    }))
}
```

```typescript
const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: {
    paths: ["password", "*.password", "token", "*.token", "req.headers.authorization", "req.headers.cookie",
            "*.apiKey", "*.secret", "*.cardNumber"],
    censor: "[REDACTED]",
  },
});
```

**Rules:**
- ERROR means a server-side failure someone should look at. Alerts come from SLO burn rates, not from
  counting ERROR lines.
- WARN is for handled degradation — circuit breakers, retries, fallbacks
- INFO is for business events — one INFO per significant state transition
- DEBUG is off in production. Turning it on must stay safe, because redaction applies at every level.
- Never log request or response bodies. Log an allow-listed set of fields.
- Never log passwords, tokens, session IDs, API keys, full card or bank numbers, or free-text PII. A
  unit test logs such fields and asserts they come out `[REDACTED]`.

## Correlation IDs

Generate a unique request ID at the edge (API gateway, load balancer, or first service). Propagate it
through every service call, log line, trace span, **and error body** (`error.request_id`, see the envelope).

```go
var validRequestID = regexp.MustCompile(`^[A-Za-z0-9._-]{8,128}$`)

type ctxKey int

const (
    requestIDKey ctxKey = iota
    loggerKey
)

// Middleware — accept a well-formed inbound ID (from our own gateway), otherwise generate one
func RequestIDMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestID := r.Header.Get("X-Request-Id")
        if !validRequestID.MatchString(requestID) { // bounded length and charset: no log injection
            requestID = "req_" + uuid.NewString()
        }
        ctx := context.WithValue(r.Context(), requestIDKey, requestID)
        w.Header().Set("X-Request-Id", requestID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Propagate to downstream services
func (c *httpClient) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
    if reqID := RequestIDFromContext(ctx); reqID != "" {
        req.Header.Set("X-Request-Id", reqID)
    }
    // W3C Trace Context (traceparent) via the OTel propagator
    otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
    return c.client.Do(req)
}

func RequestIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(requestIDKey).(string); ok {
        return v
    }
    return ""
}

func TraceIDFromContext(ctx context.Context) string {
    if sc := trace.SpanContextFromContext(ctx); sc.HasTraceID() {
        return sc.TraceID().String()
    }
    return ""
}

// Logging middleware adds request_id, trace_id and tenant_id to every log line of the request
func LoggingMiddleware(logger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := r.Context()
            reqLogger := logger.With(
                "request_id", RequestIDFromContext(ctx),
                "trace_id", TraceIDFromContext(ctx),
                "tenant_id", TenantFromContext(ctx),
                "method", r.Method,
                "path", r.URL.Path, // no query string: it can carry tokens and PII
            )
            ctx = context.WithValue(ctx, loggerKey, reqLogger)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

```typescript
const VALID_ID = /^[A-Za-z0-9._-]{8,128}$/;

function requestIdMiddleware(req: Request, res: Response, next: NextFunction) {
  const inbound = req.header("x-request-id");
  req.id = inbound && VALID_ID.test(inbound) ? inbound : `req_${randomUUID()}`;
  res.setHeader("X-Request-Id", req.id);
  next();
}

// Propagate to downstream calls. The downstream service authenticates the CALLER (service token or
// mTLS) and takes the tenant from that credential. A forwarded X-Tenant-ID header is a hint for
// logging only, never an authorization input.
async function callDownstream(ctx: RequestContext, url: string, body: unknown): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-Id": ctx.requestId, Authorization: `Bearer ${ctx.serviceToken}` },
    body: JSON.stringify(body),
    signal: ctx.signal, // the inbound deadline
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

## What coding agents implement (the checklist reviewers verify)

1. A JSON logger with a redacting handler. Each request's logger carries `request_id`, `trace_id`,
   `tenant_id`, `method` and `path` (without the query string).
2. The request-ID middleware: it validates an inbound ID, generates one otherwise, and echoes
   `X-Request-Id`. The same ID appears in `meta.request_id` and in `error.request_id`.
3. OTel tracing with W3C propagation on inbound and outbound HTTP and on DB calls. `tenant_id` is a
   span attribute.
4. The `http.server.request.duration` histogram with the bounded label set above. `http.route` is the
   template, and there is no `tenant_id` label.
5. Pool and dependency metrics: connections in use and wait time, and outbound call duration by
   dependency.
6. Tests:
   - two IDs on one route produce one `http.route` series;
   - a `password`/`authorization` field is logged as `[REDACTED]`;
   - an error response's `request_id` equals the `X-Request-Id` header.

## Critical Rules

- `tenant_id` on every log line and span — and on no metric (at most a bounded `tenant.tier`)
- Metric labels come from bounded sets. `http.route` is the route template, never `r.URL.Path`/`req.path`.
- Structured logging only — no string concatenation or template literals for log messages
- JSON format in production — human-readable format only in local development
- Request ID and trace ID on every log line — for cross-service correlation
- Redaction happens in the logger handler at every level; bodies are never logged
- The tenant comes from the verified credential, never from a client-supplied header
- Metrics at every boundary — HTTP, repository, external calls, pools
- Every span records errors — don't swallow errors silently in spans
- SLIs come from histograms at query time; alerts use multi-window burn rates; dashboards and alert rules are code
- Log levels are meaningful — follow the table above consistently
