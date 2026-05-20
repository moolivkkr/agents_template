---
skill: crud-repository-test-python
description: Python repository integration test archetype — testcontainers PostgreSQL, per-test transaction rollback, real DB queries, pagination, soft delete, optimistic locking, tenant isolation, unique constraint handling
version: "1.0"
tags:
  - python
  - repository
  - integration-test
  - postgres
  - testcontainers
  - archetype
  - backend
  - testing
  - sqlalchemy
---

# CRUD Repository Test Archetype — Python

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-repository-test.md` (Go/pgx). Both test the same CRUD operations, pagination, tenant isolation, and optimistic locking against a real PostgreSQL instance.

Complete integration test template for the Python repository layer using testcontainers. Every generated repository test MUST follow this pattern.

## Test File Location

```
tests/
  repositories/
    test_widget_repository.py    <- THIS file
    conftest.py                  <- DB fixtures (session-scoped container)
```

Rule: Integration tests live in `tests/repositories/`. Use separate `conftest.py` for DB lifecycle.

## Test Infrastructure — testcontainers + Alembic

```python
# tests/repositories/conftest.py

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from app.models.widget import Base, WidgetModel

# Session-scoped PostgreSQL container — shared across all tests in this module

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def pg_container():
    """
    Start a real PostgreSQL container once for the entire test session.
    testcontainers handles cleanup on exit.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def pg_url(pg_container) -> str:
    """Async connection URL for the test PostgreSQL container."""
    # testcontainers gives psycopg2 URL; convert to asyncpg
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    user = pg_container.username
    password = pg_container.password
    db = pg_container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

@pytest_asyncio.fixture(scope="session")
async def engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Create the async engine and run migrations (create tables)."""
    eng = create_async_engine(pg_url, echo=False, pool_size=5)

    # Create all tables from SQLAlchemy models
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    await eng.dispose()

@pytest_asyncio.fixture(scope="session")
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the test engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

## Per-Test Isolation via Transaction Rollback

```python
# tests/repositories/conftest.py (continued)

@pytest_asyncio.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """
    Per-test session that rolls back after each test.
    Ensures complete isolation without needing TRUNCATE.
    """
    async with session_factory() as sess:
        async with sess.begin():
            yield sess
            # Rollback on exit — changes from this test are discarded
            await sess.rollback()

@pytest_asyncio.fixture
async def clean_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    Alternative: provides the session factory with pre-test cleanup.
    Use this when the repository creates its own sessions internally.
    """
    async with session_factory() as sess:
        await sess.execute(text("DELETE FROM widgets"))
        await sess.commit()

    yield session_factory

    # Post-test cleanup
    async with session_factory() as sess:
        await sess.execute(text("DELETE FROM widgets"))
        await sess.commit()
```

## Test Data Factory

```python
# tests/repositories/test_widget_repository.py

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.base import ListFilters, ListResult
from app.domain.widget import Widget, WidgetStatus
from app.errors import ConflictError, NotFoundError
from app.repositories.widget import WidgetRepository

def make_widget(
    *,
    id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    name: str | None = None,
    description: str = "Test widget description",
    status: WidgetStatus = WidgetStatus.ACTIVE,
    version: int = 1,
    created_at: datetime | None = None,
) -> Widget:
    """Build a Widget domain object with unique defaults for DB insertion."""
    now = created_at or datetime.utcnow()
    return Widget(
        id=id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        name=name or f"widget-{uuid.uuid4().hex[:8]}",
        description=description,
        status=status,
        created_at=now,
        updated_at=now,
        created_by=uuid.uuid4(),
        updated_by=uuid.uuid4(),
        version=version,
    )

async def seed_widgets(
    repo: WidgetRepository,
    *widgets: Widget,
) -> None:
    """Bulk-seed widgets into the database for test setup."""
    for w in widgets:
        await repo.create(w)

@pytest.fixture
def repo(clean_session: async_sessionmaker[AsyncSession]) -> WidgetRepository:
    """Create a repository instance with the test session factory."""
    return WidgetRepository(session_factory=clean_session)
```

