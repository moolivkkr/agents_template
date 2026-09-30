# Actix-web framework patterns for Rust HTTP APIs.

## App & HttpServer Setup
```rust
use actix_web::{web, App, HttpServer, middleware};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let db_pool = PgPool::connect(&std::env::var("DATABASE_URL").unwrap())
        .await
        .expect("failed to connect to database");

    let app_state = web::Data::new(AppState {
        db: db_pool,
        jwt: JwtService::new(&config.jwt_secret),
        config: config.clone(),
    });

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(middleware::Logger::default())
            .wrap(middleware::Compress::default())
            .configure(api_config)
    })
    .bind(("0.0.0.0", 8080))?
    .workers(num_cpus::get())
    .run()
    .await
}
```
- `HttpServer::new` takes a factory closure — called once per worker thread
- `App::new()` is the per-worker application builder
- `.app_data()` shares state across handlers via `web::Data<T>` (internally `Arc<T>`)
- `.configure(fn)` modularizes route registration

## Route Definition
```rust
fn api_config(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api/v1")
            .service(
                web::resource("/widgets")
                    .route(web::post().to(create_widget))
                    .route(web::get().to(list_widgets))
            )
            .service(
                web::resource("/widgets/{id}")
                    .route(web::get().to(get_widget))
                    .route(web::put().to(update_widget))
                    .route(web::delete().to(delete_widget))
            )
            .wrap(auth_middleware())
    );
}
```
- `web::scope` groups routes under a prefix
- `web::resource` defines a single endpoint with multiple HTTP methods
- `.wrap()` applies middleware to a scope or resource
- Use `web::ServiceConfig` to split route registration across modules

## Extractors
```rust
use actix_web::{web, HttpRequest, HttpResponse};
use serde::Deserialize;
use uuid::Uuid;

// Path parameters: /widgets/{id}
async fn get_widget(path: web::Path<Uuid>) -> HttpResponse {
    let id = path.into_inner();
    // ...
}

// Query parameters: /widgets?limit=20&cursor=abc (cursor pagination only)
#[derive(Deserialize)]
struct ListParams {
    limit: Option<i64>,     // clamp to 1..=100; echoed as meta.pagination.limit
    cursor: Option<String>, // meta.pagination.next_cursor from the previous page
}
async fn list_widgets(query: web::Query<ListParams>) -> HttpResponse {
    let params = query.into_inner();
    // ...
}

// JSON request body (auto-deserialized via serde)
async fn create_widget(body: web::Json<CreateInput>) -> HttpResponse {
    let input = body.into_inner();
    // ...
}

// Shared application state
async fn handler(state: web::Data<AppState>) -> HttpResponse {
    let db = &state.db;
    // ...
}

// Multiple extractors — order does not matter (unlike Axum)
async fn update_widget(
    state: web::Data<AppState>,
    path: web::Path<Uuid>,
    body: web::Json<UpdateInput>,
) -> HttpResponse {
    // ...
}
```
- Extractors implement `FromRequest` trait — create custom extractors for auth context
- `web::Data<T>` wraps `Arc<T>` — zero-cost cloning for shared state
- `web::Json` validates Content-Type and deserializes automatically
- Failed extraction returns actix's plain-text error by default — set the `JsonConfig`/`QueryConfig`/`PathConfig`
  error handlers (JSON Configuration below) so it becomes the envelope

## Custom Extractor (AuthUser)
```rust
use actix_web::{dev::Payload, FromRequest, HttpRequest};
use std::future::{Ready, ready};

pub struct AuthUser {
    pub user_id: Uuid,
    pub tenant_id: Uuid,
    pub roles: Vec<String>,
}

impl FromRequest for AuthUser {
    type Error = AppError; // ResponseError → the envelope (ErrorUnauthorized would send plain text)
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        let extensions = req.extensions();
        match extensions.get::<AuthUser>() {
            Some(user) => ready(Ok(AuthUser {
                user_id: user.user_id,
                tenant_id: user.tenant_id,
                roles: user.roles.clone(),
            })),
            None => ready(Err(AppError::Unauthenticated)),
        }
    }
}
```
- Custom extractors enable `async fn handler(user: AuthUser)` signatures
- Use request extensions to pass data from middleware to handlers

