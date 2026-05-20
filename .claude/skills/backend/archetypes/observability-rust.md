---
skill: observability-rust
description: Rust observability archetype — OpenTelemetry traces/metrics via tracing + tracing-opentelemetry, structured logging, Axum middleware, sqlx spans, Prometheus exporter, graceful shutdown
version: "1.0"
tags:
  - rust
  - observability
  - tracing
  - opentelemetry
  - metrics
  - logging
  - axum
  - archetype
  - backend
---

# Observability Archetype (Rust)

> **CANONICAL REFERENCE**: This file is the single source of truth for Rust backend observability patterns. All other Rust skill packs that mention logging, tracing, or metrics should defer to this file. For language-agnostic patterns, see `core/observability-patterns.md`.

Complete OpenTelemetry integration for Rust services using Axum, the `tracing` ecosystem, and the `opentelemetry-rust` SDK. Every generated service MUST follow these patterns.

---

## Cargo.toml Dependencies

```toml
[dependencies]
# Tracing core
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json", "fmt"] }

# OpenTelemetry integration
tracing-opentelemetry = "0.28"
opentelemetry = { version = "0.27", features = ["metrics"] }
opentelemetry_sdk = { version = "0.27", features = ["rt-tokio", "metrics"] }
opentelemetry-otlp = { version = "0.27", features = ["tonic", "metrics"] }
opentelemetry-semantic-conventions = "0.27"

# Prometheus exporter
opentelemetry-prometheus = "0.27"
prometheus = "0.13"

# Axum + tower
axum = "0.8"
tower-http = { version = "0.6", features = ["trace", "request-id", "propagate-header"] }
tower = "0.5"

# Utilities
uuid = { version = "1", features = ["v4"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full", "signal"] }
```

---

## Full Telemetry Setup (main.rs)

```rust
use opentelemetry::trace::TracerProvider as _;
use opentelemetry::{global, KeyValue};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::{
    metrics::{SdkMeterProvider, PeriodicReader},
    propagation::TraceContextPropagator,
    runtime,
    trace::{BatchSpanProcessor, TracerProvider},
    Resource,
};
use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// Initialize all telemetry: tracing subscriber with OTel layers, metrics, and propagation.
/// Call this once at application startup before any tracing macros are used.
pub fn init_telemetry(service_name: &str, service_version: &str) -> anyhow::Result<SdkMeterProvider> {
    // --- Resource: identifies this service in all telemetry ---
    let resource = Resource::new(vec![
        KeyValue::new("service.name", service_name.to_owned()),
        KeyValue::new("service.version", service_version.to_owned()),
        KeyValue::new(
            "deployment.environment",
            std::env::var("APP_ENV").unwrap_or_else(|_| "development".into()),
        ),
    ]);

    // --- Trace context propagation (W3C Trace Context) ---
    global::set_text_map_propagator(TraceContextPropagator::new());

    // --- OTLP exporter for traces ---
    let otlp_endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://localhost:4317".into());

    let trace_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(&otlp_endpoint)
        .build()?;

    let tracer_provider = TracerProvider::builder()
        .with_resource(resource.clone())
        .with_span_processor(BatchSpanProcessor::builder(trace_exporter, runtime::Tokio).build())
        .build();

    let tracer = tracer_provider.tracer(service_name.to_owned());
    global::set_tracer_provider(tracer_provider);

    // --- OTel tracing layer (bridges tracing spans to OTel spans) ---
    let otel_trace_layer = tracing_opentelemetry::layer().with_tracer(tracer);

    // --- OTLP exporter for metrics ---
    let metrics_exporter = opentelemetry_otlp::MetricExporter::builder()
        .with_tonic()
        .with_endpoint(&otlp_endpoint)
        .build()?;

    let meter_provider = SdkMeterProvider::builder()
        .with_resource(resource)
        .with_reader(PeriodicReader::builder(metrics_exporter, runtime::Tokio).build())
        .build();

    global::set_meter_provider(meter_provider.clone());

    // --- Logging format layer: JSON in production, pretty in development ---
    let is_prod = std::env::var("APP_ENV").unwrap_or_default() == "production";

    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,tower_http=debug,sqlx=warn"));

    if is_prod {
        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt::layer().json().flatten_event(true))
            .with(otel_trace_layer)
            .init();
    } else {
        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt::layer().pretty())
            .with(otel_trace_layer)
            .init();
    }

    Ok(meter_provider)
}

/// Graceful shutdown: flush all pending spans and metrics before exit.
pub async fn shutdown_telemetry(meter_provider: SdkMeterProvider) {
    tracing::info!("shutting down telemetry — flushing spans and metrics");

    // Flush and shutdown the tracer provider
    if let Err(e) = global::tracer_provider().shutdown() {
        tracing::error!(error = %e, "failed to shutdown tracer provider");
    }

    // Flush and shutdown the meter provider
    if let Err(e) = meter_provider.shutdown() {
        tracing::error!(error = %e, "failed to shutdown meter provider");
    }
}
```