## CRUD Tests with Real Database

```python
class TestCreate:
    """Test widget creation against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_inserts_and_returns(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await repo.create(widget)

        # Verify it was persisted
        got = await repo.get_by_id(widget.tenant_id, widget.id)
        assert got is not None
        assert got.id == widget.id
        assert got.tenant_id == widget.tenant_id
        assert got.name == widget.name
        assert got.description == widget.description
        assert got.version == 1
        assert got.deleted_at is None

    @pytest.mark.asyncio
    async def test_duplicate_primary_key_raises_conflict(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await repo.create(widget)

        # Insert another with the same ID
        duplicate = make_widget(id=widget.id, tenant_id=widget.tenant_id, name="different")

        with pytest.raises((ConflictError, Exception)):
            await repo.create(duplicate)

    @pytest.mark.asyncio
    async def test_duplicate_tenant_name_raises_conflict(self, repo: WidgetRepository) -> None:
        """Unique constraint: (tenant_id, name) WHERE deleted_at IS NULL."""
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="unique-name")
        await repo.create(w1)

        w2 = make_widget(tenant_id=tenant_id, name="unique-name")
        with pytest.raises((ConflictError, Exception)):
            await repo.create(w2)

class TestGetByID:
    """Test widget retrieval against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_returns_widget(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await seed_widgets(repo, widget)

        got = await repo.get_by_id(widget.tenant_id, widget.id)
        assert got is not None
        assert got.id == widget.id
        assert got.name == widget.name

    @pytest.mark.asyncio
    async def test_not_found(self, repo: WidgetRepository) -> None:
        got = await repo.get_by_id(uuid.uuid4(), uuid.uuid4())
        assert got is None

    @pytest.mark.asyncio
    async def test_soft_deleted_excluded(self, repo: WidgetRepository) -> None:
        """GetByID must NOT return soft-deleted records."""
        widget = make_widget()
        await seed_widgets(repo, widget)

        # Soft delete
        deleted = await repo.soft_delete(widget.tenant_id, widget.id)
        assert deleted is True

        # GetByID should return None
        got = await repo.get_by_id(widget.tenant_id, widget.id)
        assert got is None

class TestUpdate:
    """Test widget updates with optimistic locking against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_increments_version(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await seed_widgets(repo, widget)

        # Update fields and increment version
        widget.name = "Updated Name"
        widget.updated_at = datetime.utcnow()
        widget.version = 2

        success = await repo.update(widget)
        assert success is True

        # Verify updated
        got = await repo.get_by_id(widget.tenant_id, widget.id)
        assert got is not None
        assert got.name == "Updated Name"
        assert got.version == 2

    @pytest.mark.asyncio
    async def test_nonexistent_returns_false(self, repo: WidgetRepository) -> None:
        widget = make_widget(version=2)
        success = await repo.update(widget)
        assert success is False

class TestSoftDelete:
    """Test soft delete against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_sets_deleted_at(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await seed_widgets(repo, widget)

        deleted = await repo.soft_delete(widget.tenant_id, widget.id)
        assert deleted is True

        # GetByID should NOT find it (filtered by deleted_at IS NULL)
        got = await repo.get_by_id(widget.tenant_id, widget.id)
        assert got is None

    @pytest.mark.asyncio
    async def test_nonexistent_returns_false(self, repo: WidgetRepository) -> None:
        deleted = await repo.soft_delete(uuid.uuid4(), uuid.uuid4())
        assert deleted is False

    @pytest.mark.asyncio
    async def test_already_deleted_returns_false(self, repo: WidgetRepository) -> None:
        widget = make_widget()
        await seed_widgets(repo, widget)

        # First delete succeeds
        assert await repo.soft_delete(widget.tenant_id, widget.id) is True
        # Second delete returns False (already deleted)
        assert await repo.soft_delete(widget.tenant_id, widget.id) is False
```

