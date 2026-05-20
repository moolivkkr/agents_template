---
skill: observability-go
description: Go OpenTelemetry integration — traces, metrics, structured logging (slog), correlation IDs, tenant-aware instrumentation, Prometheus endpoint, DB/Redis/HTTP span instrumentation
version: "1.0"
tags:
  - go
  - opentelemetry
  - observability
  - tracing
  - metrics
  - logging
  - slog
  - prometheus
  - archetype
  - backend
---

# Go Observability Archetype

> **CANONICAL REFERENCE**: This file is the single source of truth for Go observability implementation. It is the language-specific complement to `core/observability-patterns.md`, which defines the cross-language strategy and required fields. Every generated Go service MUST follow these patterns.

Complete OpenTelemetry integration for Go backend services covering traces, metrics, structured logging, and full correlation across all three signals.

---

## Dependencies

```go
// go.mod — required observability modules
require (
    go.opentelemetry.io/otel                       v1.28.0
    go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.28.0
    go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc v1.28.0
    go.opentelemetry.io/otel/exporters/prometheus   v0.50.0
    go.opentelemetry.io/otel/sdk                    v1.28.0
    go.opentelemetry.io/otel/sdk/metric             v1.28.0
    go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.53.0
    go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.53.0
    github.com/prometheus/client_golang             v1.19.1
    github.com/XSAM/otelsql                        v0.33.0
    github.com/redis/go-redis/extra/redisotel/v9   v9.5.1
    log/slog                                        // stdlib since Go 1.21
)
```

---

## 1. Traces

### 1.1 TracerProvider Setup (main.go)

```go
package main

import (
    "context"
    "fmt"
    "log/slog"
    "os"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/propagation"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

// initTracer sets up the global TracerProvider with OTLP gRPC export.
// Call shutdown() in main's defer to flush remaining spans.
func initTracer(ctx context.Context, serviceName, serviceVersion string) (shutdown func(context.Context) error, err error) {
    res, err := resource.Merge(
        resource.Default(),
        resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName(serviceName),
            semconv.ServiceVersion(serviceVersion),
            semconv.DeploymentEnvironment(os.Getenv("APP_ENV")),
        ),
    )
    if err != nil {
        return nil, fmt.Errorf("creating resource: %w", err)
    }

    // OTLP exporter — reads OTEL_EXPORTER_OTLP_ENDPOINT env var by default
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithInsecure(), // remove for production TLS
    )
    if err != nil {
        return nil, fmt.Errorf("creating OTLP trace exporter: %w", err)
    }

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter,
            sdktrace.WithBatchTimeout(5*time.Second),
            sdktrace.WithMaxExportBatchSize(512),
        ),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(1.0))), // 100% in dev, reduce in prod
    )

    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{}, // W3C Trace Context
        propagation.Baggage{},     // W3C Baggage
    ))

    return tp.Shutdown, nil
}
```

### 1.2 Span Creation in Handlers, Services, Repositories

```go
package order

import (
    "context"
    "net/http"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

// One tracer per package — named after the module
var tracer = otel.Tracer("myapp/internal/order")

// --- Handler layer ---

func (h *Handler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    // Root HTTP span is created automatically by otelhttp middleware (see 1.4).
    // Add business attributes to the current span.
    span := trace.SpanFromContext(ctx)
    span.SetAttributes(
        attribute.String("tenant_id", TenantFromContext(ctx)),
        attribute.String("user_id", UserIDFromContext(ctx)),
    )

    order, err := h.service.CreateOrder(ctx, parseCreateRequest(r))
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        respondError(w, err)
        return
    }

    span.SetAttributes(attribute.String("order_id", order.ID))
    respondJSON(w, http.StatusCreated, order)
}

// --- Service layer ---

func (s *Service) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    ctx, span := tracer.Start(ctx, "OrderService.CreateOrder",
        trace.WithAttributes(
            attribute.String("tenant_id", TenantFromContext(ctx)),
        ),
    )
    defer span.End()

    if err := req.Validate(); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "validation failed")
        return nil, err
    }

    order := newOrder(req)

    // Span event — marks a significant checkpoint within the span
    span.AddEvent("order.validated", trace.WithAttributes(
        attribute.Int("item_count", len(order.Items)),
        attribute.String("currency", order.Currency),
    ))

    if err := s.repo.Save(ctx, order); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "persist failed")
        return nil, fmt.Errorf("saving order: %w", err)
    }

    span.SetAttributes(
        attribute.String("order_id", order.ID),
        attribute.Float64("order_total", order.Total.InexactFloat64()),
    )
    return order, nil
}

// --- Repository layer ---

func (r *PostgresOrderRepo) Save(ctx context.Context, order *Order) error {
    ctx, span := tracer.Start(ctx, "postgres.orders.insert",
        trace.WithSpanKind(trace.SpanKindClient),
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.operation", "INSERT"),
            attribute.String("db.sql.table", "orders"),
            attribute.String("tenant_id", TenantFromContext(ctx)),
        ),
    )
    defer span.End()

    query := `INSERT INTO orders (id, tenant_id, user_id, total, currency, status, created_at)
              VALUES ($1, $2, $3, $4, $5, $6, $7)`

    _, err := r.pool.Exec(ctx, query,
        order.ID, order.TenantID, order.UserID,
        order.Total, order.Currency, order.Status, order.CreatedAt,
    )
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return fmt.Errorf("inserting order: %w", err)
    }
    return nil
}
```

