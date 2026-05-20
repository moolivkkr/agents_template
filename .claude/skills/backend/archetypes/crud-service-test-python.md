---
skill: crud-service-test-python
description: Python service layer test archetype — pytest + AsyncMock, mocked repository/cache/audit, table-driven tests, cache-aside verification, optimistic locking, tenant isolation, transaction rollback
version: "1.0"
tags:
  - python
  - service
  - unit-test
  - archetype
  - backend
  - testing
  - asyncio
---

# CRUD Service Test Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-service-test.md` (Go/testify). Both test the same cache-aside, audit, and optimistic locking behavior.

Complete unit test template for the Python service layer. Every generated service test file MUST follow this pattern.

## Test File Location

```
tests/
  services/
    test_widget_service.py   <- THIS file
  conftest.py                <- shared fixtures
  factories.py               <- test data builders
```

Rule: Test file lives in `tests/services/` mirroring the `app/services/` layout.

## Test Data Factory

```python
# tests/factories.py

from __future__ import annotations

import uuid
from datetime import datetime

from app.domain.base import ListFilters, ListResult
from app.domain.widget import Widget, WidgetStatus

def make_widget(
    *,
    id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    name: str | None = None,
    description: str = "A test widget",
    status: WidgetStatus = WidgetStatus.ACTIVE,
    version: int = 1,
    created_by: uuid.UUID | None = None,
    updated_by: uuid.UUID | None = None,
) -> Widget:
    """Build a Widget domain object with sensible defaults. Unique names per call."""
    now = datetime.utcnow()
    return Widget(
        id=id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        name=name or f"widget-{uuid.uuid4().hex[:8]}",
        description=description,
        status=status,
        created_at=now,
        updated_at=now,
        created_by=created_by or uuid.uuid4(),
        updated_by=updated_by or uuid.uuid4(),
        version=version,
    )

def make_list_result(
    items: list[Widget] | None = None,
    *,
    cursor: str | None = None,
    has_more: bool = False,
    total: int = 0,
) -> ListResult[Widget]:
    """Build a ListResult with defaults."""
    return ListResult(
        items=items or [],
        cursor=cursor,
        has_more=has_more,
        total=total,
    )
```

## Mock Definitions

```python
# tests/services/test_widget_service.py

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.domain.base import AuditEntry, ListFilters, ListResult
from app.domain.widget import Widget, WidgetStatus
from app.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.services.widget import WidgetService
from tests.factories import make_list_result, make_widget

# Fixtures

@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock repository implementing WidgetRepository protocol."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.soft_delete = AsyncMock()
    repo.list = AsyncMock()
    return repo

@pytest.fixture
def mock_cache() -> AsyncMock:
    """Mock cache implementing Cache protocol."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # default: cache miss
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return cache

@pytest.fixture
def mock_audit() -> AsyncMock:
    """Mock audit writer implementing AuditWriter protocol."""
    audit = AsyncMock()
    audit.write = AsyncMock()
    return audit

@pytest.fixture
def service(mock_repo: AsyncMock, mock_cache: AsyncMock, mock_audit: AsyncMock) -> WidgetService:
    """WidgetService wired to mocked dependencies — fresh per test."""
    return WidgetService(
        repo=mock_repo,
        cache=mock_cache,
        audit_writer=mock_audit,
    )

@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()

@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()
```

## Create Tests

```python
class TestCreate:
    """Tests for WidgetService.create."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        mock_repo.create.return_value = None

        result = await service.create(
            tenant_id=tenant_id,
            user_id=user_id,
            name="New Widget",
            description="Description",
        )

        assert result.name == "New Widget"
        assert result.tenant_id == tenant_id
        assert result.version == 1
        assert result.id != uuid.UUID(int=0)

        mock_repo.create.assert_called_once()
        created_widget = mock_repo.create.call_args.args[0]
        assert isinstance(created_widget, Widget)
        assert created_widget.tenant_id == tenant_id

        # Audit log must be written
        mock_audit.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_error_empty_name(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name="",
                description="Desc",
            )

        assert exc_info.value.code == "VALIDATION_ERROR"
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_error_name_too_long(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ValidationError):
            await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name="x" * 256,
                description="Desc",
            )

        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_repo_error_propagates(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        mock_repo.create.side_effect = RuntimeError("connection refused")

        with pytest.raises(RuntimeError, match="connection refused"):
            await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name="Widget",
                description="Desc",
            )
```

## Create Tests — Table-Driven

