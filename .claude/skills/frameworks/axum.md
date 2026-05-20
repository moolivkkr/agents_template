# Axum framework patterns for Rust HTTP APIs.

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
        .layer(TraceLayer::new_for_http())
        .layer(middleware::from_fn(recovery_middleware))
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

// Query parameters: /widgets?page_size=20&cursor=abc
async fn list_widgets(Query(params): Query<ListParams>) -> impl IntoResponse { .. }

// JSON request body (automatically deserializes with serde)
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
        .ok_or(AppError::Unauthorized("missing authorization header".into()))?;

    let claims = state.jwt.verify(token)
        .map_err(|_| AppError::Unauthorized("invalid token".into()))?;

    req.extensions_mut().insert(claims);
    Ok(next.run(req).await)
}
```
- Use `middleware::from_fn` / `from_fn_with_state` for async middleware
- Insert values into request extensions for downstream handlers
- Tower layers (`ServiceBuilder`, `tower_http`) for cross-cutting concerns

## Error Handling (IntoResponse)
```rust
use axum::response::{IntoResponse, Response};
use axum::http::StatusCode;

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = self.status_code();
        let body = serde_json::json!({
            "error": {
                "code": self.error_code(),
                "message": self.user_message(),
                "details": self.details(),
            }
        });
        (status, axum::Json(body)).into_response()
    }
}
```
- Implement `IntoResponse` on your error type — Axum calls it automatically on `Err`
- Handler return type: `Result<impl IntoResponse, AppError>` enables `?` operator

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
}
```
- Use `tower::ServiceExt::oneshot` — no running server needed
- Build requests with `axum::http::Request::builder()`
- Parse response body with `axum::body::to_bytes`
