---
skill: error-handling-python
description: Python error handling archetype — AppError hierarchy with field-level details, FastAPI exception handlers that write the one error envelope (request_id, retryable, X-Request-Id, Retry-After), structured logging, error code registry
version: "1.0"
tags:
  - python
  - errors
  - fastapi
  - archetype
  - backend
---

# Error Handling Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/error-handling-go.md` (Go) and `backend/archetypes/error-handling-typescript.md` (TypeScript). The wire shape all three produce is the error envelope in `~/.claude/skills/api/response-envelope.md` (`{"error": {code, message, details[], request_id, retryable}}`); if this file and the envelope ever disagree, the envelope wins.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): imported, type-checked, and every handler path exercised through TestClient (AppError, validation, 404/405, catch-all 500); 14 pydantic validation failures (missing, too short/long, out of range, wrong type, bad UUID, bad date and datetime, enum, literal, list too long, extra field, a custom validator) come back as `details[].code` values from the closed set in `api/response-envelope.md`, and `tests/lib/field_codes.py --lang python` passes. FastAPI 0.142.2, Starlette 1.7.0, Pydantic 2.13.5.

Complete error handling system for Python backend services (FastAPI, Starlette). Every generated Python service MUST follow this pattern.

## AppError Base Class

```python
# app/errors/base.py

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FieldError:
    """
    One entry of error.details[] — a field-level problem (VALIDATION_FAILED).
    `code` is one of the closed set in api/response-envelope.md (required, invalid_type, invalid_format,
    invalid_value, out_of_range, too_short, too_long, unknown_field, invalid_cursor, already_exists),
    never a validator's own word; `message` comes from a fixed catalog, never str(exc) or a raw
    validator message.
    """

    field: str
    code: str
    message: str


class AppError(Exception):
    """
    Base application error type.
    All domain errors MUST inherit from this class so the exception handlers
    can map them to the error envelope:
    {"error": {"code": "...", "message": "...", "details": [...], "request_id": "...", "retryable": false}}
    """

    def __init__(
        self,
        *,
        code: str,                                 # UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, ...
        message: str,                              # user-safe; shown by the UI as-is
        status: int,                               # HTTP status; not serialized
        details: list[FieldError] | None = None,   # serialized as error.details
        retryable: bool = False,                   # serialized as error.retryable
        retry_after: int | None = None,            # seconds; sets the Retry-After header (429/503)
        cause: BaseException | None = None,        # logged server-side, never serialized
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details: list[FieldError] = list(details or [])
        self.retryable = retryable
        self.retry_after = retry_after
        if cause is not None:
            self.__cause__ = cause

    @property
    def cause(self) -> BaseException | None:
        return self.__cause__

    def with_field(self, field: str, code: str, message: str) -> "AppError":
        """Append a field-level problem (VALIDATION_FAILED). Returns self for chaining."""
        self.details.append(FieldError(field=field, code=code, message=message))
        return self

    def with_cause(self, cause: BaseException) -> "AppError":
        """Wrap an underlying error for debugging while keeping the client message clean."""
        self.__cause__ = cause
        return self

    def to_body(self, request_id: str) -> dict[str, Any]:
        """Serialize to the error envelope. Nothing from the cause is ever included."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = [asdict(d) for d in self.details]
        error["request_id"] = request_id
        error["retryable"] = self.retryable
        return {"error": error}

    def __repr__(self) -> str:
        cause_str = f", cause={self.__cause__!r}" if self.__cause__ else ""
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}{cause_str})"
```

## Domain Error Subclasses

The codes and statuses are the table in `api/response-envelope.md`. Messages are user-safe and fixed;
nothing from a parser, driver or upstream error reaches the client.

