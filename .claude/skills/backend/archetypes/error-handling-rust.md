---
skill: error-handling-rust
description: Rust error handling archetype — AppError enum with thiserror, IntoResponse for Axum writing the API error envelope, FieldError details, request id, From implementations, tracing integration
version: "1.0"
tags:
  - rust
  - errors
  - axum
  - archetype
  - backend
---

# Error Handling Archetype (Rust)

> **CANONICAL REFERENCE**: This file is the single source of truth for Rust backend error handling patterns.
> The wire shape it produces is the error envelope in `~/.claude/skills/api/response-envelope.md`
> (`{"error": {code, message, details[], request_id, retryable}}`); if the two ever disagree, the envelope wins. All other Rust skill packs that mention error handling should defer to this file for definitive guidance. For the Go equivalent, see `backend/archetypes/error-handling-go.md`.

Complete error handling system for Rust backend services using Axum. Every generated service MUST follow this pattern.

## AppError Enum (thiserror)

```rust
use axum::http::StatusCode;
use serde::Serialize;
use thiserror::Error;

pub type BoxError = Box<dyn std::error::Error + Send + Sync>;

/// FieldError is one entry of error.details[] — field-level problems for VALIDATION_FAILED.
/// `code` is a stable lower_snake identifier; `message` comes from a fixed catalog, never an error's Display.
#[derive(Debug, Clone, Serialize)]
pub struct FieldError {
    pub field: String,
    pub code: String,
    pub message: String,
}

/// AppError is the standard application error type.
/// All domain errors MUST use this enum so the IntoResponse impl can map them to HTTP responses.
/// `Display` (from thiserror) is the server-side text for logs and includes the cause; clients only
/// ever see `error_code()`, `user_message()`, `details()` and `retryable()`.
#[derive(Debug, Error)]
pub enum AppError {
    // --- 400 MALFORMED_REQUEST: unreadable JSON, wrong content type, body too large ---
    #[error("malformed request: {0}")]
    MalformedRequest(#[source] BoxError),

    // --- 400 VALIDATION_FAILED: input fails schema/field validation; details[] lists the fields ---
    #[error("validation failed: {details:?}")]
    Validation { details: Vec<FieldError> },

    // --- 401 UNAUTHENTICATED: missing, invalid or expired credentials ---
    #[error("unauthenticated")]
    Unauthenticated,

    // --- 403 FORBIDDEN: authenticated but not allowed (function-level) ---
    #[error("forbidden")]
    Forbidden,

    // --- 404 NOT_FOUND: missing OR another tenant's/owner's object (never 403 for those) ---
    #[error("{resource} not found")]
    NotFound { resource: &'static str },

    // --- 409 CONFLICT: duplicate / version mismatch / state conflict ---
    #[error("conflict: {message}")]
    Conflict { message: String },

    // --- 409 IDEMPOTENCY_KEY_REUSED: same Idempotency-Key, different request body ---
    #[error("idempotency key reused with a different request body")]
    IdempotencyKeyReused,

    // --- 422 BUSINESS_RULE_VIOLATION: valid shape, rejected by a domain rule ---
    #[error("business rule violation: {message}")]
    BusinessRule { message: String },

    // --- 429 RATE_LIMITED ---
    #[error("rate limited")]
    RateLimited { retry_after_secs: u64 },

    // --- 500 INTERNAL ---
    #[error("internal error: {0}")]
    Internal(#[source] BoxError),

    // --- 503 UNAVAILABLE: a dependency (DB, cache, upstream API) failed or timed out ---
    #[error("dependency {service} unavailable: {source}")]
    Unavailable {
        service: &'static str,
        #[source]
        source: BoxError,
    },
}
```

## IntoResponse Implementation for Axum

`impl IntoResponse for AppError` is the only code that writes an error response. The request id reaches it
through a task-local set by the outermost middleware, so no handler has to pass it along.

