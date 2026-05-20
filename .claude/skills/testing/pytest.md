---
skill: pytest
description: Pytest skill pack — fixtures, parametrize, async tests, mocking, database fixtures with testcontainers, coverage, assertion patterns for Python 3.11+
version: "1.0"
tags:
  - python
  - pytest
  - testing
  - asyncio
  - testcontainers
---

# Pytest Patterns

## Fixtures — Scoping and Composition

```python
import pytest
from uuid import uuid4

# Function scope (default) — fresh per test. Use for mutable state.
@pytest.fixture
def tenant_id():
    return uuid4()

# Module scope — shared across all tests in the file. Use for expensive read-only setup.
@pytest.fixture(scope="module")
def api_client():
    from httpx import AsyncClient
    from app.main import create_app
    app = create_app()
    return AsyncClient(app=app, base_url="http://test")

# Session scope — shared across the entire test run. Use for DB containers.
@pytest.fixture(scope="session")
def pg_container():
    from testcontainers.postgres import PostgresContainer
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

# Autouse — runs automatically for every test in scope without importing.
@pytest.fixture(autouse=True)
def reset_request_context():
    from app.middleware.request_id import request_id_ctx
    token = request_id_ctx.set("test-request-id")
    yield
    request_id_ctx.reset(token)
```

- Use `function` scope (default) for anything mutable or test-specific
- Use `module` scope for expensive read-only resources shared across a file
- Use `session` scope for containers, engine creation, or one-time global setup
- Use `autouse=True` sparingly — only for universal setup like context vars or logging

## Parametrize — Table-Driven Tests

```python
import pytest

@pytest.mark.parametrize(
    "name, description, expected_error",
    [
        ("Valid Widget", "A description", None),
        ("", "A description", "name is required"),
        ("x" * 256, "desc", "name must be 255 characters or fewer"),
        ("Widget", "x" * 2001, "description must be 2000 characters or fewer"),
    ],
    ids=["valid", "empty_name", "name_too_long", "desc_too_long"],
)
async def test_create_validation(svc, name, description, expected_error):
    if expected_error is None:
        result = await svc.create(tenant_id=TID, user_id=UID, name=name, description=description)
        assert result.name == name
    else:
        with pytest.raises(ValidationError, match=expected_error):
            await svc.create(tenant_id=TID, user_id=UID, name=name, description=description)
```

- Always provide `ids` for readable test output: `test_create_validation[empty_name] FAILED`
- Parametrize replaces Go table-driven tests — each row becomes a subtest

## Async Test Patterns (pytest-asyncio)

```python
# pyproject.toml
# [tool.pytest.ini_options]
# asyncio_mode = "auto"  # auto-detect async tests — no @pytest.mark.asyncio needed

import pytest

# With asyncio_mode = "auto", just write async def:
async def test_get_widget(widget_service, sample_widget):
    result = await widget_service.get(tenant_id=sample_widget.tenant_id, widget_id=sample_widget.id)
    assert result.id == sample_widget.id
    assert result.name == sample_widget.name

# Async fixture:
@pytest.fixture
async def sample_widget(widget_service, tenant_id, user_id):
    return await widget_service.create(
        tenant_id=tenant_id, user_id=user_id, name="Test Widget", description="For testing"
    )

# Testing async generators / context managers:
async def test_transaction_rollback(session_factory):
    from app.db.transaction import transaction

    with pytest.raises(ValueError):
        async with transaction(session_factory) as session:
            session.add(some_model)
            raise ValueError("force rollback")

    # Verify nothing was committed
    async with session_factory() as session:
        result = await session.execute(select(SomeModel))
        assert result.scalar_one_or_none() is None
```

## Mocking with unittest.mock and pytest-mock

