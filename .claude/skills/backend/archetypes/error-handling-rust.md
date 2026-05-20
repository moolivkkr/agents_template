---
skill: error-handling-rust
description: Rust error handling archetype — AppError enum with thiserror, IntoResponse for Axum, JSON error envelope, From implementations, tracing integration
version: "1.0"
tags:
  - rust
  - errors
  - axum
  - archetype
  - backend
---

# Error Handling Archetype (Rust)

> **CANONICAL REFERENCE**: This file is the single source of truth for Rust backend error handling patterns. All other Rust skill packs that mention error handling should defer to this file for definitive guidance. For the Go equivalent, see `backend/archetypes/error-handling.md`.

Complete error handling system for Rust backend services using Axum. Every generated service MUST follow this pattern.

## AppError Enum (thiserror)

```rust
use axum::http::StatusCode;
use serde::Serialize;
use thiserror::Error;

/// AppError is the standard application error type.
/// All domain errors MUST use this enum so the IntoResponse impl can map them to HTTP responses.
#[derive(Debug, Error)]
pub enum AppError {
    // --- 400 Bad Request: Malformed Request ---
    #[error("bad request: {0}")]
    BadRequest(String),

    // --- 422 Unprocessable Entity: Business Validation Errors ---
    #[error("validation error: {message}")]
    Validation {
        message: String,
        details: Option<serde_json::Value>,
    },

    // --- 401 Unauthorized: Authentication Errors ---
    #[error("unauthorized: {0}")]
    Unauthorized(String),

    // --- 403 Forbidden: Authorization Errors ---
    #[error("forbidden: insufficient permissions to {action} {resource}")]
    Forbidden { action: String, resource: String },

    // --- 404 Not Found ---
    #[error("{resource} not found")]
    NotFound { resource: String, identifier: String },

    // --- 409 Conflict: Duplicate / Version Mismatch ---
    #[error("{resource} conflict: {reason}")]
    Conflict { resource: String, reason: String },

    // --- 429 Too Many Requests ---
    #[error("rate limited")]
    RateLimited { retry_after_secs: u64 },

    // --- 500 Internal Server Error ---
    #[error("internal error")]
    Internal(#[source] Box<dyn std::error::Error + Send + Sync>),

    // --- 502 Bad Gateway: Upstream Failure ---
    #[error("upstream service '{service}' is unavailable")]
    Upstream {
        service: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },
}
```

## IntoResponse Implementation for Axum

```rust
use axum::response::{IntoResponse, Response};
use axum::Json;

/// JSON error response body — standard envelope for all error responses.
#[derive(Serialize)]
struct ErrorResponse {
    error: ErrorDetail,
}

#[derive(Serialize)]
struct ErrorDetail {
    code: &'static str,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    details: Option<serde_json::Value>,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        // Log server-side errors with full context; client gets sanitized message.
        if self.status_code().is_server_error() {
            tracing::error!(error = %self, "server error");
        }

        let status = self.status_code();
        let body = ErrorResponse {
            error: ErrorDetail {
                code: self.error_code(),
                message: self.user_message(),
                details: self.details(),
            },
        };

        let mut response = (status, Json(body)).into_response();

        // Add Retry-After header for rate limit errors
        if let AppError::RateLimited { retry_after_secs } = &self {
            response.headers_mut().insert(
                "retry-after",
                retry_after_secs.to_string().parse().unwrap(),
            );
        }

        response
    }
}
```

## Error Metadata Methods

