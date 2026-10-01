# testing/pytest.md "Assertion Patterns": the fragment runs against the REAL crud-service WidgetService
# (in-memory protocol implementations): NotFoundError for a missing id, ConflictError with code/status/
# retryable for a stale version, ValidationFailedError with details for an empty name, then a create.
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.domain.widget import Widget
from app.services.widget import WidgetService
from docs_fragments.assertions import _fragment
from harness_stubs.pytest_pack import TID, UID, WID, InMemoryAudit, InMemoryCache, InMemoryWidgetRepository

now = datetime.now(timezone.utc)
repo = InMemoryWidgetRepository()
stored = Widget(id=WID, tenant_id=TID, name="existing", created_at=now, updated_at=now, created_by=UID,
                updated_by=UID)
repo.rows[WID] = stored
svc = WidgetService(repo=repo, cache=InMemoryCache(), audit_writer=InMemoryAudit())
items = [stored, *[replace(stored, id=uuid4()) for _ in range(4)]]
result = SimpleNamespace(name="Expected", items=items, score=0.951)
asyncio.run(_fragment(svc, result, stored))
