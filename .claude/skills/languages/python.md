> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

---
skill: python
description: Python patterns — type hints, dataclasses/pydantic, async, dependency injection, pytest, project layout and packaging
version: "1.0"
tags:
  - python
  - async
  - pydantic
  - patterns
  - testing
---

# Python patterns and conventions for building reliable, maintainable applications.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): every block type-checked and imported; the FastAPI blocks run as one app through TestClient, the SQLAlchemy tenant filter on SQLite, the async/perf helpers against a local HTTP server, the ML pipeline on CPU, the Django blocks on SQLite with a real JWT; the repository, pooling, Alembic env, transaction, fixture and asyncpg blocks against PostgreSQL 16 (`run.sh --live`). FastAPI 0.142.2, Pydantic 2.13.5, SQLAlchemy 2.1.1, asyncpg 0.31.0, Alembic 1.20.0, structlog 26.1.0, httpx 0.28.1, pytest 9.1.1, pytest-asyncio 1.4.0, factory_boy 3.3.3, testcontainers 4.15.0, numpy 2.5.3, torch 2.14.1, Django 6.1.1, DRF 3.18.1, djangorestframework-simplejwt 5.5.1, django-model-utils 5.0.0.

## Project Structure
```
src/
  myapp/
    __init__.py
    domain/        # entities, value objects
    services/      # business logic
    repositories/  # data access
    api/           # HTTP layer
    config.py
tests/
  unit/
  integration/
pyproject.toml     # prefer over setup.py
```

## Type Hints
- Use everywhere — function signatures, class attributes, return types
- Prefer `X | None` over `Optional[X]` (Python 3.10+)
- Use `TypeAlias` for complex types; `Protocol` for structural typing
- Run `mypy --strict` in CI

## Data Validation
- Use Pydantic v2 for all data at system boundaries (API in/out, config)
- `dataclasses` for pure internal data with no validation
- Never use bare `dict` for structured data — define a model

## Error Handling
```python
# Define domain errors
class UserNotFoundError(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id} not found")

# Wrap infrastructure errors at boundary
try:
    return await db.get_user(user_id)
except DBConnectionError as e:
    raise RepositoryError("Failed to fetch user") from e
```
- Never `except Exception` without re-raising or logging
- Use `from e` to preserve cause chain

## Async
- `async/await` throughout for I/O bound code
- Use `asyncio.gather()` for concurrent independent tasks
- Never mix sync and async — use `run_in_executor` if unavoidable
- `anyio` for library code; `asyncio` directly for app code

## Testing (pytest)
```python
@pytest.mark.parametrize("input,expected", [
    ("valid@email.com", True),
    ("not-an-email", False),
])
def test_email_validation(input: str, expected: bool) -> None:
    assert validate_email(input) == expected
```
- Fixtures for shared setup; `conftest.py` for cross-module fixtures
- `pytest-asyncio` for async tests
- Mock only external I/O — never mock domain logic

## Logging
```python
import structlog
log = structlog.get_logger()
log.info("user_created", user_id=user.id, tenant_id=user.tenant_id)  # ids, never the email (PII)
```
- Structured logging always — never f-strings in log calls
- Never log PII (emails, names) or secrets — log ids and let the reader look them up
- Bind request context (request_id, user_id) at middleware level

## Type Safety

```python
from typing import NotRequired, TypedDict, Protocol, Literal, TypeVar, overload, Generic
# pydantic/FastAPI need typing_extensions.TypedDict on Python < 3.12

# TypeVar for generic types and functions — defined before anything uses it
T = TypeVar("T")

# TypedDict for dictionaries with known shapes (API responses, configs)
class UserResponse(TypedDict):
    id: str
    email: str
    is_active: bool

# The API envelope (api/response-envelope.md): success = {data, meta}; lists add meta.pagination
class Pagination(TypedDict):
    next_cursor: str | None          # None when has_more is False
    has_more: bool
    limit: int
    total_count: NotRequired[int]    # only when cheap and the UI shows it

class Meta(TypedDict):
    request_id: str                  # = the X-Request-Id response header

class ListMeta(Meta):
    pagination: Pagination

class ApiResponse(TypedDict, Generic[T]):
    data: T
    meta: Meta

class PaginatedResponse(TypedDict, Generic[T]):
    data: list[T]                    # always a list — [] when empty, never None
    meta: ListMeta

# Protocol for structural typing — no inheritance required
class Repository(Protocol):
    async def find_by_id(self, id: str) -> dict | None: ...
    async def save(self, entity: dict) -> None: ...

# Any class with matching methods satisfies Repository — no explicit subclassing

# Literal types for fixed values
Status = Literal["active", "inactive", "suspended"]

def update_status(user_id: str, status: Status) -> None:
    ...  # type checker rejects update_status("x", "invalid")

# Generic function over T
def first_or_none(items: list[T]) -> T | None:
    return items[0] if items else None

# @overload for functions with multiple signatures
@overload
def fetch(id: str, *, required: Literal[True]) -> User: ...
@overload
def fetch(id: str, *, required: Literal[False] = ...) -> User | None: ...

def fetch(id: str, *, required: bool = False) -> User | None:
    user = db.get(id)
    if user is None and required:
        raise UserNotFoundError(id)
    return user
```