```rust
impl AppError {
    /// HTTP status code for this error variant.
    pub fn status_code(&self) -> StatusCode {
        match self {
            Self::BadRequest(_) => StatusCode::BAD_REQUEST,
            Self::Validation { .. } => StatusCode::UNPROCESSABLE_ENTITY,
            Self::Unauthorized(_) => StatusCode::UNAUTHORIZED,
            Self::Forbidden { .. } => StatusCode::FORBIDDEN,
            Self::NotFound { .. } => StatusCode::NOT_FOUND,
            Self::Conflict { .. } => StatusCode::CONFLICT,
            Self::RateLimited { .. } => StatusCode::TOO_MANY_REQUESTS,
            Self::Internal(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::Upstream { .. } => StatusCode::BAD_GATEWAY,
        }
    }

    /// Machine-readable error code for client consumption.
    pub fn error_code(&self) -> &'static str {
        match self {
            Self::BadRequest(_) => "BAD_REQUEST",
            Self::Validation { .. } => "VALIDATION_ERROR",
            Self::Unauthorized(_) => "UNAUTHORIZED",
            Self::Forbidden { .. } => "FORBIDDEN",
            Self::NotFound { .. } => "NOT_FOUND",
            Self::Conflict { .. } => "CONFLICT",
            Self::RateLimited { .. } => "RATE_LIMITED",
            Self::Internal(_) => "INTERNAL_ERROR",
            Self::Upstream { .. } => "UPSTREAM_ERROR",
        }
    }

    /// Human-readable message safe for client consumption.
    /// Internal errors get a generic message — never expose stack traces or DB errors.
    pub fn user_message(&self) -> String {
        match self {
            Self::BadRequest(msg) => msg.clone(),
            Self::Validation { message, .. } => message.clone(),
            Self::Unauthorized(msg) => msg.clone(),
            Self::Forbidden { action, resource } => {
                format!("insufficient permissions to {action} {resource}")
            }
            Self::NotFound { resource, identifier } => {
                if identifier.is_empty() {
                    format!("{resource} not found")
                } else {
                    format!("{resource} '{identifier}' not found")
                }
            }
            Self::Conflict { resource, reason } => {
                format!("{resource} conflict: {reason}")
            }
            Self::RateLimited { .. } => {
                "too many requests -- please retry later".to_owned()
            }
            // Never expose internal details to clients
            Self::Internal(_) => "an unexpected error occurred".to_owned(),
            Self::Upstream { service, .. } => {
                format!("upstream service '{service}' is unavailable")
            }
        }
    }

    /// Optional structured details for the error response.
    pub fn details(&self) -> Option<serde_json::Value> {
        match self {
            Self::Validation { details, .. } => details.clone(),
            Self::Forbidden { action, resource } => Some(serde_json::json!({
                "action": action,
                "resource": resource,
            })),
            Self::NotFound { resource, identifier } => Some(serde_json::json!({
                "resource": resource,
                "identifier": identifier,
            })),
            Self::Conflict { resource, reason } => Some(serde_json::json!({
                "resource": resource,
                "reason": reason,
            })),
            Self::RateLimited { retry_after_secs } => Some(serde_json::json!({
                "retry_after_seconds": retry_after_secs,
            })),
            Self::Upstream { service, .. } => Some(serde_json::json!({
                "service": service,
            })),
            _ => None,
        }
    }
}
```

## Constructor Helpers

```rust
impl AppError {
    /// Create a Validation error from validator crate errors.
    pub fn validation_from_validator(err: validator::ValidationErrors) -> Self {
        let field_errors: serde_json::Value = serde_json::to_value(
            err.field_errors()
                .into_iter()
                .map(|(field, errors)| {
                    let messages: Vec<String> = errors
                        .iter()
                        .filter_map(|e| e.message.as_ref().map(|m| m.to_string()))
                        .collect();
                    (field.to_owned(), messages)
                })
                .collect::<std::collections::HashMap<String, Vec<String>>>()
        )
        .unwrap_or_default();

        Self::Validation {
            message: "one or more fields failed validation".into(),
            details: Some(serde_json::json!({ "fields": field_errors })),
        }
    }

    /// Create a Validation error for a single field.
    pub fn validation_field(field: &str, reason: &str) -> Self {
        Self::Validation {
            message: format!("invalid value for field '{field}'"),
            details: Some(serde_json::json!({ "field": field, "reason": reason })),
        }
    }

    /// Wrap a generic error as Internal.
    pub fn internal(err: impl std::error::Error + Send + Sync + 'static) -> Self {
        Self::Internal(Box::new(err))
    }

    /// Wrap a string message as Internal (when no source error exists).
    pub fn internal_msg(msg: impl Into<String>) -> Self {
        Self::Internal(msg.into().into())
    }
}
```

## From Implementations for Common Error Types