```rust
use axum::{
    extract::Request,
    http::{header, HeaderValue},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use uuid::Uuid;

/// Request id, also available to extractors as a request extension (see `AuthUser`).
#[derive(Clone, Debug)]
pub struct RequestId(pub String);

tokio::task_local! {
    /// The current request's id — in scope for the whole handler future (extractors, handler and
    /// `into_response`), so every error body carries it.
    static REQUEST_ID: String;
}

/// The current request's id; empty outside a request (e.g. plain unit tests).
pub fn current_request_id() -> String {
    REQUEST_ID.try_with(|id| id.clone()).unwrap_or_default()
}

/// Outermost middleware: keep a well-formed incoming X-Request-Id or mint one, and echo it on every
/// response. Add it last so it wraps everything else:
///   Router::new().nest("/api/v1/widgets", widget_routes())
///       .layer(middleware::from_fn(recovery_middleware))    // inner
///       .layer(middleware::from_fn(request_id_middleware))  // outer
pub async fn request_id_middleware(mut req: Request, next: Next) -> Response {
    let id = req.headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .filter(|s| {
            !s.is_empty()
                && s.len() <= 128
                && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        })
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    req.extensions_mut().insert(RequestId(id.clone()));
    let mut response = REQUEST_ID.scope(id.clone(), next.run(req)).await;
    if let Ok(value) = HeaderValue::from_str(&id) {
        response.headers_mut().insert("x-request-id", value);
    }
    response
}

/// Error envelope (api/response-envelope.md). An error body has no `data` key.
#[derive(Serialize)]
struct ErrorBody {
    error: ApiError,
}

#[derive(Serialize)]
struct ApiError {
    code: &'static str,
    message: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    details: Vec<FieldError>,
    request_id: String,
    retryable: bool,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let request_id = current_request_id();
        let status = self.status_code();

        // 5xx: the full cause chain goes to the log under request_id — never to the client.
        if status.is_server_error() {
            tracing::error!(error = %self, code = self.error_code(), request_id = %request_id, "request failed");
        }

        let body = ErrorBody {
            error: ApiError {
                code: self.error_code(),
                message: self.user_message(),
                details: self.details().to_vec(),
                request_id: request_id.clone(),
                retryable: self.retryable(),
            },
        };
        let mut response = (status, Json(body)).into_response();

        let headers = response.headers_mut();
        if !request_id.is_empty() {
            if let Ok(value) = HeaderValue::from_str(&request_id) {
                headers.insert("x-request-id", value);
            }
        }
        if let Some(secs) = self.retry_after_secs() {
            headers.insert(header::RETRY_AFTER, HeaderValue::from(secs));
        }
        if status == StatusCode::UNAUTHORIZED {
            headers.insert(header::WWW_AUTHENTICATE, HeaderValue::from_static("Bearer"));
        }

        response
    }
}
```

## Error Metadata Methods

```rust
impl AppError {
    /// HTTP status — the table in api/response-envelope.md. The status carries the class.
    pub fn status_code(&self) -> StatusCode {
        match self {
            Self::MalformedRequest(_) | Self::Validation { .. } => StatusCode::BAD_REQUEST,
            Self::Unauthenticated => StatusCode::UNAUTHORIZED,
            Self::Forbidden => StatusCode::FORBIDDEN,
            Self::NotFound { .. } => StatusCode::NOT_FOUND,
            Self::Conflict { .. } | Self::IdempotencyKeyReused => StatusCode::CONFLICT,
            Self::BusinessRule { .. } => StatusCode::UNPROCESSABLE_ENTITY,
            Self::RateLimited { .. } => StatusCode::TOO_MANY_REQUESTS,
            Self::Internal(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::Unavailable { .. } => StatusCode::SERVICE_UNAVAILABLE,
        }
    }

    /// Stable UPPER_SNAKE code clients branch on.
    pub fn error_code(&self) -> &'static str {
        match self {
            Self::MalformedRequest(_) => "MALFORMED_REQUEST",
            Self::Validation { .. } => "VALIDATION_FAILED",
            Self::Unauthenticated => "UNAUTHENTICATED",
            Self::Forbidden => "FORBIDDEN",
            Self::NotFound { .. } => "NOT_FOUND",
            Self::Conflict { .. } => "CONFLICT",
            Self::IdempotencyKeyReused => "IDEMPOTENCY_KEY_REUSED",
            Self::BusinessRule { .. } => "BUSINESS_RULE_VIOLATION",
            Self::RateLimited { .. } => "RATE_LIMITED",
            Self::Internal(_) => "INTERNAL",
            Self::Unavailable { .. } => "UNAVAILABLE",
        }
    }

    /// User-safe message; the UI shows it as-is. Every variant that wraps a cause gets fixed text —
    /// nothing from a parser, driver or upstream reaches the client.
    pub fn user_message(&self) -> String {
        match self {
            Self::MalformedRequest(_) => "The request could not be read.".to_owned(),
            Self::Validation { .. } => "Some fields are invalid.".to_owned(),
            Self::Unauthenticated => "Sign in to continue.".to_owned(),
            Self::Forbidden => "You don't have permission to do this.".to_owned(),
            Self::NotFound { resource } => format!("{resource} not found."),
            // Caller-authored, user-safe text (see the constructors)
            Self::Conflict { message } | Self::BusinessRule { message } => message.clone(),
            Self::IdempotencyKeyReused => {
                "This Idempotency-Key was already used with a different request.".to_owned()
            }
            Self::RateLimited { .. } => "Too many requests. Try again shortly.".to_owned(),
            Self::Internal(_) => "Something went wrong.".to_owned(),
            Self::Unavailable { .. } => "The service is temporarily unavailable.".to_owned(),
        }
    }

    /// Field-level problems (VALIDATION_FAILED only), serialized as error.details.
    pub fn details(&self) -> &[FieldError] {
        match self {
            Self::Validation { details } => details,
            _ => &[],
        }
    }

    /// Serialized as error.retryable.
    pub fn retryable(&self) -> bool {
        matches!(self, Self::RateLimited { .. } | Self::Unavailable { .. })
    }

    /// Seconds for the Retry-After header (429/503).
    pub fn retry_after_secs(&self) -> Option<u64> {
        match self {
            Self::RateLimited { retry_after_secs } => Some(*retry_after_secs),
            Self::Unavailable { .. } => Some(5),
            _ => None,
        }
    }
}
```

