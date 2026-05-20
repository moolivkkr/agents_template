---
skill: performance-python
description: Python performance archetype — asyncio patterns, connection pooling, memory management, SQLAlchemy optimization, caching strategies, profiling tools, GIL considerations
version: "1.0"
tags:
  - python
  - performance
  - asyncio
  - caching
  - profiling
  - fastapi
  - archetype
  - backend
---

# Performance Archetype — Python (FastAPI / asyncio)

> **Canonical reference**: Python-specific performance patterns for FastAPI services. Apply these alongside `core/observability-patterns.md` for measured, observable performance improvements.

Every generated Python service MUST follow these patterns to avoid common performance pitfalls.

---

## 1. Async Performance

### 1.1 Don't Block the Event Loop

The single most common Python async performance mistake. CPU-bound work on the event loop starves all other coroutines.

```python
# ---- WRONG: blocks the event loop ----
import hashlib

async def hash_password(password: str) -> str:
    # This runs on the event loop — blocks ALL concurrent requests
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"salt", 100_000).hex()

# ---- CORRECT: offload CPU work to a thread pool ----
import asyncio
import hashlib
from functools import partial

async def hash_password(password: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,  # default ThreadPoolExecutor
        partial(hashlib.pbkdf2_hmac, "sha256", password.encode(), b"salt", 100_000),
    )

# ---- CORRECT: heavy CPU work → ProcessPoolExecutor ----
from concurrent.futures import ProcessPoolExecutor

_process_pool = ProcessPoolExecutor(max_workers=4)

async def generate_report(data: list[dict]) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_process_pool, _build_pdf, data)

def _build_pdf(data: list[dict]) -> bytes:
    """CPU-intensive — runs in a separate process to avoid GIL."""
    # ... PDF generation logic ...
    pass
```

### 1.2 Connection Pooling

```python
# ── asyncpg pool (used directly or via SQLAlchemy) ────────────────────

import asyncpg

async def create_pg_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn="postgresql://user:pass@localhost:5432/mydb",
        min_size=5,          # keep 5 connections warm
        max_size=20,         # never exceed 20
        max_inactive_connection_lifetime=300,  # recycle idle connections after 5 min
        command_timeout=30,  # kill queries taking longer than 30s
    )

# ── aioredis / redis.asyncio pool ────────────────────────────────────

import redis.asyncio as aioredis

def create_redis_pool() -> aioredis.Redis:
    return aioredis.Redis(
        host="localhost",
        port=6379,
        max_connections=50,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )

# ── httpx connection pool for outbound API calls ─────────────────────

import httpx

# Create once, reuse across requests (do NOT create per-request)
_http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30,
    ),
)
```

### 1.3 Semaphores for Concurrent External Calls

```python
import asyncio

# Limit concurrent calls to a downstream service
_payment_semaphore = asyncio.Semaphore(10)

async def charge_payment(order_id: str, amount: float) -> PaymentResult:
    async with _payment_semaphore:
        # At most 10 concurrent calls to the payment service
        return await _http_client.post(
            "https://payment.internal/charge",
            json={"order_id": order_id, "amount": amount},
        )

# ── Bulk operations with bounded concurrency ─────────────────────────

async def process_batch(items: list[Item], max_concurrent: int = 20) -> list[Result]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_one(item: Item) -> Result:
        async with semaphore:
            return await process_item(item)

    return await asyncio.gather(*[_process_one(item) for item in items])
```

### 1.4 gather() vs TaskGroup for Parallel Operations

```python
import asyncio

# ── asyncio.gather — use when you want all results, even if some fail ──

async def fetch_dashboard_data(tenant_id: str) -> DashboardData:
    stats, alerts, recent = await asyncio.gather(
        fetch_stats(tenant_id),
        fetch_alerts(tenant_id),
        fetch_recent_orders(tenant_id),
        return_exceptions=True,  # don't cancel siblings on failure
    )
    return DashboardData(
        stats=stats if not isinstance(stats, Exception) else None,
        alerts=alerts if not isinstance(alerts, Exception) else None,
        recent=recent if not isinstance(recent, Exception) else None,
    )

# ── TaskGroup (Python 3.11+) — use when ALL must succeed ─────────────

async def create_order_with_side_effects(order: Order) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(repo.save(order))
        tg.create_task(search_index.index(order))
        tg.create_task(analytics.track("order_created", order.id))
    # If any task raises, ALL are cancelled and ExceptionGroup is raised
```

