---
skill: crud-handler-python
description: Python FastAPI handler archetype — route decorators, Pydantic v2 request/response models, dependency injection, cursor + offset pagination, error mapping, auth dependencies, structured logging
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

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-handler.md` (Go/chi). Both produce identical response envelopes so frontend clients can use a single parsing strategy.

Complete FastAPI handler set for CRUD endpoints. Every generated Python handler MUST follow this pattern.

## Domain Types — Pydantic v2 Models

```python
# app/schemas/base.py

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Standard response metadata."""

    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=None))


class ListMeta(Meta):
    """Metadata for cursor-paginated list responses."""

    cursor: str | None = None
    has_more: bool
    total: int


class OffsetListMeta(Meta):
    """Metadata for offset-paginated list responses."""

    page: int
    per_page: int
    total: int
    total_pages: int


class Envelope(BaseModel, Generic[T]):
    """Wraps a single resource response."""

    data: T
    meta: Meta


class ListEnvelope(BaseModel, Generic[T]):
    """Wraps a cursor-paginated list response."""

    data: list[T]
    meta: ListMeta


class PageLinks(BaseModel):
    """HATEOAS navigation links for offset pagination."""

    self_link: str = Field(alias="self")
    next: str | None = None
    prev: str | None = None
    first: str
    last: str

    model_config = ConfigDict(populate_by_name=True)


class OffsetListEnvelope(BaseModel, Generic[T]):
    """Wraps an offset-paginated list response."""

    data: list[T]
    meta: OffsetListMeta
    links: PageLinks


class ErrorDetail(BaseModel):
    """Standard error response detail."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail
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

from app.errors import UnauthorizedError

bearer_scheme = HTTPBearer()


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user extracted from JWT."""

    user_id: UUID
    tenant_id: UUID
    roles: list[str]


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Dependency that extracts and validates the JWT bearer token.
    Sets the current user on the request state for downstream use.

    Replace the token decode logic with your JWT library (python-jose, PyJWT, etc.).
    """
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
        raise UnauthorizedError("invalid or expired token") from exc


def require_role(*roles: str):
    """
    Dependency factory that enforces role-based access.

    Usage:
        @router.post("/", dependencies=[Depends(require_role("admin", "editor"))])
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            from app.errors import ForbiddenError

            raise ForbiddenError(action="access", resource="this endpoint")
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
from app.errors import AppError, BadRequestError, ValidationError
from app.middleware.request_id import get_request_id
from app.schemas.base import (
    Envelope,
    ListEnvelope,
    ListMeta,
    Meta,
    OffsetListEnvelope,
    OffsetListMeta,
    PageLinks,
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

## Pagination Strategy — When to Use Which

| Strategy | Use When | Query Params | Example |
|----------|----------|--------------|---------|
| **Cursor** (default) | Public APIs, real-time feeds, large datasets, infinite scroll | `?cursor=abc&page_size=20` | User-facing list endpoints |
| **Offset** | Admin/reporting UIs, dashboards, "jump to page N", data export previews | `?page=3&per_page=20` | Back-office tables, audit logs |

**Default to cursor pagination.** Use offset only for admin/reporting UIs where users need to jump to arbitrary pages. Offset pagination degrades at high page numbers (OFFSET 10000 still scans 10000 rows).

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
    cursor: str | None = Query(None, description="Opaque cursor from previous response"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
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
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        field_filters=field_filters,
    )

    return ListEnvelope(
        data=[WidgetResponse.model_validate(item) for item in result.items],
        meta=ListMeta(
            request_id=req_id,
            cursor=result.cursor,
            has_more=result.has_more,
            total=result.total,
        ),
    )
```

## List Handler with Offset Pagination (Admin/Reporting UIs)

```python
@router.get(
    "/admin",
    response_model=OffsetListEnvelope[WidgetResponse],
    summary="List widgets (offset pagination, admin UI)",
)
async def list_widgets_admin(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    svc: WidgetService = Depends(get_widget_service),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> OffsetListEnvelope[WidgetResponse]:
    req_id = get_request_id()

    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"

    field_filters: dict[str, str] = {}
    for key, value in request.query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
            field = key[7:-1]
            if field in ALLOWED_FILTER_FIELDS:
                field_filters[field] = value

    result = await svc.list_offset(
        tenant_id=user.tenant_id,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        field_filters=field_filters,
    )

    total_pages = (result.total + per_page - 1) // per_page if per_page > 0 else 0
    base_path = request.url.path

    links = PageLinks(
        **{
            "self": f"{base_path}?page={page}&per_page={per_page}",
            "first": f"{base_path}?page=1&per_page={per_page}",
            "last": f"{base_path}?page={total_pages}&per_page={per_page}",
            "next": f"{base_path}?page={page + 1}&per_page={per_page}" if page < total_pages else None,
            "prev": f"{base_path}?page={page - 1}&per_page={per_page}" if page > 1 else None,
        }
    )

    return OffsetListEnvelope(
        data=[WidgetResponse.model_validate(item) for item in result.items],
        meta=OffsetListMeta(
            request_id=req_id,
            page=page,
            per_page=per_page,
            total=result.total,
            total_pages=total_pages,
        ),
        links=links,
    )
```

## Error Mapping — FastAPI Exception Handlers

```python
# app/errors/handlers.py

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.errors import AppError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Mount all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")

        if exc.http_status >= 500:
            logger.error(
                "internal error",
                extra={
                    "code": exc.code,
                    "message": exc.message,
                    "cause": str(exc.__cause__) if exc.__cause__ else None,
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )

        headers: dict[str, str] = {}
        if exc.http_status == 429 and "retry_after_seconds" in (exc.details or {}):
            headers["Retry-After"] = str(exc.details["retry_after_seconds"])
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
        """Catch-all: never leak internal details to clients."""
        req_id = getattr(request.state, "request_id", "")
        logger.error(
            "unhandled error",
            extra={
                "error": str(exc),
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
- Pagination MUST enforce max page size (100) via `Query(le=100)` — never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST use the envelope format: `{"data": T, "meta": {...}}`
- DELETE returns 204 No Content — `status_code=204` with `None` return
- POST create returns 201 Created — `status_code=201`
- Use `response_model` on every endpoint for OpenAPI schema generation and response validation
- Input sanitization (`.strip()`) MUST happen in Pydantic validators, not in the handler