## Middleware
```rust
use actix_web::middleware::Logger;
use actix_cors::Cors;

// Built-in logger
App::new()
    .wrap(Logger::new("%a %r %s %b %Dms"))

// CORS
App::new()
    .wrap(
        Cors::default()
            .allowed_origin("https://app.example.com")
            .allowed_methods(vec!["GET", "POST", "PUT", "DELETE"])
            .allowed_headers(vec!["Authorization", "Content-Type"])
            .max_age(3600)
    )

// Custom middleware using wrap_fn
App::new()
    .wrap_fn(|req, srv| {
        let start = std::time::Instant::now();
        let fut = srv.call(req);
        async move {
            let res = fut.await?;
            let elapsed = start.elapsed();
            tracing::info!(latency_ms = elapsed.as_millis(), "request completed");
            Ok(res)
        }
    })
```

## Custom Auth Middleware
```rust
use actix_web::dev::{Service, ServiceRequest, ServiceResponse, Transform};
use std::future::{Future, Ready, ready};
use std::pin::Pin;

pub struct AuthMiddleware;

impl<S, B> Transform<S, ServiceRequest> for AuthMiddleware
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = actix_web::Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = actix_web::Error;
    type Transform = AuthMiddlewareService<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(AuthMiddlewareService { service }))
    }
}

pub struct AuthMiddlewareService<S> {
    service: S,
}

impl<S, B> Service<ServiceRequest> for AuthMiddlewareService<S>
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = actix_web::Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = actix_web::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>>>>;

    fn poll_ready(&self, ctx: &mut core::task::Context<'_>) -> core::task::Poll<Result<(), Self::Error>> {
        self.service.poll_ready(ctx)
    }

    fn call(&self, req: ServiceRequest) -> Self::Future {
        let token = req.headers()
            .get("Authorization")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.strip_prefix("Bearer "));

        // Validate token and insert AuthUser into extensions
        // ...

        let fut = self.service.call(req);
        Box::pin(async move { fut.await })
    }
}
```
- Actix middleware uses the `Transform` + `Service` traits from Tower-like patterns
- For simpler middleware, prefer `wrap_fn` or `from_fn` helpers

