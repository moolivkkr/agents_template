> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# Python Patterns

## Project Structure
```
src/myapp/
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
- Use everywhere — signatures, class attributes, return types (including `-> None`)
- Prefer `X | None` over `Optional[X]` (Python 3.10+)
- `TypeAlias` for complex types; `Protocol` for structural typing
- Run `mypy --strict` in CI

```python
from typing import TypedDict, Protocol, Literal, TypeVar, overload, Generic

class Repository(Protocol):
    async def find_by_id(self, id: str) -> dict | None: ...
    async def save(self, entity: dict) -> None: ...

Status = Literal["active", "inactive", "suspended"]
T = TypeVar("T")
def first_or_none(items: list[T]) -> T | None:
    return items[0] if items else None

@overload
def fetch(id: str, *, required: Literal[True]) -> User: ...
@overload
def fetch(id: str, *, required: Literal[False] = ...) -> User | None: ...
def fetch(id: str, *, required: bool = False) -> User | None:
    user = db.get(id)
    if user is None and required: raise UserNotFoundError(id)
    return user
```

## Data Validation
- Pydantic v2 for all external data (API in/out, config, env vars)
- `dataclasses` for pure internal data with no validation
- Never use bare `dict` for structured data

## Error Handling

```python
# Exception hierarchy
class AppError(Exception):
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
    def __init__(self) -> None: super().__init__("Authentication required", "UNAUTHORIZED", 401)

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

# FastAPI exception handlers
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    body: dict = {"error": {"code": exc.code, "message": str(exc)}}
    if isinstance(exc, ValidationError): body["error"]["details"] = exc.fields
    headers = {}
    if isinstance(exc, RateLimitError): headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)
```

- Never `except Exception` without re-raising or logging
- Use `from e` to preserve cause chain

## Async

```python
# TaskGroup (Python 3.11+) for structured concurrency
async def fetch_user_data(user_id: str) -> UserProfile:
    async with asyncio.TaskGroup() as tg:
        profile_task = tg.create_task(fetch_profile(user_id))
        orders_task = tg.create_task(fetch_orders(user_id))
        prefs_task = tg.create_task(fetch_preferences(user_id))
    return UserProfile(profile=profile_task.result(), orders=orders_task.result(), preferences=prefs_task.result())

# Semaphore for concurrency limits
async def fetch_many(urls: list[str], max_concurrent: int = 10) -> list[Response]:
    semaphore = asyncio.Semaphore(max_concurrent)
    async def _fetch(url: str) -> Response:
        async with semaphore:
            async with aiohttp.ClientSession() as session: return await session.get(url)
    return await asyncio.gather(*[_fetch(url) for url in urls])

# Async context managers
@asynccontextmanager
async def managed_connection(pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    conn = await pool.acquire()
    try: yield conn
    finally: await pool.release(conn)

# Graceful shutdown
async def graceful_shutdown(app: FastAPI) -> None:
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: stop_event.set())
    await stop_event.wait()
    await app.state.db_pool.close()
    await app.state.redis.close()
