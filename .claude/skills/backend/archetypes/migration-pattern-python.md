---
skill: migration-pattern-python
description: Python Alembic migration archetype — async env.py setup, auto-generate from SQLAlchemy models, manual migrations, UP/DOWN functions, data migrations, RLS, seed data, migration testing
version: "1.0"
tags:
  - python
  - alembic
  - postgres
  - migration
  - sql
  - archetype
  - backend
  - sqlalchemy
---

# Migration Pattern Archetype — Python (Alembic)

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/migration-pattern.md` (Go/golang-migrate). Both produce the same `widgets` and `widget_categories` tables, indexes, RLS policies and constraints. This chain also creates a `tenants` registry first, so the seed has a list of tenants to seed (see "Seed Data Migration").

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): type-checked; alembic 1.20.0 offline upgrade and downgrade SQL generated through env.py up to d4e5f6a7b8c9 (the batched backfill refuses `--sql` with its own message); the migration tests pass against PostgreSQL 16 with the two roles (`run.sh --live`, 12 passed): round trips as `app_migrator` (BYPASSRLS), env.py refusing `app_runtime`, the seed reaching a tenant with no widgets, a re-run adding nothing and not reviving a deleted default, `provision_tenant()` idempotent, RLS isolating `app_runtime`. `pg_locks` was read while a batch was paused mid-UPDATE (AccessShareLock + RowExclusiveLock on widgets, no AccessExclusiveLock; the application's SELECT and INSERT ran with `lock_timeout = 200ms`) and while `ALTER TABLE ... NO FORCE` was open (AccessExclusiveLock; the application's query timed out). SQLAlchemy 2.1.1, asyncpg 0.31.0.

Complete Alembic migration setup for async SQLAlchemy + asyncpg. Every generated migration MUST follow this pattern.

## Directory Structure

```
alembic/
  alembic.ini                    <- Alembic configuration
  env.py                         <- Migration environment (async)
  script.py.mako                 <- Template for new migrations
  versions/
    20260115_095000_create_tenants_table.py
    20260115_100000_create_widgets_table.py
    20260115_100100_add_widget_categories.py
    20260115_100200_seed_default_categories.py
    20260115_100300_backfill_widget_category.py
```

Naming convention: `YYYYMMDD_HHMMSS_description.py` — matches the Go archetype's timestamp format.

**Who runs migrations.** Two database roles, neither of them a superuser:

- The **migration role** (`app_migrator` in the tests) owns the schema and every table, and has
  `BYPASSRLS`. Only the migrate Job (or a developer running `alembic upgrade`) gets its credentials;
  the application's Deployment never mounts them.
- The **application role** (`app_runtime`) owns nothing and has no `BYPASSRLS`, so row-level security
  applies to every query it makes (`infrastructure/saas-tenancy-models.md`). It reads and writes the
  tables through `ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator ... GRANT SELECT, INSERT, UPDATE,
  DELETE ON TABLES TO app_runtime`, run once when the database is provisioned (the `db_roles` fixture
  in `tests/test_migrations.py` has the statements).

Data migrations, seeds and foreign-key validation read and write every tenant's rows. The migration
role does that without changing any RLS setting, so a backfill batch holds row locks and `ROW
EXCLUSIVE` on the table, and the application's reads and writes don't wait for it. `env.py` refuses to
run as a role that RLS applies to, so the application's credentials can't start a migration that would
fail halfway. Tables still get `FORCE ROW LEVEL SECURITY`, so a table owner without `BYPASSRLS` (a
misconfigured deployment) is refused rather than shown every tenant.

The trade-off, measured with `pg_locks` on PostgreSQL 16 by the migration tests:

| Design | Locks on `widgets` while a backfill batch runs | Cost |
|---|---|---|
| Migration role with `BYPASSRLS` (this archetype) | `ROW EXCLUSIVE` plus the rows it updates. The application's `SELECT` and `INSERT` ran during a paused batch with `lock_timeout = 200ms`. | A role that sees every tenant's rows. As table owner it could already turn RLS off (`ALTER TABLE ... NO FORCE ROW LEVEL SECURITY`), so `BYPASSRLS` only removes the error an accidental tenant-less query by that role would get. Keep its secret in the migrate Job. |
| Owner without `BYPASSRLS`, `FORCE` lifted inside every batch (the previous version of this archetype) | `ACCESS EXCLUSIVE` from the `ALTER TABLE` until the batch commits. The application's `SELECT` timed out behind it. | Every batch blocks all reads and writes of the table, and its `ALTER TABLE` first waits for every running query on the table while new ones queue behind it. |
| Owner without `BYPASSRLS`, `FORCE` lifted once around the whole backfill | Not measured separately: the same `ALTER TABLE`, so `ACCESS EXCLUSIVE` twice (lift, restore) if each runs in its own transaction, for the whole backfill if not. | If the backfill fails midway, `FORCE` stays off for the owner until someone restores it. |

## alembic.ini

```ini
# alembic.ini

