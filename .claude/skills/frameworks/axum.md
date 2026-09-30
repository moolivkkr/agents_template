# Axum framework patterns for Rust HTTP APIs.

> The Error Handling block and its bad-path test compile-checked 2026-09-30 and the test passes (tests/archetype-compile/rust/run.sh): rustc 1.98.1, axum 0.8.9. The other blocks are not checked yet.

## Router Setup
```rust
use axum::{
    Router,
    routing::{get, post, put, delete},
    middleware,
};
use std::sync::Arc;
use tower_http::trace::TraceLayer;

pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        .nest("/api/v1", api_routes(state.clone()))
        .fallback(|| async { AppError::NotFound("Resource") }) // unknown route → envelope, not an empty 404
        .layer(TraceLayer::new_for_http())
        .layer(middleware::from_fn(recovery_middleware))
        .layer(middleware::from_fn(request_id_middleware)) // added last = outermost (see Error Handling)
        .with_state(state)
}

fn api_routes(state: Arc<AppState>) -> Router<Arc<AppState>> {
    Router::new()
        .nest("/widgets", widget_routes())
        .nest("/users", user_routes())
        .route_layer(middleware::from_fn_with_state(state.clone(), auth_middleware))
}

fn widget_routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/", post(create_widget).get(list_widgets))
        .route("/{id}", get(get_widget).put(update_widget).delete(delete_widget))
}
```
- Use `Router::new()` — composable, tower-based
- Nest subrouters with `.nest("/prefix", sub_router)` for clean grouping
- Middleware via `.layer()` at any router level — applies to all routes below

## Extractors
```rust
use axum::extract::{Path, Query, Json, State, Extension};
use uuid::Uuid;

// Path parameters: /widgets/{id}
async fn get_widget(Path(id): Path<Uuid>) -> impl IntoResponse { .. }

// Query parameters: /widgets?limit=20&cursor=abc (cursor pagination only)
async fn list_widgets(Query(params): Query<ListParams>) -> impl IntoResponse { .. }

// JSON request body (automatically deserializes with serde). In real handlers use the rejection-mapping
// AppJson/AppQuery/AppPath wrappers (Error Handling below), or a bad body answers in plain text, not the envelope.
async fn create_widget(Json(input): Json<CreateInput>) -> impl IntoResponse { .. }

// Shared state (Arc<AppState>)
async fn handler(State(state): State<Arc<AppState>>) -> impl IntoResponse { .. }

// Multiple extractors — order matters: State/Path/Query before body (Json)
async fn update(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(input): Json<UpdateInput>,
) -> impl IntoResponse { .. }
```
- Extractors run left-to-right; body-consuming extractors (Json) must be last
- `State` wraps shared application state — always use `Arc<AppState>` for thread safety
- Implement `FromRequestParts` for custom extractors (e.g., `AuthUser`)

## Middleware (Tower Layers)
```rust
use axum::{extract::Request, middleware::Next, response::Response};

async fn auth_middleware(
    State(state): State<Arc<AppState>>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let token = req.headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(AppError::Unauthenticated)?;

    let claims = state.jwt.verify(token)
        .map_err(|_| AppError::Unauthenticated)?; // why it failed goes to a debug log, not the client

    req.extensions_mut().insert(claims);
    Ok(next.run(req).await)
}
```
- Use `middleware::from_fn` / `from_fn_with_state` for async middleware
- Insert values into request extensions for downstream handlers
- Tower layers (`ServiceBuilder`, `tower_http`) for cross-cutting concerns