```

- `async/await` throughout for I/O; never mix sync/async
- `anyio` for library code; `asyncio` for app code
- `run_in_executor` if sync calls unavoidable

## Multi-Tenancy

```python
# FastAPI tenant dependency
async def get_current_tenant(x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> UUID:
    try: return UUID(x_tenant_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid tenant ID")

# Tenant middleware with contextvars
current_tenant: ContextVar[UUID] = ContextVar("current_tenant")

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id: return JSONResponse(status_code=401, content={"error": "Missing tenant"})
        token = current_tenant.set(UUID(tenant_id))
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
        try: return await call_next(request)
        finally:
            current_tenant.reset(token)
            structlog.contextvars.unbind_contextvars("tenant_id")
```

## Repository Pattern

```python
class BaseRepository[T]:
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def find_by_id(self, tenant_id: UUID, entity_id: UUID) -> T | None:
        stmt = select(self._model).where(
            self._model.tenant_id == tenant_id, self._model.id == entity_id, self._model.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_paginated(self, tenant_id: UUID, *, cursor: str | None = None, limit: int = 20) -> tuple[list[T], str | None]:
        stmt = (select(self._model).where(self._model.tenant_id == tenant_id, self._model.deleted_at.is_(None))
                .order_by(self._model.created_at.desc()).limit(limit + 1))
        if cursor: stmt = stmt.where(self._model.created_at < decode_cursor(cursor))
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        if has_more: rows = rows[:limit]
        return rows, encode_cursor(rows[-1].created_at) if has_more else None

    async def save(self, entity: T) -> T:
        self._session.add(entity); await self._session.flush(); return entity

    async def soft_delete(self, tenant_id: UUID, entity_id: UUID) -> None:
        stmt = update(self._model).where(self._model.tenant_id == tenant_id, self._model.id == entity_id).values(deleted_at=func.now())
        await self._session.execute(stmt)
```

## Service & DI Pattern (FastAPI)

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try: yield session; await session.commit()
        except Exception: await session.rollback(); raise

def get_user_service(repo: UserRepository = Depends(get_user_repository), cache: CacheService = Depends(get_cache)) -> UserService:
    return UserService(repo, cache)

@router.post("/users", status_code=201)
async def create_user(request: CreateUserRequest, tenant_id: UUID = Depends(get_current_tenant), service: UserService = Depends(get_user_service)) -> UserResponse:
    return UserResponse.model_validate(await service.create_user(tenant_id, request))

# Transaction spans entire service method
class OrderService:
    async def create_order(self, tenant_id: UUID, request: CreateOrderRequest) -> Order:
        async with self._session.begin():
            order = await self._repo.save(Order(tenant_id=tenant_id, **request.model_dump()))
            await self._repo.update_inventory(tenant_id, order.items)
            return order
```

## Connection Pooling
```python
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    pool_size=20, max_overflow=10, pool_timeout=30, pool_recycle=3600, pool_pre_ping=True)
```

## Testing (pytest)

```python
@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16-alpine") as pg: yield pg

@pytest.fixture
async def db_session(postgres) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(postgres.get_connection_url())
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session: yield session; await session.rollback()

@pytest.fixture
def user_factory(db_session):
    async def _create(**overrides) -> User:
        defaults = {"tenant_id": UUID("00000000-0000-0000-0000-000000000001"), "email": f"test-{uuid4().hex[:8]}@example.com"}
        user = User(**(defaults | overrides))
        db_session.add(user); await db_session.flush(); return user
    return _create

@pytest.mark.asyncio
async def test_create_user_sends_welcome_email(user_service, mock_mailer: AsyncMock):
    user = await user_service.create_user(TENANT_ID, CreateUserRequest(email="new@example.com", name="New User"))
    assert user.email == "new@example.com"
    mock_mailer.send.assert_awaited_once()

# monkeypatch for env/config, mock for collaborator interactions
```

- Fixtures for shared setup; `conftest.py` for cross-module
- `pytest-asyncio` for async tests
- Mock only external I/O, never domain logic

## Performance
- Generator expressions over list comprehensions for large data
- `@dataclass(slots=True)` for classes with many instances (40-50% memory savings)
- `functools.lru_cache` for pure functions; `cached_property` for methods
- `asyncio` for I/O-bound; `multiprocessing.Pool` for CPU-bound
- NumPy vectorization over Python loops (10-100x speedup)

## ML-Specific

```python
# Batch processing for inference
def predict_batch(model, inputs: list[np.ndarray], batch_size: int = 32) -> list[np.ndarray]:
    results = []
    for i in range(0, len(inputs), batch_size):
        batch = torch.tensor(np.stack(inputs[i:i+batch_size]))
        with torch.no_grad(): output = model(batch)
        results.extend(output.cpu().numpy())
    return results

# GPU memory management
@contextmanager
def gpu_scope(device="cuda:0"):
    try: torch.cuda.set_device(device); yield
    finally: torch.cuda.empty_cache(); torch.cuda.is_available() and torch.cuda.synchronize()

# Generator chains for O(1) memory pipelines
pipeline = transform(filter_valid(load_data("data.jsonl")))
for batch in batched(pipeline, 1000): process(batch)

# Reproducibility
def set_seeds(seed=42):
    import random; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False
```

## Django Patterns

```python
# Multi-tenant model manager
class TenantManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset().filter(deleted_at__isnull=True)
        from .middleware import get_current_tenant
        tenant_id = get_current_tenant()
        return qs.filter(tenant_id=tenant_id) if tenant_id else qs

class Order(models.Model):
    tenant_id = models.UUIDField(db_index=True)
    objects = TenantManager()
    all_objects = models.Manager()  # admin: unfiltered
    class Meta:
        indexes = [models.Index(fields=["tenant_id", "status"]), models.Index(fields=["tenant_id", "created_at"])]

# Tenant middleware (thread-local)
_thread_local = threading.local()
class TenantMiddleware:
    def __call__(self, request):
        _thread_local.tenant_id = request.headers.get("X-Tenant-ID", "")
        request.tenant_id = _thread_local.tenant_id
        try: return self.get_response(request)
        finally: _thread_local.tenant_id = None
def get_current_tenant() -> str | None: return getattr(_thread_local, "tenant_id", None)

# Audit signals
@receiver(post_save, sender=Order)
def audit_order_change(sender, instance, created, **kwargs):
    AuditLog.objects.create(tenant_id=instance.tenant_id, entity_type="Order", entity_id=instance.id,
        action="created" if created else "updated", changes=instance.tracker.changed())
```

## Logging
```python
import structlog
log = structlog.get_logger()
log.info("user_created", user_id=user.id, email=user.email)
```
- Structured logging always — never f-strings in log calls
- Bind request context at middleware level

## Rules
- Never `import *`
- Prefer `pathlib.Path` over `os.path`
- `uv` or `poetry` for dependency management
- 88-char line length (Black default)
- `__slots__` on hot dataclasses
