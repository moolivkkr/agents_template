"""harness (--live): uses testing/pytest.md's database fixtures against PostgreSQL 16 — the per-test
rollback session, and the repository wired to the session factory."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.widget import Widget
from app.models.widget import WidgetModel
from harness_stubs.pytest_pack import TID, UID


async def test_harness_session_sees_its_own_writes(session) -> None:
    now = datetime.now(timezone.utc)
    session.add(WidgetModel(id=uuid4(), tenant_id=TID, name="in-tx", description="", status="active",
                            created_at=now, updated_at=now, created_by=UID, updated_by=UID, version=1))
    await session.flush()
    assert await session.scalar(select(func.count()).select_from(WidgetModel)) == 1


async def test_harness_previous_test_was_rolled_back(session_factory) -> None:
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(WidgetModel)) == 0


async def test_harness_repository_through_the_factory(widget_repo) -> None:
    now = datetime.now(timezone.utc)
    w = Widget(id=uuid4(), tenant_id=TID, name="via-repo", created_at=now, updated_at=now, created_by=UID,
               updated_by=UID)
    await widget_repo.create(w)
    got = await widget_repo.get_by_id(TID, w.id)
    assert got is not None and got.name == "via-repo"


async def test_harness_repository_table_was_emptied(session_factory) -> None:
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(WidgetModel)) == 0
