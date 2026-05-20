---
skill: crud-repository-python
description: Python repository archetype — SQLAlchemy async + asyncpg, parameterized queries, cursor pagination, soft delete, optimistic locking, multi-tenant isolation, batch operations, multi-level caching
version: "1.0"
tags:
  - python
  - repository
  - sqlalchemy
  - asyncpg
  - postgres
  - archetype
  - backend
---

# CRUD Repository Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-repository.md` (Go/pgx). Both follow the same structural conventions: parameterized queries, tenant isolation, soft delete, optimistic locking, and multi-level caching.

Complete SQLAlchemy async repository template backed by asyncpg. Every generated repository MUST follow this pattern.

## SQLAlchemy Model Definition

```python
# app/models/widget.py

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class WidgetModel(Base):
    """SQLAlchemy model for the widgets table."""

    __tablename__ = "widgets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

## Async Engine and Session Factory

```python
# app/db/engine.py

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Recommended pool configuration — match Go archetype's PoolConfig.
# Use asyncpg as the driver for production PostgreSQL connections.
_POOL_CONFIG = {
    "pool_size": 20,             # max steady-state connections
    "max_overflow": 30,          # burst connections above pool_size (total max = 50)
    "pool_timeout": 30,          # seconds to wait for a connection from the pool
    "pool_recycle": 3600,        # recycle connections after 1 hour
    "pool_pre_ping": True,       # health-check connection before use
}


def create_engine(database_url: str):
    """
    Create an async SQLAlchemy engine.

    database_url format: postgresql+asyncpg://user:password@host:5432/dbname
    """
    return create_async_engine(database_url, **_POOL_CONFIG, echo=False)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

## Transaction Context Manager

```python
# app/db/transaction.py

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@asynccontextmanager
async def transaction(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """
    Async context manager for database transactions.
    Commits on success, rolls back on exception.

    Usage:
        async with transaction(session_factory) as session:
            session.add(widget)
            session.add(component)
        # auto-committed here, or rolled back on exception
    """
    async with session_factory() as session:
        async with session.begin():
            yield session
```

## Repository Implementation

```python
# app/repositories/widget.py

import json
import logging
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.base import ListFilters, ListResult, OffsetListFilters, OffsetListResult
from app.domain.widget import Widget, WidgetStatus
from app.errors import ConflictError, InternalError, NotFoundError, ValidationError
from app.models.widget import WidgetModel

logger = logging.getLogger(__name__)


class WidgetRepository:
    """
    PostgreSQL repository for widgets using SQLAlchemy async sessions.

    Implements the WidgetRepository protocol from app.services.protocols.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: "RedisClient | None" = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._logger = logging.getLogger(f"{__name__}.WidgetRepository")

    # -----------------------------------------------------------------------
    # Mapping helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_domain(model: WidgetModel) -> Widget:
        """Map SQLAlchemy model to domain object."""
        return Widget(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            status=WidgetStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            version=model.version,
        )

    @staticmethod
    def _to_model(widget: Widget) -> WidgetModel:
        """Map domain object to SQLAlchemy model."""
        return WidgetModel(
            id=widget.id,
            tenant_id=widget.tenant_id,
            name=widget.name,
            description=widget.description,
            status=widget.status.value,
            created_at=widget.created_at,
            updated_at=widget.updated_at,
            deleted_at=widget.deleted_at,
            created_by=widget.created_by,
            updated_by=widget.updated_by,
            version=widget.version,
        )
```

## Create

```python
    async def create(self, widget: Widget) -> None:
        log = self._logger.getChild("create")

        async with self._session_factory() as session, session.begin():
            model = self._to_model(widget)
            session.add(model)
            try:
                await session.flush()
            except Exception as exc:
                raise self._map_error(exc, "create") from exc

        log.info("widget created", extra={"widget_id": str(widget.id), "tenant_id": str(widget.tenant_id)})
```

## GetByID with Cache