### 1.3 Span Attributes — Required on Every Span

| Attribute | Layer | Source |
|-----------|-------|--------|
| `tenant_id` | All | Context middleware |
| `user_id` | Handler, Service | Auth middleware |
| `request_id` | Handler | Request ID middleware |
| `order_id` (or relevant entity) | Service, Repo | Business logic |
| `db.system` | Repository | Hardcoded |
| `db.operation` | Repository | Query type |
| `db.sql.table` | Repository | Target table |

### 1.4 HTTP Middleware — otelhttp (Automatic Span Creation)

```go
package server

import (
    "net/http"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

// WrapHandler wraps your root mux so every incoming request gets a span.
func NewServer(handler http.Handler) *http.Server {
    // otelhttp creates a root span for every request with:
    //   - span name = "HTTP {METHOD} {route}"
    //   - http.method, http.url, http.status_code, etc.
    wrappedHandler := otelhttp.NewHandler(handler, "http-server",
        otelhttp.WithMessageEvents(otelhttp.ReadEvents, otelhttp.WriteEvents),
        otelhttp.WithSpanNameFormatter(func(operation string, r *http.Request) string {
            // Use the route pattern if available (Go 1.22+ ServeMux)
            if pattern := r.Pattern; pattern != "" {
                return fmt.Sprintf("HTTP %s %s", r.Method, pattern)
            }
            return fmt.Sprintf("HTTP %s %s", r.Method, r.URL.Path)
        }),
    )

    return &http.Server{
        Addr:    ":8080",
        Handler: wrappedHandler,
    }
}

// For outgoing HTTP calls, wrap the transport:
func NewInstrumentedHTTPClient() *http.Client {
    return &http.Client{
        Transport: otelhttp.NewTransport(http.DefaultTransport),
        Timeout:   30 * time.Second,
    }
}
```

### 1.5 Database Span Instrumentation (otelsql)

```go
package database

import (
    "database/sql"
    "fmt"

    "github.com/XSAM/otelsql"
    semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

// OpenDB wraps database/sql with automatic span creation for every query.
func OpenDB(dsn string) (*sql.DB, error) {
    db, err := otelsql.Open("pgx", dsn,
        otelsql.WithAttributes(
            semconv.DBSystemPostgreSQL,
        ),
        otelsql.WithDBName("myapp"),
        otelsql.WithSpanOptions(otelsql.SpanOptions{
            Ping:      true,
            RowsNext:  false, // avoid noisy per-row spans
            RowsClose: false,
        }),
    )
    if err != nil {
        return nil, fmt.Errorf("opening instrumented db: %w", err)
    }

    // Set pool limits (see performance-go.md for detailed tuning)
    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(10)
    db.SetConnMaxLifetime(5 * time.Minute)

    return db, nil
}

// If using pgx directly (without database/sql), use manual spans as in 1.2 repo example.
```

### 1.6 Redis Span Instrumentation

```go
package cache

import (
    "github.com/redis/go-redis/extra/redisotel/v9"
    "github.com/redis/go-redis/v9"
)

func NewRedisClient(addr string) *redis.Client {
    rdb := redis.NewClient(&redis.Options{
        Addr:     addr,
        PoolSize: 20,
    })

    // Enable tracing — every Redis command gets a child span
    if err := redisotel.InstrumentTracing(rdb); err != nil {
        panic(fmt.Sprintf("redis tracing instrumentation: %v", err))
    }

    // Enable metrics — command duration, pool stats
    if err := redisotel.InstrumentMetrics(rdb); err != nil {
        panic(fmt.Sprintf("redis metrics instrumentation: %v", err))
    }

    return rdb
}
```

### 1.7 Error Recording on Spans

