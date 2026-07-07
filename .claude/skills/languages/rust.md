> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

---
skill: rust
description: Rust patterns — ownership, Result/Option error handling, traits, async with tokio, cargo layout, testing conventions
version: "1.0"
tags:
  - rust
  - ownership
  - async
  - traits
  - testing
---

# Rust patterns and conventions for safe, performant applications.

## Project Structure
```
src/
  main.rs         # binary entry point
  lib.rs          # library root (if dual crate)
  domain/
    mod.rs        # entities, value objects
    error.rs      # domain error types
  services/
    mod.rs        # business logic
  repositories/
    mod.rs        # data access (SQLx)
  api/
    mod.rs        # HTTP handlers
    extractors.rs # custom Axum/Actix extractors
    middleware.rs  # auth, tenant, tracing middleware
  error.rs        # unified error types + HTTP mapping
  config.rs       # configuration loading
Cargo.toml
migrations/       # SQLx migrations
tests/            # integration tests
```

## Ownership
- Prefer `&str` over `String` in function parameters when ownership isn't needed
- Use `Arc<T>` for shared ownership across threads; `Rc<T>` only for single-thread
- `Cow<'_, str>` when sometimes borrowing, sometimes owning
- Clone deliberately — every `.clone()` should have a reason (e.g., moving into a spawned task)

---

## Error Handling

### thiserror for Library/Domain Errors
```rust
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum DomainError {
    #[error("validation failed: {field} — {message}")]
    Validation { field: String, message: String },

    #[error("{resource} {id} not found")]
    NotFound { resource: &'static str, id: Uuid },

    #[error("conflict: {0}")]
    Conflict(String),

    #[error("unauthorized")]
    Unauthorized,

    #[error("forbidden: {0}")]
    Forbidden(String),

    #[error("rate limited, retry after {retry_after_secs}s")]
    RateLimited { retry_after_secs: u64 },

    #[error("upstream service {service} failed: {detail}")]
    Upstream { service: String, detail: String },

    #[error("internal error: {0}")]
    Internal(String),
}
```

### anyhow for Application/Binary Code
```rust
use anyhow::{Context, Result};

fn run() -> Result<()> {
    let config = load_config()
        .context("failed to load config")?;

    let db = connect_db(&config.database_url)
        .await
        .context("failed to connect to database")?;

    Ok(())
}

// Use .context() to add human-readable info at each call site
// The error chain is preserved for debugging
```

### From Trait for Error Conversion
```rust
// Convert infrastructure errors to domain errors at boundaries
impl From<sqlx::Error> for DomainError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => DomainError::NotFound {
                resource: "entity",
                id: Uuid::nil(),
            },
            sqlx::Error::Database(ref db_err) => {
                if let Some(code) = db_err.code() {
                    match code.as_ref() {
                        "23505" => DomainError::Conflict("duplicate entry".into()),
                        "23503" => DomainError::Validation {
                            field: "reference".into(),
                            message: "foreign key violation".into(),
                        },
                        _ => DomainError::Internal(err.to_string()),
                    }
                } else {
                    DomainError::Internal(err.to_string())
                }
            }
            _ => DomainError::Internal(err.to_string()),
        }
    }
}
```

### HTTP Error Mapping (Axum)
```rust
use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde_json::json;

impl IntoResponse for DomainError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            DomainError::Validation { .. } => (StatusCode::BAD_REQUEST, "VALIDATION_ERROR"),
            DomainError::NotFound { .. } => (StatusCode::NOT_FOUND, "NOT_FOUND"),
            DomainError::Conflict(_) => (StatusCode::CONFLICT, "CONFLICT"),
            DomainError::Unauthorized => (StatusCode::UNAUTHORIZED, "UNAUTHORIZED"),
            DomainError::Forbidden(_) => (StatusCode::FORBIDDEN, "FORBIDDEN"),
            DomainError::RateLimited { .. } => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMITED"),
            DomainError::Upstream { .. } => (StatusCode::BAD_GATEWAY, "UPSTREAM_ERROR"),
            DomainError::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
        };

        let body = json!({
            "error": {
                "code": code,
                "message": self.to_string(),
            }
        });

        (status, Json(body)).into_response()
    }
}
```

