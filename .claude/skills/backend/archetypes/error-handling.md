---
skill: error-handling
description: Go error handling archetype — domain error taxonomy, error types, HTTP mapping, error middleware, sentinel errors, wrapping guidelines
version: "1.0"
tags:
  - go
  - errors
  - middleware
  - archetype
  - backend
---

# Error Handling Archetype

Complete error handling system for Go backend services. Every generated service MUST follow this pattern.

## Domain Error Type

```go
package apperr

import (
    "errors"
    "fmt"
    "log/slog"
    "net/http"
    "runtime"
)

// AppError is the standard application error type.
// All domain errors MUST use this type so the error middleware can map them to HTTP responses.
type AppError struct {
    Code       string         `json:"code"`        // machine-readable: VALIDATION_ERROR, NOT_FOUND, etc.
    Message    string         `json:"message"`      // human-readable message safe for clients
    HTTPStatus int            `json:"-"`            // HTTP status code (not serialized to client)
    Details    map[string]any `json:"details,omitempty"` // optional structured details
    Err        error          `json:"-"`            // wrapped underlying error (not serialized)
}

// Error implements the error interface.
func (e *AppError) Error() string {
    if e.Err != nil {
        return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.Err)
    }
    return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// Unwrap supports errors.Is and errors.As for wrapped errors.
func (e *AppError) Unwrap() error {
    return e.Err
}

// Is supports errors.Is comparison by error code.
func (e *AppError) Is(target error) bool {
    var appErr *AppError
    if errors.As(target, &appErr) {
        return e.Code == appErr.Code
    }
    return false
}

// WithDetails adds structured context to the error.
func (e *AppError) WithDetails(key string, value any) *AppError {
    if e.Details == nil {
        e.Details = make(map[string]any)
    }
    e.Details[key] = value
    return e
}

// WithError wraps an underlying error for debugging while keeping the client message clean.
func (e *AppError) WithError(err error) *AppError {
    e.Err = err
    return e
}
```

## Error Taxonomy — Constructor Functions

```go
// --- 400 Bad Request: Validation Errors ---

func NewValidationError(field string, err error) *AppError {
    return &AppError{
        Code:       "VALIDATION_ERROR",
        Message:    fmt.Sprintf("invalid value for field '%s'", field),
        HTTPStatus: http.StatusBadRequest,
        Details:    map[string]any{"field": field, "reason": err.Error()},
        Err:        err,
    }
}

func NewMultiValidationError(fieldErrors map[string]string) *AppError {
    return &AppError{
        Code:       "VALIDATION_ERROR",
        Message:    "one or more fields failed validation",
        HTTPStatus: http.StatusBadRequest,
        Details:    map[string]any{"fields": fieldErrors},
    }
}

// --- 401 Unauthorized: Authentication Errors ---

func NewUnauthorizedError(reason string) *AppError {
    return &AppError{
        Code:       "UNAUTHORIZED",
        Message:    reason,
        HTTPStatus: http.StatusUnauthorized,
    }
}

// --- 403 Forbidden: Authorization Errors ---

func NewForbiddenError(action, resource string) *AppError {
    return &AppError{
        Code:       "FORBIDDEN",
        Message:    fmt.Sprintf("insufficient permissions to %s %s", action, resource),
        HTTPStatus: http.StatusForbidden,
        Details:    map[string]any{"action": action, "resource": resource},
    }
}

// --- 404 Not Found ---

func NewNotFoundError(resource, identifier string) *AppError {
    msg := fmt.Sprintf("%s not found", resource)
    if identifier != "" {
        msg = fmt.Sprintf("%s '%s' not found", resource, identifier)
    }
    return &AppError{
        Code:       "NOT_FOUND",
        Message:    msg,
        HTTPStatus: http.StatusNotFound,
        Details:    map[string]any{"resource": resource, "identifier": identifier},
    }
}

// --- 409 Conflict: Duplicate / Version Mismatch ---

func NewConflictError(resource, reason string) *AppError {
    return &AppError{
        Code:       "CONFLICT",
        Message:    fmt.Sprintf("%s conflict: %s", resource, reason),
        HTTPStatus: http.StatusConflict,
        Details:    map[string]any{"resource": resource, "reason": reason},
    }
}

// --- 429 Too Many Requests ---

func NewRateLimitError(retryAfterSecs int) *AppError {
    return &AppError{
        Code:       "RATE_LIMITED",
        Message:    "too many requests — please retry later",
        HTTPStatus: http.StatusTooManyRequests,
        Details:    map[string]any{"retry_after_seconds": retryAfterSecs},
    }
}

// --- 500 Internal Server Error ---

func NewInternalError(err error) *AppError {
    return &AppError{
        Code:       "INTERNAL_ERROR",
        Message:    "an unexpected error occurred",
        HTTPStatus: http.StatusInternalServerError,
        Err:        err,
    }
}

// --- 502 Bad Gateway: Upstream Failure ---

func NewUpstreamError(service string, err error) *AppError {
    return &AppError{
        Code:       "UPSTREAM_ERROR",
        Message:    fmt.Sprintf("upstream service '%s' is unavailable", service),
        HTTPStatus: http.StatusBadGateway,
        Details:    map[string]any{"service": service},
        Err:        err,
    }
}
```

