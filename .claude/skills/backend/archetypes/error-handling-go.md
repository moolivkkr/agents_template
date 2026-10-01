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

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, chi v5.3.2, testify v1.12.1; the tests in Testing Error Types were run, and a panic behind chi was checked to log the route template (tests/archetype-compile/go/run.sh).

> **CANONICAL REFERENCE**: This file is the single source of truth for backend error handling patterns.
> The wire shape it produces is the error envelope in `~/.claude/skills/api/response-envelope.md`
> (`{"error": {code, message, details[], request_id, retryable}}`); if the two ever disagree, the envelope wins. All other skill packs that mention error handling should defer to this file for definitive guidance. For the TypeScript equivalent, see `backend/archetypes/error-handling-typescript.md`.

Complete error handling system for Go backend services. Every generated service MUST follow this pattern.

## Domain Error Type

```go
package apperr

import (
    "encoding/json"
    "errors"
    "fmt"
    "log/slog"
    "net/http"
    "runtime"
    "strconv"

    "github.com/go-chi/chi/v5"
)

// FieldError is one entry of error.details[] — field-level problems for VALIDATION_FAILED.
// Code is a stable lower_snake identifier; Message comes from a fixed catalog, never err.Error().
type FieldError struct {
    Field   string `json:"field"`
    Code    string `json:"code"`
    Message string `json:"message"`
}

// AppError is the standard application error type.
// All domain errors MUST use this type so the error middleware can map them to HTTP responses.
type AppError struct {
    Code       string       // UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, ...
    Message    string       // user-safe; shown by the UI as-is
    HTTPStatus int          // not serialized
    Details    []FieldError // serialized as error.details
    Retryable  bool         // serialized as error.retryable
    RetryAfter int          // seconds; sets the Retry-After header (429/503)
    Err        error        // wrapped cause, logged server-side, never serialized
}

// Error implements the error interface (server-side text: includes the cause for logs).
func (e *AppError) Error() string {
    if e.Err != nil {
        return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.Err)
    }
    return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// Unwrap supports errors.Is and errors.As for wrapped errors.
func (e *AppError) Unwrap() error { return e.Err }

// Is supports errors.Is comparison by error code.
func (e *AppError) Is(target error) bool {
    var appErr *AppError
    if errors.As(target, &appErr) {
        return e.Code == appErr.Code
    }
    return false
}

// WithField appends a field-level problem (VALIDATION_FAILED).
func (e *AppError) WithField(field, code, message string) *AppError {
    e.Details = append(e.Details, FieldError{Field: field, Code: code, Message: message})
    return e
}

// WithError wraps an underlying error for debugging while keeping the client message clean.
func (e *AppError) WithError(err error) *AppError {
    e.Err = err
    return e
}
```

## Error Taxonomy — Constructor Functions

The codes and statuses are the table in `api/response-envelope.md`. Messages are user-safe and fixed;
nothing from a parser, driver or upstream error reaches the client.