```rust
/// sqlx database errors — map at the repository boundary.
impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        match &err {
            sqlx::Error::RowNotFound => Self::NotFound {
                resource: "record".into(),
                identifier: String::new(),
            },
            sqlx::Error::Database(db_err) => {
                if let Some(code) = db_err.code() {
                    match code.as_ref() {
                        "23505" => return Self::Conflict {
                            resource: "record".into(),
                            reason: format!(
                                "duplicate value on {}",
                                db_err.constraint().unwrap_or("unknown")
                            ),
                        },
                        "23503" => return Self::Validation {
                            message: "referenced resource does not exist".into(),
                            details: None,
                        },
                        _ => {}
                    }
                }
                Self::Internal(Box::new(err))
            }
            _ => Self::Internal(Box::new(err)),
        }
    }
}

/// Redis errors via deadpool.
impl From<deadpool_redis::PoolError> for AppError {
    fn from(err: deadpool_redis::PoolError) -> Self {
        tracing::error!(error = %err, "redis pool error");
        Self::Internal(Box::new(err))
    }
}

impl From<redis::RedisError> for AppError {
    fn from(err: redis::RedisError) -> Self {
        tracing::error!(error = %err, "redis error");
        Self::Internal(Box::new(err))
    }
}

/// Serde JSON errors (request body parsing).
impl From<serde_json::Error> for AppError {
    fn from(err: serde_json::Error) -> Self {
        Self::BadRequest(format!("invalid JSON: {err}"))
    }
}

/// Axum JSON rejection (malformed request body).
impl From<axum::extract::rejection::JsonRejection> for AppError {
    fn from(err: axum::extract::rejection::JsonRejection) -> Self {
        Self::BadRequest(format!("invalid request body: {err}"))
    }
}

/// UUID parse errors (path parameter parsing).
impl From<uuid::Error> for AppError {
    fn from(_: uuid::Error) -> Self {
        Self::Validation {
            message: "invalid UUID format".into(),
            details: None,
        }
    }
}

/// Generic string → Internal conversion.
impl From<String> for AppError {
    fn from(msg: String) -> Self {
        Self::Internal(msg.into())
    }
}
```

## Panic Recovery Middleware

```rust
use axum::{extract::Request, middleware::Next, response::Response};
use std::panic::AssertUnwindSafe;
use futures::FutureExt;

/// Catches panics and returns a 500 JSON response instead of dropping the connection.
/// This MUST be in the middleware stack to prevent the server from crashing.
pub async fn recovery_middleware(req: Request, next: Next) -> Response {
    let result = AssertUnwindSafe(next.run(req)).catch_unwind().await;

    match result {
        Ok(response) => response,
        Err(panic_info) => {
            let panic_msg = if let Some(s) = panic_info.downcast_ref::<&str>() {
                s.to_string()
            } else if let Some(s) = panic_info.downcast_ref::<String>() {
                s.clone()
            } else {
                "unknown panic".to_owned()
            };

            tracing::error!(panic = %panic_msg, "panic recovered in handler");

            AppError::internal_msg("panic recovered").into_response()
        }
    }
}
```

## Error Response Examples

```json
// 400 Bad Request (malformed input):
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "invalid JSON: expected `,` or `}` at line 3 column 1"
  }
}

// 422 Validation Error (business rule violation):
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "one or more fields failed validation",
    "details": {
      "fields": {
        "name": ["name must be 1-255 characters"],
        "email": ["invalid email format"]
      }
    }
  }
}

// 404 Not Found:
{
  "error": {
    "code": "NOT_FOUND",
    "message": "widget 'abc-123' not found",
    "details": { "resource": "widget", "identifier": "abc-123" }
  }
}

// 409 Conflict:
{
  "error": {
    "code": "CONFLICT",
    "message": "widget conflict: version mismatch -- reload and retry",
    "details": { "resource": "widget", "reason": "version mismatch" }
  }
}

// 429 Rate Limited:
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "too many requests -- please retry later",
    "details": { "retry_after_seconds": 30 }
  }
}

// 500 Internal Error:
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "an unexpected error occurred"
  }
}
```

## Error Wrapping Guidelines

