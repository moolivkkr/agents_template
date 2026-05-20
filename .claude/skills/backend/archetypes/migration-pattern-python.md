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

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/migration-pattern.md` (Go/golang-migrate). Both produce identical database schemas — same tables, indexes, RLS policies, and constraints.

Complete Alembic migration setup for async SQLAlchemy + asyncpg. Every generated migration MUST follow this pattern.

## Directory Structure

```
alembic/
  alembic.ini                    <- Alembic configuration
  env.py                         <- Migration environment (async)
  script.py.mako                 <- Template for new migrations
  versions/
    20260115_100000_create_widgets_table.py
    20260115_100100_add_widget_categories.py
    20260115_100200_seed_default_categories.py
    20260115_100300_backfill_widget_status.py
```

Naming convention: `YYYYMMDD_HHMMSS_description.py` — matches the Go archetype's timestamp format.

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
from sqlalchemy import pool
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

# Override DB URL from environment variable (never hardcode credentials)
database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/appdb",
)
config.set_main_option("sqlalchemy.url", database_url)

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

def do_run_migrations(connection) -> None:
    """Run migrations with a live connection."""
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

## Table Creation Migration — UP + DOWN

```python
# alembic/versions/20260115_100000_create_widgets_table.py

"""Create widgets table.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-01-15 10:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Table: widgets
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

    # Indexes

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

    # Row-Level Security (Multi-Tenant Isolation)

    op.execute("ALTER TABLE widgets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE widgets FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON widgets
            USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID)
    """)

    # Triggers — auto-update updated_at

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

    # Comments

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

    # RLS for categories
    op.execute("ALTER TABLE widget_categories ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE widget_categories FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON widget_categories
            USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID)
    """)

    # Add category_id FK to widgets
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

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_widgets_category")
    op.drop_constraint("fk_widgets_category", "widgets", type_="foreignkey")
    op.drop_column("widgets", "category_id")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON widget_categories")
    op.execute("DROP INDEX IF EXISTS idx_widget_categories_tenant_slug")
    op.drop_table("widget_categories")
```

## Seed Data Migration

```python
# alembic/versions/20260115_100200_seed_default_categories.py

"""Seed default categories for existing tenants.

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
    Insert default categories for each existing tenant.
    Uses ON CONFLICT DO NOTHING for idempotency (safe to re-run).
    """
    op.execute("""
        INSERT INTO widget_categories (id, tenant_id, name, slug, description, sort_order, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            t.id,
            category.name,
            category.slug,
            category.description,
            category.sort_order,
            NOW(),
            NOW()
        FROM tenants t
        CROSS JOIN (
            VALUES
                ('General',    'general',    'Default category for uncategorized widgets', 0),
                ('Internal',   'internal',   'Internal-use widgets',                       1),
                ('Customer',   'customer',   'Customer-facing widgets',                    2),
                ('Deprecated', 'deprecated', 'Widgets scheduled for removal',              3)
        ) AS category(name, slug, description, sort_order)
        ON CONFLICT DO NOTHING
    """)

def downgrade() -> None:
    """Remove only the seeded default categories (by slug pattern)."""
    op.execute("""
        DELETE FROM widget_categories
        WHERE slug IN ('general', 'internal', 'customer', 'deprecated')
    """)
```

## Data Migration (Backfill / Transform)

```python
# alembic/versions/20260115_100300_backfill_widget_status.py

"""Backfill status for legacy widgets with NULL status.

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
    Small tables (< 100K rows): single UPDATE.
    """
    op.execute("""
        UPDATE widgets
        SET status = 'active', updated_at = NOW()
        WHERE status IS NULL AND deleted_at IS NULL
    """)

def downgrade() -> None:
    """
    Reverting a backfill is generally not safe — data was already in an
    inconsistent state. Log a warning instead of blindly setting to NULL.
    """
    # Intentionally no-op: reverting a data fix is usually wrong.
    # If truly needed:
    # op.execute("UPDATE widgets SET status = NULL WHERE status = 'active'")
    pass
```

## Large Table Batch Data Migration

```python
# For tables > 100K rows, use batched updates to avoid long locks.

def upgrade() -> None:
    """Batch update in chunks of 5000 to avoid lock contention."""
    from sqlalchemy import text

    conn = op.get_bind()
    batch_size = 5000

    while True:
        result = conn.execute(text("""
            UPDATE widgets
            SET status = 'active', updated_at = NOW()
            WHERE id IN (
                SELECT id FROM widgets
                WHERE status IS NULL AND deleted_at IS NULL
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
        """), {"batch_size": batch_size})

        rows_updated = result.rowcount
        if rows_updated == 0:
            break

        conn.commit()
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

## Testing Migrations — Apply, Rollback, Re-apply

```python
# tests/test_migrations.py

"""
Verify that all migrations can be applied, rolled back, and re-applied cleanly.
This catches common issues:
- Missing downgrade logic
- Non-idempotent operations
- Foreign key dependency ordering
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config

@pytest.fixture(scope="session")
def alembic_config(pg_url: str) -> Config:
    """Alembic config pointing at the test database."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_url.replace("+asyncpg", ""))
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
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions("base", "heads"))
        revisions.reverse()  # oldest first

        for rev in revisions:
            # Apply
            command.upgrade(alembic_config, rev.revision)
            # Rollback
            command.downgrade(alembic_config, rev.down_revision or "base")
            # Re-apply
            command.upgrade(alembic_config, rev.revision)
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
- Every table MUST have `tenant_id`, `deleted_at`, and `version` columns
- Every table MUST have RLS enabled with a tenant isolation policy
- Every `downgrade()` MUST use `IF EXISTS` guards — safe to re-run
- Every `downgrade()` MUST be the exact reverse of the `upgrade()`
- Unique indexes MUST be scoped to tenant: `(tenant_id, column)` not just `(column)`
- Unique indexes MUST use partial index `WHERE deleted_at IS NULL`
- Schema migrations and seed data are SEPARATE files — never combine
- Data migrations (backfills) are SEPARATE from schema changes
- Seed data MUST use `ON CONFLICT DO NOTHING` for idempotency
- Large table updates (> 100K rows) MUST use batch processing to avoid long locks
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction — use `op.execute()` outside transaction context
- Always use `op.execute()` for raw SQL (RLS, triggers, partial indexes) since Alembic ops don't support all PostgreSQL features
- Database URL MUST come from environment variables — never hardcode credentials
- Every auto-generated migration MUST be reviewed before applying — auto-generate is a starting point, not gospel
- Migration tests MUST verify: upgrade, downgrade, and round-trip for every revision