### Error Rules
- `thiserror` for library/domain errors (structured, typed, pattern-matchable)
- `anyhow` for application/binary error propagation (quick prototyping, scripts, main.rs)
- Never `.unwrap()` or `.expect()` in production code — only in tests or provably unreachable paths
- Use `?` operator everywhere — it calls `From::from()` automatically
- Add `.context("what was happening")` at every boundary crossing

---

## Web Framework Patterns

### Axum Handler Patterns
```rust
use axum::{extract::{Path, Query, State, Json}, http::StatusCode};

// Handler: Parse → Validate → Execute → Respond
async fn create_order(
    State(state): State<AppState>,
    tenant: TenantId,                      // custom extractor
    Json(request): Json<CreateOrderRequest>,
) -> Result<(StatusCode, Json<ApiResponse<OrderResponse>>), DomainError> {
    // Validation handled by serde + custom validators in CreateOrderRequest
    let order = state.order_service
        .create_order(tenant.0, request)
        .await?;

    Ok((
        StatusCode::CREATED,
        Json(ApiResponse::success(OrderResponse::from(order))),
    ))
}

// List with pagination
async fn list_orders(
    State(state): State<AppState>,
    tenant: TenantId,
    Query(params): Query<PaginationParams>,
) -> Result<Json<ApiResponse<Vec<OrderResponse>>>, DomainError> {
    let (orders, next_cursor) = state.order_service
        .list_orders(tenant.0, params.cursor.as_deref(), params.limit.unwrap_or(20))
        .await?;

    Ok(Json(ApiResponse::paginated(
        orders.into_iter().map(OrderResponse::from).collect(),
        next_cursor,
    )))
}

// Router setup
fn order_routes() -> Router<AppState> {
    Router::new()
        .route("/orders", post(create_order).get(list_orders))
        .route("/orders/:id", get(get_order).put(update_order).delete(delete_order))
}
```

### Custom Axum Extractors
```rust
use axum::{extract::FromRequestParts, http::request::Parts};
use uuid::Uuid;

pub struct TenantId(pub Uuid);

#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for TenantId {
    type Rejection = DomainError;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let tenant_str = parts
            .headers
            .get("X-Tenant-ID")
            .and_then(|v| v.to_str().ok())
            .ok_or(DomainError::Unauthorized)?;

        let tenant_id = Uuid::parse_str(tenant_str)
            .map_err(|_| DomainError::Validation {
                field: "X-Tenant-ID".into(),
                message: "invalid UUID".into(),
            })?;

        Ok(TenantId(tenant_id))
    }
}

// Pagination params
#[derive(Debug, Deserialize)]
pub struct PaginationParams {
    pub cursor: Option<String>,
    pub limit: Option<i64>,
}
```

### Actix-web Patterns
```rust
use actix_web::{web, HttpResponse, middleware};

// Handler with Path and JSON extractors
async fn get_order(
    path: web::Path<Uuid>,
    tenant: TenantId,
    service: web::Data<OrderService>,
) -> Result<HttpResponse, DomainError> {
    let order = service.find_by_id(tenant.0, *path).await?;
    Ok(HttpResponse::Ok().json(ApiResponse::success(OrderResponse::from(order))))
}

// App setup
fn configure_app(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api/v1")
            .wrap(middleware::Logger::default())
            .wrap(TenantMiddleware)
            .service(
                web::scope("/orders")
                    .route("", web::post().to(create_order))
                    .route("", web::get().to(list_orders))
                    .route("/{id}", web::get().to(get_order))
            )
    );
}
```

### Tower Middleware (Axum)
```rust
use tower_http::{trace::TraceLayer, cors::CorsLayer, timeout::TimeoutLayer};
use std::time::Duration;

fn app(state: AppState) -> Router {
    Router::new()
        .merge(order_routes())
        .merge(user_routes())
        .layer(
            ServiceBuilder::new()
                .layer(TraceLayer::new_for_http())
                .layer(TimeoutLayer::new(Duration::from_secs(30)))
                .layer(CorsLayer::permissive()) // tighten for production
                .layer(middleware::from_fn(tenant_middleware))
        )
        .with_state(state)
}

// Custom middleware function
async fn tenant_middleware(
    mut req: axum::extract::Request,
    next: axum::middleware::Next,
) -> Result<Response, DomainError> {
    let tenant_id = req.headers()
        .get("X-Tenant-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| Uuid::parse_str(v).ok())
        .ok_or(DomainError::Unauthorized)?;

    req.extensions_mut().insert(TenantId(tenant_id));

    let span = tracing::info_span!("request", tenant_id = %tenant_id);
    Ok(next.run(req).instrument(span).await)
}
```

