---
skill: crud-service-python
description: Python service layer archetype — async CRUD operations with cache-aside, audit logging, transaction management, tenant isolation, structured logging, and input validation
version: "1.0"
tags:
  - python
  - service
  - crud
  - archetype
  - backend
  - asyncio
---

# CRUD Service Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-service.md` (Go). Both follow the same structural conventions: dependency injection, tenant isolation, cache-aside, audit logging, and optimistic locking.

Complete, production-ready Python service layer template. Every generated service MUST follow this pattern.

## Domain Types

```python
# app/domain/base.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass
class Entity:
    """Base for all domain objects."""

    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=None))
    deleted_at: datetime | None = None
    created_by: UUID = field(default_factory=uuid4)
    updated_by: UUID = field(default_factory=uuid4)
    version: int = 1


@dataclass
class ListFilters:
    """Common filter parameters for cursor-based list operations."""

    cursor: str | None = None
    page_size: int = 20
    sort_by: str = "created_at"
    sort_dir: str = "desc"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ListResult(Generic[T]):
    """Wraps cursor-paginated results."""

    items: list[T]
    cursor: str | None = None
    has_more: bool = False
    total: int = 0


@dataclass
class OffsetListFilters:
    """Offset-based pagination parameters (for admin/reporting UIs)."""

    page: int = 1
    per_page: int = 20
    sort_by: str = "created_at"
    sort_dir: str = "desc"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class OffsetListResult(Generic[T]):
    """Wraps offset-paginated results."""

    items: list[T]
    total: int = 0


@dataclass
class AuditEntry:
    """Records a mutation for compliance."""

    action: str
    entity_id: UUID
    tenant_id: UUID
    actor_id: UUID
    timestamp: datetime
    changes: Any = None
```

## Widget Domain Model

```python
# app/domain/widget.py

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.base import Entity


class WidgetStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass
class Widget(Entity):
    """Widget domain object."""

    name: str = ""
    description: str = ""
    status: WidgetStatus = WidgetStatus.ACTIVE
```

## Protocol Definitions (Interfaces)

```python
# app/services/protocols.py

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.domain.base import ListFilters, ListResult, OffsetListFilters, OffsetListResult
from app.domain.widget import Widget


@runtime_checkable
class WidgetRepository(Protocol):
    """Data access contract for widgets. Owned by the consumer (service)."""

    async def create(self, widget: Widget) -> None: ...
    async def get_by_id(self, tenant_id: UUID, widget_id: UUID) -> Widget | None: ...
    async def update(self, widget: Widget) -> bool: ...
    async def soft_delete(self, tenant_id: UUID, widget_id: UUID) -> bool: ...
    async def list(self, tenant_id: UUID, filters: ListFilters) -> ListResult[Widget]: ...
    async def list_offset(self, tenant_id: UUID, filters: OffsetListFilters) -> OffsetListResult[Widget]: ...


@runtime_checkable
class Cache(Protocol):
    """Abstracts the caching layer."""

    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...


@runtime_checkable
class AuditWriter(Protocol):
    """Writes audit entries to the audit log."""

    async def write(self, entry: Any) -> None: ...


@runtime_checkable
class TxManager(Protocol):
    """Abstracts database transactions for service-layer orchestration."""

    async def __aenter__(self) -> "TxManager": ...
    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None: ...
```

## Service Implementation

```python
# app/services/widget.py

import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.base import AuditEntry, ListFilters, ListResult, OffsetListFilters, OffsetListResult
from app.domain.widget import Widget, WidgetStatus
from app.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.middleware.request_id import get_request_id
from app.services.protocols import AuditWriter, Cache, TxManager, WidgetRepository

logger = logging.getLogger(__name__)

# Cache TTL in seconds
_CACHE_TTL = 300  # 5 minutes


class WidgetService:
    """
    Widget business logic with cache-aside, audit logging, and tenant isolation.

    Rule: Every dependency explicit in constructor. No global state.
    """

    def __init__(
        self,
        repo: WidgetRepository,
        cache: Cache,
        audit_writer: AuditWriter,
        tx_manager_factory: type[TxManager] | None = None,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._audit = audit_writer
        self._tx_factory = tx_manager_factory
        self._logger = logging.getLogger(f"{__name__}.WidgetService")
```

## Create Implementation

