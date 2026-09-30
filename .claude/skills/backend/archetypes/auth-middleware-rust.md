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

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, axum 0.8.9, jsonwebtoken 11.1.0, tower-http 0.7.1, composed with the error-handling and CRUD archetypes into one crate; its tests also ran and pass.

Complete middleware stack for Axum REST APIs. Every generated project MUST follow this pattern.

## Dependencies (Cargo.toml)

```toml
[dependencies]
axum = { version = "0.8", features = ["macros"] } # macros: AppJson/AppPath/AppQuery (error-handling-rust.md)
axum-extra = { version = "0.12", features = ["typed-header"] }
tower = "0.5"
tower-http = { version = "0.7", features = ["cors", "request-id", "trace", "propagate-header"] }
tower-layer = "0.3"
# 10+: pick exactly one crypto backend ("rust_crypto" or "aws_lc_rs"); with neither it builds, then
# panics on the first encode/decode
jsonwebtoken = { version = "11", features = ["rust_crypto"] }
async-trait = "0.1"    # ApiKeyStore is used as a trait object
ring = "0.17"          # SHA-256 of API keys
serde = { version = "1", features = ["derive"] }
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
tracing = "0.1"
thiserror = "2"

[dev-dependencies]
tower = { version = "0.5", features = ["util"] } # ServiceExt::oneshot in the tests
http-body-util = "0.1"
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
    /// Tenant ID — all queries scoped to this tenant. It comes ONLY from these verified claims
    /// (or a server-side API-key record), never from a client header such as X-Tenant-ID.
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
            // The reason (expired, bad signature, malformed) is for the security log only; every
            // failure is the same 401 UNAUTHENTICATED to the client, so it can't probe tokens.
            tracing::warn!(error = %e, kind = ?e.kind(), "JWT validation failed");
            AppError::Unauthenticated
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
    extract::Request,
    http::header::AUTHORIZATION,
    middleware::Next,
    response::Response,
};

use crate::auth::claims::JwtClaims;
use crate::config::AppConfig;
use crate::error::AppError;

/// Axum middleware function: validates the JWT and injects claims into request extensions.
/// Every failure is `AppError::Unauthenticated` → 401 envelope with `WWW-Authenticate: Bearer`
/// (written by `AppError`'s `IntoResponse`, error-handling-rust.md).
///
/// Usage in router (the state is the shared `Arc<AppConfig>`, see startup.rs below):
/// ```ignore
/// Router::new()
///     .route("/protected", get(handler))
///     .layer(axum::middleware::from_fn_with_state(
///         state.config.clone(),
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
            AppError::Unauthenticated
        })?;

    let token = auth_header
        .strip_prefix("Bearer ")
        .ok_or_else(|| {
            tracing::debug!("Authorization header missing 'Bearer ' prefix");
            AppError::Unauthenticated
        })?;

    // 2. Validate JWT
    let claims = JwtClaims::from_token(token, config.jwt_secret.as_bytes())?;

    // 3. Optional: check token revocation (e.g., Redis blocklist)
    // if let Some(jti) = &claims.jti {
    //     if config.token_blocklist.is_revoked(jti).await? {
    //         tracing::warn!(jti = %jti, "revoked token used");
    //         return Err(AppError::Unauthenticated);
    //     }
    // }

    // 4. Inject the verified claims for downstream extractors. This is the ONLY source of
    //    tenant_id: a client-sent X-Tenant-ID (or similar) header is never read.
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
use crate::error::{current_request_id, AppError, RequestId};

/// Extracts authenticated user information from request extensions.
/// Requires `jwt_auth_middleware` to run before this extractor.
///
/// Usage in handler:
/// ```ignore
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

    /// Require a specific role or return 403 FORBIDDEN.
    pub fn require_role(&self, role: &str) -> Result<(), AppError> {
        self.require_any_role(&[role])
    }

    /// Require any one of the roles or return 403 FORBIDDEN (function-level authorization).
    pub fn require_any_role(&self, roles: &[&str]) -> Result<(), AppError> {
        if roles.iter().any(|r| self.has_role(r)) {
            Ok(())
        } else {
            tracing::warn!(user_id = %self.user_id, required = ?roles, "insufficient permissions");
            Err(AppError::Forbidden)
        }
    }
}

// axum 0.8: FromRequestParts is a native async trait — no #[async_trait] attribute
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
                AppError::Unauthenticated
            })?;

        // Set by request_id_middleware (error-handling-rust.md) — the same id error bodies carry
        let request_id = parts
            .extensions
            .get::<RequestId>()
            .map(|r| r.0.clone())
            .unwrap_or_else(current_request_id);

        // tenant_id and user_id come from the verified token claims — never from a header, path or body
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
    extract::Request,
    middleware::Next,
    response::Response,
};

use crate::auth::claims::JwtClaims;
use crate::error::AppError;