```go
// ALWAYS record errors on the span that encountered them.
// This surfaces errors in trace UIs (Jaeger, Grafana Tempo, Honeycomb).

func (s *Service) Process(ctx context.Context, id string) error {
    ctx, span := tracer.Start(ctx, "Service.Process")
    defer span.End()

    result, err := s.repo.FindByID(ctx, id)
    if err != nil {
        // RecordError adds an exception event to the span
        span.RecordError(err, trace.WithAttributes(
            attribute.String("entity_id", id),
        ))
        // SetStatus marks the span as errored in the trace UI
        span.SetStatus(codes.Error, err.Error())
        return fmt.Errorf("finding entity %s: %w", id, err)
    }

    // For non-fatal issues, use span events instead of RecordError
    if result.IsDeprecated() {
        span.AddEvent("entity.deprecated_access", trace.WithAttributes(
            attribute.String("entity_id", id),
            attribute.String("deprecation_date", result.DeprecatedAt.String()),
        ))
    }

    return nil
}
```

### 1.8 Context Propagation — Full Picture

```go
// Context flows through every layer, carrying trace context + app values.
//
//   Request arrives
//     -> otelhttp extracts W3C traceparent header, creates root span
//     -> RequestIDMiddleware injects request_id into context
//     -> TenantMiddleware injects tenant_id into context
//     -> AuthMiddleware injects user_id into context
//     -> Handler reads context, calls service
//       -> Service reads context, starts child span, calls repo
//         -> Repo reads context, starts child span, executes query
//
// For outgoing HTTP calls:
//     -> otelhttp.NewTransport injects traceparent + baggage into outgoing headers
//     -> Downstream service extracts them, continues the trace

// Context key types (unexported to prevent collisions)
type ctxKey int

const (
    ctxKeyRequestID ctxKey = iota
    ctxKeyTenantID
    ctxKeyUserID
    ctxKeyLogger
)

func TenantFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(ctxKeyTenantID).(string); ok {
        return v
    }
    return "unknown"
}

func RequestIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(ctxKeyRequestID).(string); ok {
        return v
    }
    return ""
}

func UserIDFromContext(ctx context.Context) string {
    if v, ok := ctx.Value(ctxKeyUserID).(string); ok {
        return v
    }
    return ""
}

// TraceIDFromContext extracts the trace ID from the current span.
func TraceIDFromContext(ctx context.Context) string {
    span := trace.SpanFromContext(ctx)
    if span.SpanContext().HasTraceID() {
        return span.SpanContext().TraceID().String()
    }
    return ""
}

// SpanIDFromContext extracts the span ID from the current span.
func SpanIDFromContext(ctx context.Context) string {
    span := trace.SpanFromContext(ctx)
    if span.SpanContext().HasSpanID() {
        return span.SpanContext().SpanID().String()
    }
    return ""
}
```

---

## 2. Metrics

### 2.1 MeterProvider Setup (main.go)

```go
package main

import (
    "context"
    "fmt"
    "net/http"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/otel/exporters/prometheus"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    "go.opentelemetry.io/otel/sdk/resource"
    promclient "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

// initMetrics sets up the global MeterProvider with both OTLP and Prometheus export.
func initMetrics(ctx context.Context, res *resource.Resource) (shutdown func(context.Context) error, err error) {
    // OTLP exporter — push metrics to collector
    otlpExporter, err := otlpmetricgrpc.New(ctx,
        otlpmetricgrpc.WithInsecure(),
    )
    if err != nil {
        return nil, fmt.Errorf("creating OTLP metric exporter: %w", err)
    }

    // Prometheus exporter — pull metrics via /metrics endpoint
    promExporter, err := prometheus.New(
        prometheus.WithRegisterer(promclient.DefaultRegisterer),
    )
    if err != nil {
        return nil, fmt.Errorf("creating Prometheus exporter: %w", err)
    }

    mp := sdkmetric.NewMeterProvider(
        sdkmetric.WithResource(res),
        sdkmetric.WithReader(
            sdkmetric.NewPeriodicReader(otlpExporter,
                sdkmetric.WithInterval(15*time.Second),
            ),
        ),
        sdkmetric.WithReader(promExporter), // also serves /metrics
    )

    otel.SetMeterProvider(mp)
    return mp.Shutdown, nil
}

// serveMetrics starts the Prometheus scrape endpoint on a separate port.
func serveMetrics(addr string) *http.Server {
    mux := http.NewServeMux()
    mux.Handle("/metrics", promhttp.Handler())
    mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
        w.Write([]byte("ok"))
    })

    srv := &http.Server{Addr: addr, Handler: mux}
    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("metrics server failed", "error", err)
        }
    }()
    return srv
}
```

### 2.2 Counter — Request Count by Route, Status, Tenant