## Sentinel Errors for Common Cases

```go
// Sentinel errors for use with errors.Is() checks.
// Use these when you need to check for a specific error condition
// without constructing a full AppError.

var (
    ErrNotFound     = &AppError{Code: "NOT_FOUND", HTTPStatus: http.StatusNotFound}
    ErrUnauthorized = &AppError{Code: "UNAUTHORIZED", HTTPStatus: http.StatusUnauthorized}
    ErrForbidden    = &AppError{Code: "FORBIDDEN", HTTPStatus: http.StatusForbidden}
    ErrConflict     = &AppError{Code: "CONFLICT", HTTPStatus: http.StatusConflict}
    ErrRateLimited  = &AppError{Code: "RATE_LIMITED", HTTPStatus: http.StatusTooManyRequests}
    ErrInternal     = &AppError{Code: "INTERNAL_ERROR", HTTPStatus: http.StatusInternalServerError}
)

// Usage:
//   if errors.Is(err, apperr.ErrNotFound) {
//       // handle not found case
//   }
```

## HTTP Error Response Format

```go
// ErrorResponse is the standard JSON error response body.
// Every error response MUST use this format for client consistency.
type ErrorResponse struct {
    Error ErrorDetail `json:"error"`
}

type ErrorDetail struct {
    Code    string         `json:"code"`              // machine-readable error code
    Message string         `json:"message"`           // human-readable description
    Details map[string]any `json:"details,omitempty"`  // optional structured context
}

// Example error responses:
//
// 400 Validation Error:
// {
//   "error": {
//     "code": "VALIDATION_ERROR",
//     "message": "invalid value for field 'email'",
//     "details": { "field": "email", "reason": "invalid format" }
//   }
// }
//
// 404 Not Found:
// {
//   "error": {
//     "code": "NOT_FOUND",
//     "message": "widget 'abc-123' not found",
//     "details": { "resource": "widget", "identifier": "abc-123" }
//   }
// }
//
// 409 Conflict:
// {
//   "error": {
//     "code": "CONFLICT",
//     "message": "widget conflict: version mismatch — reload and retry",
//     "details": { "resource": "widget", "reason": "version mismatch" }
//   }
// }
//
// 500 Internal Error:
// {
//   "error": {
//     "code": "INTERNAL_ERROR",
//     "message": "an unexpected error occurred"
//   }
// }
```

## Error Mapping Middleware

```go
// RecoveryMiddleware catches panics, logs the stack trace, and returns a 500 response.
// This MUST be in the middleware stack to prevent the server from crashing.
func RecoveryMiddleware(logger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            defer func() {
                if rec := recover(); rec != nil {
                    // Capture stack trace
                    buf := make([]byte, 4096)
                    n := runtime.Stack(buf, false)
                    stack := string(buf[:n])

                    reqID := RequestIDFromContext(r.Context())

                    logger.Error("panic recovered",
                        "panic", rec,
                        "stack", stack,
                        "request_id", reqID,
                        "method", r.Method,
                        "path", r.URL.Path,
                    )

                    // Return a clean 500 — never expose panic details to clients
                    w.Header().Set("Content-Type", "application/json; charset=utf-8")
                    w.WriteHeader(http.StatusInternalServerError)
                    fmt.Fprintf(w, `{"error":{"code":"INTERNAL_ERROR","message":"an unexpected error occurred"}}`)
                }
            }()

            next.ServeHTTP(w, r)
        })
    }
}

// ErrorMapper is a helper that maps AppError types to HTTP responses.
// Use this in handlers instead of duplicating mapping logic.
func ErrorMapper(w http.ResponseWriter, err error) {
    var appErr *AppError
    if errors.As(err, &appErr) {
        // Log internal errors with full detail; client gets sanitized message
        if appErr.HTTPStatus >= 500 {
            slog.Error("internal error",
                "code", appErr.Code,
                "message", appErr.Message,
                "error", appErr.Err,
            )
        }

        w.Header().Set("Content-Type", "application/json; charset=utf-8")

        // Add Retry-After header for rate limit errors
        if appErr.HTTPStatus == http.StatusTooManyRequests {
            if retryAfter, ok := appErr.Details["retry_after_seconds"]; ok {
                w.Header().Set("Retry-After", fmt.Sprintf("%v", retryAfter))
            }
        }

        w.WriteHeader(appErr.HTTPStatus)
        json.NewEncoder(w).Encode(ErrorResponse{
            Error: ErrorDetail{
                Code:    appErr.Code,
                Message: appErr.Message,
                Details: appErr.Details,
            },
        })
        return
    }

    // Unknown error type — treat as 500, never expose message
    slog.Error("unmapped error", "error", err)
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    w.WriteHeader(http.StatusInternalServerError)
    fmt.Fprintf(w, `{"error":{"code":"INTERNAL_ERROR","message":"an unexpected error occurred"}}`)
}
```

