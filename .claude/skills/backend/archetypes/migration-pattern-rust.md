---
skill: migration-pattern-rust
description: Rust sqlx migration archetype — CLI usage, embedded migrations (sqlx::migrate!), UP/DOWN files, reversible migrations, data migrations, testing, CI integration with sqlx prepare for offline mode
version: "1.0"
tags:
  - rust
  - sqlx
  - migration
  - postgres
  - database
  - archetype
  - backend
---

# Migration Pattern Archetype (Rust / sqlx)

Complete database migration patterns for sqlx-based Rust projects. Every generated project MUST follow these patterns.

## Dependencies (Cargo.toml)

```toml
[dependencies]
sqlx = { version = "0.8", features = [
    "runtime-tokio",
    "tls-rustls",
    "postgres",
    "migrate",
    "uuid",
    "chrono",
    "json",
] }

[dev-dependencies]
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "migrate"] }
```

## Directory Structure

```
migrations/
  20240101000000_create_widgets.sql         <- forward-only (simple)
  20240102000000_add_status_column.up.sql   <- reversible (up)
  20240102000000_add_status_column.down.sql <- reversible (down)
  20240103000000_seed_statuses.sql          <- data migration
  20240104000000_add_index.sql              <- index migration
```

Rule: Migration files MUST be named with a timestamp prefix `YYYYMMDDHHMMSS_description`. sqlx sorts by filename, so timestamps ensure correct ordering.

## CLI Usage

```bash
# Install sqlx-cli
cargo install sqlx-cli --no-default-features --features rustls,postgres

# Create a new migration (forward-only)
sqlx migrate add create_widgets

# Create a reversible migration (generates .up.sql and .down.sql)
sqlx migrate add -r add_status_column

# Run all pending migrations
sqlx migrate run --database-url "$DATABASE_URL"

# Revert the last migration (only works for reversible migrations)
sqlx migrate revert --database-url "$DATABASE_URL"

# Show migration status
sqlx migrate info --database-url "$DATABASE_URL"
```

## Embedded Migrations (Production)

```rust
// src/db.rs

use sqlx::PgPool;
use crate::error::AppError;

/// Run embedded migrations at application startup.
///
/// The `sqlx::migrate!()` macro embeds all migration SQL files at compile time.
/// This ensures the binary always contains the correct migrations — no need to
/// ship migration files alongside the binary.
pub async fn run_migrations(pool: &PgPool) -> Result<(), AppError> {
    tracing::info!("running database migrations");

    sqlx::migrate!("./migrations")
        .run(pool)
        .await
        .map_err(|e| {
            tracing::error!(error = %e, "migration failed");
            AppError::Internal(format!("migration failed: {e}").into())
        })?;

    tracing::info!("migrations completed successfully");
    Ok(())
}

/// Usage in main.rs:
///
/// ```rust
/// #[tokio::main]
/// async fn main() -> Result<(), Box<dyn std::error::Error>> {
///     let pool = PgPool::connect(&database_url).await?;
///     crate::db::run_migrations(&pool).await?;
///     // ... start server
/// }
/// ```
```

## Migration: Create Table

```sql
-- migrations/20240101000000_create_widgets.sql

-- Create the widgets table with all standard fields.
-- This is a forward-only migration (no .down.sql).