```python
    async def get_by_id(self, tenant_id: UUID, widget_id: UUID) -> Widget | None:
        log = self._logger.getChild("get_by_id")
        cache_key = f"widget:{tenant_id}:{widget_id}"

        # L1: Redis cache
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached is not None:
                log.debug("cache hit", extra={"widget_id": str(widget_id)})
                return self._deserialize(cached)

        # L2: PostgreSQL
        async with self._session_factory() as session:
            stmt = (
                select(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == tenant_id,
                        WidgetModel.id == widget_id,
                        WidgetModel.deleted_at.is_(None),
                    )
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

            if model is None:
                return None

            widget = self._to_domain(model)

        # Populate cache
        if self._redis is not None:
            await self._cache_set(cache_key, widget)

        return widget
```

## Update with Optimistic Locking

```python
    async def update(self, widget: Widget) -> bool:
        """
        Update a widget using optimistic locking.
        Returns True if the update succeeded, False if version mismatch.

        The WHERE clause checks version = (widget.version - 1) to ensure
        no concurrent modification occurred.
        """
        log = self._logger.getChild("update")

        async with self._session_factory() as session, session.begin():
            stmt = (
                update(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == widget.tenant_id,
                        WidgetModel.id == widget.id,
                        WidgetModel.version == widget.version - 1,  # expected previous version
                        WidgetModel.deleted_at.is_(None),
                    )
                )
                .values(
                    name=widget.name,
                    description=widget.description,
                    status=widget.status.value,
                    updated_at=widget.updated_at,
                    updated_by=widget.updated_by,
                    version=widget.version,
                )
            )
            result = await session.execute(stmt)
            rows_affected = result.rowcount

        if rows_affected == 0:
            return False

        # Invalidate cache on write
        await self._invalidate_cache(widget.tenant_id, widget.id)

        log.info("widget updated", extra={"widget_id": str(widget.id), "version": widget.version})
        return True
```

## Soft Delete

```python
    async def soft_delete(self, tenant_id: UUID, widget_id: UUID) -> bool:
        """
        Soft delete a widget by setting deleted_at.
        Returns True if a row was affected, False if not found.
        """
        log = self._logger.getChild("soft_delete")
        now = datetime.utcnow()

        async with self._session_factory() as session, session.begin():
            stmt = (
                update(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == tenant_id,
                        WidgetModel.id == widget_id,
                        WidgetModel.deleted_at.is_(None),
                    )
                )
                .values(deleted_at=now, updated_at=now)
            )
            result = await session.execute(stmt)
            rows_affected = result.rowcount

        if rows_affected == 0:
            return False

        await self._invalidate_cache(tenant_id, widget_id)

        log.info("widget soft-deleted", extra={"widget_id": str(widget_id), "tenant_id": str(tenant_id)})
        return True
```

## List with Cursor-Based Pagination

```python
    async def list(self, tenant_id: UUID, filters: ListFilters) -> ListResult[Widget]:
        """
        List widgets with cursor-based pagination.

        Cursor strategy: base64-encoded JSON of (sort_value, id) for stable pagination.
        Requests LIMIT + 1 to detect has_more without a separate count query.
        """
        log = self._logger.getChild("list")

        # Resolve the sort column from the model
        sort_col = self._resolve_sort_column(filters.sort_by)

        async with self._session_factory() as session:
            # Base query with tenant isolation and soft delete filter
            stmt = (
                select(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == tenant_id,
                        WidgetModel.deleted_at.is_(None),
                    )
                )
            )

            # Apply dynamic field filters
            stmt = self._apply_field_filters(stmt, filters.fields)

            # Apply cursor
            if filters.cursor:
                sort_value, cursor_id = self._decode_cursor(filters.cursor)
                if filters.sort_dir == "desc":
                    stmt = stmt.where(
                        (sort_col, WidgetModel.id) < (sort_value, cursor_id)
                    )
                else:
                    stmt = stmt.where(
                        (sort_col, WidgetModel.id) > (sort_value, cursor_id)
                    )

            # Order and limit (request limit+1 to detect has_more)
            if filters.sort_dir == "desc":
                stmt = stmt.order_by(sort_col.desc(), WidgetModel.id.desc())
            else:
                stmt = stmt.order_by(sort_col.asc(), WidgetModel.id.asc())

            stmt = stmt.limit(filters.page_size + 1)

            result = await session.execute(stmt)
            models = list(result.scalars().all())

        # Determine has_more and trim to requested page size
        has_more = len(models) > filters.page_size
        if has_more:
            models = models[: filters.page_size]

        items = [self._to_domain(m) for m in models]

        # Build next cursor from last item
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            sort_value = getattr(last, filters.sort_by)
            next_cursor = self._encode_cursor(sort_value, last.id)

        # Count total (optional — use for UI, skip for performance on huge tables)
        total = await self._count_total(tenant_id, filters.fields)

        log.info(
            "list completed",
            extra={"result_count": len(items), "has_more": has_more, "total": total},
        )

        return ListResult(items=items, cursor=next_cursor, has_more=has_more, total=total)
```