## Error Handling (ResponseError trait)
Every error body is the envelope in `api/response-envelope.md`:
`{"error": {code, message, details?, request_id, retryable}}` — no `data`, no source-error text.
```rust
use actix_web::{
    dev::{Service, ServiceResponse},
    http::{header::{self, HeaderName, HeaderValue}, StatusCode},
    HttpResponse, ResponseError,
};
use serde::Serialize;
use std::fmt;

/// One error.details[] entry: stable lower_snake `code`, fixed catalog `message`.
#[derive(Debug, Serialize)]
pub struct FieldError {
    pub field: String,
    pub code: &'static str,
    pub message: &'static str,
}

#[derive(Debug)]
pub enum AppError {
    MalformedRequest,                // 400: unparseable JSON, wrong content type, body too large
    Validation(Vec<FieldError>),     // 400: details[] lists the fields
    Unauthenticated,                 // 401
    Forbidden,                       // 403: authenticated, not allowed
    NotFound(&'static str),          // 404: resource name — also another tenant's object (never 403)
    Conflict(String),                // 409: user-safe text
    BusinessRule(String),            // 422: user-safe text
    RateLimited { retry_after_secs: u64 }, // 429
    Unavailable(anyhow::Error),      // 503: a dependency failed/timed out — cause is logged, not sent
    Internal(anyhow::Error),         // 500: cause is logged, not sent
}

// Display is server-side log text. error_response() never uses it.
impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unavailable(e) => write!(f, "dependency unavailable: {e:#}"),
            Self::Internal(e) => write!(f, "internal error: {e:#}"),
            other => write!(f, "{other:?}"),
        }
    }
}

impl AppError {
    /// (status, code, user-safe message, retryable) — exactly the table in api/response-envelope.md
    fn parts(&self) -> (StatusCode, &'static str, String, bool) {
        match self {
            Self::MalformedRequest => (StatusCode::BAD_REQUEST, "MALFORMED_REQUEST", "The request could not be read.".into(), false),
            Self::Validation(_) => (StatusCode::BAD_REQUEST, "VALIDATION_FAILED", "Some fields are invalid.".into(), false),
            Self::Unauthenticated => (StatusCode::UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.".into(), false),
            Self::Forbidden => (StatusCode::FORBIDDEN, "FORBIDDEN", "You don't have permission to do this.".into(), false),
            Self::NotFound(resource) => (StatusCode::NOT_FOUND, "NOT_FOUND", format!("{resource} not found."), false),
            Self::Conflict(msg) => (StatusCode::CONFLICT, "CONFLICT", msg.clone(), false),
            Self::BusinessRule(msg) => (StatusCode::UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION", msg.clone(), false),
            Self::RateLimited { .. } => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMITED", "Too many requests. Try again shortly.".into(), true),
            Self::Unavailable(_) => (StatusCode::SERVICE_UNAVAILABLE, "UNAVAILABLE", "The service is temporarily unavailable.".into(), true),
            Self::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL", "Something went wrong.".into(), false),
        }
    }
}

impl ResponseError for AppError {
    fn status_code(&self) -> StatusCode {
        self.parts().0
    }

    fn error_response(&self) -> HttpResponse {
        let (status, code, message, retryable) = self.parts();
        let request_id = REQUEST_ID.try_with(Clone::clone).unwrap_or_default();
        if status.is_server_error() {
            tracing::error!(%request_id, code, error = %self, "request failed"); // the cause: logs only
        }
        let mut error = serde_json::json!({
            "code": code, "message": message, "request_id": request_id, "retryable": retryable,
        });
        if let Self::Validation(details) = self {
            error["details"] = serde_json::json!(details);
        }
        let mut res = HttpResponse::build(status);
        match self {
            Self::RateLimited { retry_after_secs } => {
                res.insert_header((header::RETRY_AFTER, HeaderValue::from(*retry_after_secs)));
            }
            Self::Unavailable(_) => {
                res.insert_header((header::RETRY_AFTER, HeaderValue::from_static("5")));
            }
            Self::Unauthenticated => {
                res.insert_header((header::WWW_AUTHENTICATE, HeaderValue::from_static("Bearer")));
            }
            _ => {}
        }
        res.json(serde_json::json!({ "error": error }))
    }
}

tokio::task_local! {
    /// The current request's id; set by the request-id middleware and equal to the X-Request-Id header.
    pub static REQUEST_ID: String;
}

// Request-id middleware — register it LAST (outermost). Inner errors are rendered inside its scope,
// so every envelope carries the same id the response echoes as X-Request-Id.
App::new()
    // ... other .wrap(...) calls first ...
    .wrap_fn(|req, srv| {
        let id = req.headers().get("x-request-id")
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned)
            .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
        let http_req = req.request().clone();
        let fut = srv.call(req);
        REQUEST_ID.scope(id.clone(), async move {
            let mut res = match fut.await {
                Ok(res) => res.map_into_boxed_body(),
                Err(err) => ServiceResponse::from_err(err, http_req), // error_response() runs here, in scope
            };
            if let Ok(value) = HeaderValue::from_str(&id) {
                res.headers_mut().insert(HeaderName::from_static("x-request-id"), value);
            }
            Ok::<_, actix_web::Error>(res)
        })
    })
```
- Implement `ResponseError` on your error type — Actix calls it automatically on `Err`
- Handler return type: `Result<HttpResponse, AppError>` enables `?` operator
- Never expose internal error details to clients — no `Display`/source text in any body, 4xx or 5xx
- Success bodies are `{"data": …, "meta": {"request_id": …}}`; lists add `meta.pagination`
  (`next_cursor`, `has_more`, `limit`) — the `ApiResponse` type in `languages/rust.md`