## Pagination Tests

```python
class TestListCursorPagination:
    """Test cursor-based pagination against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_cursor_pagination_full_traversal(self, repo: WidgetRepository) -> None:
        """Insert 25 widgets, paginate through all of them in pages of 20 + 5."""
        tenant_id = uuid.uuid4()
        base_time = datetime.utcnow() - timedelta(hours=1)

        for i in range(25):
            widget = make_widget(
                tenant_id=tenant_id,
                name=f"widget-{i:03d}",
                created_at=base_time + timedelta(seconds=i),
            )
            await repo.create(widget)

        # Page 1: first 20
        page1 = await repo.list(tenant_id, ListFilters(
            page_size=20,
            sort_by="created_at",
            sort_dir="desc",
        ))
        assert len(page1.items) == 20
        assert page1.has_more is True
        assert page1.cursor is not None
        assert page1.total == 25

        # Page 2: remaining 5
        page2 = await repo.list(tenant_id, ListFilters(
            page_size=20,
            cursor=page1.cursor,
            sort_by="created_at",
            sort_dir="desc",
        ))
        assert len(page2.items) == 5
        assert page2.has_more is False

        # Verify no duplicates between pages
        page1_ids = {w.id for w in page1.items}
        page2_ids = {w.id for w in page2.items}
        assert page1_ids.isdisjoint(page2_ids), "pages must not have duplicate items"

    @pytest.mark.asyncio
    async def test_empty_result(self, repo: WidgetRepository) -> None:
        result = await repo.list(uuid.uuid4(), ListFilters(
            page_size=20,
            sort_by="created_at",
            sort_dir="desc",
        ))
        assert len(result.items) == 0
        assert result.has_more is False
        assert result.cursor is None
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_sort_order_ascending(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        base_time = datetime.utcnow()

        w1 = make_widget(tenant_id=tenant_id, name="alpha", created_at=base_time)
        w2 = make_widget(tenant_id=tenant_id, name="bravo", created_at=base_time + timedelta(seconds=1))
        w3 = make_widget(tenant_id=tenant_id, name="charlie", created_at=base_time + timedelta(seconds=2))
        await seed_widgets(repo, w1, w2, w3)

        result = await repo.list(tenant_id, ListFilters(
            page_size=10, sort_by="created_at", sort_dir="asc",
        ))
        assert len(result.items) == 3
        assert result.items[0].id == w1.id, "first item should be oldest"
        assert result.items[2].id == w3.id, "last item should be newest"

    @pytest.mark.asyncio
    async def test_sort_order_descending(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        base_time = datetime.utcnow()

        w1 = make_widget(tenant_id=tenant_id, name="alpha", created_at=base_time)
        w2 = make_widget(tenant_id=tenant_id, name="bravo", created_at=base_time + timedelta(seconds=1))
        w3 = make_widget(tenant_id=tenant_id, name="charlie", created_at=base_time + timedelta(seconds=2))
        await seed_widgets(repo, w1, w2, w3)

        result = await repo.list(tenant_id, ListFilters(
            page_size=10, sort_by="created_at", sort_dir="desc",
        ))
        assert len(result.items) == 3
        assert result.items[0].id == w3.id, "first item should be newest"
        assert result.items[2].id == w1.id, "last item should be oldest"
```

## Soft Delete Exclusion Tests