- Run `mypy --strict` in CI — no exceptions
- Use `TypedDict` for external data shapes (API payloads, JSON config)
- `Protocol` for structural typing — enables dependency inversion without inheritance
- `Literal` for restricted string/int values — catches typos at type-check time
- `@overload` for functions whose return type depends on input values
- All function signatures fully annotated — including `-> None` for void returns

## Performance

```python
import asyncio
import functools
import tomllib
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

import httpx

# Generator expressions for large data — avoid materializing full list
def process_large_file(path: Path) -> int:
    # Generator: O(1) memory regardless of file size
    with open(path) as f:
        return sum(1 for line in f if "ERROR" in line)
    # NOT: len([line for line in f if "ERROR" in line])  # O(n) memory

# __slots__ for classes with many instances — 40-50% memory savings
@dataclass(slots=True)
class Point:
    x: float
    y: float
    z: float

# Without slots: each instance has a __dict__ (~200 bytes overhead)
# With slots: no __dict__, fields stored directly (~64 bytes per instance)

# functools.lru_cache for expensive pure functions
@functools.lru_cache(maxsize=256)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# For methods, use functools.cached_property
class Config:
    def __init__(self, raw_content: str) -> None:
        self._raw_content = raw_content

    @functools.cached_property
    def parsed(self) -> dict:
        return tomllib.loads(self._raw_content)  # stdlib TOML parser (3.11+)

# asyncio for I/O-bound concurrency — one client (one connection pool) for all requests
async def fetch_all(urls: list[str]) -> list[httpx.Response]:
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(client.get(url) for url in urls))

# multiprocessing for CPU-bound work
def process_images(paths: list[Path]) -> list[Result]:
    with Pool() as pool:
        return pool.map(resize_image, paths)
```

- Generator expressions over list comprehensions when you don't need the full list
- `__slots__` (or `@dataclass(slots=True)`) for data classes with many instances
- `functools.lru_cache` for pure functions — set `maxsize` to bound memory
- `asyncio` for I/O-bound work (HTTP, DB, file I/O) — never block the event loop
- `multiprocessing.Pool` for CPU-bound work (image processing, computation)
- Avoid global mutable state — it breaks multiprocessing and makes testing painful

## ML-Specific Patterns

