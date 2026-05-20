> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# Rust Patterns

## Project Structure
```
src/
  main.rs         # binary entry
  lib.rs          # library root
  domain/mod.rs, error.rs
  services/mod.rs
  repositories/mod.rs
  api/mod.rs, extractors.rs, middleware.rs
  error.rs        # unified error types + HTTP mapping
  config.rs
Cargo.toml
migrations/       # SQLx migrations
tests/            # integration tests
```

## Ownership
- `&str` over `String` in params when ownership unneeded
- `Arc<T>` for shared ownership across threads; `Rc<T>` single-thread only
- `Cow<'_, str>` when sometimes borrowing, sometimes owning
- Clone deliberately — every `.clone()` should have a reason

## Error Handling

```rust
// thiserror for domain errors
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

// anyhow for binary/application code
fn run() -> Result<()> {
    let config = load_config().context("failed to load config")?;
    let db = connect_db(&config.database_url).await.context("failed to connect to database")?;
    Ok(())
}

// From trait for error conversion at boundaries
impl From<sqlx::Error> for DomainError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => DomainError::NotFound { resource: "entity", id: Uuid::nil() },
            sqlx::Error::Database(ref db_err) => match db_err.code().map(|c| c.as_ref()) {
                Some("23505") => DomainError::Conflict("duplicate entry".into()),
                Some("23503") => DomainError::Validation { field: "reference".into(), message: "foreign key violation".into() },
                _ => DomainError::Internal(err.to_string()),
            },
            _ => DomainError::Internal(err.to_string()),
        }
    }
}

// HTTP mapping (Axum)
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
        (status, Json(json!({"error": {"code": code, "message": self.to_string()}}))).into_response()
    }
}
```

- `thiserror` for library/domain (typed, pattern-matchable); `anyhow` for binaries
- Never `.unwrap()` in production — only in tests
- `?` operator everywhere; `.context()` at every boundary

## Web Frameworks

### Axum
```rust
// Handler pattern
async fn create_order(
    State(state): State<AppState>,
    tenant: TenantId,
    Json(request): Json<CreateOrderRequest>,
) -> Result<(StatusCode, Json<ApiResponse<OrderResponse>>), DomainError> {
    let order = state.order_service.create_order(tenant.0, request).await?;
    Ok((StatusCode::CREATED, Json(ApiResponse::success(OrderResponse::from(order)))))
}

// Custom extractor
pub struct TenantId(pub Uuid);
#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for TenantId {
    type Rejection = DomainError;
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let tenant_str = parts.headers.get("X-Tenant-ID").and_then(|v| v.to_str().ok()).ok_or(DomainError::Unauthorized)?;
        Ok(TenantId(Uuid::parse_str(tenant_str).map_err(|_| DomainError::Validation { field: "X-Tenant-ID".into(), message: "invalid UUID".into() })?))
    }
}

// Router + middleware
fn app(state: AppState) -> Router {
    Router::new()
        .route("/orders", post(create_order).get(list_orders))
        .route("/orders/:id", get(get_order).put(update_order).delete(delete_order))
        .layer(ServiceBuilder::new()
            .layer(TraceLayer::new_for_http())
            .layer(TimeoutLayer::new(Duration::from_secs(30)))
            .layer(middleware::from_fn(tenant_middleware)))
        .with_state(state)
}
```

### Actix-web
```rust
async fn get_order(path: web::Path<Uuid>, tenant: TenantId, service: web::Data<OrderService>) -> Result<HttpResponse, DomainError> {
    let order = service.find_by_id(tenant.0, *path).await?;
    Ok(HttpResponse::Ok().json(ApiResponse::success(OrderResponse::from(order))))
}
```

## Repository (SQLx)

```rust
// Compile-time query checking with sqlx::query_as!
pub struct OrderRepository { pool: PgPool }
impl OrderRepository {
    pub async fn save(&self, order: &Order) -> Result<Order, DomainError> {
        Ok(sqlx::query_as!(Order, r#"
            INSERT INTO orders (id, tenant_id, status, total, created_by, version) VALUES ($1, $2, $3, $4, $5, 1)
            RETURNING id, tenant_id, status as "status: OrderStatus", total, created_at, version"#,
            order.id, order.tenant_id, order.status as OrderStatus, order.total, order.created_by,
        ).fetch_one(&self.pool).await?)
    }

    pub async fn update_with_optimistic_lock(&self, tenant_id: Uuid, order_id: Uuid, status: OrderStatus, expected_version: i32) -> Result<Order, DomainError> {
        sqlx::query_as!(Order, r#"
            UPDATE orders SET status = $1, version = version + 1, updated_at = NOW()
            WHERE tenant_id = $2 AND id = $3 AND version = $4 AND deleted_at IS NULL
            RETURNING id, tenant_id, status as "status: OrderStatus", total, created_at, version"#,
            status as OrderStatus, tenant_id, order_id, expected_version,
        ).fetch_optional(&self.pool).await?.ok_or(DomainError::Conflict("order was modified".into()))
    }

    pub async fn soft_delete(&self, tenant_id: Uuid, order_id: Uuid) -> Result<(), DomainError> {
        let rows = sqlx::query!("UPDATE orders SET deleted_at = NOW() WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL", tenant_id, order_id)
            .execute(&self.pool).await?.rows_affected();
        if rows == 0 { return Err(DomainError::NotFound { resource: "Order", id: order_id }); }
        Ok(())
    }
}

// Connection pooling
let pool = PgPoolOptions::new()
    .max_connections(20).min_connections(5).acquire_timeout(Duration::from_secs(30))
    .idle_timeout(Duration::from_secs(600)).max_lifetime(Duration::from_secs(1800))
    .connect(&database_url).await.context("failed to create pool")?;

// Transactions
let mut tx = pool.begin().await?;
let order = sqlx::query_as!(...).fetch_one(&mut *tx).await?;
// ... more ops on &mut *tx ...
tx.commit().await?;
```

