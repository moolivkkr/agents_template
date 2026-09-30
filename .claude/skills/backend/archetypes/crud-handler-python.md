---
skill: crud-handler-python
description: Python FastAPI handler archetype — route decorators, Pydantic v2 request/response models, dependency injection, cursor pagination, error mapping, auth dependencies, structured logging
version: "1.0"
tags:
  - python
  - fastapi
  - handler
  - http
  - archetype
  - backend
---

# CRUD Handler Archetype — Python (FastAPI)

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-handler-go.md` (Go/chi). Both produce the one response envelope in `~/.claude/skills/api/response-envelope.md` — success `{data, meta}`, error `{error}`, never both; list metadata in `meta.pagination`. If this file and the envelope ever disagree, the envelope wins.

Complete FastAPI handler set for CRUD endpoints. Every generated Python handler MUST follow this pattern.

## Domain Types — Pydantic v2 Models

```python
# app/schemas/base.py
# The shape is ~/.claude/skills/api/response-envelope.md. Error bodies are written by
# app/errors/handlers.py (error-handling-python.md); the error models here document them in OpenAPI.

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    """Success metadata. request_id equals the X-Request-Id response header."""

    request_id: str


class Pagination(BaseModel):
    """Cursor pagination — the only kind. Next page: ?cursor=<next_cursor>&limit=<n>."""

    next_cursor: str | None  # null when has_more is false
    has_more: bool
    limit: int
    # total_count: int — add only if the count is cheap AND documented; omit the key rather than send null


class ListMeta(Meta):
    """Metadata for list responses."""

    pagination: Pagination


class Envelope(BaseModel, Generic[T]):
    """Wraps a single resource response: {"data": T, "meta": {"request_id"}}."""

    data: T
    meta: Meta


class ListEnvelope(BaseModel, Generic[T]):
    """Wraps a list response. data is [] when empty, never null."""

    data: list[T]
    meta: ListMeta


class FieldErrorBody(BaseModel):
    """One entry of error.details[] — a field-level problem."""

    field: str
    code: str  # lower_snake, stable
    message: str


class APIError(BaseModel):
    """The error object. No data key, no detail field."""

    code: str  # UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, ...
    message: str
    details: list[FieldErrorBody] | None = None  # VALIDATION_FAILED only; omitted otherwise
    request_id: str
    retryable: bool


class ErrorBody(BaseModel):
    """Error envelope — use in `responses={404: {"model": ErrorBody}}` for OpenAPI."""

    error: APIError
```

## Widget Schemas — Request / Response Models

```python
# app/schemas/widget.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WidgetResponse(BaseModel):
    """Wire format for widget responses."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    version: int

    model_config = ConfigDict(from_attributes=True)


class CreateWidgetRequest(BaseModel):
    """Request body for creating a widget."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        return v.strip()


class UpdateWidgetRequest(BaseModel):
    """Request body for updating a widget."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    version: int = Field(ge=1, description="Optimistic lock — must match current version")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        return v.strip()
```

## Auth Dependencies

```python
# app/dependencies/auth.py

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import ForbiddenError, UnauthenticatedError

# auto_error=False: a missing header reaches get_current_user, which raises UnauthenticatedError
# (401 UNAUTHENTICATED in the envelope) instead of FastAPI's own {"detail": "Not authenticated"}.
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user extracted from JWT."""

    user_id: UUID
    tenant_id: UUID
    roles: list[str]


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Dependency that extracts and validates the JWT bearer token.
    Sets the current user on the request state for downstream use.

    Replace the token decode logic with your JWT library (python-jose, PyJWT, etc.).
    """
    if credentials is None:
        raise UnauthenticatedError()
    token = credentials.credentials
    try:
        # Replace with real JWT decode
        payload = decode_jwt(token)  # noqa: F821 — placeholder
        user = CurrentUser(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            roles=payload.get("roles", []),
        )
        request.state.current_user = user
        return user
    except Exception as exc:
        raise UnauthenticatedError() from exc  # the decode error stays in the chain, never in the body


def require_role(*roles: str):
    """
    Dependency factory that enforces role-based access.

    Usage:
        @router.post("/", dependencies=[Depends(require_role("admin", "editor"))])
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            raise ForbiddenError()
        return user

    return _check