[alembic]
# Path to migration scripts
script_location = alembic

# Template for new migrations (uses Mako)
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(slug)s

# Encoding
output_encoding = utf-8

# Truncate long revision IDs in filenames
truncate_slug_length = 60

# Set to 'true' to use timezone-aware datetimes
timezone = utc

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

## env.py — Async Configuration

```python
# alembic/env.py

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import ALL models so Alembic auto-generates from their metadata
from app.models.widget import Base  # noqa: F401 — triggers model registration

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for auto-generation
target_metadata = Base.metadata

# DB URL from the environment: required, no default (never hardcode credentials). A caller that
# already set sqlalchemy.url (the migration tests, via Config.set_main_option) keeps its URL.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL without connecting to the database.
    Useful for reviewing migration SQL before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def check_migration_role(connection: Connection) -> None:
    """Refuse to migrate as a role that row-level security applies to (the application's role).

    Data migrations and seeds read and write every tenant's rows; under RLS they would fail halfway
    through the chain instead of before it. See "Who runs migrations".
    """
    # Its own transaction, ended before alembic begins one. A query outside it would auto-begin a
    # transaction that alembic then treats as the caller's: it would not commit it, and closing the
    # connection would roll every migration back.
    with connection.begin():
        bypasses_rls = connection.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()
    if not bypasses_rls:
        raise RuntimeError(
            "alembic must run as the migration role (owner of the tables, BYPASSRLS), "
            "not as the application role: DATABASE_URL has the wrong credentials"
        )


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live connection."""
    check_migration_role(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schemas to auto-detect changes
        include_schemas=True,
        # Render column type changes as ALTER rather than DROP+CREATE
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async engine.
    This is the standard path for asyncpg-based applications.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool during migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## Auto-Generate from SQLAlchemy Models

```bash
# Generate a migration by comparing models to the current database schema
alembic revision --autogenerate -m "create widgets table"

