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

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, opentelemetry/_sdk/-otlp/-prometheus 0.33.0, tracing-opentelemetry 0.34.0, prometheus 0.14.0, axum 0.8.9. Compiled, not run (no collector).

> **CANONICAL REFERENCE**: This file is the single source of truth for Rust backend observability patterns. All other Rust skill packs that mention logging, tracing, or metrics should defer to this file. For language-agnostic patterns, see `core/observability-patterns.md`.

Complete OpenTelemetry integration for Rust services using Axum, the `tracing` ecosystem, and the `opentelemetry-rust` SDK. Every generated service MUST follow these patterns.

---

## Cargo.toml Dependencies

```toml
[dependencies]
# Tracing core
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json", "fmt"] }

# OpenTelemetry integration — the opentelemetry* crates move together; tracing-opentelemetry
# 0.34 pairs with opentelemetry 0.33
tracing-opentelemetry = "0.34"
opentelemetry = { version = "0.33", features = ["metrics"] }
opentelemetry_sdk = { version = "0.33", features = ["rt-tokio", "metrics"] }
opentelemetry-otlp = { version = "0.33", features = ["tonic", "metrics"] }
opentelemetry-semantic-conventions = "0.33"

# Prometheus exporter
opentelemetry-prometheus = "0.33"
prometheus = "0.14"

# Axum + tower
axum = "0.8"
tower-http = { version = "0.7", features = ["trace", "request-id", "propagate-header"] }
tower = "0.5"

# Utilities
anyhow = "1"                                          # init_telemetry's error type
reqwest = { version = "0.13", features = ["json"] }  # outgoing calls (trace-context propagation)
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
    metrics::SdkMeterProvider,
    propagation::TraceContextPropagator,
    trace::SdkTracerProvider,
    Resource,
};
use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// The providers init_telemetry installs. Keep them: shutdown_telemetry flushes and stops them
/// (the global provider has no shutdown since opentelemetry 0.28).
pub struct Telemetry {
    tracer_provider: SdkTracerProvider,
    meter_provider: SdkMeterProvider,
}

/// Initialize all telemetry: tracing subscriber with OTel layers, metrics, and propagation.
/// Call this once at application startup (inside the Tokio runtime: the OTLP exporters use tonic)
/// before any tracing macros are used.
pub fn init_telemetry(service_name: &str, service_version: &str) -> anyhow::Result<Telemetry> {
    // --- Resource: identifies this service in all telemetry ---
    let resource = Resource::builder()
        .with_service_name(service_name.to_owned())
        .with_attributes([
            KeyValue::new("service.version", service_version.to_owned()),
            KeyValue::new(
                "deployment.environment",
                std::env::var("APP_ENV").unwrap_or_else(|_| "development".into()),
            ),
        ])
        .build();

    // --- Trace context propagation (W3C Trace Context) ---
    global::set_text_map_propagator(TraceContextPropagator::new());

    // --- OTLP exporter for traces ---
    let otlp_endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://localhost:4317".into());

    let trace_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .with_endpoint(&otlp_endpoint)
        .build()?;

    let tracer_provider = SdkTracerProvider::builder()
        .with_resource(resource.clone())
        .with_batch_exporter(trace_exporter)
        .build();

    let tracer = tracer_provider.tracer(service_name.to_owned());
    global::set_tracer_provider(tracer_provider.clone());

    // --- OTel tracing layer (bridges tracing spans to OTel spans) ---
    let otel_trace_layer = tracing_opentelemetry::layer().with_tracer(tracer);

    // --- OTLP exporter for metrics ---
    let metrics_exporter = opentelemetry_otlp::MetricExporter::builder()
        .with_tonic()
        .with_endpoint(&otlp_endpoint)
        .build()?;

    let meter_provider = SdkMeterProvider::builder()
        .with_resource(resource)
        .with_periodic_exporter(metrics_exporter)
        .build();

    global::set_meter_provider(meter_provider.clone());

    // --- Logging format layer: JSON in production, pretty in development ---
    let is_prod = std::env::var("APP_ENV").unwrap_or_default() == "production";

    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,tower_http=debug,sqlx=warn"));

    // The OTel layer goes on before the branch: a layer's type includes the stack below it, so one
    // otel_trace_layer can't be added on top of two different stacks
    let subscriber = tracing_subscriber::registry()
        .with(env_filter)
        .with(otel_trace_layer);

    if is_prod {
        // RedactingJson redacts by field NAME for every event at every level
        // (see Sensitive Data Protection)
        subscriber.with(fmt::layer().json().event_format(RedactingJson)).init();
    } else {
        // Pretty output is not redacted: local development only
        subscriber.with(fmt::layer().pretty()).init();
    }

    Ok(Telemetry { tracer_provider, meter_provider })
}

/// Graceful shutdown: flush all pending spans and metrics before exit.
pub async fn shutdown_telemetry(telemetry: Telemetry) {
    tracing::info!("shutting down telemetry — flushing spans and metrics");

    // Flush and shutdown the tracer provider
    if let Err(e) = telemetry.tracer_provider.shutdown() {
        tracing::error!(error = %e, "failed to shutdown tracer provider");
    }

    // Flush and shutdown the meter provider
    if let Err(e) = telemetry.meter_provider.shutdown() {
        tracing::error!(error = %e, "failed to shutdown meter provider");
    }
}
```