## Constructor Helpers

The codes and statuses are the table in `api/response-envelope.md`. Messages passed to `conflict` and
`business_rule` are shown to users as-is: write them for users, never pass an error's Display.

```rust
impl AppError {
    /// 400 MALFORMED_REQUEST — the parser error is kept as the cause (logged, never sent).
    pub fn malformed(err: impl Into<BoxError>) -> Self {
        Self::MalformedRequest(err.into())
    }

    /// 400 VALIDATION_FAILED for one field. `code` is lower_snake; `message` is fixed catalog text.
    pub fn validation(field: &str, code: &str, message: &str) -> Self {
        Self::Validation {
            details: vec![FieldError {
                field: field.to_owned(),
                code: code.to_owned(),
                message: message.to_owned(),
            }],
        }
    }

    /// 400 VALIDATION_FAILED from validator crate errors: stable codes + catalog messages.
    /// Validator messages and Display text never reach the client.
    pub fn validation_from_validator(err: validator::ValidationErrors) -> Self {
        let mut details = Vec::new();
        for (field, errors) in err.field_errors() {
            for e in errors {
                details.push(field_error(&field, &e.code));
            }
        }
        Self::Validation { details }
    }

    /// 404 NOT_FOUND — also for another tenant's or owner's object.
    pub fn not_found(resource: &'static str) -> Self {
        Self::NotFound { resource }
    }

    /// 409 CONFLICT — `message` is shown to the user.
    pub fn conflict(message: impl Into<String>) -> Self {
        Self::Conflict { message: message.into() }
    }

    /// 422 BUSINESS_RULE_VIOLATION — `message` is shown to the user.
    pub fn business_rule(message: impl Into<String>) -> Self {
        Self::BusinessRule { message: message.into() }
    }

    /// 429 RATE_LIMITED — sets Retry-After.
    pub fn rate_limited(retry_after_secs: u64) -> Self {
        Self::RateLimited { retry_after_secs }
    }

    /// 500 INTERNAL — the cause is logged under request_id, the client gets a generic message.
    pub fn internal(err: impl Into<BoxError>) -> Self {
        Self::Internal(err.into())
    }

    /// 503 UNAVAILABLE — a dependency failed or timed out. The service name goes to the log, not the client.
    pub fn unavailable(service: &'static str, err: impl Into<BoxError>) -> Self {
        Self::Unavailable { service, source: err.into() }
    }
}

/// validator codes → (stable lower_snake code, fixed user-safe message).
fn field_error(field: &str, validator_code: &str) -> FieldError {
    let (code, message) = match validator_code {
        "required" => ("required", "This field is required."),
        "length" => ("invalid_length", "This value is too short or too long."),
        "range" => ("out_of_range", "This value is out of range."),
        "email" => ("invalid_format", "Enter a valid email address."),
        "url" | "regex" => ("invalid_format", "This value has the wrong format."),
        _ => ("invalid", "This value is invalid."),
    };
    FieldError {
        field: field.to_owned(),
        code: code.to_owned(),
        message: message.to_owned(),
    }
}
```