```rust
// --- WRAPPING RULES ---
// 1. Use the ? operator with From implementations — errors convert automatically.
//    let widget = sqlx::query_as!(Widget, ...)
//        .fetch_optional(&pool).await?  // sqlx::Error → AppError via From
//        .ok_or_else(|| AppError::NotFound { .. })?;
// 2. Create domain errors at the BOUNDARY where you know the error type.
//    // In the repository — this is where we know "no rows" means "not found":
//    .ok_or_else(|| AppError::NotFound {
//        resource: "widget".into(),
//        identifier: id.to_string(),
//    })?;
//    // NOT in the handler — the handler shouldn't know about sqlx internals.
// 3. Use .map_err() when you need to add context beyond what From provides.
//    self.repo.create(&widget).await.map_err(|e| {
//        tracing::error!(error = %e, "widget create failed");
//        e
//    })?;
// 4. Log errors at the TOP of the call stack (handler/middleware), not at every layer.
//    The IntoResponse impl logs 5xx errors automatically.
// 5. Never use anyhow::Error in service/handler code — always use AppError.
//    anyhow is acceptable only in CLI tools or one-off scripts.
```

## Testing Error Types

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;

    #[test]
    fn test_not_found_status() {
        let err = AppError::NotFound {
            resource: "widget".into(),
            identifier: "abc".into(),
        };
        assert_eq!(err.status_code(), StatusCode::NOT_FOUND);
        assert_eq!(err.error_code(), "NOT_FOUND");
        assert!(err.user_message().contains("widget"));
    }

    #[test]
    fn test_internal_hides_details() {
        let err = AppError::internal_msg("database connection reset by peer");
        assert_eq!(err.user_message(), "an unexpected error occurred");
        assert_eq!(err.error_code(), "INTERNAL_ERROR");
    }

    #[test]
    fn test_validation_from_validator() {
        // validator crate integration tested via the service layer tests
        let err = AppError::validation_field("email", "invalid format");
        assert_eq!(err.status_code(), StatusCode::UNPROCESSABLE_ENTITY);
        assert!(err.details().is_some());
    }

    #[test]
    fn test_conflict_details() {
        let err = AppError::Conflict {
            resource: "widget".into(),
            reason: "version mismatch".into(),
        };
        let details = err.details().unwrap();
        assert_eq!(details["resource"], "widget");
        assert_eq!(details["reason"], "version mismatch");
    }
}
```

## Error Taxonomy Summary

| Error Variant | HTTP Status | Code | When to Use |
|---|---|---|---|
| `BadRequest` | 400 | `BAD_REQUEST` | Malformed JSON, wrong content type, request parsing failure |
| `Validation` | 422 | `VALIDATION_ERROR` | Well-formed request that fails business/domain validation rules |
| `Unauthorized` | 401 | `UNAUTHORIZED` | Missing or invalid credentials (JWT, API key) |
| `Forbidden` | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `NotFound` | 404 | `NOT_FOUND` | Resource does not exist or was soft-deleted |
| `Conflict` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `RateLimited` | 429 | `RATE_LIMITED` | Too many requests from tenant/user |
| `Internal` | 500 | `INTERNAL_ERROR` | Unexpected server error — never expose details |
| `Upstream` | 502 | `UPSTREAM_ERROR` | External service (CA, email, webhook) failure |

## Critical Rules

- Every error returned from service/repo layers MUST be an `AppError` variant — no raw `Box<dyn Error>` crossing boundaries
- Internal error messages (500, 502) MUST NOT leak to clients — always return generic message
- Validation errors (422) SHOULD include the field name and reason in `details`
- Bad request errors (400) are for malformed JSON/request parsing — NOT business validation
- `From` impls MUST exist for all infrastructure errors (sqlx, redis, serde, uuid) — enables `?` operator
- Log errors ONCE at the top of the call stack — the `IntoResponse` impl handles 5xx logging
- Create domain errors at the BOUNDARY where you know the error type (repo maps sqlx errors, service maps business rules)
- Panic recovery middleware MUST be in the stack — panics MUST NOT crash the server
- Rate limit responses MUST include `Retry-After` header
- Never use `unwrap()` or `expect()` in handler/service code — always propagate with `?`
- Use `thiserror` for the error enum — it generates `Display` and `Error` impls correctly
