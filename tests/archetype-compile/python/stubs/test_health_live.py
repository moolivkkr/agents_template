"""harness-only (--live): dockerfile-python.md's /readyz against a real PostgreSQL and the
migration-pattern-python.md revisions — not ready before or between migrations, ready at this release's
head and at a revision it doesn't ship (a newer release migrated first)."""
import asyncio

import asyncpg
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.api.health as health


async def _set_revision(pg_url: str, revision: str) -> None:
    conn = await asyncpg.connect(pg_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute("UPDATE alembic_version SET version_num = $1", revision)
    finally:
        await conn.close()


def test_readyz_follows_the_schema(pg_url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_url)
    app = FastAPI()
    app.include_router(health.router)
    health.configure_health(async_sessionmaker(create_async_engine(pg_url, poolclass=NullPool)))

    with TestClient(app) as c:
        assert c.get("/readyz").json() == {"status": "schema_not_ready"}  # never migrated
        command.upgrade(cfg, "b2c3d4e5f6a7")
        r = c.get("/readyz")
        assert r.status_code == 503 and r.json() == {"status": "schema_not_ready"}  # behind this release
        command.upgrade(cfg, "head")
        r = c.get("/readyz")
        assert r.status_code == 200 and r.json() == {"status": "ready"}, r.text
        asyncio.run(_set_revision(pg_url, "ffffffffffff"))  # a revision this release doesn't ship
        assert c.get("/readyz").status_code == 200
        asyncio.run(_set_revision(pg_url, "d4e5f6a7b8c9"))
        command.downgrade(cfg, "base")