## From Implementations for Common Error Types

```rust
/// sqlx database errors — the fallback for `?`. Repositories map with more context at their
/// boundary (crud-repository-rust.md). SQLSTATE picks the class; the constraint name and driver
/// text go to the log only.
impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        if matches!(err, sqlx::Error::RowNotFound) {
            return Self::not_found("Record");
        }
        if matches!(err, sqlx::Error::PoolTimedOut) {
            return Self::unavailable("postgres", err);
        }

        let db = err.as_database_error();
        let sql_state = db.and_then(|d| d.code()).map(|c| c.into_owned());
        let constraint = db.and_then(|d| d.constraint()).unwrap_or("unknown").to_owned();

        match sql_state.as_deref() {
            // unique_violation
            Some("23505") => {
                tracing::warn!(%constraint, "unique violation");
                Self::conflict("This already exists.")
            }
            // foreign_key_violation / check_violation
            Some("23503") | Some("23514") => {
                tracing::warn!(%constraint, sql_state = ?sql_state, "integrity violation");
                Self::business_rule("This change conflicts with related data.")
            }
            // query_canceled — statement_timeout fired
            Some("57014") => Self::unavailable("postgres", err),
            _ => Self::internal(err),
        }
    }
}

/// Redis errors via deadpool — the cache is a dependency: 503 UNAVAILABLE.
impl From<deadpool_redis::PoolError> for AppError {
    fn from(err: deadpool_redis::PoolError) -> Self {
        Self::unavailable("redis", err)
    }
}

impl From<redis::RedisError> for AppError {
    fn from(err: redis::RedisError) -> Self {
        Self::unavailable("redis", err)
    }
}

/// Serde JSON errors (request body parsing) → 400 MALFORMED_REQUEST; the parser text is only logged.
impl From<serde_json::Error> for AppError {
    fn from(err: serde_json::Error) -> Self {
        Self::malformed(err)
    }
}

/// UUID parse errors (path parameter parsing).
impl From<uuid::Error> for AppError {
    fn from(_: uuid::Error) -> Self {
        Self::validation("id", "invalid_format", "Must be a valid ID.")
    }
}

/// Generic string → Internal conversion.
impl From<String> for AppError {
    fn from(msg: String) -> Self {
        Self::internal(msg)
    }
}
```

### Extractors whose rejections are envelope errors

axum's own `Json`, `Path` and `Query` rejections are plain-text responses. Handlers use these wrappers
instead (needs `axum = { features = ["macros"] }`), so a bad body or path produces the error envelope:

```rust
use axum::extract::rejection::{JsonRejection, PathRejection, QueryRejection};
use axum::extract::{FromRequest, FromRequestParts};

#[derive(FromRequest)]
#[from_request(via(axum::Json), rejection(AppError))]
pub struct AppJson<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Path), rejection(AppError))]
pub struct AppPath<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Query), rejection(AppError))]
pub struct AppQuery<T>(pub T);

/// Unreadable JSON, wrong Content-Type, missing or mistyped fields → 400 MALFORMED_REQUEST.
impl From<JsonRejection> for AppError {
    fn from(rejection: JsonRejection) -> Self {
        Self::malformed(rejection)
    }
}

/// e.g. /widgets/not-a-uuid. Routes in this archetype have one path parameter, `{id}`.
impl From<PathRejection> for AppError {
    fn from(rejection: PathRejection) -> Self {
        tracing::debug!(%rejection, "path rejected");
        Self::validation("id", "invalid_format", "Must be a valid ID.")
    }
}

impl From<QueryRejection> for AppError {
    fn from(rejection: QueryRejection) -> Self {
        tracing::debug!(%rejection, "query rejected");
        Self::validation("query", "invalid_format", "The query string is not valid.")
    }
}
```

## Panic Recovery Middleware

