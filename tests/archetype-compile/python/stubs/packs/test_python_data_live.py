"""harness (--live): languages/python.md's data blocks against PostgreSQL 16 — the doc's pytest fixtures
(postgres, db_session, user_factory), BaseRepository's keyset pages and soft delete, the service
transaction, the pooled engine, the async Alembic env (upgrade, downgrade, upgrade) and the asyncpg
context manager."""
import importlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.orders import OrderService
from app.pg import ping
from app.repository import BaseRepository
from harness_stubs.py_data import CreateOrderRequest, InsufficientStock, Note, Order, OrderRepository, Stock, User


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_user_factory_writes_through_db_session(db_session: AsyncSession, user_factory) -> None:
    user = await user_factory(name="Ada")
    assert (await db_session.get(User, user.id)).name == "Ada"


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_keyset_pages_have_no_gaps_or_repeats_even_on_tied_timestamps(db_session: AsyncSession) -> None:
    tenant, other = uuid4(), uuid4()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    notes = [Note(tenant_id=tenant, created_at=t0 + timedelta(seconds=i // 3)) for i in range(10)]  # ties
    db_session.add_all([*notes, Note(tenant_id=other, created_at=t0)])
    await db_session.flush()
    repo = BaseRepository(db_session, Note)
    seen, cursor = [], None
    while True:
        rows, cursor = await repo.find_paginated(tenant, cursor=cursor, limit=4)
        seen += [r.id for r in rows]
        if cursor is None:
            break
    assert sorted(seen) == sorted(n.id for n in notes) and len(seen) == len(set(seen))
    first, second = notes[0].id, notes[1].id
    await repo.soft_delete(tenant, first)
    db_session.expire_all()
    assert await repo.find_by_id(tenant, first) is None
    assert await repo.find_by_id(other, second) is None  # another tenant's id


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_service_transaction_commits_or_rolls_back_as_one(db_session: AsyncSession) -> None:
    tenant = uuid4()
    async with db_session.begin():
        db_session.add(Stock(sku=f"W-{tenant.hex[:6]}", on_hand=5))
    sku = f"W-{tenant.hex[:6]}"
    svc = OrderService(db_session, OrderRepository(db_session))
    order = await svc.create_order(tenant, CreateOrderRequest(sku=sku, quantity=3))
    assert svc.audit == [(tenant, "order.created", order.id)]
    with pytest.raises(InsufficientStock):
        await svc.create_order(tenant, CreateOrderRequest(sku=sku, quantity=3))  # only 2 left
    count = await db_session.scalar(select(func.count()).select_from(Order).where(Order.tenant_id == tenant))
    assert count == 1  # the second order rolled back with the stock update
    assert (await db_session.get(Stock, sku)).on_hand == 2


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_pooled_engine_from_the_environment(postgres, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres.get_connection_url(driver="asyncpg"))
    import app.engine

    engine = importlib.reload(app.engine).engine
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT 1"))).scalar() == 1
    assert engine.pool.size() == 20
    await engine.dispose()


def test_async_alembic_env_upgrade_downgrade_upgrade(postgres, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres.get_connection_url(driver="asyncpg"))
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_alembic_created_the_table(postgres) -> None:
    conn = await asyncpg.connect(postgres.get_connection_url(driver=None))
    try:
        assert await conn.fetchval("SELECT to_regclass('harness_migrated')") == "harness_migrated"
        assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0001"
    finally:
        await conn.close()


@pytest.mark.asyncio  # strict mode, as languages/python.md's own async tests
async def test_managed_connection(postgres) -> None:
    pool = await asyncpg.create_pool(postgres.get_connection_url(driver=None), min_size=1, max_size=2)
    try:
        await ping(pool)
        assert pool.get_idle_size() == pool.get_size()  # released back to the pool
    finally:
        await pool.close()
