> **This file contains Go-specific patterns for: Migration Pattern Archetype.** The language-neutral version at [migration-pattern.md](migration-pattern.md) contains the same Go patterns and serves as the canonical reference. This file exists for consistent `{{LANG}}` placeholder resolution by `agent_factory`.

---
skill: migration-pattern
description: PostgreSQL migration archetype — table creation, indexes, soft delete, RLS, seed data, data migrations, naming conventions, rollback safety
version: "1.0"
tags:
  - go
  - postgres
  - migration
  - sql
  - archetype
  - backend
---

# Migration Pattern Archetype

Complete PostgreSQL migration templates. Every generated migration MUST follow this pattern.

## Naming Convention

```
migrations/
  20260115100000_create_widgets_table.up.sql
  20260115100000_create_widgets_table.down.sql
  20260115100100_add_widget_categories.up.sql
  20260115100100_add_widget_categories.down.sql
  20260115100200_seed_default_categories.up.sql
  20260115100200_seed_default_categories.down.sql
  20260115100300_backfill_widget_status.up.sql
  20260115100300_backfill_widget_status.down.sql
```

Format: `YYYYMMDDHHMMSS_description.{up|down}.sql`

Rules:
- Timestamp is UTC, monotonically increasing
- Description uses `snake_case`, starts with verb: `create_`, `add_`, `alter_`, `drop_`, `seed_`, `backfill_`
- Schema migrations and seed data are SEPARATE files
- Data migrations (backfills) are SEPARATE from schema changes
- Each migration is a single, atomic operation — don't combine unrelated changes

## UP Migration — Table Creation

```sql
-- Migration: 20260115100000_create_widgets_table.up.sql
-- Purpose: Create the widgets table with standard columns, indexes, and RLS

BEGIN;

-- =============================================================================
-- Table: widgets
-- =============================================================================

CREATE TABLE IF NOT EXISTS widgets (
    -- Primary key: UUID v7 (time-ordered) for natural sort + uniqueness
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tenant isolation: every row belongs to exactly one tenant
    tenant_id   UUID        NOT NULL,

    -- Business fields
    name        TEXT        NOT NULL,
    description TEXT        NOT NULL DEFAULT '',
    status      TEXT        NOT NULL DEFAULT 'active',
    priority    INT         NOT NULL DEFAULT 0,
    config      JSONB       NOT NULL DEFAULT '{}',

    -- Audit trail: who created/modified
    created_by  UUID        NOT NULL,
    updated_by  UUID        NOT NULL,

    -- Timestamps
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,  -- NULL = active, set = soft-deleted

    -- Optimistic locking: increment on every update
    version     INT         NOT NULL DEFAULT 1,

    -- Foreign keys
    CONSTRAINT fk_widgets_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_widgets_created_by
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,

    -- Check constraints for enum-like fields
    CONSTRAINT chk_widgets_status
        CHECK (status IN ('active', 'inactive', 'archived', 'draft')),
    CONSTRAINT chk_widgets_priority
        CHECK (priority BETWEEN 0 AND 10),
    CONSTRAINT chk_widgets_version
        CHECK (version > 0)
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Tenant isolation index: EVERY query filters by tenant_id — this MUST exist
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_id
    ON widgets (tenant_id);

-- Composite index for common list query: tenant + sort + cursor pagination
-- Covers: WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_created
    ON widgets (tenant_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;

-- Unique constraint scoped to tenant (name is unique per tenant, not globally)
CREATE UNIQUE INDEX IF NOT EXISTS idx_widgets_tenant_name_unique
    ON widgets (tenant_id, lower(name))
    WHERE deleted_at IS NULL;

-- Partial index for active records — soft delete filter
-- All queries that filter `WHERE deleted_at IS NULL` benefit from this
CREATE INDEX IF NOT EXISTS idx_widgets_active
    ON widgets (id)
    WHERE deleted_at IS NULL;

-- Status filter (common filter in list queries)
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_status
    ON widgets (tenant_id, status)
    WHERE deleted_at IS NULL;

-- GIN index for JSONB config column (supports @>, ?, ?& operators)
CREATE INDEX IF NOT EXISTS idx_widgets_config_gin
    ON widgets USING GIN (config);

-- Updated_at index for change-feed / sync queries
CREATE INDEX IF NOT EXISTS idx_widgets_updated_at
    ON widgets (updated_at DESC)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- Row-Level Security (Multi-Tenant Isolation)
-- =============================================================================

-- Enable RLS on the table
ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;

-- Force RLS for table owner too (prevents bypass via superuser queries)
ALTER TABLE widgets FORCE ROW LEVEL SECURITY;

-- Policy: tenant can only see/modify their own rows
-- Application sets current_setting('app.current_tenant_id') before each request
CREATE POLICY tenant_isolation ON widgets
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- =============================================================================
-- Triggers
-- =============================================================================

-- Auto-update updated_at on every modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_widgets_updated_at
    BEFORE UPDATE ON widgets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Comments (documentation in the schema itself)
-- =============================================================================

COMMENT ON TABLE widgets IS 'Core widget entities — multi-tenant, soft-deletable';
COMMENT ON COLUMN widgets.id IS 'UUID primary key (gen_random_uuid)';
COMMENT ON COLUMN widgets.tenant_id IS 'Owning tenant — enforced by RLS policy';
COMMENT ON COLUMN widgets.status IS 'Lifecycle status: active, inactive, archived, draft';
COMMENT ON COLUMN widgets.config IS 'Flexible JSONB configuration (schema validated in app layer)';
COMMENT ON COLUMN widgets.deleted_at IS 'Soft delete timestamp — NULL means active';
COMMENT ON COLUMN widgets.version IS 'Optimistic lock counter — increment on every update';

COMMIT;
```

