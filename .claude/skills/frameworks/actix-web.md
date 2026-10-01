# Actix-web framework patterns for Rust HTTP APIs.

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, actix-web 4.15.0, actix-cors 0.7.2, deadpool-postgres 0.14.2, r2d2_postgres 0.18.2, jsonwebtoken 11.1.0, with languages/rust.md's ApiResponse. Both tests run and pass (against stub widget handlers); harness tests on top: a missing, forged, expired, wrong-issuer or wrong-audience token is a 401 envelope with the echoed request id, a malformed id a 400 on `id`, a malformed body a 400 MALFORMED_REQUEST.

## App & HttpServer Setup
```rust
use actix_web::{middleware, web, App, HttpServer};
use sqlx::PgPool;

/// Shared by every worker; handlers take `web::Data<AppState>`.
pub struct AppState {
    pub db: PgPool,
    pub jwt: JwtService, // verifies bearer tokens (Custom Auth Middleware below)
    pub config: AppConfig,
}

#[actix_web::main]
async fn main() -> anyhow::Result<()> {
    // Required settings come from the environment; a missing one fails startup — no default secrets
    let config = AppConfig::from_env()?;
    let db_pool = PgPool::connect(&config.database_url).await?;

    let app_state = web::Data::new(AppState {
        db: db_pool,
        jwt: JwtService::new(&config.jwt_secret, &config.jwt_issuer, &config.jwt_audience),
        config: config.clone(),
    });

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            // extractor failures become the envelope (JSON Configuration below)
            .app_data(json_config())
            .app_data(query_config())
            .app_data(path_config())
            .wrap(middleware::Compress::default())
            .wrap(access_log()) // Middleware below
            .wrap(cors())
            .wrap(middleware::from_fn(request_id)) // added last = outermost (Error Handling below)
            .configure(api_config)
    })
    .bind(("0.0.0.0", 8080))?
    .workers(num_cpus::get())
    .run()
    .await?;
    Ok(())
}
```
- `HttpServer::new` takes a factory closure — called once per worker thread
- `App::new()` is the per-worker application builder
- `.app_data()` shares state across handlers via `web::Data<T>` (internally `Arc<T>`)
- `.configure(fn)` modularizes route registration
- `.wrap()` order: the LAST call is the OUTERMOST layer

## Route Definition
```rust
pub fn api_config(cfg: &mut web::ServiceConfig) {
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
            .wrap(AuthMiddleware) // every route in the scope needs a verified bearer token
    );
}
```
- `web::scope` groups routes under a prefix
- `web::resource` defines a single endpoint with multiple HTTP methods
- `.wrap()` applies middleware to a scope or resource
- Use `web::ServiceConfig` to split route registration across modules

## Extractors
```rust
use actix_web::{web, HttpResponse};
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
    limit: Option<i64>,     // default 20; outside 1..=100 is a 400 VALIDATION_FAILED on `limit` — never clamped
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
use std::future::{ready, Ready};

use actix_web::{dev::Payload, FromRequest, HttpMessage, HttpRequest};
use uuid::Uuid;

/// Inserted by AuthMiddleware only after the bearer token verified; the tenant comes from the token.
#[derive(Clone, Debug)]
pub struct AuthUser {
    pub user_id: Uuid,
    pub tenant_id: Uuid,
    pub roles: Vec<String>,
}

impl FromRequest for AuthUser {
    type Error = AppError; // ResponseError → the envelope (ErrorUnauthorized would send plain text)
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        ready(req.extensions().get::<AuthUser>().cloned().ok_or(AppError::Unauthenticated))
    }
}
```
- Custom extractors enable `async fn handler(user: AuthUser)` signatures
- Use request extensions to pass data from middleware to handlers