---

## Multi-Tenancy in Rust

### Extractor-Based Tenant Context
```rust
// The TenantId extractor (shown above) is the primary mechanism
// Every handler that needs tenant context includes it as a parameter
// Axum extracts it from the request before the handler runs

async fn create_order(
    State(state): State<AppState>,
    tenant: TenantId,              // extracted from X-Tenant-ID header
    Json(request): Json<CreateOrderRequest>,
) -> Result<impl IntoResponse, DomainError> {
    // tenant.0 is the UUID — pass it through every layer
    let order = state.order_service.create_order(tenant.0, request).await?;
    Ok((StatusCode::CREATED, Json(order)))
}
```

### SQLx Queries with Tenant Filtering
```rust
// EVERY query includes tenant_id — no exceptions
pub async fn find_by_id(
    pool: &PgPool,
    tenant_id: Uuid,
    order_id: Uuid,
) -> Result<Option<Order>, DomainError> {
    let order = sqlx::query_as!(
        Order,
        r#"
        SELECT id, tenant_id, status as "status: OrderStatus", total, created_at, version
        FROM orders
        WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
        "#,
        tenant_id,
        order_id,
    )
    .fetch_optional(pool)
    .await?;

    Ok(order)
}

// Cursor-based pagination with tenant isolation
pub async fn list_paginated(
    pool: &PgPool,
    tenant_id: Uuid,
    cursor: Option<chrono::DateTime<Utc>>,
    limit: i64,
) -> Result<(Vec<Order>, Option<String>), DomainError> {
    let orders = match cursor {
        Some(c) => sqlx::query_as!(
            Order,
            r#"
            SELECT id, tenant_id, status as "status: OrderStatus", total, created_at, version
            FROM orders
            WHERE tenant_id = $1 AND created_at < $2 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $3
            "#,
            tenant_id, c, limit + 1,
        ).fetch_all(pool).await?,
        None => sqlx::query_as!(
            Order,
            r#"
            SELECT id, tenant_id, status as "status: OrderStatus", total, created_at, version
            FROM orders
            WHERE tenant_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $2
            "#,
            tenant_id, limit + 1,
        ).fetch_all(pool).await?,
    };

    let has_more = orders.len() as i64 > limit;
    let orders: Vec<Order> = orders.into_iter().take(limit as usize).collect();
    let next_cursor = if has_more {
        orders.last().map(|o| encode_cursor(o.created_at))
    } else {
        None
    };

    Ok((orders, next_cursor))
}
```

---

## Repository Pattern in Rust

### SQLx with Compile-Time Query Checking
```rust
// sqlx::query_as! checks queries against the actual database at compile time
// Catches typos, type mismatches, and missing columns BEFORE runtime

pub struct OrderRepository {
    pool: PgPool,
}

impl OrderRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn save(&self, order: &Order) -> Result<Order, DomainError> {
        let saved = sqlx::query_as!(
            Order,
            r#"
            INSERT INTO orders (id, tenant_id, status, total, created_by, version)
            VALUES ($1, $2, $3, $4, $5, 1)
            RETURNING id, tenant_id, status as "status: OrderStatus", total, created_at, version
            "#,
            order.id,
            order.tenant_id,
            order.status as OrderStatus,
            order.total,
            order.created_by,
        )
        .fetch_one(&self.pool)
        .await?;

        Ok(saved)
    }

    pub async fn update_with_optimistic_lock(
        &self,
        tenant_id: Uuid,
        order_id: Uuid,
        status: OrderStatus,
        expected_version: i32,
    ) -> Result<Order, DomainError> {
        let result = sqlx::query_as!(
            Order,
            r#"
            UPDATE orders
            SET status = $1, version = version + 1, updated_at = NOW()
            WHERE tenant_id = $2 AND id = $3 AND version = $4 AND deleted_at IS NULL
            RETURNING id, tenant_id, status as "status: OrderStatus", total, created_at, version
            "#,
            status as OrderStatus,
            tenant_id,
            order_id,
            expected_version,
        )
        .fetch_optional(&self.pool)
        .await?;

        result.ok_or(DomainError::Conflict(
            "order was modified by another request".into(),
        ))
    }

    pub async fn soft_delete(&self, tenant_id: Uuid, order_id: Uuid) -> Result<(), DomainError> {
        let rows = sqlx::query!(
            "UPDATE orders SET deleted_at = NOW() WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL",
            tenant_id,
            order_id,
        )
        .execute(&self.pool)
        .await?
        .rows_affected();

        if rows == 0 {
            return Err(DomainError::NotFound { resource: "Order", id: order_id });
        }
        Ok(())
    }
}
```