```go
// --- 400 MALFORMED_REQUEST: JSON parse errors, wrong content type, body too large ---

func NewMalformedRequestError(err error) *AppError {
    return &AppError{Code: "MALFORMED_REQUEST", Message: "The request could not be read.",
        HTTPStatus: http.StatusBadRequest, Err: err}
}

// --- 400 VALIDATION_FAILED: the input fails schema/validation; details[] lists the fields ---

func NewValidationError(field, code, message string) *AppError {
    return (&AppError{Code: "VALIDATION_FAILED", Message: "Some fields are invalid.",
        HTTPStatus: http.StatusBadRequest}).WithField(field, code, message)
}

func NewMultiValidationError(fields []FieldError) *AppError {
    return &AppError{Code: "VALIDATION_FAILED", Message: "Some fields are invalid.",
        HTTPStatus: http.StatusBadRequest, Details: fields}
}

// Map validator output (e.g. go-playground/validator) to stable codes + catalog messages:
//   for _, fe := range verrs { fields = append(fields, FieldError{Field: jsonName(fe), Code: fe.Tag(), Message: catalog(fe)}) }
// Never put fe.Error() / err.Error() in Message — it can carry internals and isn't written for users.

// --- 422 BUSINESS_RULE_VIOLATION: a valid request rejected by a domain rule ---

func NewBusinessRuleError(message string) *AppError {
    return &AppError{Code: "BUSINESS_RULE_VIOLATION", Message: message, HTTPStatus: http.StatusUnprocessableEntity}
}

// --- 401 UNAUTHENTICATED ---

func NewUnauthenticatedError() *AppError {
    return &AppError{Code: "UNAUTHENTICATED", Message: "Sign in to continue.", HTTPStatus: http.StatusUnauthorized}
}

// --- 403 FORBIDDEN: authenticated, not allowed (function-level) ---

func NewForbiddenError() *AppError {
    return &AppError{Code: "FORBIDDEN", Message: "You don't have permission to do this.", HTTPStatus: http.StatusForbidden}
}

// --- 404 NOT_FOUND: missing OR another tenant's/owner's object (never 403 for those) ---

func NewNotFoundError(resource string) *AppError {
    return &AppError{Code: "NOT_FOUND", Message: resource + " not found.", HTTPStatus: http.StatusNotFound}
}

// --- 409 CONFLICT: duplicate / version mismatch / state conflict ---

func NewConflictError(message string) *AppError {
    return &AppError{Code: "CONFLICT", Message: message, HTTPStatus: http.StatusConflict}
}

// --- 429 RATE_LIMITED ---

func NewRateLimitError(retryAfterSecs int) *AppError {
    return &AppError{Code: "RATE_LIMITED", Message: "Too many requests. Try again shortly.",
        HTTPStatus: http.StatusTooManyRequests, Retryable: true, RetryAfter: retryAfterSecs}
}

// --- 500 INTERNAL ---

func NewInternalError(err error) *AppError {
    return &AppError{Code: "INTERNAL", Message: "Something went wrong.", HTTPStatus: http.StatusInternalServerError, Err: err}
}

// --- 503 UNAVAILABLE: a dependency (DB, upstream API) failed or timed out ---
// The service name goes to the log, not the client.

func NewUnavailableError(service string, err error) *AppError {
    return &AppError{Code: "UNAVAILABLE", Message: "The service is temporarily unavailable.",
        HTTPStatus: http.StatusServiceUnavailable, Retryable: true, RetryAfter: 5,
        Err: fmt.Errorf("upstream %s: %w", service, err)}
}
```

## Sentinel Errors for Common Cases

```go
// Sentinel errors for use with errors.Is() checks.
// Use these when you need to check for a specific error condition
// without constructing a full AppError.

var (
    ErrNotFound        = &AppError{Code: "NOT_FOUND", HTTPStatus: http.StatusNotFound}
    ErrUnauthenticated = &AppError{Code: "UNAUTHENTICATED", HTTPStatus: http.StatusUnauthorized}
    ErrForbidden       = &AppError{Code: "FORBIDDEN", HTTPStatus: http.StatusForbidden}
    ErrConflict        = &AppError{Code: "CONFLICT", HTTPStatus: http.StatusConflict}
    ErrRateLimited     = &AppError{Code: "RATE_LIMITED", HTTPStatus: http.StatusTooManyRequests}
    ErrUnavailable     = &AppError{Code: "UNAVAILABLE", HTTPStatus: http.StatusServiceUnavailable}
    ErrInternal        = &AppError{Code: "INTERNAL", HTTPStatus: http.StatusInternalServerError}
)

// Usage:
//   if errors.Is(err, apperr.ErrNotFound) {
//       // handle not found case
//   }
```

## HTTP Error Response Format

