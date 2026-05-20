---
skill: auth-middleware-rust
description: Axum auth middleware archetype — JWT validation (jsonwebtoken), AuthUser extractor (FromRequestParts), role-based access (RequireRole layer), rate limiting, CORS, request ID, API key authentication, middleware ordering
version: "1.0"
tags:
  - rust
  - axum
  - auth
  - middleware
  - jwt
  - rbac
  - archetype
  - backend
---

# Auth Middleware Archetype (Rust / Axum)

Complete middleware stack for Axum REST APIs. Every generated project MUST follow this pattern.

## Dependencies (Cargo.toml)

```toml
[dependencies]
axum = "0.8"
axum-extra = { version = "0.10", features = ["typed-header"] }
tower = "0.5"
tower-http = { version = "0.6", features = ["cors", "request-id", "trace", "propagate-header"] }
tower-layer = "0.3"
jsonwebtoken = "9"
serde = { version = "1", features = ["derive"] }
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
tracing = "0.1"
thiserror = "2"
```

## JWT Claims and Validation

```rust
// src/auth/claims.rs

use chrono::{DateTime, Utc};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::AppError;

/// JWT claims embedded in the Bearer token.
/// Matches the token structure issued by the auth service.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JwtClaims {
    /// Subject — the user ID.
    pub sub: Uuid,
    /// Tenant ID — all queries scoped to this tenant.
    pub tenant_id: Uuid,
    /// Roles assigned to this user (e.g., "admin", "editor", "viewer").
    pub roles: Vec<String>,
    /// Issued at (Unix timestamp).
    pub iat: usize,
    /// Expiration (Unix timestamp).
    pub exp: usize,
    /// Optional: JWT ID for revocation checking.
    #[serde(default)]
    pub jti: Option<String>,
}

impl JwtClaims {
    /// Validate and decode a JWT token string.
    pub fn from_token(token: &str, secret: &[u8]) -> Result<Self, AppError> {
        let mut validation = Validation::new(Algorithm::HS256);
        validation.set_required_spec_claims(&["exp", "sub", "tenant_id"]);
        validation.validate_exp = true;
        validation.leeway = 30; // 30 seconds clock skew tolerance

        let token_data = decode::<JwtClaims>(
            token,
            &DecodingKey::from_secret(secret),
            &validation,
        )
        .map_err(|e| {
            tracing::warn!(error = %e, "JWT validation failed");
            match e.kind() {
                jsonwebtoken::errors::ErrorKind::ExpiredSignature => {
                    AppError::Unauthorized("token expired".into())
                }
                jsonwebtoken::errors::ErrorKind::InvalidToken
                | jsonwebtoken::errors::ErrorKind::InvalidSignature => {
                    AppError::Unauthorized("invalid token".into())
                }
                _ => AppError::Unauthorized("authentication failed".into()),
                }
        })?;

        Ok(token_data.claims)
    }

    /// Check whether this claims set includes a specific role.
    pub fn has_role(&self, role: &str) -> bool {
        self.roles.iter().any(|r| r == role)
    }

    /// Check whether any of the given roles is present.
    pub fn has_any_role(&self, roles: &[&str]) -> bool {
        roles.iter().any(|r| self.has_role(r))
    }
}
```

## Auth Middleware Layer

