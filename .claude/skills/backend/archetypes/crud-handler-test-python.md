---
skill: crud-handler-test-python
description: Python FastAPI handler test archetype — pytest + httpx AsyncClient, dependency overrides, CRUD endpoint validation, pagination, auth, error mapping, parametrize table-driven tests
version: "1.0"
tags:
  - python
  - fastapi
  - handler
  - http
  - unit-test
  - archetype
  - backend
  - testing
---

# CRUD Handler Test Archetype — Python (FastAPI)

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-handler-test.md` (Go/chi). Both test the same response envelope, error codes, and pagination behavior.

Complete FastAPI handler test template using pytest + httpx. Every generated handler test file MUST follow this pattern.

## Test File Location

```
tests/
  api/
    v1/
      test_widgets.py       <- THIS file
  conftest.py               <- shared fixtures (app, client, auth)
  factories.py              <- test data builders
```

Rule: Test files live in a `tests/` tree mirroring the `app/` layout. Shared fixtures go in `conftest.py`.

## Shared Fixtures — conftest.py

```python
# tests/conftest.py

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import CurrentUser, get_current_user
from app.main import create_app
from app.services.widget import WidgetService


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

DEFAULT_TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEFAULT_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def make_user(
    *,
    user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    roles: list[str] | None = None,
) -> CurrentUser:
    """Build a CurrentUser with sensible defaults."""
    return CurrentUser(
        user_id=user_id or DEFAULT_USER_ID,
        tenant_id=tenant_id or DEFAULT_TENANT_ID,
        roles=roles or ["user"],
    )


# ---------------------------------------------------------------------------
# Application + Client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_service() -> AsyncMock:
    """Fresh AsyncMock for WidgetService — reset per test."""
    return AsyncMock(spec=WidgetService)