```python
import json
from collections.abc import Generator
from contextlib import contextmanager
from itertools import batched
from pathlib import Path

import numpy as np
import torch

# NumPy vectorization — 100x faster than Python loops
def normalize(data: np.ndarray) -> np.ndarray:
    # Vectorized: operates on entire array at C speed
    return (data - data.mean(axis=0)) / data.std(axis=0)
    # NOT: [[(x - mean) / std for x in row] for row in data]  # Python loop — slow

# Batch processing for model inference
def predict_batch(
    model: torch.nn.Module,
    inputs: list[np.ndarray],
    batch_size: int = 32,
) -> list[np.ndarray]:
    results: list[np.ndarray] = []
    for i in range(0, len(inputs), batch_size):
        batch = torch.tensor(np.stack(inputs[i : i + batch_size]))
        with torch.no_grad():
            output = model(batch)
        results.extend(output.cpu().numpy())
    return results

# GPU memory management — explicit cleanup with context managers
@contextmanager
def gpu_scope(device: str = "cuda:0") -> Generator[None, None, None]:
    """Context manager for GPU operations with cleanup; a no-op where there is no CUDA device."""
    if not torch.cuda.is_available():
        yield
        return
    torch.cuda.set_device(device)
    try:
        yield
    finally:
        torch.cuda.synchronize()  # let queued kernels finish before their memory is released
        torch.cuda.empty_cache()

# Usage:
with gpu_scope():
    results = predict_batch(model, data)

# Data pipeline with generator chains — process streaming data in constant memory
def load_data(path: Path):
    """Generator: yields one record at a time (the file closes when the generator finishes)."""
    with open(path) as f:
        for line in f:
            yield json.loads(line)

def filter_valid(records):
    """Generator: filters without materializing."""
    for record in records:
        if record.get("status") == "active":
            yield record

def transform(records):
    """Generator: transforms without materializing."""
    for record in records:
        yield {
            "id": record["id"],
            "features": extract_features(record),
        }

# Chain generators — entire pipeline runs in O(1) memory
pipeline = transform(filter_valid(load_data(Path("data.jsonl"))))
for batch in batched(pipeline, 1000):
    process(batch)

# Reproducibility — seed everything
def set_seeds(seed: int = 42) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # For fully deterministic behavior:
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# Model versioning and experiment tracking
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ExperimentConfig:
    model_name: str
    learning_rate: float
    batch_size: int
    epochs: int
    seed: int = 42
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_artifact_path(self) -> Path:
        return Path(f"runs/{self.model_name}/{self.timestamp}")
```

- NumPy vectorization over Python loops — 10-100x speedup for array operations
- Batch processing for inference — amortizes overhead, controls memory usage
- GPU memory management: explicit `torch.cuda.empty_cache()`, context managers for scope
- Generator chains for data pipelines — process terabytes in constant memory
- Seed everything for reproducibility: `random`, `numpy`, `torch`, and CUDA
- Track experiments: config dataclass, artifact paths, versioned outputs

---

## Multi-Tenancy in Python

### FastAPI Tenant Dependency
```python
from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel
from uuid import UUID

class TokenClaims(BaseModel):
    """Claims of a JWT whose signature, expiry and audience get_verified_claims has already checked."""
    sub: str
    tenant_id: str                  # the token's tenant
    tenant_ids: list[str] = []      # multi-tenant users only: tenants X-Tenant-ID may select from

def resolve_tenant(claims: TokenClaims, requested: str | None) -> UUID | None:
    """The token's tenant, or one the X-Tenant-ID header SELECTS from the token's own list.
    A client header never grants a tenant on its own: anyone can send one."""
    chosen = requested or claims.tenant_id
    return UUID(chosen) if chosen in {claims.tenant_id, *claims.tenant_ids} else None

async def get_current_tenant(
    claims: TokenClaims = Depends(get_verified_claims),             # the auth dependency: 401 if missing/invalid
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),   # optional selector, checked below
) -> UUID:
    tenant_id = resolve_tenant(claims, x_tenant_id)
    if tenant_id is None:
        raise ForbiddenError()  # AppError → 403 envelope via the exception handler
    return tenant_id

# Use as dependency in every route. Lists: ?cursor=<opaque>&limit=<n> — cursor pagination only
@router.get("/orders")
async def list_orders(
    cursor: str | None = None,                      # meta.pagination.next_cursor from the previous page
    limit: int = Query(20, ge=1, le=100),           # out of range → 400 VALIDATION_FAILED (handler below)
    tenant_id: UUID = Depends(get_current_tenant),
    service: OrderService = Depends(get_order_service),
    request_id: str = Depends(get_request_id),
) -> PaginatedResponse[OrderResponse]:
    rows, next_cursor = await service.list_orders(tenant_id, cursor=cursor, limit=limit)
    return {
        "data": [OrderResponse.model_validate(r) for r in rows],
        "meta": {
            "request_id": request_id,
            "pagination": {"next_cursor": next_cursor, "has_more": next_cursor is not None, "limit": limit},
        },
    }
```