## List with Offset-Based Pagination (Admin/Reporting)

```python
    async def list_offset(self, tenant_id: UUID, filters: OffsetListFilters) -> OffsetListResult[Widget]:
        """
        List widgets with offset-based pagination.
        Use for admin dashboards and reporting UIs where users need "jump to page N".
        """
        log = self._logger.getChild("list_offset")
        offset = (filters.page - 1) * filters.per_page

        sort_col = self._resolve_sort_column(filters.sort_by)

        async with self._session_factory() as session:
            stmt = (
                select(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == tenant_id,
                        WidgetModel.deleted_at.is_(None),
                    )
                )
            )

            stmt = self._apply_field_filters(stmt, filters.fields)

            if filters.sort_dir == "desc":
                stmt = stmt.order_by(sort_col.desc(), WidgetModel.id.desc())
            else:
                stmt = stmt.order_by(sort_col.asc(), WidgetModel.id.asc())

            stmt = stmt.limit(filters.per_page).offset(offset)

            result = await session.execute(stmt)
            models = list(result.scalars().all())

        items = [self._to_domain(m) for m in models]
        total = await self._count_total(tenant_id, filters.fields)

        log.info(
            "list_offset completed",
            extra={"page": filters.page, "per_page": filters.per_page, "result_count": len(items), "total": total},
        )

        return OffsetListResult(items=items, total=total)
```

## Batch Operations

```python
    async def batch_create(self, widgets: list[Widget]) -> None:
        """
        Bulk insert widgets using SQLAlchemy's insert with multiple values.
        More efficient than individual inserts for large batches.
        """
        if not widgets:
            return

        log = self._logger.getChild("batch_create")

        async with self._session_factory() as session, session.begin():
            models = [self._to_model(w) for w in widgets]
            session.add_all(models)
            try:
                await session.flush()
            except Exception as exc:
                raise self._map_error(exc, "batch_create") from exc

        log.info("batch created", extra={"count": len(widgets)})

    async def batch_update(self, widgets: list[Widget]) -> None:
        """
        Bulk update widgets within a single transaction.
        Each update uses optimistic locking — ConflictError on version mismatch.
        """
        if not widgets:
            return

        log = self._logger.getChild("batch_update")

        async with self._session_factory() as session, session.begin():
            for i, widget in enumerate(widgets):
                stmt = (
                    update(WidgetModel)
                    .where(
                        and_(
                            WidgetModel.tenant_id == widget.tenant_id,
                            WidgetModel.id == widget.id,
                            WidgetModel.version == widget.version - 1,
                            WidgetModel.deleted_at.is_(None),
                        )
                    )
                    .values(
                        name=widget.name,
                        description=widget.description,
                        status=widget.status.value,
                        updated_at=widget.updated_at,
                        updated_by=widget.updated_by,
                        version=widget.version,
                    )
                )
                result = await session.execute(stmt)
                if result.rowcount == 0:
                    raise ConflictError(
                        resource="widget",
                        reason=f"version mismatch on item {i} (id={widget.id})",
                    )

        # Invalidate cache for all updated widgets
        for w in widgets:
            await self._invalidate_cache(w.tenant_id, w.id)

        log.info("batch updated", extra={"count": len(widgets)})
```

## Cursor Encoding / Decoding