```python
# app/errors/domain.py

from app.errors.base import AppError, FieldError


# --- 400 MALFORMED_REQUEST: unparseable JSON, wrong content type, body too large ---

class MalformedRequestError(AppError):
    def __init__(self, cause: BaseException | None = None) -> None:
        super().__init__(
            code="MALFORMED_REQUEST",
            message="The request could not be read.",
            status=400,
            cause=cause,
        )


# --- 400 VALIDATION_FAILED: the input fails schema/validation; details[] lists the fields ---
# One field:  ValidationFailedError("email", "invalid_format", "Enter a valid email address.")
# Several:    ValidationFailedError(fields=[FieldError(...), FieldError(...)])
# Named ValidationFailedError so it never shadows pydantic.ValidationError.

class ValidationFailedError(AppError):
    def __init__(
        self,
        field: str = "",
        code: str = "",
        message: str = "",
        *,
        fields: list[FieldError] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        details = list(fields or [])
        if field:
            details.insert(0, FieldError(field=field, code=code, message=message))
        super().__init__(
            code="VALIDATION_FAILED",
            message="Some fields are invalid.",
            status=400,
            details=details,
            cause=cause,
        )


# --- 401 UNAUTHENTICATED: missing, invalid or expired credentials ---

class UnauthenticatedError(AppError):
    def __init__(self, cause: BaseException | None = None) -> None:
        super().__init__(code="UNAUTHENTICATED", message="Sign in to continue.", status=401, cause=cause)


# --- 403 FORBIDDEN: authenticated, not allowed (function-level) ---

class ForbiddenError(AppError):
    def __init__(self) -> None:
        super().__init__(code="FORBIDDEN", message="You don't have permission to do this.", status=403)


# --- 404 NOT_FOUND: missing OR another tenant's/owner's object (never 403 for those) ---

class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(code="NOT_FOUND", message=f"{resource} not found.", status=404)


# --- 409 CONFLICT: duplicate / version mismatch / state conflict ---

class ConflictError(AppError):
    def __init__(
        self,
        message: str = "This conflicts with the current state. Reload and try again.",
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(code="CONFLICT", message=message, status=409, cause=cause)


# --- 409 IDEMPOTENCY_KEY_REUSED: Idempotency-Key replayed with a different body ---

class IdempotencyKeyReusedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="IDEMPOTENCY_KEY_REUSED",
            message="This Idempotency-Key was already used with a different request.",
            status=409,
        )


# --- 422 BUSINESS_RULE_VIOLATION: a valid request rejected by a domain rule ---

class BusinessRuleError(AppError):
    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(code="BUSINESS_RULE_VIOLATION", message=message, status=422, cause=cause)


# --- 429 RATE_LIMITED ---

class RateLimitError(AppError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            code="RATE_LIMITED",
            message="Too many requests. Try again shortly.",
            status=429,
            retryable=True,
            retry_after=retry_after_seconds,
        )


# --- 500 INTERNAL ---

class InternalError(AppError):
    """Unexpected server error — never expose details to clients."""

    def __init__(self, cause: BaseException | None = None) -> None:
        super().__init__(code="INTERNAL", message="Something went wrong.", status=500, cause=cause)


# --- 503 UNAVAILABLE: a dependency (DB, upstream API) failed or timed out ---
# The service name goes to the log (an exception note), not the client.

class UnavailableError(AppError):
    def __init__(self, service: str, cause: BaseException | None = None) -> None:
        super().__init__(
            code="UNAVAILABLE",
            message="The service is temporarily unavailable.",
            status=503,
            retryable=True,
            retry_after=5,
            cause=cause,
        )
        self.service = service
        self.add_note(f"dependency: {service}")  # printed in the logged traceback only
```

## Barrel Export

```python
# app/errors/__init__.py

from app.errors.base import AppError, FieldError
from app.errors.domain import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    IdempotencyKeyReusedError,
    InternalError,
    MalformedRequestError,
    NotFoundError,
    RateLimitError,
    UnauthenticatedError,
    UnavailableError,
    ValidationFailedError,
)

__all__ = [
    "AppError",
    "BusinessRuleError",
    "ConflictError",
    "FieldError",
    "ForbiddenError",
    "IdempotencyKeyReusedError",
    "InternalError",
    "MalformedRequestError",
    "NotFoundError",
    "RateLimitError",
    "UnauthenticatedError",
    "UnavailableError",
    "ValidationFailedError",
]
```

## FastAPI Exception Handlers

FastAPI's built-in handlers answer `{"detail": ...}` — and 422 for request validation. Neither matches
the envelope, so `register_exception_handlers` replaces them. `error_response` is the only function that
writes an error body.

