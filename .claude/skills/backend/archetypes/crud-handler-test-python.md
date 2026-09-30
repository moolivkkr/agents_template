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

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/crud-handler-test-go.md` (Go/chi). Both test the same response envelope (`~/.claude/skills/api/response-envelope.md`), error codes, and pagination behavior.

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
    """httpx AsyncClient wired to the test app — no real HTTP server needed.

    raise_app_exceptions=False: Starlette re-raises an unhandled exception after the catch-all
    handler has sent its 500 envelope; without this flag httpx raises it and the 500 can't be asserted.
    """
    transport = ASGITransport(app=app_with_overrides, raise_app_exceptions=False)
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
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, Response

from app.domain.base import ListResult
from app.domain.widget import Widget
from app.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    UnauthenticatedError,
    UnavailableError,
    ValidationFailedError,
)
from tests.conftest import DEFAULT_TENANT_ID, DEFAULT_USER_ID
from tests.factories import make_widget


# ---------------------------------------------------------------------------
# Helper assertions — the shapes are ~/.claude/skills/api/response-envelope.md
# ---------------------------------------------------------------------------

def assert_envelope(body: dict) -> Any:
    """Assert the success envelope: exactly data + meta, meta.request_id, no error key. Returns data."""
    assert set(body) == {"data", "meta"}, f"expected exactly 'data' and 'meta': {body}"
    assert body["meta"]["request_id"]
    return body["data"]


def assert_error_envelope(resp: Response, expected_status: int, expected_code: str) -> dict:
    """Assert the status/code pair and the error envelope. Returns the error object."""
    assert resp.status_code == expected_status, resp.text
    body = resp.json()
    assert set(body) == {"error"}, f"an error body has only the 'error' key (no 'data'): {body}"
    err = body["error"]
    assert err["code"] == expected_code, f"expected code '{expected_code}', got '{err['code']}'"
    assert err["message"]
    assert err["request_id"]
    assert err["request_id"] == resp.headers["x-request-id"]
    assert isinstance(err["retryable"], bool)
    assert "detail" not in err, "no technical detail field"
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

        # Pydantic catches min_length=1 -> 400 VALIDATION_FAILED (the handlers replace FastAPI's 422)
        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"] == [
            {"field": "name", "code": "string_too_short", "message": "This value is too short."}
        ]
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_error_missing_name(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Missing required field -> 400 VALIDATION_FAILED."""
        resp = await client.post(
            "/api/v1/widgets/",
            json={"description": "desc"},
        )

        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"][0]["field"] == "name"
        assert err["details"][0]["code"] == "missing"
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_json(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Invalid JSON body -> 400 MALFORMED_REQUEST (not a validation error)."""
        resp = await client.post(
            "/api/v1/widgets/",
            content=b"{invalid json",
            headers={"content-type": "application/json"},
        )

        assert_error_envelope(resp, 400, "MALFORMED_REQUEST")
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_body(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Empty body -> 400 MALFORMED_REQUEST."""
        resp = await client.post(
            "/api/v1/widgets/",
            content=b"",
            headers={"content-type": "application/json"},
        )

        assert_error_envelope(resp, 400, "MALFORMED_REQUEST")
        mock_service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_validation_error(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Service-level validation error -> 400 VALIDATION_FAILED."""
        mock_service.create.side_effect = ValidationFailedError("name", "required", "Name is required.")

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "X", "description": "desc"},
        )

        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"] == [{"field": "name", "code": "required", "message": "Name is required."}]

    @pytest.mark.asyncio
    async def test_service_conflict_error(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Duplicate name -> 409 Conflict."""
        mock_service.create.side_effect = ConflictError("A widget with this name already exists.")

        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "Duplicate", "description": "desc"},
        )

        assert_error_envelope(resp, 409, "CONFLICT")

    @pytest.mark.asyncio
    async def test_name_too_long(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Name exceeding max_length -> 400 VALIDATION_FAILED from Pydantic."""
        resp = await client.post(
            "/api/v1/widgets/",
            json={"name": "x" * 256, "description": "desc"},
        )

        assert_error_envelope(resp, 400, "VALIDATION_FAILED")
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
        mock_service.get.side_effect = NotFoundError("Widget")

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert_error_envelope(resp, 404, "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_uuid(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Invalid UUID path param -> 400 VALIDATION_FAILED from FastAPI path validation."""
        resp = await client.get("/api/v1/widgets/not-a-uuid")

        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"][0]["field"] == "widget_id"
        mock_service.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrong_tenant_returns_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Wrong tenant MUST see 404, not 403 — prevents entity enumeration."""
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError("Widget")

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert_error_envelope(resp, 404, "NOT_FOUND")
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
            "This widget was changed by someone else. Reload and try again.",
        )

        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 1},
        )

        assert_error_envelope(resp, 409, "CONFLICT")

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.update.side_effect = NotFoundError("Widget")

        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 1},
        )

        assert_error_envelope(resp, 404, "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_json(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            content=b"{bad",
            headers={"content-type": "application/json"},
        )

        assert_error_envelope(resp, 400, "MALFORMED_REQUEST")
        mock_service.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_version_field(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Version is required for optimistic locking."""
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc"},
        )

        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"][0]["field"] == "version"
        mock_service.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_version_must_be_positive(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """Version < 1 should be rejected by Pydantic ge=1 constraint."""
        widget_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/widgets/{widget_id}",
            json={"name": "Updated", "description": "desc", "version": 0},
        )

        assert_error_envelope(resp, 400, "VALIDATION_FAILED")
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
        mock_service.delete.side_effect = NotFoundError("Widget")

        resp = await client.delete(f"/api/v1/widgets/{widget_id}")

        assert_error_envelope(resp, 404, "NOT_FOUND")

    @pytest.mark.asyncio
    async def test_invalid_uuid(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.delete("/api/v1/widgets/xyz-not-uuid")

        assert_error_envelope(resp, 400, "VALIDATION_FAILED")
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

        resp = await client.get("/api/v1/widgets/?limit=3&sort_by=created_at&sort_dir=desc")

        assert resp.status_code == 200
        body = resp.json()

        # Assert data array
        data = assert_envelope(body)
        assert isinstance(data, list)
        assert len(data) == 3

        # Assert pagination meta: meta.pagination {next_cursor, has_more, limit}
        meta = body["meta"]
        assert meta["request_id"]
        assert meta["pagination"] == {"next_cursor": "next-cursor-token", "has_more": True, "limit": 3}

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
        assert body["data"] == [], "empty list is [] — never null"
        pagination = body["meta"]["pagination"]
        assert pagination["has_more"] is False
        assert pagination["next_cursor"] is None, "next_cursor is null when has_more is false"

    @pytest.mark.asyncio
    async def test_cursor_forwarded_to_service(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list.return_value = ListResult(
            items=[make_widget()],
            has_more=False,
            total=25,
        )

        resp = await client.get("/api/v1/widgets/?cursor=some-cursor-token&limit=10")

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        assert call_kwargs["cursor"] == "some-cursor-token"
        assert call_kwargs["limit"] == 10
        assert resp.json()["meta"]["pagination"]["has_more"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_string, expected_limit",
        [
            ("", 20),                 # default when missing
            ("limit=50", 50),         # respects valid size
            ("limit=100", 100),       # max allowed
        ],
        ids=["default", "valid-50", "max-100"],
    )
    async def test_limit_values(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        query_string: str,
        expected_limit: int,
    ) -> None:
        mock_service.list.return_value = ListResult(items=[], total=0)

        url = f"/api/v1/widgets/?{query_string}" if query_string else "/api/v1/widgets/"
        resp = await client.get(url)

        assert resp.status_code == 200
        call_kwargs = mock_service.list.call_args.kwargs
        assert call_kwargs["limit"] == expected_limit
        assert resp.json()["meta"]["pagination"]["limit"] == expected_limit

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_string",
        [
            "limit=0",
            "limit=-5",
            "limit=101",
        ],
        ids=["zero", "negative", "exceeds-max"],
    )
    async def test_limit_out_of_range(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        query_string: str,
    ) -> None:
        """limit outside [1, 100] -> 400 VALIDATION_FAILED from FastAPI Query(ge=1, le=100)."""
        resp = await client.get(f"/api/v1/widgets/?{query_string}")

        err = assert_error_envelope(resp, 400, "VALIDATION_FAILED")
        assert err["details"][0]["field"] == "limit"
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

        assert_error_envelope(resp, 400, "VALIDATION_FAILED")
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
                NotFoundError("Widget"),
                404,
                "NOT_FOUND",
            ),
            (
                ConflictError("This widget was changed by someone else. Reload and try again."),
                409,
                "CONFLICT",
            ),
            (
                ValidationFailedError("name", "required", "Name is required."),
                400,
                "VALIDATION_FAILED",
            ),
            (
                BusinessRuleError("Archived widgets can't be edited."),
                422,
                "BUSINESS_RULE_VIOLATION",
            ),
            (
                UnauthenticatedError(),
                401,
                "UNAUTHENTICATED",
            ),
            (
                UnavailableError("postgres", cause=TimeoutError("statement timeout")),
                503,
                "UNAVAILABLE",
            ),
        ],
        ids=["not-found-404", "conflict-409", "validation-400", "business-rule-422", "unauthenticated-401", "unavailable-503"],
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

        err = assert_error_envelope(resp, expected_status, expected_code)
        # Only a dependency failure is retryable, and it tells the client when to retry
        assert err["retryable"] is (expected_code == "UNAVAILABLE")
        if expected_status == 503:
            assert "retry-after" in resp.headers
        if expected_status == 401:
            assert resp.headers["www-authenticate"] == "Bearer"
        # The cause (e.g. "statement timeout", "postgres") never reaches the client
        assert "statement timeout" not in resp.text
        assert "postgres" not in resp.text

    @pytest.mark.asyncio
    async def test_internal_error_does_not_leak_details(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        """Internal errors MUST NOT leak error details to the client."""
        mock_service.get.side_effect = RuntimeError("database connection pool exhausted")

        widget_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        err = assert_error_envelope(resp, 500, "INTERNAL")
        # CRITICAL: the message must be generic — no internal details anywhere in the body
        assert err["message"] == "Something went wrong."
        assert "connection pool" not in resp.text
        assert "RuntimeError" not in resp.text
        assert "Traceback" not in resp.text
```