```python
    @staticmethod
    def _encode_cursor(sort_value: datetime | str, entity_id: UUID) -> str:
        """Encode a cursor as base64(JSON{sort_value, id}) — opaque, stable across inserts."""
        if isinstance(sort_value, datetime):
            sort_value = sort_value.isoformat()
        payload = json.dumps({"sv": sort_value, "id": str(entity_id)})
        return urlsafe_b64encode(payload.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, UUID]:
        """Decode a cursor from base64 JSON. Returns (sort_value, id)."""
        try:
            data = json.loads(urlsafe_b64decode(cursor.encode()))
            return data["sv"], UUID(data["id"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError(field="cursor", reason="invalid cursor format") from exc
```

## Query Helpers

```python
    @staticmethod
    def _resolve_sort_column(sort_by: str):
        """
        Map sort field names to SQLAlchemy model columns.
        Allow-listed to prevent SQL injection — unknown fields default to created_at.
        """
        allowed = {
            "created_at": WidgetModel.created_at,
            "updated_at": WidgetModel.updated_at,
            "name": WidgetModel.name,
        }
        return allowed.get(sort_by, WidgetModel.created_at)

    @staticmethod
    def _apply_field_filters(stmt, fields: dict[str, str]):
        """
        Apply dynamic field filters to a SELECT statement.
        Only allow-listed fields are applied — unknown fields are silently ignored.
        """
        allowed = {
            "status": WidgetModel.status,
            "priority": None,    # add WidgetModel.priority when column exists
            "category": None,    # add WidgetModel.category when column exists
        }
        for field_name, value in fields.items():
            col = allowed.get(field_name)
            if col is not None:
                stmt = stmt.where(col == value)
        return stmt

    async def _count_total(self, tenant_id: UUID, fields: dict[str, str] | None = None) -> int:
        """Count total matching widgets for pagination metadata."""
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(WidgetModel)
                .where(
                    and_(
                        WidgetModel.tenant_id == tenant_id,
                        WidgetModel.deleted_at.is_(None),
                    )
                )
            )
            if fields:
                stmt = self._apply_field_filters(stmt, fields)

            result = await session.execute(stmt)
            return result.scalar_one()
```

## Cache Helpers

```python
    _CACHE_TTL = 300  # 5 minutes

    async def _cache_set(self, key: str, widget: Widget) -> None:
        """Store a widget in Redis cache. Failures are logged, not raised."""
        if self._redis is None:
            return
        try:
            data = json.dumps({
                "id": str(widget.id),
                "tenant_id": str(widget.tenant_id),
                "name": widget.name,
                "description": widget.description,
                "status": widget.status.value,
                "created_at": widget.created_at.isoformat(),
                "updated_at": widget.updated_at.isoformat(),
                "deleted_at": widget.deleted_at.isoformat() if widget.deleted_at else None,
                "created_by": str(widget.created_by),
                "updated_by": str(widget.updated_by),
                "version": widget.version,
            }).encode()
            await self._redis.set(key, data, self._CACHE_TTL)
        except Exception:
            self._logger.warning("cache set failed", extra={"key": key}, exc_info=True)

    @staticmethod
    def _deserialize(data: bytes) -> Widget:
        """Deserialize a widget from cached JSON bytes."""
        obj = json.loads(data)
        return Widget(
            id=UUID(obj["id"]),
            tenant_id=UUID(obj["tenant_id"]),
            name=obj["name"],
            description=obj["description"],
            status=WidgetStatus(obj["status"]),
            created_at=datetime.fromisoformat(obj["created_at"]),
            updated_at=datetime.fromisoformat(obj["updated_at"]),
            deleted_at=datetime.fromisoformat(obj["deleted_at"]) if obj["deleted_at"] else None,
            created_by=UUID(obj["created_by"]),
            updated_by=UUID(obj["updated_by"]),
            version=obj["version"],
        )

    async def _invalidate_cache(self, tenant_id: UUID, widget_id: UUID) -> None:
        """Remove a widget from the cache."""
        if self._redis is None:
            return
        key = f"widget:{tenant_id}:{widget_id}"
        try:
            await self._redis.delete(key)
        except Exception:
            self._logger.warning("cache invalidation failed", extra={"key": key}, exc_info=True)
```