### Application Entrypoint

```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let telemetry = init_telemetry("order-service", env!("CARGO_PKG_VERSION"))?;

    // Your services, AppMetrics and Prometheus registry (see Metrics); the router is the
    // "Complete Middleware Stack" at the end of this file
    let state = Arc::new(AppState::from_env().await?);
    let app = build_router(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    tracing::info!("listening on {}", listener.local_addr()?);

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    shutdown_telemetry(telemetry).await;
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
use std::sync::Arc;

use axum::{extract::{Extension, State}, http::StatusCode, response::IntoResponse, Json};
use uuid::Uuid;

use crate::error::{AppError, AppJson, RequestId}; // error-handling-rust.md
use crate::extractors::auth_user::AuthUser;      // auth-middleware-rust.md

// --- Handler layer ---
#[tracing::instrument(
    name = "HTTP POST /api/v1/orders",
    skip(state, auth_user, request_id, body),
    fields(
        tenant_id = %auth_user.tenant_id,
        user_id = %auth_user.user_id,
        request_id = %request_id.0,
    )
)]
pub async fn create_order(
    State(state): State<Arc<AppState>>,
    auth_user: AuthUser,
    Extension(request_id): Extension<RequestId>, // inserted by request_id_middleware
    AppJson(body): AppJson<CreateOrderRequest>,
) -> Result<impl IntoResponse, AppError> {
    let order = state.order_service.create(auth_user.tenant_id, auth_user.user_id, body).await?;

    // Success body is the envelope (api/response-envelope.md)
    Ok((
        StatusCode::CREATED,
        Json(serde_json::json!({ "data": order, "meta": { "request_id": request_id.0 } })),
    ))
}

// --- Service layer ---
#[tracing::instrument(
    name = "OrderService.create",
    skip(self, body),
    fields(order_id = tracing::field::Empty)
)]
pub async fn create(
    &self,
    tenant_id: Uuid,
    user_id: Uuid,
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
        AppError::internal(e) // 500 with a generic message; the cause stays in the log
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
use std::sync::Arc;

use axum::{routing::get, Router};
use tower_http::trace::{DefaultMakeSpan, DefaultOnResponse, TraceLayer};
use tracing::Level;

pub fn build_router(state: Arc<AppState>) -> Router {
    let trace_layer = TraceLayer::new_for_http()
        .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
        .on_response(DefaultOnResponse::new().level(Level::INFO));

    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler)) // reads the registry from the state
        .layer(trace_layer)
        .with_state(state)
        // The request-ID, auth and tenant layers, and a make_span_with that declares tenant_id,
        // are in "Complete Middleware Stack" below
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
use tracing_opentelemetry::OpenTelemetrySpanExt; // Span::context()

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
            AppError::unavailable("downstream-service", e) // 503, retryable
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

// No request counter: the http.server.request.duration histogram's count IS the request count.
pub struct AppMetrics {
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
            request_duration: meter
                .f64_histogram("http.server.request.duration")
                .with_description("Duration of HTTP server requests")
                .with_unit("s")
                // OTel HTTP semconv buckets; the NFR latency threshold must be one of them. If your
                // opentelemetry version has no with_boundaries, set the same buckets with a View.
                .with_boundaries(vec![0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0])
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

These follow the stable OTel HTTP semantic conventions, and every attribute is bounded. **There is no
`tenant_id`**: each distinct value is a new time series (see `core/observability-patterns.md`
§tenant_id). If you really need a per-tenant dimension on a metric, the only one allowed is a bounded
`tenant.tier` (free/pro/enterprise). Ask per-tenant questions of traces and logs.

```rust
use axum::{
    body::Body,
    extract::{MatchedPath, State},
    http::{Request, Response},
    middleware::Next,
};
use opentelemetry::KeyValue;
use std::sync::Arc;
use std::time::Instant;