```rust
use axum::{extract::Request, middleware::Next, response::Response};
use std::panic::AssertUnwindSafe;
use futures::FutureExt;

/// Catches panics and returns a 500 JSON response instead of dropping the connection.
/// This MUST be in the middleware stack (inside `request_id_middleware`) to prevent the server from crashing.
pub async fn recovery_middleware(req: Request, next: Next) -> Response {
    let result = AssertUnwindSafe(next.run(req)).catch_unwind().await;

    match result {
        Ok(response) => response,
        Err(panic_info) => {
            let panic_msg = if let Some(s) = panic_info.downcast_ref::<&str>() {
                (*s).to_owned()
            } else if let Some(s) = panic_info.downcast_ref::<String>() {
                s.clone()
            } else {
                "unknown panic".to_owned()
            };

            tracing::error!(panic = %panic_msg, request_id = %current_request_id(), "panic recovered in handler");

            // Clean 500 INTERNAL — the panic message stays in the log
            AppError::internal("panic recovered").into_response()
        }
    }
}
```

## Error Response Examples

The HTTP status carries the class; `X-Request-Id` header = `request_id`.

```json
// 400 MALFORMED_REQUEST (the parser's text is in the log line with the same request_id):
{
  "error": {
    "code": "MALFORMED_REQUEST",
    "message": "The request could not be read.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 400 VALIDATION_FAILED:
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Some fields are invalid.",
    "details": [
      { "field": "name", "code": "invalid_length", "message": "This value is too short or too long." },
      { "field": "email", "code": "invalid_format", "message": "Enter a valid email address." }
    ],
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 404 NOT_FOUND (also for another tenant's widget — don't confirm it exists):
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Widget not found.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 409 CONFLICT:
{
  "error": {
    "code": "CONFLICT",
    "message": "This widget was changed by someone else. Reload and try again.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 429 RATE_LIMITED (with header Retry-After: 30):
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Try again shortly.",
    "request_id": "b7e1c2…",
    "retryable": true
  }
}

// 500 INTERNAL (the cause is in the log line with the same request_id):
{
  "error": {
    "code": "INTERNAL",
    "message": "Something went wrong.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 503 UNAVAILABLE (with header Retry-After: 5):
{
  "error": {
    "code": "UNAVAILABLE",
    "message": "The service is temporarily unavailable.",
    "request_id": "b7e1c2…",
    "retryable": true
  }
}
```

## Error Wrapping Guidelines

```rust
// --- WRAPPING RULES ---
//
// 1. Use the ? operator with From implementations — errors convert automatically.
//
//    let widget = sqlx::query_as!(Widget, ...)
//        .fetch_optional(&pool).await?  // sqlx::Error → AppError via From
//        .ok_or_else(|| AppError::not_found("Widget"))?;
//
// 2. Create domain errors at the BOUNDARY where you know the error type.
//
//    // In the repository — this is where we know "no rows" means "not found":
//    .ok_or_else(|| AppError::not_found("Widget"))?;
//
//    // NOT in the handler — the handler shouldn't know about sqlx internals.
//
// 3. Use .map_err() when you need to add context beyond what From provides.
//
//    self.repo.create(&widget).await.map_err(|e| {
//        tracing::error!(error = %e, "widget create failed");
//        e
//    })?;
//
// 4. Log errors at the TOP of the call stack (handler/middleware), not at every layer.
//    The IntoResponse impl logs 5xx errors automatically, with request_id.
//
// 5. Never use anyhow::Error in service/handler code — always use AppError.
//    anyhow is acceptable only in CLI tools or one-off scripts.
```

