# Actix-web framework patterns for Rust HTTP APIs.

## App & HttpServer Setup
```rust
#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let db_pool = PgPool::connect(&std::env::var("DATABASE_URL").unwrap()).await.expect("failed to connect");
    let app_state = web::Data::new(AppState { db: db_pool, jwt: JwtService::new(&config.jwt_secret), config: config.clone() });

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(middleware::Logger::default())
            .wrap(middleware::Compress::default())
            .configure(api_config)
    })
    .bind(("0.0.0.0", 8080))?.workers(num_cpus::get()).run().await
}
```
- Factory closure called once per worker thread
- `.app_data()` shares state via `web::Data<T>` (internally `Arc<T>`)

## Route Definition
```rust
fn api_config(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api/v1")
            .service(web::resource("/widgets").route(web::post().to(create_widget)).route(web::get().to(list_widgets)))
            .service(web::resource("/widgets/{id}").route(web::get().to(get_widget)).route(web::put().to(update_widget)).route(web::delete().to(delete_widget)))
            .wrap(auth_middleware())
    );
}
```

## Extractors
```rust
async fn get_widget(path: web::Path<Uuid>) -> HttpResponse { let id = path.into_inner(); /* ... */ }

#[derive(Deserialize)]
struct ListParams { page_size: Option<i32>, cursor: Option<String> }
async fn list_widgets(query: web::Query<ListParams>) -> HttpResponse { /* ... */ }

async fn create_widget(body: web::Json<CreateInput>) -> HttpResponse { /* ... */ }

// Multiple extractors — order doesn't matter (unlike Axum)
async fn update_widget(state: web::Data<AppState>, path: web::Path<Uuid>, body: web::Json<UpdateInput>) -> HttpResponse { /* ... */ }
```
- `web::Json` validates Content-Type and deserializes; failed extraction returns 400

## Custom Extractor (AuthUser)
```rust
pub struct AuthUser { pub user_id: Uuid, pub tenant_id: Uuid, pub roles: Vec<String> }

impl FromRequest for AuthUser {
    type Error = actix_web::Error;
    type Future = Ready<Result<Self, Self::Error>>;
    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        match req.extensions().get::<AuthUser>() {
            Some(user) => ready(Ok(AuthUser { user_id: user.user_id, tenant_id: user.tenant_id, roles: user.roles.clone() })),
            None => ready(Err(actix_web::error::ErrorUnauthorized("missing auth context"))),
        }
    }
}
```

## Middleware
```rust
// Built-in logger + CORS
App::new()
    .wrap(Logger::new("%a %r %s %b %Dms"))
    .wrap(Cors::default().allowed_origin("https://app.example.com").allowed_methods(vec!["GET","POST","PUT","DELETE"]).max_age(3600))

// Custom auth middleware (Transform + Service traits)
pub struct AuthMiddleware;
impl<S, B> Transform<S, ServiceRequest> for AuthMiddleware
where S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = actix_web::Error>, S::Future: 'static, B: 'static {
    type Response = ServiceResponse<B>; type Error = actix_web::Error; type Transform = AuthMiddlewareService<S>;
    type InitError = (); type Future = Ready<Result<Self::Transform, Self::InitError>>;
    fn new_transform(&self, service: S) -> Self::Future { ready(Ok(AuthMiddlewareService { service })) }
}
// For simpler middleware, prefer wrap_fn or from_fn helpers
```

## Error Handling (ResponseError)
```rust
#[derive(Debug)]
pub enum AppError {
    NotFound(String), BadRequest(String), Unauthorized(String), Conflict(String),
    Validation { field: String, reason: String }, Internal(String),
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
        HttpResponse::build(status).json(json!({"error": {"code": code, "message": self.to_string()}}))
    }
}
```
- Handler return `Result<HttpResponse, AppError>` enables `?` operator

## Connection Pooling
```rust
// deadpool (async, preferred)
let mut cfg = Config::new();
cfg.url = Some(database_url.to_string());
cfg.pool = Some(deadpool_postgres::PoolConfig { max_size: 50, ..Default::default() });
let pool = cfg.create_pool(Some(Runtime::Tokio1), NoTls).unwrap();
```

## Testing
```rust
#[actix_rt::test]
async fn test_get_widget() {
    let state = web::Data::new(test_app_state().await);
    let app = test::init_service(App::new().app_data(state.clone()).configure(api_config)).await;
    let req = test::TestRequest::get().uri("/api/v1/widgets/some-uuid")
        .insert_header(("Authorization", "Bearer test-token")).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::OK);
    let body: serde_json::Value = test::read_body_json(resp).await;
    assert!(body["data"]["id"].is_string());
}
```
- `test::init_service` + `test::call_service` — no real HTTP server needed

## JSON Config
```rust
App::new().app_data(web::JsonConfig::default().limit(1_048_576).error_handler(|err, _req| {
    actix_web::error::InternalError::from_response(err,
        HttpResponse::BadRequest().json(json!({"error": {"code": "BAD_REQUEST", "message": format!("invalid JSON: {}", err)}}))).into()
}))
```

## Rules
- `web::Data<T>` for shared state (wraps `Arc<T>`)
- Never `.unwrap()` in handlers — return `Result<HttpResponse, AppError>`
- `ResponseError` trait for automatic HTTP error mapping
- `deadpool`/`sqlx` for async pooling
- `web::block()` for CPU-bound work
- Custom extractors via `FromRequest` for auth context
- `JsonConfig` must set body size limit