```go
package middleware

import (
    "net/http"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/metric"
)

var meter = otel.Meter("myapp/middleware")

var (
    httpRequestTotal    metric.Int64Counter
    httpRequestDuration metric.Float64Histogram
    httpActiveRequests  metric.Int64UpDownCounter
)

func init() {
    var err error

    httpRequestTotal, err = meter.Int64Counter("http.server.request.total",
        metric.WithDescription("Total HTTP requests received"),
        metric.WithUnit("{request}"),
    )
    if err != nil {
        panic(fmt.Sprintf("creating request counter: %v", err))
    }

    httpRequestDuration, err = meter.Float64Histogram("http.server.request.duration",
        metric.WithDescription("HTTP request duration in seconds"),
        metric.WithUnit("s"),
        metric.WithExplicitBucketBoundaries(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    if err != nil {
        panic(fmt.Sprintf("creating request duration histogram: %v", err))
    }

    httpActiveRequests, err = meter.Int64UpDownCounter("http.server.active_requests",
        metric.WithDescription("Number of in-flight HTTP requests"),
        metric.WithUnit("{request}"),
    )
    if err != nil {
        panic(fmt.Sprintf("creating active requests gauge: %v", err))
    }
}

// MetricsMiddleware records request count, duration, and active requests.
func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx := r.Context()
        start := time.Now()
        tenantID := TenantFromContext(ctx)

        baseAttrs := []attribute.KeyValue{
            attribute.String("tenant_id", tenantID),
            attribute.String("http.method", r.Method),
            attribute.String("http.route", routePattern(r)),
        }

        httpActiveRequests.Add(ctx, 1, metric.WithAttributes(baseAttrs...))
        defer httpActiveRequests.Add(ctx, -1, metric.WithAttributes(baseAttrs...))

        rec := &statusRecorder{ResponseWriter: w, statusCode: http.StatusOK}
        next.ServeHTTP(rec, r)

        duration := time.Since(start).Seconds()
        allAttrs := append(baseAttrs, attribute.Int("http.status_code", rec.statusCode))

        httpRequestTotal.Add(ctx, 1, metric.WithAttributes(allAttrs...))
        httpRequestDuration.Record(ctx, duration, metric.WithAttributes(allAttrs...))
    })
}

// statusRecorder captures the status code written by downstream handlers.
type statusRecorder struct {
    http.ResponseWriter
    statusCode int
}

func (r *statusRecorder) WriteHeader(code int) {
    r.statusCode = code
    r.ResponseWriter.WriteHeader(code)
}

// routePattern returns the registered route pattern (Go 1.22+ ServeMux)
// or falls back to the raw path. Avoid high-cardinality paths in metrics.
func routePattern(r *http.Request) string {
    if p := r.Pattern; p != "" {
        return p
    }
    return r.URL.Path
}
```

### 2.3 Histogram — DB Query Duration

```go
package repository

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/metric"
)

var repoMeter = otel.Meter("myapp/repository")

var dbQueryDuration metric.Float64Histogram

func init() {
    var err error
    dbQueryDuration, err = repoMeter.Float64Histogram("db.query.duration",
        metric.WithDescription("Database query duration in seconds"),
        metric.WithUnit("s"),
        metric.WithExplicitBucketBoundaries(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
    )
    if err != nil {
        panic(fmt.Sprintf("creating db query duration histogram: %v", err))
    }
}

// recordQueryDuration is a helper called after every DB operation.
func recordQueryDuration(ctx context.Context, start time.Time, operation, table string) {
    duration := time.Since(start).Seconds()
    dbQueryDuration.Record(ctx, duration, metric.WithAttributes(
        attribute.String("tenant_id", TenantFromContext(ctx)),
        attribute.String("db.operation", operation),
        attribute.String("db.sql.table", table),
    ))
}

// Usage in repo methods:
func (r *PostgresOrderRepo) FindByID(ctx context.Context, id string) (*Order, error) {
    start := time.Now()
    defer recordQueryDuration(ctx, start, "SELECT", "orders")

    // ... query execution ...
}
```

### 2.4 Gauge — Active Connections, Goroutines, Queue Depth

