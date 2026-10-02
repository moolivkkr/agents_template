

# ── harness-only (--live): the doc's batch backfill, which the harness makes revision e5f6a7b8c9d0 ──
# Proves the lock claims in "Who runs migrations" with pg_locks: a batch paused inside its UPDATE holds
# ROW EXCLUSIVE (no ACCESS EXCLUSIVE) on widgets while the application reads and writes; the replaced
# design's ALTER TABLE ... NO FORCE holds ACCESS EXCLUSIVE and the application's query times out.
import threading
import time

PAUSE_KEY = 4242
# Pauses every UPDATE of a widget until the test releases the advisory lock: the batch stops mid-UPDATE.
PAUSE_TRIGGER = """
    CREATE FUNCTION harness_pause() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN PERFORM pg_advisory_xact_lock_shared(4242); RETURN NEW; END $$;
    CREATE TRIGGER harness_pause BEFORE UPDATE ON widgets FOR EACH ROW EXECUTE FUNCTION harness_pause();
"""
DROP_PAUSE = "DROP TRIGGER IF EXISTS harness_pause ON widgets; DROP FUNCTION IF EXISTS harness_pause();"
MIGRATOR_WAITING_ON = """
    SELECT pid FROM pg_stat_activity
    WHERE usename = 'app_migrator' AND wait_event_type = 'Lock' AND wait_event = $1
"""
WIDGET_LOCKS = """
    SELECT mode FROM pg_locks
    WHERE pid = $1 AND locktype = 'relation' AND relation = 'widgets'::regclass AND granted
"""


def _admin_url(pg_url: str) -> str:
    """The superuser, on the migrations database (to install the pause trigger and read pg_locks)."""
    return _plain(make_url(pg_url).set(database="migrations_test").render_as_string(hide_password=False))


async def _app_read_write(url: str, tenant: uuid.UUID, timeout_ms: int) -> int:
    """The application's read and write of widgets, each refused if it waits timeout_ms for a lock."""
    conn = await asyncpg.connect(_plain(url))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant))
            await conn.execute(f"SET LOCAL lock_timeout = '{timeout_ms}ms'")
            before = await conn.fetchval("SELECT count(*) FROM widgets")
            await conn.execute(
                "INSERT INTO widgets (tenant_id, name, created_by, updated_by) VALUES ($1, $2, $3, $3)",
                tenant, f"during-batch-{uuid.uuid4().hex[:8]}", uuid.uuid4(),
            )
            return before
    finally:
        await conn.close()


async def _waiting_migrator(admin: asyncpg.Connection, wait_event: str) -> int:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        pid = await admin.fetchval(MIGRATOR_WAITING_ON, wait_event)
        if pid is not None:
            return pid
        await asyncio.sleep(0.05)
    raise AssertionError(f"the migration never waited on a {wait_event} lock")


def _in_thread(alembic_config: Config, revision: str, errors: list[BaseException]) -> threading.Thread:
    def migrate() -> None:
        try:
            command.upgrade(alembic_config, revision)
        except BaseException as exc:  # reported by the test, not lost in the thread
            errors.append(exc)

    return threading.Thread(target=migrate, daemon=True)


def _schema_with_uncategorized_widgets(alembic_config: Config, db_roles: DbRoles, count: int) -> uuid.UUID:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "d4e5f6a7b8c9")  # seed + single-UPDATE backfill
    tenant = uuid.uuid4()
    asyncio.run(provision(db_roles.runtime_url, tenant))
    for _ in range(count):  # created after the backfill: no category yet
        asyncio.run(insert_widget(db_roles.runtime_url, tenant))
    assert asyncio.run(uncategorized(db_roles.runtime_url, tenant)) == count
    return tenant


def _join(batch: threading.Thread, errors: list[BaseException]) -> None:
    if batch.ident is not None:
        batch.join(60)
    assert not batch.is_alive(), "the batch backfill did not finish"
    assert not errors, errors