### SQLAlchemy Tenant Filter on Every Query
```python
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, with_loader_criteria

current_tenant: ContextVar[UUID] = ContextVar("current_tenant")  # set by TenantMiddleware below

class TenantScoped:
    """Mixin for every tenant-owned model (declares the column the filter uses)."""
    tenant_id: Mapped[UUID] = mapped_column(index=True)

@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(state: ORMExecuteState) -> None:
    """Adds WHERE tenant_id = <current tenant> to every ORM SELECT, UPDATE and DELETE on a TenantScoped
    model, in every Session (an AsyncSession runs on one)."""
    if (state.is_select or state.is_update or state.is_delete) and not (
        state.is_column_load or state.is_relationship_load
    ):
        tenant_id = current_tenant.get()  # LookupError when no tenant is set: fails closed, never unfiltered
        state.statement = state.statement.options(
            with_loader_criteria(TenantScoped, lambda cls: cls.tenant_id == tenant_id, include_aliases=True)
        )
```
- SQLAlchemy's own global-filter hook (`do_orm_execute` + `with_loader_criteria`): a wrapper around
  `session.execute()` can't know which model a statement targets, and code that holds the session directly
  bypasses it
- Defense in depth: PostgreSQL row-level security on the same column (`backend/archetypes/migration-pattern-python.md`)

### Tenant Middleware
```python
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # request.state.claims: set by the auth middleware after verifying the JWT. It must run first,
        # so add it AFTER this one (the last add_middleware call is the outermost).
        claims: TokenClaims | None = getattr(request.state, "claims", None)
        # Middleware runs outside FastAPI's AppError handler — build the envelope directly
        if claims is None:
            return error_response(request, UnauthenticatedError())
        tenant_id = resolve_tenant(claims, request.headers.get("X-Tenant-ID"))  # header can only select
        if tenant_id is None:
            return error_response(request, ForbiddenError())

        token = current_tenant.set(tenant_id)
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))
        try:
            response = await call_next(request)
            return response
        finally:
            current_tenant.reset(token)
            structlog.contextvars.unbind_contextvars("tenant_id")
```

---

## Error Handling Patterns

### Exception Hierarchy
```python
from typing import TypedDict

class FieldError(TypedDict):
    field: str
    code: str      # stable lower_snake: required, invalid_format, too_long, …
    message: str   # fixed catalog text — never the validator's own message

class AppError(Exception):
    """Base for all domain errors — serialized as the error envelope (api/response-envelope.md)."""
    def __init__(
        self, message: str, code: str, status_code: int = 500, *,
        details: list[FieldError] | None = None, retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message          # user-safe catalog text: the only text a client sees
        self.code = code                # UPPER_SNAKE, stable
        self.status_code = status_code
        self.details = details or []
        self.retryable = retryable
        self.retry_after: int | None = None

class MalformedRequestError(AppError):   # 400: unparseable JSON, wrong content type
    def __init__(self) -> None:
        super().__init__("The request could not be read.", "MALFORMED_REQUEST", 400)

class ValidationError(AppError):         # 400: details[] lists the fields
    def __init__(self, details: list[FieldError]) -> None:
        super().__init__("Some fields are invalid.", "VALIDATION_FAILED", 400, details=details)

class UnauthenticatedError(AppError):    # 401: missing, invalid or expired credentials
    def __init__(self) -> None:
        super().__init__("Sign in to continue.", "UNAUTHENTICATED", 401)

class ForbiddenError(AppError):          # 403: authenticated, not allowed
    def __init__(self) -> None:
        super().__init__("You don't have permission to do this.", "FORBIDDEN", 403)

class NotFoundError(AppError):           # 404: missing OR another tenant's object (never 403)
    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found.", "NOT_FOUND", 404)

class ConflictError(AppError):           # 409: duplicate, version mismatch, state conflict
    def __init__(self, message: str = "This was changed by someone else. Reload and try again.") -> None:
        super().__init__(message, "CONFLICT", 409)

class BusinessRuleError(AppError):       # 422: valid shape, rejected by a domain rule
    def __init__(self, message: str) -> None:
        super().__init__(message, "BUSINESS_RULE_VIOLATION", 422)

class RateLimitError(AppError):          # 429: Retry-After header, retryable
    def __init__(self, retry_after: int = 60) -> None:
        super().__init__("Too many requests. Try again shortly.", "RATE_LIMITED", 429, retryable=True)
        self.retry_after = retry_after

class UnavailableError(AppError):        # 503: a dependency failed or timed out
    # raise UnavailableError("billing") from exc — service name and cause reach the log, not the client
    def __init__(self, service: str) -> None:
        super().__init__("The service is temporarily unavailable.", "UNAVAILABLE", 503, retryable=True)
        self.service = service
        self.retry_after = 5

class InternalError(AppError):           # 500: generic message; the cause goes to the log
    def __init__(self) -> None:
        super().__init__("Something went wrong.", "INTERNAL", 500)
```