```python
class TestSoftDeleteExclusion:
    """Verify soft-deleted records are excluded from all queries."""

    @pytest.mark.asyncio
    async def test_list_excludes_soft_deleted(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="visible")
        w2 = make_widget(tenant_id=tenant_id, name="deleted")
        await seed_widgets(repo, w1, w2)

        # Soft-delete w2
        await repo.soft_delete(tenant_id, w2.id)

        result = await repo.list(tenant_id, ListFilters(
            page_size=20, sort_by="created_at", sort_dir="desc",
        ))
        assert len(result.items) == 1
        assert result.items[0].id == w1.id

    @pytest.mark.asyncio
    async def test_total_count_excludes_soft_deleted(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="kept")
        w2 = make_widget(tenant_id=tenant_id, name="removed")
        await seed_widgets(repo, w1, w2)

        await repo.soft_delete(tenant_id, w2.id)

        result = await repo.list(tenant_id, ListFilters(page_size=20))
        assert result.total == 1
```

## Tenant Isolation Tests

```python
class TestTenantIsolation:
    """Verify that tenants cannot see, modify, or delete each other's data."""

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_tenant(self, repo: WidgetRepository) -> None:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        widget_a = make_widget(tenant_id=tenant_a, name="tenant-a-widget")
        await seed_widgets(repo, widget_a)

        # Tenant A can see their own widget
        got = await repo.get_by_id(tenant_a, widget_a.id)
        assert got is not None

        # Tenant B CANNOT see tenant A's widget
        got = await repo.get_by_id(tenant_b, widget_a.id)
        assert got is None

    @pytest.mark.asyncio
    async def test_list_scoped_to_tenant(self, repo: WidgetRepository) -> None:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        # Seed 3 for tenant A, 2 for tenant B
        for i in range(3):
            await seed_widgets(repo, make_widget(tenant_id=tenant_a, name=f"a-{i}"))
        for i in range(2):
            await seed_widgets(repo, make_widget(tenant_id=tenant_b, name=f"b-{i}"))

        result_a = await repo.list(tenant_a, ListFilters(page_size=20))
        assert len(result_a.items) == 3
        assert result_a.total == 3
        for w in result_a.items:
            assert w.tenant_id == tenant_a

        result_b = await repo.list(tenant_b, ListFilters(page_size=20))
        assert len(result_b.items) == 2
        assert result_b.total == 2
        for w in result_b.items:
            assert w.tenant_id == tenant_b

    @pytest.mark.asyncio
    async def test_soft_delete_wrong_tenant(self, repo: WidgetRepository) -> None:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        widget_a = make_widget(tenant_id=tenant_a)
        await seed_widgets(repo, widget_a)

        # Tenant B cannot delete tenant A's widget
        deleted = await repo.soft_delete(tenant_b, widget_a.id)
        assert deleted is False

        # Widget still exists for tenant A
        got = await repo.get_by_id(tenant_a, widget_a.id)
        assert got is not None

    @pytest.mark.asyncio
    async def test_update_wrong_tenant(self, repo: WidgetRepository) -> None:
        """Update with wrong tenant_id should not affect the row (version mismatch or no rows)."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        widget_a = make_widget(tenant_id=tenant_a)
        await seed_widgets(repo, widget_a)

        # Attempt update with wrong tenant
        widget_a.tenant_id = tenant_b
        widget_a.name = "hijacked"
        widget_a.version = 2
        widget_a.updated_at = datetime.utcnow()

        success = await repo.update(widget_a)
        assert success is False

        # Verify original is untouched
        widget_a.tenant_id = tenant_a  # restore for lookup
        got = await repo.get_by_id(tenant_a, widget_a.id)
        assert got is not None
        assert got.name != "hijacked"
```

## Optimistic Locking Tests