```python
# app/errors/handlers.py

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.errors.base import AppError, FieldError
from app.errors.domain import (
    ConflictError,
    ForbiddenError,
    InternalError,
    MalformedRequestError,
    NotFoundError,
    UnauthenticatedError,
    UnavailableError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)

# Pydantic's error types ("missing", "string_too_long", "greater_than_equal", ...) are its own vocabulary.
# Each maps onto the closed details[].code set in api/response-envelope.md, with the message the client
# sees; a type not listed is invalid_value. Pydantic's own `msg` is never sent: a custom validator's
# ValueError text lands there and can carry internals.
_PYDANTIC_FIELD_ERRORS: dict[str, tuple[str, str]] = {
    "missing": ("required", "This field is required."),
    "string_too_short": ("too_short", "This value is too short."),
    "too_short": ("too_short", "Too few items."),
    "string_too_long": ("too_long", "This value is too long."),
    "too_long": ("too_long", "Too many items."),
    "greater_than": ("out_of_range", "This value is too small."),
    "greater_than_equal": ("out_of_range", "This value is too small."),
    "less_than": ("out_of_range", "This value is too large."),
    "less_than_equal": ("out_of_range", "This value is too large."),
    "int_parsing": ("invalid_type", "Must be a whole number."),
    "int_type": ("invalid_type", "Must be a whole number."),
    "int_from_float": ("invalid_type", "Must be a whole number."),
    "float_parsing": ("invalid_type", "Must be a number."),
    "bool_parsing": ("invalid_type", "Must be true or false."),
    "string_type": ("invalid_type", "Must be text."),
    "uuid_parsing": ("invalid_format", "Must be a valid ID."),
    "string_pattern_mismatch": ("invalid_format", "This value has an invalid format."),
    # a malformed date / datetime string is reported as *_from_*_parsing, not date_parsing / datetime_parsing
    "date_parsing": ("invalid_format", "Must be a date (YYYY-MM-DD)."),
    "date_from_datetime_parsing": ("invalid_format", "Must be a date (YYYY-MM-DD)."),
    "datetime_parsing": ("invalid_format", "Must be a date and time (RFC 3339)."),
    "datetime_from_date_parsing": ("invalid_format", "Must be a date and time (RFC 3339)."),
    "enum": ("invalid_value", "This value is not one of the allowed options."),
    "literal_error": ("invalid_value", "This value is not one of the allowed options."),
    "extra_forbidden": ("unknown_field", "This field is not accepted."),
}
_FALLBACK_FIELD_ERROR = ("invalid_value", "This value is invalid.")
_LOCATIONS = {"body", "query", "path", "header", "cookie"}


def field_error(loc: tuple, pydantic_type: str) -> FieldError:
    """One pydantic error as a details[] entry: the path without its location, a code from the set."""
    code, message = _PYDANTIC_FIELD_ERRORS.get(pydantic_type, _FALLBACK_FIELD_ERROR)
    return FieldError(field=_field_path(loc), code=code, message=message)


def request_id_of(request: Request) -> str:
    """The request_id set by RequestIDMiddleware. Read it from request.state, which every handler
    (including the catch-all) sees; the contextvar is already reset when a 500 is being written."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def error_response(request: Request, exc: AppError) -> JSONResponse:
    """The only function that writes an error response (mirrors writeErrorBody in error-handling-go.md)."""
    request_id = request_id_of(request)
    log_extra = {
        "code": exc.code,
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
    }
    if exc.status >= 500:
        # Cause, traceback and exception notes go to the log, never to the client
        logger.error("request failed", extra=log_extra, exc_info=exc)
    elif exc.__cause__ is not None:
        # A 4xx built from a driver error (e.g. unique violation → 409): the constraint name lives only here
        logger.info("request rejected", extra=log_extra, exc_info=exc)

    headers = {"X-Request-Id": request_id}  # set here too: a 500 from the catch-all bypasses RequestIDMiddleware
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    if exc.status == 401:
        headers["WWW-Authenticate"] = "Bearer"

    return JSONResponse(status_code=exc.status, content=exc.to_body(request_id), headers=headers)


def _field_path(loc: tuple) -> str:
    """("body", "items", 0, "name") -> "items.0.name"; ("query", "limit") -> "limit"."""
    parts = [str(p) for p in loc]
    if parts and parts[0] in _LOCATIONS:
        parts = parts[1:]
    return ".".join(parts) or "body"


def _is_malformed(err: dict) -> bool:
    # FastAPI reports unparseable JSON as "json_invalid" and an empty body as a missing ("body",)
    return err["type"] == "json_invalid" or (err["type"] == "missing" and tuple(err["loc"]) == ("body",))


def _from_http_status(status: int, exc: Exception) -> AppError:
    """Re-shape an HTTPException by its status only. exc.detail is never sent (it can carry internals)."""
    if status == 401:
        return UnauthenticatedError()
    if status == 403:
        return ForbiddenError()
    if status == 404:
        return NotFoundError("Resource")
    if status == 409:
        return ConflictError()
    if status == 503:
        return UnavailableError("http", cause=exc)
    if status >= 500:
        return InternalError(cause=exc)
    return MalformedRequestError()  # 400, 405, 413, 415 and any other 4xx


def register_exception_handlers(app: FastAPI) -> None:
    """
    The ONE registration point for error handling. Call this once during application startup.

    Usage:
        app = FastAPI()
        register_exception_handlers(app)
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Pydantic / FastAPI request validation (body, query, path). FastAPI's default is
        422 {"detail": [...]}; the envelope says 400 VALIDATION_FAILED with details[],
        or 400 MALFORMED_REQUEST when the body isn't readable JSON.
        """
        errors = exc.errors()
        if any(_is_malformed(e) for e in errors):
            return error_response(request, MalformedRequestError())

        fields = [field_error(e["loc"], e["type"]) for e in errors]
        return error_response(request, ValidationFailedError(fields=fields))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """
        Unknown routes (404), wrong methods (405) and any HTTPException raised by FastAPI or a
        dependency. FastAPI's default body is {"detail": ...}. App code raises AppError subclasses,
        not HTTPException.
        """
        return error_response(request, _from_http_status(exc.status_code, exc))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all handler. Acts as the Python equivalent of Go's recovery middleware:
        500 INTERNAL with a generic message; the exception and traceback go to the log under request_id.
        Starlette runs this in ServerErrorMiddleware and re-raises after the response is sent (so the
        server logs it too). In tests, use ASGITransport(app=app, raise_app_exceptions=False).
        """
        return error_response(request, InternalError(cause=exc))
```