### Connection Pooling
```rust
use sqlx::postgres::PgPoolOptions;

let pool = PgPoolOptions::new()
    .max_connections(20)
    .min_connections(5)
    .acquire_timeout(Duration::from_secs(30))
    .idle_timeout(Duration::from_secs(600))
    .max_lifetime(Duration::from_secs(1800))
    .after_connect(|conn, _meta| Box::pin(async move {
        // Set session-level defaults (e.g., statement timeout)
        sqlx::query("SET statement_timeout = '30s'")
            .execute(conn)
            .await?;
        Ok(())
    }))
    .connect(&database_url)
    .await
    .context("failed to create connection pool")?;
```

### Transaction Support
```rust
pub async fn create_order_with_inventory(
    pool: &PgPool,
    tenant_id: Uuid,
    request: CreateOrderRequest,
) -> Result<Order, DomainError> {
    let mut tx = pool.begin().await?;

    // All operations in one transaction
    let order = sqlx::query_as!(
        Order,
        r#"INSERT INTO orders (id, tenant_id, status, total) VALUES ($1, $2, 'pending', $3)
           RETURNING id, tenant_id, status as "status: OrderStatus", total, created_at, version"#,
        Uuid::new_v4(), tenant_id, request.total,
    )
    .fetch_one(&mut *tx)
    .await?;

    for item in &request.items {
        sqlx::query!(
            "UPDATE inventory SET quantity = quantity - $1 WHERE tenant_id = $2 AND sku = $3 AND quantity >= $1",
            item.quantity, tenant_id, item.sku,
        )
        .execute(&mut *tx)
        .await
        .map_err(|_| DomainError::Conflict("insufficient inventory".into()))?;
    }

    tx.commit().await?;
    Ok(order)
}
```

### Migration Patterns
```bash
# Create migration
sqlx migrate add create_orders_table

# Migration file: migrations/20240115_create_orders_table.sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total DECIMAL(12,2) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    created_by UUID
);

CREATE INDEX idx_orders_tenant_status ON orders(tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_orders_tenant_created ON orders(tenant_id, created_at DESC) WHERE deleted_at IS NULL;

# Run migrations
sqlx migrate run

# Compile-time verification
cargo sqlx prepare  # generates query metadata for offline builds
```

---

## Testing in Rust

### Unit Tests with #[test] and #[tokio::test]
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_order_status_transition() {
        let order = Order::new(Uuid::new_v4(), Uuid::new_v4());
        assert_eq!(order.status, OrderStatus::Pending);

        let order = order.confirm().unwrap();
        assert_eq!(order.status, OrderStatus::Confirmed);

        // Invalid transition
        let err = order.confirm().unwrap_err();
        assert!(matches!(err, DomainError::Conflict(_)));
    }

    #[tokio::test]
    async fn test_service_create_order() {
        let mock_repo = MockOrderRepository::new();
        mock_repo.expect_save()
            .returning(|order| Ok(order.clone()));

        let service = OrderService::new(mock_repo);
        let result = service.create_order(TENANT_ID, valid_request()).await;

        assert!(result.is_ok());
        assert_eq!(result.unwrap().status, OrderStatus::Pending);
    }
}
```

### mockall for Mocking Traits
```rust
use mockall::automock;

#[automock]
#[async_trait]
pub trait OrderRepository: Send + Sync {
    async fn find_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Option<Order>, DomainError>;
    async fn save(&self, order: &Order) -> Result<Order, DomainError>;
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), DomainError>;
}