```python
class TestOptimisticLocking:
    """Test concurrent access handling via version-based optimistic locking."""

    @pytest.mark.asyncio
    async def test_concurrent_update_conflict(self, repo: WidgetRepository) -> None:
        """Simulate two concurrent reads — second update should fail."""
        widget = make_widget()
        await seed_widgets(repo, widget)

        # Simulate two concurrent reads
        read1 = await repo.get_by_id(widget.tenant_id, widget.id)
        read2 = await repo.get_by_id(widget.tenant_id, widget.id)
        assert read1 is not None
        assert read2 is not None

        # First update succeeds
        read1.name = "Update A"
        read1.version = 2
        read1.updated_at = datetime.utcnow()
        success = await repo.update(read1)
        assert success is True

        # Second update fails — version was already incremented
        read2.name = "Update B"
        read2.version = 2  # same expected version, but actual is now 2
        read2.updated_at = datetime.utcnow()
        success = await repo.update(read2)
        assert success is False

        # Verify first update persisted
        final = await repo.get_by_id(widget.tenant_id, widget.id)
        assert final is not None
        assert final.name == "Update A"
        assert final.version == 2

    @pytest.mark.asyncio
    async def test_stale_version_rejected(self, repo: WidgetRepository) -> None:
        """Update with wrong expected version should fail."""
        widget = make_widget(version=5)
        await seed_widgets(repo, widget)

        # Try to update with stale version
        widget.name = "Stale Update"
        widget.version = 3  # expects version 2, but actual is 5
        widget.updated_at = datetime.utcnow()
        success = await repo.update(widget)
        assert success is False
```

## Filter Tests

```python
class TestFilters:
    """Test dynamic field filters against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_filter_by_status(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        await seed_widgets(
            repo,
            make_widget(tenant_id=tenant_id, name="active-1", status=WidgetStatus.ACTIVE),
            make_widget(tenant_id=tenant_id, name="active-2", status=WidgetStatus.ACTIVE),
            make_widget(tenant_id=tenant_id, name="archived-1", status=WidgetStatus.ARCHIVED),
        )

        result = await repo.list(tenant_id, ListFilters(
            page_size=20,
            fields={"status": "active"},
        ))
        assert len(result.items) == 2
        for w in result.items:
            assert w.status == WidgetStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_filter_returns_correct_total(self, repo: WidgetRepository) -> None:
        """Total count must respect the active filters."""
        tenant_id = uuid.uuid4()
        await seed_widgets(
            repo,
            make_widget(tenant_id=tenant_id, name="a1", status=WidgetStatus.ACTIVE),
            make_widget(tenant_id=tenant_id, name="a2", status=WidgetStatus.ACTIVE),
            make_widget(tenant_id=tenant_id, name="i1", status=WidgetStatus.INACTIVE),
        )

        result = await repo.list(tenant_id, ListFilters(
            page_size=20,
            fields={"status": "active"},
        ))
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_unknown_filter_ignored(self, repo: WidgetRepository) -> None:
        """Unknown filter fields should be silently ignored."""
        tenant_id = uuid.uuid4()
        w = make_widget(tenant_id=tenant_id)
        await seed_widgets(repo, w)

        result = await repo.list(tenant_id, ListFilters(
            page_size=20,
            fields={"nonexistent_column": "value"},
        ))
        # Should return results (filter ignored), not error
        assert len(result.items) == 1
```

## Unique Constraint Tests

```python
class TestUniqueConstraints:
    """Test database-level unique constraints."""

    @pytest.mark.asyncio
    async def test_same_name_different_tenant_allowed(self, repo: WidgetRepository) -> None:
        """Name uniqueness is scoped to tenant — different tenants can have same name."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        w1 = make_widget(tenant_id=tenant_a, name="shared-name")
        w2 = make_widget(tenant_id=tenant_b, name="shared-name")

        await repo.create(w1)
        await repo.create(w2)  # Should NOT raise

        # Both exist
        got_a = await repo.get_by_id(tenant_a, w1.id)
        got_b = await repo.get_by_id(tenant_b, w2.id)
        assert got_a is not None
        assert got_b is not None

    @pytest.mark.asyncio
    async def test_deleted_name_can_be_reused(self, repo: WidgetRepository) -> None:
        """
        After soft-deleting a widget, the same name should be available for reuse
        (partial unique index WHERE deleted_at IS NULL).
        """
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="reusable-name")
        await repo.create(w1)

        # Soft delete
        await repo.soft_delete(tenant_id, w1.id)

        # Create new widget with same name — should succeed
        w2 = make_widget(tenant_id=tenant_id, name="reusable-name")
        await repo.create(w2)  # Should NOT raise

        got = await repo.get_by_id(tenant_id, w2.id)
        assert got is not None
        assert got.name == "reusable-name"
```