```go
package observability

import (
    "context"
    "database/sql"
    "runtime"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/metric"
)

var runtimeMeter = otel.Meter("myapp/runtime")

// RegisterRuntimeMetrics registers observable gauges for Go runtime stats.
func RegisterRuntimeMetrics(db *sql.DB) error {
    // Goroutine count
    _, err := runtimeMeter.Int64ObservableGauge("go.goroutine.count",
        metric.WithDescription("Number of active goroutines"),
        metric.WithUnit("{goroutine}"),
        metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
            o.Observe(int64(runtime.NumGoroutine()))
            return nil
        }),
    )
    if err != nil {
        return fmt.Errorf("registering goroutine gauge: %w", err)
    }

    // DB pool — open connections
    _, err = runtimeMeter.Int64ObservableGauge("db.pool.open_connections",
        metric.WithDescription("Number of open database connections"),
        metric.WithUnit("{connection}"),
        metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
            stats := db.Stats()
            o.Observe(int64(stats.OpenConnections))
            return nil
        }),
    )
    if err != nil {
        return fmt.Errorf("registering db pool gauge: %w", err)
    }

    // DB pool — in-use connections
    _, err = runtimeMeter.Int64ObservableGauge("db.pool.in_use",
        metric.WithDescription("Number of in-use database connections"),
        metric.WithUnit("{connection}"),
        metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
            stats := db.Stats()
            o.Observe(int64(stats.InUse))
            return nil
        }),
    )
    if err != nil {
        return fmt.Errorf("registering db in-use gauge: %w", err)
    }

    // DB pool — idle connections
    _, err = runtimeMeter.Int64ObservableGauge("db.pool.idle",
        metric.WithDescription("Number of idle database connections"),
        metric.WithUnit("{connection}"),
        metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
            stats := db.Stats()
            o.Observe(int64(stats.Idle))
            return nil
        }),
    )
    if err != nil {
        return fmt.Errorf("registering db idle gauge: %w", err)
    }

    return nil
}

// QueueDepthGauge tracks items in an async processing queue.
// Call this from your worker pool or queue consumer.
func RegisterQueueGauge(queueLen func() int64) error {
    _, err := runtimeMeter.Int64ObservableGauge("queue.depth",
        metric.WithDescription("Number of items pending in the work queue"),
        metric.WithUnit("{item}"),
        metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
            o.Observe(queueLen())
            return nil
        }),
    )
    return err
}
```

### 2.5 Custom Business Metrics

```go
package service

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/metric"
)

var bizMeter = otel.Meter("myapp/business")

var (
    ordersCreated metric.Int64Counter
    orderRevenue  metric.Float64Counter
    itemsCreated  metric.Int64Counter
)

func init() {
    var err error

    ordersCreated, err = bizMeter.Int64Counter("business.orders.created",
        metric.WithDescription("Total orders created"),
        metric.WithUnit("{order}"),
    )
    if err != nil {
        panic(fmt.Sprintf("creating orders counter: %v", err))
    }

    orderRevenue, err = bizMeter.Float64Counter("business.orders.revenue",
        metric.WithDescription("Total revenue from orders"),
        metric.WithUnit("USD"),
    )
    if err != nil {
        panic(fmt.Sprintf("creating revenue counter: %v", err))
    }

    itemsCreated, err = bizMeter.Int64Counter("business.items.created",
        metric.WithDescription("Total items created"),
        metric.WithUnit("{item}"),
    )
    if err != nil {
        panic(fmt.Sprintf("creating items counter: %v", err))
    }
}

// After a successful order creation:
func (s *OrderService) recordBusinessMetrics(ctx context.Context, order *Order) {
    attrs := metric.WithAttributes(
        attribute.String("tenant_id", TenantFromContext(ctx)),
        attribute.String("payment_method", order.PaymentMethod),
        attribute.String("currency", order.Currency),
    )

    ordersCreated.Add(ctx, 1, attrs)
    orderRevenue.Add(ctx, order.Total.InexactFloat64(), attrs)
    itemsCreated.Add(ctx, int64(len(order.Items)), attrs)
}
```

### 2.6 Prometheus Endpoint

The `/metrics` endpoint is served by `serveMetrics()` in section 2.1. Kubernetes `ServiceMonitor` example:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
    - port: metrics     # typically 9090 or 2112
      path: /metrics
      interval: 15s
```

---

## 3. Structured Logging

### 3.1 slog Setup with JSON Handler

```go
package logging

import (
    "context"
    "io"
    "log/slog"
    "os"
    "strings"
)

// NewLogger creates the application logger.
// Production: JSON output, INFO level.
// Development: Text output, DEBUG level.
func NewLogger(serviceName, version, env string) *slog.Logger {
    var handler slog.Handler

    level := slog.LevelInfo
    if env == "development" || env == "local" {
        level = slog.LevelDebug
    }

    opts := &slog.HandlerOptions{
        Level:     level,
        AddSource: env == "development", // file:line in dev only (performance cost)
        ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
            // Mask sensitive fields
            return maskSensitiveAttr(a)
        },
    }

    if env == "development" || env == "local" {
        handler = slog.NewTextHandler(os.Stdout, opts)
    } else {
        handler = slog.NewJSONHandler(os.Stdout, opts)
    }

    logger := slog.New(handler).With(
        "service", serviceName,
        "version", version,
        "env", env,
    )

    slog.SetDefault(logger)
    return logger
}

// maskSensitiveAttr redacts known-sensitive field names.
func maskSensitiveAttr(a slog.Attr) slog.Attr {
    sensitiveKeys := map[string]bool{
        "password":      true,
        "token":         true,
        "secret":        true,
        "authorization": true,
        "api_key":       true,
        "ssn":           true,
        "credit_card":   true,
        "email":         true, // PII — redact in production
    }

    if sensitiveKeys[strings.ToLower(a.Key)] {
        a.Value = slog.StringValue("[REDACTED]")
    }
    return a
}
```

### 3.2 Log Correlation with trace_id and span_id

```go
package logging