## DOWN Migration — Exact Reverse

```sql
-- Migration: 20260115100000_create_widgets_table.down.sql
-- Purpose: Reverse the widgets table creation — drop everything in reverse order

BEGIN;

-- Drop trigger first (depends on function)
DROP TRIGGER IF EXISTS trg_widgets_updated_at ON widgets;

-- Drop RLS policy (must drop before table)
DROP POLICY IF EXISTS tenant_isolation ON widgets;

-- Drop indexes explicitly (for clarity, though DROP TABLE CASCADE handles them)
DROP INDEX IF EXISTS idx_widgets_updated_at;
DROP INDEX IF EXISTS idx_widgets_config_gin;
DROP INDEX IF EXISTS idx_widgets_tenant_status;
DROP INDEX IF EXISTS idx_widgets_active;
DROP INDEX IF EXISTS idx_widgets_tenant_name_unique;
DROP INDEX IF EXISTS idx_widgets_tenant_created;
DROP INDEX IF EXISTS idx_widgets_tenant_id;

-- Drop the table
DROP TABLE IF EXISTS widgets;

-- Drop trigger function only if no other tables use it
-- (In practice, this is shared — only drop in the LAST migration that uses it)
-- DROP FUNCTION IF EXISTS update_updated_at_column();

COMMIT;
```

## Foreign Key Table Pattern

```sql
-- Migration: 20260115100100_add_widget_categories.up.sql
-- Purpose: Add categories with foreign key relationship to widgets

BEGIN;

CREATE TABLE IF NOT EXISTS widget_categories (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL,
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL,
    description TEXT        NOT NULL DEFAULT '',
    sort_order  INT         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,

    CONSTRAINT fk_widget_categories_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_widget_categories_tenant_slug
    ON widget_categories (tenant_id, lower(slug))
    WHERE deleted_at IS NULL;

-- Add category_id to widgets with ON DELETE SET NULL (don't cascade delete widgets)
ALTER TABLE widgets
    ADD COLUMN IF NOT EXISTS category_id UUID,
    ADD CONSTRAINT fk_widgets_category
        FOREIGN KEY (category_id) REFERENCES widget_categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_widgets_category
    ON widgets (category_id)
    WHERE deleted_at IS NULL AND category_id IS NOT NULL;

-- RLS for categories
ALTER TABLE widget_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE widget_categories FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON widget_categories
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

COMMIT;
```

## Seed Data Migration

```sql
-- Migration: 20260115100200_seed_default_categories.up.sql
-- Purpose: Insert default categories for existing tenants
-- NOTE: Seed data is SEPARATE from schema migrations

BEGIN;

-- Insert default categories for each existing tenant
-- Uses ON CONFLICT to make the migration idempotent (safe to re-run)
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
ON CONFLICT DO NOTHING;

COMMIT;
```

```sql
-- Migration: 20260115100200_seed_default_categories.down.sql
BEGIN;

-- Remove only the seeded default categories (by slug pattern)
DELETE FROM widget_categories
WHERE slug IN ('general', 'internal', 'customer', 'deprecated');

COMMIT;
```

## Data Migration Pattern (Backfill / Transform)

```sql
-- Migration: 20260115100300_backfill_widget_status.up.sql
-- Purpose: Backfill status for legacy widgets that have NULL status
--
-- IMPORTANT: For tables with > 100K rows, run this in batches to avoid long locks.

BEGIN;

-- Small tables (< 100K rows): single UPDATE is fine
UPDATE widgets
SET status = 'active', updated_at = NOW()
WHERE status IS NULL AND deleted_at IS NULL;

COMMIT;

-- ============================================================================
-- LARGE TABLE ALTERNATIVE: Batch update pattern (run outside a transaction)
-- Use this for tables with > 100K rows to avoid long-running locks.
-- ============================================================================
--
-- DO $$
-- DECLARE
--     batch_size INT := 5000;
--     rows_updated INT;
-- BEGIN
--     LOOP
--         UPDATE widgets
--         SET status = 'active', updated_at = NOW()
--         WHERE id IN (
--             SELECT id FROM widgets
--             WHERE status IS NULL AND deleted_at IS NULL
--             LIMIT batch_size
--             FOR UPDATE SKIP LOCKED
--         );
--         GET DIAGNOSTICS rows_updated = ROW_COUNT;
--         RAISE NOTICE 'Updated % rows', rows_updated;
--         EXIT WHEN rows_updated = 0;
--         PERFORM pg_sleep(0.1);  -- brief pause to reduce lock pressure
--     END LOOP;
-- END $$;
```

