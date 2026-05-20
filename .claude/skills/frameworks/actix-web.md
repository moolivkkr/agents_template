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

// Query parameters: /widgets?page_size=20&cursor=abc
#[derive(Deserialize)]
struct ListParams {
    page_size: Option<i32>,
    cursor: Option<String>,
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
- Failed extraction returns 400 by default — customize via `JsonConfig`

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
    type Error = actix_web::Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        let extensions = req.extensions();
        match extensions.get::<AuthUser>() {
            Some(user) => ready(Ok(AuthUser {
                user_id: user.user_id,
                tenant_id: user.tenant_id,
                roles: user.roles.clone(),
            })),
            None => ready(Err(actix_web::error::ErrorUnauthorized("missing auth context"))),
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
```rust
use actix_web::{HttpResponse, ResponseError};
use std::fmt;

#[derive(Debug)]
pub enum AppError {
    NotFound(String),
    BadRequest(String),
    Unauthorized(String),
    Conflict(String),
    Validation { field: String, reason: String },
    Internal(String),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound(msg) => write!(f, "not found: {msg}"),
            Self::BadRequest(msg) => write!(f, "bad request: {msg}"),
            Self::Unauthorized(msg) => write!(f, "unauthorized: {msg}"),
            Self::Conflict(msg) => write!(f, "conflict: {msg}"),
            Self::Validation { field, reason } => write!(f, "validation error on {field}: {reason}"),
            Self::Internal(msg) => write!(f, "internal error: {msg}"),
        }
    }
}

impl ResponseError for AppError {
    fn error_response(&self) -> HttpResponse {
        let (status, code) = match self {
            Self::NotFound(_) => (StatusCode::NOT_FOUND, "NOT_FOUND"),
            Self::BadRequest(_) => (StatusCode::BAD_REQUEST, "BAD_REQUEST"),
            Self::Unauthorized(_) => (StatusCode::UNAUTHORIZED, "UNAUTHORIZED"),
            Self::Conflict(_) => (StatusCode::CONFLICT, "CONFLICT"),
            Self::Validation { .. } => (StatusCode::UNPROCESSABLE_ENTITY, "VALIDATION_ERROR"),
            Self::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
        };

        HttpResponse::build(status).json(serde_json::json!({
            "error": {
                "code": code,
                "message": self.to_string(),
            }
        }))
    }
}
```
- Implement `ResponseError` on your error type — Actix calls it automatically on `Err`
- Handler return type: `Result<HttpResponse, AppError>` enables `?` operator
- Never expose internal error details to clients in 500 responses

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
// Customize JSON extractor behavior globally
App::new()
    .app_data(
        web::JsonConfig::default()
            .limit(1_048_576) // 1MB body limit
            .error_handler(|err, _req| {
                let detail = err.to_string();
                actix_web::error::InternalError::from_response(
                    err,
                    HttpResponse::BadRequest().json(serde_json::json!({
                        "error": {
                            "code": "BAD_REQUEST",
                            "message": format!("invalid JSON: {detail}")
                        }
                    })),
                ).into()
            })
    )
```

## Rules
- Use `web::Data<T>` for shared state — it wraps `Arc<T>` internally
- Never use `.unwrap()` in handlers — return `Result<HttpResponse, AppError>` and use `?`
- Implement `ResponseError` on your error type for automatic HTTP error mapping
- Use `deadpool` or `sqlx` for async connection pooling — `r2d2` is sync only
- `web::block()` for CPU-bound work — offloads to thread pool, prevents blocking the event loop
- Custom extractors via `FromRequest` — never parse auth headers manually in every handler
- Use `actix_cors` crate for CORS — never implement CORS manually
- `JsonConfig` must set body size limit — never accept unbounded request bodies
- Test with `actix_web::test` module — no real server needed for unit tests