#[tokio::test]
async fn test_get_order_not_found() {
    let mut mock_repo = MockOrderRepository::new();
    mock_repo
        .expect_find_by_id()
        .with(eq(TENANT_ID), eq(ORDER_ID))
        .returning(|_, _| Ok(None));

    let service = OrderService::new(Arc::new(mock_repo));
    let result = service.get_order(TENANT_ID, ORDER_ID).await;

    assert!(matches!(result, Err(DomainError::NotFound { .. })));
}
```

### Test Fixtures and Factories
```rust
// Test helpers module
#[cfg(test)]
pub mod test_helpers {
    use super::*;

    pub const TENANT_ID: Uuid = uuid!("00000000-0000-0000-0000-000000000001");

    pub fn build_order(overrides: OrderOverrides) -> Order {
        Order {
            id: overrides.id.unwrap_or_else(Uuid::new_v4),
            tenant_id: overrides.tenant_id.unwrap_or(TENANT_ID),
            status: overrides.status.unwrap_or(OrderStatus::Pending),
            total: overrides.total.unwrap_or(Decimal::new(10000, 2)),
            version: overrides.version.unwrap_or(1),
            created_at: overrides.created_at.unwrap_or_else(Utc::now),
        }
    }

    #[derive(Default)]
    pub struct OrderOverrides {
        pub id: Option<Uuid>,
        pub tenant_id: Option<Uuid>,
        pub status: Option<OrderStatus>,
        pub total: Option<Decimal>,
        pub version: Option<i32>,
        pub created_at: Option<DateTime<Utc>>,
    }

    // Usage:
    // let order = build_order(OrderOverrides { status: Some(OrderStatus::Confirmed), ..Default::default() });
}
```

### Integration Tests with testcontainers
```rust
// tests/integration/mod.rs
use testcontainers::{clients::Cli, images::postgres::Postgres};

async fn setup_test_db() -> (PgPool, ContainerAsync<Postgres>) {
    let docker = Cli::default();
    let container = docker.run(Postgres::default()).await;
    let port = container.get_host_port_ipv4(5432).await;
    let url = format!("postgresql://postgres:postgres@localhost:{}/postgres", port);

    let pool = PgPool::connect(&url).await.unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();

    (pool, container)
}

#[tokio::test]
async fn test_order_repository_crud() {
    let (pool, _container) = setup_test_db().await;
    let repo = OrderRepository::new(pool.clone());

    // Create
    let order = build_order(Default::default());
    let saved = repo.save(&order).await.unwrap();
    assert_eq!(saved.tenant_id, TENANT_ID);

    // Read
    let found = repo.find_by_id(TENANT_ID, saved.id).await.unwrap();
    assert!(found.is_some());

    // Soft delete
    repo.soft_delete(TENANT_ID, saved.id).await.unwrap();
    let found = repo.find_by_id(TENANT_ID, saved.id).await.unwrap();
    assert!(found.is_none()); // filtered by deleted_at IS NULL
}
```

---

## Performance

### Zero-Cost Abstractions
```rust
// Iterators are zero-cost — compiled to the same code as manual loops
let total: Decimal = orders
    .iter()
    .filter(|o| o.status == OrderStatus::Confirmed)
    .map(|o| o.total)
    .sum();

// Generic functions are monomorphized — no runtime dispatch overhead
fn process<T: Serialize>(item: &T) -> Result<Vec<u8>, serde_json::Error> {
    serde_json::to_vec(item) // compiled to specialized code for each T
}

// Enums instead of trait objects when variants are known at compile time
enum Notification {
    Email(EmailNotification),
    Sms(SmsNotification),
    Push(PushNotification),
}
// No vtable lookup — pattern match is a jump table
```

### Arc, Mutex, and Channels
```rust
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock, mpsc};

// Shared state in Axum — Arc is the standard approach
#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,                          // PgPool is already Arc internally
    pub cache: Arc<RwLock<HashMap<String, CachedValue>>>, // read-heavy cache
    pub order_service: Arc<OrderService>,
}

// Use RwLock for read-heavy data (many readers, rare writers)
// Use Mutex for write-heavy data
// Use channels (mpsc, broadcast) for message passing between tasks

// mpsc channel for background job queue
let (tx, mut rx) = mpsc::channel::<Job>(100);

tokio::spawn(async move {
    while let Some(job) = rx.recv().await {
        process_job(job).await;
    }
});