```rust
// src/auth/middleware.rs

use axum::{
    body::Body,
    extract::Request,
    http::{header::AUTHORIZATION, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};

use crate::auth::claims::JwtClaims;
use crate::config::AppConfig;
use crate::error::AppError;

/// Request extension — inserted by auth middleware, consumed by extractors.
#[derive(Clone, Debug)]
pub struct RequestId(pub String);

/// Axum middleware function: validates the JWT and injects claims into request extensions.
///
/// Usage in router:
/// ```rust
/// Router::new()
///     .route("/protected", get(handler))
///     .layer(axum::middleware::from_fn_with_state(
///         app_state.clone(),
///         jwt_auth_middleware,
///     ))
/// ```
pub async fn jwt_auth_middleware(
    axum::extract::State(config): axum::extract::State<std::sync::Arc<AppConfig>>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    // 1. Extract Bearer token from Authorization header
    let auth_header = req
        .headers()
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .ok_or_else(|| {
            tracing::debug!("missing Authorization header");
            AppError::Unauthorized("missing Authorization header".into())
        })?;

    let token = auth_header
        .strip_prefix("Bearer ")
        .ok_or_else(|| {
            tracing::debug!("Authorization header missing 'Bearer ' prefix");
            AppError::Unauthorized("invalid Authorization header format".into())
        })?;

    // 2. Validate JWT
    let claims = JwtClaims::from_token(token, config.jwt_secret.as_bytes())?;

    // 3. Optional: check token revocation (e.g., Redis blocklist)
    // if let Some(jti) = &claims.jti {
    //     if config.token_blocklist.is_revoked(jti).await? {
    //         return Err(AppError::Unauthorized("token revoked".into()));
    //     }
    // }

    // 4. Inject claims into request extensions for downstream extractors
    req.extensions_mut().insert(claims);

    // 5. Continue to the next handler/middleware
    Ok(next.run(req).await)
}
```

## AuthUser Extractor

```rust
// src/extractors/auth_user.rs

use axum::{
    extract::FromRequestParts,
    http::request::Parts,
};
use std::sync::Arc;
use uuid::Uuid;

use crate::auth::claims::JwtClaims;
use crate::auth::middleware::RequestId;
use crate::config::AppConfig;
use crate::error::AppError;

/// Extracts authenticated user information from request extensions.
/// Requires `jwt_auth_middleware` to run before this extractor.
///
/// Usage in handler:
/// ```rust
/// async fn my_handler(auth: AuthUser) -> impl IntoResponse {
///     let tenant_id = auth.tenant_id;
///     let user_id = auth.user_id;
///     // ...
/// }
/// ```
#[derive(Debug, Clone)]
pub struct AuthUser {
    pub tenant_id: Uuid,
    pub user_id: Uuid,
    pub roles: Vec<String>,
    request_id: String,
}

impl AuthUser {
    pub fn request_id(&self) -> String {
        self.request_id.clone()
    }

    /// Check if the user has a specific role.
    pub fn has_role(&self, role: &str) -> bool {
        self.roles.iter().any(|r| r == role)
    }

    /// Require a specific role or return Forbidden.
    pub fn require_role(&self, role: &str) -> Result<(), AppError> {
        if self.has_role(role) {
            Ok(())
        } else {
            Err(AppError::Forbidden {
                action: "access".into(),
                resource: "endpoint".into(),
            })
        }
    }
}

#[axum::async_trait]
impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(
        parts: &mut Parts,
        _state: &S,
    ) -> Result<Self, Self::Rejection> {
        let claims = parts
            .extensions
            .get::<JwtClaims>()
            .ok_or_else(|| {
                tracing::error!("JwtClaims not found in extensions — is jwt_auth_middleware applied?");
                AppError::Unauthorized("missing auth context".into())
            })?;

        let request_id = parts
            .extensions
            .get::<RequestId>()
            .map(|r| r.0.clone())
            .unwrap_or_else(|| Uuid::new_v4().to_string());

        Ok(AuthUser {
            tenant_id: claims.tenant_id,
            user_id: claims.sub,
            roles: claims.roles.clone(),
            request_id,
        })
    }
}
```

## Role-Based Access Control (RequireRole Layer)

```rust
// src/auth/require_role.rs

use axum::{
    body::Body,
    extract::Request,
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};

use crate::auth::claims::JwtClaims;
use crate::error::AppError;

/// Middleware that requires a specific role to access the route.
///
/// Usage:
/// ```rust
/// Router::new()
///     .route("/admin/users", get(list_users))
///     .layer(axum::middleware::from_fn(require_role::<"admin">))
/// ```
///
/// For multiple roles, use the closure variant:
/// ```rust
/// .layer(axum::middleware::from_fn(|req, next| {
///     require_any_role(req, next, &["admin", "editor"])
/// }))
/// ```
pub async fn require_any_role(
    req: Request,
    next: Next,
    required_roles: &[&str],
) -> Result<Response, AppError> {
    let claims = req
        .extensions()
        .get::<JwtClaims>()
        .ok_or_else(|| AppError::Unauthorized("missing auth context".into()))?;

    if !claims.has_any_role(required_roles) {
        tracing::warn!(
            user_id = %claims.sub,
            required = ?required_roles,
            actual = ?claims.roles,
            "insufficient permissions"
        );
        return Err(AppError::Forbidden {
            action: "access".into(),
            resource: "resource".into(),
        });
    }

    Ok(next.run(req).await)
}