```python
from unittest.mock import AsyncMock, MagicMock, patch

# pytest-mock's mocker fixture — auto-cleanup after each test
async def test_create_calls_repo(mocker):
    mock_repo = mocker.AsyncMock(spec=WidgetRepository)
    mock_cache = mocker.AsyncMock(spec=Cache)
    mock_audit = mocker.AsyncMock(spec=AuditWriter)

    svc = WidgetService(repo=mock_repo, cache=mock_cache, audit_writer=mock_audit)
    await svc.create(tenant_id=TID, user_id=UID, name="Widget", description="")

    mock_repo.create.assert_called_once()
    created = mock_repo.create.call_args[0][0]
    assert created.name == "Widget"
    assert created.tenant_id == TID

# Mock a specific return value
async def test_get_returns_cached(mocker):
    mock_cache = mocker.AsyncMock(spec=Cache)
    mock_cache.get.return_value = b'{"id": "...", "name": "Cached"}'

    svc = WidgetService(repo=mocker.AsyncMock(), cache=mock_cache, audit_writer=mocker.AsyncMock())
    result = await svc.get(tenant_id=TID, widget_id=WID)
    assert result.name == "Cached"

# Mock side effects for error paths
async def test_create_handles_duplicate(mocker):
    mock_repo = mocker.AsyncMock(spec=WidgetRepository)
    mock_repo.create.side_effect = ConflictError(resource="widget", reason="duplicate")

    svc = WidgetService(repo=mock_repo, cache=mocker.AsyncMock(), audit_writer=mocker.AsyncMock())
    with pytest.raises(ConflictError, match="duplicate"):
        await svc.create(tenant_id=TID, user_id=UID, name="Dup")

# Patching module-level functions
async def test_with_patched_time(mocker):
    mocker.patch("app.services.widget.datetime", wraps=datetime)
    # or use freezegun:
    # from freezegun import freeze_time
    # @freeze_time("2024-01-15T10:00:00")
```

## Database Fixtures with Testcontainers

```python
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

@pytest.fixture(scope="session")
def pg_container():
    """Spin up a real PostgreSQL container for integration tests."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def pg_url(pg_container):
    """Async connection URL for the test database."""
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://test:test@{host}:{port}/test"

@pytest.fixture(scope="session")
async def engine(pg_url):
    """Create the async engine and run migrations."""
    eng = create_async_engine(pg_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()

@pytest.fixture
async def session(engine) -> AsyncSession:
    """Per-test session with automatic rollback — each test gets a clean slate."""
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()

@pytest.fixture
def widget_repo(session):
    """Repository wired to the test session."""
    return WidgetRepository(session_factory=lambda: session)
```

## Coverage Configuration

```toml
# pyproject.toml

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",                      # show summary of all non-passing tests
]
markers = [
    "integration: requires database container",
    "slow: tests that take > 5 seconds",
]

[tool.coverage.run]
source = ["app"]
branch = true
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@overload",
]
```

Run: `pytest --cov=app --cov-report=term-missing --cov-report=html`

## Assertion Patterns

```python
import pytest
from app.errors import AppError, NotFoundError, ConflictError, ValidationError

# Exact match
assert result.name == "Expected"

# Collection checks
assert len(result.items) == 5
assert widget in result.items
assert all(w.tenant_id == TID for w in result.items)

# Error type + message pattern
with pytest.raises(NotFoundError, match="widget.*not found"):
    await svc.get(tenant_id=TID, widget_id=MISSING_ID)

# Error attribute inspection
with pytest.raises(ConflictError) as exc_info:
    await svc.update(tenant_id=TID, widget_id=WID, version=0, name="New")
assert exc_info.value.code == "CONFLICT"
assert exc_info.value.http_status == 409
assert exc_info.value.details["resource"] == "widget"

# isinstance checks for error hierarchy
with pytest.raises(AppError) as exc_info:
    await svc.create(tenant_id=TID, user_id=UID, name="")
assert isinstance(exc_info.value, ValidationError)

# Approximate comparisons (floats, timestamps)
from pytest import approx
assert result.score == approx(0.95, rel=1e-2)

# Checking that no exception is raised (explicit is better than implicit)
result = await svc.create(tenant_id=TID, user_id=UID, name="Valid")
assert result is not None
```

## Critical Rules

- Use `asyncio_mode = "auto"` in pyproject.toml — no need for `@pytest.mark.asyncio` on every test
- Use `scope="session"` for testcontainers — spinning up a container per test is too slow
- Use per-test session rollback for database isolation — each test gets a clean slate
- Use `mocker.AsyncMock(spec=Protocol)` to enforce interface contracts in mocks
- Use `pytest.raises(ErrorType, match=...)` for error assertions — check both type and message
- Use `ids` in `@pytest.mark.parametrize` for readable test output
- Set `fail_under = 80` in coverage config — enforce minimum coverage in CI
- Mark slow tests with `@pytest.mark.slow` so they can be skipped in local dev: `pytest -m "not slow"`
- Mark integration tests with `@pytest.mark.integration` for selective CI runs