### FastAPI Exception Handlers
FastAPI's defaults are not the envelope: `HTTPException` and unknown routes answer `{"detail": ...}`, and request
validation answers 422 with pydantic's error list. Replace all of them — every error body goes through
`error_response()`.
```python
from collections.abc import Mapping

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()
app = FastAPI()

def get_request_id(request: Request) -> str:
    # Set by the request-id middleware (added last = outermost), which also sets the X-Request-Id header
    return getattr(request.state, "request_id", "")

def error_response(request: Request, exc: AppError, headers: Mapping[str, str] | None = None) -> JSONResponse:
    """The only function that writes an error body."""
    error: dict = {"code": exc.code, "message": exc.message}
    if exc.details:
        error["details"] = exc.details
    error["request_id"] = get_request_id(request)
    error["retryable"] = exc.retryable
    headers = dict(headers or {})
    headers["X-Request-Id"] = error["request_id"]  # set here too: a 500 from the catch-all bypasses middleware
    if exc.retry_after:
        headers.setdefault("Retry-After", str(exc.retry_after))
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=headers)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.warning("app_error", code=exc.code, request_id=get_request_id(request), path=request.url.path,
                exc_info=exc if exc.status_code >= 500 else None)  # cause chain: logs only
    return error_response(request, exc)

# pydantic error type → a details[].code from the envelope's closed set (api/response-envelope.md) + a
# catalog message. pydantic's "msg" (and "input", which echoes the submitted value) never reaches the client.
_OUT_OF_RANGE = ("out_of_range", "This value is out of range.")
_INVALID_TYPE = ("invalid_type", "This value has the wrong type.")
_INVALID_FORMAT = ("invalid_format", "This value has the wrong format.")
PYDANTIC_FIELD_ERRORS: dict[str, tuple[str, str]] = {
    "missing": ("required", "This field is required."),
    "string_too_short": ("too_short", "This value is too short."),
    "too_short": ("too_short", "This value is too short."),
    "string_too_long": ("too_long", "This value is too long."),
    "too_long": ("too_long", "This value is too long."),
    **dict.fromkeys(["greater_than", "greater_than_equal", "less_than", "less_than_equal", "multiple_of"],
                    _OUT_OF_RANGE),
    **dict.fromkeys(["int_parsing", "int_type", "int_from_float", "float_parsing", "float_type", "bool_parsing",
                     "bool_type", "string_type", "decimal_parsing", "list_type", "dict_type", "model_type",
                     "uuid_type"], _INVALID_TYPE),
    **dict.fromkeys(["uuid_parsing", "string_pattern_mismatch", "date_parsing", "date_from_datetime_parsing",
                     "datetime_parsing", "datetime_from_date_parsing", "url_parsing"], _INVALID_FORMAT),
    "enum": ("invalid_value", "Choose one of the allowed values."),
    "literal_error": ("invalid_value", "Choose one of the allowed values."),
    "extra_forbidden": ("unknown_field", "This field is not accepted."),
}

@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if any(e["type"] == "json_invalid" for e in errors):   # unparseable body → MALFORMED_REQUEST
        return error_response(request, MalformedRequestError())
    details: list[FieldError] = []
    for e in errors:
        code, message = PYDANTIC_FIELD_ERRORS.get(e["type"], ("invalid_value", "This value is invalid."))
        details.append({"field": ".".join(str(p) for p in e["loc"][1:]),  # drop "body"/"query"/"header"
                        "code": code, "message": message})
    return error_response(request, ValidationError(details))  # 400, not FastAPI's default 422

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Unknown route (404), wrong method (405), any HTTPException: pick the code by status; exc.detail is not copied
    err: AppError
    if exc.status_code == 404:
        err = NotFoundError("Resource")
    elif exc.status_code == 401:
        err = UnauthenticatedError()
    elif exc.status_code == 403:
        err = ForbiddenError()
    elif exc.status_code == 429:
        err = RateLimitError()
    elif exc.status_code < 500:
        err = AppError("The request could not be read.", "MALFORMED_REQUEST", exc.status_code)
    else:
        err = InternalError()
    return error_response(request, err, headers=exc.headers)  # keeps e.g. Allow on a 405

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", request_id=get_request_id(request), path=request.url.path)
    return error_response(request, InternalError())  # generic 500; the cause stays in the log
```