# Review the generated migration BEFORE applying
cat alembic/versions/*_create_widgets_table.py

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history --verbose
```

## Tenants Registry Migration

```python
# alembic/versions/20260115_095000_create_tenants_table.py

"""Create the tenants registry.

Revision ID: f0e1d2c3b4a5
Revises:
Create Date: 2026-01-15 09:50:00.000000+00:00

One row per tenant: the list a seed or a backfill iterates over (a tenant with no widgets yet is still
a tenant), and the row signup creates (app/db/tenants.py provision_tenant). RLS keys on id, so the
application role sees only its own tenant's row.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f0e1d2c3b4a5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),  # chosen by provisioning, not by the database
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenants
            USING (id = current_setting('app.current_tenant_id')::UUID)
            WITH CHECK (id = current_setting('app.current_tenant_id')::UUID)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.drop_table("tenants")
```

## Table Creation Migration — UP + DOWN

```python
# alembic/versions/20260115_100000_create_widgets_table.py

"""Create widgets table.

Revision ID: a1b2c3d4e5f6
Revises: f0e1d2c3b4a5
Create Date: 2026-01-15 10:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "f0e1d2c3b4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # Table: widgets
    # -----------------------------------------------------------------
    op.create_table(
        "widgets",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Check constraints
        sa.CheckConstraint("status IN ('active', 'inactive', 'archived')", name="chk_widgets_status"),
        sa.CheckConstraint("version > 0", name="chk_widgets_version"),
    )

    # -----------------------------------------------------------------
    # Indexes
    # -----------------------------------------------------------------

    # Tenant isolation — EVERY query filters by tenant_id
    op.create_index("idx_widgets_tenant_id", "widgets", ["tenant_id"])

    # Composite for list query: WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC
    op.execute("""
        CREATE INDEX idx_widgets_tenant_created
        ON widgets (tenant_id, created_at DESC, id DESC)
        WHERE deleted_at IS NULL
    """)

    # Unique constraint scoped to tenant (partial: only active records)
    op.execute("""
        CREATE UNIQUE INDEX idx_widgets_tenant_name_unique
        ON widgets (tenant_id, lower(name))
        WHERE deleted_at IS NULL
    """)

    # Partial index for active records — soft delete optimization
    op.execute("""
        CREATE INDEX idx_widgets_active
        ON widgets (id)
        WHERE deleted_at IS NULL
    """)

    # Status filter
    op.execute("""
        CREATE INDEX idx_widgets_tenant_status
        ON widgets (tenant_id, status)
        WHERE deleted_at IS NULL
    """)

    # -----------------------------------------------------------------
    # Row-Level Security (Multi-Tenant Isolation)
    # -----------------------------------------------------------------

    op.execute("ALTER TABLE widgets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE widgets FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON widgets
            USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID)
    """)

    # -----------------------------------------------------------------
    # Triggers — auto-update updated_at
    # -----------------------------------------------------------------

    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER trg_widgets_updated_at
            BEFORE UPDATE ON widgets
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

    # -----------------------------------------------------------------
    # Comments
    # -----------------------------------------------------------------

    op.execute("COMMENT ON TABLE widgets IS 'Core widget entities — multi-tenant, soft-deletable'")
    op.execute("COMMENT ON COLUMN widgets.deleted_at IS 'Soft delete timestamp — NULL means active'")
    op.execute("COMMENT ON COLUMN widgets.version IS 'Optimistic lock counter — increment on every update'")


def downgrade() -> None:
    """Exact reverse of upgrade — drop everything in reverse order."""

    op.execute("DROP TRIGGER IF EXISTS trg_widgets_updated_at ON widgets")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON widgets")

    op.execute("DROP INDEX IF EXISTS idx_widgets_tenant_status")
    op.execute("DROP INDEX IF EXISTS idx_widgets_active")
    op.execute("DROP INDEX IF EXISTS idx_widgets_tenant_name_unique")
    op.execute("DROP INDEX IF EXISTS idx_widgets_tenant_created")
    op.drop_index("idx_widgets_tenant_id", table_name="widgets")

    op.drop_table("widgets")

    # Only drop if no other tables use this function
    # op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
```

## Manual Migration for Complex Changes

```python
# alembic/versions/20260115_100100_add_widget_categories.py

"""Add widget categories with foreign key.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"


def upgrade() -> None:
    # Create categories table
    op.create_table(
        "widget_categories",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("""
        CREATE UNIQUE INDEX idx_widget_categories_tenant_slug
        ON widget_categories (tenant_id, lower(slug))
        WHERE deleted_at IS NULL
    """)

    # Add category_id FK to widgets. Creating a foreign key runs a validation query that reads both
    # tables; the migration role has BYPASSRLS, so RLS neither hides rows from it nor refuses it for
    # having no tenant set (see "Who runs migrations").
    op.add_column("widgets", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_widgets_category", "widgets", "widget_categories",
        ["category_id"], ["id"], ondelete="SET NULL",
    )
    op.execute("""
        CREATE INDEX idx_widgets_category
        ON widgets (category_id)
        WHERE deleted_at IS NULL AND category_id IS NOT NULL
    """)

    # RLS for categories
    op.execute("ALTER TABLE widget_categories ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE widget_categories FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON widget_categories
            USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_widgets_category")
    op.drop_constraint("fk_widgets_category", "widgets", type_="foreignkey")
    op.drop_column("widgets", "category_id")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON widget_categories")
    op.execute("DROP INDEX IF EXISTS idx_widget_categories_tenant_slug")
    op.drop_table("widget_categories")
```

## Seed Data Migration

What a seed means here, and what the tests prove:

- Every tenant in the `tenants` registry when the migration runs gets the defaults, whether or not it
  has any widgets yet (the old version seeded only tenants that had widgets, so new tenants got none).
- Tenants created later get the same defaults from `provision_tenant()` (`app/db/tenants.py`): a
  migration runs once, signup runs for every tenant.
- Running it again adds nothing, and never brings back a default the tenant has since deleted.

```python
# alembic/versions/20260115_100200_seed_default_categories.py

"""Seed default categories for every existing tenant.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7

NOTE: Seed data is SEPARATE from schema migrations — always.
"""

from __future__ import annotations

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"


def upgrade() -> None:
    """
    Insert the default categories for every live tenant in the registry, including tenants with no
    widgets. Idempotent: a default the tenant already has (live or soft-deleted) is skipped, so a re-run
    adds nothing and a category the tenant deleted stays deleted. ON CONFLICT DO NOTHING covers a
    provision_tenant() for the same tenant committing at the same moment.
    The migration role has BYPASSRLS, so it sees every tenant (see "Who runs migrations"). The list is
    a snapshot: app/db/tenants.py keeps its own copy for tenants created later.
    """
    op.execute("""
        INSERT INTO widget_categories (tenant_id, name, slug, description, sort_order)
        SELECT t.id, d.name, d.slug, d.description, d.sort_order
        FROM tenants t
        CROSS JOIN (
            VALUES
                ('General',    'general',    'Default category for uncategorized widgets', 0),
                ('Internal',   'internal',   'Internal-use widgets',                       1),
                ('Customer',   'customer',   'Customer-facing widgets',                    2),
                ('Deprecated', 'deprecated', 'Widgets scheduled for removal',              3)
        ) AS d(name, slug, description, sort_order)
        WHERE t.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM widget_categories c
              WHERE c.tenant_id = t.id AND lower(c.slug) = d.slug
          )
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    """Remove the default categories (by slug)."""
    op.execute("""
        DELETE FROM widget_categories
        WHERE slug IN ('general', 'internal', 'customer', 'deprecated')
    """)
```

## Data Migration (Backfill / Transform)

```python
# alembic/versions/20260115_100300_backfill_widget_category.py

"""Backfill: put every existing widget in its tenant's "general" category.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8

For large tables (> 100K rows), use the batch approach below.
"""

from __future__ import annotations

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"


def upgrade() -> None:
    """
    Small tables (< 100K rows): one UPDATE. The migration role has BYPASSRLS, so it sees every
    tenant's widgets (see "Who runs migrations").
    """
    op.execute("""
        UPDATE widgets w
        SET category_id = c.id, updated_at = NOW()
        FROM widget_categories c
        WHERE c.tenant_id = w.tenant_id AND c.slug = 'general' AND c.deleted_at IS NULL
          AND w.category_id IS NULL AND w.deleted_at IS NULL
    """)


def downgrade() -> None:
    """
    Reverting a backfill is generally not safe: rows that chose "general" themselves since can't be
    told apart. Intentionally a no-op; the previous migration's downgrade drops the column anyway.
    """
    pass
```

## Large Table Batch Data Migration

```python
# For tables > 100K rows, backfill in batches. Inside autocommit_block() every statement commits on its
# own, so each batch is a short transaction: no lock is held for the whole run, and a failure keeps the
# batches already done (re-running continues where it stopped). The migration role has BYPASSRLS, so a
# batch changes no RLS setting and takes no table lock: ROW EXCLUSIVE on widgets plus its rows, which
# the application's reads and writes don't wait for.
import sqlalchemy as sa
from alembic import context, op

BATCH_SIZE = 5000

# No SKIP LOCKED: a row an application transaction holds is waited for rather than skipped, so the loop
# can't stop while rows are left. The outer conditions repeat the inner ones so that a row the
# application changed while the batch waited for it is checked again in its new state: a widget that
# was just given a category keeps it.
BATCH_UPDATE = sa.text("""
    UPDATE widgets w
    SET category_id = c.id, updated_at = NOW()
    FROM widget_categories c
    WHERE c.tenant_id = w.tenant_id AND c.slug = 'general' AND c.deleted_at IS NULL
      AND w.category_id IS NULL AND w.deleted_at IS NULL
      AND w.id IN (
          SELECT w2.id
          FROM widgets w2
          JOIN widget_categories c2
            ON c2.tenant_id = w2.tenant_id AND c2.slug = 'general' AND c2.deleted_at IS NULL
          WHERE w2.category_id IS NULL AND w2.deleted_at IS NULL
          LIMIT :batch_size
      )
""")


def upgrade() -> None:
    """Backfill category_id in batches of BATCH_SIZE until a batch updates nothing."""
    if context.is_offline_mode():
        # The loop's length depends on the data, so `alembic upgrade --sql` can't render it: generate
        # SQL up to the revision before this one, and run this one against the database.
        raise RuntimeError("the batched category backfill needs a live database; it has no --sql form")
    with op.get_context().autocommit_block():
        bind = op.get_bind()
        while bind.execute(BATCH_UPDATE, {"batch_size": BATCH_SIZE}).rowcount:
            pass
```

## RLS Application-Level Setup

```python
# app/db/rls.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """
    Set the RLS context variable before each query.
    Call this at the start of every request or repository method.

    Uses set_config('app.current_tenant_id', ..., true) where true = local to transaction.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
```

## Provisioning a New Tenant

The seed covers the tenants that exist when it runs. Every tenant created afterwards gets the same
defaults at signup, in the same transaction as its registry row, as the application role under RLS.

```python
# app/db/tenants.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import set_tenant_context

_INSERT_TENANT = text("""
    INSERT INTO tenants (id, name) VALUES (:tenant_id, :name)
    ON CONFLICT (id) DO NOTHING
    RETURNING id
""")

# The seed migration's defaults (c3d4e5f6a7b8 keeps its own frozen copy). A default the tenant already
# has, live or soft-deleted, is skipped, so a repeated call never brings back one the tenant deleted.
_INSERT_DEFAULT_CATEGORIES = text("""
    INSERT INTO widget_categories (tenant_id, name, slug, description, sort_order)
    SELECT t.id, d.name, d.slug, d.description, d.sort_order
    FROM tenants t
    CROSS JOIN (
        VALUES
            ('General',    'general',    'Default category for uncategorized widgets', 0),
            ('Internal',   'internal',   'Internal-use widgets',                       1),
            ('Customer',   'customer',   'Customer-facing widgets',                    2),
            ('Deprecated', 'deprecated', 'Widgets scheduled for removal',              3)
    ) AS d(name, slug, description, sort_order)
    WHERE t.id = :tenant_id AND t.deleted_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM widget_categories c
          WHERE c.tenant_id = t.id AND lower(c.slug) = d.slug
      )
    ON CONFLICT DO NOTHING
""")


async def provision_tenant(session: AsyncSession, tenant_id: UUID, name: str) -> bool:
    """Create a tenant's registry row and its default categories. Returns False if it already existed.

    Call it inside the caller's transaction (`async with session.begin():`) so both commit together.
    tenant_id is chosen once by the signup flow (a new uuid4, or the identity provider's organisation
    id from the verified token), never read from request input. Calling again with the same id changes
    nothing, so a retried signup is safe.
    """
    await set_tenant_context(session, tenant_id)  # RLS: the new rows must belong to this tenant
    created = (
        await session.execute(_INSERT_TENANT, {"tenant_id": tenant_id, "name": name})
    ).scalar_one_or_none() is not None
    await session.execute(_INSERT_DEFAULT_CATEGORIES, {"tenant_id": tenant_id})
    return created
```

## Testing Migrations — Apply, Rollback, Re-apply

```python
# tests/test_migrations.py

"""
Verify that all migrations apply, roll back and re-apply cleanly, as the two roles they run with when
deployed: the migration role (owns the tables, BYPASSRLS) runs them, and the application role (owns
nothing, no BYPASSRLS) reads the result under row-level security. Never as a superuser: a superuser
skips RLS and hides every failure on the application's side.
This catches common issues:
- Missing downgrade logic
- Non-idempotent operations
- Foreign key dependency ordering
- A seed that misses tenants, adds duplicates, or brings back a default a tenant deleted
- An application role that can see another tenant's rows, or run the migrations
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.tenants import provision_tenant

MIGRATOR = "app_migrator"  # owns the schema and runs the migrations: NOSUPERUSER BYPASSRLS
RUNTIME = "app_runtime"  # the application: owns nothing, NOSUPERUSER NOBYPASSRLS
DEFAULTS = ["customer", "deprecated", "general", "internal"]


@dataclass(frozen=True)
class DbRoles:
    migrator_url: str
    runtime_url: str


def _plain(url: str) -> str:
    """asyncpg.connect() takes postgresql://; SQLAlchemy and Alembic take postgresql+asyncpg://."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="session")
def db_roles(pg_url: str) -> DbRoles:
    """A fresh database and both roles, provisioned the way a deployment's database is (once, by an
    administrator). pg_url is the superuser URL of the testcontainers fixture in
    crud-repository-test-python.md, from a conftest.py this directory can see."""
    passwords = {MIGRATOR: uuid.uuid4().hex, RUNTIME: uuid.uuid4().hex}  # throwaway, per run
    db_url = make_url(pg_url).set(database="migrations_test")

    async def provision() -> None:
        admin = await asyncpg.connect(_plain(pg_url))
        try:  # CREATE ROLE takes no bind parameters; the passwords are generated hex
            await admin.execute(f"CREATE ROLE {MIGRATOR} LOGIN NOSUPERUSER BYPASSRLS PASSWORD '{passwords[MIGRATOR]}'")
            await admin.execute(f"CREATE ROLE {RUNTIME} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{passwords[RUNTIME]}'")
            await admin.execute(f"CREATE DATABASE migrations_test OWNER {MIGRATOR}")
        finally:
            await admin.close()
        db = await asyncpg.connect(_plain(db_url.render_as_string(hide_password=False)))
        try:  # every table the migration role creates is usable by the application role
            await db.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATOR} IN SCHEMA public "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {RUNTIME}"
            )
        finally:
            await db.close()

    asyncio.run(provision())
    return DbRoles(
        migrator_url=db_url.set(username=MIGRATOR, password=passwords[MIGRATOR]).render_as_string(hide_password=False),
        runtime_url=db_url.set(username=RUNTIME, password=passwords[RUNTIME]).render_as_string(hide_password=False),
    )


@pytest.fixture(scope="session")
def alembic_config(db_roles: DbRoles) -> Config:
    """Alembic config pointing at the test database, as the migration role."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_roles.migrator_url)  # keep +asyncpg: env.py runs an async engine
    return cfg


class TestMigrations:
    """Integration tests for migration round-trips."""

    def test_upgrade_to_head(self, alembic_config: Config) -> None:
        """All migrations apply cleanly from scratch."""
        command.upgrade(alembic_config, "head")

    def test_downgrade_to_base(self, alembic_config: Config) -> None:
        """All migrations roll back cleanly."""
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")

    def test_round_trip(self, alembic_config: Config) -> None:
        """Upgrade -> downgrade -> upgrade produces identical schema."""
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

    def test_step_by_step(self, alembic_config: Config) -> None:
        """Each migration applies and rolls back individually."""
        # Start from base
        command.downgrade(alembic_config, "base")

        # Get all revision IDs
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions("base", "heads"))
        revisions.reverse()  # oldest first

        for rev in revisions:
            # Apply
            command.upgrade(alembic_config, rev.revision)
            # Rollback one step ("-1", not rev.down_revision: a merge revision has a tuple of parents)
            command.downgrade(alembic_config, "-1")
            # Re-apply
            command.upgrade(alembic_config, rev.revision)

    def test_application_role_cannot_migrate(self, db_roles: DbRoles) -> None:
        """env.py stops before the first migration when DATABASE_URL has the application's credentials."""
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_roles.runtime_url)
        with pytest.raises(RuntimeError, match="must run as the migration role"):
            command.upgrade(cfg, "head")


class TestSeedAndProvisioning:
    """The default categories reach every tenant exactly once, and RLS holds for the application."""

    def test_seed_covers_every_tenant(self, alembic_config: Config, db_roles: DbRoles) -> None:
        """Every registered tenant gets the defaults, including one with no widgets; existing widgets
        land in "general"."""
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "b2c3d4e5f6a7")  # the schema, before the seed and backfill
        busy, idle = uuid.uuid4(), uuid.uuid4()
        for tenant in (busy, idle):
            asyncio.run(as_tenant(db_roles.runtime_url, tenant, "INSERT INTO tenants (id, name) VALUES ($1, 'acme')", tenant))
        asyncio.run(insert_widget(db_roles.runtime_url, busy))

        command.upgrade(alembic_config, "head")

        for tenant in (busy, idle):
            assert asyncio.run(live_slugs(db_roles.runtime_url, tenant)) == DEFAULTS
        assert asyncio.run(uncategorized(db_roles.runtime_url, busy)) == 0

    def test_seed_rerun_adds_nothing(self, alembic_config: Config, db_roles: DbRoles) -> None:
        """Running the seed again adds no duplicate, and a default the tenant deleted stays deleted."""
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "b2c3d4e5f6a7")
        tenant = uuid.uuid4()
        asyncio.run(as_tenant(db_roles.runtime_url, tenant, "INSERT INTO tenants (id, name) VALUES ($1, 'acme')", tenant))
        command.upgrade(alembic_config, "c3d4e5f6a7b8")
        asyncio.run(soft_delete_category(db_roles.runtime_url, tenant, "deprecated"))

        command.stamp(alembic_config, "b2c3d4e5f6a7")  # mark the seed as not applied...
        command.upgrade(alembic_config, "c3d4e5f6a7b8")  # ...and run it again

        assert asyncio.run(live_slugs(db_roles.runtime_url, tenant)) == ["customer", "general", "internal"]
        assert asyncio.run(category_rows(db_roles.runtime_url, tenant)) == 4  # the deleted one included

    def test_provision_tenant_after_the_seed(self, alembic_config: Config, db_roles: DbRoles) -> None:
        """A tenant that signs up later gets the defaults from provision_tenant(), as the application
        role; calling it again changes nothing and doesn't bring back a deleted default."""
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        tenant = uuid.uuid4()

        assert asyncio.run(provision(db_roles.runtime_url, tenant)) is True
        assert asyncio.run(live_slugs(db_roles.runtime_url, tenant)) == DEFAULTS
        asyncio.run(soft_delete_category(db_roles.runtime_url, tenant, "internal"))
        assert asyncio.run(provision(db_roles.runtime_url, tenant)) is False
        assert asyncio.run(live_slugs(db_roles.runtime_url, tenant)) == ["customer", "deprecated", "general"]

    def test_application_role_sees_only_its_tenant(self, alembic_config: Config, db_roles: DbRoles) -> None:
        """Under RLS the application sees its own tenant's rows only, and nothing without a tenant."""
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        mine, other = uuid.uuid4(), uuid.uuid4()
        for tenant in (mine, other):
            asyncio.run(provision(db_roles.runtime_url, tenant))
        asyncio.run(insert_widget(db_roles.runtime_url, other))

        assert asyncio.run(as_tenant(db_roles.runtime_url, mine, "SELECT id FROM tenants")) == [(mine,)]
        assert asyncio.run(category_rows(db_roles.runtime_url, mine)) == 4  # not the other tenant's 4
        assert asyncio.run(as_tenant(db_roles.runtime_url, mine, "SELECT id FROM widgets")) == []
        with pytest.raises(asyncpg.exceptions.UndefinedObjectError):  # app.current_tenant_id unset
            asyncio.run(count_widgets_without_tenant(db_roles.runtime_url))


async def as_tenant(url: str, tenant: uuid.UUID, sql: str, *args: object) -> list[tuple[object, ...]]:
    """One transaction as `tenant`: under RLS every query names its tenant (app/db/rls.py)."""
    conn = await asyncpg.connect(_plain(url))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant))
            return [tuple(row.values()) for row in await conn.fetch(sql, *args)]
    finally:
        await conn.close()


async def insert_widget(url: str, tenant: uuid.UUID) -> None:
    await as_tenant(
        url, tenant,
        "INSERT INTO widgets (tenant_id, name, created_by, updated_by) VALUES ($1, $2, $3, $3)",
        tenant, f"widget-{uuid.uuid4().hex[:8]}", uuid.uuid4(),
    )


async def soft_delete_category(url: str, tenant: uuid.UUID, slug: str) -> None:
    await as_tenant(url, tenant, "UPDATE widget_categories SET deleted_at = NOW() WHERE slug = $1", slug)


async def live_slugs(url: str, tenant: uuid.UUID) -> list[object]:
    rows = await as_tenant(url, tenant, "SELECT slug FROM widget_categories WHERE deleted_at IS NULL ORDER BY slug")
    return [slug for (slug,) in rows]


async def category_rows(url: str, tenant: uuid.UUID) -> object:
    return (await as_tenant(url, tenant, "SELECT count(*) FROM widget_categories"))[0][0]


async def uncategorized(url: str, tenant: uuid.UUID) -> object:
    return (await as_tenant(url, tenant, "SELECT count(*) FROM widgets WHERE category_id IS NULL"))[0][0]


async def provision(url: str, tenant: uuid.UUID) -> bool:
    """provision_tenant() through the application's own session, as the application role."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            return await provision_tenant(session, tenant, "acme")
    finally:
        await engine.dispose()


async def count_widgets_without_tenant(url: str) -> int:
    conn = await asyncpg.connect(_plain(url))
    try:
        return await conn.fetchval("SELECT count(*) FROM widgets")
    finally:
        await conn.close()
```

## CLI Commands

```bash
# Create a new auto-generated migration
alembic revision --autogenerate -m "add priority column to widgets"

# Create a manual migration (for data migrations, RLS, etc.)
alembic revision -m "seed default categories"

# Apply all pending migrations
alembic upgrade head

# Apply next N migrations
alembic upgrade +1

# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade a1b2c3d4e5f6

# Rollback all migrations
alembic downgrade base

# Show current migration state
alembic current

# Show full migration history
alembic history --verbose

# Generate SQL without applying (offline mode)
alembic upgrade head --sql > migration.sql
```

## Critical Rules

- Every migration MUST have both `upgrade()` and `downgrade()` functions
- Every tenant-owned table MUST have `tenant_id`, `deleted_at`, and `version` columns
- Every table MUST have RLS enabled with a tenant isolation policy (the `tenants` registry keys it on `id`)
- Every `downgrade()` MUST use `IF EXISTS` guards — safe to re-run
- Every `downgrade()` MUST be the exact reverse of the `upgrade()`
- Unique indexes MUST be scoped to tenant: `(tenant_id, column)` not just `(column)`
- Unique indexes MUST use partial index `WHERE deleted_at IS NULL`
- Schema migrations and seed data are SEPARATE files — never combine
- Data migrations (backfills) are SEPARATE from schema changes
- Migrations run as the migration role: owns the tables, has `BYPASSRLS`, is not a superuser, and its credentials go to the migrate Job only. The application connects as a role that owns nothing and has no `BYPASSRLS`; `env.py` refuses to migrate as such a role
- Data migrations never toggle RLS: `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` takes an `ACCESS EXCLUSIVE` lock, which blocks the application's queries on the table until the transaction ends
- Migration tests run as those two roles, never a superuser (a superuser skips RLS and hides the application's failures)
- Seeds select tenants from the `tenants` registry (not from whichever rows happen to exist), skip rows the tenant already has (soft-deleted ones included) and use `ON CONFLICT DO NOTHING`; tenants created later get the same defaults from `provision_tenant()`
- Large table updates (> 100K rows) MUST use batch processing to avoid long locks
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction — use `op.execute()` outside transaction context
- Always use `op.execute()` for raw SQL (RLS, triggers, partial indexes) since Alembic ops don't support all PostgreSQL features
- Database URL MUST come from environment variables — never hardcode credentials
- Every auto-generated migration MUST be reviewed before applying — auto-generate is a starting point, not gospel
- Migration tests MUST verify: upgrade, downgrade, and round-trip for every revision