```python
class TestCreateTableDriven:
    """Table-driven create tests for concise input/output coverage."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name, description, should_raise",
        [
            ("Valid Name", "Valid description", False),
            ("", "Description", True),            # empty name
            ("   ", "Description", True),           # whitespace-only name
            ("x" * 256, "Description", True),       # name too long
            ("Valid", "x" * 2001, True),            # description too long
        ],
        ids=[
            "valid-input",
            "empty-name",
            "whitespace-name",
            "name-too-long",
            "description-too-long",
        ],
    )
    async def test_input_validation(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        description: str,
        should_raise: bool,
    ) -> None:
        mock_repo.create.return_value = None

        if should_raise:
            with pytest.raises(ValidationError):
                await service.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    name=name,
                    description=description,
                )
            mock_repo.create.assert_not_called()
        else:
            result = await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                description=description,
            )
            assert result.name == name
            mock_repo.create.assert_called_once()
```

## Get Tests — Cache-Aside Behavior

```python
class TestGet:
    """Tests for WidgetService.get — cache-aside pattern."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Cache hit should return from cache without querying the database."""
        widget = make_widget(tenant_id=tenant_id)
        cache_data = json.dumps({
            "id": str(widget.id),
            "tenant_id": str(widget.tenant_id),
            "name": widget.name,
            "description": widget.description,
            "status": widget.status.value,
            "created_at": widget.created_at.isoformat(),
            "updated_at": widget.updated_at.isoformat(),
            "deleted_at": None,
            "created_by": str(widget.created_by),
            "updated_by": str(widget.updated_by),
            "version": widget.version,
        }).encode()

        mock_cache.get.return_value = cache_data

        result = await service.get(tenant_id=tenant_id, widget_id=widget.id)

        assert result.id == widget.id
        mock_repo.get_by_id.assert_not_called()  # DB never queried

    @pytest.mark.asyncio
    async def test_cache_miss_populates_cache(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Cache miss should query DB and populate the cache."""
        widget = make_widget(tenant_id=tenant_id)
        cache_key = f"widget:{tenant_id}:{widget.id}"

        mock_cache.get.return_value = None
        mock_repo.get_by_id.return_value = widget

        result = await service.get(tenant_id=tenant_id, widget_id=widget.id)

        assert result.id == widget.id
        mock_repo.get_by_id.assert_called_once_with(tenant_id, widget.id)
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        widget_id = uuid.uuid4()
        mock_cache.get.return_value = None
        mock_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            await service.get(tenant_id=tenant_id, widget_id=widget_id)

        assert exc_info.value.http_status == 404
        mock_cache.set.assert_not_called()  # don't cache 404s

    @pytest.mark.asyncio
    async def test_cache_failure_falls_through_to_db(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Cache errors should be swallowed — cache is an optimization, not correctness."""
        widget = make_widget(tenant_id=tenant_id)
        mock_cache.get.side_effect = ConnectionError("redis down")
        mock_repo.get_by_id.return_value = widget

        # Should NOT raise — cache failure is logged, not propagated
        result = await service.get(tenant_id=tenant_id, widget_id=widget.id)

        assert result.id == widget.id
        mock_repo.get_by_id.assert_called_once()
```

## Update Tests — Optimistic Locking

```python
class TestUpdate:
    """Tests for WidgetService.update — optimistic locking and cache invalidation."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = True

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            widget_id=existing.id,
            name="Updated Name",
            description="Updated desc",
            version=1,
        )

        assert result.name == "Updated Name"
        assert result.version == 2  # version incremented

        # Cache must be invalidated
        mock_cache.delete.assert_called_once()

        # Audit log must record the update
        mock_audit.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_version_conflict(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Stale version -> ConflictError, no update attempted."""
        existing = make_widget(tenant_id=tenant_id, version=3)
        mock_repo.get_by_id.return_value = existing

        with pytest.raises(ConflictError) as exc_info:
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                widget_id=existing.id,
                name="Updated",
                description="desc",
                version=1,  # stale — current is 3
            )

        assert exc_info.value.http_status == 409
        mock_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        mock_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                widget_id=uuid.uuid4(),
                name="Updated",
                description="desc",
                version=1,
            )

        mock_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_modification_detected(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """When repo.update returns False (rows_affected == 0), raise ConflictError."""
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = False  # concurrent modification

        with pytest.raises(ConflictError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                widget_id=existing.id,
                name="Updated",
                description="desc",
                version=1,
            )

    @pytest.mark.asyncio
    async def test_validation_on_update(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Input validation must happen before any side effects."""
        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                widget_id=uuid.uuid4(),
                name="",  # invalid
                description="desc",
                version=1,
            )

        mock_repo.get_by_id.assert_not_called()
        mock_repo.update.assert_not_called()
```