```python
    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        description: str = "",
    ) -> Widget:
        req_id = get_request_id()
        log = self._logger.getChild("create")

        # 1. Validate input
        self._validate_name(name)
        self._validate_description(description)

        # 2. Build domain object
        now = datetime.utcnow()
        widget = Widget(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            description=description,
            status=WidgetStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            created_by=user_id,
            updated_by=user_id,
            version=1,
        )

        # 3. Persist
        await self._repo.create(widget)

        # 4. Audit log
        await self._audit_log(
            action="widget.created",
            entity_id=widget.id,
            tenant_id=tenant_id,
            actor_id=user_id,
            changes={"name": name, "description": description},
        )

        log.info(
            "widget created",
            extra={"request_id": req_id, "widget_id": str(widget.id), "tenant_id": str(tenant_id)},
        )
        return widget
```

## Get with Cache-Aside Pattern

```python
    async def get(self, *, tenant_id: UUID, widget_id: UUID) -> Widget:
        req_id = get_request_id()
        log = self._logger.getChild("get")

        # 1. Check cache
        cache_key = f"widget:{tenant_id}:{widget_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            log.debug("cache hit", extra={"request_id": req_id, "widget_id": str(widget_id)})
            return self._deserialize_widget(cached)

        log.debug("cache miss, querying database", extra={"request_id": req_id, "widget_id": str(widget_id)})

        # 2. Query DB
        widget = await self._repo.get_by_id(tenant_id, widget_id)
        if widget is None:
            raise NotFoundError(resource="widget", identifier=str(widget_id))

        # 3. Populate cache
        await self._cache_set(cache_key, widget)

        return widget
```

## Update with Cache Invalidation and Optimistic Locking

```python
    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        widget_id: UUID,
        name: str,
        description: str,
        version: int,
    ) -> Widget:
        req_id = get_request_id()
        log = self._logger.getChild("update")

        # 1. Validate input
        self._validate_name(name)
        self._validate_description(description)

        # 2. Fetch current (ensures tenant-scoping)
        existing = await self._repo.get_by_id(tenant_id, widget_id)
        if existing is None:
            raise NotFoundError(resource="widget", identifier=str(widget_id))

        # 3. Optimistic lock check
        if version != existing.version:
            raise ConflictError(
                resource="widget",
                reason="version mismatch — reload and retry",
            )

        # 4. Apply changes
        existing.name = name
        existing.description = description
        existing.updated_at = datetime.utcnow()
        existing.updated_by = user_id
        existing.version += 1

        # 5. Persist
        success = await self._repo.update(existing)
        if not success:
            raise ConflictError(resource="widget", reason="concurrent modification detected")

        # 6. Invalidate cache
        cache_key = f"widget:{tenant_id}:{widget_id}"
        await self._cache.delete(cache_key)

        # 7. Audit log
        await self._audit_log(
            action="widget.updated",
            entity_id=widget_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            changes={"name": name, "description": description, "version": existing.version},
        )

        log.info(
            "widget updated",
            extra={"request_id": req_id, "widget_id": str(widget_id), "tenant_id": str(tenant_id)},
        )
        return existing
```

## Delete with Cache Invalidation

```python
    async def delete(self, *, tenant_id: UUID, widget_id: UUID) -> None:
        req_id = get_request_id()
        log = self._logger.getChild("delete")

        # 1. Soft delete (sets deleted_at, does not remove row)
        deleted = await self._repo.soft_delete(tenant_id, widget_id)
        if not deleted:
            raise NotFoundError(resource="widget", identifier=str(widget_id))

        # 2. Invalidate cache
        cache_key = f"widget:{tenant_id}:{widget_id}"
        await self._cache.delete(cache_key)

        # 3. Audit log — extract user_id from request context if available
        await self._audit_log(
            action="widget.deleted",
            entity_id=widget_id,
            tenant_id=tenant_id,
            actor_id=UUID(int=0),  # caller should pass user_id in production
            changes=None,
        )

        log.info(
            "widget deleted",
            extra={"request_id": req_id, "widget_id": str(widget_id), "tenant_id": str(tenant_id)},
        )
```

## List with Filters

