"""harness: the app-level names testing/pytest.md's tests leave to the reader — the ids they use and small
in-memory implementations of the crud-service archetype's WidgetRepository / Cache / AuditWriter
protocols, so the REAL WidgetService runs under the doc's tests. Also SomeModel/some_model, the doc's
placeholders in the rollback test (the crud-repository archetype's WidgetModel)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.base import ListFilters, ListResult
from app.domain.widget import Widget
from app.models.widget import WidgetModel as SomeModel

TID = UUID("00000000-0000-0000-0000-0000000000a1")
UID = UUID("00000000-0000-0000-0000-0000000000b1")
WID = UUID("00000000-0000-0000-0000-0000000000c1")
MISSING_ID = UUID("00000000-0000-0000-0000-0000000000d1")

_now = datetime.now(timezone.utc)
some_model = SomeModel(id=uuid4(), tenant_id=TID, name="rollback-me", description="", status="active",
                       created_at=_now, updated_at=_now, created_by=UID, updated_by=UID, version=1)


class InMemoryWidgetRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Widget] = {}

    async def create(self, widget: Widget) -> None:
        self.rows[widget.id] = replace(widget)

    async def get_by_id(self, tenant_id: UUID, widget_id: UUID) -> Widget | None:
        w = self.rows.get(widget_id)
        return replace(w) if w is not None and w.tenant_id == tenant_id and w.deleted_at is None else None

    async def update(self, widget: Widget) -> bool:
        current = self.rows.get(widget.id)
        if current is None or current.version != widget.version - 1:
            return False
        self.rows[widget.id] = replace(widget)
        return True

    async def soft_delete(self, tenant_id: UUID, widget_id: UUID) -> bool:
        w = self.rows.get(widget_id)
        if w is None or w.tenant_id != tenant_id:
            return False
        self.rows[widget_id] = replace(w, deleted_at=datetime.now(timezone.utc))
        return True

    async def list(self, tenant_id: UUID, filters: ListFilters) -> ListResult[Widget]:
        items = [w for w in self.rows.values() if w.tenant_id == tenant_id and w.deleted_at is None]
        return ListResult(items=items[: filters.page_size], has_more=len(items) > filters.page_size)


class InMemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)


class InMemoryAudit:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def write(self, entry: Any) -> None:
        self.entries.append(entry)