### Application Entrypoint

```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let meter_provider = init_telemetry("order-service", env!("CARGO_PKG_VERSION"))?;

    let app = build_router();

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    tracing::info!("listening on {}", listener.local_addr()?);

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    shutdown_telemetry(meter_provider).await;
    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = tokio::signal::ctrl_c();
    let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .expect("failed to install SIGTERM handler");

    tokio::select! {
        _ = ctrl_c => tracing::info!("received SIGINT"),
        _ = sigterm.recv() => tracing::info!("received SIGTERM"),
    }
}
```

---

## Distributed Tracing

### #[tracing::instrument] on Handler / Service / Repository

The `tracing::instrument` attribute macro creates a span for every function invocation. Use it at every layer boundary.

```rust
use axum::extract::{Json, Path, State};
use sqlx::PgPool;
use uuid::Uuid;

// --- Handler layer ---
#[tracing::instrument(
    name = "HTTP POST /api/v1/orders",
    skip(state, auth_user, body),
    fields(
        tenant_id = %auth_user.tenant_id,
        user_id = %auth_user.user_id,
        request_id = %request_id,
    )
)]
pub async fn create_order(
    State(state): State<Arc<AppState>>,
    auth_user: AuthUser,
    request_id: RequestId,
    Json(body): Json<CreateOrderRequest>,
) -> Result<impl IntoResponse, AppError> {
    let order = state.order_service.create(
        &auth_user.tenant_id,
        &auth_user.user_id,
        body,
    ).await?;

    Ok((StatusCode::CREATED, Json(order)))
}

// --- Service layer ---
#[tracing::instrument(
    name = "OrderService.create",
    skip(self, body),
    fields(order_id = tracing::field::Empty)
)]
pub async fn create(
    &self,
    tenant_id: &str,
    user_id: &str,
    body: CreateOrderRequest,
) -> Result<Order, AppError> {
    body.validate()?;

    let order = Order::new(tenant_id, user_id, body.items);
    // Record the order_id on the span after creation
    tracing::Span::current().record("order_id", &tracing::field::display(&order.id));

    self.repo.insert(&order).await?;

    tracing::info!(
        order_id = %order.id,
        item_count = order.items.len(),
        total = %order.total,
        "order created"
    );

    Ok(order)
}

// --- Repository layer ---
#[tracing::instrument(
    name = "postgres.orders.insert",
    skip(self, order),
    fields(
        db.system = "postgresql",
        db.operation = "INSERT",
        db.sql.table = "orders",
    )
)]
pub async fn insert(&self, order: &Order) -> Result<(), AppError> {
    sqlx::query!(
        r#"
        INSERT INTO orders (id, tenant_id, user_id, total, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        "#,
        order.id,
        order.tenant_id,
        order.user_id,
        order.total,
        order.status.as_str(),
        order.created_at,
    )
    .execute(&self.pool)
    .await
    .map_err(|e| {
        tracing::error!(error = %e, "failed to insert order");
        AppError::Internal(anyhow::anyhow!("database error"))
    })?;

    Ok(())
}
```

### Span Naming Convention

| Layer | Format | Example |
|-------|--------|---------|
| HTTP handler | `HTTP {METHOD} {path}` | `HTTP POST /api/v1/orders` |
| Service method | `{ServiceName}.{method}` | `OrderService.create` |
| Repository | `{system}.{table}.{operation}` | `postgres.orders.insert` |
| External call | `{service}.{endpoint}` | `payment-gateway.charge` |
| Background job | `job.{name}` | `job.send_email_notification` |