## Delete Tests

```python
class TestDelete:
    """Tests for WidgetService.delete — soft delete with cache invalidation."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        widget_id = uuid.uuid4()
        mock_repo.soft_delete.return_value = True

        await service.delete(tenant_id=tenant_id, widget_id=widget_id)

        mock_repo.soft_delete.assert_called_once_with(tenant_id, widget_id)
        mock_cache.delete.assert_called_once()
        mock_audit.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        mock_repo.soft_delete.return_value = False

        with pytest.raises(NotFoundError):
            await service.delete(tenant_id=tenant_id, widget_id=uuid.uuid4())
```

## List Tests — Table-Driven

```python
class TestList:
    """Tests for WidgetService.list — pagination, defaults, clamping."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "page_size, expected_clamped",
        [
            (0, 1),        # zero -> clamp to min 1
            (-5, 1),       # negative -> clamp to min 1
            (50, 50),      # valid
            (100, 100),    # max
            (500, 100),    # exceeds max -> clamp to 100
        ],
        ids=["zero", "negative", "valid-50", "max-100", "exceeds-max"],
    )
    async def test_page_size_clamping(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        page_size: int,
        expected_clamped: int,
    ) -> None:
        mock_repo.list.return_value = make_list_result()

        await service.list(tenant_id=tenant_id, page_size=page_size)

        call_args = mock_repo.list.call_args
        filters = call_args.args[1]  # second positional arg is ListFilters
        assert filters.page_size == expected_clamped

    @pytest.mark.asyncio
    async def test_returns_paginated_results(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        widgets = [make_widget() for _ in range(3)]
        mock_repo.list.return_value = ListResult(
            items=widgets,
            cursor="abc",
            has_more=True,
            total=25,
        )

        result = await service.list(tenant_id=tenant_id, page_size=10)

        assert len(result.items) == 3
        assert result.has_more is True
        assert result.cursor == "abc"
        assert result.total == 25

    @pytest.mark.asyncio
    async def test_empty_list(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        mock_repo.list.return_value = make_list_result()

        result = await service.list(tenant_id=tenant_id)

        assert len(result.items) == 0
        assert result.has_more is False
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_sort_field_allow_list(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Unknown sort_by should default to 'created_at'."""
        mock_repo.list.return_value = make_list_result()

        await service.list(tenant_id=tenant_id, sort_by="drop_table")

        call_args = mock_repo.list.call_args
        filters = call_args.args[1]
        assert filters.sort_by == "created_at"

    @pytest.mark.asyncio
    async def test_sort_dir_validation(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Invalid sort_dir should default to 'desc'."""
        mock_repo.list.return_value = make_list_result()

        await service.list(tenant_id=tenant_id, sort_dir="invalid")

        call_args = mock_repo.list.call_args
        filters = call_args.args[1]
        assert filters.sort_dir == "desc"

    @pytest.mark.asyncio
    async def test_repo_error_propagates(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        mock_repo.list.side_effect = RuntimeError("timeout")

        with pytest.raises(RuntimeError, match="timeout"):
            await service.list(tenant_id=tenant_id)
```

## Audit Logging Verification

```python
class TestAuditLogging:
    """Verify audit entries contain correct fields for compliance."""

    @pytest.mark.asyncio
    async def test_create_audit_entry(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        mock_repo.create.return_value = None

        result = await service.create(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Audited Widget",
            description="desc",
        )

        mock_audit.write.assert_called_once()
        entry = mock_audit.write.call_args.args[0]
        assert entry.action == "widget.created"
        assert entry.tenant_id == tenant_id
        assert entry.actor_id == user_id
        assert entry.entity_id == result.id
        assert entry.timestamp is not None

    @pytest.mark.asyncio
    async def test_update_audit_entry(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = True

        await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            widget_id=existing.id,
            name="Updated",
            description="desc",
            version=1,
        )

        mock_audit.write.assert_called_once()
        entry = mock_audit.write.call_args.args[0]
        assert entry.action == "widget.updated"
        assert entry.tenant_id == tenant_id
        assert entry.actor_id == user_id

    @pytest.mark.asyncio
    async def test_delete_audit_entry(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        widget_id = uuid.uuid4()
        mock_repo.soft_delete.return_value = True

        await service.delete(tenant_id=tenant_id, widget_id=widget_id)

        mock_audit.write.assert_called_once()
        entry = mock_audit.write.call_args.args[0]
        assert entry.action == "widget.deleted"
        assert entry.entity_id == widget_id

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_block_operation(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Audit log failures are logged but MUST NOT fail the business operation."""
        mock_repo.create.return_value = None
        mock_audit.write.side_effect = ConnectionError("audit service down")

        # Should NOT raise — audit failure is fire-and-forget
        result = await service.create(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Widget",
            description="desc",
        )

        assert result.name == "Widget"
```