def test_harness_batch_backfill_takes_no_table_lock(alembic_config: Config, db_roles: DbRoles, pg_url: str) -> None:
    tenant = _schema_with_uncategorized_widgets(alembic_config, db_roles, 3)
    errors: list[BaseException] = []
    batch = _in_thread(alembic_config, "e5f6a7b8c9d0", errors)

    async def while_paused() -> tuple[set[str], int]:
        admin = await asyncpg.connect(_admin_url(pg_url))
        try:
            await admin.execute(PAUSE_TRIGGER)
            await admin.execute("SELECT pg_advisory_lock($1)", PAUSE_KEY)
            batch.start()
            pid = await _waiting_migrator(admin, "advisory")  # paused inside the batch's UPDATE
            modes = {r["mode"] for r in await admin.fetch(WIDGET_LOCKS, pid)}
            seen = await _app_read_write(db_roles.runtime_url, tenant, timeout_ms=200)
            await admin.execute("SELECT pg_advisory_unlock($1)", PAUSE_KEY)
            return modes, seen
        finally:
            await admin.close()  # also releases the advisory lock if an assertion failed above

    async def drop_pause() -> None:
        admin = await asyncpg.connect(_admin_url(pg_url))
        try:
            await admin.execute(DROP_PAUSE)
        finally:
            await admin.close()

    try:
        modes, seen = asyncio.run(while_paused())
        _join(batch, errors)
    finally:
        asyncio.run(drop_pause())
    print(f"locks on widgets held by a paused batch: {sorted(modes)}")
    assert "RowExclusiveLock" in modes and "AccessExclusiveLock" not in modes, modes
    assert seen == 3  # the application read (and then wrote) while the batch was open
    # the widget the application added during the batch was picked up by a later batch
    assert asyncio.run(uncategorized(db_roles.runtime_url, tenant)) == 0


def test_harness_batch_waits_for_a_locked_row_and_rechecks_it(alembic_config: Config, db_roles: DbRoles, pg_url: str) -> None:
    tenant = _schema_with_uncategorized_widgets(alembic_config, db_roles, 2)
    errors: list[BaseException] = []
    batch = _in_thread(alembic_config, "e5f6a7b8c9d0", errors)

    async def app_categorizes_during_batch() -> tuple[object, object]:
        app = await asyncpg.connect(_plain(db_roles.runtime_url))
        admin = await asyncpg.connect(_admin_url(pg_url))
        try:
            tx = app.transaction()
            await tx.start()
            await app.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant))
            target = await app.fetchval("SELECT id FROM widgets WHERE category_id IS NULL LIMIT 1")
            customer = await app.fetchval("SELECT id FROM widget_categories WHERE slug = 'customer'")
            await app.execute("UPDATE widgets SET category_id = $1 WHERE id = $2", customer, target)
            batch.start()
            await _waiting_migrator(admin, "transactionid")  # the batch waits for the app's row lock
            await tx.commit()
            return target, customer
        finally:
            await app.close()
            await admin.close()

    target, customer = asyncio.run(app_categorizes_during_batch())
    _join(batch, errors)
    rows = asyncio.run(as_tenant(db_roles.runtime_url, tenant, "SELECT category_id FROM widgets WHERE id = $1", target))
    assert rows == [(customer,)], "the batch overwrote the category the application set"
    assert asyncio.run(uncategorized(db_roles.runtime_url, tenant)) == 0  # waited for, not skipped


def test_harness_force_toggle_blocks_the_application(alembic_config: Config, db_roles: DbRoles, pg_url: str) -> None:
    """The replaced design lifted FORCE inside every batch. The ALTER TABLE's lock doesn't depend on
    BYPASSRLS or on the migrator policy, so the migration role (the owner) shows what it cost."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    tenant = uuid.uuid4()
    asyncio.run(provision(db_roles.runtime_url, tenant))

    async def toggled() -> tuple[set[str], BaseException | None]:
        owner = await asyncpg.connect(_plain(db_roles.migrator_url))
        admin = await asyncpg.connect(_admin_url(pg_url))
        try:
            tx = owner.transaction()
            await tx.start()
            await owner.execute("ALTER TABLE widgets NO FORCE ROW LEVEL SECURITY")
            pid = await owner.fetchval("SELECT pg_backend_pid()")
            modes = {r["mode"] for r in await admin.fetch(WIDGET_LOCKS, pid)}
            refused: BaseException | None = None
            try:
                await _app_read_write(db_roles.runtime_url, tenant, timeout_ms=200)
            except asyncpg.exceptions.LockNotAvailableError as exc:
                refused = exc
            await tx.rollback()
            return modes, refused
        finally:
            await owner.close()
            await admin.close()

    modes, refused = asyncio.run(toggled())
    print(f"locks on widgets held by ALTER TABLE ... NO FORCE: {sorted(modes)}")
    assert "AccessExclusiveLock" in modes, modes
    assert refused is not None, "the application's query should have timed out behind ACCESS EXCLUSIVE"