## Error Handling (IntoResponse)
Every error body is the envelope in `api/response-envelope.md`:
`{"error": {code, message, details?, request_id, retryable}}` — no `data`, no source-error text.
```rust
use axum::{
    extract::{rejection::{JsonRejection, PathRejection, QueryRejection}, FromRequest, FromRequestParts, Request},
    http::{header, HeaderValue, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde::Serialize;

/// One error.details[] entry: stable lower_snake `code`, fixed catalog `message`.
#[derive(Debug, Serialize)]
pub struct FieldError {
    pub field: String,
    pub code: &'static str,
    pub message: &'static str,
}

// Display (#[error]) is log text only — the body is built from parts()
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("malformed request")] MalformedRequest,
    #[error("validation failed: {0:?}")] Validation(Vec<FieldError>),
    #[error("unauthenticated")] Unauthenticated,
    #[error("forbidden")] Forbidden,
    #[error("{0} not found")] NotFound(&'static str),
    #[error("conflict: {0}")] Conflict(String),          // user-safe text
    #[error("business rule: {0}")] BusinessRule(String), // user-safe text
    #[error("rate limited")] RateLimited { retry_after_secs: u64 },
    #[error("unavailable: {0:#}")] Unavailable(anyhow::Error),
    #[error("internal: {0:#}")] Internal(anyhow::Error),
}

impl AppError {
    /// (status, code, user-safe message, retryable) — exactly the table in api/response-envelope.md
    fn parts(&self) -> (StatusCode, &'static str, String, bool) {
        match self {
            Self::MalformedRequest => (StatusCode::BAD_REQUEST, "MALFORMED_REQUEST", "The request could not be read.".into(), false),
            Self::Validation(_) => (StatusCode::BAD_REQUEST, "VALIDATION_FAILED", "Some fields are invalid.".into(), false),
            Self::Unauthenticated => (StatusCode::UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.".into(), false),
            Self::Forbidden => (StatusCode::FORBIDDEN, "FORBIDDEN", "You don't have permission to do this.".into(), false),
            // also for another tenant's object — never 403, don't confirm it exists
            Self::NotFound(resource) => (StatusCode::NOT_FOUND, "NOT_FOUND", format!("{resource} not found."), false),
            Self::Conflict(msg) => (StatusCode::CONFLICT, "CONFLICT", msg.clone(), false),
            Self::BusinessRule(msg) => (StatusCode::UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION", msg.clone(), false),
            Self::RateLimited { .. } => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMITED", "Too many requests. Try again shortly.".into(), true),
            Self::Unavailable(_) => (StatusCode::SERVICE_UNAVAILABLE, "UNAVAILABLE", "The service is temporarily unavailable.".into(), true),
            Self::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL", "Something went wrong.".into(), false),
        }
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, message, retryable) = self.parts();
        let request_id = REQUEST_ID.try_with(Clone::clone).unwrap_or_default();
        if status.is_server_error() {
            // the cause is logged under the same request_id — never serialized
            tracing::error!(%request_id, code, error = %self, "request failed");
        }
        let mut error = serde_json::json!({
            "code": code, "message": message, "request_id": request_id, "retryable": retryable,
        });
        if let Self::Validation(details) = &self {
            error["details"] = serde_json::json!(details);
        }
        let mut res = (status, axum::Json(serde_json::json!({ "error": error }))).into_response();
        match &self {
            Self::RateLimited { retry_after_secs } => {
                res.headers_mut().insert(header::RETRY_AFTER, HeaderValue::from(*retry_after_secs));
            }
            Self::Unavailable(_) => {
                res.headers_mut().insert(header::RETRY_AFTER, HeaderValue::from_static("5"));
            }
            Self::Unauthenticated => {
                res.headers_mut().insert(header::WWW_AUTHENTICATE, HeaderValue::from_static("Bearer"));
            }
            _ => {}
        }
        res
    }
}

tokio::task_local! {
    /// The current request's id; set by request_id_middleware and equal to the X-Request-Id header.
    pub static REQUEST_ID: String;
}

// Outermost layer: take or generate the id, run the whole request inside the scope (so handler,
// extractor and middleware errors all see it), and echo it on the response.
pub async fn request_id_middleware(req: Request, next: Next) -> Response {
    let id = req.headers().get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let mut res = REQUEST_ID.scope(id.clone(), next.run(req)).await;
    if let Ok(value) = HeaderValue::from_str(&id) {
        res.headers_mut().insert("x-request-id", value);
    }
    res
}

// Axum's built-in rejections answer in plain text (a JSON shape error is even a 422). Wrap the extractors
// so every rejection becomes an AppError and therefore the envelope (axum "macros" feature).
#[derive(FromRequest)]
#[from_request(via(axum::Json), rejection(AppError))]
pub struct AppJson<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Query), rejection(AppError))]
pub struct AppQuery<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Path), rejection(AppError))]
pub struct AppPath<T>(pub T);

// serde's rejection text goes to a debug log, never to the client
impl From<JsonRejection> for AppError {
    fn from(rejection: JsonRejection) -> Self {
        // syntax, shape and content-type failures: 400 MALFORMED_REQUEST. Field rules (e.g. the
        // validator crate) produce Validation(details) → 400 VALIDATION_FAILED.
        tracing::debug!(error = %rejection.body_text(), "json body rejected");
        Self::MalformedRequest
    }
}

impl From<QueryRejection> for AppError {
    fn from(rejection: QueryRejection) -> Self {
        tracing::debug!(error = %rejection.body_text(), "query rejected");
        Self::MalformedRequest
    }
}

impl From<PathRejection> for AppError {
    fn from(rejection: PathRejection) -> Self {
        tracing::debug!(error = %rejection.body_text(), "path rejected");
        // /widgets/not-a-uuid: the client sent a malformed id → 400 VALIDATION_FAILED on `id`, the same
        // status and code as error-handling-rust.md (not a 404)
        Self::Validation(vec![FieldError { field: "id".into(), code: "invalid_format", message: "Must be a valid ID." }])
    }
}
```
- Implement `IntoResponse` on your error type — Axum calls it automatically on `Err`
- Handler return type: `Result<impl IntoResponse, AppError>` enables `?` operator
- Success bodies are `{"data": …, "meta": {"request_id": …}}`; lists add `meta.pagination`
  (`next_cursor`, `has_more`, `limit`) — the `ApiResponse` type in `languages/rust.md`