```go
// ErrorBody is the error envelope (api/response-envelope.md). Every error response uses it.
type ErrorBody struct {
    Error APIError `json:"error"`
}

type APIError struct {
    Code      string       `json:"code"`
    Message   string       `json:"message"`
    Details   []FieldError `json:"details,omitempty"`
    RequestID string       `json:"request_id"`
    Retryable bool         `json:"retryable"`
}

// Example error responses (the HTTP status carries the class; X-Request-Id header = request_id):
//
// 400 VALIDATION_FAILED:
// {"error": {"code": "VALIDATION_FAILED", "message": "Some fields are invalid.",
//            "details": [{"field": "email", "code": "invalid_format", "message": "Enter a valid email address."}],
//            "request_id": "b7e1c2…", "retryable": false}}
//
// 404 NOT_FOUND (also for another tenant's or owner's widget — don't confirm it exists):
// {"error": {"code": "NOT_FOUND", "message": "Widget not found.", "request_id": "b7e1c2…", "retryable": false}}
//
// 409 CONFLICT:
// {"error": {"code": "CONFLICT", "message": "This widget was changed by someone else. Reload and try again.",
//            "request_id": "b7e1c2…", "retryable": false}}
//
// 500 INTERNAL (the cause is in the log line with the same request_id):
// {"error": {"code": "INTERNAL", "message": "Something went wrong.", "request_id": "b7e1c2…", "retryable": false}}
```

## Error Mapping Middleware

```go
// requestID returns the ID the RequestID middleware (auth-middleware-go.md) already set on this
// response as X-Request-Id. The body repeats it, so the header and error.request_id always match.
// Reading it from the response keeps apperr free of an import on the middleware package, which
// itself imports apperr.
func requestID(w http.ResponseWriter) string {
    return w.Header().Get("X-Request-Id")
}

// routeOf returns the matched route template for logs — never the raw path, which is unbounded and
// can carry IDs. chi records the template in its route context, which middleware can read after
// routing; r.Pattern is only set on the request copy chi hands the final handler, so a middleware
// that ran earlier sees "" there. r.Pattern is the answer for net/http's ServeMux.
func routeOf(r *http.Request) string {
    if rctx := chi.RouteContext(r.Context()); rctx != nil {
        return rctx.RoutePattern()
    }
    return r.Pattern
}

// writeErrorBody is the only function that writes an error response.
func writeErrorBody(w http.ResponseWriter, e *AppError) {
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    if e.RetryAfter > 0 {
        w.Header().Set("Retry-After", strconv.Itoa(e.RetryAfter))
    }
    if e.HTTPStatus == http.StatusUnauthorized {
        w.Header().Set("WWW-Authenticate", "Bearer")
    }
    w.WriteHeader(e.HTTPStatus)
    _ = json.NewEncoder(w).Encode(ErrorBody{Error: APIError{
        Code: e.Code, Message: e.Message, Details: e.Details,
        RequestID: requestID(w), Retryable: e.Retryable,
    }})
}

// RecoveryMiddleware catches panics, logs the stack trace, and returns a 500 response.
// This MUST be in the middleware stack to prevent the server from crashing.
func RecoveryMiddleware(logger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            defer func() {
                if rec := recover(); rec != nil {
                    buf := make([]byte, 4096)
                    n := runtime.Stack(buf, false)
                    logger.ErrorContext(r.Context(), "panic recovered",
                        "panic", rec,
                        "stack", string(buf[:n]),
                        "request_id", requestID(w),
                        "method", r.Method,
                        "route", routeOf(r), // the route template, not the raw path
                    )
                    // Return a clean 500 — never expose panic details to clients
                    writeErrorBody(w, NewInternalError(nil))
                }
            }()
            next.ServeHTTP(w, r)
        })
    }
}

// ErrorMapper maps any error to the envelope. Use it in handlers instead of duplicating mapping logic.
func ErrorMapper(w http.ResponseWriter, r *http.Request, err error) {
    var appErr *AppError
    if !errors.As(err, &appErr) {
        appErr = NewInternalError(err) // unknown error type: 500, message never exposed
    }
    if appErr.HTTPStatus >= 500 {
        slog.ErrorContext(r.Context(), "request failed",
            "code", appErr.Code,
            "error", err, // the full chain, server-side only
            "request_id", requestID(w),
        )
    }
    writeErrorBody(w, appErr)
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
//        return nil, apperr.NewNotFoundError("Widget")
//    }
//    // NOT in the handler — the handler shouldn't know about pgx.
//
// 4. Log the wrapped error at the TOP of the call stack (handler/middleware), not at every layer.
//
//    // ✅ Handler logs once:
//    result, err := h.svc.Create(ctx, input)
//    if err != nil {
//        logger.Error("create failed", "error", err) // full chain visible
//        ErrorMapper(w, r, err)
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
// Assert an error's type and code, never its message text. Services wrap repository errors
// ("widget get: %w"), so the assertions must see through the chain. (Service tests with mocks:
// crud-service-test-go.md.)

func TestNotFoundSurvivesWrapping(t *testing.T) {
    err := fmt.Errorf("widget get: %w", apperr.NewNotFoundError("Widget"))

    // Assert using errors.Is with the sentinel (AppError.Is compares codes)
    assert.True(t, errors.Is(err, apperr.ErrNotFound))
    assert.False(t, errors.Is(err, apperr.ErrConflict))

    // Assert using errors.As for detailed inspection
    var appErr *apperr.AppError
    require.True(t, errors.As(err, &appErr))
    assert.Equal(t, "NOT_FOUND", appErr.Code)
    assert.Equal(t, http.StatusNotFound, appErr.HTTPStatus)
}

func TestConflictSurvivesWrapping(t *testing.T) {
    err := fmt.Errorf("widget update: %w", apperr.NewConflictError("This widget was changed by someone else."))

    var appErr *apperr.AppError
    require.True(t, errors.As(err, &appErr))
    assert.Equal(t, "CONFLICT", appErr.Code)
    assert.Equal(t, http.StatusConflict, appErr.HTTPStatus)
}

func TestErrorMapperHidesUnknownErrors(t *testing.T) {
    rec := httptest.NewRecorder()
    rec.Header().Set("X-Request-Id", "req-1") // the RequestID middleware sets this in production
    req := httptest.NewRequest(http.MethodGet, "/api/v1/widgets", nil)

    apperr.ErrorMapper(rec, req, errors.New("dial tcp 10.0.0.5:5432: connection refused"))

    assert.Equal(t, http.StatusInternalServerError, rec.Code)
    assert.JSONEq(t, `{"error": {"code": "INTERNAL", "message": "Something went wrong.",
        "request_id": "req-1", "retryable": false}}`, rec.Body.String())
}
```