### tower-http TraceLayer for Automatic HTTP Spans

```rust
use tower_http::trace::{DefaultMakeSpan, DefaultOnResponse, TraceLayer};
use tracing::Level;

pub fn build_router() -> Router {
    let trace_layer = TraceLayer::new_for_http()
        .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
        .on_response(DefaultOnResponse::new().level(Level::INFO));

    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler))
        .layer(trace_layer)
        .layer(RequestIdLayer::new())
        .layer(TenantLayer::new())
}
```

### sqlx Built-in Tracing Support

sqlx emits tracing spans automatically when `sqlx` is compiled with tracing support (enabled by default). Each query creates a span named `sqlx::query` with fields for the SQL statement and execution time.

Control the log level via `RUST_LOG`:

```bash
# Show sqlx queries at debug level, suppress at info
RUST_LOG=info,sqlx=debug cargo run

# Suppress all sqlx logs in production
RUST_LOG=info,sqlx=warn cargo run
```

To add custom context around sqlx queries, wrap them in an instrumented function (as shown in the repository layer above).

### Manual Span Creation

For complex operations that span multiple steps within a single function:

```rust
use tracing::{info_span, Instrument};

pub async fn process_batch(
    &self,
    tenant_id: &str,
    items: Vec<BatchItem>,
) -> Result<BatchResult, AppError> {
    let batch_span = info_span!(
        "OrderService.process_batch",
        tenant_id = %tenant_id,
        batch_size = items.len(),
        processed = tracing::field::Empty,
        failed = tracing::field::Empty,
    );

    async {
        let mut processed = 0u64;
        let mut failed = 0u64;

        for item in &items {
            let item_span = info_span!(
                "process_batch_item",
                item_id = %item.id,
            );

            let result = async {
                self.validate_item(item).await?;
                self.persist_item(item).await
            }
            .instrument(item_span)
            .await;

            match result {
                Ok(_) => processed += 1,
                Err(e) => {
                    tracing::warn!(item_id = %item.id, error = %e, "batch item failed");
                    failed += 1;
                }
            }
        }

        // Record final counts on the batch span
        tracing::Span::current().record("processed", processed);
        tracing::Span::current().record("failed", failed);

        Ok(BatchResult { processed, failed })
    }
    .instrument(batch_span)
    .await
}
```

### Error Recording in Spans

```rust
use tracing::{error, warn};

// Errors that should wake someone up (5xx-class)
#[tracing::instrument(skip(self))]
pub async fn charge_payment(&self, order: &Order) -> Result<PaymentReceipt, AppError> {
    let result = self.payment_client.charge(order).await;

    match &result {
        Ok(receipt) => {
            tracing::info!(
                receipt_id = %receipt.id,
                amount = %receipt.amount,
                "payment charged successfully"
            );
        }
        Err(e) => {
            // tracing::error! automatically records on the current span
            tracing::error!(
                order_id = %order.id,
                error = %e,
                "payment charge failed — upstream error"
            );
        }
    }

    result
}

// Handled degradation (warn, not error)
pub async fn get_cached_or_fetch(&self, key: &str) -> Result<Data, AppError> {
    match self.cache.get(key).await {
        Ok(Some(data)) => {
            tracing::debug!(key = %key, "cache hit");
            Ok(data)
        }
        Ok(None) => {
            tracing::debug!(key = %key, "cache miss — fetching from database");
            self.fetch_from_db(key).await
        }
        Err(e) => {
            tracing::warn!(key = %key, error = %e, "cache read failed — falling back to database");
            self.fetch_from_db(key).await
        }
    }
}
```

### Context Propagation

In the `tracing` ecosystem, spans propagate automatically through `.await` points when using `#[tracing::instrument]` or `.instrument(span)`. The `tracing-opentelemetry` layer bridges this to W3C Trace Context for cross-service propagation.

For outgoing HTTP calls, inject the trace context into headers:

```rust
use opentelemetry::global;
use opentelemetry::propagation::Injector;
use reqwest::header::HeaderMap;

struct HeaderInjector<'a>(&'a mut HeaderMap);

impl<'a> Injector for HeaderInjector<'a> {
    fn set(&mut self, key: &str, value: String) {
        if let Ok(header_name) = reqwest::header::HeaderName::from_bytes(key.as_bytes()) {
            if let Ok(header_value) = reqwest::header::HeaderValue::from_str(&value) {
                self.0.insert(header_name, header_value);
            }
        }
    }
}

#[tracing::instrument(
    name = "http_client.call",
    skip(self, body),
    fields(http.method = %method, http.url = %url)
)]
pub async fn call_service(
    &self,
    method: &str,
    url: &str,
    body: &impl serde::Serialize,
) -> Result<reqwest::Response, AppError> {
    let mut headers = HeaderMap::new();

    // Inject W3C Trace Context headers (traceparent, tracestate)
    let cx = tracing::Span::current().context();
    global::get_text_map_propagator(|propagator| {
        propagator.inject_context(&cx, &mut HeaderInjector(&mut headers));
    });

    let resp = self
        .client
        .request(method.parse().unwrap(), url)
        .headers(headers)
        .json(body)
        .send()
        .await
        .map_err(|e| {
            tracing::error!(error = %e, "outgoing HTTP request failed");
            AppError::upstream("downstream-service", e)
        })?;

    tracing::info!(status = resp.status().as_u16(), "downstream response received");
    Ok(resp)
}
```