import (
    "context"
    "log/slog"

    "go.opentelemetry.io/otel/trace"
)

// TracingHandler wraps any slog.Handler to automatically inject
// trace_id and span_id from the context into every log record.
type TracingHandler struct {
    inner slog.Handler
}

func NewTracingHandler(inner slog.Handler) *TracingHandler {
    return &TracingHandler{inner: inner}
}

func (h *TracingHandler) Enabled(ctx context.Context, level slog.Level) bool {
    return h.inner.Enabled(ctx, level)
}

func (h *TracingHandler) Handle(ctx context.Context, rec slog.Record) error {
    // Extract trace context from the span in ctx
    span := trace.SpanFromContext(ctx)
    if span.SpanContext().IsValid() {
        rec.AddAttrs(
            slog.String("trace_id", span.SpanContext().TraceID().String()),
            slog.String("span_id", span.SpanContext().SpanID().String()),
        )
    }
    return h.inner.Handle(ctx, rec)
}

func (h *TracingHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
    return &TracingHandler{inner: h.inner.WithAttrs(attrs)}
}

func (h *TracingHandler) WithGroup(name string) slog.Handler {
    return &TracingHandler{inner: h.inner.WithGroup(name)}
}

// Usage in NewLogger — wrap the JSON handler:
//   handler = NewTracingHandler(slog.NewJSONHandler(os.Stdout, opts))
```

### 3.3 Request-Scoped Logger (via Context)

```go
package middleware

import (
    "context"
    "log/slog"
    "net/http"
)

// LoggerMiddleware creates a request-scoped logger with correlation fields
// and stores it in the context for all downstream handlers/services.
func LoggerMiddleware(baseLogger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := r.Context()

            reqLogger := baseLogger.With(
                "request_id", RequestIDFromContext(ctx),
                "tenant_id", TenantFromContext(ctx),
                "user_id", UserIDFromContext(ctx),
                "http.method", r.Method,
                "http.path", r.URL.Path,
                "http.remote_addr", r.RemoteAddr,
            )

            ctx = context.WithValue(ctx, ctxKeyLogger, reqLogger)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// LoggerFromContext retrieves the request-scoped logger.
// Falls back to the default logger if none was set.
func LoggerFromContext(ctx context.Context) *slog.Logger {
    if l, ok := ctx.Value(ctxKeyLogger).(*slog.Logger); ok {
        return l
    }
    return slog.Default()
}

// Usage in service/repository code:
func (s *Service) Process(ctx context.Context, id string) error {
    logger := LoggerFromContext(ctx)
    logger.InfoContext(ctx, "processing entity",
        "entity_id", id,
    )
    // ...
}
```

### 3.4 Log Level Strategy

| Environment | Default Level | Override Mechanism |
|-------------|---------------|-------------------|
| `local` | DEBUG | None needed |
| `development` | DEBUG | `LOG_LEVEL` env var |
| `staging` | INFO | `LOG_LEVEL` env var |
| `production` | INFO | `LOG_LEVEL` env var, per-service |

Dynamic log level (change at runtime without restart):

```go
// Use slog.LevelVar for runtime level changes.
var programLevel = new(slog.LevelVar) // default INFO

func NewLogger(env string) *slog.Logger {
    if env == "development" {
        programLevel.Set(slog.LevelDebug)
    }

    handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: programLevel,
    })

    return slog.New(NewTracingHandler(handler))
}

// Expose an admin endpoint to change log level at runtime:
func handleSetLogLevel(w http.ResponseWriter, r *http.Request) {
    level := r.URL.Query().Get("level")
    switch strings.ToUpper(level) {
    case "DEBUG":
        programLevel.Set(slog.LevelDebug)
    case "INFO":
        programLevel.Set(slog.LevelInfo)
    case "WARN":
        programLevel.Set(slog.LevelWarn)
    case "ERROR":
        programLevel.Set(slog.LevelError)
    default:
        http.Error(w, "invalid level: use DEBUG, INFO, WARN, ERROR", http.StatusBadRequest)
        return
    }
    w.WriteHeader(http.StatusOK)
    fmt.Fprintf(w, "log level set to %s", level)
}
```

### 3.5 Sensitive Data Masking

The `maskSensitiveAttr` function in 3.1 handles field-level masking. Additional patterns:

```go
// MaskEmail partially masks email addresses: j***@example.com
func MaskEmail(email string) string {
    parts := strings.SplitN(email, "@", 2)
    if len(parts) != 2 || len(parts[0]) == 0 {
        return "[REDACTED]"
    }
    return string(parts[0][0]) + "***@" + parts[1]
}