## Error Response Format

All error responses use the error envelope from `api/response-envelope.md`. The HTTP status carries the
class, there is no `data` key, and every error response sets `X-Request-Id` = `request_id`:

```json
// 400 MALFORMED_REQUEST (unparseable JSON, wrong content type, body too large):
{
  "error": {
    "code": "MALFORMED_REQUEST",
    "message": "The request could not be read.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 400 VALIDATION_FAILED (pydantic request validation lands here too, not on 422):
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Some fields are invalid.",
    "details": [
      { "field": "name", "code": "required", "message": "This field is required." },
      { "field": "email", "code": "invalid_format", "message": "Enter a valid email address." }
    ],
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 404 Not Found (also for another tenant's or owner's widget — don't confirm it exists):
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Widget not found.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 409 Conflict:
{
  "error": {
    "code": "CONFLICT",
    "message": "This widget was changed by someone else. Reload and try again.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 422 BUSINESS_RULE_VIOLATION (valid shape, rejected by a domain rule):
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Archived widgets can't be edited.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 429 Rate Limited (includes Retry-After header):
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

// 503 UNAVAILABLE (a dependency failed or timed out; includes Retry-After header):
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

```python
# --- WRAPPING RULES ---
#
# 1. Raise domain errors at the BOUNDARY where you KNOW the error type.
#
#    # In repository — this is where we know IntegrityError means conflict:
#    except IntegrityError as exc:
#        raise ConflictError("A widget with this name already exists.") from exc
#    # NOT in the handler — the handler shouldn't know about SQLAlchemy.
#
# 2. Use `raise ... from exc` to preserve the exception chain for debugging.
#
#    try:
#        await repo.create(widget)
#    except IntegrityError as exc:
#        raise ConflictError("A widget with this name already exists.") from exc
#    # The __cause__ is preserved for logging in the exception handler — it is never sent.
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
#    # ConflictError("A widget with this name already exists.")
#    #   caused by IntegrityError("unique_violation on idx_widgets_name")
#    #     caused by asyncpg.UniqueViolationError(...)
```

## Usage in Service Layer

```python
# app/services/widget.py

from uuid import UUID

from app.domain.widget import Widget, WidgetStatus
from app.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from app.services.protocols import WidgetRepository


class WidgetService:
    def __init__(self, repo: WidgetRepository) -> None:
        self._repo = repo

    async def create(self, *, tenant_id: UUID, name: str) -> Widget:
        # Validate — raises 400 VALIDATION_FAILED on failure
        if not name.strip():
            raise ValidationFailedError("name", "required", "Name is required.")

        # A duplicate name is 409 CONFLICT, raised by the repository when the unique index rejects
        # the insert (rule 1 above). A check-then-insert here would race a concurrent create.
        widget = Widget(tenant_id=tenant_id, name=name.strip())
        await self._repo.create(widget)
        return widget

    async def get(self, *, tenant_id: UUID, widget_id: UUID) -> Widget:
        widget = await self._repo.get_by_id(tenant_id, widget_id)
        if widget is None:
            raise NotFoundError("Widget")  # also when it belongs to another tenant
        return widget

    async def update(self, *, tenant_id: UUID, widget_id: UUID, version: int, **fields) -> Widget:
        existing = await self.get(tenant_id=tenant_id, widget_id=widget_id)

        # Domain rule — raises 422 BUSINESS_RULE_VIOLATION
        if existing.status == WidgetStatus.ARCHIVED:
            raise BusinessRuleError("Archived widgets can't be edited.")

        # Optimistic lock check — raises 409 on version mismatch
        if version != existing.version:
            raise ConflictError("This widget was changed by someone else. Reload and try again.")

        existing.version += 1
        if not await self._repo.update(existing):  # 0 rows: changed concurrently since the read
            raise ConflictError("This widget was changed by someone else. Reload and try again.")
        return existing
