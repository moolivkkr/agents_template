---
skill: error-handling-python
description: Python error handling archetype — AppError base class hierarchy, FastAPI exception handlers, error response envelope, structured logging, error code registry
version: "1.0"
tags:
  - python
  - errors
  - fastapi
  - archetype
  - backend
---

# Error Handling Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/error-handling.md` (Go) and `backend/archetypes/error-handling-typescript.md` (TypeScript). All three produce identical error response envelopes so frontend clients can use a single error parsing strategy.

Complete error handling system for Python backend services (FastAPI, Starlette). Every generated Python service MUST follow this pattern.

## AppError Base Class

```python
# app/errors/base.py

from typing import Any


class AppError(Exception):
    """
    Base application error type.
    All domain errors MUST inherit from this class so exception handlers
    can map them to HTTP responses.

    Produces the same JSON envelope as the Go and TypeScript archetypes:
    {"error": {"code": "...", "message": "...", "details": {...}}}
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        http_status: int,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause

    def with_details(self, key: str, value: Any) -> "AppError":
        """Add structured context to the error. Returns self for chaining."""
        self.details[key] = value
        return self

    def with_cause(self, cause: Exception) -> "AppError":
        """Wrap an underlying error for debugging while keeping the client message clean."""
        self.__cause__ = cause
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the standard error detail format."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result

    def __repr__(self) -> str:
        cause_str = f", cause={self.__cause__!r}" if self.__cause__ else ""
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}{cause_str})"
```

## Domain Error Subclasses

```python
# app/errors/domain.py

from app.errors.base import AppError


# --- 400 Bad Request: Malformed Request (JSON parse errors, wrong content type) ---

class BadRequestError(AppError):
    """Malformed request — unparseable JSON, wrong content type, etc."""

    def __init__(self, reason: str, cause: Exception | None = None) -> None:
        super().__init__(
            code="BAD_REQUEST",
            message=reason,
            http_status=400,
            cause=cause,
        )


# --- 422 Unprocessable Entity: Business Validation Errors ---
# Use 422 for well-formed requests that fail domain/business validation rules.
# Use 400 (above) for malformed JSON, wrong content type, or request parsing errors.

class ValidationError(AppError):
    """Business validation failure on a single field."""

    def __init__(self, *, field: str, reason: str, cause: Exception | None = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=f"invalid value for field '{field}'",
            http_status=422,
            details={"field": field, "reason": reason},
            cause=cause,
        )


class MultiValidationError(AppError):
    """Multiple field validation failures."""

    def __init__(self, field_errors: dict[str, str]) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message="one or more fields failed validation",
            http_status=422,
            details={"fields": field_errors},
        )


# --- 401 Unauthorized: Authentication Errors ---

class UnauthorizedError(AppError):
    """Missing or invalid credentials (JWT, API key)."""

    def __init__(self, reason: str = "authentication required") -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=reason,
            http_status=401,
        )


# --- 403 Forbidden: Authorization Errors ---

class ForbiddenError(AppError):
    """Valid credentials but insufficient permissions."""

    def __init__(self, *, action: str, resource: str) -> None:
        super().__init__(
            code="FORBIDDEN",
            message=f"insufficient permissions to {action} {resource}",
            http_status=403,
            details={"action": action, "resource": resource},
        )


# --- 404 Not Found ---

class NotFoundError(AppError):
    """Resource does not exist or was soft-deleted."""

    def __init__(self, *, resource: str, identifier: str = "") -> None:
        msg = f"{resource} not found" if not identifier else f"{resource} '{identifier}' not found"
        super().__init__(
            code="NOT_FOUND",
            message=msg,
            http_status=404,
            details={"resource": resource, "identifier": identifier},
        )


# --- 409 Conflict: Duplicate / Version Mismatch ---

class ConflictError(AppError):
    """Duplicate entry, version mismatch, or state conflict."""

    def __init__(self, *, resource: str, reason: str) -> None:
        super().__init__(
            code="CONFLICT",
            message=f"{resource} conflict: {reason}",
            http_status=409,
            details={"resource": resource, "reason": reason},
        )


# --- 429 Too Many Requests ---

class RateLimitError(AppError):
    """Too many requests from tenant/user."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            code="RATE_LIMITED",
            message="too many requests — please retry later",
            http_status=429,
            details={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


# --- 500 Internal Server Error ---

class InternalError(AppError):
    """Unexpected server error — never expose details to clients."""

    def __init__(self, cause: Exception | None = None) -> None:
        super().__init__(
            code="INTERNAL_ERROR",
            message="an unexpected error occurred",
            http_status=500,
            cause=cause,
        )


# --- 502 Bad Gateway: Upstream Failure ---

class UpstreamError(AppError):
    """External service (CA, email, webhook) failure."""

    def __init__(self, service: str, cause: Exception | None = None) -> None:
        super().__init__(
            code="UPSTREAM_ERROR",
            message=f"upstream service '{service}' is unavailable",
            http_status=502,
            details={"service": service},
            cause=cause,
        )
```