CREATE TABLE IF NOT EXISTS widgets (
    id          UUID PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    status      VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    created_by  UUID NOT NULL,
    updated_by  UUID NOT NULL,
    version     INT NOT NULL DEFAULT 1,

    -- Multi-tenant isolation: every query filters by tenant_id.
    -- Composite unique constraint scoped to tenant.
    CONSTRAINT uq_widgets_tenant_name UNIQUE (tenant_id, name)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_id ON widgets (tenant_id);
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_status ON widgets (tenant_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_created ON widgets (tenant_id, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_name_search ON widgets (tenant_id, name)
    WHERE deleted_at IS NULL;

-- Soft delete partial index: most queries filter deleted_at IS NULL.
-- This index covers only active rows, making it smaller and faster.
```

## Migration: Add Column (Reversible)

```sql
-- migrations/20240102000000_add_priority_column.up.sql

ALTER TABLE widgets
    ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'medium';

-- Backfill existing rows
UPDATE widgets SET priority = 'medium' WHERE priority IS NULL;

-- Add index for filtering by priority
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_priority
    ON widgets (tenant_id, priority)
    WHERE deleted_at IS NULL;
```

```sql
-- migrations/20240102000000_add_priority_column.down.sql

DROP INDEX IF EXISTS idx_widgets_tenant_priority;
ALTER TABLE widgets DROP COLUMN IF EXISTS priority;
```

## Migration: Add Index (Concurrently)

```sql
-- migrations/20240103000000_add_search_index.sql

-- IMPORTANT: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
-- sqlx wraps migrations in transactions by default.
-- To use CONCURRENTLY, you must:
--   1. Run this migration manually outside sqlx, OR
--   2. Use a non-transactional migration (see below).

-- For sqlx, use regular CREATE INDEX (locks the table briefly):
CREATE INDEX IF NOT EXISTS idx_widgets_name_trgm
    ON widgets USING gin (name gin_trgm_ops)
    WHERE deleted_at IS NULL;

-- If downtime is unacceptable on large tables, run this manually:
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_widgets_name_trgm
--     ON widgets USING gin (name gin_trgm_ops)
--     WHERE deleted_at IS NULL;
```

## Migration: Data Migration

```sql
-- migrations/20240104000000_migrate_status_values.sql

-- Data migration: rename status values.
-- Always idempotent — safe to run multiple times.

UPDATE widgets
SET status = 'active'
WHERE status = 'enabled'
  AND deleted_at IS NULL;

UPDATE widgets
SET status = 'archived'
WHERE status = 'disabled'
  AND deleted_at IS NULL;

-- Log the migration for audit
INSERT INTO _migration_audit (migration_name, rows_affected, executed_at)
VALUES (
    '20240104000000_migrate_status_values',
    (SELECT COUNT(*) FROM widgets WHERE status IN ('active', 'archived')),
    NOW()
)
ON CONFLICT (migration_name) DO NOTHING;
```

## Migration: Create Enum Type

```sql
-- migrations/20240105000000_create_widget_status_enum.up.sql

-- Create a PostgreSQL enum type for widget status.
-- Prefer CHECK constraints for simple cases; use enums when the type
-- is shared across multiple tables.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'widget_status') THEN
        CREATE TYPE widget_status AS ENUM ('active', 'archived', 'draft', 'deleted');
    END IF;
END
$$;

-- Migrate the column from VARCHAR to enum
ALTER TABLE widgets
    ALTER COLUMN status TYPE widget_status
    USING status::widget_status;
```

```sql
-- migrations/20240105000000_create_widget_status_enum.down.sql

ALTER TABLE widgets
    ALTER COLUMN status TYPE VARCHAR(50)
    USING status::text;

DROP TYPE IF EXISTS widget_status;
```

## Migration: Add Foreign Key

```sql
-- migrations/20240106000000_create_components.up.sql

CREATE TABLE IF NOT EXISTS components (
    id          UUID PRIMARY KEY,
    widget_id   UUID NOT NULL,
    tenant_id   UUID NOT NULL,
    name        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    version     INT NOT NULL DEFAULT 1,

    -- Foreign key with ON DELETE CASCADE ensures child rows are
    -- automatically removed when the parent is hard-deleted.
    -- For soft delete, the application layer handles cascading.
    CONSTRAINT fk_components_widget
        FOREIGN KEY (widget_id) REFERENCES widgets (id)
        ON DELETE CASCADE,

    -- Ensure component belongs to the same tenant as its parent widget.
    CONSTRAINT uq_components_tenant_name
        UNIQUE (widget_id, tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_components_widget_id
    ON components (widget_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_components_tenant_id
    ON components (tenant_id)
    WHERE deleted_at IS NULL;
```

```sql
-- migrations/20240106000000_create_components.down.sql

DROP TABLE IF EXISTS components;
```

## Migration: Audit Trail Table

```sql
-- migrations/20240107000000_create_audit_log.sql

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id   UUID NOT NULL,
    tenant_id   UUID NOT NULL,
    actor_id    UUID NOT NULL,
    changes     JSONB,
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partition by month for large-scale audit logs (optional).
-- CREATE TABLE audit_log (...) PARTITION BY RANGE (created_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_entity
    ON audit_log (tenant_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created
    ON audit_log (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor_id, created_at DESC);
```

## Testing Migrations

```rust
#[cfg(test)]
mod tests {
    use sqlx::PgPool;

    /// Verify that all migrations run successfully on a clean database.
    /// sqlx::test creates a fresh database, runs migrations, and drops it after.
    #[sqlx::test(migrations = "./migrations")]
    async fn migrations_run_cleanly(pool: PgPool) {
        // If we reach here, all migrations ran successfully.
        // Verify the expected tables exist.
        let tables: Vec<(String,)> = sqlx::query_as(
            "SELECT table_name::text FROM information_schema.tables \
             WHERE table_schema = 'public' AND table_type = 'BASE TABLE' \
             ORDER BY table_name"
        )
        .fetch_all(&pool)
        .await
        .expect("failed to query tables");

        let table_names: Vec<&str> = tables.iter().map(|t| t.0.as_str()).collect();
        assert!(table_names.contains(&"widgets"), "widgets table must exist");
        assert!(
            table_names.contains(&"_sqlx_migrations"),
            "migration tracking table must exist"
        );
    }

    /// Verify that the widgets table has all expected columns.
    #[sqlx::test(migrations = "./migrations")]
    async fn widgets_table_has_expected_columns(pool: PgPool) {
        let columns: Vec<(String,)> = sqlx::query_as(
            "SELECT column_name::text FROM information_schema.columns \
             WHERE table_name = 'widgets' ORDER BY ordinal_position"
        )
        .fetch_all(&pool)
        .await
        .unwrap();

        let col_names: Vec<&str> = columns.iter().map(|c| c.0.as_str()).collect();
        let expected = [
            "id", "tenant_id", "name", "description", "status",
            "created_at", "updated_at", "deleted_at",
            "created_by", "updated_by", "version",
        ];
        for col in &expected {
            assert!(col_names.contains(col), "missing column: {col}");
        }
    }

    /// Verify unique constraints work.
    #[sqlx::test(migrations = "./migrations")]
    async fn unique_constraint_on_tenant_name(pool: PgPool) {
        let tenant_id = uuid::Uuid::new_v4();
        let user_id = uuid::Uuid::new_v4();
        let now = chrono::Utc::now();

        sqlx::query!(
            "INSERT INTO widgets (id, tenant_id, name, status, created_at, updated_at, created_by, updated_by, version) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            uuid::Uuid::new_v4(), tenant_id, "Unique Name", "active", now, now, user_id, user_id, 1_i32,
        )
        .execute(&pool)
        .await
        .expect("first insert should succeed");

        let result = sqlx::query!(
            "INSERT INTO widgets (id, tenant_id, name, status, created_at, updated_at, created_by, updated_by, version) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            uuid::Uuid::new_v4(), tenant_id, "Unique Name", "active", now, now, user_id, user_id, 1_i32,
        )
        .execute(&pool)
        .await;

        assert!(result.is_err(), "duplicate (tenant_id, name) must fail");
    }

    /// Verify indexes exist.
    #[sqlx::test(migrations = "./migrations")]
    async fn expected_indexes_exist(pool: PgPool) {
        let indexes: Vec<(String,)> = sqlx::query_as(
            "SELECT indexname::text FROM pg_indexes WHERE tablename = 'widgets'"
        )
        .fetch_all(&pool)
        .await
        .unwrap();

        let idx_names: Vec<&str> = indexes.iter().map(|i| i.0.as_str()).collect();
        assert!(
            idx_names.contains(&"idx_widgets_tenant_id"),
            "tenant_id index must exist"
        );
    }
}
```

## CI Integration: Offline Mode with `sqlx prepare`

```bash
#!/usr/bin/env bash
# scripts/sqlx-prepare.sh
# Run this before committing to generate offline query metadata.

set -euo pipefail

# 1. Ensure a running PostgreSQL instance
export DATABASE_URL="${DATABASE_URL:-postgres://postgres:postgres@localhost:5432/sqlx_prepare}"

# 2. Create the database if it does not exist
psql "$DATABASE_URL" -c "SELECT 1" 2>/dev/null || createdb -U postgres sqlx_prepare

# 3. Run migrations to bring schema up to date
cargo sqlx migrate run

# 4. Generate offline query data
# This creates .sqlx/ directory with JSON files for each compile-time-checked query.
cargo sqlx prepare -- --all-targets --all-features

# 5. Verify the prepared data is correct
cargo sqlx prepare --check -- --all-targets --all-features

echo "sqlx offline data generated successfully. Commit the .sqlx/ directory."
```

```yaml
# .github/workflows/ci.yml (relevant section)

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install sqlx-cli
        run: cargo install sqlx-cli --no-default-features --features rustls,postgres

      - name: Verify sqlx offline data
        run: cargo sqlx prepare --check -- --all-targets --all-features
        env:
          SQLX_OFFLINE: true

      - name: Build (offline mode — no database needed)
        run: cargo build --release
        env:
          SQLX_OFFLINE: true

      - name: Run unit tests
        run: cargo test --lib
        env:
          SQLX_OFFLINE: true

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Run integration tests
        run: cargo test --test '*'
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/test
```

## .sqlx Directory (Offline Query Cache)

```
.sqlx/
  query-abc123def456.json   <- cached metadata for each sqlx::query!() call
  query-789ghi012jkl.json
  ...
```

```gitignore
# .gitignore — DO commit .sqlx/ for offline builds
# If using sqlx::query!() compile-time checks:
# .sqlx/     <- DO NOT add this line; .sqlx/ must be committed
```

## Migration Best Practices

```
1. ALWAYS use IF NOT EXISTS / IF EXISTS for idempotency.
2. NEVER rename columns in a single migration — add new, copy data, drop old (3 migrations).
3. NEVER drop columns in the same release they are removed from code.
   Deploy code that stops reading the column first, then drop it next release.
4. ALWAYS add new columns with DEFAULT values to avoid full table rewrites.
5. ALWAYS add indexes on foreign keys — PostgreSQL does not auto-index FKs.
6. PREFER partial indexes (WHERE deleted_at IS NULL) for soft-delete tables.
7. KEEP migrations small — one logical change per migration file.
8. NEVER modify an existing migration after it has been applied.
   Create a new migration to fix issues.
9. TEST migrations in CI against a real PostgreSQL instance.
10. COMMIT the .sqlx/ directory for offline compile-time query checking.
```

## Critical Rules

- Every migration MUST be idempotent — use `IF NOT EXISTS` / `IF EXISTS`
- Every migration MUST include tenant_id in all new table schemas and indexes
- Reversible migrations MUST have matching `.up.sql` and `.down.sql` files
- Data migrations MUST be idempotent — use `WHERE` clauses to prevent double-application
- Never modify an already-applied migration — create a new one instead
- Column renames MUST be done across 3 migrations: add new, copy data, drop old
- Column drops MUST happen in a release AFTER code stops using the column
- New columns MUST have DEFAULT values to avoid long-running table rewrites
- Indexes on foreign keys MUST be created explicitly
- `cargo sqlx prepare` MUST be run before committing query changes
- `.sqlx/` directory MUST be committed for offline CI builds
- `SQLX_OFFLINE=true` MUST be set in CI for builds without a database
- `CREATE INDEX CONCURRENTLY` cannot be used inside sqlx migrations (they run in transactions)