For incoming requests, extract the context in middleware (tower-http's `TraceLayer` does this automatically when `TraceContextPropagator` is set as the global propagator).

---

## Metrics

### OpenTelemetry Metrics via the Metrics API

```rust
use opentelemetry::{global, KeyValue};
use opentelemetry::metrics::{Counter, Histogram, UpDownCounter, Meter};
use std::sync::LazyLock;

static METER: LazyLock<Meter> = LazyLock::new(|| global::meter("order-service"));

pub struct AppMetrics {
    pub request_count: Counter<u64>,
    pub request_duration: Histogram<f64>,
    pub active_requests: UpDownCounter<i64>,
    pub db_query_duration: Histogram<f64>,
    pub order_total: Counter<u64>,
    pub order_value: Histogram<f64>,
    pub cache_hits: Counter<u64>,
    pub cache_misses: Counter<u64>,
    pub active_db_connections: UpDownCounter<i64>,
}

impl AppMetrics {
    pub fn new() -> Self {
        let meter = &*METER;

        Self {
            request_count: meter
                .u64_counter("http.server.request.total")
                .with_description("Total HTTP requests")
                .with_unit("request")
                .build(),

            request_duration: meter
                .f64_histogram("http.server.request.duration")
                .with_description("HTTP request duration in seconds")
                .with_unit("s")
                .build(),

            active_requests: meter
                .i64_up_down_counter("http.server.active_requests")
                .with_description("Currently active requests")
                .with_unit("request")
                .build(),

            db_query_duration: meter
                .f64_histogram("db.query.duration")
                .with_description("Database query duration in seconds")
                .with_unit("s")
                .build(),

            order_total: meter
                .u64_counter("business.order.total")
                .with_description("Total orders processed")
                .with_unit("order")
                .build(),

            order_value: meter
                .f64_histogram("business.order.value")
                .with_description("Order value distribution")
                .with_unit("USD")
                .build(),

            cache_hits: meter
                .u64_counter("cache.hit.total")
                .with_description("Cache hit count")
                .with_unit("hit")
                .build(),

            cache_misses: meter
                .u64_counter("cache.miss.total")
                .with_description("Cache miss count")
                .with_unit("miss")
                .build(),

            active_db_connections: meter
                .i64_up_down_counter("db.pool.active_connections")
                .with_description("Active database connections")
                .with_unit("connection")
                .build(),
        }
    }
}
```

### Axum Metrics Middleware

```rust
use axum::{
    body::Body,
    extract::State,
    http::{Request, Response},
    middleware::Next,
};
use std::sync::Arc;
use std::time::Instant;

pub async fn metrics_middleware(
    State(state): State<Arc<AppState>>,
    request: Request<Body>,
    next: Next,
) -> Response<Body> {
    let start = Instant::now();
    let method = request.method().to_string();
    let path = request.uri().path().to_string();

    let tenant_id = request
        .extensions()
        .get::<TenantId>()
        .map(|t| t.0.clone())
        .unwrap_or_else(|| "unknown".into());

    let base_attrs = [
        KeyValue::new("tenant_id", tenant_id.clone()),
        KeyValue::new("http.method", method.clone()),
        KeyValue::new("http.route", normalize_path(&path)),
    ];

    state.metrics.active_requests.add(1, &base_attrs);

    let response = next.run(request).await;

    let duration = start.elapsed().as_secs_f64();
    let status = response.status().as_u16();

    let full_attrs = [
        KeyValue::new("tenant_id", tenant_id),
        KeyValue::new("http.method", method),
        KeyValue::new("http.route", normalize_path(&path)),
        KeyValue::new("http.status_code", i64::from(status)),
    ];

    state.metrics.request_count.add(1, &full_attrs);
    state.metrics.request_duration.record(duration, &full_attrs);
    state.metrics.active_requests.add(-1, &base_attrs);

    response
}

/// Normalize paths to avoid high-cardinality metrics.
/// /api/v1/orders/abc123 → /api/v1/orders/{id}
fn normalize_path(path: &str) -> String {
    let segments: Vec<&str> = path.split('/').collect();
    segments
        .iter()
        .map(|s| {
            if uuid::Uuid::parse_str(s).is_ok() || s.parse::<i64>().is_ok() {
                "{id}"
            } else {
                s
            }
        })
        .collect::<Vec<_>>()
        .join("/")
}
```

Wire it into the router:

```rust
use axum::middleware;

pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler))
        .layer(middleware::from_fn_with_state(state.clone(), metrics_middleware))
        .with_state(state)
}
```

### Prometheus Exporter Endpoint

```rust
use opentelemetry_prometheus::exporter;
use prometheus::TextEncoder;

pub fn setup_prometheus_exporter() -> prometheus::Registry {
    let registry = prometheus::Registry::new();

    let prometheus_exporter = exporter()
        .with_registry(registry.clone())
        .build()
        .expect("failed to build prometheus exporter");

    // Register as a global meter provider (alternative to OTLP for metrics)
    // Use this when you want /metrics endpoint instead of or alongside OTLP push
    global::set_meter_provider(prometheus_exporter.meter_provider().clone());

    registry
}

/// Axum handler for GET /metrics
pub async fn metrics_handler(
    State(state): State<Arc<AppState>>,
) -> Result<String, AppError> {
    let encoder = TextEncoder::new();
    let metric_families = state.prometheus_registry.gather();
    encoder
        .encode_to_string(&metric_families)
        .map_err(|e| AppError::Internal(anyhow::anyhow!("metrics encoding error: {e}")))
}
```

### Business Metrics

```rust
#[tracing::instrument(skip(self, body), fields(order_id = tracing::field::Empty))]
pub async fn create_order(
    &self,
    tenant_id: &str,
    user_id: &str,
    body: CreateOrderRequest,
) -> Result<Order, AppError> {
    let order = Order::new(tenant_id, user_id, body.items);
    tracing::Span::current().record("order_id", tracing::field::display(&order.id));

    self.repo.insert(&order).await?;

    // Record business metrics
    self.metrics.order_total.add(1, &[
        KeyValue::new("tenant_id", tenant_id.to_owned()),
        KeyValue::new("payment_method", order.payment_method.to_string()),
    ]);
    self.metrics.order_value.record(order.total_as_f64(), &[
        KeyValue::new("tenant_id", tenant_id.to_owned()),
    ]);

    Ok(order)
}
```

### Key Metrics Table

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http.server.request.total` | Counter | tenant_id, method, route, status_code | Request volume and error rates |
| `http.server.request.duration` | Histogram | tenant_id, method, route | Latency distribution (p50/p95/p99) |
| `http.server.active_requests` | UpDownCounter | tenant_id, route | Concurrency / saturation |
| `db.query.duration` | Histogram | tenant_id, operation, table | Database performance |
| `db.pool.active_connections` | UpDownCounter | pool_name | Connection pool saturation |
| `cache.hit.total` | Counter | tenant_id, cache_name | Cache effectiveness |
| `cache.miss.total` | Counter | tenant_id, cache_name | Cache miss rate |
| `business.<event>.total` | Counter | tenant_id, type | Business KPIs |

---

## Structured Logging

### JSON Format (Production) and Pretty Format (Development)

The format is configured in `init_telemetry()` above. The key difference:

```rust
// Production: JSON — machine-parseable, one JSON object per line
// {"timestamp":"2024-01-15T10:30:00Z","level":"INFO","target":"order_service::service",
//  "message":"order created","tenant_id":"tenant_abc","order_id":"ord_123",
//  "trace_id":"abc123","span_id":"def456"}

// Development: pretty — colorized, multi-line, human-readable
// 2024-01-15T10:30:00Z  INFO order_service::service: order created
//   tenant_id=tenant_abc order_id=ord_123
```

### Structured Fields on Spans Propagate to All Child Log Events

This is the killer feature of `tracing` vs traditional logging. When you put fields on a span, every `tracing::info!()` emitted inside that span automatically includes those fields.

```rust
#[tracing::instrument(fields(tenant_id = %tenant_id, user_id = %user_id))]
pub async fn process_order(&self, tenant_id: &str, user_id: &str, order: Order) -> Result<(), AppError> {
    // This log line automatically includes tenant_id and user_id from the span
    tracing::info!(order_id = %order.id, "starting order processing");

    self.validate(&order).await?;

    // This too — no need to pass tenant_id again
    tracing::info!(order_id = %order.id, status = "validated", "order validation passed");

    self.persist(&order).await?;

    // And this
    tracing::info!(order_id = %order.id, status = "persisted", "order saved to database");

    Ok(())
}
```

### tracing Macros with Structured Fields

```rust
// INFO — business events
tracing::info!(
    order_id = %order.id,
    item_count = order.items.len(),
    total = %order.total,
    "order created"
);

// WARN — handled degradation
tracing::warn!(
    circuit = "payment-service",
    failures = cb.failure_count(),
    reset_in_secs = cb.reset_timeout().as_secs(),
    "circuit breaker opened"
);

// ERROR — actionable, needs investigation
tracing::error!(
    error = %err,
    order_id = %order.id,
    "payment charge failed"
);

// DEBUG — troubleshooting detail (off in production by default)
tracing::debug!(
    query = "SELECT * FROM orders WHERE tenant_id = $1",
    params = ?[tenant_id],
    "executing database query"
);
```

### Env Filter (RUST_LOG)

```bash
# Default: info for app, debug for tower_http, warn for sqlx
RUST_LOG=info,tower_http=debug,sqlx=warn

# Verbose: debug for the app
RUST_LOG=debug,sqlx=debug

# Production: info only, suppress framework noise
RUST_LOG=info,tower_http=info,hyper=warn,sqlx=warn

# Target a specific module
RUST_LOG=info,order_service::service=debug
```

### Sensitive Data Protection

```rust
// BAD: Logs the entire struct including potentially sensitive fields
#[tracing::instrument]
pub async fn create_user(&self, req: CreateUserRequest) -> Result<User, AppError> { ... }

// GOOD: skip_all + explicitly list safe fields
#[tracing::instrument(
    skip_all,
    fields(
        tenant_id = %tenant_id,
        email_domain = %extract_domain(&req.email),
    )
)]
pub async fn create_user(
    &self,
    tenant_id: &str,
    req: CreateUserRequest,
) -> Result<User, AppError> { ... }