```

## Request ID Middleware

```python
# app/middleware/request_id.py

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Retrieve the current request ID from context."""
    return request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique request_id into every request and response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = rid
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = rid
            return response
        finally:
            request_id_ctx.reset(token)
```

## Router and Handler

```python
# app/api/v1/widgets.py

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies.auth import CurrentUser, get_current_user
from app.middleware.request_id import get_request_id
from app.schemas.base import (
    Envelope,
    ListEnvelope,
    ListMeta,
    Meta,
    Pagination,
)
from app.schemas.widget import CreateWidgetRequest, UpdateWidgetRequest, WidgetResponse
from app.services.widget import WidgetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widgets", tags=["widgets"])


# ---------------------------------------------------------------------------
# Dependency: inject the service
# ---------------------------------------------------------------------------

def get_widget_service() -> WidgetService:
    """
    Override this dependency in tests or use FastAPI's dependency_overrides.
    In production, wire via the application lifespan or a DI container.
    """
    raise NotImplementedError("wire WidgetService in app startup")


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=Envelope[WidgetResponse],
    status_code=201,
    summary="Create a widget",
)
async def create_widget(
    body: CreateWidgetRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
) -> Envelope[WidgetResponse]:
    req_id = get_request_id()
    logger.info("create_widget", extra={"request_id": req_id, "tenant_id": str(user.tenant_id)})

    result = await svc.create(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        name=body.name,
        description=body.description,
    )

    return Envelope(
        data=WidgetResponse.model_validate(result),
        meta=Meta(request_id=req_id),
    )


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

@router.get(
    "/{widget_id}",
    response_model=Envelope[WidgetResponse],
    summary="Get a widget by ID",
)
async def get_widget(
    widget_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
) -> Envelope[WidgetResponse]:
    req_id = get_request_id()

    result = await svc.get(tenant_id=user.tenant_id, widget_id=widget_id)

    return Envelope(
        data=WidgetResponse.model_validate(result),
        meta=Meta(request_id=req_id),
    )


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

@router.put(
    "/{widget_id}",
    response_model=Envelope[WidgetResponse],
    summary="Update a widget",
)
async def update_widget(
    widget_id: UUID,
    body: UpdateWidgetRequest,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
) -> Envelope[WidgetResponse]:
    req_id = get_request_id()
    logger.info("update_widget", extra={"request_id": req_id, "widget_id": str(widget_id)})

    result = await svc.update(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        widget_id=widget_id,
        name=body.name,
        description=body.description,
        version=body.version,
    )

    return Envelope(
        data=WidgetResponse.model_validate(result),
        meta=Meta(request_id=req_id),
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@router.delete(
    "/{widget_id}",
    status_code=204,
    summary="Delete a widget (soft delete)",
)
async def delete_widget(
    widget_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
) -> None:
    req_id = get_request_id()
    logger.info("delete_widget", extra={"request_id": req_id, "widget_id": str(widget_id)})

    await svc.delete(tenant_id=user.tenant_id, widget_id=widget_id)
    # FastAPI returns 204 No Content automatically when return is None
```

## Pagination — cursor only

List endpoints take `?cursor=<next_cursor>&limit=<n>` and return `meta.pagination`. There is no offset
or page-number variant: offset pages skip or repeat rows under concurrent writes, and `OFFSET 10000`
still scans 10,000 rows. For "jump to page N" admin tables, filter instead (date range, search, status).
If a spec truly needs numbered pages, record it in `docs/DECISIONS.md`; the response still uses the
envelope.

## List Handler with Cursor Pagination and Filters

```python
# Allowed sort and filter fields — prevents SQL injection by allow-listing
ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "name"}
ALLOWED_FILTER_FIELDS = {"status", "priority", "category"}


@router.get(
    "/",
    response_model=ListEnvelope[WidgetResponse],
    summary="List widgets (cursor pagination)",
)
async def list_widgets(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
    cursor: str | None = Query(None, description="Opaque next_cursor from the previous page"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
) -> ListEnvelope[WidgetResponse]:
    req_id = get_request_id()

    # Validate sort field against allow-list
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"

    # Extract dynamic field filters: ?filter[status]=active&filter[priority]=high
    field_filters: dict[str, str] = {}
    for key, value in request.query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
            field = key[7:-1]
            if field in ALLOWED_FILTER_FIELDS:
                field_filters[field] = value

    result = await svc.list(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        field_filters=field_filters,
    )

    # data is [] (never null) when empty; next_cursor is null when has_more is false
    return ListEnvelope(
        data=[WidgetResponse.model_validate(item) for item in result.items],
        meta=ListMeta(
            request_id=req_id,
            pagination=Pagination(
                next_cursor=result.cursor if result.has_more else None,
                has_more=result.has_more,
                limit=limit,
            ),
        ),
    )
```

## Error Mapping — FastAPI Exception Handlers

Error bodies are written by `app/errors/handlers.py` (`error-handling-python.md`), the only place the
error envelope is built. Handlers never format errors themselves: they raise, or let the service's
`AppError` propagate. `register_exception_handlers(app)` replaces FastAPI's defaults, which answer
`{"detail": ...}` (and 422 for request validation):

- `AppError` subclasses → their own status and code (`NotFoundError` → 404 `NOT_FOUND`, ...)
- `RequestValidationError` (pydantic body/query/path) → 400 `VALIDATION_FAILED` with `details[]`;
  unparseable JSON or an empty body → 400 `MALFORMED_REQUEST`
- `HTTPException` (unknown route, wrong method) → re-shaped by status; `exc.detail` is never sent
- any other exception → 500 `INTERNAL` with a generic message; the cause is logged under `request_id`

Every error response sets `X-Request-Id` (= `error.request_id`); 429/503 set `Retry-After`; 401 sets
`WWW-Authenticate: Bearer`.

## Application Wiring

```python
# app/main.py

from fastapi import FastAPI

from app.api.v1 import widgets
from app.errors.handlers import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Widget API", version="1.0.0")

    # Middleware — order matters: outermost runs first
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routes
    app.include_router(widgets.router, prefix="/api/v1")

    return app
```

## Critical Rules

- Every handler MUST use dependency injection for services — never instantiate in the handler
- Every handler MUST extract `request_id` from context and include it in logs
- Tenant ID comes from the authenticated `CurrentUser` dependency — NEVER from path params or body
- Request validation is automatic via Pydantic — leverage `Field` constraints and `field_validator`
- Error responses MUST map domain errors (`AppError` subclasses) to correct HTTP status codes
- Internal error messages MUST NOT leak to clients — return generic message for 500s
- Pagination is cursor-only (`?cursor=&limit=`) and MUST bound `limit` via `Query(ge=1, le=100)` — out of range is 400 `VALIDATION_FAILED`; never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST follow `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}` for success (lists add `meta.pagination` `{next_cursor, has_more, limit}` and `data` is `[]` when empty), `{"error": {code, message, details?, request_id, retryable}}` for failure, never both
- DELETE returns 204 No Content — `status_code=204` with `None` return
- POST create returns 201 Created — `status_code=201`
- Use `response_model` on every endpoint for OpenAPI schema generation and response validation
- Input sanitization (`.strip()`) MUST happen in Pydantic validators, not in the handler