// MaskCard masks all but last 4 digits: ****1234
func MaskCard(card string) string {
    if len(card) < 4 {
        return "[REDACTED]"
    }
    return "****" + card[len(card)-4:]
}

// Usage — NEVER log raw PII:
logger.InfoContext(ctx, "payment processed",
    "email", MaskEmail(user.Email),      // j***@example.com
    "card", MaskCard(payment.CardNumber), // ****1234
    "amount", payment.Amount,
)
```

---

## 4. Correlation — Tying It All Together

### 4.1 Required Fields on EVERY Signal

| Field | Log | Metric | Trace | Source |
|-------|-----|--------|-------|--------|
| `trace_id` | Yes | No (linked via exemplars) | Automatic | OTel SDK |
| `span_id` | Yes | No | Automatic | OTel SDK |
| `request_id` | Yes | Yes (attribute) | Yes (attribute) | RequestID middleware |
| `tenant_id` | Yes | Yes (attribute) | Yes (attribute) | Tenant middleware |

### 4.2 Correlation Context Middleware Stack

Middleware MUST be applied in this order:

```go
func buildMiddlewareChain(logger *slog.Logger, handler http.Handler) http.Handler {
    // Applied bottom-to-top (last middleware runs first):
    h := handler

    // 5. Business logic handler
    // 4. Metrics recording
    h = MetricsMiddleware(h)
    // 3. Request-scoped logger (needs tenant_id, request_id, user_id from ctx)
    h = LoggerMiddleware(logger)(h)
    // 2. Auth — extracts and validates user identity
    h = AuthMiddleware(h)
    // 1b. Tenant ID extraction
    h = TenantMiddleware(h)
    // 1a. Request ID — generate or extract from header
    h = RequestIDMiddleware(h)
    // 0. OTel HTTP handler — creates root trace span, extracts W3C traceparent
    //    (applied in NewServer via otelhttp.NewHandler)

    return h
}
```

### 4.3 W3C TraceContext Propagation to Downstream Services

```go
package httpclient

import (
    "context"
    "net/http"
    "time"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/propagation"
)

// Client wraps http.Client with trace propagation and request_id forwarding.
type Client struct {
    inner *http.Client
}

func NewClient() *Client {
    return &Client{
        inner: &http.Client{
            Transport: otelhttp.NewTransport(http.DefaultTransport),
            Timeout:   30 * time.Second,
        },
    }
}

// Do sends the request, propagating W3C TraceContext + app correlation IDs.
func (c *Client) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
    // OTel transport automatically injects traceparent and tracestate headers.
    // We additionally forward our application-level correlation IDs:
    if reqID := RequestIDFromContext(ctx); reqID != "" {
        req.Header.Set("X-Request-ID", reqID)
    }
    if tenantID := TenantFromContext(ctx); tenantID != "" {
        req.Header.Set("X-Tenant-ID", tenantID)
    }

    return c.inner.Do(req.WithContext(ctx))
}
```

### 4.4 Log-to-Trace Linking

When using Grafana (Loki + Tempo) or similar backends, structured logs with `trace_id` enable "click log line, see trace":

```go
// The TracingHandler (section 3.2) automatically adds trace_id and span_id.
// Example log output:
// {
//   "time": "2024-06-15T10:30:00.123Z",
//   "level": "INFO",
//   "msg": "order created",
//   "service": "order-service",
//   "version": "1.2.3",
//   "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",  <-- click this in Grafana
//   "span_id": "00f067aa0ba902b7",
//   "request_id": "req_abc123",
//   "tenant_id": "tenant_xyz",
//   "order_id": "ord_456"
// }
//
// Grafana Loki query: {service="order-service"} | json | trace_id != ""
// Click trace_id → opens Tempo trace view showing the full request waterfall.
```

For Prometheus metric-to-trace linking via exemplars:

```go
// OTel Prometheus exporter supports exemplars automatically when
// the context carries a valid trace. Exemplars attach trace_id
// to histogram/counter observations, enabling:
//   Prometheus query → see exemplar → click → open trace in Tempo/Jaeger
```

---

## 5. Full Initialization (main.go)

```go
package main