## Connection Pooling
```rust
use deadpool_postgres::{Config, Pool, Runtime};
use tokio_postgres::NoTls;

// deadpool (async, preferred for Actix)
fn create_pool(database_url: &str) -> Pool {
    let mut cfg = Config::new();
    cfg.url = Some(database_url.to_string());
    cfg.pool = Some(deadpool_postgres::PoolConfig {
        max_size: 50,
        timeouts: deadpool_postgres::Timeouts {
            wait: Some(Duration::from_secs(5)),
            create: Some(Duration::from_secs(5)),
            recycle: Some(Duration::from_secs(30)),
        },
        ..Default::default()
    });
    cfg.create_pool(Some(Runtime::Tokio1), NoTls).unwrap()
}

// r2d2 (sync — use only with web::block for CPU-bound work)
use r2d2_postgres::{postgres::NoTls, PostgresConnectionManager};

fn create_sync_pool(database_url: &str) -> r2d2::Pool<PostgresConnectionManager<NoTls>> {
    let manager = PostgresConnectionManager::new(database_url.parse().unwrap(), NoTls);
    r2d2::Pool::builder()
        .max_size(20)
        .min_idle(Some(5))
        .build(manager)
        .unwrap()
}
```
- Prefer `deadpool` or `sqlx` for async connection pooling with Actix
- Use `r2d2` only when wrapping sync libraries with `web::block()`
- Always set `max_size` explicitly — never use unlimited connections

## Testing with actix-rt
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::{test, App, web};

    #[actix_rt::test]
    async fn test_get_widget() {
        let state = web::Data::new(test_app_state().await);
        let app = test::init_service(
            App::new()
                .app_data(state.clone())
                .configure(api_config)
        ).await;

        let req = test::TestRequest::get()
            .uri("/api/v1/widgets/some-uuid")
            .insert_header(("Authorization", "Bearer test-token"))
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), StatusCode::OK);

        let body: serde_json::Value = test::read_body_json(resp).await;
        assert!(body["data"]["id"].is_string());
        assert!(body["meta"]["request_id"].is_string()); // envelope: data + meta.request_id
    }

    #[actix_rt::test]
    async fn test_create_widget() {
        let state = web::Data::new(test_app_state().await);
        let app = test::init_service(
            App::new()
                .app_data(state.clone())
                .configure(api_config)
        ).await;

        let input = serde_json::json!({
            "name": "New Widget",
            "description": "Test"
        });

        let req = test::TestRequest::post()
            .uri("/api/v1/widgets")
            .set_json(&input)
            .insert_header(("Authorization", "Bearer test-token"))
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), StatusCode::CREATED);
    }
}
```
- Use `actix_rt::test` macro for async test functions
- `test::init_service` builds a test application instance
- `test::TestRequest` constructs requests with fluent API
- `test::call_service` sends request without starting a real HTTP server
- `test::read_body_json` deserializes response body

## JSON Configuration
```rust
// Customize extractor failures globally: each becomes an AppError, so the body is the envelope.
// serde's text goes to a debug log — never into the message.
App::new()
    .app_data(
        web::JsonConfig::default()
            .limit(1_048_576) // 1MB body limit
            .error_handler(|err, _req| {
                // bad syntax, wrong shape, wrong content type, too large → 400 MALFORMED_REQUEST
                tracing::debug!(error = %err, "json body rejected");
                AppError::MalformedRequest.into()
            })
    )
    .app_data(
        web::QueryConfig::default().error_handler(|err, _req| {
            tracing::debug!(error = %err, "query rejected");
            AppError::MalformedRequest.into()
        })
    )
    .app_data(
        web::PathConfig::default().error_handler(|err, _req| {
            tracing::debug!(error = %err, "path rejected");
            AppError::NotFound("Resource").into() // /widgets/not-a-uuid can't name an existing resource
        })
    )
```

## Rules
- Use `web::Data<T>` for shared state — it wraps `Arc<T>` internally
- Never use `.unwrap()` in handlers — return `Result<HttpResponse, AppError>` and use `?`
- Implement `ResponseError` on your error type for automatic HTTP error mapping — it writes the envelope
  (`api/response-envelope.md`), and extractor failures map to `AppError` via the `*Config` error handlers
- Use `deadpool` or `sqlx` for async connection pooling — `r2d2` is sync only
- `web::block()` for CPU-bound work — offloads to thread pool, prevents blocking the event loop
- Custom extractors via `FromRequest` — never parse auth headers manually in every handler
- Use `actix_cors` crate for CORS — never implement CORS manually
- `JsonConfig` must set body size limit — never accept unbounded request bodies
- Test with `actix_web::test` module — no real server needed for unit tests
