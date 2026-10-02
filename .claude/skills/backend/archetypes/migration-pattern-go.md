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

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, golang-migrate v4.20.1, pgx v5.11.0, testcontainers-go v0.44.0; the SQL migrations below were run with golang-migrate against postgres:16-alpine as a non-superuser owner without BYPASSRLS, the RDS migrator (up, down, re-up for every version; seed, backfill and foreign-key validation under FORCE ROW LEVEL SECURITY through the D-001 migrator policies, re-run 2026-10-01; with one `app_grant_migrator` call removed the backfill migration fails; the app role still sees one tenant), and the large-table DO-block alternative was run once (tests/archetype-compile/go/run.sh, ARCHETYPE_DB_TESTS=1). The schema matches migration-pattern-python.md.

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
  20260115100300_backfill_widget_category.up.sql
  20260115100300_backfill_widget_category.down.sql
  20260115100400_add_widget_search_index.up.sql
  20260115100400_add_widget_search_index.down.sql
```

Format: `YYYYMMDDHHMMSS_description.{up|down}.sql`

Rules:
- Timestamp is UTC, monotonically increasing
- Description uses `snake_case`, starts with verb: `create_`, `add_`, `alter_`, `drop_`, `seed_`, `backfill_`
- Schema migrations and seed data are SEPARATE files
- Data migrations (backfills) are SEPARATE from schema changes
- Each migration is a single, atomic operation — don't combine unrelated changes

**Who runs migrations.** The migrator: a plain login role that owns the tables and is not a superuser.
The application connects as a different role that owns nothing and has no `BYPASSRLS`
(`infrastructure/saas-tenancy-models.md`). `FORCE ROW LEVEL SECURITY` applies RLS to the owner too, so
the migrator reaches every tenant's rows through its own policy (decision D-001):
- The first migration creates the helper `app_grant_migrator(regclass)`.
- Every migration that creates a tenant table calls `SELECT app_grant_migrator('<table>')`. That gives
  the table a permissive policy `TO` its owner only, `USING (true) WITH CHECK (true)`.
- Data migrations, seeds and foreign-key validation then see every tenant with `FORCE` on, on both deploy
  paths:
  - lab: the migrator is also `BYPASSRLS`;
  - RDS/Aurora: it can't be (`infrastructure/eks.md`), so this policy is what makes migrations work.
- Never lift `FORCE` in a migration. `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` takes an
  `ACCESS EXCLUSIVE` lock that blocks the application until commit.
- The app role is neither the owner nor a member of it, so the policy never applies to it.

Run the migration tests as a NOBYPASSRLS owner (Testing Migrations, below): that is the RDS migrator, the
stricter path. A superuser skips RLS and hides every one of these failures.

## UP Migration — Table Creation

```sql
-- Migration: 20260115100000_create_widgets_table.up.sql
-- Purpose: Create the widgets table with standard columns, indexes, and RLS

BEGIN;

-- =============================================================================
-- The migrator-policy helper (decision D-001) — ONCE, in the first migration
-- =============================================================================