## Middleware
```rust
use actix_cors::Cors;
use actix_web::{
    body::MessageBody,
    dev::{ServiceRequest, ServiceResponse},
    middleware::{Logger, Next},
};

// Built-in logger: .wrap(access_log())
pub fn access_log() -> Logger {
    Logger::new("%a %r %s %b %Dms")
}

// CORS: an explicit allow-list — .wrap(cors())
pub fn cors() -> Cors {
    Cors::default()
        .allowed_origin("https://app.example.com")
        .allowed_methods(vec!["GET", "POST", "PUT", "DELETE"])
        .allowed_headers(vec!["Authorization", "Content-Type"])
        .max_age(3600)
}

// Custom middleware as an async fn: .wrap(middleware::from_fn(timing))
pub async fn timing(
    req: ServiceRequest,
    next: Next<impl MessageBody>,
) -> Result<ServiceResponse<impl MessageBody>, actix_web::Error> {
    let start = std::time::Instant::now();
    let res = next.call(req).await?;
    tracing::info!(latency_ms = start.elapsed().as_millis() as u64, status = res.status().as_u16(), "request completed");
    Ok(res)
}
```

## Custom Auth Middleware
```rust
use std::future::{ready, Future, Ready};
use std::pin::Pin;

use actix_web::body::EitherBody;
use actix_web::dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform};
use actix_web::{web, HttpMessage};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::Deserialize;
use uuid::Uuid;

/// Verifies bearer tokens: HS256 signature, exp, iss and aud. Built once at startup from config.
pub struct JwtService {
    key: DecodingKey,
    validation: Validation,
}

#[derive(Deserialize)]
struct Claims {
    sub: Uuid,
    tenant_id: Uuid,
    #[serde(default)]
    roles: Vec<String>,
}

impl JwtService {
    pub fn new(secret: &str, issuer: &str, audience: &str) -> Self {
        let mut validation = Validation::new(Algorithm::HS256);
        validation.set_issuer(&[issuer]);
        validation.set_audience(&[audience]);
        validation.set_required_spec_claims(&["exp", "iss", "aud", "sub"]);
        validation.leeway = 30; // seconds of clock skew
        Self { key: DecodingKey::from_secret(secret.as_bytes()), validation }
    }

    /// The tenant comes only from the verified token — never from a header or the body.
    pub fn verify(&self, token: &str) -> Result<AuthUser, AppError> {
        let data = decode::<Claims>(token, &self.key, &self.validation).map_err(|e| {
            tracing::debug!(kind = ?e.kind(), "bearer token rejected"); // why: the log, never the client
            AppError::Unauthenticated
        })?;
        Ok(AuthUser { user_id: data.claims.sub, tenant_id: data.claims.tenant_id, roles: data.claims.roles })
    }
}

pub struct AuthMiddleware;

impl<S, B> Transform<S, ServiceRequest> for AuthMiddleware
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = actix_web::Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<EitherBody<B>>; // left: the handler's response, right: our 401
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
    type Response = ServiceResponse<EitherBody<B>>;
    type Error = actix_web::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>>>>;

    forward_ready!(service);

    fn call(&self, req: ServiceRequest) -> Self::Future {
        let user = match (req.app_data::<web::Data<AppState>>(), bearer_token(&req)) {
            (Some(state), Some(token)) => state.jwt.verify(token),
            (None, _) => Err(AppError::Internal(anyhow::anyhow!("AppState was not registered with .app_data()"))),
            (_, None) => Err(AppError::Unauthenticated),
        };
        match user {
            Ok(user) => {
                req.extensions_mut().insert(user); // what the AuthUser extractor reads
                let fut = self.service.call(req);
                Box::pin(async move { Ok(fut.await?.map_into_left_body()) })
            }
            // missing, malformed, expired, wrong issuer/audience: one 401 envelope, rendered here (inside
            // the request-id scope) as a response rather than an Err; the handler never runs
            Err(err) => Box::pin(ready(Ok(req.error_response(err).map_into_right_body()))),
        }
    }
}

fn bearer_token(req: &ServiceRequest) -> Option<&str> {
    req.headers().get("Authorization")?.to_str().ok()?.strip_prefix("Bearer ")
}
```
- Actix middleware uses the `Transform` + `Service` traits from Tower-like patterns
- For simpler middleware, prefer `middleware::from_fn` (Middleware above)