/// Middleware that requires a specific role to access the route.
/// No claims → 401 UNAUTHENTICATED; wrong role → 403 FORBIDDEN (function-level).
/// Another tenant's object is NOT a role problem: that is 404 NOT_FOUND from the data layer.
///
/// Usage:
/// ```ignore
/// Router::new()
///     .route("/admin/users", get(list_users))
///     .layer(axum::middleware::from_fn(admin_only()))
/// ```
///
/// For multiple roles, use a guard factory (see `editor_or_admin` below):
/// ```ignore
/// .layer(axum::middleware::from_fn(editor_or_admin()))
/// ```
pub async fn require_any_role(
    req: Request,
    next: Next,
    required_roles: &[&str],
) -> Result<Response, AppError> {
    let claims = req
        .extensions()
        .get::<JwtClaims>()
        .ok_or(AppError::Unauthenticated)?;

    if !claims.has_any_role(required_roles) {
        tracing::warn!(
            user_id = %claims.sub,
            required = ?required_roles,
            actual = ?claims.roles,
            "insufficient permissions"
        );
        return Err(AppError::Forbidden);
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
    extract::{Request, State},
    middleware::Next,
    response::Response,
};
use std::sync::Arc;
use uuid::Uuid;

use crate::auth::claims::JwtClaims;
use crate::auth::middleware::jwt_auth_middleware;
use crate::config::AppConfig;
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

/// State for `api_key_or_jwt_middleware`: the key store, plus the config the JWT fallback needs.
#[derive(Clone)]
pub struct ApiKeyAuth {
    pub store: Arc<dyn ApiKeyStore>,
    pub config: Arc<AppConfig>,
}

/// Middleware: authenticate via API key header.
/// Falls through to JWT auth if no API key is present.
///
/// Usage (in place of jwt_auth_middleware on the routes that accept API keys):
/// ```ignore
/// .layer(axum::middleware::from_fn_with_state(api_key_auth.clone(), api_key_or_jwt_middleware))
/// ```
pub async fn api_key_or_jwt_middleware(
    State(auth): State<ApiKeyAuth>,
    mut req: Request,
    next: Next,
) -> Result<Response, AppError> {
    // Check for API key first
    if let Some(api_key) = req.headers().get(API_KEY_HEADER).and_then(|v| v.to_str().ok()) {
        let key_hash = sha256_hex(api_key);

        let record = auth
            .store
            .lookup(&key_hash)
            .await?
            .ok_or_else(|| {
                tracing::warn!("unknown API key");
                AppError::Unauthenticated
            })?;

        if !record.is_active {
            tracing::warn!(tenant_id = %record.tenant_id, "deactivated API key used");
            return Err(AppError::Unauthenticated);
        }

        // Inject equivalent JwtClaims so downstream extractors work uniformly. The tenant comes
        // from the server-side key record, never from a client header.
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
    jwt_auth_middleware(State(auth.config.clone()), req, next).await
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
            // 429 RATE_LIMITED, retryable, with Retry-After
            return Err(AppError::rate_limited(self.window.as_secs()));
        }

        timestamps.push(now);
        Ok(())
    }
}

/// Rate limit middleware keyed by tenant_id (from verified JWT claims — never a client header).
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

Use `request_id_middleware`, `RequestId` and `current_request_id()` from `error-handling-rust.md`
(`crate::error`) — do not define a second one. That middleware keeps a well-formed incoming
`X-Request-Id` (or mints a UUID), inserts the `RequestId` extension, puts the id in the task-local scope
that `AppError`'s `IntoResponse` reads (so every error body's `request_id` matches the header), and
echoes `X-Request-Id` on every response.

## Middleware Stack Assembly (Router)

```rust
// src/startup.rs

use axum::{middleware, Router};
use std::sync::Arc;
use std::time::Duration;
use tower_http::trace::TraceLayer;

use crate::auth::middleware::jwt_auth_middleware;
use crate::config::AppConfig;
use crate::error::{recovery_middleware, request_id_middleware};
use crate::middleware::cors::cors_layer;
use crate::middleware::rate_limit::{rate_limit_middleware, RateLimiter};
use crate::services::widget::WidgetService;

pub struct AppState {
    pub config: Arc<AppConfig>, // Arc: jwt_auth_middleware's state (State<Arc<AppConfig>>)
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
        config: Arc::new(config),
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
            state.config.clone(),
            jwt_auth_middleware,
        ));

    // --- Admin routes (JWT + admin role required) ---
    let admin_routes = Router::new()
        .nest("/admin", crate::handlers::admin::admin_routes())
        .layer(middleware::from_fn(crate::auth::require_role::admin_only()))
        .layer(middleware::from_fn_with_state(
            state.config.clone(),
            jwt_auth_middleware,
        ));

    // --- Assemble full router ---
    //
    // Middleware execution order (top to bottom = first to last):
    //   request_id -> cors -> trace -> rate_limit -> recovery -> [route-specific auth]
    Router::new()
        .merge(public_routes)
        .merge(api_routes)
        .merge(admin_routes)
        .with_state(state)
        // Layer order: LAST added = FIRST to execute
        .layer(middleware::from_fn(recovery_middleware)) // panics → 500 INTERNAL envelope
        .layer(middleware::from_fn_with_state(
            rate_limiter,
            rate_limit_middleware,
        ))
        .layer(TraceLayer::new_for_http())
        .layer(cors_layer())
        .layer(middleware::from_fn(request_id_middleware)) // outermost: request_id in scope for all errors
}
```