@pytest_asyncio.fixture
async def app_with_overrides(mock_service: AsyncMock):
    """
    Create a FastAPI app with dependency overrides:
    - WidgetService -> AsyncMock
    - get_current_user -> returns a default authenticated user
    """
    from app.api.v1.widgets import get_widget_service

    app = create_app()

    current_user = make_user()

    async def override_current_user() -> CurrentUser:
        return current_user

    async def override_service() -> WidgetService:
        return mock_service  # type: ignore[return-value]

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_widget_service] = override_service

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_with_overrides) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient wired to the test app — no real HTTP server needed."""
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

## Test Data Factories

```python
# tests/factories.py

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.widget import Widget, WidgetStatus


def make_widget(
    *,
    id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    name: str = "Test Widget",
    description: str = "A test widget",
    status: WidgetStatus = WidgetStatus.ACTIVE,
    version: int = 1,
    created_by: uuid.UUID | None = None,
    updated_by: uuid.UUID | None = None,
) -> Widget:
    """Build a Widget domain object with sensible defaults."""
    now = datetime.utcnow()
    return Widget(
        id=id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        name=name,
        description=description,
        status=status,
        created_at=now,
        updated_at=now,
        created_by=created_by or uuid.uuid4(),
        updated_by=updated_by or uuid.uuid4(),
        version=version,
    )
```

## Create Handler Tests

```python
# tests/api/v1/test_widgets.py

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.domain.base import ListResult
from app.domain.widget import Widget
from app.errors import ConflictError, NotFoundError, ValidationError
from tests.conftest import DEFAULT_TENANT_ID, DEFAULT_USER_ID
from tests.factories import make_widget


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def assert_envelope(body: dict, status: int = 200) -> dict:
    """Assert the standard success envelope shape and return data."""
    assert "data" in body, f"expected 'data' key in response: {body}"
    assert "meta" in body, f"expected 'meta' key in response: {body}"
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]
    return body["data"]


def assert_error_envelope(body: dict, expected_code: str) -> dict:
    """Assert the standard error envelope shape and return error detail."""
    assert "error" in body, f"expected 'error' key in response: {body}"
    err = body["error"]
    assert err["code"] == expected_code, f"expected code '{expected_code}', got '{err['code']}'"
    assert "message" in err
    return err


# ---------------------------------------------------------------------------
# CREATE — POST /api/v1/widgets/
# ---------------------------------------------------------------------------

class TestCreateWidget:
    """Tests for POST /api/v1/widgets/."""

    @pytest.mark.asyncio
    async def test_happy_path(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        created = make_widget(name="New Widget")
        mock_service.create.return_value = created

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "New Widget", "description": "A fine widget"},
        )

        assert resp.status_code == 201
        body = resp.json()
        data = assert_envelope(body)
        assert data["name"] == "New Widget"

        # Verify service was called with correct tenant/user from auth
        mock_service.create.assert_called_once()
        call_kwargs = mock_service.create.call_args.kwargs
        assert call_kwargs["tenant_id"] == DEFAULT_TENANT_ID
        assert call_kwargs["user_id"] == DEFAULT_USER_ID
        assert call_kwargs["name"] == "New Widget"

    @pytest.mark.asyncio
    async def test_validation_error_empty_name(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Empty name should be rejected by Pydantic before reaching the service."""
        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "", "description": "desc"},
        )

        # Pydantic catches min_length=1 -> 422
        assert resp.status_code == 422
        err = assert_error_envelope(resp.json(), "VALIDATION_ERROR")
        assert "fields" in err.get("details", {})
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_error_missing_name(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Missing required field -> 422."""
        resp = await client.post(
            "/api/v1/widgets/",
            json={"description": "desc"},
        )

        assert resp.status_code == 422
        assert_error_envelope(resp.json(), "VALIDATION_ERROR")
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_json(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Invalid JSON body -> 422 from FastAPI's request parser."""
        resp = await client.post(
            "/api/v1/widgets/",
            content=b"{invalid json",
            headers={"content-type": "application/json"},
        )

        assert resp.status_code == 422
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_body(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Empty body -> 422."""
        resp = await client.post(
            "/api/v1/widgets/",
            content=b"",
            headers={"content-type": "application/json"},
        )

        assert resp.status_code == 422
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_validation_error(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Service-level validation error -> 422."""
        mock_service.create.side_effect = ValidationError(field="name", reason="name is required")

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "X", "description": "desc"},
        )

        assert resp.status_code == 422
        assert_error_envelope(resp.json(), "VALIDATION_ERROR")

    @pytest.mark.asyncio
    async def test_service_conflict_error(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Duplicate name -> 409 Conflict."""
        mock_service.create.side_effect = ConflictError(
            resource="widget", reason="name already exists",
        )

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "Duplicate", "description": "desc"},
        )

        assert resp.status_code == 409
        assert_error_envelope(resp.json(), "CONFLICT")

    @pytest.mark.asyncio
    async def test_name_too_long(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Name exceeding max_length -> 422 from Pydantic."""
        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "x" * 256, "description": "desc"},
        )

        assert resp.status_code == 422
        assert_error_envelope(resp.json(), "VALIDATION_ERROR")
        mock_service.create.assert_not_called()