## Error Mapping

```python
    @staticmethod
    def _map_error(exc: Exception, operation: str) -> Exception:
        """
        Map database exceptions to domain error types.
        Creates domain errors at the repository boundary where we KNOW the error type.
        """
        from sqlalchemy.exc import IntegrityError, OperationalError

        if isinstance(exc, IntegrityError):
            detail = str(exc.orig) if exc.orig else str(exc)

            # unique_violation (PostgreSQL 23505)
            if "unique" in detail.lower() or "23505" in detail:
                return ConflictError(
                    resource="widget",
                    reason=f"duplicate value — {detail}",
                )

            # foreign_key_violation (PostgreSQL 23503)
            if "foreign key" in detail.lower() or "23503" in detail:
                return ValidationError(
                    field="reference",
                    reason="referenced resource does not exist",
                )

            # check_violation (PostgreSQL 23514)
            if "check" in detail.lower() or "23514" in detail:
                return ValidationError(
                    field="constraint",
                    reason=f"value violates constraint — {detail}",
                )

        if isinstance(exc, OperationalError):
            return InternalError(cause=exc)

        return InternalError(cause=exc)
```

## Raw asyncpg Alternative (No ORM)

For performance-critical paths or when you need raw SQL, use asyncpg directly:

```python
# app/repositories/widget_raw.py

import asyncpg
from uuid import UUID

from app.domain.widget import Widget
from app.errors import NotFoundError


class WidgetRawRepository:
    """
    Raw asyncpg repository for performance-critical operations.
    Use when SQLAlchemy overhead is unacceptable (e.g., batch analytics queries).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, tenant_id: UUID, widget_id: UUID) -> Widget | None:
        query = """
            SELECT id, tenant_id, name, description, status,
                   created_at, updated_at, deleted_at, created_by, updated_by, version
            FROM widgets
            WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, tenant_id, widget_id)
            if row is None:
                return None
            return self._row_to_domain(row)

    async def batch_create_copy(self, widgets: list[Widget]) -> int:
        """
        High-performance bulk insert using PostgreSQL COPY protocol.
        Equivalent to pgx.CopyFrom in the Go archetype.
        """
        records = [
            (w.id, w.tenant_id, w.name, w.description, w.status.value,
             w.created_at, w.updated_at, w.created_by, w.updated_by, w.version)
            for w in widgets
        ]
        async with self._pool.acquire() as conn:
            return await conn.copy_records_to_table(
                "widgets",
                records=records,
                columns=[
                    "id", "tenant_id", "name", "description", "status",
                    "created_at", "updated_at", "created_by", "updated_by", "version",
                ],
            )

    @staticmethod
    def _row_to_domain(row: asyncpg.Record) -> Widget:
        from app.domain.widget import WidgetStatus
        return Widget(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            description=row["description"],
            status=WidgetStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
            version=row["version"],
        )
```

## Critical Rules

- Every query MUST scope by `tenant_id` — no cross-tenant data leaks
- Every query MUST use parameterized placeholders (SQLAlchemy binds or asyncpg `$N`) — never string interpolation
- Every read query MUST filter `deleted_at IS NULL` (soft delete)
- Every write operation MUST use `async with session.begin()` for automatic commit/rollback
- Update operations MUST use optimistic locking: `WHERE version = expected`
- Column names in ORDER BY / WHERE MUST be allow-listed via `_resolve_sort_column` and `_apply_field_filters`
- Cursor values MUST be opaque (base64-encoded JSON) — never expose raw DB values
- List queries MUST request `LIMIT + 1` to detect `has_more` without extra count query
- Batch inserts SHOULD use `copy_records_to_table` for high-throughput (asyncpg's COPY protocol)
- Database exceptions MUST be mapped to domain errors (`ConflictError`, `ValidationError`, `InternalError`) at the repository boundary
- Cache MUST be invalidated on every write (Update, Delete)
- Cache failures are logged, never raised — cache is an optimization, not a correctness requirement
- Use `async_sessionmaker` with `expire_on_commit=False` to avoid lazy-load issues after commit