const KNOWN_METHODS: [&str; 7] = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"];

pub async fn metrics_middleware(
    State(state): State<Arc<AppState>>,
    request: Request<Body>,
    next: Next,
) -> Response<Body> {
    let start = Instant::now();
    let method = match request.method().as_str() {
        m if KNOWN_METHODS.contains(&m) => m.to_owned(),
        _ => "_OTHER".to_owned(),
    };
    let scheme = request.uri().scheme_str().unwrap_or("http").to_owned();
    // The route TEMPLATE ("/api/v1/orders/{id}"), which the router puts in the extensions for layers
    // added with Router::layer. It is None for an unmatched request (404), and then http.route is left
    // out. NEVER request.uri().path(): raw paths are unbounded series.
    let route = request
        .extensions()
        .get::<MatchedPath>()
        .map(|p| p.as_str().to_owned());

    // Concurrency is measured per method and scheme only, with no http.route
    let active_attrs = [
        KeyValue::new("http.request.method", method.clone()),
        KeyValue::new("url.scheme", scheme.clone()),
    ];
    state.metrics.active_requests.add(1, &active_attrs);

    let response = next.run(request).await;

    let status = response.status().as_u16();
    let mut attrs = vec![
        KeyValue::new("http.request.method", method),
        KeyValue::new("url.scheme", scheme),
        KeyValue::new("http.response.status_code", i64::from(status)),
    ];
    if let Some(route) = route {
        attrs.push(KeyValue::new("http.route", route));
    }
    if status >= 500 {
        attrs.push(KeyValue::new("error.type", status.to_string()));
    }
    state.metrics.request_duration.record(start.elapsed().as_secs_f64(), &attrs);
    state.metrics.active_requests.add(-1, &active_attrs);

    response
}
```

Test the route template: request `/api/v1/orders/123` and `/api/v1/orders/456`, then assert there is
exactly one series, with `http.route="/api/v1/orders/{id}"`.

Wire it into the router:

```rust
use axum::{middleware, routing::get, Router};

pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler))
        // Router::layer after the routes: the router has matched by then, so MatchedPath is set
        .layer(middleware::from_fn_with_state(state.clone(), metrics_middleware))
        .with_state(state)
}
```

### Prometheus Exporter Endpoint

```rust
use std::sync::Arc;

use axum::extract::State;
use opentelemetry::global;
use opentelemetry_prometheus::exporter;
use opentelemetry_sdk::metrics::SdkMeterProvider;
use prometheus::TextEncoder;

use crate::error::AppError;

pub fn setup_prometheus_exporter() -> prometheus::Registry {
    let registry = prometheus::Registry::new();

    let prometheus_exporter = exporter()
        .with_registry(registry.clone())
        .build()
        .expect("failed to build prometheus exporter");

    // The exporter is a metric reader: install a meter provider that reads through it as the global
    // provider. Use this when you want a /metrics endpoint instead of (or alongside) OTLP push.
    let provider = SdkMeterProvider::builder().with_reader(prometheus_exporter).build();
    global::set_meter_provider(provider);

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
        .map_err(AppError::internal) // 500 INTERNAL; the encoder's message stays in the log
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

    // Record business metrics. Small enums only, with no tenant_id (it is on the span already).
    self.metrics.order_total.add(1, &[
        KeyValue::new("payment_method", order.payment_method.to_string()),
    ]);
    self.metrics.order_value.record(order.total_as_f64(), &[
        KeyValue::new("payment_method", order.payment_method.to_string()),
    ]);

    Ok(order)
}
```

### Key Metrics Table

Every label comes from a small, known set: no `tenant_id`, user or entity IDs, raw paths, query
strings or error messages.

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http.server.request.duration` | Histogram (s) | http.request.method, http.route (`MatchedPath`), http.response.status_code, url.scheme, error.type (5xx) | Rate, errors and latency (RED); the count is the request count |
| `http.server.active_requests` | UpDownCounter | http.request.method, url.scheme | Concurrency / saturation |
| `db.query.duration` | Histogram | operation, table | Database performance |
| `db.pool.active_connections` | UpDownCounter | pool_name | Connection pool saturation |
| `cache.hit.total` | Counter | cache_name | Cache effectiveness |
| `cache.miss.total` | Counter | cache_name | Cache miss rate |
| `business.<event>.total` | Counter | type (a small enum) | Business KPIs |