## AppError IntoResponse Implementation

Defined once, in `error-handling-rust.md` — do not write a second `impl IntoResponse for AppError`
here. What the auth layer relies on from it:

| Returned by the auth layer | Status | `error.code` | Extra |
|---|---|---|---|
| `AppError::Unauthenticated` (missing/malformed/expired/invalid token, bad API key) | 401 | `UNAUTHENTICATED` | `WWW-Authenticate: Bearer`; one fixed message for every cause |
| `AppError::Forbidden` (role guard) | 403 | `FORBIDDEN` | fixed message; required role only in the log |
| `AppError::rate_limited(secs)` | 429 | `RATE_LIMITED` | `Retry-After`, `retryable: true` |

Every body is `{"error": {code, message, request_id, retryable}}` with `request_id` = `X-Request-Id`.

## Testing Auth Middleware

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::{Request, StatusCode}, response::IntoResponse, Router, routing::get};
    use std::sync::Arc;
    use tower::ServiceExt;
    use http_body_util::BodyExt;
    use uuid::Uuid;

    use crate::auth::claims::JwtClaims;
    use crate::auth::middleware::jwt_auth_middleware;
    use crate::config::AppConfig;
    use crate::error::request_id_middleware;
    use crate::extractors::auth_user::AuthUser;

    /// Read the body and check it is the 401 error envelope (api/response-envelope.md).
    async fn assert_unauthenticated(resp: axum::response::Response) {
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(
            resp.headers().get("www-authenticate").and_then(|v| v.to_str().ok()),
            Some("Bearer")
        );
        let header_id = resp.headers().get("x-request-id").and_then(|v| v.to_str().ok()).map(str::to_owned);
        let body = resp.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(json.get("data").is_none(), "an error body has no 'data' key");
        assert_eq!(json["error"]["code"], "UNAUTHENTICATED");
        assert_eq!(json["error"]["retryable"], false);
        assert_eq!(json["error"]["request_id"].as_str(), header_id.as_deref());
    }

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
        assert_unauthenticated(resp).await;
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
        assert_unauthenticated(resp).await;
    }

    #[tokio::test]
    async fn tenant_comes_from_token_not_from_client_header() {
        let app = test_app();
        let token_tenant = Uuid::new_v4();
        let token = make_token(token_tenant, Uuid::new_v4(), vec!["viewer".into()]);

        // A client trying to switch tenants with a header must be ignored
        let req = Request::builder()
            .uri("/protected")
            .header("Authorization", format!("Bearer {token}"))
            .header("X-Tenant-ID", Uuid::new_v4().to_string())
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let body = resp.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["tenant_id"], token_tenant.to_string());
    }

    #[tokio::test]
    async fn missing_role_returns_403_forbidden() {
        let app = Router::new()
            .route("/admin", get(|| async { "ok" }))
            .layer(axum::middleware::from_fn(crate::auth::require_role::admin_only()))
            .layer(axum::middleware::from_fn_with_state(
                Arc::new(AppConfig::test_defaults()),
                jwt_auth_middleware,
            ))
            .layer(axum::middleware::from_fn(request_id_middleware));
        let token = make_token(Uuid::new_v4(), Uuid::new_v4(), vec!["viewer".into()]);

        let req = Request::builder()
            .uri("/admin")
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::FORBIDDEN);
        let body = resp.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["error"]["code"], "FORBIDDEN");
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
- `tenant_id` (and `user_id`) MUST come from the verified token claims, or from the server-side API-key record — never from `X-Tenant-ID` or any other client header, path or body
- Auth failures return the error envelope from `error-handling-rust.md`: 401 `UNAUTHENTICATED` (with `WWW-Authenticate: Bearer`, one fixed message whatever the cause), 403 `FORBIDDEN` for a missing role, 429 `RATE_LIMITED` with `Retry-After`
- The failure reason (expired, bad signature, unknown key, missing role) goes to the `warn` log, never into the response
- Internal errors MUST NOT leak to clients — `AppError::Internal` returns "Something went wrong."
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Rate limiting MUST run BEFORE auth to reject floods before expensive JWT validation
- Request ID MUST be the first middleware (outermost layer) so all logs include it
- CORS MUST be configured BEFORE route handlers — preflight OPTIONS requests exit early
- API key authentication MUST hash keys with SHA-256 — never store or compare raw keys
- Role guards MUST use the `JwtClaims` from extensions, not re-parse the token
- Middleware ordering: request_id -> cors -> trace -> rate_limit -> recovery -> auth -> role_guard; use the single `request_id_middleware` from `error-handling-rust.md`
- `allow_credentials(true)` and `AllowOrigin::any()` are mutually exclusive — pick one
- Token expiration leeway MUST be small (30 seconds max) to limit replay window
- Every auth failure MUST log at `warn` level with the failure reason (for security monitoring)