## CREATE INDEX CONCURRENTLY for Large Tables

```sql
-- Migration: 20260115100400_add_widget_search_index.up.sql
-- Purpose: Add full-text search index on large widgets table
--
-- IMPORTANT: CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
-- The migration runner must support non-transactional migrations.

-- DO NOT wrap in BEGIN/COMMIT
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_widgets_search
    ON widgets USING GIN (to_tsvector('english', name || ' ' || description))
    WHERE deleted_at IS NULL;
```

```sql
-- Migration: 20260115100400_add_widget_search_index.down.sql
DROP INDEX CONCURRENTLY IF EXISTS idx_widgets_search;
```

## Go Migration Runner Integration

```go
package main

import (
    "database/sql"
    "embed"
    "log/slog"

    "github.com/golang-migrate/migrate/v4"
    "github.com/golang-migrate/migrate/v4/database/postgres"
    "github.com/golang-migrate/migrate/v4/source/iofs"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

func runMigrations(db *sql.DB, logger *slog.Logger) error {
    source, err := iofs.New(migrationsFS, "migrations")
    if err != nil {
        return fmt.Errorf("migration source: %w", err)
    }

    driver, err := postgres.WithInstance(db, &postgres.Config{})
    if err != nil {
        return fmt.Errorf("migration driver: %w", err)
    }

    m, err := migrate.NewWithInstance("iofs", source, "postgres", driver)
    if err != nil {
        return fmt.Errorf("migration init: %w", err)
    }

    if err := m.Up(); err != nil && err != migrate.ErrNoChange {
        return fmt.Errorf("migration up: %w", err)
    }

    version, dirty, err := m.Version()
    if err != nil {
        return fmt.Errorf("migration version: %w", err)
    }
    logger.Info("migrations applied", "version", version, "dirty", dirty)
    return nil
}
```

## RLS Application-Level Setup

```go
// setTenantContext sets the RLS context variable before each query.
// Call this at the start of every request handler or repository method.
func setTenantContext(ctx context.Context, pool *pgxpool.Pool, tenantID uuid.UUID) error {
    _, err := pool.Exec(ctx,
        "SELECT set_config('app.current_tenant_id', $1, true)", // true = local to transaction
        tenantID.String(),
    )
    return err
}

// WithTenantTx wraps a function in a transaction with the tenant context set.
func WithTenantTx(ctx context.Context, pool *pgxpool.Pool, tenantID uuid.UUID, fn func(pgx.Tx) error) error {
    tx, err := pool.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)

    // Set RLS context for this transaction
    if _, err := tx.Exec(ctx,
        "SELECT set_config('app.current_tenant_id', $1, true)",
        tenantID.String(),
    ); err != nil {
        return fmt.Errorf("set tenant context: %w", err)
    }

    if err := fn(tx); err != nil {
        return err
    }

    return tx.Commit(ctx)
}
```

## Standard Columns Reference

Every table MUST include these columns:

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `id` | `UUID` | `gen_random_uuid()` | Primary key |
| `tenant_id` | `UUID` | — (NOT NULL) | Multi-tenant isolation, RLS |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOW()` | Last modification (auto-trigger) |
| `deleted_at` | `TIMESTAMPTZ` | `NULL` | Soft delete marker |
| `created_by` | `UUID` | — (NOT NULL) | Audit: who created |
| `version` | `INT` | `1` | Optimistic locking counter |

Optional but recommended:

| Column | Type | Purpose |
|--------|------|---------|
| `updated_by` | `UUID` | Audit: who last modified |
| `config` | `JSONB` | Flexible structured data |

## Critical Rules

- Every migration MUST be wrapped in `BEGIN`/`COMMIT` (except `CREATE INDEX CONCURRENTLY`)
- Every table MUST have `tenant_id` with a foreign key to `tenants`
- Every table MUST have `deleted_at` for soft delete support
- Every table MUST have a `version` column for optimistic locking
- Every table MUST have RLS enabled with a tenant isolation policy
- Every DOWN migration MUST use `IF EXISTS` guards — it must be safe to re-run
- Every DOWN migration MUST be the exact reverse of the UP migration
- Unique indexes MUST be scoped to tenant: `(tenant_id, column)` not just `(column)`
- Unique indexes MUST use partial index `WHERE deleted_at IS NULL` to allow re-creation after soft delete
- Indexes for list queries MUST match the `ORDER BY` clause: `(tenant_id, sort_col DESC, id DESC)`
- `CREATE INDEX CONCURRENTLY` MUST be used for large tables (> 100K rows) to avoid locks
- Data migrations (backfills) MUST be separate from schema migrations
- Seed data MUST use `ON CONFLICT DO NOTHING` for idempotency
- Foreign keys MUST specify `ON DELETE` behavior explicitly (`CASCADE`, `SET NULL`, `RESTRICT`)
- JSONB columns MUST have a GIN index if they will be queried
- Table and column comments MUST be added for documentation