---

## Repository Pattern in Python

### Async SQLAlchemy Repository
```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped

class TenantModel:
    """The columns BaseRepository relies on (a declarative mixin for tenant-owned models)."""
    id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    created_at: Mapped[datetime]
    deleted_at: Mapped[datetime | None]

class BaseRepository[T: TenantModel]:
    """Generic async repository with tenant isolation and soft delete."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def find_by_id(self, tenant_id: UUID, entity_id: UUID) -> T | None:
        stmt = (
            select(self._model)
            .where(
                self._model.tenant_id == tenant_id,
                self._model.id == entity_id,
                self._model.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_paginated(
        self, tenant_id: UUID, *, cursor: str | None = None, limit: int = 20,
    ) -> tuple[list[T], str | None]:
        # Keyset on (created_at, id): unique and stable, so no row repeats or goes missing between pages
        # even when timestamps tie. The cursor is opaque (base64 of both values; crud-repository-python.md).
        stmt = (
            select(self._model)
            .where(self._model.tenant_id == tenant_id, self._model.deleted_at.is_(None))
            .order_by(self._model.created_at.desc(), self._model.id.desc())
            .limit(limit + 1)
        )
        if cursor:
            created_at, last_id = decode_cursor(cursor)
            stmt = stmt.where(tuple_(self._model.created_at, self._model.id) < (created_at, last_id))

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
        return rows, next_cursor

    async def save(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def soft_delete(self, tenant_id: UUID, entity_id: UUID) -> None:
        stmt = (
            update(self._model)
            .where(
                self._model.tenant_id == tenant_id,
                self._model.id == entity_id,
            )
            .values(deleted_at=func.now())
        )
        await self._session.execute(stmt)
```

### Alembic Migration Patterns
```python
# alembic/env.py — configure for async
import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)

    async def do_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(do_migrations())

# Migration naming: YYYYMMDD_HHMMSS_description.py
# Always include both upgrade() and downgrade()
# Test migrations in CI: upgrade head, then downgrade base, then upgrade head again
```

### Connection Pooling
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    settings.DATABASE_URL,  # from the environment — never credentials in code
    pool_size=20,           # base connections
    max_overflow=10,        # extra connections under load
    pool_timeout=30,        # wait time for connection from pool
    pool_recycle=3600,      # recycle connections after 1 hour
    pool_pre_ping=True,     # validate connections before use
)
```

---

## Service Pattern in Python

### FastAPI Dependency Injection
```python
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

def get_user_repository(
    # scope="function": the commit after `yield` runs before the response is sent, so a failed commit is
    # a 500, not a 201 for data that was never saved (the default scope runs it after the response)
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> UserRepository:
    return UserRepository(session)

def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    cache: CacheService = Depends(get_cache),
    events: EventPublisher = Depends(get_event_publisher),
) -> UserService:
    return UserService(repo, cache, events)

# Handler — thin, no business logic; returns the success envelope {data, meta}
@router.post("/users", status_code=201)
async def create_user(
    request: CreateUserRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    service: UserService = Depends(get_user_service),
    request_id: str = Depends(get_request_id),
) -> ApiResponse[UserResponse]:
    user = await service.create_user(tenant_id, request)
    return {"data": UserResponse.model_validate(user), "meta": {"request_id": request_id}}
```

### Transaction Management
```python
class OrderService:
    def __init__(self, session: AsyncSession, repo: OrderRepository) -> None:
        self._session = session
        self._repo = repo

    async def create_order(self, tenant_id: UUID, request: CreateOrderRequest) -> Order:
        """Transaction spans the entire service method. The order is read after the commit, so the
        session needs expire_on_commit=False (an AsyncSession can't lazy-load expired attributes)."""
        async with self._session.begin():
            order = Order(tenant_id=tenant_id, **request.model_dump())
            order = await self._repo.save(order)
            # All operations in the same transaction
            await self._repo.update_inventory(tenant_id, order.items)
            await self._audit_log(tenant_id, "order.created", order.id)
            return order
```

---

## Testing in Python

### pytest Fixtures
```python
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer  # testcontainers.postgres is deprecated