-- app_grant_migrator(t) gives t a PERMISSIVE policy TO t's owner only, USING (true) WITH CHECK (true).
-- The owner is the migrator (it owns every object), so data migrations and seeds reach every tenant
-- under FORCE ROW LEVEL SECURITY without BYPASSRLS (RDS/Aurora can't grant it). The target comes from
-- the catalog: no role name in the SQL. Rules: databases/postgres.md, "The migrator policy".
CREATE OR REPLACE FUNCTION app_grant_migrator(tbl regclass) RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
    owner_role name;
    pol        name;
BEGIN
    SELECT pg_get_userbyid(c.relowner), left(c.relname, 49) || '_migrator_all'
      INTO owner_role, pol
      FROM pg_class c WHERE c.oid = tbl;
    IF EXISTS (SELECT FROM pg_policy WHERE polrelid = tbl AND polname = pol) THEN
        EXECUTE format('ALTER POLICY %I ON %s TO %I', pol, tbl, owner_role);
    ELSE
        EXECUTE format('CREATE POLICY %I ON %s AS PERMISSIVE FOR ALL TO %I USING (true) WITH CHECK (true)',
                       pol, tbl, owner_role);
    END IF;
END
$fn$;
REVOKE ALL ON FUNCTION app_grant_migrator(regclass) FROM PUBLIC;

-- =============================================================================
-- Table: widgets
-- =============================================================================

CREATE TABLE widgets (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tenant isolation: every row belongs to exactly one tenant. These samples have no tenants
    -- table; if your schema has one, add FOREIGN KEY (tenant_id) REFERENCES tenants(id).
    tenant_id   UUID          NOT NULL,

    -- Business fields
    name        VARCHAR(255)  NOT NULL,
    description VARCHAR(2000) NOT NULL DEFAULT '',
    status      VARCHAR(50)   NOT NULL DEFAULT 'active',

    -- Timestamps
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,  -- NULL = active, set = soft-deleted

    -- Audit trail: who created/modified (user IDs from the verified token)
    created_by  UUID          NOT NULL,
    updated_by  UUID          NOT NULL,

    -- Optimistic locking: increment on every update
    version     INT           NOT NULL DEFAULT 1,

    -- Check constraints for enum-like fields
    CONSTRAINT chk_widgets_status
        CHECK (status IN ('active', 'inactive', 'archived')),
    CONSTRAINT chk_widgets_version
        CHECK (version > 0)
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Tenant isolation index: EVERY query filters by tenant_id — this MUST exist
CREATE INDEX idx_widgets_tenant_id
    ON widgets (tenant_id);

-- Composite index for common list query: tenant + sort + cursor pagination
-- Covers: WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC, id DESC
CREATE INDEX idx_widgets_tenant_created
    ON widgets (tenant_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;

-- Unique constraint scoped to tenant (name is unique per tenant, not globally)
CREATE UNIQUE INDEX idx_widgets_tenant_name_unique
    ON widgets (tenant_id, lower(name))
    WHERE deleted_at IS NULL;

-- Partial index for active records — soft delete filter
CREATE INDEX idx_widgets_active
    ON widgets (id)
    WHERE deleted_at IS NULL;

-- Status filter (common filter in list queries)
CREATE INDEX idx_widgets_tenant_status
    ON widgets (tenant_id, status)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- Row-Level Security (Multi-Tenant Isolation)
-- =============================================================================

-- Enable RLS on the table
ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;

-- FORCE: the policy applies to the table owner too (superusers and BYPASSRLS roles still skip it)
ALTER TABLE widgets FORCE ROW LEVEL SECURITY;

-- Policy: tenant can only see/modify their own rows
-- The application sets app.current_tenant_id inside each transaction (WithTenantTx, below)
CREATE POLICY tenant_isolation ON widgets
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- The migrator's policy (widgets_migrator_all, TO the owner only): seeds and backfills see every tenant
SELECT app_grant_migrator('widgets');

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

-- Drop RLS policies (must drop before table)
DROP POLICY IF EXISTS widgets_migrator_all ON widgets;
DROP POLICY IF EXISTS tenant_isolation ON widgets;

-- Drop indexes explicitly (for clarity, though DROP TABLE handles them)
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

-- The migrator-policy helper was created by this (the first) migration
DROP FUNCTION IF EXISTS app_grant_migrator(regclass);

COMMIT;
```

## Foreign Key Table Pattern

```sql
-- Migration: 20260115100100_add_widget_categories.up.sql
-- Purpose: Add categories with foreign key relationship to widgets

BEGIN;

CREATE TABLE widget_categories (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL,
    name        VARCHAR(255)  NOT NULL,
    slug        VARCHAR(255)  NOT NULL,
    description VARCHAR(2000) NOT NULL DEFAULT '',
    sort_order  INT           NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_widget_categories_tenant_slug
    ON widget_categories (tenant_id, lower(slug))
    WHERE deleted_at IS NULL;

-- Add category_id to widgets with ON DELETE SET NULL (don't cascade delete widgets). Creating a
-- foreign key runs a validation query that reads widgets as the owner; FORCE ROW LEVEL SECURITY
-- applies to it, and widgets_migrator_all (first migration) lets it see every row. No FORCE lifting.
ALTER TABLE widgets ADD COLUMN category_id UUID;
ALTER TABLE widgets
    ADD CONSTRAINT fk_widgets_category
        FOREIGN KEY (category_id) REFERENCES widget_categories(id) ON DELETE SET NULL;

CREATE INDEX idx_widgets_category
    ON widgets (category_id)
    WHERE deleted_at IS NULL AND category_id IS NOT NULL;

-- RLS for categories: tenant policy + the migrator's policy, in the migration that creates the table
ALTER TABLE widget_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE widget_categories FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON widget_categories
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

SELECT app_grant_migrator('widget_categories');

COMMIT;
```

```sql
-- Migration: 20260115100100_add_widget_categories.down.sql
BEGIN;

DROP INDEX IF EXISTS idx_widgets_category;
ALTER TABLE widgets DROP CONSTRAINT IF EXISTS fk_widgets_category;
ALTER TABLE widgets DROP COLUMN IF EXISTS category_id;

DROP POLICY IF EXISTS widget_categories_migrator_all ON widget_categories;
DROP POLICY IF EXISTS tenant_isolation ON widget_categories;
DROP INDEX IF EXISTS idx_widget_categories_tenant_slug;
DROP TABLE IF EXISTS widget_categories;

COMMIT;
```

## Seed Data Migration

```sql
-- Migration: 20260115100200_seed_default_categories.up.sql
-- Purpose: Insert default categories for every tenant that has widgets
-- NOTE: Seed data is SEPARATE from schema migrations

BEGIN;

-- These samples have no tenants table: the tenants are the ones that have widgets. If your schema
-- has a tenants table, select the tenants from it instead.
-- The migrator runs this with FORCE ROW LEVEL SECURITY on; its migrator policies (widgets_migrator_all,
-- widget_categories_migrator_all) let it read and write every tenant's rows. No tenant is set.

-- Uses ON CONFLICT to make the migration idempotent (safe to re-run)
INSERT INTO widget_categories (id, tenant_id, name, slug, description, sort_order, created_at, updated_at)
SELECT
    gen_random_uuid(),
    t.tenant_id,
    category.name,
    category.slug,
    category.description,
    category.sort_order,
    NOW(),
    NOW()
FROM (SELECT DISTINCT tenant_id FROM widgets) AS t
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

-- Remove only the seeded default categories (by slug), every tenant's (the migrator policy)
DELETE FROM widget_categories
WHERE slug IN ('general', 'internal', 'customer', 'deprecated');

COMMIT;
```

## Data Migration Pattern (Backfill / Transform)

```sql
-- Migration: 20260115100300_backfill_widget_category.up.sql
-- Purpose: Put every existing widget in its tenant's "general" category
--
-- IMPORTANT: For tables with > 100K rows, run this in batches to avoid long locks (below).

BEGIN;

-- Small tables (< 100K rows): single UPDATE across every tenant, FORCE left on: the migrator's
-- policies let it see all rows (see "Who runs migrations")
UPDATE widgets w
SET category_id = c.id, updated_at = NOW()
FROM widget_categories c
WHERE c.tenant_id = w.tenant_id AND c.slug = 'general' AND c.deleted_at IS NULL
  AND w.category_id IS NULL AND w.deleted_at IS NULL;

COMMIT;

-- ============================================================================
-- LARGE TABLE ALTERNATIVE: batches, each its own short transaction, so no lock is held for the
-- whole run. A DO block may COMMIT between batches (PostgreSQL 11+) when it runs outside a
-- transaction block: make it the ONLY statement in its migration file (no BEGIN/COMMIT) —
-- golang-migrate sends the file as one statement. FORCE stays on: the migrator's policies let each
-- batch reach every tenant, and no batch takes an ACCESS EXCLUSIVE lock.
-- ============================================================================
--
-- DO $$
-- DECLARE
--     updated integer;
-- BEGIN
--     LOOP
--         UPDATE widgets w
--         SET category_id = c.id, updated_at = NOW()
--         FROM widget_categories c
--         WHERE c.tenant_id = w.tenant_id AND c.slug = 'general' AND c.deleted_at IS NULL
--           AND w.id IN (
--               SELECT w2.id
--               FROM widgets w2
--               JOIN widget_categories c2
--                 ON c2.tenant_id = w2.tenant_id AND c2.slug = 'general' AND c2.deleted_at IS NULL
--               WHERE w2.category_id IS NULL AND w2.deleted_at IS NULL
--               LIMIT 5000
--               FOR UPDATE OF w2 SKIP LOCKED
--           );
--         GET DIAGNOSTICS updated = ROW_COUNT;
--         COMMIT;
--         EXIT WHEN updated = 0;
--     END LOOP;
-- END $$;
```

```sql
-- Migration: 20260115100300_backfill_widget_category.down.sql
-- Reverting a backfill is generally not safe: rows that chose "general" themselves since can't be
-- told apart. Intentionally a no-op; the previous migration's down drops the column anyway.
SELECT 1;
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
    "errors"
    "fmt"
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
    // m.Close also closes db (postgres.WithInstance takes it over), so give the migrator a *sql.DB of
    // its own — the migrate job's — never the application's pool.
    defer func() { _, _ = m.Close() }()

    if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
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
// WithTenantTx runs fn in a transaction with the RLS tenant set. The setting MUST live in the same
// transaction as the queries: set_config(..., true) is transaction-local, so issued as a bare
// pool.Exec it ends with that statement's own implicit transaction — and the next query may run on
// another pooled connection anyway. Run every tenant-scoped query through here.
func WithTenantTx(ctx context.Context, pool *pgxpool.Pool, tenantID uuid.UUID, fn func(pgx.Tx) error) error {
    tx, err := pool.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer func() { _ = tx.Rollback(ctx) }() // no-op after a successful Commit

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

## Testing Migrations — Up, Down, Round Trip

```go
// cmd/migrate/migrate_test.go — runs the embedded migrations (migrationsFS, above) against a real
// PostgreSQL as a NON-superuser table owner without BYPASSRLS, the way the migrator runs on RDS/Aurora
// (the stricter of the two deploy paths). A superuser skips row-level security, which hides every
// migration that breaks under FORCE ROW LEVEL SECURITY. It catches: missing or wrong DOWN migrations,
// foreign-key ordering, a tenant table without its migrator policy (decision D-001: data migrations
// then fail, or silently update nothing), and a migrator policy that leaks to the app role.
package main

import (
    "context"
    "database/sql"
    "errors"
    "fmt"
    "io/fs"
    "slices"
    "testing"
    "time"

    "github.com/golang-migrate/migrate/v4"
    "github.com/golang-migrate/migrate/v4/database/postgres"
    "github.com/golang-migrate/migrate/v4/source/iofs"
    "github.com/google/uuid"
    "github.com/jackc/pgx/v5/pgconn"
    _ "github.com/jackc/pgx/v5/stdlib" // registers the "pgx" database/sql driver
    "github.com/testcontainers/testcontainers-go"
    tcpostgres "github.com/testcontainers/testcontainers-go/modules/postgres"
    "github.com/testcontainers/testcontainers-go/wait"
)

const (
    owner   = "app_owner"   // owns the schema and runs the migrations: NOSUPERUSER NOBYPASSRLS (RDS migrator)
    runtime = "app_runtime" // the application: owns nothing, NOSUPERUSER NOBYPASSRLS
)

// schemaVersion is the last schema migration, before the seed and the backfill.
const schemaVersion = 20260115100100

// ownerDSN starts PostgreSQL, creates the owner role, a database it owns and the app role, and returns
// DSNs that connect as the owner and as the app role.
func ownerDSN(t *testing.T) (string, string) {
    t.Helper()
    ctx := context.Background()
    pg, err := tcpostgres.Run(ctx, "postgres:16-alpine",
        tcpostgres.WithDatabase("postgres"),
        tcpostgres.WithUsername("postgres"),
        tcpostgres.WithPassword("postgres"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2).WithStartupTimeout(30*time.Second),
        ),
    )
    if err != nil {
        t.Fatalf("start postgres: %v", err)
    }
    t.Cleanup(func() { _ = testcontainers.TerminateContainer(pg) })

    superDSN, err := pg.ConnectionString(ctx, "sslmode=disable")
    if err != nil {
        t.Fatal(err)
    }
    super, err := sql.Open("pgx", superDSN)
    if err != nil {
        t.Fatal(err)
    }
    defer super.Close()

    password := uuid.NewString() // throwaway, per run (CREATE ROLE takes no bind parameters)
    for _, stmt := range []string{
        fmt.Sprintf("CREATE ROLE %s LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '%s'", owner, password),
        fmt.Sprintf("CREATE ROLE %s LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '%s'", runtime, password),
        "CREATE DATABASE migrations_test OWNER " + owner,
    } {
        if _, err := super.ExecContext(ctx, stmt); err != nil {
            t.Fatalf("%s: %v", stmt, err)
        }
    }
    host, err := pg.Host(ctx)
    if err != nil {
        t.Fatal(err)
    }
    port, err := pg.MappedPort(ctx, "5432/tcp")
    if err != nil {
        t.Fatal(err)
    }
    dsn := func(role string) string {
        return fmt.Sprintf("postgres://%s:%s@%s:%s/migrations_test?sslmode=disable", role, password, host, port.Port())
    }
    return dsn(owner), dsn(runtime)
}

func openDB(t *testing.T, dsn string) *sql.DB {
    t.Helper()
    db, err := sql.Open("pgx", dsn)
    if err != nil {
        t.Fatal(err)
    }
    t.Cleanup(func() { _ = db.Close() })
    return db
}

// newMigrator returns a migrator over the embedded migrations, on a *sql.DB of its own (m.Close
// closes it).
func newMigrator(t *testing.T, dsn string) *migrate.Migrate {
    t.Helper()
    db, err := sql.Open("pgx", dsn)
    if err != nil {
        t.Fatal(err)
    }
    source, err := iofs.New(migrationsFS, "migrations")
    if err != nil {
        t.Fatal(err)
    }
    driver, err := postgres.WithInstance(db, &postgres.Config{})
    if err != nil {
        t.Fatal(err)
    }
    m, err := migrate.NewWithInstance("iofs", source, "postgres", driver)
    if err != nil {
        t.Fatal(err)
    }
    t.Cleanup(func() { _, _ = m.Close() })
    return m
}

// versions lists the migration versions, oldest first.
func versions(t *testing.T) []uint {
    t.Helper()
    source, err := iofs.New(migrationsFS, "migrations")
    if err != nil {
        t.Fatal(err)
    }
    var out []uint
    v, err := source.First()
    for err == nil {
        out = append(out, v)
        v, err = source.Next(v)
    }
    if !errors.Is(err, fs.ErrNotExist) {
        t.Fatal(err)
    }
    return out
}

func must(t *testing.T, err error) {
    t.Helper()
    if err != nil && !errors.Is(err, migrate.ErrNoChange) {
        t.Fatal(err)
    }
}

func TestMigrations(t *testing.T) {
    dsn, appDSN := ownerDSN(t)
    m := newMigrator(t, dsn)

    t.Run("up, down, up again", func(t *testing.T) {
        must(t, m.Up())
        must(t, m.Down())
        must(t, m.Up())
    })

    t.Run("each migration applies, reverses and re-applies", func(t *testing.T) {
        must(t, m.Down())
        for _, v := range versions(t) {
            must(t, m.Migrate(v))
            must(t, m.Steps(-1))
            must(t, m.Migrate(v))
        }
    })

    t.Run("seed and backfill work under FORCE ROW LEVEL SECURITY", func(t *testing.T) {
        must(t, m.Down())
        must(t, m.Migrate(schemaVersion))
        db := openDB(t, dsn)
        tenants := []uuid.UUID{uuid.New(), uuid.New()}
        for _, tenant := range tenants {
            insertWidget(t, db, tenant)
        }

        must(t, m.Up())

        // FORCE stayed on throughout; the owner saw every tenant through its migrator policy (D-001).
        var n int
        if err := db.QueryRow("SELECT count(*) FROM widgets WHERE category_id IS NOT NULL").Scan(&n); err != nil || n != len(tenants) {
            t.Fatalf("owner, no tenant set: %d categorized widgets, %v; want %d (its migrator policy)", n, err, len(tenants))
        }

        // Read the result as the app role (the deployed service), which the migrator policy must not
        // reach: each tenant sees exactly its own four categories and no uncategorized widget.
        if _, err := db.Exec("GRANT SELECT ON widgets, widget_categories TO " + runtime); err != nil {
            t.Fatal(err)
        }
        app := openDB(t, appDSN)
        for _, tenant := range tenants {
            slugs, uncategorized := tenantState(t, app, tenant)
            if !slices.Equal(slugs, []string{"customer", "deprecated", "general", "internal"}) || uncategorized != 0 {
                t.Errorf("tenant %s: categories %v, %d uncategorized widgets", tenant, slugs, uncategorized)
            }
        }

        // Without a tenant the app role is refused, not shown every row. The error is 42704
        // (undefined_object) on a connection that never set the tenant, and 22P02 ('' is not a UUID)
        // on a pooled one whose earlier transaction-local set_config left the setting empty.
        err := app.QueryRow("SELECT count(*) FROM widgets").Scan(&n)
        var pgErr *pgconn.PgError
        if !errors.As(err, &pgErr) || (pgErr.Code != "42704" && pgErr.Code != "22P02") {
            t.Fatalf("app role, no tenant: count = %d, %v; want it refused (42704 or 22P02)", n, err)
        }
    })
}

// insertWidget writes one widget the way the application does under RLS: in a transaction that
// names its tenant (WithTenantTx).
func insertWidget(t *testing.T, db *sql.DB, tenant uuid.UUID) {
    t.Helper()
    tx, err := db.Begin()
    if err != nil {
        t.Fatal(err)
    }
    defer func() { _ = tx.Rollback() }()
    if _, err := tx.Exec("SELECT set_config('app.current_tenant_id', $1, true)", tenant.String()); err != nil {
        t.Fatal(err)
    }
    user := uuid.New()
    if _, err := tx.Exec("INSERT INTO widgets (tenant_id, name, created_by, updated_by) VALUES ($1, $2, $3, $3)",
        tenant, "widget-"+uuid.NewString()[:8], user); err != nil {
        t.Fatal(err)
    }
    if err := tx.Commit(); err != nil {
        t.Fatal(err)
    }
}

// tenantState returns the tenant's category slugs and how many of its widgets have no category.
func tenantState(t *testing.T, db *sql.DB, tenant uuid.UUID) ([]string, int) {
    t.Helper()
    tx, err := db.Begin()
    if err != nil {
        t.Fatal(err)
    }
    defer func() { _ = tx.Rollback() }()
    if _, err := tx.Exec("SELECT set_config('app.current_tenant_id', $1, true)", tenant.String()); err != nil {
        t.Fatal(err)
    }
    rows, err := tx.Query("SELECT slug FROM widget_categories ORDER BY slug")
    if err != nil {
        t.Fatal(err)
    }
    var slugs []string
    for rows.Next() {
        var s string
        if err := rows.Scan(&s); err != nil {
            t.Fatal(err)
        }
        slugs = append(slugs, s)
    }
    if err := rows.Err(); err != nil {
        t.Fatal(err)
    }
    var uncategorized int
    if err := tx.QueryRow("SELECT count(*) FROM widgets WHERE category_id IS NULL").Scan(&uncategorized); err != nil {
        t.Fatal(err)
    }
    return slugs, uncategorized
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
- Every table MUST have `tenant_id` (with a foreign key to `tenants` if your schema has that table)
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
- JSONB columns MUST have a GIN index if they will be queried (when you add one)
- Table and column comments MUST be added for documentation
- The first migration creates `app_grant_migrator(regclass)`; every migration that creates a `FORCE ROW LEVEL SECURITY` table calls `SELECT app_grant_migrator('<table>')` (decision D-001), so the migrator, with or without `BYPASSRLS`, reaches every tenant in data migrations, seeds and foreign-key validation
- Never lift `FORCE` in a migration (`NO FORCE` takes an `ACCESS EXCLUSIVE` lock), and never write an unconditional (`USING (true)`) policy for any role but the table owner: one `TO PUBLIC` or `TO` the app role hands the application every tenant's rows (BLOCKING in review; the deploy's `db-rls-check` fails on it)
- Migration tests run as a non-superuser owner without `BYPASSRLS` (the RDS migrator; a superuser skips RLS and hides these failures), cover up, down and re-up for every version, and prove the app role still sees only its tenant