## Testing

```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_order_status_transition() {
        let order = Order::new(Uuid::new_v4(), Uuid::new_v4());
        let order = order.confirm().unwrap();
        assert!(matches!(order.confirm().unwrap_err(), DomainError::Conflict(_)));
    }

    #[tokio::test]
    async fn test_service_create_order() {
        let mock_repo = MockOrderRepository::new();
        mock_repo.expect_save().returning(|order| Ok(order.clone()));
        let service = OrderService::new(mock_repo);
        let result = service.create_order(TENANT_ID, valid_request()).await;
        assert!(result.is_ok());
    }
}

// mockall
#[automock]
#[async_trait]
pub trait OrderRepository: Send + Sync {
    async fn find_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Option<Order>, DomainError>;
    async fn save(&self, order: &Order) -> Result<Order, DomainError>;
}

// Test fixtures
pub fn build_order(overrides: OrderOverrides) -> Order {
    Order {
        id: overrides.id.unwrap_or_else(Uuid::new_v4),
        tenant_id: overrides.tenant_id.unwrap_or(TENANT_ID),
        status: overrides.status.unwrap_or(OrderStatus::Pending),
        ..Default::default()
    }
}

// Integration with testcontainers
async fn setup_test_db() -> (PgPool, ContainerAsync<Postgres>) {
    let container = Cli::default().run(Postgres::default()).await;
    let url = format!("postgresql://postgres:postgres@localhost:{}/postgres", container.get_host_port_ipv4(5432).await);
    let pool = PgPool::connect(&url).await.unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    (pool, container)
}
```

## Async Patterns

```rust
// tokio::select! for racing futures
async fn fetch_with_fallback(primary: &str, fallback: &str) -> Result<Response, DomainError> {
    tokio::select! {
        result = fetch(primary) => result,
        _ = tokio::time::sleep(Duration::from_secs(2)) => fetch(fallback).await
    }
}

// tokio::try_join! for concurrent execution
let (user, orders, preferences) = tokio::try_join!(
    user_repo.find_by_id(tenant_id, user_id),
    order_repo.find_by_user(tenant_id, user_id),
    pref_repo.find_by_user(tenant_id, user_id),
)?;

// Streaming with bounded concurrency
let results: Vec<_> = stream::iter(items)
    .map(|item| { let sem = semaphore.clone(); async move { let _permit = sem.acquire().await.unwrap(); process_item(item).await } })
    .buffer_unordered(max_concurrent)
    .collect().await;

// Graceful shutdown
let shutdown_signal = async {
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {},
        _ = sigterm.recv() => {},
    }
};
tokio::select! {
    _ = run_server(listener, shutdown_rx) => {},
    _ = shutdown_signal => { let _ = shutdown_tx.send(()); tokio::time::sleep(Duration::from_secs(10)).await; }
}
pool.close().await;
```

## Performance

```rust
// Iterators are zero-cost — compiled to same code as manual loops
let total: Decimal = orders.iter().filter(|o| o.status == OrderStatus::Confirmed).map(|o| o.total).sum();

// Enums over trait objects when variants known at compile time (no vtable)
// Arc for shared state; RwLock for read-heavy, Mutex for write-heavy
// mpsc channels for background job queues
// spawn_blocking for CPU-bound work (bcrypt, image processing)
async fn hash_password(password: String) -> Result<String, DomainError> {
    tokio::task::spawn_blocking(move || bcrypt::hash(password, 12).map_err(|e| DomainError::Internal(e.to_string())))
        .await.map_err(|e| DomainError::Internal(e.to_string()))?
}
```

## Rules
- `#![deny(warnings)]` in CI; `clippy -- -D warnings`; `rustfmt`
- `cargo audit` for vulnerability scanning
- Feature flags for optional dependencies
- Never `.unwrap()` in production
- `tracing` crate for structured logging (not `log`)
- Pin versions in `Cargo.lock` (commit for binaries, not libraries)