@pytest.fixture(scope="session")
def postgres():
    """Real PostgreSQL via testcontainers — shared across all tests."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest_asyncio.fixture  # an async fixture (plain @pytest.fixture works only in asyncio_mode = "auto")
async def db_session(postgres) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(postgres.get_connection_url(driver="asyncpg"))  # default URL is psycopg2
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # expire_on_commit=False: an AsyncSession can't lazy-load, so objects must stay readable after a commit
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()  # reset state between tests
    await engine.dispose()

@pytest.fixture
def user_factory(db_session: AsyncSession):
    """Factory for creating test users with sensible defaults."""
    async def _create(**overrides) -> User:
        defaults = {
            "tenant_id": UUID("00000000-0000-0000-0000-000000000001"),
            "email": f"test-{uuid4().hex[:8]}@example.com",
            "name": "Test User",
        }
        user = User(**(defaults | overrides))
        db_session.add(user)
        await db_session.flush()
        return user
    return _create
```

### factory_boy for Test Data
```python
from uuid import UUID, uuid4

import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.orm import scoped_session, sessionmaker

# factory_boy writes through a (sync) Session; conftest binds it: Session.configure(bind=engine)
Session = scoped_session(sessionmaker())

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = Session
        sqlalchemy_session_persistence = "flush"

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(lambda: UUID("00000000-0000-0000-0000-000000000001"))
    email = factory.Sequence(lambda n: f"user-{n}@example.com")
    name = factory.Faker("name")

# Usage (in a test: building one writes it through the session)
def test_specific_email() -> None:
    user = UserFactory(email="specific@example.com")  # override only what matters
    assert user.email == "specific@example.com"
```

### Async Test Patterns
```python
import asyncio
from unittest.mock import AsyncMock

import pytest

@pytest.mark.asyncio
async def test_create_user_sends_welcome_email(
    user_service: UserService,
    mock_mailer: AsyncMock,
) -> None:
    request = CreateUserRequest(email="new@example.com", name="New User")
    user = await user_service.create_user(TENANT_ID, request)

    assert user.email == "new@example.com"
    mock_mailer.send.assert_awaited_once()

@pytest.mark.asyncio
async def test_concurrent_order_creation(order_service: OrderService) -> None:
    """Ensure optimistic locking prevents double-spend."""
    tasks = [
        order_service.create_order(TENANT_ID, make_order_request())
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    conflicts = [r for r in results if isinstance(r, ConflictError)]
    assert len(successes) >= 1
    assert len(successes) + len(conflicts) == 5
```

### monkeypatch vs mock
```python
# monkeypatch: replace attributes/env vars — test-scoped, auto-restored
def test_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    config = load_config()
    assert config.database_url == "postgresql://test"

# mock/AsyncMock: verify interactions with collaborators
from unittest.mock import AsyncMock

@pytest.fixture
def mock_mailer() -> AsyncMock:
    return AsyncMock(spec=Mailer)

# Rule: use monkeypatch for environment/config, mock for collaborator interactions
```

---

## Async Patterns

### Async Context Managers
```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg

@asynccontextmanager
async def managed_connection(pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.pool.PoolConnectionProxy, None]:
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)

# Usage (inside a coroutine)
async def ping(pool: asyncpg.Pool) -> None:
    async with managed_connection(pool) as conn:
        await conn.execute("SELECT 1")
```

### Task Groups (Python 3.11+)
```python
import asyncio

async def fetch_user_data(user_id: str) -> UserProfile:
    """Fetch multiple resources concurrently with structured concurrency."""
    async with asyncio.TaskGroup() as tg:
        profile_task = tg.create_task(fetch_profile(user_id))
        orders_task = tg.create_task(fetch_orders(user_id))
        prefs_task = tg.create_task(fetch_preferences(user_id))

    # All tasks complete or all are cancelled on first failure
    return UserProfile(
        profile=profile_task.result(),
        orders=orders_task.result(),
        preferences=prefs_task.result(),
    )
```

### Semaphores for Concurrency Limits
```python
import asyncio

import httpx

async def fetch_many(urls: list[str], max_concurrent: int = 10) -> list[httpx.Response]:
    """Limit concurrent HTTP requests to avoid overwhelming upstream."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient() as client:  # one client: one connection pool for every request
        async def _fetch(url: str) -> httpx.Response:
            async with semaphore:
                return await client.get(url)

        return await asyncio.gather(*[_fetch(url) for url in urls])