import (
    "context"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer cancel()

    env := getEnv("APP_ENV", "development")
    serviceName := "order-service"
    serviceVersion := "1.0.0"

    // 1. Logger — must be first so other init functions can log
    logger := NewLogger(serviceName, serviceVersion, env)
    slog.SetDefault(logger)

    // 2. Tracer
    shutdownTracer, err := initTracer(ctx, serviceName, serviceVersion)
    if err != nil {
        slog.Error("failed to init tracer", "error", err)
        os.Exit(1)
    }
    defer shutdownTracer(context.Background())

    // 3. Metrics
    res := buildResource(serviceName, serviceVersion, env)
    shutdownMetrics, err := initMetrics(ctx, res)
    if err != nil {
        slog.Error("failed to init metrics", "error", err)
        os.Exit(1)
    }
    defer shutdownMetrics(context.Background())

    // 4. Prometheus /metrics endpoint (separate port)
    metricsSrv := serveMetrics(":9090")
    defer metricsSrv.Shutdown(context.Background())

    // 5. Database (with instrumentation)
    db, err := OpenDB(os.Getenv("DATABASE_URL"))
    if err != nil {
        slog.Error("failed to open database", "error", err)
        os.Exit(1)
    }
    defer db.Close()

    // 6. Redis (with instrumentation)
    rdb := NewRedisClient(os.Getenv("REDIS_URL"))
    defer rdb.Close()

    // 7. Runtime metrics (goroutines, db pool)
    if err := RegisterRuntimeMetrics(db); err != nil {
        slog.Error("failed to register runtime metrics", "error", err)
        os.Exit(1)
    }

    // 8. Build handler chain
    repo := NewPostgresOrderRepo(db)
    svc := NewOrderService(repo)
    handler := NewOrderHandler(svc)

    mux := http.NewServeMux()
    mux.HandleFunc("POST /api/v1/orders", handler.CreateOrder)
    mux.HandleFunc("GET /api/v1/orders/{id}", handler.GetOrder)

    chain := buildMiddlewareChain(logger, mux)
    srv := NewServer(chain) // wraps with otelhttp

    // 9. Start server
    slog.Info("server starting",
        "addr", srv.Addr,
        "env", env,
        "service", serviceName,
        "version", serviceVersion,
    )

    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("server failed", "error", err)
            os.Exit(1)
        }
    }()

    // 10. Graceful shutdown
    <-ctx.Done()
    slog.Info("shutting down gracefully")

    shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer shutdownCancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        slog.Error("server shutdown error", "error", err)
    }

    slog.Info("server stopped")
}

func getEnv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
```

---

## 6. Span Naming Convention

| Layer | Pattern | Example |
|-------|---------|---------|
| HTTP handler | `HTTP {METHOD} {route_pattern}` | `HTTP POST /api/v1/orders` |
| Service method | `{ServiceName}.{MethodName}` | `OrderService.CreateOrder` |
| Repository | `{system}.{table}.{operation}` | `postgres.orders.insert` |
| Cache | `{system}.{operation}` | `redis.get`, `redis.set` |
| External call | `{service}.{endpoint}` | `payment-gateway.charge` |
| Queue publish | `{queue}.publish` | `orders.publish` |
| Queue consume | `{queue}.consume` | `orders.consume` |

---

## 7. Metric Naming Convention

Follow OpenTelemetry semantic conventions:

| Metric | Type | Unit | Attributes |
|--------|------|------|------------|
| `http.server.request.total` | Counter | `{request}` | tenant_id, http.method, http.route, http.status_code |
| `http.server.request.duration` | Histogram | `s` | tenant_id, http.method, http.route |
| `http.server.active_requests` | UpDownCounter | `{request}` | tenant_id, http.route |
| `db.query.duration` | Histogram | `s` | tenant_id, db.operation, db.sql.table |
| `db.pool.open_connections` | Gauge | `{connection}` | - |
| `db.pool.in_use` | Gauge | `{connection}` | - |
| `go.goroutine.count` | Gauge | `{goroutine}` | - |
| `queue.depth` | Gauge | `{item}` | queue_name |
| `business.orders.created` | Counter | `{order}` | tenant_id, payment_method |
| `business.orders.revenue` | Counter | `USD` | tenant_id, currency |

---

## Critical Rules

1. **tenant_id on every signal** — logs, metrics, traces. Zero exceptions.
2. **trace_id + span_id on every log line** — use `TracingHandler` to automate this.
3. **RecordError + SetStatus on every error** — never swallow errors silently in spans.
4. **Middleware order matters** — otelhttp first, then request_id, tenant, auth, logger, metrics.
5. **No high-cardinality metric attributes** — never use user_id, order_id, or raw paths as metric labels. Use route patterns.
6. **JSON logs in production** — text logs only in local development.
7. **Never log sensitive data** — passwords, tokens, API keys, raw PII. Use masking helpers.
8. **Graceful shutdown flushes telemetry** — defer `shutdownTracer` and `shutdownMetrics` to avoid losing final spans/metrics.
9. **Separate metrics port** — serve `/metrics` on a different port (9090) from the application port (8080). Keeps Prometheus scraping out of application routing.
10. **Exemplars link metrics to traces** — the OTel Prometheus exporter handles this automatically when context carries valid trace spans.