/// Factory: create a role-checking middleware for a specific role.
/// Returns a closure suitable for `axum::middleware::from_fn`.
pub fn role_guard(
    role: &'static str,
) -> impl Fn(Request, Next) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<Response, AppError>> + Send>>
       + Clone
       + Send
{
    move |req: Request, next: Next| {
        Box::pin(async move { require_any_role(req, next, &[role]).await })
    }
}

/// Convenience: admin-only guard.
pub fn admin_only() -> impl Fn(Request, Next) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<Response, AppError>> + Send>>
       + Clone
       + Send
{
    role_guard("admin")
}

/// Convenience: editor or admin guard.
pub fn editor_or_admin() -> impl Fn(Request, Next) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<Response, AppError>> + Send>>
       + Clone
       + Send
{
    move |req: Request, next: Next| {
        Box::pin(async move { require_any_role(req, next, &["admin", "editor"]).await })
    }
}
```

## API Key Authentication (Alternative to JWT)

```rust
// src/auth/api_key.rs

use axum::{
    extract::Request,
    http::header::HeaderValue,
    middleware::Next,
    response::Response,
};
use uuid::Uuid;

use crate::auth::claims::JwtClaims;
use crate::auth::middleware::RequestId;
use crate::error::AppError;

const API_KEY_HEADER: &str = "X-API-Key";

/// API key entry stored in the database or config.
#[derive(Debug, Clone)]
pub struct ApiKeyRecord {
    pub key_hash: String,
    pub tenant_id: Uuid,
    pub user_id: Uuid,
    pub roles: Vec<String>,
    pub is_active: bool,
}

/// Trait for API key lookup — implement against your database.
#[async_trait::async_trait]
pub trait ApiKeyStore: Send + Sync {
    async fn lookup(&self, key_hash: &str) -> Result<Option<ApiKeyRecord>, AppError>;
}

/// Middleware: authenticate via API key header.
/// Falls through to JWT auth if no API key is present.
///
/// Usage (before jwt_auth_middleware in the middleware stack):
/// ```rust
/// .layer(axum::middleware::from_fn_with_state(state.clone(), api_key_or_jwt_middleware))
/// ```
pub async fn api_key_or_jwt_middleware(
    axum::extract::State(state): axum::extract::State<std::sync::Arc<crate::startup::AppState>>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    // Check for API key first
    if let Some(api_key) = req.headers().get(API_KEY_HEADER).and_then(|v| v.to_str().ok()) {
        let key_hash = sha256_hex(api_key);

        let record = state
            .api_key_store
            .lookup(&key_hash)
            .await?
            .ok_or_else(|| AppError::Unauthorized("invalid API key".into()))?;

        if !record.is_active {
            return Err(AppError::Unauthorized("API key deactivated".into()));
        }

        // Inject equivalent JwtClaims so downstream extractors work uniformly
        let claims = JwtClaims {
            sub: record.user_id,
            tenant_id: record.tenant_id,
            roles: record.roles,
            iat: chrono::Utc::now().timestamp() as usize,
            exp: (chrono::Utc::now().timestamp() + 3600) as usize,
            jti: None,
        };
        req.extensions_mut().insert(claims);

        return Ok(next.run(req).await);
    }

    // No API key — fall through to JWT validation
    jwt_auth_middleware(
        axum::extract::State(std::sync::Arc::new(state.config.clone())),
        req,
        next,
    )
    .await
}

/// Hash an API key with SHA-256 (never store raw keys).
fn sha256_hex(input: &str) -> String {
    use std::fmt::Write;
    let digest = ring::digest::digest(&ring::digest::SHA256, input.as_bytes());
    let mut hex = String::with_capacity(64);
    for byte in digest.as_ref() {
        write!(&mut hex, "{byte:02x}").unwrap();
    }
    hex
}
```

## Rate Limiting

```rust
// src/middleware/rate_limit.rs