## Error Handling (ResponseError trait)
Every error body is the envelope in `api/response-envelope.md`:
`{"error": {code, message, details?, request_id, retryable}}` — no `data`, no source-error text.
```rust
use actix_web::{
    body::MessageBody,
    dev::{ServiceRequest, ServiceResponse},
    error::InternalError,
    http::{header::{self, HeaderName, HeaderValue}, StatusCode},
    middleware::Next,
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

// The task-local ApiResponse::success reads (languages/rust.md "Response Envelope"): ONE id for
// success and error bodies. A second task_local! here would leave every success meta.request_id empty.
use crate::response::REQUEST_ID;

// Request-id middleware — register it LAST (outermost): .wrap(middleware::from_fn(request_id)).
// Inner errors are rendered inside its scope, so every envelope carries the id it echoes as X-Request-Id.
pub async fn request_id(
    req: ServiceRequest,
    next: Next<impl MessageBody + 'static>,
) -> Result<ServiceResponse<impl MessageBody>, actix_web::Error> {
    let id = req.headers().get("x-request-id")
        .and_then(|v| v.to_str().ok())
        // a client-chosen id lands in logs and headers: short, plain characters only
        .filter(|s| !s.is_empty() && s.len() <= 128 && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_'))
        .map(str::to_owned)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let header = HeaderValue::from_str(&id).ok();
    // Don't clone req.request() to keep it for later: actix panics routing a request whose
    // HttpRequest is shared ("Panics if this HttpRequest has been cloned").
    REQUEST_ID.scope(id, async move {
        match next.call(req).await {
            Ok(mut res) => {
                if let Some(value) = header {
                    res.headers_mut().insert(HeaderName::from_static("x-request-id"), value);
                }
                Ok(res)
            }
            // An inner middleware's Err: render the envelope HERE, inside the scope, so it carries the
            // id — the server would otherwise render it after the scope ended, with an empty request_id
            Err(err) => {
                let mut res = err.error_response();
                if let Some(value) = header {
                    res.headers_mut().insert(HeaderName::from_static("x-request-id"), value);
                }
                Err(InternalError::from_response(err, res).into())
            }
        }
    })
    .await
}
```
- Implement `ResponseError` on your error type — Actix calls it automatically on `Err`
- Handler return type: `Result<HttpResponse, AppError>` enables `?` operator
- Never expose internal error details to clients — no `Display`/source text in any body, 4xx or 5xx
- Success bodies are `{"data": …, "meta": {"request_id": …}}`; lists add `meta.pagination`
  (`next_cursor`, `has_more`, `limit`) — the `ApiResponse` type in `languages/rust.md`

## Connection Pooling
```rust
use std::time::Duration;

use deadpool_postgres::{Config, Pool, PoolConfig, Runtime, Timeouts};

// deadpool (async, preferred for Actix). NoTls only to a database on the same host or a private
// sidecar; across a network use a TLS connector (e.g. tokio-postgres-rustls).
fn create_pool(database_url: &str) -> anyhow::Result<Pool> {
    let mut cfg = Config::new();
    cfg.url = Some(database_url.to_string());
    cfg.pool = Some(PoolConfig {
        max_size: 50,
        timeouts: Timeouts {
            wait: Some(Duration::from_secs(5)),
            create: Some(Duration::from_secs(5)),
            recycle: Some(Duration::from_secs(30)),
        },
        ..Default::default()
    });
    Ok(cfg.create_pool(Some(Runtime::Tokio1), tokio_postgres::NoTls)?)
}

// r2d2 (sync — every call that uses it goes inside web::block so it never blocks a worker thread)
use r2d2_postgres::{postgres, PostgresConnectionManager};

fn create_sync_pool(database_url: &str) -> anyhow::Result<r2d2::Pool<PostgresConnectionManager<postgres::NoTls>>> {
    let manager = PostgresConnectionManager::new(database_url.parse()?, postgres::NoTls);
    Ok(r2d2::Pool::builder()
        .max_size(20)
        .min_idle(Some(5))
        .build(manager)?)
}
```
- Prefer `deadpool` or `sqlx` for async connection pooling with Actix
- Use `r2d2` only when wrapping sync libraries with `web::block()`
- Always set `max_size` explicitly — never use unlimited connections
- Pool construction fails startup with an error (`?`), never a panic in a request path