## Error Taxonomy Summary

| Error Type | HTTP Status | Code | When to Use |
|---|---|---|---|
| `MalformedRequestError` | 400 | `MALFORMED_REQUEST` | Malformed JSON, wrong content type, body too large |
| `ValidationError` | 400 | `VALIDATION_FAILED` | Input fails schema/validation — `details[]` lists `{field, code, message}` |
| `UnauthenticatedError` | 401 | `UNAUTHENTICATED` | Missing, invalid or expired credentials |
| `ForbiddenError` | 403 | `FORBIDDEN` | Authenticated but not allowed (function-level) |
| `NotFoundError` | 404 | `NOT_FOUND` | Doesn't exist, soft-deleted, **or belongs to another tenant/owner** |
| `ConflictError` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `BusinessRuleError` | 422 | `BUSINESS_RULE_VIOLATION` | Valid shape, rejected by a domain rule |
| `RateLimitError` | 429 | `RATE_LIMITED` | Too many requests (`Retry-After`, `retryable: true`) |
| `InternalError` | 500 | `INTERNAL` | Unexpected server error — never expose details |
| `UnavailableError` | 503 | `UNAVAILABLE` | A dependency failed or timed out (`retryable: true`) |

## Critical Rules

- Every error returned from service/repo layers MUST be an `*AppError` or wrapped with `fmt.Errorf("context: %w", err)`
- Internal error messages (500, 503) MUST NOT leak to clients — always return generic message
- No client-visible field ever contains `err.Error()`, SQL, a driver/upstream message, a path or a stack trace
- Validation errors (400 `VALIDATION_FAILED`) carry `details[]` of `{field, code, message}` from a fixed catalog
- Business-rule rejections are 422 `BUSINESS_RULE_VIOLATION`; malformed bodies are 400 `MALFORMED_REQUEST`
- Every error body carries `request_id` (= the `X-Request-Id` header) and `retryable`
- `errors.Is` and `errors.As` MUST work — implement `Unwrap()` on all custom error types
- Log errors ONCE at the top of the call stack — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type (repo maps pgx errors, service maps business rule violations)
- Panic recovery middleware MUST be in the stack — panics MUST NOT crash the server
- Rate limit responses MUST include `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