// GOOD: implement a safe Display for sensitive types
pub struct SensitiveEmail(String);

impl std::fmt::Display for SensitiveEmail {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if let Some(at) = self.0.find('@') {
            write!(f, "***@{}", &self.0[at + 1..])
        } else {
            write!(f, "***")
        }
    }
}
```

### Log Correlation: trace_id and span_id

When the `tracing-opentelemetry` layer is active, every log event automatically includes `trace_id` and `span_id` fields. This allows you to:

1. Click a log line in your log aggregator
2. Jump directly to the trace in Jaeger/Tempo
3. See every log line for a given trace across all services

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "target": "order_service::service",
  "message": "order created",
  "tenant_id": "tenant_abc",
  "order_id": "ord_123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

---

## Request ID Middleware

```rust
use axum::{
    body::Body,
    http::{HeaderValue, Request, Response},
    middleware::Next,
};
use uuid::Uuid;

/// Extract or generate a request ID. Propagate it in the response header and on the current span.
pub async fn request_id_middleware(
    mut request: Request<Body>,
    next: Next,
) -> Response<Body> {
    let request_id = request
        .headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(String::from)
        .unwrap_or_else(|| format!("req_{}", Uuid::new_v4()));

    // Record on the current tracing span
    tracing::Span::current().record("request_id", &request_id.as_str());

    // Store in extensions for downstream extractors
    request.extensions_mut().insert(RequestId(request_id.clone()));

    let mut response = next.run(request).await;
    response.headers_mut().insert(
        "x-request-id",
        HeaderValue::from_str(&request_id).unwrap_or_else(|_| HeaderValue::from_static("unknown")),
    );

    response
}