use axum::{
    extract::ConnectInfo,
    extract::Request,
    middleware::Next,
    response::Response,
};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

use crate::error::AppError;

/// Simple in-memory sliding window rate limiter.
/// For production, use Redis-backed rate limiting (tower-governor or custom).
#[derive(Clone)]
pub struct RateLimiter {
    /// Max requests per window.
    max_requests: u64,
    /// Window duration.
    window: Duration,
    /// Per-key request timestamps.
    state: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
}

impl RateLimiter {
    pub fn new(max_requests: u64, window: Duration) -> Self {
        Self {
            max_requests,
            window,
            state: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn check(&self, key: &str) -> Result<(), AppError> {
        let mut state = self.state.lock().await;
        let now = Instant::now();
        let cutoff = now - self.window;

        let timestamps = state.entry(key.to_owned()).or_default();
        timestamps.retain(|t| *t > cutoff);

        if timestamps.len() as u64 >= self.max_requests {
            tracing::warn!(key = key, limit = self.max_requests, "rate limit exceeded");
            return Err(AppError::TooManyRequests {
                retry_after_secs: self.window.as_secs(),
            });
        }

        timestamps.push(now);
        Ok(())
    }
}

/// Rate limit middleware keyed by tenant_id (from JWT claims).
/// Falls back to IP-based limiting for unauthenticated requests.
pub async fn rate_limit_middleware(
    axum::extract::State(limiter): axum::extract::State<RateLimiter>,
    req: Request,
    next: Next,
) -> Result<Response, AppError> {
    let key = req
        .extensions()
        .get::<crate::auth::claims::JwtClaims>()
        .map(|c| format!("tenant:{}", c.tenant_id))
        .unwrap_or_else(|| {
            req.extensions()
                .get::<ConnectInfo<SocketAddr>>()
                .map(|ci| format!("ip:{}", ci.0.ip()))
                .unwrap_or_else(|| "unknown".into())
        });

    limiter.check(&key).await?;
    Ok(next.run(req).await)
}
```

## CORS Configuration

```rust
// src/middleware/cors.rs

use tower_http::cors::{Any, CorsLayer};
use axum::http::{header, Method};

/// Build the CORS layer for the API.
///
/// Production: replace `Any` origins with explicit allowed origins.
pub fn cors_layer() -> CorsLayer {
    CorsLayer::new()
        .allow_origin(Any) // TODO: restrict in production
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PUT,
            Method::PATCH,
            Method::DELETE,
            Method::OPTIONS,
        ])
        .allow_headers([
            header::AUTHORIZATION,
            header::CONTENT_TYPE,
            header::ACCEPT,
            header::HeaderName::from_static("x-request-id"),
            header::HeaderName::from_static("x-api-key"),
        ])
        .expose_headers([
            header::HeaderName::from_static("x-request-id"),
            header::HeaderName::from_static("x-ratelimit-limit"),
            header::HeaderName::from_static("x-ratelimit-remaining"),
        ])
        .max_age(std::time::Duration::from_secs(3600))
}

/// Restrictive CORS for production — only allow specific origins.
pub fn cors_layer_production(allowed_origins: &[&str]) -> CorsLayer {
    use tower_http::cors::AllowOrigin;

    let origins: Vec<_> = allowed_origins
        .iter()
        .map(|o| o.parse().expect("invalid origin"))
        .collect();

    CorsLayer::new()
        .allow_origin(AllowOrigin::list(origins))
        .allow_methods([
            Method::GET,
            Method::POST,
            Method::PUT,
            Method::PATCH,
            Method::DELETE,
        ])
        .allow_headers([
            header::AUTHORIZATION,
            header::CONTENT_TYPE,
            header::ACCEPT,
        ])
        .allow_credentials(true)
        .max_age(std::time::Duration::from_secs(3600))
}
```

## Request ID Layer

```rust
// src/middleware/request_id.rs

use axum::{
    extract::Request,
    middleware::Next,
    response::Response,
};
use uuid::Uuid;

use crate::auth::middleware::RequestId;