### 1.5 Streaming Responses for Large Payloads

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import csv
import io

async def export_orders_csv(tenant_id: str):
    """Stream CSV rows instead of buffering the entire file in memory."""

    async def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "total", "status", "created_at"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        async for batch in repo.iter_orders(tenant_id, batch_size=1000):
            for order in batch:
                writer.writerow([order.id, order.total, order.status, order.created_at])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )
```

---

## 2. Memory Management

### 2.1 \_\_slots\_\_ on Hot-Path Dataclasses

```python
from dataclasses import dataclass

# ---- WRONG: default dataclass — each instance has a __dict__ (~200 bytes overhead) ----
@dataclass
class OrderLine:
    product_id: str
    quantity: int
    unit_price: float

# ---- CORRECT: slots=True — fixed memory layout, ~40% less memory per instance ----
@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: str
    quantity: int
    unit_price: float

# For Pydantic models on hot paths, use model_config
from pydantic import BaseModel, ConfigDict

class OrderLineSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    quantity: int
    unit_price: float
```

### 2.2 Generators and Async Generators for Large Result Sets

```python
# ---- WRONG: loads all rows into memory ----
async def get_all_orders(tenant_id: str) -> list[Order]:
    result = await session.execute(select(OrderModel).where(OrderModel.tenant_id == tenant_id))
    return [Order.from_model(row) for row in result.scalars().all()]  # OOM on large tenants