#[derive(Clone, Debug)]
pub struct RequestId(pub String);
```

---

## Tenant-Aware Observability

Every log, metric, and trace MUST include `tenant_id`. This is enforced at the middleware layer.

```rust
pub async fn tenant_middleware(
    mut request: Request<Body>,
    next: Next,
) -> Result<Response<Body>, AppError> {
    let tenant_id = request
        .headers()
        .get("x-tenant-id")
        .and_then(|v| v.to_str().ok())
        .map(String::from)
        .ok_or_else(|| AppError::BadRequest("missing X-Tenant-ID header".into()))?;

    // Record on the current tracing span — propagates to all child spans and logs
    tracing::Span::current().record("tenant_id", &tenant_id.as_str());

    request.extensions_mut().insert(TenantId(tenant_id));

    Ok(next.run(request).await)
}

#[derive(Clone, Debug)]
pub struct TenantId(pub String);
```

---

## Docker Compose with Jaeger

```yaml
services:
  app:
    build: .
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
      - OTEL_SERVICE_NAME=order-service
      - APP_ENV=development
      - RUST_LOG=info,tower_http=debug,sqlx=warn
    ports:
      - "8080:8080"
    depends_on:
      - jaeger
      - postgres

  jaeger:
    image: jaegertracing/all-in-one:1.54
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC receiver
      - "4318:4318"    # OTLP HTTP receiver

  prometheus:
    image: prom/prometheus:v2.49.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
```

### prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "order-service"
    static_configs:
      - targets: ["app:8080"]
    metrics_path: /metrics
```

---

## Complete Middleware Stack (Recommended Order)

```rust
pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler))
        // --- Middleware applied bottom-up (last added = first executed) ---
        // 4. Metrics: records request count, duration, active requests
        .layer(middleware::from_fn_with_state(state.clone(), metrics_middleware))
        // 3. Tenant extraction: reads X-Tenant-ID, records on span
        .layer(middleware::from_fn(tenant_middleware))
        // 2. Request ID: generates or extracts X-Request-ID
        .layer(middleware::from_fn(request_id_middleware))
        // 1. HTTP trace: creates root span for each request
        .layer(
            TraceLayer::new_for_http()
                .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
                .on_response(DefaultOnResponse::new().level(Level::INFO)),
        )
        .with_state(state)
}
```

---

## Required Fields on Every Log Line

| Field | Source | Purpose |
|-------|--------|---------|
| `timestamp` | tracing-subscriber auto-generates | When it happened |
| `level` | tracing macro | Severity |
| `target` | Module path (automatic) | Which module |
| `message` | Developer | What happened |
| `tenant_id` | Span field from middleware | Whose request |
| `request_id` | Span field from middleware | Correlate within a request |
| `trace_id` | tracing-opentelemetry layer | Correlate across services |
| `span_id` | tracing-opentelemetry layer | Specific span reference |

---

## Critical Rules

- `tenant_id` on every log, metric, and trace -- zero exceptions
- Use `#[tracing::instrument]` at every layer boundary (handler, service, repository)
- Use `skip_all` and explicitly list safe fields to avoid leaking sensitive data
- JSON logging in production, pretty logging in development
- `RUST_LOG` env filter controls verbosity -- never hardcode log levels
- Every span records errors with `tracing::error!()` -- do not swallow errors silently
- Flush telemetry on graceful shutdown -- pending spans and metrics must be exported
- Path normalization in metrics middleware -- avoid high-cardinality label explosion
- Business metrics alongside technical metrics -- track domain events, not just HTTP stats
- Prometheus `/metrics` endpoint for pull-based monitoring alongside OTLP push