```

### Graceful Shutdown
```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Zero-downtime deploys. The server (uvicorn) owns SIGTERM/SIGINT: on the signal it stops accepting
    connections and lets in-flight requests finish (--timeout-graceful-shutdown), then runs the code after
    `yield`. Installing your own signal handlers would replace uvicorn's and it would never shut down."""
    app.state.db_pool = await create_db_pool()
    app.state.redis = create_redis()
    yield
    log.info("shutdown_started")
    await app.state.db_pool.close()
    await app.state.redis.aclose()  # redis-py 5+: aclose(); close() is deprecated
    log.info("shutdown_complete")

app = FastAPI(lifespan=lifespan)
```
- A plain asyncio worker (no server) installs the handlers itself: `loop.add_signal_handler` with
  `asyncio.get_running_loop()` (`backend/archetypes/worker-pattern-python.md`)

---

## Django-Specific Patterns

### Multi-Tenant Model Managers
```python
from django.db import models
from model_utils import FieldTracker

class TenantManager(models.Manager):
    """Automatically filters by tenant — prevents accidental cross-tenant reads."""

    def get_queryset(self):
        qs = super().get_queryset().filter(deleted_at__isnull=True)
        # Tenant filtering is applied via middleware-set thread-local (from the verified credential)
        from .middleware import get_current_tenant
        tenant_id = get_current_tenant()
        if not tenant_id:
            return qs.none()  # fail closed: no verified tenant → no rows (admin code uses all_objects)
        return qs.filter(tenant_id=tenant_id)

class Order(models.Model):
    tenant_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20)
    total = models.IntegerField(default=0)  # money in minor units (cents)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)

    objects = TenantManager()          # default: tenant-filtered
    all_objects = models.Manager()     # admin: unfiltered (use sparingly)
    tracker = FieldTracker()           # django-model-utils: the changed fields, for the audit signal

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "created_at"]),
        ]
```

### DRF Serializers
```python
from rest_framework import serializers

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "status", "total", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs: dict) -> dict:
        if attrs.get("total", 0) < 0:
            # code= becomes details[].code (one of the envelope's closed set); the EXCEPTION_HANDLER sends
            # a catalog message for it, as 400 VALIDATION_FAILED (see frameworks/drf.md)
            raise serializers.ValidationError({"total": "Must be non-negative"}, code="out_of_range")
        return attrs

    def create(self, validated_data: dict) -> Order:
        # Inject tenant_id from request context
        validated_data["tenant_id"] = self.context["request"].tenant_id
        return super().create(validated_data)
```

### Django Middleware Chain
```python
import threading

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

_thread_local = threading.local()

class TenantMiddleware:
    """Place after django.contrib.auth.middleware.AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = self._extract_tenant(request)
        _thread_local.tenant_id = tenant_id
        request.tenant_id = tenant_id
        try:
            return self.get_response(request)
        finally:
            _thread_local.tenant_id = None

    def _extract_tenant(self, request) -> str | None:
        # Only from a VERIFIED credential. A client header or subdomain alone is never trusted:
        # anyone can send X-Tenant-ID. (Multi-tenant users: a header may only select a tenant the
        # token lists — see resolve_tenant under Multi-Tenancy.)
        user = getattr(request, "user", None)  # session auth, set by AuthenticationMiddleware
        if user is not None and user.is_authenticated:
            return str(user.tenant_id)
        try:
            result = JWTAuthentication().authenticate(request)  # checks the signature and expiry
        except AuthenticationFailed:
            return None  # the DRF view then answers 401 with the envelope
        return result[1].get("tenant_id") if result else None

def get_current_tenant() -> str | None:
    return getattr(_thread_local, "tenant_id", None)
```

### Signals for Audit Logging
```python
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

@receiver(post_save, sender=Order)
def audit_order_change(sender, instance, created, **kwargs):
    action = "created" if created else "updated"
    AuditLog.objects.create(
        tenant_id=instance.tenant_id,
        entity_type="Order",
        entity_id=instance.id,
        action=action,
        actor_id=get_current_user_id(),
        changes=instance.tracker.changed(),  # django-model-utils FieldTracker
    )

@receiver(pre_delete, sender=Order)
def prevent_hard_delete(sender, instance, **kwargs):
    raise ValueError("Hard deletes are not allowed — use soft_delete()")
```

---

## Rules
- Never `import *`
- Prefer `pathlib.Path` over `os.path`
- Use `__slots__` on hot dataclasses
- `uv` or `poetry` for dependency management — not bare pip
- 88-char line length (Black default)