## Error Wrapping Guidelines

```go
// --- WRAPPING RULES ---
//
// 1. Wrap at boundaries — add context when crossing layers (handler → service → repo).
//
//    // In service layer:
//    cert, err := s.repo.GetByID(ctx, id)
//    if err != nil {
//        return nil, fmt.Errorf("certificate get: %w", err) // adds context, preserves original
//    }
//
// 2. Never double-wrap domain errors — if the error is already an AppError, return it directly.
//
//    var appErr *AppError
//    if errors.As(err, &appErr) {
//        return nil, err // already a domain error — don't re-wrap
//    }
//    return nil, NewInternalError(err) // unknown error — wrap as internal
//
// 3. Create domain errors at the boundary where you KNOW the error type.
//
//    // In repository — this is where we know "no rows" means "not found":
//    if errors.Is(err, pgx.ErrNoRows) {
//        return nil, apperr.NewNotFoundError("widget", id.String())
//    }
//    // NOT in the handler — the handler shouldn't know about pgx.
//
// 4. Log the wrapped error at the TOP of the call stack (handler/middleware), not at every layer.
//
//    // ✅ Handler logs once:
//    result, err := h.svc.Create(ctx, input)
//    if err != nil {
//        logger.Error("create failed", "error", err) // full chain visible
//        ErrorMapper(w, err)
//        return
//    }
//
//    // ❌ Don't log at every layer — you get duplicate log lines.
//
// 5. Preserve the error chain for debugging.
//
//    // The error chain should read like a call stack:
//    // "widget create: persistence: unique_violation on idx_widgets_name"
//    //  ↑ service      ↑ repo         ↑ pgx mapping
```

## Testing Error Types

```go
// Testing helpers — use in unit tests to assert specific error types.

func TestServiceReturnsNotFound(t *testing.T) {
    svc := NewService(mockRepo{getErr: apperr.NewNotFoundError("widget", "abc")}, ...)
    _, err := svc.Get(ctx, uuid.MustParse("abc"))

    // Assert using errors.Is with sentinel
    assert.True(t, errors.Is(err, apperr.ErrNotFound))

    // Assert using errors.As for detailed inspection
    var appErr *apperr.AppError
    require.True(t, errors.As(err, &appErr))
    assert.Equal(t, "NOT_FOUND", appErr.Code)
    assert.Equal(t, http.StatusNotFound, appErr.HTTPStatus)
}

func TestServiceReturnsConflict(t *testing.T) {
    svc := NewService(mockRepo{updateErr: apperr.NewConflictError("widget", "version mismatch")}, ...)
    _, err := svc.Update(ctx, id, input)

    var appErr *apperr.AppError
    require.True(t, errors.As(err, &appErr))
    assert.Equal(t, "CONFLICT", appErr.Code)
    assert.Equal(t, http.StatusConflict, appErr.HTTPStatus)
}
```

## Error Taxonomy Summary

| Error Type | HTTP Status | Code | When to Use |
|---|---|---|---|
| `ValidationError` | 400 | `VALIDATION_ERROR` | Invalid input, bad format, missing required field |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` | Missing or invalid credentials (JWT, API key) |
| `ForbiddenError` | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `NotFoundError` | 404 | `NOT_FOUND` | Resource does not exist or was soft-deleted |
| `ConflictError` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `RateLimitError` | 429 | `RATE_LIMITED` | Too many requests from tenant/user |
| `InternalError` | 500 | `INTERNAL_ERROR` | Unexpected server error — never expose details |
| `UpstreamError` | 502 | `UPSTREAM_ERROR` | External service (CA, email, webhook) failure |

## Critical Rules

- Every error returned from service/repo layers MUST be an `*AppError` or wrapped with `fmt.Errorf("context: %w", err)`
- Internal error messages (500, 502) MUST NOT leak to clients — always return generic message
- Validation errors (400) SHOULD include the field name and reason in `details`
- `errors.Is` and `errors.As` MUST work — implement `Unwrap()` on all custom error types
- Log errors ONCE at the top of the call stack — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type (repo maps pgx errors, service maps business rule violations)
- Panic recovery middleware MUST be in the stack — panics MUST NOT crash the server
- Rate limit responses MUST include `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