```

## Get Handler Tests

```python
class TestGetWidget:
    """Tests for GET /api/v1/widgets/{widget_id}."""

    @pytest.mark.asyncio
    async def test_happy_path(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget = make_widget()
        mock_service.get.return_value = widget

        resp = await client.get(f"/api/v1/widgets/{widget.id}")

        assert resp.status_code == 200
        data = assert_envelope(resp.json())
        assert data["id"] == str(widget.id)
        assert data["name"] == widget.name

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == 404
        assert_error_envelope(resp.json(), "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_uuid(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Invalid UUID path param -> 422 from FastAPI path validation."""
        resp = await client.get("/api/v1/widgets/not-a-uuid")

        assert resp.status_code == 422
        mock_service.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrong_tenant_returns_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Wrong tenant MUST see 404, not 403 — prevents entity enumeration."""
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == 404
        assert_error_envelope(resp.json(), "NOT_FOUND")
```

## Update Handler Tests

```python
class TestUpdateWidget:
    """Tests for PUT /api/v1/widgets/{widget_id}."""

    @pytest.mark.asyncio
    async def test_happy_path(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget = make_widget(name="Updated Name", version=2)
        mock_service.update.return_value = widget

        resp = await client.put(
            f"/api/v1/widgets/{widget.id}",
            json={"name": "Updated Name", "description": "Updated desc", "version": 1},
        )

        assert resp.status_code == 200
        data = assert_envelope(resp.json())
        assert data["name"] == "Updated Name"
        assert data["version"] == 2

        mock_service.update.assert_called_once()
        call_kwargs = mock_service.update.call_args.kwargs
        assert call_kwargs["version"] == 1
        assert call_kwargs["widget_id"] == widget.id

    @pytest.mark.asyncio
    async def test_version_conflict(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.update.side_effect = ConflictError(
            resource="widget", reason="version mismatch",
        )

        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 1},
        )

        assert resp.status_code == 409
        assert_error_envelope(resp.json(), "CONFLICT")

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.update.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 1},
        )

        assert resp.status_code == 404
        assert_error_envelope(resp.json(), "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_json(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            content=b"{bad",
            headers={"content-type": "application/json"},
        )

        assert resp.status_code == 422
        mock_service.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_version_field(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Version is required for optimistic locking."""
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc"},
        )

        assert resp.status_code == 422
        assert_error_envelope(resp.json(), "VALIDATION_ERROR")
        mock_service.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_version_must_be_positive(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Version < 1 should be rejected by Pydantic ge=1 constraint."""
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 0},
        )

        assert resp.status_code == 422
        mock_service.update.assert_not_called()
```

## Delete Handler Tests

```python
class TestDeleteWidget:
    """Tests for DELETE /api/v1/widgets/{widget_id}."""

    @pytest.mark.asyncio
    async def test_happy_path(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.delete.return_value = None

        resp = await client.delete(f"/api/v1/widgets/{widget_id}")

        # DELETE returns 204 No Content with empty body
        assert resp.status_code == 204
        assert resp.content == b""
        mock_service.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.delete.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.delete(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == 404
        assert_error_envelope(resp.json(), "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_uuid(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.delete("/api/v1/widgets/xyz-not-uuid")

        assert resp.status_code == 422
        mock_service.delete.assert_not_called()
```

## List Handler with Pagination Tests

```python
class TestListWidgets:
    """Tests for GET /api/v1/widgets/."""

    @pytest.mark.asyncio
    async def test_happy_path(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widgets = [make_widget() for _ in range(3)]
        mock_service.list.return_value = ListResult(
            items=widgets,
            cursor="next-cursor-token",
            has_more=True,
            total=25,
        )

        resp = await client.get("/api/v1/widgets/?page_size=3&sort_by=created_at&sort_dir=desc")

        assert resp.status_code == 200
        body = resp.json()

        # Assert data array
        data = body["data"]
        assert isinstance(data, list)
        assert len(data) == 3

        # Assert pagination meta
        meta = body["meta"]
        assert meta["cursor"] == "next-cursor-token"
        assert meta["has_more"] is True
        assert meta["total"] == 25
        assert "request_id" in meta
        assert "timestamp" in meta

    @pytest.mark.asyncio
    async def test_empty_results(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = ListResult(
            items=[],
            has_more=False,
            total=0,
        )

        resp = await client.get("/api/v1/widgets/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["has_more"] is False
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_cursor_forwarded_to_service(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = ListResult(
            items=[make_widget()],
            has_more=False,
            total=25,
        )

        resp = await client.get("/api/v1/widgets/?cursor=some-cursor-token&page_size=10")

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        assert call_kwargs["cursor"] == "some-cursor-token"
        assert call_kwargs["page_size"] == 10

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_string, expected_page_size",
        [
            ("", 20),                     # default when missing
            ("page_size=50", 50),         # respects valid size
            ("page_size=100", 100),       # max allowed
        ],
        ids=["default", "valid-50", "max-100"],
    )
    async def test_page_size_values(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        query_string: str,
        expected_page_size: int,
    ) -> None:
        mock_service.list.return_value = ListResult(items=[], total=0)

        url = f"/api/v1/widgets/?{query_string}" if query_string else "/api/v1/widgets/"
        resp = await client.get(url)

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        assert call_kwargs["page_size"] == expected_page_size

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_string",
        [
            "page_size=0",
            "page_size=-5",
            "page_size=101",
        ],
        ids=["zero", "negative", "exceeds-max"],
    )
    async def test_page_size_out_of_range(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        query_string: str,
    ) -> None:
        """page_size outside [1, 100] -> 422 from FastAPI Query(ge=1, le=100)."""
        resp = await client.get(f"/api/v1/widgets/?{query_string}")

        assert resp.status_code == 422
        mock_service.list.assert_not_called()

    @pytest.mark.asyncio
    async def test_filter_params_forwarded(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Allowed filter[field] params should be forwarded to the service."""
        mock_service.list.return_value = ListResult(items=[], total=0)

        resp = await client.get(
            "/api/v1/widgets/?filter[status]=active&filter[priority]=high"
        )

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        assert call_kwargs["field_filters"]["status"] == "active"
        assert call_kwargs["field_filters"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_disallowed_filter_ignored(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Disallowed filter fields should be silently ignored."""
        mock_service.list.return_value = ListResult(items=[], total=0)

        resp = await client.get("/api/v1/widgets/?filter[password]=secret")

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        field_filters = call_kwargs.get("field_filters", {})
        assert "password" not in field_filters

    @pytest.mark.asyncio
    async def test_sort_validation_defaults(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Unknown sort_by should default to 'created_at', invalid sort_dir defaults to 'desc'."""
        mock_service.list.return_value = ListResult(items=[], total=0)

        resp = await client.get("/api/v1/widgets/?sort_by=drop_table")

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        # Handler should have defaulted to "created_at" (allow-listed)
        assert call_kwargs["sort_by"] == "created_at"

    @pytest.mark.asyncio
    async def test_sort_dir_validation(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Invalid sort_dir should be rejected by regex pattern."""
        resp = await client.get("/api/v1/widgets/?sort_dir=invalid")

        assert resp.status_code == 422
        mock_service.list.assert_not_called()
```

## Error Mapping Tests (Parametrized Table-Driven)

```python
class TestErrorMapping:
    """Verify that service-layer errors map to correct HTTP status codes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "service_error, expected_status, expected_code",
        [
            (
                NotFoundError(resource="widget", identifier="123"),
                404,
                "NOT_FOUND",
            ),
            (
                ConflictError(resource="widget", reason="version mismatch"),
                409,
                "CONFLICT",
            ),
            (
                ValidationError(field="name", reason="required"),
                422,
                "VALIDATION_ERROR",
            ),
        ],
        ids=["not-found-404", "conflict-409", "validation-422"],
    )
    async def test_error_mapping(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        service_error: Exception,
        expected_status: int,
        expected_code: str,
    ) -> None:
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = service_error

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == expected_status
        assert_error_envelope(resp.json(), expected_code)

    @pytest.mark.asyncio
    async def test_internal_error_does_not_leak_details(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        """Internal errors MUST NOT leak error details to the client."""
        mock_service.get.side_effect = RuntimeError("database connection pool exhausted")

        widget_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == 500
        body = resp.json()
        err = body["error"]
        assert err["code"] == "INTERNAL_ERROR"
        # CRITICAL: the message must be generic — no internal details
        assert "database" not in err["message"].lower()
        assert "connection pool" not in err["message"].lower()
        assert err["message"] == "an unexpected error occurred"
```

## Auth Tests

```python
class TestAuth:
    """Authentication and authorization tests."""

    @pytest.mark.asyncio
    async def test_missing_auth_token(self, mock_service: AsyncMock) -> None:
        """Request without Bearer token -> 403 (HTTPBearer returns 403 by default)."""
        from app.api.v1.widgets import get_widget_service
        from app.main import create_app

        app = create_app()

        # Override only the service, NOT the auth dependency
        async def override_service() -> WidgetService:
            return mock_service  # type: ignore[return-value]

        app.dependency_overrides[get_widget_service] = override_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/widgets/{uuid.uuid4()}")

        # FastAPI's HTTPBearer returns 403 when no credentials are provided
        assert resp.status_code == 403
        mock_service.get.assert_not_called()
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_wrong_tenant_sees_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """
        CRITICAL: Wrong tenant sees 404, not 403 — prevents entity enumeration.
        The service layer returns NotFound (not Forbidden) for wrong-tenant access.
        """
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert resp.status_code == 404
        assert_error_envelope(resp.json(), "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_admin_role_access(self, mock_service: AsyncMock) -> None:
        """Verify role-protected endpoints accept users with the required role."""
        from app.api.v1.widgets import get_widget_service
        from app.main import create_app

        app = create_app()

        admin_user = make_user(roles=["admin"])

        async def override_admin():
            return admin_user

        async def override_service():
            return mock_service

        app.dependency_overrides[get_current_user] = override_admin
        app.dependency_overrides[get_widget_service] = override_service

        mock_service.list.return_value = ListResult(items=[], total=0)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/widgets/")

        assert resp.status_code == 200
        app.dependency_overrides.clear()
```

## Response Shape Tests

```python
class TestResponseShape:
    """Verify response envelope structure matches the contract."""

    @pytest.mark.asyncio
    async def test_single_resource_shape(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget = make_widget()
        mock_service.get.return_value = widget

        resp = await client.get(f"/api/v1/widgets/{widget.id}")

        body = resp.json()
        # Must have exactly "data" and "meta" top-level keys
        assert set(body.keys()) == {"data", "meta"}

        # data must contain expected widget fields
        data = body["data"]
        for field in ("id", "tenant_id", "name", "version", "created_at", "updated_at"):
            assert field in data, f"missing field '{field}' in data"

        # meta must contain request tracking fields
        meta = body["meta"]
        assert "request_id" in meta
        assert "timestamp" in meta

    @pytest.mark.asyncio
    async def test_list_resource_shape(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = ListResult(
            items=[make_widget()],
            cursor="abc",
            has_more=True,
            total=10,
        )

        resp = await client.get("/api/v1/widgets/")

        body = resp.json()
        # Must have "data" (array) and "meta" top-level keys
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1

        meta = body["meta"]
        for field in ("cursor", "has_more", "total", "request_id", "timestamp"):
            assert field in meta, f"missing field '{field}' in meta"

    @pytest.mark.asyncio
    async def test_error_response_shape(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError(resource="widget", identifier=str(widget_id))

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        body = resp.json()
        # Error envelope: {"error": {"code": "...", "message": "..."}}
        assert "error" in body
        err = body["error"]
        assert "code" in err
        assert "message" in err

    @pytest.mark.asyncio
    async def test_create_returns_201(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.create.return_value = make_widget()

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "Widget", "description": "desc"},
        )

        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_delete_returns_204_empty_body(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.delete.return_value = None

        resp = await client.delete(f"/api/v1/widgets/{uuid.uuid4()}")

        assert resp.status_code == 204
        assert resp.content == b""
```

## Content-Type Tests

```python
class TestContentType:
    """Verify response content types are correct."""

    @pytest.mark.asyncio
    async def test_json_content_type(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.get.return_value = make_widget()
        resp = await client.get(f"/api/v1/widgets/{uuid.uuid4()}")

        assert "application/json" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_error_content_type(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.get.side_effect = NotFoundError(resource="widget", identifier="x")
        resp = await client.get(f"/api/v1/widgets/{uuid.uuid4()}")

        assert "application/json" in resp.headers.get("content-type", "")
```

## Critical Rules

- Every handler test MUST use `httpx.AsyncClient` with `ASGITransport` — no real HTTP server needed for unit tests
- Dependency overrides MUST inject mock service and test user — mirrors production DI
- Pydantic validation errors return 422 with `VALIDATION_ERROR` code and field details
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Internal errors MUST NOT leak error details to the client — assert generic message in 500 responses
- Every response MUST follow the envelope format: `{"data": T, "meta": {...}}` for success, `{"error": {...}}` for failure
- DELETE MUST return 204 with empty body
- POST create MUST return 201 Created
- List responses MUST include `cursor`, `has_more`, `total` in meta
- Page size MUST be validated: `Query(ge=1, le=100)` — out-of-range returns 422
- Sort and filter fields MUST be allow-listed — disallowed values default to safe values
- Use `pytest.mark.asyncio` on every async test function
- Use `pytest.mark.parametrize` for table-driven tests (error mapping, page size limits)
- Every test MUST use fresh `AsyncMock(spec=WidgetService)` — never share mock state between tests
- Always assert `mock_service.method.assert_not_called()` for methods that should NOT be invoked
- Fixtures MUST clean up `dependency_overrides` to prevent test pollution
