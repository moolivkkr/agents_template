> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# Python patterns and conventions for building reliable, maintainable applications.

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
log.info("user_created", user_id=user.id, email=user.email)
```
- Structured logging always — never f-strings in log calls
- Bind request context (request_id, user_id) at middleware level

## Type Safety

```python
from typing import TypedDict, Protocol, Literal, TypeVar, overload, Generic

# TypedDict for dictionaries with known shapes (API responses, configs)
class UserResponse(TypedDict):
    id: str
    email: str
    is_active: bool

class PaginatedResponse(TypedDict, Generic[T]):
    data: list[T]
    total: int
    has_more: bool

# Protocol for structural typing — no inheritance required
class Repository(Protocol):
    async def find_by_id(self, id: str) -> dict | None: ...
    async def save(self, entity: dict) -> None: ...

# Any class with matching methods satisfies Repository — no explicit subclassing

# Literal types for fixed values
Status = Literal["active", "inactive", "suspended"]

def update_status(user_id: str, status: Status) -> None:
    ...  # type checker rejects update_status("x", "invalid")

# TypeVar for generic functions
T = TypeVar("T")

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
import functools
import asyncio
from multiprocessing import Pool
from dataclasses import dataclass

# Generator expressions for large data — avoid materializing full list
def process_large_file(path: Path) -> int:
    # Generator: O(1) memory regardless of file size
    return sum(1 for line in open(path) if "ERROR" in line)
    # NOT: len([line for line in open(path) if "ERROR" in line])  # O(n) memory

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
    @functools.cached_property
    def parsed(self) -> dict:
        return toml.loads(self._raw_content)

# asyncio for I/O-bound concurrency
async def fetch_all(urls: list[str]) -> list[Response]:
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        return await asyncio.gather(*tasks)

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
import numpy as np
import torch
from contextlib import contextmanager

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
def gpu_scope(device: str = "cuda:0"):
    """Context manager for GPU operations with cleanup."""
    try:
        torch.cuda.set_device(device)
        yield
    finally:
        torch.cuda.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.synchronize()

# Usage:
with gpu_scope():
    results = predict_batch(model, data)

# Data pipeline with generator chains — process streaming data in constant memory
def load_data(path: Path):
    """Generator: yields one record at a time."""
    for line in open(path):
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
pipeline = transform(filter_valid(load_data("data.jsonl")))
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
from fastapi import Depends, Header, HTTPException, Request
from uuid import UUID

async def get_current_tenant(
    request: Request,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> UUID:
    """Extract and validate tenant from request headers/JWT."""
    try:
        tenant_id = UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")
    # Optionally validate tenant exists and is active
    return tenant_id

# Use as dependency in every route
@router.get("/orders")
async def list_orders(
    tenant_id: UUID = Depends(get_current_tenant),
    service: OrderService = Depends(get_order_service),
) -> PaginatedResponse[OrderResponse]:
    return await service.list_orders(tenant_id)
```

### SQLAlchemy Scoped Session Per Tenant
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar

current_tenant: ContextVar[UUID] = ContextVar("current_tenant")

class TenantAwareSession:
    """Automatically applies tenant filter to all queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, stmt, *args, **kwargs):
        tenant_id = current_tenant.get()
        # Inject tenant filter for all SELECT/UPDATE/DELETE
        if hasattr(stmt, "whereclause"):
            stmt = stmt.where(model.tenant_id == tenant_id)
        return await self._session.execute(stmt, *args, **kwargs)
```

### Tenant Middleware
```python
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return JSONResponse(status_code=401, content={"error": "Missing tenant"})

        token = current_tenant.set(UUID(tenant_id))
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
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
class AppError(Exception):
    """Base for all domain errors."""
    def __init__(self, message: str, code: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code

class ValidationError(AppError):
    def __init__(self, fields: list[dict[str, str]]) -> None:
        super().__init__("Validation failed", "VALIDATION_ERROR", 400)
        self.fields = fields

class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(f"{resource} {resource_id} not found", "NOT_FOUND", 404)

class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message, "CONFLICT", 409)

class UnauthorizedError(AppError):
    def __init__(self) -> None:
        super().__init__("Authentication required", "UNAUTHORIZED", 401)

class ForbiddenError(AppError):
    def __init__(self, action: str = "this action") -> None:
        super().__init__(f"Not allowed to perform {action}", "FORBIDDEN", 403)

class RateLimitError(AppError):
    def __init__(self, retry_after: int = 60) -> None:
        super().__init__("Rate limit exceeded", "RATE_LIMITED", 429)
        self.retry_after = retry_after

class UpstreamError(AppError):
    def __init__(self, service: str, detail: str = "") -> None:
        super().__init__(f"Upstream service {service} failed: {detail}", "UPSTREAM_ERROR", 502)

class InternalError(AppError):
    def __init__(self, detail: str = "Internal server error") -> None:
        super().__init__(detail, "INTERNAL_ERROR", 500)
```

### FastAPI Exception Handlers
```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.error("app_error", code=exc.code, message=str(exc), path=request.url.path)
    body: dict = {"error": {"code": exc.code, "message": str(exc)}}
    if isinstance(exc, ValidationError):
        body["error"]["details"] = exc.fields
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong"}},
    )
```

---

## Repository Pattern in Python

### Async SQLAlchemy Repository
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from uuid import UUID

class BaseRepository[T]:
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
        stmt = (
            select(self._model)
            .where(self._model.tenant_id == tenant_id, self._model.deleted_at.is_(None))
            .order_by(self._model.created_at.desc())
            .limit(limit + 1)
        )
        if cursor:
            stmt = stmt.where(self._model.created_at < decode_cursor(cursor))

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at) if has_more else None
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
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)

    async def do_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(do_migrations())