```python
    async def list(
        self,
        *,
        tenant_id: UUID,
        cursor: str | None = None,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        field_filters: dict[str, str] | None = None,
    ) -> ListResult[Widget]:
        req_id = get_request_id()
        log = self._logger.getChild("list")

        # Enforce pagination defaults and maximums
        page_size = max(1, min(page_size, 100))
        if sort_by not in {"created_at", "updated_at", "name"}:
            sort_by = "created_at"
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"

        filters = ListFilters(
            cursor=cursor,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fields=field_filters or {},
        )

        result = await self._repo.list(tenant_id, filters)

        log.info(
            "list completed",
            extra={
                "request_id": req_id,
                "result_count": len(result.items),
                "has_more": result.has_more,
                "tenant_id": str(tenant_id),
            },
        )
        return result

    async def list_offset(
        self,
        *,
        tenant_id: UUID,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        field_filters: dict[str, str] | None = None,
    ) -> OffsetListResult[Widget]:
        req_id = get_request_id()
        log = self._logger.getChild("list_offset")

        per_page = max(1, min(per_page, 100))
        page = max(1, page)

        filters = OffsetListFilters(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fields=field_filters or {},
        )

        result = await self._repo.list_offset(tenant_id, filters)

        log.info(
            "list_offset completed",
            extra={
                "request_id": req_id,
                "page": page,
                "per_page": per_page,
                "result_count": len(result.items),
                "total": result.total,
            },
        )
        return result
```

## Transaction Support for Multi-Step Operations

```python
    async def create_with_components(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        description: str,
        components: list[dict],
    ) -> Widget:
        """
        Create a widget and its child components within a single transaction.

        Uses the async context manager pattern for transaction management.
        If any step fails, the entire transaction rolls back.
        """
        req_id = get_request_id()
        log = self._logger.getChild("create_with_components")

        self._validate_name(name)
        self._validate_description(description)

        now = datetime.utcnow()
        widget = Widget(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            description=description,
            status=WidgetStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            created_by=user_id,
            updated_by=user_id,
            version=1,
        )

        if self._tx_factory is None:
            raise RuntimeError("transaction manager not configured")

        async with self._tx_factory() as tx:  # type: ignore[call-arg]
            # Step 1: Create parent widget
            await self._repo.create(widget)

            # Step 2: Create child components (all within same transaction)
            for comp_data in components:
                # component_repo.create(tx_ctx, component) — placeholder
                pass

        log.info(
            "widget created with components",
            extra={
                "request_id": req_id,
                "widget_id": str(widget.id),
                "component_count": len(components),
            },
        )
        return widget
```

## Input Validation Helpers

```python
    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate widget name. Raises ValidationError on failure."""
        if not name or not name.strip():
            raise ValidationError(field="name", reason="name is required")
        if len(name) > 255:
            raise ValidationError(field="name", reason="name must be 255 characters or fewer")

    @staticmethod
    def _validate_description(description: str) -> None:
        """Validate widget description. Raises ValidationError on failure."""
        if len(description) > 2000:
            raise ValidationError(
                field="description",
                reason="description must be 2000 characters or fewer",
            )
```

## Cache Helpers

```python
    async def _cache_set(self, key: str, widget: Widget) -> None:
        """Serialize and store a widget in the cache. Failures are logged, not raised."""
        try:
            data = json.dumps(
                {
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
                }
            ).encode()
            await self._cache.set(key, data, _CACHE_TTL)
        except Exception:
            self._logger.warning("cache set failed", extra={"key": key}, exc_info=True)

    @staticmethod
    def _deserialize_widget(data: bytes) -> Widget:
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
```

## Audit Logging Helper

```python
    async def _audit_log(
        self,
        *,
        action: str,
        entity_id: UUID,
        tenant_id: UUID,
        actor_id: UUID,
        changes: dict | None,
    ) -> None:
        """
        Fire-and-forget audit entry. Never blocks the business operation.
        In production, publishes to an event bus or writes to an append-only table.
        """
        entry = AuditEntry(
            action=action,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            timestamp=datetime.utcnow(),
            changes=changes,
        )
        try:
            await self._audit.write(entry)
        except Exception:
            self._logger.error(
                "audit log failed",
                extra={"action": action, "entity_id": str(entity_id)},
                exc_info=True,
            )
```

## Critical Rules

- Every operation MUST scope queries by `tenant_id` — no cross-tenant data leaks
- Every mutation MUST produce an audit log entry
- Every public method MUST extract `request_id` via `get_request_id()` and include it in all structured log lines
- Cache invalidation MUST happen on every write (Update, Delete)
- Cache misses MUST populate the cache before returning
- Optimistic locking via `version` field — reject stale writes with `ConflictError`
- Input validation MUST happen before any side effects (DB, cache, external calls)
- Errors MUST use the domain error types from `app/errors` — never raise bare `Exception`
- Max 40 lines of logic per method — extract helpers for complex steps
- Accept protocols (interfaces), inject concrete implementations — constructor takes protocols
- Never return unbounded lists — always enforce `page_size` max (100)
- Transaction support uses `async with` context managers — rollback is automatic on exception
- Cache failures are logged, never raised — cache is a performance optimization, not a correctness requirement
- Use `logging.getLogger(__name__)` for structured logging — never print to stdout