## Auth Tests

```python
class TestAuth:
    """Authentication and authorization tests."""

    @pytest.mark.asyncio
    async def test_missing_auth_token(self, mock_service: AsyncMock) -> None:
        """Request without Bearer token -> 401 UNAUTHENTICATED (HTTPBearer(auto_error=False) + the dependency)."""
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

        # No credentials is 401 UNAUTHENTICATED in the envelope — not FastAPI's {"detail": "Not authenticated"}
        assert_error_envelope(resp, 401, "UNAUTHENTICATED")
        assert resp.headers["www-authenticate"] == "Bearer"
        mock_service.get.assert_not_called()
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_wrong_tenant_sees_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        """
        CRITICAL: Wrong tenant sees 404, not 403 — prevents entity enumeration.
        The service layer returns NotFound (not Forbidden) for wrong-tenant access.
        """
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError("Widget")

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        assert_error_envelope(resp, 404, "NOT_FOUND")

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

        # meta carries only request_id (equal to the X-Request-Id header) — no pagination, no timestamp
        meta = body["meta"]
        assert set(meta) == {"request_id"}
        assert meta["request_id"] == resp.headers["x-request-id"]

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
        # Exactly "data" (array) and "meta" at the top level — no top-level pagination/links/total
        assert set(body) == {"data", "meta"}
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1

        meta = body["meta"]
        assert set(meta) == {"request_id", "pagination"}
        assert set(meta["pagination"]) == {"next_cursor", "has_more", "limit"}

    @pytest.mark.asyncio
    async def test_error_response_shape(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        widget_id = uuid.uuid4()
        mock_service.get.side_effect = NotFoundError("Widget")

        resp = await client.get(f"/api/v1/widgets/{widget_id}")

        body = resp.json()
        # Error envelope: {"error": {"code", "message", "details"?, "request_id", "retryable"}} — no "data"
        assert set(body) == {"error"}
        err = body["error"]
        assert {"code", "message", "request_id", "retryable"} <= set(err)
        assert "details" not in err, "details[] is for field-level problems only"

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
        mock_service.get.side_effect = NotFoundError("Widget")
        resp = await client.get(f"/api/v1/widgets/{uuid.uuid4()}")

        assert "application/json" in resp.headers.get("content-type", "")
```