# Migration naming: YYYYMMDD_HHMMSS_description.py
# Always include both upgrade() and downgrade()
# Test migrations in CI: upgrade head, then downgrade base, then upgrade head again
```

### Connection Pooling
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
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
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)

def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    cache: CacheService = Depends(get_cache),
    events: EventPublisher = Depends(get_event_publisher),
) -> UserService:
    return UserService(repo, cache, events)

# Handler — thin, no business logic
@router.post("/users", status_code=201)
async def create_user(
    request: CreateUserRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.create_user(tenant_id, request)
    return UserResponse.model_validate(user)
```

### Transaction Management
```python
class OrderService:
    def __init__(self, session: AsyncSession, repo: OrderRepository) -> None:
        self._session = session
        self._repo = repo

    async def create_order(self, tenant_id: UUID, request: CreateOrderRequest) -> Order:
        """Transaction spans the entire service method."""
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
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture(scope="session")
def postgres():
    """Real PostgreSQL via testcontainers — shared across all tests."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture
async def db_session(postgres) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(postgres.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()  # reset state between tests

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
import factory
from factory.alchemy import SQLAlchemyModelFactory

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(lambda: UUID("00000000-0000-0000-0000-000000000001"))
    email = factory.Sequence(lambda n: f"user-{n}@example.com")
    name = factory.Faker("name")

# Usage
user = UserFactory(email="specific@example.com")  # override only what matters
```

### Async Test Patterns
```python
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
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def managed_connection(pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)

# Usage
async with managed_connection(pool) as conn:
    await conn.execute("SELECT 1")
```

### Task Groups (Python 3.11+)
```python
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
async def fetch_many(urls: list[str], max_concurrent: int = 10) -> list[Response]:
    """Limit concurrent HTTP requests to avoid overwhelming upstream."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _fetch(url: str) -> Response:
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                return await session.get(url)

    return await asyncio.gather(*[_fetch(url) for url in urls])
```

### Graceful Shutdown
```python
import signal

async def graceful_shutdown(app: FastAPI) -> None:
    """Handle SIGTERM/SIGINT for zero-downtime deployments."""
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        log.info("shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    # Drain in-flight requests, close DB pools, flush metrics
    await app.state.db_pool.close()
    await app.state.redis.close()
    log.info("shutdown_complete")
```

---

## Django-Specific Patterns

### Multi-Tenant Model Managers
```python
from django.db import models

class TenantManager(models.Manager):
    """Automatically filters by tenant — prevents accidental cross-tenant reads."""

    def get_queryset(self):
        qs = super().get_queryset().filter(deleted_at__isnull=True)
        # Tenant filtering is applied via middleware-set thread-local
        from .middleware import get_current_tenant
        tenant_id = get_current_tenant()
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

class Order(models.Model):
    tenant_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)

    objects = TenantManager()          # default: tenant-filtered
    all_objects = models.Manager()     # admin: unfiltered (use sparingly)

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
            raise serializers.ValidationError({"total": "Must be non-negative"})
        return attrs

    def create(self, validated_data: dict) -> Order:
        # Inject tenant_id from request context
        validated_data["tenant_id"] = self.context["request"].tenant_id
        return super().create(validated_data)
```

### Django Middleware Chain
```python
import threading

_thread_local = threading.local()

class TenantMiddleware:
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

    def _extract_tenant(self, request) -> str:
        # From JWT, header, or subdomain
        return request.headers.get("X-Tenant-ID", "")

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