## Testing Error Types

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use axum::response::IntoResponse;

    #[test]
    fn test_not_found_status() {
        let err = AppError::not_found("Widget");
        assert_eq!(err.status_code(), StatusCode::NOT_FOUND);
        assert_eq!(err.error_code(), "NOT_FOUND");
        assert_eq!(err.user_message(), "Widget not found.");
        assert!(!err.retryable());
    }

    #[test]
    fn test_internal_hides_details() {
        let err = AppError::internal("database connection reset by peer");
        assert_eq!(err.user_message(), "Something went wrong.");
        assert_eq!(err.error_code(), "INTERNAL");
    }

    #[test]
    fn test_validation_is_400_with_field_details() {
        let err = AppError::validation("email", "invalid_format", "Enter a valid email address.");
        assert_eq!(err.status_code(), StatusCode::BAD_REQUEST);
        assert_eq!(err.error_code(), "VALIDATION_FAILED");
        assert_eq!(err.details()[0].field, "email");
        assert_eq!(err.details()[0].code, "invalid_format");
    }

    #[test]
    fn test_unavailable_is_retryable_with_retry_after() {
        let err = AppError::unavailable("postgres", "statement timeout");
        assert_eq!(err.status_code(), StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(err.error_code(), "UNAVAILABLE");
        assert!(err.retryable());
        assert_eq!(err.retry_after_secs(), Some(5));
    }

    #[tokio::test]
    async fn test_error_body_is_the_envelope_and_hides_the_cause() {
        let resp = AppError::internal("pool exhausted: 50/50 connections busy").into_response();
        assert_eq!(resp.status(), StatusCode::INTERNAL_SERVER_ERROR);

        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        let body: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert!(body.get("data").is_none(), "an error body has no 'data' key");
        assert_eq!(body["error"]["code"], "INTERNAL");
        assert_eq!(body["error"]["retryable"], false);
        assert!(body["error"].get("request_id").is_some());
        assert!(!String::from_utf8_lossy(&bytes).contains("pool"), "the cause must not leak");
    }
}
```

## Error Taxonomy Summary

| Error Variant | HTTP Status | Code | When to Use |
|---|---|---|---|
| `MalformedRequest` | 400 | `MALFORMED_REQUEST` | Malformed JSON, wrong content type, body too large |
| `Validation` | 400 | `VALIDATION_FAILED` | Input fails schema/validation — `details[]` lists `{field, code, message}` |
| `Unauthenticated` | 401 | `UNAUTHENTICATED` | Missing, invalid or expired credentials (sets `WWW-Authenticate: Bearer`) |
| `Forbidden` | 403 | `FORBIDDEN` | Authenticated but not allowed (function-level) |
| `NotFound` | 404 | `NOT_FOUND` | Doesn't exist, soft-deleted, **or belongs to another tenant/owner** |
| `Conflict` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `IdempotencyKeyReused` | 409 | `IDEMPOTENCY_KEY_REUSED` | Idempotency-Key replayed with a different body |
| `BusinessRule` | 422 | `BUSINESS_RULE_VIOLATION` | Valid shape, rejected by a domain rule |
| `RateLimited` | 429 | `RATE_LIMITED` | Too many requests (`Retry-After`, `retryable: true`) |
| `Internal` | 500 | `INTERNAL` | Unexpected server error — never expose details |
| `Unavailable` | 503 | `UNAVAILABLE` | A dependency (DB, cache, upstream) failed or timed out (`Retry-After`, `retryable: true`) |

## Critical Rules

- Every error returned from service/repo layers MUST be an `AppError` variant — no raw `Box<dyn Error>` crossing boundaries
- `impl IntoResponse for AppError` is the ONLY place that writes an error body: `{"error": {code, message, details?, request_id, retryable}}`, never a `data` key
- Every error body carries `request_id` (= the `X-Request-Id` header, from `request_id_middleware`) and `retryable`
- No client-visible field ever contains an error's Display/Debug text, SQL, a constraint name, a driver/upstream message, a path or a stack trace
- Internal error messages (500, 503) MUST NOT leak to clients — always return the generic message
- Validation errors (400 `VALIDATION_FAILED`) carry `details[]` of `{field, code, message}` from a fixed catalog
- Business-rule rejections are 422 `BUSINESS_RULE_VIOLATION`; malformed bodies are 400 `MALFORMED_REQUEST`
- DB errors: unique violation → 409 `CONFLICT`, FK/check violation → 422 `BUSINESS_RULE_VIOLATION`, statement/pool timeout → 503 `UNAVAILABLE`, each with a generic message
- Handlers MUST extract with `AppJson` / `AppPath` / `AppQuery` so rejections become envelope errors
- `From` impls MUST exist for all infrastructure errors (sqlx, redis, serde, uuid, axum rejections) — enables `?` operator
- Log errors ONCE at the top of the call stack — the `IntoResponse` impl handles 5xx logging
- Create domain errors at the BOUNDARY where you know the error type (repo maps sqlx errors, service maps business rules)
- Panic recovery middleware MUST be in the stack — panics MUST NOT crash the server
- Rate limit (429) and unavailable (503) responses MUST include the `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer`
- Never use `unwrap()` or `expect()` in handler/service code — always propagate with `?`
- Use `thiserror` for the error enum — it generates `Display` and `Error` impls correctly