## Critical Rules

- Every handler test MUST use `httpx.AsyncClient` with `ASGITransport(..., raise_app_exceptions=False)` — no real HTTP server needed for unit tests, and the catch-all 500 response stays assertable
- Dependency overrides MUST inject mock service and test user — mirrors production DI
- Pydantic request validation MUST return 400 `VALIDATION_FAILED` with `details[]` of `{field, code, message}` (not FastAPI's default 422); malformed JSON 400 `MALFORMED_REQUEST`; a domain rule 422 `BUSINESS_RULE_VIOLATION`
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Internal errors MUST NOT leak error details to the client — assert generic message in 500 responses
- Every response MUST follow `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}` for success, `{"error": {code, message, details?, request_id, retryable}}` for failure, never both
- Every error response MUST carry `request_id` equal to the `X-Request-Id` header, and `retryable`
- DELETE MUST return 204 with empty body
- POST create MUST return 201 Created
- List responses MUST include `meta.pagination` `{next_cursor, has_more, limit}`; `data` is `[]` when empty
- `limit` MUST be validated: `Query(ge=1, le=100)` — out of range returns 400 `VALIDATION_FAILED`
- Sort and filter fields MUST be allow-listed — disallowed values default to safe values
- Use `pytest.mark.asyncio` on every async test function
- Use `pytest.mark.parametrize` for table-driven tests (error mapping, `limit` bounds)
- Every test MUST use fresh `AsyncMock(spec=WidgetService)` — never share mock state between tests
- Always assert `mock_service.method.assert_not_called()` for methods that should NOT be invoked
- Fixtures MUST clean up `dependency_overrides` to prevent test pollution
