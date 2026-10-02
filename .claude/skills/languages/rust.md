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

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, axum 0.8.9, sqlx 0.9.0 (query! macros checked against this file's own migration on Postgres 17), actix-web 4.15.0, mockall 0.15.0, testcontainers-modules 0.15.0. Run (run-tests.sh): the unit and mockall tests and the testcontainers test (a real postgres:17-alpine) pass; harness tests on top show an out-of-range `limit` is a 400, the tenant comes from the verified token, the keyset cursor neither skips nor repeats rows, short stock rolls the whole order back, and a stale version is a 409. The repository tests run as a NOSUPERUSER NOBYPASSRLS role that owns nothing: with the migration's RLS, a tenant sees only its own rows even without a WHERE clause, and a query with no tenant set — or after the tenant transaction ended — errors.

## Project Structure
```text
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
use serde::Serialize;
use thiserror::Error;
use uuid::Uuid;

/// One entry of error.details[] (api/response-envelope.md): `code` from its closed set, catalog `message`.
#[derive(Debug, Clone, Serialize)]
pub struct FieldError {
    pub field: String,
    pub code: &'static str,
    pub message: &'static str, // fixed catalog text — never a validator's or driver's message
}

impl FieldError {
    pub fn new(field: impl Into<String>, code: &'static str) -> Self {
        let message = match code {
            "required" => "This field is required.",
            "invalid_format" => "This value has the wrong format.",
            "too_short" => "This value is too short.",
            "too_long" => "This value is too long.",
            "out_of_range" => "This value is out of range.",
            "invalid_cursor" => "This cursor is not valid. Start from the first page.",
            "already_exists" => "This already exists.",
            _ => "This value is invalid.", // invalid_value
        };
        Self { field: field.into(), code, message }
    }
}

// Display (#[error]) is server-side log text. The response body uses the catalog in `into_response`.
#[derive(Debug, Error)]
pub enum DomainError {
    #[error("malformed request")]
    MalformedRequest,

    #[error("validation failed: {0:?}")]
    Validation(Vec<FieldError>),

    #[error("{resource} {id} not found")]
    NotFound { resource: &'static str, id: Uuid },

    #[error("conflict: {0}")]
    Conflict(String), // user-safe text, shown as-is

    #[error("business rule violated: {0}")]
    BusinessRule(String), // user-safe text, shown as-is

    #[error("unauthenticated")]
    Unauthenticated,

    #[error("forbidden")]
    Forbidden,

    #[error("rate limited, retry after {retry_after_secs}s")]
    RateLimited { retry_after_secs: u64 },

    #[error("dependency {service} unavailable: {cause:#}")]
    Unavailable { service: &'static str, cause: anyhow::Error },

    #[error("internal error: {0:#}")]
    Internal(anyhow::Error),
}
```

### anyhow for Application/Binary Code
```rust
use anyhow::{Context, Result};
use sqlx::PgPool;

async fn run() -> Result<()> {
    let config = load_config()
        .context("failed to load config")?;

    let pool = PgPool::connect(&config.database_url)
        .await
        .context("failed to connect to database")?;

    serve(config, pool).await.context("server stopped with an error")
}

// Use .context() to add human-readable info at each call site
// The error chain is preserved for debugging
```

### From Trait for Error Conversion
```rust
// Convert infrastructure errors to domain errors at boundaries
impl From<sqlx::Error> for DomainError {
    fn from(err: sqlx::Error) -> Self {
        if matches!(err, sqlx::Error::RowNotFound) {
            return DomainError::NotFound { resource: "entity", id: Uuid::nil() };
        }
        let pg_code = err.as_database_error().and_then(|e| e.code()).map(|c| c.into_owned());
        match pg_code.as_deref() {
            Some("23505") => DomainError::Conflict("This already exists.".into()),
            // a reference to a row that does not exist (foreign key)
            Some("23503") => DomainError::Validation(vec![FieldError::new("reference", "invalid_value")]),
            // Anything else: the driver's text stays in the source chain for the log, never in the body
            _ => DomainError::Internal(err.into()),
        }
    }
}
```

### Response Envelope
```rust
use serde::Serialize;

// Every body is the envelope in api/response-envelope.md.
tokio::task_local! {
    /// Set for the whole request by the request-id middleware (outermost layer); = the X-Request-Id header.
    pub static REQUEST_ID: String;
}
pub fn current_request_id() -> String {
    REQUEST_ID.try_with(Clone::clone).unwrap_or_default()
}

/// Success: {"data": …, "meta": {"request_id": …}}; lists add meta.pagination (cursor only).
#[derive(Serialize)]
pub struct ApiResponse<T> {
    pub data: T,
    pub meta: Meta,
}

#[derive(Serialize)]
pub struct Meta {
    pub request_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pagination: Option<Pagination>,
}

#[derive(Serialize)]
pub struct Pagination {
    pub next_cursor: Option<String>, // serialized as null when has_more is false
    pub has_more: bool,
    pub limit: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_count: Option<i64>, // only when cheap and the UI shows it
}

impl<T: Serialize> ApiResponse<T> {
    pub fn success(data: T) -> Self {
        Self { data, meta: Meta { request_id: current_request_id(), pagination: None } }
    }
}

impl<T: Serialize> ApiResponse<Vec<T>> {
    pub fn paginated(data: Vec<T>, next_cursor: Option<String>, limit: i64) -> Self {
        let has_more = next_cursor.is_some();
        let pagination = Pagination { next_cursor, has_more, limit, total_count: None };
        Self { data, meta: Meta { request_id: current_request_id(), pagination: Some(pagination) } }
    }
}
```

### HTTP Error Mapping (Axum)
```rust
use axum::{http::{header, HeaderValue, StatusCode}, response::{IntoResponse, Response}, Json};
use serde_json::json;

impl DomainError {
    /// (status, code, user-safe message, retryable) — the table in api/response-envelope.md
    fn parts(&self) -> (StatusCode, &'static str, String, bool) {
        match self {
            DomainError::MalformedRequest => (StatusCode::BAD_REQUEST, "MALFORMED_REQUEST", "The request could not be read.".into(), false),
            DomainError::Validation(_) => (StatusCode::BAD_REQUEST, "VALIDATION_FAILED", "Some fields are invalid.".into(), false),
            DomainError::Unauthenticated => (StatusCode::UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.".into(), false),
            DomainError::Forbidden => (StatusCode::FORBIDDEN, "FORBIDDEN", "You don't have permission to do this.".into(), false),
            // also for another tenant's object — never 403, don't confirm it exists
            DomainError::NotFound { resource, .. } => (StatusCode::NOT_FOUND, "NOT_FOUND", format!("{resource} not found."), false),
            DomainError::Conflict(msg) => (StatusCode::CONFLICT, "CONFLICT", msg.clone(), false),
            DomainError::BusinessRule(msg) => (StatusCode::UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION", msg.clone(), false),
            DomainError::RateLimited { .. } => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMITED", "Too many requests. Try again shortly.".into(), true),
            DomainError::Unavailable { .. } => (StatusCode::SERVICE_UNAVAILABLE, "UNAVAILABLE", "The service is temporarily unavailable.".into(), true),
            DomainError::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL", "Something went wrong.".into(), false),
        }
    }
}

impl IntoResponse for DomainError {
    fn into_response(self) -> Response {
        let (status, code, message, retryable) = self.parts();
        let request_id = current_request_id();
        if status.is_server_error() {
            // the only place the cause (driver/upstream text) goes: the log, under the same request_id
            tracing::error!(%request_id, code, error = %self, "request failed");
        }

        let mut error = json!({ "code": code, "message": message, "request_id": request_id, "retryable": retryable });
        if let DomainError::Validation(details) = &self {
            error["details"] = json!(details);
        }
        let mut res = (status, Json(json!({ "error": error }))).into_response();

        match &self {
            DomainError::RateLimited { retry_after_secs } => {
                res.headers_mut().insert(header::RETRY_AFTER, HeaderValue::from(*retry_after_secs));
            }
            DomainError::Unavailable { .. } => {
                res.headers_mut().insert(header::RETRY_AFTER, HeaderValue::from_static("5"));
            }
            DomainError::Unauthenticated => {
                res.headers_mut().insert(header::WWW_AUTHENTICATE, HeaderValue::from_static("Bearer"));
            }
            _ => {}
        }
        res
    }
}
// Axum's own extractor rejections (bad JSON, bad query/path) have plain-text bodies —
// map them to DomainError as shown in frameworks/axum.md.
```

### Error Rules
- `thiserror` for library/domain errors (structured, typed, pattern-matchable)
- `anyhow` for application/binary error propagation (quick prototyping, scripts, main.rs)
- Never `.unwrap()` or `.expect()` in production code — only in tests or provably unreachable paths
- Use `?` operator everywhere — it calls `From::from()` automatically
- Add `.context("what was happening")` at every boundary crossing
- A domain error's `Display` output is log text: it never goes into a response body
  (codes/statuses: `api/response-envelope.md`)

---

## Web Framework Patterns

### Axum Handler Patterns
```rust
use axum::{extract::{Query, State, Json}, http::StatusCode, routing::{get, post}, Router};

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

// List with cursor pagination: ?cursor=<opaque>&limit=<n>
async fn list_orders(
    State(state): State<AppState>,
    tenant: TenantId,
    Query(params): Query<PaginationParams>,
) -> Result<Json<ApiResponse<Vec<OrderResponse>>>, DomainError> {
    // limit defaults to 20; outside 1..=100 is 400 VALIDATION_FAILED — never clamped silently
    // (api/response-envelope.md: a client asking for 500 and getting 100 can't tell)
    let limit = params.limit.unwrap_or(20);
    if !(1..=100).contains(&limit) {
        return Err(DomainError::Validation(vec![FieldError::new("limit", "out_of_range")]));
    }
    let (orders, next_cursor) = state.order_service
        .list_orders(tenant.0, params.cursor.as_deref(), limit)
        .await?;

    Ok(Json(ApiResponse::paginated(
        orders.into_iter().map(OrderResponse::from).collect(),
        next_cursor,
        limit,
    )))
}

// Router setup
pub fn order_routes() -> Router<AppState> {
    Router::new()
        .route("/orders", post(create_order).get(list_orders))
        // axum 0.8: `{id}` (a `:id` segment panics when the router is built)
        .route("/orders/{id}", get(get_order).put(update_order).delete(delete_order))
}
```

### Custom Axum Extractors
```rust
use axum::{extract::FromRequestParts, http::request::Parts};
use serde::Deserialize;
use uuid::Uuid;

#[derive(Clone, Copy, Debug)] // Clone: tenant_middleware also stores it in the request extensions
pub struct TenantId(pub Uuid);

/// Claims of a JWT the auth middleware has already verified (signature, expiry, audience) and
/// inserted into the request extensions.
#[derive(Clone, Debug, Deserialize)]
pub struct Claims {
    pub sub: Uuid,
    pub tenant_id: Uuid,        // the token's tenant
    #[serde(default)]
    pub tenant_ids: Vec<Uuid>,  // multi-tenant users only: tenants X-Tenant-ID may select from
}

impl Claims {
    /// The token's tenant, or one the X-Tenant-ID header SELECTS from the token's own list.
    /// A client header never grants a tenant on its own: anyone can send one.
    pub fn resolve_tenant(&self, requested: Option<&str>) -> Option<Uuid> {
        match requested {
            None => Some(self.tenant_id),
            Some(raw) => {
                let id = Uuid::parse_str(raw).ok()?;
                (id == self.tenant_id || self.tenant_ids.contains(&id)).then_some(id)
            }
        }
    }
}

// axum 0.8: FromRequestParts is a native async trait — no #[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for TenantId {
    type Rejection = DomainError;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let claims = parts
            .extensions
            .get::<Claims>() // inserted by the auth middleware only after the JWT verified
            .ok_or(DomainError::Unauthenticated)?;

        let requested = parts.headers.get("X-Tenant-ID").and_then(|v| v.to_str().ok());
        let tenant_id = claims.resolve_tenant(requested).ok_or(DomainError::Forbidden)?;

        Ok(TenantId(tenant_id))
    }
}

// Pagination params — cursor + limit only, never page numbers or offsets
#[derive(Debug, Deserialize)]
pub struct PaginationParams {
    pub cursor: Option<String>, // meta.pagination.next_cursor from the previous page
    pub limit: Option<i64>,
}
```

### Actix-web Patterns
```rust
use actix_web::{middleware, web, HttpResponse};
use uuid::Uuid;

// The same handler under actix-web. AppError (actix's ResponseError → the same envelope), AuthUser and
// AuthMiddleware (verifies the bearer token; the tenant comes from it) are in frameworks/actix-web.md.
async fn get_order(
    path: web::Path<Uuid>,
    user: AuthUser,
    service: web::Data<OrderService>,
) -> Result<HttpResponse, AppError> {
    let order = service.get_order(user.tenant_id, path.into_inner()).await?;
    Ok(HttpResponse::Ok().json(ApiResponse::success(OrderResponse::from(order))))
}

// App setup
fn configure_app(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api/v1")
            .wrap(middleware::Logger::default())
            .wrap(AuthMiddleware)
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
use std::time::Duration;

use axum::{error_handling::HandleErrorLayer, middleware, response::Response, BoxError, Router};
use tower::ServiceBuilder;
use tower_http::{cors::CorsLayer, trace::TraceLayer};
use tracing::Instrument;

fn app(state: AppState) -> Router {
    Router::new()
        .merge(order_routes())
        .merge(user_routes())
        .layer(
            ServiceBuilder::new()
                // first = outermost: runs the request inside REQUEST_ID.scope(..) so every envelope
                // (success meta and error body) carries the id it echoes as X-Request-Id — frameworks/axum.md
                .layer(middleware::from_fn(request_id_middleware))
                .layer(TraceLayer::new_for_http())
                // a request over 30s becomes the 503 UNAVAILABLE envelope (tower-http's TimeoutLayer
                // would answer an empty-bodied 408 instead)
                .layer(HandleErrorLayer::new(timeout_error))
                .timeout(Duration::from_secs(30))
                .layer(CorsLayer::permissive()) // tighten for production
                // verifies the JWT and inserts Claims — must come before tenant_middleware
                .layer(middleware::from_fn_with_state(state.clone(), auth_middleware))
                .layer(middleware::from_fn(tenant_middleware))
        )
        .with_state(state)
}

async fn timeout_error(err: BoxError) -> DomainError {
    // retryable: true lets a client retry; it still retries only idempotent requests (or ones that
    // carry an Idempotency-Key), since the timed-out write may have happened
    DomainError::Unavailable { service: "request handling", cause: anyhow::anyhow!("{err}") }
}

// Custom middleware function — the tenant comes from the verified Claims, never from a header alone
async fn tenant_middleware(
    mut req: axum::extract::Request,
    next: axum::middleware::Next,
) -> Result<Response, DomainError> {
    let claims = req.extensions().get::<Claims>().cloned().ok_or(DomainError::Unauthenticated)?;
    let requested = req.headers().get("X-Tenant-ID").and_then(|v| v.to_str().ok());
    let tenant_id = claims.resolve_tenant(requested).ok_or(DomainError::Forbidden)?; // header can only select

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
// Axum extracts it from the VERIFIED JWT claims before the handler runs

async fn create_order(
    State(state): State<AppState>,
    tenant: TenantId,              // from the verified token's claims (a header may only select among them)
    Json(request): Json<CreateOrderRequest>,
) -> Result<impl IntoResponse, DomainError> {
    // tenant.0 is the UUID — pass it through every layer
    let order = state.order_service.create_order(tenant.0, request).await?;
    Ok((StatusCode::CREATED, Json(ApiResponse::success(OrderResponse::from(order)))))
}
```

### Domain Types the Queries Map Into
```rust
// src/domain/mod.rs — entities (see Project Structure)
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// The Postgres enum `order_status` (migration below). `query_as!` needs the type hint
/// `status as "status: OrderStatus"` to read it and `status as OrderStatus` to bind it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, sqlx::Type)]
#[sqlx(type_name = "order_status", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum OrderStatus {
    Pending,
    Confirmed,
    Shipped,
    Cancelled,
}

#[derive(Debug, Clone)]
pub struct Order {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub status: OrderStatus,
    pub total_cents: i64, // money in integer minor units — never f32/f64
    pub created_at: DateTime<Utc>,
    pub version: i32, // optimistic lock
}

impl Order {
    pub fn new(id: Uuid, tenant_id: Uuid) -> Self {
        Self { id, tenant_id, status: OrderStatus::Pending, total_cents: 0, created_at: Utc::now(), version: 1 }
    }

    /// Pending → Confirmed; confirming anything else is a 409 CONFLICT.
    pub fn confirm(self) -> Result<Self, DomainError> {
        match self.status {
            OrderStatus::Pending => Ok(Self { status: OrderStatus::Confirmed, ..self }),
            _ => Err(DomainError::Conflict("Only a pending order can be confirmed.".into())),
        }
    }
}
```

### SQLx Queries with Tenant Filtering
```rust
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Utc};
use sqlx::{PgPool, Postgres, Transaction};
use uuid::Uuid;

/// A transaction for one tenant. The RLS policies on orders and inventory (migration below) read
/// app.current_tenant_id; set_config(.., true) sets it for THIS transaction only. Never at session
/// level (SET, or set_config(.., false)): the pool hands the connection to another request next, with
/// this tenant still set. Without the setting, every query on those tables errors.
pub async fn begin_tenant_tx(pool: &PgPool, tenant_id: Uuid) -> Result<Transaction<'static, Postgres>, DomainError> {
    let mut tx = pool.begin().await?;
    sqlx::query!("SELECT set_config('app.current_tenant_id', $1, true)", tenant_id.to_string())
        .fetch_one(&mut *tx)
        .await?;
    Ok(tx)
}

// EVERY query includes tenant_id — no exceptions. RLS is the second line of defence, not the first.
pub async fn find_by_id(
    pool: &PgPool,
    tenant_id: Uuid,
    order_id: Uuid,
) -> Result<Option<Order>, DomainError> {
    let mut tx = begin_tenant_tx(pool, tenant_id).await?;
    let order = sqlx::query_as!(
        Order,
        r#"
        SELECT id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version
        FROM orders
        WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
        "#,
        tenant_id,
        order_id,
    )
    .fetch_optional(&mut *tx)
    .await?;
    tx.commit().await?;

    Ok(order)
}

// Cursor (keyset) pagination with tenant isolation. The cursor is the last row's (created_at, id):
// rows that share a created_at are neither skipped nor repeated. Index: (tenant_id, created_at DESC, id DESC).
pub async fn list_paginated(
    pool: &PgPool,
    tenant_id: Uuid,
    cursor: Option<&str>, // meta.pagination.next_cursor of the previous page, opaque to clients
    limit: i64,           // already checked to be in 1..=100 by the handler
) -> Result<(Vec<Order>, Option<String>), DomainError> {
    let after = cursor.map(decode_cursor).transpose()?; // a bad cursor is a 400 before any query
    let mut tx = begin_tenant_tx(pool, tenant_id).await?;
    let mut orders = match after {
        Some((after_created_at, after_id)) => sqlx::query_as!(
            Order,
            r#"
            SELECT id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version
            FROM orders
            WHERE tenant_id = $1 AND deleted_at IS NULL AND (created_at, id) < ($2, $3)
            ORDER BY created_at DESC, id DESC
            LIMIT $4
            "#,
            tenant_id, after_created_at, after_id, limit + 1,
        ).fetch_all(&mut *tx).await?,
        None => sqlx::query_as!(
            Order,
            r#"
            SELECT id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version
            FROM orders
            WHERE tenant_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT $2
            "#,
            tenant_id, limit + 1,
        ).fetch_all(&mut *tx).await?,
    };
    tx.commit().await?;

    let has_more = orders.len() as i64 > limit;
    orders.truncate(limit as usize);
    let next_cursor = if has_more { orders.last().map(encode_cursor) } else { None };

    Ok((orders, next_cursor))
}

fn encode_cursor(last: &Order) -> String {
    URL_SAFE_NO_PAD.encode(format!("{}|{}", last.created_at.to_rfc3339(), last.id))
}

/// A tampered or garbled cursor is a 400 VALIDATION_FAILED on `cursor` — not a 500, not page one.
fn decode_cursor(cursor: &str) -> Result<(DateTime<Utc>, Uuid), DomainError> {
    let invalid = || DomainError::Validation(vec![FieldError::new("cursor", "invalid_cursor")]);
    let bytes = URL_SAFE_NO_PAD.decode(cursor).map_err(|_| invalid())?;
    let text = String::from_utf8(bytes).map_err(|_| invalid())?;
    let (created_at, id) = text.split_once('|').ok_or_else(invalid)?;
    let created_at = DateTime::parse_from_rfc3339(created_at).map_err(|_| invalid())?.with_timezone(&Utc);
    Ok((created_at, Uuid::parse_str(id).map_err(|_| invalid())?))
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

    pub async fn find_by_id(&self, tenant_id: Uuid, order_id: Uuid) -> Result<Option<Order>, DomainError> {
        find_by_id(&self.pool, tenant_id, order_id).await // the tenant-filtered query above
    }

    pub async fn save(&self, order: &Order) -> Result<Order, DomainError> {
        let mut tx = begin_tenant_tx(&self.pool, order.tenant_id).await?; // RLS WITH CHECK: the row's own tenant
        let saved = sqlx::query_as!(
            Order,
            r#"
            INSERT INTO orders (id, tenant_id, status, total_cents, version)
            VALUES ($1, $2, $3, $4, 1)
            RETURNING id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version
            "#,
            order.id,
            order.tenant_id,
            order.status as OrderStatus,
            order.total_cents,
        )
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;

        Ok(saved)
    }

    pub async fn update_with_optimistic_lock(
        &self,
        tenant_id: Uuid,
        order_id: Uuid,
        status: OrderStatus,
        expected_version: i32,
    ) -> Result<Order, DomainError> {
        let mut tx = begin_tenant_tx(&self.pool, tenant_id).await?;
        let result = sqlx::query_as!(
            Order,
            r#"
            UPDATE orders
            SET status = $1, version = version + 1, updated_at = NOW()
            WHERE tenant_id = $2 AND id = $3 AND version = $4 AND deleted_at IS NULL
            RETURNING id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version
            "#,
            status as OrderStatus,
            tenant_id,
            order_id,
            expected_version,
        )
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;

        match result {
            Some(order) => Ok(order),
            // No row: the order is gone (or is another tenant's — the same 404) or its version moved on
            None => match self.find_by_id(tenant_id, order_id).await? {
                Some(_) => Err(DomainError::Conflict("This order was changed by someone else. Reload it and try again.".into())),
                None => Err(DomainError::NotFound { resource: "Order", id: order_id }),
            },
        }
    }

    pub async fn soft_delete(&self, tenant_id: Uuid, order_id: Uuid) -> Result<(), DomainError> {
        let mut tx = begin_tenant_tx(&self.pool, tenant_id).await?;
        let rows = sqlx::query!(
            "UPDATE orders SET deleted_at = NOW() WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL",
            tenant_id,
            order_id,
        )
        .execute(&mut *tx)
        .await?
        .rows_affected();
        tx.commit().await?;

        if rows == 0 {
            return Err(DomainError::NotFound { resource: "Order", id: order_id });
        }
        Ok(())
    }
}
```

### Connection Pooling
```rust
use std::time::Duration;

use anyhow::Context;
use sqlx::postgres::{PgPool, PgPoolOptions};

pub async fn connect_pool(database_url: &str) -> anyhow::Result<PgPool> {
    PgPoolOptions::new()
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
        .connect(database_url)
        .await
        .context("failed to create connection pool")
}
```

### Transaction Support
```rust
pub async fn create_order_with_inventory(
    pool: &PgPool,
    tenant_id: Uuid,
    request: CreateOrderRequest,
) -> Result<Order, DomainError> {
    // All operations in one transaction, for one tenant (RLS: begin_tenant_tx above)
    let mut tx = begin_tenant_tx(pool, tenant_id).await?;

    let order = sqlx::query_as!(
        Order,
        r#"INSERT INTO orders (id, tenant_id, status, total_cents) VALUES ($1, $2, 'pending', $3)
           RETURNING id, tenant_id, status as "status: OrderStatus", total_cents, created_at, version"#,
        Uuid::new_v4(), tenant_id, request.total_cents,
    )
    .fetch_one(&mut *tx)
    .await?;

    for item in &request.items {
        let reserved = sqlx::query!(
            "UPDATE inventory SET quantity = quantity - $1 WHERE tenant_id = $2 AND sku = $3 AND quantity >= $1",
            item.quantity, tenant_id, item.sku,
        )
        .execute(&mut *tx)
        .await? // a database error stays a database error (500/503) — never relabelled as a conflict
        .rows_affected();

        // The guarded UPDATE matches no row when stock is short (or the SKU is unknown): that is not
        // an error from Postgres, so check it. Returning here drops `tx`, which rolls the order back.
        if reserved == 0 {
            return Err(DomainError::Conflict("Not enough stock for this order.".into()));
        }
    }

    tx.commit().await?;
    Ok(order)
}
```

### Migration Patterns
```bash
sqlx migrate add create_orders   # writes migrations/<timestamp>_create_orders.sql
sqlx migrate run                 # applies pending migrations to DATABASE_URL
cargo sqlx prepare               # writes .sqlx/ query metadata so CI builds offline (SQLX_OFFLINE=true)
```

```sql
-- migrations/20240115000000_create_orders.sql
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'shipped', 'cancelled');

CREATE TABLE orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,               -- the verified token's tenant
    status      order_status NOT NULL DEFAULT 'pending',
    total_cents BIGINT NOT NULL CHECK (total_cents >= 0), -- money in integer minor units (api/response-envelope.md)
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE INDEX idx_orders_tenant_status ON orders (tenant_id, status) WHERE deleted_at IS NULL;
-- the keyset list: WHERE tenant_id = $1 AND (created_at, id) < ($2, $3) ORDER BY created_at DESC, id DESC
CREATE INDEX idx_orders_tenant_created ON orders (tenant_id, created_at DESC, id DESC) WHERE deleted_at IS NULL;

CREATE TABLE inventory (
    tenant_id UUID NOT NULL,
    sku       TEXT NOT NULL,
    quantity  INTEGER NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (tenant_id, sku)
);

-- Tenant isolation in the database too (infrastructure/saas-tenancy-models.md): the app sets
-- app.current_tenant_id with set_config(..., true) inside each transaction.
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inventory
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- The migrator's policy (decision D-001): TO the table owner (the migrator) only, so migrations and seeds
-- reach every tenant without BYPASSRLS (RDS/Aurora has none) and without lifting FORCE. This is the first
-- migration, so it creates the helper; later migrations only call it (databases/postgres.md).
CREATE OR REPLACE FUNCTION app_grant_migrator(tbl regclass) RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
    owner_role name;
    pol        name;
BEGIN
    SELECT pg_get_userbyid(c.relowner), left(c.relname, 49) || '_migrator_all'
      INTO owner_role, pol
      FROM pg_class c WHERE c.oid = tbl;
    IF EXISTS (SELECT FROM pg_policy WHERE polrelid = tbl AND polname = pol) THEN
        EXECUTE format('ALTER POLICY %I ON %s TO %I', pol, tbl, owner_role);
    ELSE
        EXECUTE format('CREATE POLICY %I ON %s AS PERMISSIVE FOR ALL TO %I USING (true) WITH CHECK (true)',
                       pol, tbl, owner_role);
    END IF;
END
$fn$;
REVOKE ALL ON FUNCTION app_grant_migrator(regclass) FROM PUBLIC;
SELECT app_grant_migrator('orders');
SELECT app_grant_migrator('inventory');
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
        let mut mock_repo = MockOrderRepository::new();
        mock_repo.expect_save()
            .returning(|order| Ok(order.clone()));

        let service = OrderService::new(Arc::new(mock_repo));
        let result = service.create_order(TENANT_ID, valid_request()).await;

        assert!(result.is_ok());
        assert_eq!(result.unwrap().status, OrderStatus::Pending);
    }
}
```

### mockall for Mocking Traits
```rust
use async_trait::async_trait;
#[cfg(test)]
use mockall::automock;

// The service holds the repository as Arc<dyn OrderRepository>: a native `async fn` trait isn't
// dyn-compatible, so #[async_trait] stays. #[automock] goes first, and only in test builds
// (mockall is a dev-dependency).
#[cfg_attr(test, automock)]
#[async_trait]
pub trait OrderRepository: Send + Sync {
    async fn find_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Option<Order>, DomainError>;
    async fn save(&self, order: &Order) -> Result<Order, DomainError>;
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), DomainError>;
}

#[cfg(test)]
mod repository_mock_tests {
    use super::*;
    use mockall::predicate::eq;
    use std::sync::Arc;

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
}
```

### Test Fixtures and Factories
```rust
// Test helpers module
#[cfg(test)]
pub mod test_helpers {
    use super::*;
    use uuid::uuid;

    pub const TENANT_ID: Uuid = uuid!("00000000-0000-0000-0000-000000000001");
    pub const ORDER_ID: Uuid = uuid!("00000000-0000-0000-0000-0000000000a1");

    pub fn build_order(overrides: OrderOverrides) -> Order {
        Order {
            id: overrides.id.unwrap_or_else(Uuid::new_v4),
            tenant_id: overrides.tenant_id.unwrap_or(TENANT_ID),
            status: overrides.status.unwrap_or(OrderStatus::Pending),
            total_cents: overrides.total_cents.unwrap_or(10_000), // $100.00
            version: overrides.version.unwrap_or(1),
            created_at: overrides.created_at.unwrap_or_else(Utc::now),
        }
    }

    #[derive(Default)]
    pub struct OrderOverrides {
        pub id: Option<Uuid>,
        pub tenant_id: Option<Uuid>,
        pub status: Option<OrderStatus>,
        pub total_cents: Option<i64>,
        pub version: Option<i32>,
        pub created_at: Option<DateTime<Utc>>,
    }

    pub fn valid_request() -> CreateOrderRequest {
        CreateOrderRequest { total_cents: 10_000, items: vec![] }
    }

    // Usage:
    // let order = build_order(OrderOverrides { status: Some(OrderStatus::Confirmed), ..Default::default() });
}
```

### Integration Tests with testcontainers
```rust
// tests/integration/main.rs — integration tests link the crate as a library, so #[cfg(test)]
// helpers in src/ (test_helpers above) aren't visible here
// [dev-dependencies] testcontainers-modules = { version = "0.15", features = ["postgres"] }
use sqlx::PgPool;
use testcontainers_modules::{
    postgres::Postgres,
    testcontainers::{runners::AsyncRunner, ContainerAsync, ImageExt},
};
use uuid::Uuid;
use yourapp::{domain::Order, repositories::OrderRepository};

async fn setup_test_db() -> (PgPool, ContainerAsync<Postgres>) {
    // pin the server version production runs (the module's default tag is older)
    let container = Postgres::default().with_tag("17-alpine").start().await.expect("start postgres (is Docker running?)");
    let port = container.get_host_port_ipv4(5432).await.unwrap();
    let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/postgres");

    let pool = PgPool::connect(&url).await.unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();

    (pool, container) // the container is removed when this handle drops: keep it alive for the test
}

#[tokio::test]
async fn test_order_repository_crud() {
    let (pool, _container) = setup_test_db().await;
    let repo = OrderRepository::new(pool.clone());
    let tenant_id = Uuid::new_v4();

    // Create
    let order = Order::new(Uuid::new_v4(), tenant_id);
    let saved = repo.save(&order).await.unwrap();
    assert_eq!(saved.tenant_id, tenant_id);

    // Read — and another tenant can't (tenant_id is in every WHERE)
    let found = repo.find_by_id(tenant_id, saved.id).await.unwrap();
    assert!(found.is_some());
    assert!(repo.find_by_id(Uuid::new_v4(), saved.id).await.unwrap().is_none());

    // Soft delete
    repo.soft_delete(tenant_id, saved.id).await.unwrap();
    let found = repo.find_by_id(tenant_id, saved.id).await.unwrap();
    assert!(found.is_none()); // filtered by deleted_at IS NULL
}
```

---

## Performance

### Zero-Cost Abstractions
```rust
// Iterators are zero-cost — compiled to the same code as manual loops
fn confirmed_total_cents(orders: &[Order]) -> i64 {
    orders
        .iter()
        .filter(|o| o.status == OrderStatus::Confirmed)
        .map(|o| o.total_cents)
        .sum()
}

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
use std::collections::HashMap;
use std::sync::Arc;

use sqlx::PgPool;
use tokio::sync::{mpsc, RwLock};
use uuid::Uuid;

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

// mpsc channel for a background job queue — bounded, so a burst waits instead of growing memory
pub fn start_job_worker() -> mpsc::Sender<Job> {
    let (tx, mut rx) = mpsc::channel::<Job>(100);

    tokio::spawn(async move {
        while let Some(job) = rx.recv().await {
            process_job(job).await;
        }
    });
    tx
}

// Send jobs from handlers (waits while the queue is full; errors only once the worker has stopped)
pub async fn enqueue_order(tx: &mpsc::Sender<Job>, order_id: Uuid) -> anyhow::Result<()> {
    tx.send(Job::ProcessOrder(order_id)).await?;
    Ok(())
}
```

### Tokio Runtime Configuration
```rust
// Default: #[tokio::main] = a multi-threaded runtime with one worker thread per CPU core.
// For most services, the default is correct:
//     #[tokio::main]
//     async fn main() -> anyhow::Result<()> { run_server().await }

// Custom runtime for fine-tuning: build it in a plain fn main. Never inside #[tokio::main] —
// block_on there panics ("Cannot start a runtime from within a runtime").
fn main() -> anyhow::Result<()> {
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)        // limit worker threads
        .max_blocking_threads(64) // for spawn_blocking calls
        .enable_all()
        .build()?;

    runtime.block_on(run_server())
}

// CPU-bound work: use spawn_blocking to avoid blocking the async runtime
async fn hash_password(password: String) -> Result<String, DomainError> {
    tokio::task::spawn_blocking(move || {
        bcrypt::hash(password, 12).map_err(|e| DomainError::Internal(e.into()))
    })
    .await
    .map_err(|e| DomainError::Internal(e.into()))?
}
```

---

## Async Patterns

### tokio::select! for Racing Futures
```rust
use std::time::Duration;

use tokio::net::TcpListener;

// Idempotent reads only: the primary request may still complete after we give up on it
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
pub async fn run_server(listener: TcpListener, mut shutdown: tokio::sync::watch::Receiver<()>) {
    loop {
        tokio::select! {
            accepted = listener.accept() => match accepted {
                Ok((stream, _peer)) => {
                    tokio::spawn(handle_connection(stream));
                }
                // e.g. too many open files: log and keep accepting (an `Ok(..) = accept()` pattern would
                // instead disable this branch and stop accepting until shutdown)
                Err(e) => tracing::warn!(error = %e, "accept failed"),
            },
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
impl ProfileService {
    pub async fn fetch_user_profile(&self, tenant_id: Uuid, user_id: Uuid) -> Result<UserProfile, DomainError> {
        // Run all three queries concurrently; the first error cancels the other two
        let (user, orders, preferences) = tokio::try_join!(
            self.user_repo.find_by_id(tenant_id, user_id),
            self.order_repo.find_by_user(tenant_id, user_id),
            self.pref_repo.find_by_user(tenant_id, user_id),
        )?;

        let user = user.ok_or(DomainError::NotFound { resource: "User", id: user_id })?;

        Ok(UserProfile { user, orders, preferences })
    }
}
```

### Streaming with futures::Stream
```rust
use futures::stream::{self, StreamExt};

async fn process_batch(
    items: Vec<Item>,
    max_concurrent: usize,
) -> Vec<Result<ProcessedItem, DomainError>> {
    // buffer_unordered polls at most max_concurrent futures at once — that IS the limit, no
    // Semaphore needed. (Share an Arc<Semaphore> only to cap concurrency ACROSS calls or tasks,
    // e.g. all requests to one upstream.) Results arrive in completion order, not input order.
    stream::iter(items)
        .map(process_item)
        .buffer_unordered(max_concurrent)
        .collect()
        .await
}
```

### Graceful Shutdown
```rust
// With axum, prefer axum::serve(..).with_graceful_shutdown(..) (frameworks/axum.md): it stops
// accepting and waits for in-flight requests by itself. With a hand-rolled accept loop (run_server above):
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let pool = connect_pool(&std::env::var("DATABASE_URL").context("DATABASE_URL is not set")?).await?;
    let listener = TcpListener::bind("0.0.0.0:8080").await?;
    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(());
    let server = tokio::spawn(run_server(listener, shutdown_rx));

    // Listen for OS signals
    let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())?;
    tokio::select! {
        _ = tokio::signal::ctrl_c() => tracing::info!("received SIGINT"),
        _ = sigterm.recv() => tracing::info!("received SIGTERM"),
    }

    tracing::info!("initiating graceful shutdown");
    let _ = shutdown_tx.send(()); // run_server stops accepting
    server.await?;
    // Accepted connections run in their own tasks: give them a grace period (shorter than the
    // orchestrator's termination grace period), then exit anyway
    tokio::time::sleep(Duration::from_secs(10)).await;

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

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 SQL block parsed with libpg_query 17.7 and executed on PostgreSQL 17.11; 4 claims in the text proven on PostgreSQL 17.11.
