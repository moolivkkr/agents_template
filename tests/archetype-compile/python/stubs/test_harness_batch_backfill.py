

# ── harness-only (--live): the doc's batch backfill, which the harness makes revision e5f6a7b8c9d0 ──
def test_harness_batch_backfill_moves_rows(alembic_config: Config, owner_url: str) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "b2c3d4e5f6a7")
    tenant = uuid.uuid4()
    asyncio.run(insert_widgets(owner_url, [tenant]))           # the tenant exists before the seed
    command.upgrade(alembic_config, "d4e5f6a7b8c9")            # seed + single-UPDATE backfill
    asyncio.run(insert_widgets(owner_url, [tenant, tenant]))   # two new widgets, no category yet
    assert asyncio.run(tenant_state(owner_url, tenant))[1] == 2
    command.upgrade(alembic_config, "e5f6a7b8c9d0")            # the batch backfill (DO block, COMMITs)
    assert asyncio.run(tenant_state(owner_url, tenant))[1] == 0
    with pytest.raises(asyncpg.exceptions.UndefinedObjectError):  # FORCE is back on
        asyncio.run(count_widgets_without_tenant(owner_url))