## Barrel Export

```python
# app/errors/__init__.py

from app.errors.base import AppError
from app.errors.domain import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalError,
    MultiValidationError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    UpstreamError,
    ValidationError,
)

__all__ = [
    "AppError",
    "BadRequestError",
    "ConflictError",
    "ForbiddenError",
    "InternalError",
    "MultiValidationError",
    "NotFoundError",
    "RateLimitError",
    "UnauthorizedError",
    "UpstreamError",
    "ValidationError",
]
```

## FastAPI Exception Handlers

```python
# app/errors/handlers.py

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.errors.base import AppError
from app.errors.domain import RateLimitError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Mount all custom exception handlers on the FastAPI app.
    Call this once during application startup.

    Usage:
        app = FastAPI()
        register_exception_handlers(app)
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")

        # Log internal errors with full detail; client gets sanitized message
        if exc.http_status >= 500:
            logger.error(
                "internal error",
                extra={
                    "code": exc.code,
                    "message": exc.message,
                    "cause": str(exc.__cause__) if exc.__cause__ else None,
                    "traceback": traceback.format_exc() if exc.__cause__ else None,
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )

        headers: dict[str, str] = {}

        # Add Retry-After header for rate limit errors
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after_seconds)

        # Add WWW-Authenticate header for 401 errors
        if exc.http_status == 401:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.to_dict()},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Pydantic / FastAPI validation errors → 422 with field details.
        Maps FastAPI's native validation to our standard error envelope.
        """
        field_errors: dict[str, str] = {}
        for error in exc.errors():
            # Build field path: "body → name" or "query → page_size"
            loc = " → ".join(str(part) for part in error["loc"] if part != "body")
            field_errors[loc] = error["msg"]

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "one or more fields failed validation",
                    "details": {"fields": field_errors},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all handler. Acts as the Python equivalent of Go's recovery middleware.
        Never leaks internal error details to clients.
        """
        req_id = getattr(request.state, "request_id", "")
        logger.error(
            "unhandled error",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "an unexpected error occurred",
                }
            },
        )
```

## Error Response Format

All error responses use the same envelope format as the Go and TypeScript archetypes:

```json
// 400 Bad Request (malformed input):
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "invalid JSON in request body"
  }
}

// 422 Validation Error (business rule violation):
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "invalid value for field 'email'",
    "details": { "field": "email", "reason": "invalid format" }
  }
}

// 422 Multi-field Validation Error:
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "one or more fields failed validation",
    "details": { "fields": { "name": "name is required", "email": "invalid format" } }
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
    "message": "widget conflict: version mismatch — reload and retry",
    "details": { "resource": "widget", "reason": "version mismatch" }
  }
}

// 429 Rate Limited (includes Retry-After header):
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "too many requests — please retry later",
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

```python
# --- WRAPPING RULES ---
#
# 1. Raise domain errors at the BOUNDARY where you KNOW the error type.
#
#    # In repository — this is where we know IntegrityError means conflict:
#    except IntegrityError as exc:
#        raise ConflictError(resource="widget", reason="duplicate name") from exc
#    # NOT in the handler — the handler shouldn't know about SQLAlchemy.
#
# 2. Use `raise ... from exc` to preserve the exception chain for debugging.
#
#    try:
#        await repo.create(widget)
#    except IntegrityError as exc:
#        raise ConflictError(resource="widget", reason="duplicate") from exc
#    # The __cause__ is preserved for logging in the exception handler.
#
# 3. Never double-wrap domain errors — if the error is already an AppError, re-raise it.
#
#    except Exception as exc:
#        if isinstance(exc, AppError):
#            raise  # already a domain error — don't re-wrap
#        raise InternalError(cause=exc) from exc  # unknown error — wrap as internal
#
# 4. Log the wrapped error at the TOP of the call stack (exception handler), not at every layer.
#
#    # ✅ Exception handler logs once with full context
#    # ❌ Don't logger.error() at every layer — you get duplicate log lines
#
# 5. Preserve the exception chain for debugging.
#
#    # The chain should read like a traceback:
#    # ConflictError("widget conflict: duplicate name")
#    #   caused by IntegrityError("unique_violation on idx_widgets_name")
#    #     caused by asyncpg.UniqueViolationError(...)
```

## Usage in Service Layer

```python
# app/services/widget.py