# ---- CORRECT: async generator — yields batches ----
async def iter_orders(tenant_id: str, batch_size: int = 1000):
    """Yield orders in batches to keep memory bounded."""
    offset = 0
    while True:
        result = await session.execute(
            select(OrderModel)
            .where(OrderModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.scalars().all()
        if not rows:
            break
        yield [Order.from_model(row) for row in rows]
        offset += batch_size

# ---- CORRECT: server-side cursor (asyncpg) — true streaming ----
async def stream_orders(pool: asyncpg.Pool, tenant_id: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            async for record in conn.cursor(
                "SELECT * FROM orders WHERE tenant_id = $1 ORDER BY created_at",
                tenant_id,
            ):
                yield Order.from_record(record)
```

### 2.3 Weak References for Caches

```python
import weakref

class EntityCache:
    """
    Cache that does not prevent garbage collection.
    Useful for large objects that should be cached while in use
    but freed when no other references exist.
    """

    def __init__(self):
        self._cache: weakref.WeakValueDictionary[str, object] = weakref.WeakValueDictionary()

    def get(self, key: str):
        return self._cache.get(key)

    def set(self, key: str, value):
        self._cache[key] = value
```

### 2.4 Memory Profiling with tracemalloc

```python
import tracemalloc
import linecache

def start_memory_profiling():
    """Enable tracemalloc for debugging memory leaks. Do NOT use in production."""
    tracemalloc.start(25)  # store 25 frames per allocation

def get_memory_snapshot() -> str:
    """
    Call from a debug endpoint to get top memory consumers.
    Expose only in non-production environments.
    """
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")

    lines = ["=== Top 20 memory consumers ==="]
    for stat in top_stats[:20]:
        lines.append(f"  {stat}")
    return "\n".join(lines)

# FastAPI debug endpoint
from fastapi import APIRouter

debug_router = APIRouter(prefix="/debug", tags=["debug"])

@debug_router.get("/memory")
async def memory_profile():
    """Only available when ENVIRONMENT=local."""
    return {"snapshot": get_memory_snapshot()}
```

### 2.5 Avoid Unnecessary Intermediate Lists

```python
# ---- WRONG: creates 3 intermediate lists ----
def get_active_order_ids(orders: list[Order]) -> list[str]:
    filtered = [o for o in orders if o.status == "active"]       # list 1
    sorted_orders = sorted(filtered, key=lambda o: o.created_at) # list 2
    return [o.id for o in sorted_orders]                         # list 3

# ---- BETTER: use generator expressions where possible ----
def get_active_order_ids(orders: list[Order]) -> list[str]:
    active = (o for o in orders if o.status == "active")  # generator, no allocation
    return [o.id for o in sorted(active, key=lambda o: o.created_at)]  # 1 list

# ---- ALSO: use itertools for chaining operations ----
from itertools import islice

def get_top_active_ids(orders: list[Order], limit: int = 100) -> list[str]:
    active = (o for o in orders if o.status == "active")
    top = islice(sorted(active, key=lambda o: -o.total), limit)
    return [o.id for o in top]
```

---

## 3. Database Performance

### 3.1 SQLAlchemy Async Session Pool Settings

```python
# app/db.py

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

def create_engine():
    return create_async_engine(
        "postgresql+asyncpg://user:pass@localhost:5432/mydb",

        # Pool settings — tune for your workload
        pool_size=10,           # baseline connections kept open
        max_overflow=20,        # burst capacity above pool_size (total max = 30)
        pool_recycle=3600,      # recycle connections after 1 hour (avoids stale connections)
        pool_pre_ping=True,     # verify connection is alive before using it
        pool_timeout=30,        # seconds to wait for a connection from pool

        # Query settings
        echo=False,             # set True for debugging (logs all SQL)
        echo_pool="debug",      # log pool checkout/checkin events (remove in production)
    )

engine = create_engine()
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### 3.2 Eager Loading vs Lazy Loading

```python
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select

# ---- WRONG: lazy loading causes N+1 ----
async def get_orders(session: AsyncSession, tenant_id: str) -> list[Order]:
    result = await session.execute(
        select(OrderModel).where(OrderModel.tenant_id == tenant_id)
    )
    orders = result.scalars().all()
    for order in orders:
        # EACH access triggers a separate query — N+1!
        print(order.items)
    return orders

# ---- CORRECT: selectinload — one extra query (SELECT ... WHERE id IN (...)) ----
async def get_orders_with_items(session: AsyncSession, tenant_id: str) -> list[Order]:
    result = await session.execute(
        select(OrderModel)
        .where(OrderModel.tenant_id == tenant_id)
        .options(selectinload(OrderModel.items))
    )
    return result.scalars().all()

# ---- CORRECT: joinedload — single query with JOIN (use for to-one relationships) ----
async def get_order_with_customer(session: AsyncSession, order_id: str) -> Order:
    result = await session.execute(
        select(OrderModel)
        .where(OrderModel.id == order_id)
        .options(joinedload(OrderModel.customer))
    )
    return result.scalar_one_or_none()

# ── When to use which ────────────────────────────────────────────────
# selectinload → to-many relationships (order → items) — avoids cartesian explosion
# joinedload   → to-one relationships (order → customer) — single query
# subqueryload → to-many with complex filters — secondary subquery
# lazyload     → NEVER in async (raises MissingGreenlet error)
```

### 3.3 Bulk Inserts

```python
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ── Bulk insert with executemany (SQLAlchemy) ─────────────────────────
async def bulk_create_orders(session: AsyncSession, orders: list[dict]) -> None:
    await session.execute(insert(OrderModel), orders)
    await session.commit()

# ── Upsert (INSERT ... ON CONFLICT) ──────────────────────────────────
async def upsert_products(session: AsyncSession, products: list[dict]) -> None:
    stmt = pg_insert(ProductModel).values(products)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sku"],
        set_={
            "name": stmt.excluded.name,
            "price": stmt.excluded.price,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()

# ── COPY for maximum throughput (raw asyncpg) ────────────────────────
async def bulk_load_via_copy(pool: asyncpg.Pool, records: list[tuple]) -> int:
    """
    asyncpg COPY is 5-10x faster than INSERT for large batches.
    Use for data imports, ETL, seeding.
    """
    async with pool.acquire() as conn:
        return await conn.copy_records_to_table(
            "orders",
            records=records,
            columns=["id", "tenant_id", "total", "status", "created_at"],
        )
```

### 3.4 Read Replicas with SQLAlchemy Binds

```python
# app/db.py

from sqlalchemy.ext.asyncio import create_async_engine

primary_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@primary:5432/mydb",
    pool_size=10,
    max_overflow=20,
)

replica_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@replica:5432/mydb",
    pool_size=10,
    max_overflow=20,
)

# ── Route reads to replica, writes to primary ────────────────────────

from sqlalchemy.ext.asyncio import async_sessionmaker

write_session = async_sessionmaker(primary_engine, expire_on_commit=False)
read_session = async_sessionmaker(replica_engine, expire_on_commit=False)

# In repository:
class OrderRepository:
    async def find_by_id(self, order_id: str) -> Order | None:
        async with read_session() as session:  # reads from replica
            result = await session.get(OrderModel, order_id)
            return Order.from_model(result) if result else None

    async def save(self, order: Order) -> None:
        async with write_session() as session:  # writes to primary
            session.add(order.to_model())
            await session.commit()
```

### 3.5 N+1 Query Detection

```python
# app/middleware/query_counter.py

import contextvars
import structlog
from sqlalchemy import event

logger = structlog.get_logger()

_query_count: contextvars.ContextVar[int] = contextvars.ContextVar("query_count", default=0)

N_PLUS_ONE_THRESHOLD = 10  # warn if a single request fires more than 10 queries

def install_query_counter(engine):
    """Attach to engine to count queries per request."""

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        _query_count.set(_query_count.get(0) + 1)

def reset_query_counter():
    _query_count.set(0)

def check_query_count(request_path: str):
    count = _query_count.get(0)
    if count > N_PLUS_ONE_THRESHOLD:
        logger.warning(
            "possible_n_plus_one",
            query_count=count,
            threshold=N_PLUS_ONE_THRESHOLD,
            path=request_path,
        )

# ── Wire into middleware ──────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class QueryCountMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        reset_query_counter()
        response = await call_next(request)
        check_query_count(request.url.path)
        return response
```

---

## 4. Profiling

### 4.1 cProfile / py-spy for CPU Profiling

```bash
# ── py-spy — attach to a running process (no code changes) ───────────
# Install: pip install py-spy
py-spy top --pid $(pgrep -f uvicorn)          # live top-like view
py-spy record --pid $(pgrep -f uvicorn) -o profile.svg  # flame graph

# ── cProfile — run a script with profiling ────────────────────────────
python -m cProfile -o output.prof app/scripts/benchmark.py
# View: pip install snakeviz && snakeviz output.prof
```

```python
# ── Programmatic profiling for a specific code path ───────────────────
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    """Profile a single function call and print top 20 cumulative time consumers."""
    profiler = cProfile.Profile()
    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(20)
    print(stream.getvalue())
    return result
```

### 4.2 tracemalloc for Memory Profiling

```python
# Already covered in Section 2.4 — use for debugging memory leaks.
# Key commands:
#   tracemalloc.start(25)
#   snapshot = tracemalloc.take_snapshot()
#   top_stats = snapshot.statistics("lineno")

# ── Compare two snapshots to find growth ──────────────────────────────
import tracemalloc

tracemalloc.start()
snapshot1 = tracemalloc.take_snapshot()

# ... run workload ...

snapshot2 = tracemalloc.take_snapshot()
top_stats = snapshot2.compare_to(snapshot1, "lineno")
for stat in top_stats[:10]:
    print(stat)  # shows memory growth between snapshots
```

### 4.3 asyncio Debug Mode

```python
# Enable via environment variable (recommended for development)
# PYTHONASYNCIODEBUG=1 python -m uvicorn app.main:app

# Or programmatically:
import asyncio

loop = asyncio.get_event_loop()
loop.set_debug(True)
# This will:
#   - Log coroutines that take >100ms (blocks event loop)
#   - Log callbacks that take >100ms
#   - Warn about unawaited coroutines
#   - Track coroutine creation stack traces
```

### 4.4 line_profiler for Hot Functions

```bash
# Install: pip install line_profiler
```

```python
# Decorate the function you want to profile
from line_profiler import profile

@profile
def calculate_order_total(items: list[OrderLine]) -> Decimal:
    subtotal = sum(item.quantity * item.unit_price for item in items)
    tax = subtotal * Decimal("0.08")
    discount = calculate_discount(items)
    return subtotal + tax - discount

# Run: kernprof -l -v app/services/pricing.py
# Output shows time spent on each LINE of the function
```

### 4.5 Benchmark with pytest-benchmark

```python
# tests/benchmarks/test_order_performance.py

import pytest

def test_order_creation_performance(benchmark, order_factory):
    """Ensure order creation stays under 1ms."""
    order_data = order_factory.build_request()
    result = benchmark(create_order_sync, order_data)
    assert result is not None

    # pytest-benchmark automatically reports:
    #   min, max, mean, stddev, median, rounds, iterations
    # Fail if mean exceeds threshold:
    assert benchmark.stats["mean"] < 0.001  # 1ms

def test_bulk_insert_performance(benchmark, db_session, order_factory):
    """Benchmark bulk insert of 1000 orders."""
    orders = [order_factory.build_dict() for _ in range(1000)]

    def insert_batch():
        db_session.execute(insert(OrderModel), orders)
        db_session.commit()
        db_session.rollback()  # clean up

    benchmark.pedantic(insert_batch, rounds=10, warmup_rounds=2)
```

```bash
# Run benchmarks
pytest tests/benchmarks/ --benchmark-only --benchmark-sort=mean
pytest tests/benchmarks/ --benchmark-compare  # compare against saved baseline
pytest tests/benchmarks/ --benchmark-save=baseline  # save current run as baseline
```

---

## 5. Caching Strategy

### 5.1 Redis Cache Patterns

```python
# app/cache/redis_cache.py

import json
from typing import TypeVar, Callable, Awaitable

import redis.asyncio as aioredis

T = TypeVar("T")

class RedisCache:
    def __init__(self, redis: aioredis.Redis, default_ttl: int = 300):
        self._redis = redis
        self._default_ttl = default_ttl

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._redis.set(key, value, ex=ttl or self._default_ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int | None = None,
        serialize: Callable[[T], str] = json.dumps,
        deserialize: Callable[[str], T] = json.loads,
    ) -> T:
        """
        Cache-aside pattern: return cached value or compute and store.
        """
        cached = await self._redis.get(key)
        if cached is not None:
            return deserialize(cached)

        value = await factory()
        await self._redis.set(key, serialize(value), ex=ttl or self._default_ttl)
        return value

# ── Usage ─────────────────────────────────────────────────────────────

class OrderService:
    async def get_order(self, ctx: RequestContext, order_id: str) -> Order:
        cache_key = f"order:{ctx.tenant_id}:{order_id}"
        return await self._cache.get_or_set(
            key=cache_key,
            factory=lambda: self._repo.find_by_id(ctx, order_id),
            ttl=600,  # 10 minutes
            serialize=lambda o: o.model_dump_json(),
            deserialize=lambda s: Order.model_validate_json(s),
        )

    async def update_order(self, ctx: RequestContext, order_id: str, req: UpdateReq) -> Order:
        order = await self._repo.update(ctx, order_id, req)
        # Invalidate cache on write
        await self._cache.delete(f"order:{ctx.tenant_id}:{order_id}")
        return order
```

### 5.2 In-Process Cache (lru_cache, TTLCache)

```python
from functools import lru_cache
from cachetools import TTLCache
import threading

# ── lru_cache — for pure functions with immutable args ────────────────
@lru_cache(maxsize=1024)
def parse_feature_flags(raw_config: str) -> dict[str, bool]:
    """Parse feature flag config. Cached because config rarely changes."""
    return json.loads(raw_config)

# ── TTLCache — for data that expires ──────────────────────────────────
_tenant_config_cache = TTLCache(maxsize=500, ttl=300)  # 5 min TTL
_cache_lock = threading.Lock()

async def get_tenant_config(tenant_id: str) -> TenantConfig:
    with _cache_lock:
        cached = _tenant_config_cache.get(tenant_id)
        if cached is not None:
            return cached

    # Cache miss — fetch from DB
    config = await repo.get_tenant_config(tenant_id)

    with _cache_lock:
        _tenant_config_cache[tenant_id] = config
    return config

# ── Async-safe TTLCache with asyncio.Lock ─────────────────────────────
import asyncio

_async_cache = TTLCache(maxsize=500, ttl=300)
_async_lock = asyncio.Lock()

async def get_tenant_config_async(tenant_id: str) -> TenantConfig:
    async with _async_lock:
        cached = _async_cache.get(tenant_id)
        if cached is not None:
            return cached

    config = await repo.get_tenant_config(tenant_id)

    async with _async_lock:
        _async_cache[tenant_id] = config
    return config
```

### 5.3 Cache Stampede Prevention (Single-Flight Pattern)

```python
# app/cache/single_flight.py

import asyncio
from typing import TypeVar, Callable, Awaitable

T = TypeVar("T")

class SingleFlight:
    """
    Ensures only one concurrent call for a given key.
    All concurrent callers for the same key wait for the first result.
    Prevents cache stampede on expiry.
    """

    def __init__(self):
        self._in_flight: dict[str, asyncio.Future] = {}

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        if key in self._in_flight:
            return await self._in_flight[key]

        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        self._in_flight[key] = future

        try:
            result = await fn()
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(key, None)

# ── Usage with RedisCache ─────────────────────────────────────────────

_single_flight = SingleFlight()

class OrderService:
    async def get_order(self, ctx: RequestContext, order_id: str) -> Order:
        cache_key = f"order:{ctx.tenant_id}:{order_id}"

        # Check cache first
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return Order.model_validate_json(cached)

        # Single-flight: only one DB call even if 100 requests arrive simultaneously
        order = await _single_flight.do(
            cache_key,
            lambda: self._repo.find_by_id(ctx, order_id),
        )

        await self._cache.set(cache_key, order.model_dump_json(), ttl=600)
        return order
```

### 5.4 Serialization Speed Comparison

```python
import json
import msgpack
import pickle
import timeit

data = {"id": "order_123", "items": [{"sku": f"SKU_{i}", "qty": i} for i in range(100)]}

# ── Benchmark results (typical, 10000 iterations) ────────────────────
# | Format  | Serialize | Deserialize | Size (bytes) | Safety    |
# |---------|-----------|-------------|--------------|-----------|
# | json    | 1.00x     | 1.00x       | 3,200        | Safe      |
# | msgpack | 2-3x fast | 2-3x fast   | 2,100 (34%)  | Safe      |
# | pickle  | 3-5x fast | 3-5x fast   | 2,800        | UNSAFE *  |
# * pickle can execute arbitrary code on deserialization — NEVER use
#   for data from untrusted sources (user input, external APIs, Redis
#   shared between services).

# ── Recommendation: use msgpack for Redis cache values ────────────────
import msgpack

serialized = msgpack.packb(data, use_bin_type=True)
deserialized = msgpack.unpackb(serialized, raw=False)

# For Pydantic models:
class Order(BaseModel):
    def to_cache(self) -> bytes:
        return msgpack.packb(self.model_dump(), use_bin_type=True)

    @classmethod
    def from_cache(cls, data: bytes) -> "Order":
        return cls.model_validate(msgpack.unpackb(data, raw=False))
```

---

## 6. GIL Considerations

### 6.1 CPU-Bound: Use ProcessPoolExecutor, Not Threads

```python
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import asyncio

# ---- WRONG: ThreadPoolExecutor for CPU work — GIL prevents parallelism ----
_thread_pool = ThreadPoolExecutor(max_workers=4)

async def compress_image_wrong(data: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    # Threads take turns holding the GIL — no actual parallelism
    return await loop.run_in_executor(_thread_pool, _compress, data)

# ---- CORRECT: ProcessPoolExecutor for CPU work — each process has its own GIL ----
_process_pool = ProcessPoolExecutor(max_workers=4)

async def compress_image(data: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    # Separate processes = true parallelism for CPU work
    return await loop.run_in_executor(_process_pool, _compress, data)

def _compress(data: bytes) -> bytes:
    """Pure CPU work — runs in a separate process."""
    import zlib
    return zlib.compress(data, level=6)
```

### 6.2 IO-Bound: asyncio Is Sufficient

```python
# For IO-bound work (HTTP calls, DB queries, file IO), asyncio releases
# the GIL while waiting. No need for threads or processes.

async def fetch_multiple_apis():
    """GIL is released during await — all three run concurrently."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
            client.get("https://api3.example.com/data"),
        )
    return results

# Rule of thumb:
#   IO-bound → asyncio (or ThreadPoolExecutor for sync IO libraries)
#   CPU-bound → ProcessPoolExecutor
#   Mixed → asyncio + offload CPU parts to ProcessPoolExecutor
```

### 6.3 When to Use multiprocessing vs Celery

```python
# ── ProcessPoolExecutor — use for short CPU tasks within a request ────
# Good for: image processing, PDF generation, compression, hashing
# Characteristics: in-process, low overhead, bounded by process pool size
_pool = ProcessPoolExecutor(max_workers=4)

async def handle_request():
    result = await asyncio.get_running_loop().run_in_executor(_pool, cpu_task)
    return result

# ── Celery — use for long-running or distributed background jobs ──────
# Good for: email sending, report generation, data pipelines, webhooks
# Characteristics: separate workers, retry logic, scheduling, monitoring

from celery import Celery
app = Celery("tasks", broker="redis://localhost:6379/0")

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_monthly_report(self, tenant_id: str):
    """Runs in a separate Celery worker process."""
    try:
        data = fetch_month_data(tenant_id)
        pdf = build_pdf(data)        # CPU-intensive
        upload_to_s3(pdf)             # IO-bound
        send_notification(tenant_id)  # IO-bound
    except Exception as exc:
        self.retry(exc=exc)

# Dispatch from FastAPI:
async def request_report(tenant_id: str):
    generate_monthly_report.delay(tenant_id)  # async dispatch
    return {"status": "queued"}
```

### 6.4 uvloop for Faster Event Loop

```python
# uvloop is a drop-in replacement for asyncio's event loop, written in Cython.
# Typically 2-4x faster for IO-heavy workloads.

# Install: pip install uvloop

# ── Option 1: in uvicorn command ──────────────────────────────────────
# uvicorn app.main:app --loop uvloop

# ── Option 2: programmatic ────────────────────────────────────────────
import uvloop
uvloop.install()  # call before any asyncio code

# ── Option 3: uvicorn config ─────────────────────────────────────────
# uvicorn.run(app, host="0.0.0.0", port=8000, loop="uvloop")

# NOTE: uvloop is Linux/macOS only. Falls back to asyncio on Windows.
# Do NOT use if you need asyncio.subprocess (uvloop has limitations there).
```

---

## 7. Critical Rules

1. **Never block the event loop** — offload CPU work to `ProcessPoolExecutor` or `run_in_executor`
2. **Create connection pools once** — httpx.AsyncClient, asyncpg.Pool, redis pool created at startup, shared across requests
3. **Use `slots=True`** on dataclasses in hot paths — 40% less memory per instance
4. **Stream large results** — use async generators and `StreamingResponse`, never load unbounded result sets into memory
5. **Eager load relationships** — `selectinload` for to-many, `joinedload` for to-one; never lazy load in async SQLAlchemy
6. **Detect N+1 queries** — install the query counter middleware in development, alert on threshold breaches
7. **Cache with invalidation** — always invalidate on write, use single-flight to prevent stampedes
8. **Profile before optimizing** — use py-spy, tracemalloc, pytest-benchmark to find actual bottlenecks, not guessed ones
9. **Use uvloop** — install it for 2-4x event loop throughput on Linux/macOS
10. **GIL awareness** — threads for IO-bound sync libraries, processes for CPU-bound work, asyncio for everything else