```

## Type Checking Errors

```python
# Use isinstance for error type checking — mirrors Go's errors.As and TypeScript's instanceof

try:
    await widget_service.create(tenant_id=tid, name=name)
except ValidationFailedError as exc:
    # exc.details is a list[FieldError]: exc.details[0].field, .code, .message
    pass
except NotFoundError as exc:
    # exc.code == "NOT_FOUND", exc.status == 404
    pass
except AppError as exc:
    # Any domain error — access exc.code, exc.status, exc.details, exc.retryable
    pass
except Exception:
    # Unknown error — rethrow or wrap
    raise
```

## Error Taxonomy Summary

| Error Class | HTTP Status | Code | When to Use |
|---|---|---|---|
| `MalformedRequestError` | 400 | `MALFORMED_REQUEST` | Malformed JSON, wrong content type, body too large |
| `ValidationFailedError` | 400 | `VALIDATION_FAILED` | Input fails schema/validation (including pydantic request validation) — `details[]` lists `{field, code, message}` |
| `UnauthenticatedError` | 401 | `UNAUTHENTICATED` | Missing, invalid or expired credentials |
| `ForbiddenError` | 403 | `FORBIDDEN` | Authenticated but not allowed (function-level) |
| `NotFoundError` | 404 | `NOT_FOUND` | Doesn't exist, soft-deleted, **or belongs to another tenant/owner** |
| `ConflictError` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `IdempotencyKeyReusedError` | 409 | `IDEMPOTENCY_KEY_REUSED` | `Idempotency-Key` replayed with a different body |
| `BusinessRuleError` | 422 | `BUSINESS_RULE_VIOLATION` | Valid shape, rejected by a domain rule |
| `RateLimitError` | 429 | `RATE_LIMITED` | Too many requests (`Retry-After`, `retryable: true`) |
| `InternalError` | 500 | `INTERNAL` | Unexpected server error — never expose details |
| `UnavailableError` | 503 | `UNAVAILABLE` | A dependency failed or timed out (`Retry-After`, `retryable: true`) |

## Critical Rules

- Every error raised from service/repo layers MUST be an `AppError` subclass
- The wire shape is `api/response-envelope.md`: `{"error": {code, message, details?, request_id, retryable}}` — no `data` key, no `detail` field, and `details` is a list of `{field, code, message}`, never a dict
- Internal error messages (500, 503) MUST NOT leak to clients — always return the generic message
- No client-visible field ever contains `str(exc)`, `repr(exc)`, `exc.args`, a raw pydantic `msg`, SQL, a constraint name, a driver/upstream message, a path or a traceback — the cause goes to the log under `request_id`
- Validation errors (400 `VALIDATION_FAILED`) carry `details[]` from a fixed catalog; pydantic/FastAPI request validation is 400 `VALIDATION_FAILED`, not FastAPI's default 422
- `details[].code` is one of the closed set in `api/response-envelope.md`. Pydantic's error types (`missing`, `string_too_short`, `greater_than_equal`, ...) are mapped onto it by `_PYDANTIC_FIELD_ERRORS`; an unmapped type becomes `invalid_value`
- Malformed bodies are 400 `MALFORMED_REQUEST`; business-rule rejections are 422 `BUSINESS_RULE_VIOLATION`
- `register_exception_handlers` MUST replace FastAPI's default `RequestValidationError` and `HTTPException` handlers — their `{"detail": ...}` bodies never reach a client
- Every error response sets `X-Request-Id` (= `error.request_id`) and carries `retryable`
- `isinstance` checks MUST work — never raise bare `Exception` from domain code
- Use `raise ... from exc` to preserve the exception chain for debugging
- Log errors ONCE at the top of the call stack (`error_response`) — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type (repo maps SQLAlchemy errors, service maps business rule violations)
- Catch-all exception handler MUST exist — unhandled exceptions MUST NOT crash the server or leak details
- Rate limit (429) and unavailable (503) responses MUST include the `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