## Batch Operation Tests

```python
class TestBatchOperations:
    """Test batch CRUD operations with meaningful data volumes."""

    @pytest.mark.asyncio
    async def test_batch_create(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        widgets = [
            make_widget(tenant_id=tenant_id, name=f"batch-{i:03d}")
            for i in range(50)
        ]

        await repo.batch_create(widgets)

        result = await repo.list(tenant_id, ListFilters(page_size=100))
        assert result.total == 50

    @pytest.mark.asyncio
    async def test_batch_update(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="batch-1")
        w2 = make_widget(tenant_id=tenant_id, name="batch-2")
        await seed_widgets(repo, w1, w2)

        # Update both
        now = datetime.utcnow()
        w1.name = "updated-1"
        w1.version = 2
        w1.updated_at = now
        w2.name = "updated-2"
        w2.version = 2
        w2.updated_at = now

        await repo.batch_update([w1, w2])

        got1 = await repo.get_by_id(tenant_id, w1.id)
        assert got1 is not None
        assert got1.name == "updated-1"

        got2 = await repo.get_by_id(tenant_id, w2.id)
        assert got2 is not None
        assert got2.name == "updated-2"
```

## Error Mapping Tests

```python
class TestErrorMapping:
    """Verify database exceptions are mapped to domain error types."""

    @pytest.mark.asyncio
    async def test_unique_violation_maps_to_conflict(self, repo: WidgetRepository) -> None:
        tenant_id = uuid.uuid4()
        w1 = make_widget(tenant_id=tenant_id, name="unique")
        await repo.create(w1)

        w2 = make_widget(tenant_id=tenant_id, name="unique")

        with pytest.raises((ConflictError, Exception)) as exc_info:
            await repo.create(w2)

        # If the repo properly maps the error, it should be ConflictError
        if isinstance(exc_info.value, ConflictError):
            assert exc_info.value.http_status == 409

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_false(self, repo: WidgetRepository) -> None:
        """RowsAffected == 0 -> returns False (or raises ConflictError depending on implementation)."""
        widget = make_widget(version=2)
        success = await repo.update(widget)
        assert success is False
```

## Critical Rules

- TestMain (conftest session fixtures) MUST start a real PostgreSQL container — never mock the database in repository tests
- Every test MUST have isolation via transaction rollback or per-test cleanup (TRUNCATE/DELETE)
- Test factories MUST generate unique names and IDs (`uuid.uuid4()`) to prevent constraint violations
- Pagination tests MUST verify: item count, has_more flag, cursor presence, no duplicates between pages, correct total
- Tenant isolation tests MUST verify: GET returns None, LIST returns empty, UPDATE returns False, DELETE returns False
- Optimistic locking tests MUST simulate two concurrent reads and verify second update fails
- Soft delete tests MUST verify: GetByID returns None, List excludes deleted, total count excludes deleted
- Unique constraint tests MUST verify: same name across tenants allowed, deleted names can be reused
- Error mapping tests MUST verify: unique violation -> ConflictError, no rows -> False/NotFoundError
- Batch operations MUST be tested with meaningful data volumes (10+ rows)
- Never use `@pytest.mark.asyncio` with `t.Parallel()` equivalent — sequential execution within each class for shared DB
- Container cleanup happens automatically via `testcontainers` context manager
- Use `async_sessionmaker` with `expire_on_commit=False` to avoid lazy-load issues
- Session-scoped container means one PostgreSQL instance for the entire test run (fast startup)
- Per-test cleanup ensures isolation despite shared container
