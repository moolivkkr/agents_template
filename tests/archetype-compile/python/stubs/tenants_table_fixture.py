

# ── harness-only (appended to the repository conftest for the migrations unit) ──────────────────────
# The seed migration reads the project's `tenants` table, which the migration samples don't create
# (a real project already has it). Create it once so the upgrade/downgrade round trips can run.
import asyncio as _harness_asyncio

import asyncpg as _harness_asyncpg


@pytest.fixture(scope="session", autouse=True)
def _harness_tenants_table(pg_url: str) -> None:
    async def _create() -> None:
        conn = await _harness_asyncpg.connect(pg_url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            await conn.execute("CREATE TABLE IF NOT EXISTS tenants (id uuid PRIMARY KEY)")
            await conn.execute("INSERT INTO tenants (id) VALUES (gen_random_uuid())")
        finally:
            await conn.close()

    _harness_asyncio.run(_create())