**SLIs and alerting.** Don't compute SLIs in-process: no p99, availability or "budget remaining"
gauges. Percentiles can't be averaged across pods, and an in-memory window resets on every restart.
Compute SLIs at query time from the `http.server.request.duration` histogram (its 5xx share and its
bucket counts; the NFR latency threshold must be a bucket boundary), and alert with multi-window burn
rates. See `core/observability-patterns.md` §SLOs and Alerting.

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
// skip_all: without it, instrument records every argument with Debug (self, the whole order)
#[tracing::instrument(skip_all, fields(tenant_id = %tenant_id, user_id = %user_id))]
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

// DEBUG — troubleshooting detail (off in production by default). The query shape, never the
// parameter values.
tracing::debug!(
    query = "SELECT * FROM orders WHERE tenant_id = $1",
    param_count = 1,
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

`skip_all` and safe `Display` types protect a single call site. On top of them, **redaction by key
name is enforced in the subscriber**, for every event at every level. DEBUG gets switched on in
production during incidents, and it must stay safe then. tracing-subscriber's JSON formatter has no
redaction hook, so `init_telemetry()` plugs in this event formatter instead:

```rust
use serde_json::{Map, Value};
use std::fmt;
use tracing::field::{Field, Visit};
use tracing::{Event, Subscriber};
use tracing_subscriber::fmt::format::{JsonFields, Writer};
use tracing_subscriber::fmt::time::{FormatTime, SystemTime};
use tracing_subscriber::fmt::{FmtContext, FormatEvent, FormattedFields};
use tracing_subscriber::registry::LookupSpan;

const SENSITIVE: &[&str] = &[
    "pass", "secret", "token", "authorization", "cookie", "api_key", "apikey",
    "session", "card", "cvv", "iban", "ssn",
];

fn redact(key: &str, value: Value) -> Value {
    let key = key.to_ascii_lowercase();
    if SENSITIVE.iter().any(|s| key.contains(s)) { Value::from("[REDACTED]") } else { value }
}

struct RedactingVisitor<'a>(&'a mut Map<String, Value>);

impl RedactingVisitor<'_> {
    fn put(&mut self, field: &Field, value: Value) {
        self.0.insert(field.name().to_owned(), redact(field.name(), value));
    }
}

impl Visit for RedactingVisitor<'_> {
    fn record_str(&mut self, f: &Field, v: &str) { self.put(f, v.into()) }
    fn record_i64(&mut self, f: &Field, v: i64) { self.put(f, v.into()) }
    fn record_u64(&mut self, f: &Field, v: u64) { self.put(f, v.into()) }
    fn record_bool(&mut self, f: &Field, v: bool) { self.put(f, v.into()) }
    fn record_debug(&mut self, f: &Field, v: &dyn fmt::Debug) { self.put(f, format!("{v:?}").into()) }
}

/// JSON event formatter that redacts by field NAME. That covers the event's own fields and the ones
/// inherited from parent spans (tenant_id, request_id, ...).
pub struct RedactingJson;

impl<S> FormatEvent<S, JsonFields> for RedactingJson
where
    S: Subscriber + for<'a> LookupSpan<'a>,
{
    fn format_event(&self, ctx: &FmtContext<'_, S, JsonFields>, mut w: Writer<'_>, event: &Event<'_>) -> fmt::Result {
        let mut out = Map::new();
        let mut ts = String::new();
        SystemTime.format_time(&mut Writer::new(&mut ts))?;
        out.insert("timestamp".into(), ts.into());
        out.insert("level".into(), event.metadata().level().to_string().into());
        out.insert("target".into(), event.metadata().target().into());
        // Span fields first, root to leaf, so the event's own fields win on a name clash
        if let Some(scope) = ctx.event_scope() {
            for span in scope.from_root() {
                if let Some(f) = span.extensions().get::<FormattedFields<JsonFields>>() {
                    if let Ok(Value::Object(fields)) = serde_json::from_str::<Value>(&f.fields) {
                        for (k, v) in fields {
                            let v = redact(&k, v);
                            out.insert(k, v);
                        }
                    }
                }
            }
        }
        event.record(&mut RedactingVisitor(&mut out));
        writeln!(w, "{}", Value::Object(out))
    }
}
```

Never log request or response bodies. Add a unit test that logs `password` and `authorization` fields
and asserts they come out as `[REDACTED]`.

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
// There is ONE request-id middleware: error-handling-rust.md's (crate::error). It keeps a well-formed
// inbound X-Request-Id (bounded charset and length, so it can't inject log lines or bloat records) or
// mints one; runs the request in the task-local scope every error body reads its request_id from;
// inserts the RequestId extension; records the id on the request span (which declares request_id as
// an Empty field — see the middleware stack); and echoes X-Request-Id. A second middleware here would
// leave error bodies with a request_id that doesn't match the header.
use crate::error::{request_id_middleware, RequestId};
```

---

## Tenant-Aware Observability

Every log line and trace span MUST include `tenant_id`, and **no metric** may. This is enforced at
the middleware layer.

```rust
use axum::{body::Body, http::{Request, Response}, middleware::Next};

use crate::auth::claims::JwtClaims; // auth-middleware-rust.md
use crate::error::AppError;

/// Runs after the auth middleware. The tenant comes from the VERIFIED token's claims, via the
/// `JwtClaims` jwt_auth_middleware put in the request extensions. It never comes from a client header
/// such as X-Tenant-ID, which anyone can set.
pub async fn tenant_middleware(
    mut request: Request<Body>,
    next: Next,
) -> Result<Response<Body>, AppError> {
    let tenant_id = request
        .extensions()
        .get::<JwtClaims>()
        .map(|claims| claims.tenant_id.to_string())
        .ok_or(AppError::Unauthenticated)?;

    // Record on the request span (declared as an Empty field in make_span_with; see the middleware
    // stack). Every child span and log line inherits it. Never on a metric.
    tracing::Span::current().record("tenant_id", tenant_id.as_str());

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
use std::sync::Arc;

use axum::{body::Body, http::Request, middleware, routing::get, Router};
use tower_http::trace::{DefaultOnResponse, TraceLayer};
use tracing::Level;

use crate::auth::middleware::jwt_auth_middleware; // auth-middleware-rust.md
use crate::error::request_id_middleware;          // error-handling-rust.md
// metrics_middleware, metrics_handler and tenant_middleware are the sections above

pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .nest("/api/v1/orders", order_routes())
        .route("/health", get(health_check))
        .route("/metrics", get(metrics_handler))
        // --- Middleware applied bottom-up (last added = first executed) ---
        // 5. Tenant: records tenant_id from the verified JwtClaims on the request span
        .layer(middleware::from_fn(tenant_middleware))
        // 4. Auth: jwt_auth_middleware verifies the bearer token and inserts the verified JwtClaims
        //    { sub, tenant_id, roles } into the extensions
        .layer(middleware::from_fn_with_state(state.config.clone(), jwt_auth_middleware))
        // 3. Metrics: duration histogram + active requests. It sits outside auth so 401s are counted;
        //    MatchedPath is available because every layer here is a Router::layer.
        .layer(middleware::from_fn_with_state(state.clone(), metrics_middleware))
        // 2. Request ID (error-handling-rust.md): validates an inbound X-Request-Id or generates one
        .layer(middleware::from_fn(request_id_middleware))
        // 1. HTTP trace: the root span for each request. It declares the fields the middleware records
        //    later, because Span::record() on a field the span wasn't created with is silently dropped.
        //    It records url.path only, since the query string can carry tokens and PII.
        .layer(
            TraceLayer::new_for_http()
                .make_span_with(|req: &Request<Body>| {
                    tracing::info_span!(
                        "http_request",
                        http.request.method = %req.method(),
                        url.path = %req.uri().path(),
                        request_id = tracing::field::Empty,
                        tenant_id = tracing::field::Empty,
                    )
                })
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
| `tenant_id` | Span field from middleware (verified token) | Whose request |
| `request_id` | Span field from middleware (validated or generated) | Correlate within a request |
| `trace_id` | tracing-opentelemetry layer | Correlate across services |
| `span_id` | tracing-opentelemetry layer | Specific span reference |

---

## Critical Rules

- `tenant_id` on every log line and trace span, and on **no metric** (at most a bounded `tenant.tier`). It comes from the verified token (the `JwtClaims` the auth middleware inserts), never from a client header.
- Use `#[tracing::instrument]` at every layer boundary (handler, service, repository)
- Use `skip_all` and explicitly list safe fields to avoid leaking sensitive data. `RedactingJson` also redacts by field name at every level. Never log request or response bodies.
- Request IDs from an inbound header are validated (charset + length) before use
- JSON logging in production, pretty logging in development
- `RUST_LOG` env filter controls verbosity -- never hardcode log levels
- Every span records errors with `tracing::error!()` -- do not swallow errors silently
- Flush telemetry on graceful shutdown -- pending spans and metrics must be exported
- `http.route` on metrics is the router's `MatchedPath` template, never `uri().path()`. All metric labels are bounded; no request counter (the histogram count is the request count).
- SLIs come from the histogram at query time, and alerts use multi-window burn rates. No in-process SLA gauges.
- Business metrics alongside technical metrics -- track domain events, not just HTTP stats
- Prometheus `/metrics` endpoint for pull-based monitoring alongside OTLP push