- `request_id_middleware` must be the outermost layer, so every body's `request_id` matches `X-Request-Id`

## State Management
```rust
pub struct AppState {
    pub db: sqlx::PgPool,
    pub redis: deadpool_redis::Pool,
    pub jwt: JwtService,
    pub config: AppConfig,
}

// In main.rs:
let state = Arc::new(AppState {
    db: sqlx::PgPool::connect(&config.database_url).await?,
    redis: deadpool_redis::Config::from_url(&config.redis_url).create_pool(None)?,
    jwt: JwtService::new(&config.jwt_secret),
    config,
});
let app = build_router(state);
```
- `Arc<AppState>` is the standard pattern — thread-safe shared ownership
- All dependencies live in `AppState` — no globals, fully testable

## Graceful Shutdown
```rust
use tokio::signal;

let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
tracing::info!("listening on {}", listener.local_addr()?);
axum::serve(listener, app)
    .with_graceful_shutdown(shutdown_signal())
    .await?;

async fn shutdown_signal() {
    let ctrl_c = signal::ctrl_c();
    let mut sigterm = signal::unix::signal(signal::unix::SignalKind::terminate())
        .expect("failed to register SIGTERM handler");
    tokio::select! {
        _ = ctrl_c => tracing::info!("received Ctrl+C"),
        _ = sigterm.recv() => tracing::info!("received SIGTERM"),
    }
}
```

## Testing with axum::test
```rust
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt; // for `oneshot`

#[tokio::test]
async fn test_get_widget() {
    let state = Arc::new(test_app_state().await);
    let app = build_router(state);

    let req = Request::builder()
        .uri("/api/v1/widgets/some-uuid")
        .header("authorization", "Bearer test-token")
        .body(Body::empty())
        .unwrap();

    let resp = app.oneshot(req).await.unwrap();
    assert_eq!(resp.status(), StatusCode::OK);

    let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert!(json["data"]["id"].is_string());
    assert!(json["meta"]["request_id"].is_string()); // envelope: data + meta.request_id
}
```
A bad path parameter is a 400 envelope, not axum's plain-text rejection (same module as the error
handling above):

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request, routing::get, Router};
    use tower::ServiceExt; // for `oneshot`

    #[tokio::test]
    async fn test_bad_path_param_is_400_validation_failed() {
        let app = Router::new()
            .route("/widgets/{id}", get(|AppPath(id): AppPath<uuid::Uuid>| async move { id.to_string() }))
            .layer(axum::middleware::from_fn(request_id_middleware));

        let req = Request::builder().uri("/widgets/not-a-uuid").body(Body::empty()).unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::BAD_REQUEST);

        let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["error"]["code"], "VALIDATION_FAILED");
        assert_eq!(json["error"]["details"][0]["field"], "id");
        assert!(json["error"]["request_id"].as_str().is_some_and(|id| !id.is_empty()));
    }
}
```
- Use `tower::ServiceExt::oneshot` — no running server needed
- Build requests with `axum::http::Request::builder()`
- Parse response body with `axum::body::to_bytes`