## Edge Case and Isolation Tests

```python
class TestEdgeCases:
    """Edge cases: missing context, tenant isolation, cancelled context."""

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Update MUST invalidate the cache before returning."""
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = True

        await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            widget_id=existing.id,
            name="Updated",
            description="desc",
            version=1,
        )

        cache_key = f"widget:{tenant_id}:{existing.id}"
        mock_cache.delete.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_delete(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
    ) -> None:
        """Delete MUST invalidate the cache."""
        widget_id = uuid.uuid4()
        mock_repo.soft_delete.return_value = True

        await service.delete(tenant_id=tenant_id, widget_id=widget_id)

        cache_key = f"widget:{tenant_id}:{widget_id}"
        mock_cache.delete.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_description_defaults_to_empty(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Omitting description should default to empty string."""
        mock_repo.create.return_value = None

        result = await service.create(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Widget",
        )

        assert result.description == ""

    @pytest.mark.asyncio
    async def test_whitespace_name_rejected(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Names that are only whitespace must be rejected."""
        with pytest.raises(ValidationError):
            await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name="   \t\n  ",
                description="desc",
            )

        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_sets_correct_audit_fields(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Verify created_by, updated_by, tenant_id are set from caller context."""
        mock_repo.create.return_value = None

        result = await service.create(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Widget",
            description="desc",
        )

        assert result.created_by == user_id
        assert result.updated_by == user_id
        assert result.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_update_increments_version(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Update must increment the version number by 1."""
        existing = make_widget(tenant_id=tenant_id, version=5)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = True

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            widget_id=existing.id,
            name="Updated",
            description="desc",
            version=5,
        )

        assert result.version == 6

    @pytest.mark.asyncio
    async def test_update_sets_updated_by(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Update must set updated_by to the current user."""
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = True

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            widget_id=existing.id,
            name="Updated",
            description="desc",
            version=1,
        )

        assert result.updated_by == user_id
```

## Transaction Rollback Tests

```python
class TestTransactionRollback:
    """Verify that errors during multi-step operations cause full rollback."""

    @pytest.mark.asyncio
    async def test_repo_failure_prevents_audit(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_audit: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """If repo.create fails, audit log should NOT be written."""
        mock_repo.create.side_effect = RuntimeError("db error")

        with pytest.raises(RuntimeError):
            await service.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name="Widget",
                description="desc",
            )

        mock_audit.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_repo_failure_prevents_cache_invalidation(
        self,
        service: WidgetService,
        mock_repo: AsyncMock,
        mock_cache: AsyncMock,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """If repo.update raises, cache should NOT be invalidated."""
        existing = make_widget(tenant_id=tenant_id, version=1)
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.side_effect = RuntimeError("db timeout")

        with pytest.raises(RuntimeError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                widget_id=existing.id,
                name="Updated",
                description="desc",
                version=1,
            )

        mock_cache.delete.assert_not_called()
```

## Critical Rules

- Every test MUST use fresh mocks per test via fixtures — never share mock state
- `AsyncMock(spec=...)` or `AsyncMock()` with explicit method setup — spec ensures typo detection
- Audit tests MUST verify: action, entity_id, tenant_id, actor_id, and timestamp
- Cache-aside tests MUST verify both hit and miss paths
- Cache tests MUST verify invalidation on Update and Delete
- Cache failures MUST be swallowed — assert that business operation completes
- Audit failures MUST be swallowed — assert that business operation completes
- Version conflict test: set existing.version = 3, input version = 1 — assert ConflictError
- Validation MUST happen before any side effects (DB, cache, audit)
- Use `pytest.raises` for expected exceptions, always checking `.code` or `.http_status`
- Use `pytest.mark.parametrize` for table-driven tests with descriptive `ids`
- Use `assert_not_called()` to verify methods that should NOT be invoked
- Use `call_args.args[0]` or `call_args.kwargs` to inspect what was passed to mocks
- Every async test MUST use `@pytest.mark.asyncio`