## Testing with actix-rt
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::{http::StatusCode, middleware, test, web, App};

    #[actix_rt::test]
    async fn test_get_widget() {
        // your test helpers: a test database, a seeded row, and a token signed with the test key
        // (testing/rust-test.md) — never a fixed string the server accepts as a token
        let state = web::Data::new(test_app_state().await);
        let widget = seed_widget(&state).await;
        let token = test_token(&state, widget.tenant_id);
        let app = test::init_service(
            App::new()
                .app_data(state.clone())
                .app_data(path_config())
                .wrap(middleware::from_fn(request_id))
                .configure(api_config)
        ).await;

        let req = test::TestRequest::get()
            .uri(&format!("/api/v1/widgets/{}", widget.id)) // a real id: "some-uuid" is a 400
            .insert_header(("Authorization", format!("Bearer {token}")))
            .to_request();

        let resp = test::call_service(&app, req).await;
        assert_eq!(resp.status(), StatusCode::OK);
        let request_id = resp.headers().get("x-request-id").unwrap().to_str().unwrap().to_owned();

        let body: serde_json::Value = test::read_body_json(resp).await;
        assert_eq!(body["data"]["id"], widget.id.to_string());
        assert_eq!(body["meta"]["request_id"], request_id.as_str()); // envelope: data + meta.request_id = X-Request-Id
    }

    #[actix_rt::test]
    async fn test_create_widget() {
        let state = web::Data::new(test_app_state().await);
        let token = test_token(&state, uuid::Uuid::new_v4());
        let app = test::init_service(
            App::new()
                .app_data(state.clone())
                .app_data(json_config())
                .wrap(middleware::from_fn(request_id))
                .configure(api_config)
        ).await;

        let input = serde_json::json!({
            "name": "New Widget",
            "description": "Test"
        });

        let req = test::TestRequest::post()
            .uri("/api/v1/widgets")
            .set_json(&input)
            .insert_header(("Authorization", format!("Bearer {token}")))
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
use actix_web::web;

// Extractor failures become an AppError, so the body is the envelope: .app_data(json_config()) etc.
// serde's text goes to a debug log — never into the message.
pub fn json_config() -> web::JsonConfig {
    web::JsonConfig::default()
        .limit(1_048_576) // 1MB body limit
        .error_handler(|err, _req| {
            // bad syntax, wrong shape, wrong content type, too large → 400 MALFORMED_REQUEST
            tracing::debug!(error = %err, "json body rejected");
            AppError::MalformedRequest.into()
        })
}

pub fn query_config() -> web::QueryConfig {
    web::QueryConfig::default().error_handler(|err, _req| {
        tracing::debug!(error = %err, "query rejected");
        AppError::MalformedRequest.into()
    })
}

pub fn path_config() -> web::PathConfig {
    web::PathConfig::default().error_handler(|err, _req| {
        tracing::debug!(error = %err, "path rejected");
        // /widgets/not-a-uuid: the client sent a malformed id → 400 VALIDATION_FAILED on `id`
        // (as in frameworks/axum.md and error-handling-rust.md), not a 404
        AppError::Validation(vec![FieldError { field: "id".into(), code: "invalid_format", message: "Must be a valid ID." }]).into()
    })
}
```

## Rules
- Use `web::Data<T>` for shared state — it wraps `Arc<T>` internally
- Never use `.unwrap()` in handlers — return `Result<HttpResponse, AppError>` and use `?`
- Implement `ResponseError` on your error type for automatic HTTP error mapping — it writes the envelope
  (`api/response-envelope.md`), and extractor failures map to `AppError` via the `*Config` error handlers
- Use `deadpool` or `sqlx` for async connection pooling — `r2d2` is sync only
- `web::block()` for blocking calls (sync drivers, CPU-heavy work) — runs them on the blocking thread pool, so the workers keep serving
- Custom extractors via `FromRequest` — never parse auth headers manually in every handler
- Use `actix_cors` crate for CORS — never implement CORS manually
- `JsonConfig` must set body size limit — never accept unbounded request bodies
- Test with `actix_web::test` module — no real server needed for unit tests