from app.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class WidgetService:
    def __init__(self, repo: WidgetRepository) -> None:
        self._repo = repo

    async def create(self, *, tenant_id: UUID, name: str) -> Widget:
        # Validate — raises 422 on failure
        if not name.strip():
            raise ValidationError(field="name", reason="name is required")

        # Check for duplicates — raises 409 on conflict
        existing = await self._repo.find_by_name(tenant_id, name)
        if existing is not None:
            raise ConflictError(resource="widget", reason=f"name '{name}' already exists")

        return await self._repo.create(widget)

    async def get(self, *, tenant_id: UUID, widget_id: UUID) -> Widget:
        widget = await self._repo.get_by_id(tenant_id, widget_id)
        if widget is None:
            raise NotFoundError(resource="widget", identifier=str(widget_id))
        return widget

    async def update(self, *, tenant_id: UUID, widget_id: UUID, version: int, **fields) -> Widget:
        existing = await self.get(tenant_id=tenant_id, widget_id=widget_id)

        # Optimistic lock check — raises 409 on version mismatch
        if version != existing.version:
            raise ConflictError(resource="widget", reason="version mismatch — reload and retry")

        return await self._repo.update(existing)
```

## Type Checking Errors

```python
# Use isinstance for error type checking — mirrors Go's errors.As and TypeScript's instanceof

try:
    await widget_service.create(tenant_id=tid, name=name)
except ValidationError as exc:
    # Access exc.details["field"], exc.details["reason"]
    pass
except NotFoundError as exc:
    # Access exc.details["resource"], exc.details["identifier"]
    pass
except AppError as exc:
    # Any domain error — access exc.code, exc.http_status, exc.details
    pass
except Exception:
    # Unknown error — rethrow or wrap
    raise
```

## Error Taxonomy Summary

| Error Class | HTTP Status | Code | When to Use |
|---|---|---|---|
| `BadRequestError` | 400 | `BAD_REQUEST` | Malformed JSON, wrong content type, request parsing failure |
| `ValidationError` | 422 | `VALIDATION_ERROR` | Well-formed request that fails business/domain validation |
| `MultiValidationError` | 422 | `VALIDATION_ERROR` | Multiple field validation failures |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` | Missing or invalid credentials (JWT, API key) |
| `ForbiddenError` | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `NotFoundError` | 404 | `NOT_FOUND` | Resource does not exist or was soft-deleted |
| `ConflictError` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `RateLimitError` | 429 | `RATE_LIMITED` | Too many requests from tenant/user |
| `InternalError` | 500 | `INTERNAL_ERROR` | Unexpected server error — never expose details |
| `UpstreamError` | 502 | `UPSTREAM_ERROR` | External service failure |

## Critical Rules

- Every error raised from service/repo layers MUST be an `AppError` subclass
- Internal error messages (500, 502) MUST NOT leak to clients — always return generic message
- Validation errors (422) SHOULD include the field name and reason in `details`
- Bad request errors (400) are for malformed JSON/request parsing — NOT business validation
- `isinstance` checks MUST work — never raise bare `Exception` from domain code
- Use `raise ... from exc` to preserve the exception chain for debugging
- Log errors ONCE at the top of the call stack (exception handler) — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type (repo maps SQLAlchemy errors, service maps business rule violations)
- Catch-all exception handler MUST exist — unhandled exceptions MUST NOT crash the server or leak details
- Rate limit responses MUST include `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
- Error response format MUST match the Go archetype: `{"error": {"code": "...", "message": "...", "details": {...}}}`