/// Middleware: generate or propagate a request ID.
///
/// If the incoming request has an `X-Request-Id` header, use it.
/// Otherwise, generate a new UUID v4.
/// Injects `RequestId` into extensions and adds the header to the response.
pub async fn request_id_middleware(
    mut req: Request,
    next: Next,
) -> Response {
    let request_id = req
        .headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_owned())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    req.extensions_mut().insert(RequestId(request_id.clone()));

    // Add to tracing span
    tracing::Span::current().record("request_id", &request_id);

    let mut response = next.run(req).await;

    // Echo request ID in response headers
    if let Ok(val) = request_id.parse() {
        response.headers_mut().insert("x-request-id", val);
    }

    response
}
```

## Middleware Stack Assembly (Router)

```rust
// src/startup.rs

use axum::{middleware, Router};
use std::sync::Arc;
use std::time::Duration;
use tower_http::trace::TraceLayer;

use crate::auth::middleware::jwt_auth_middleware;
use crate::middleware::cors::cors_layer;
use crate::middleware::rate_limit::{rate_limit_middleware, RateLimiter};
use crate::middleware::request_id::request_id_middleware;

pub struct AppState {
    pub config: AppConfig,
    pub widget_service: WidgetService,
    // ... other services
}

/// Build the complete Axum application with all middleware layers.
///
/// IMPORTANT: Middleware ordering matters. Layers are applied bottom-to-top
/// (last added = first to execute). The order below ensures:
///
/// 1. Request ID is assigned first (available to all downstream layers)
/// 2. CORS headers are set early (preflight responses exit here)
/// 3. Tracing captures the full request lifecycle
/// 4. Rate limiting runs before auth (rejects floods early)
/// 5. JWT auth validates tokens and injects claims
/// 6. Route-specific role guards check permissions
pub async fn build_app(config: AppConfig, pool: sqlx::PgPool) -> Router {
    let state = Arc::new(AppState {
        config: config.clone(),
        widget_service: WidgetService::new(/* ... */),
    });

    let rate_limiter = RateLimiter::new(100, Duration::from_secs(60));

    // --- Public routes (no auth required) ---
    let public_routes = Router::new()
        .route("/health", axum::routing::get(health_check))
        .route("/ready", axum::routing::get(readiness_check));

    // --- Protected routes (JWT required) ---
    let api_routes = Router::new()
        .nest("/api/v1/widgets", crate::handlers::widget::widget_routes())
        // Add more resource routes here...
        .layer(middleware::from_fn_with_state(
            state.clone(),
            jwt_auth_middleware,
        ));

    // --- Admin routes (JWT + admin role required) ---
    let admin_routes = Router::new()
        .nest("/admin", crate::handlers::admin::admin_routes())
        .layer(middleware::from_fn(crate::auth::require_role::admin_only()))
        .layer(middleware::from_fn_with_state(
            state.clone(),
            jwt_auth_middleware,
        ));

    // --- Assemble full router ---
    //
    // Middleware execution order (top to bottom = first to last):
    //   request_id -> cors -> trace -> rate_limit -> [route-specific auth]
    Router::new()
        .merge(public_routes)
        .merge(api_routes)
        .merge(admin_routes)
        .with_state(state)
        // Layer order: LAST added = FIRST to execute
        .layer(middleware::from_fn_with_state(
            rate_limiter,
            rate_limit_middleware,
        ))
        .layer(TraceLayer::new_for_http())
        .layer(cors_layer())
        .layer(middleware::from_fn(request_id_middleware))
}
```

## AppError IntoResponse Implementation

```rust
// src/error.rs

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, message) = match &self {
            AppError::Validation { message, details } => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "VALIDATION_ERROR",
                message.clone(),
            ),
            AppError::NotFound { resource, identifier } => (
                StatusCode::NOT_FOUND,
                "NOT_FOUND",
                format!("{resource} not found"),
            ),
            AppError::Conflict { resource, reason } => (
                StatusCode::CONFLICT,
                "CONFLICT",
                format!("{resource}: {reason}"),
            ),
            AppError::Unauthorized(msg) => (
                StatusCode::UNAUTHORIZED,
                "UNAUTHORIZED",
                msg.clone(),
            ),
            AppError::Forbidden { action, resource } => (
                StatusCode::FORBIDDEN,
                "FORBIDDEN",
                format!("insufficient permissions to {action} {resource}"),
            ),
            AppError::TooManyRequests { retry_after_secs } => (
                StatusCode::TOO_MANY_REQUESTS,
                "TOO_MANY_REQUESTS",
                "rate limit exceeded".into(),
            ),
            AppError::Internal(e) => {
                // CRITICAL: Never leak internal error details to the client
                tracing::error!(error = %e, "internal server error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "INTERNAL_ERROR",
                    "an unexpected error occurred".into(),
                )
            }
        };

        let body = json!({
            "error": {
                "code": code,
                "message": message,
            }
        });

        // Add rate limit headers for 429 responses
        let mut response = (status, Json(body)).into_response();
        if let AppError::TooManyRequests { retry_after_secs } = &self {
            if let Ok(val) = retry_after_secs.to_string().parse() {
                response.headers_mut().insert("retry-after", val);
            }
        }

        response
    }
}
```

## Testing Auth Middleware

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request, Router, routing::get};
    use tower::ServiceExt;
    use http_body_util::BodyExt;

    async fn protected_handler(auth: AuthUser) -> impl IntoResponse {
        axum::Json(serde_json::json!({
            "tenant_id": auth.tenant_id,
            "user_id": auth.user_id,
            "roles": auth.roles,
        }))
    }

    fn test_app() -> Router {
        let config = Arc::new(AppConfig::test_defaults());
        Router::new()
            .route("/protected", get(protected_handler))
            .layer(axum::middleware::from_fn_with_state(
                config,
                jwt_auth_middleware,
            ))
            .layer(axum::middleware::from_fn(request_id_middleware))
    }

    fn make_token(tenant_id: Uuid, user_id: Uuid, roles: Vec<String>) -> String {
        use jsonwebtoken::{encode, EncodingKey, Header};
        let claims = JwtClaims {
            sub: user_id,
            tenant_id,
            roles,
            iat: chrono::Utc::now().timestamp() as usize,
            exp: (chrono::Utc::now().timestamp() + 3600) as usize,
            jti: None,
        };
        encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(b"test-secret"),
        )
        .unwrap()
    }

    #[tokio::test]
    async fn missing_auth_header_returns_401() {
        let app = test_app();
        let req = Request::builder()
            .uri("/protected")
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn invalid_token_returns_401() {
        let app = test_app();
        let req = Request::builder()
            .uri("/protected")
            .header("Authorization", "Bearer invalid.jwt.token")
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn valid_token_extracts_claims() {
        let app = test_app();
        let tenant_id = Uuid::new_v4();
        let user_id = Uuid::new_v4();
        let token = make_token(tenant_id, user_id, vec!["admin".into()]);

        let req = Request::builder()
            .uri("/protected")
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);

        let body = resp.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["tenant_id"], tenant_id.to_string());
        assert_eq!(json["user_id"], user_id.to_string());
    }

    #[tokio::test]
    async fn response_includes_request_id_header() {
        let app = test_app();
        let token = make_token(Uuid::new_v4(), Uuid::new_v4(), vec!["admin".into()]);

        let req = Request::builder()
            .uri("/protected")
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert!(resp.headers().contains_key("x-request-id"));
    }
}
```

## Critical Rules

- JWT validation MUST happen in middleware, not in individual handlers — defense in depth
- AuthUser extractor MUST only read from `request.extensions()` — never parse the token itself
- Internal errors MUST NOT leak to clients — `AppError::Internal` returns "an unexpected error occurred"
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Rate limiting MUST run BEFORE auth to reject floods before expensive JWT validation
- Request ID MUST be the first middleware (outermost layer) so all logs include it
- CORS MUST be configured BEFORE route handlers — preflight OPTIONS requests exit early
- API key authentication MUST hash keys with SHA-256 — never store or compare raw keys
- Role guards MUST use the `JwtClaims` from extensions, not re-parse the token
- Middleware ordering: request_id -> cors -> trace -> rate_limit -> auth -> role_guard
- `allow_credentials(true)` and `AllowOrigin::any()` are mutually exclusive — pick one
- Token expiration leeway MUST be small (30 seconds max) to limit replay window
- Every auth failure MUST log at `warn` level with the failure reason (for security monitoring)