// Send jobs from handlers
tx.send(Job::ProcessOrder(order_id)).await?;
```

### Tokio Runtime Configuration
```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Default: multi-threaded runtime with worker threads = CPU cores
    // For most services, the default is correct

    // Custom runtime for fine-tuning:
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)        // limit worker threads
        .max_blocking_threads(64) // for spawn_blocking calls
        .enable_all()
        .build()?;

    runtime.block_on(async { run_server().await })
}

// CPU-bound work: use spawn_blocking to avoid blocking the async runtime
async fn hash_password(password: String) -> Result<String, DomainError> {
    tokio::task::spawn_blocking(move || {
        bcrypt::hash(password, 12).map_err(|e| DomainError::Internal(e.to_string()))
    })
    .await
    .map_err(|e| DomainError::Internal(e.to_string()))?
}
```

---

## Async Patterns

### tokio::select! for Racing Futures
```rust
use tokio::time::timeout;

async fn fetch_with_fallback(primary: &str, fallback: &str) -> Result<Response, DomainError> {
    tokio::select! {
        result = fetch(primary) => result,
        _ = tokio::time::sleep(Duration::from_secs(2)) => {
            // Primary timed out — try fallback
            fetch(fallback).await
        }
    }
}

// Graceful shutdown with select
async fn run_server(listener: TcpListener, shutdown: tokio::sync::watch::Receiver<()>) {
    loop {
        tokio::select! {
            Ok((stream, _)) = listener.accept() => {
                tokio::spawn(handle_connection(stream));
            }
            _ = shutdown.changed() => {
                tracing::info!("shutdown signal received");
                break;
            }
        }
    }
}
```

### tokio::join! for Concurrent Execution
```rust
async fn fetch_user_profile(tenant_id: Uuid, user_id: Uuid) -> Result<UserProfile, DomainError> {
    // Run all three queries concurrently
    let (user, orders, preferences) = tokio::try_join!(
        user_repo.find_by_id(tenant_id, user_id),
        order_repo.find_by_user(tenant_id, user_id),
        pref_repo.find_by_user(tenant_id, user_id),
    )?;

    let user = user.ok_or(DomainError::NotFound { resource: "User", id: user_id })?;

    Ok(UserProfile { user, orders, preferences })
}
```

### Streaming with futures::Stream
```rust
use futures::stream::{self, StreamExt};
use tokio::sync::Semaphore;

async fn process_batch(
    items: Vec<Item>,
    max_concurrent: usize,
) -> Vec<Result<ProcessedItem, DomainError>> {
    let semaphore = Arc::new(Semaphore::new(max_concurrent));

    let results: Vec<_> = stream::iter(items)
        .map(|item| {
            let sem = semaphore.clone();
            async move {
                let _permit = sem.acquire().await.unwrap();
                process_item(item).await
            }
        })
        .buffer_unordered(max_concurrent)
        .collect()
        .await;

    results
}
```

### Graceful Shutdown
```rust
async fn main() -> anyhow::Result<()> {
    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(());

    // Listen for OS signals
    let shutdown_signal = async {
        let ctrl_c = tokio::signal::ctrl_c();
        let mut sigterm = tokio::signal::unix::signal(
            tokio::signal::unix::SignalKind::terminate()
        ).unwrap();

        tokio::select! {
            _ = ctrl_c => tracing::info!("received SIGINT"),
            _ = sigterm.recv() => tracing::info!("received SIGTERM"),
        }
    };

    tokio::select! {
        _ = run_server(listener, shutdown_rx) => {},
        _ = shutdown_signal => {
            tracing::info!("initiating graceful shutdown");
            let _ = shutdown_tx.send(());
            // Allow in-flight requests to complete (up to timeout)
            tokio::time::sleep(Duration::from_secs(10)).await;
        }
    }

    // Cleanup: close DB pool, flush metrics
    pool.close().await;
    tracing::info!("shutdown complete");

    Ok(())
}
```

---

## Rules
- `#![deny(warnings)]` in CI (not in library crate root)
- Run `clippy -- -D warnings` in CI
- `rustfmt` for formatting — no manual style debates
- `cargo audit` for dependency vulnerability scanning
- Feature flags in `Cargo.toml` for optional dependencies
- Never `.unwrap()` in production — only in tests
- Prefer `&str` over `String` in function params when not taking ownership
- Use `tracing` crate for structured logging (not `log` + `env_logger`)
- Pin dependency versions in `Cargo.lock` (commit it for binaries, not for libraries)
