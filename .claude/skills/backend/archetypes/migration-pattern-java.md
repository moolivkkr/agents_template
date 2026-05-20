---
skill: migration-pattern-java
description: Flyway migration archetype — SQL naming conventions, repeatable migrations, Java-based migrations, rollback patterns, seed data, multi-tenant schema, @FlywayTest integration
version: "1.0"
tags:
  - java
  - spring-boot
  - flyway
  - migration
  - sql
  - postgres
  - archetype
  - backend
---

# Flyway Migration Pattern Archetype (Spring Boot)

Complete, production-ready Flyway migration template for Spring Boot projects. Every generated migration MUST follow this pattern.

## Flyway Configuration (application.yml)

```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
    baseline-version: "0"
    validate-on-migrate: true
    out-of-order: false
    clean-disabled: true          # CRITICAL: prevent accidental clean in production
    table: flyway_schema_history
    connect-retries: 3
    default-schema: public

  jpa:
    hibernate:
      ddl-auto: validate          # Flyway manages schema; Hibernate only validates
    properties:
      hibernate:
        format_sql: true
        jdbc:
          time_zone: UTC
```

```yaml
# Profile-specific overrides
---
spring:
  config:
    activate:
      on-profile: local
  flyway:
    clean-disabled: false         # Allow clean in local dev only
    locations: classpath:db/migration,classpath:db/seed
---
spring:
  config:
    activate:
      on-profile: test
  flyway:
    clean-disabled: false
    locations: classpath:db/migration,classpath:db/testdata
```

## Directory Structure

```
src/main/resources/db/
  migration/
    V1__create_widgets_table.sql
    V2__add_widget_categories.sql
    V3__add_widget_tags_table.sql
    V4__backfill_widget_status.sql
    R__create_views.sql                    # Repeatable migration
  seed/
    V1000__seed_default_categories.sql     # Seed data for local dev
  callback/
    afterMigrate__seed_demo_data.sql       # Callback script
src/main/java/com/example/app/migration/
    V5__ComplexDataMigration.java          # Java-based migration
src/test/resources/db/
  testdata/
    V9000__seed_test_data.sql              # Test-only seed data
```

## Naming Convention

| Type | Pattern | Example |
|------|---------|---------|
| Versioned | `V{version}__{description}.sql` | `V1__create_widgets_table.sql` |
| Repeatable | `R__{description}.sql` | `R__create_views.sql` |
| Seed data | `V{high_number}__{description}.sql` | `V1000__seed_default_categories.sql` |
| Java-based | `V{version}__{Description}.java` | `V5__ComplexDataMigration.java` |

Rules:
- Double underscore `__` separates version from description
- Description uses `snake_case`, starts with verb: `create_`, `add_`, `alter_`, `drop_`, `backfill_`, `seed_`
- Version numbers are monotonically increasing integers
- Seed data uses high version numbers (1000+) to run after all schema migrations
- Schema migrations and seed data are SEPARATE files
- Each migration is a single atomic operation

## V1 — Table Creation

```sql
-- V1__create_widgets_table.sql
-- Purpose: Create the widgets table with standard columns, indexes, and constraints

-- ============================================================================
-- Table: widgets
-- ============================================================================

CREATE TABLE IF NOT EXISTS widgets (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID            NOT NULL,
    name        VARCHAR(255)    NOT NULL,
    description VARCHAR(2000),
    status      VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',
    config      JSONB           NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    created_by  UUID            NOT NULL,
    updated_by  UUID            NOT NULL,
    version     INTEGER         NOT NULL DEFAULT 0,

    CONSTRAINT chk_widgets_status
        CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED'))
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Tenant isolation: EVERY query filters by tenant_id
CREATE INDEX idx_widgets_tenant_id
    ON widgets (tenant_id)
    WHERE deleted_at IS NULL;

-- Composite index for list queries: tenant + sort + pagination
CREATE INDEX idx_widgets_tenant_created
    ON widgets (tenant_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;

-- Unique name per tenant (case-insensitive, only active records)
CREATE UNIQUE INDEX idx_widgets_tenant_name_unique
    ON widgets (tenant_id, LOWER(name))
    WHERE deleted_at IS NULL;

-- Status filter index
CREATE INDEX idx_widgets_tenant_status
    ON widgets (tenant_id, status)
    WHERE deleted_at IS NULL;

-- GIN index for JSONB config column
CREATE INDEX idx_widgets_config_gin
    ON widgets USING GIN (config);

-- ============================================================================
-- Trigger: auto-update updated_at
-- ============================================================================

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

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE widgets IS 'Core widget entities — multi-tenant, soft-deletable';
COMMENT ON COLUMN widgets.tenant_id IS 'Owning tenant — all queries MUST filter by this';
COMMENT ON COLUMN widgets.status IS 'Lifecycle status: ACTIVE, INACTIVE, ARCHIVED';
COMMENT ON COLUMN widgets.deleted_at IS 'Soft delete timestamp — NULL means active';
COMMENT ON COLUMN widgets.version IS 'Optimistic lock counter — JPA @Version auto-increments';
```

## V2 — Alter Table (Add Column)

```sql
-- V2__add_widget_categories.sql
-- Purpose: Add categories with foreign key to widgets

CREATE TABLE IF NOT EXISTS widget_categories (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID            NOT NULL,
    name        VARCHAR(100)    NOT NULL,
    slug        VARCHAR(100)    NOT NULL,
    sort_order  INTEGER         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_widget_categories_tenant_slug
    ON widget_categories (tenant_id, LOWER(slug))
    WHERE deleted_at IS NULL;

-- Add category_id to widgets
ALTER TABLE widgets
    ADD COLUMN IF NOT EXISTS category_id UUID;

ALTER TABLE widgets
    ADD CONSTRAINT fk_widgets_category
        FOREIGN KEY (category_id) REFERENCES widget_categories(id) ON DELETE SET NULL;

CREATE INDEX idx_widgets_category
    ON widgets (category_id)
    WHERE deleted_at IS NULL AND category_id IS NOT NULL;
```

## Repeatable Migration

```sql
-- R__create_views.sql
-- Purpose: Recreatable views — Flyway re-runs this whenever the checksum changes
-- Useful for views, functions, and stored procedures that can be safely replaced

CREATE OR REPLACE VIEW widget_stats AS
SELECT
    tenant_id,
    status,
    COUNT(*) AS count,
    MAX(created_at) AS latest_created,
    MIN(created_at) AS earliest_created
FROM widgets
WHERE deleted_at IS NULL
GROUP BY tenant_id, status;

CREATE OR REPLACE FUNCTION widget_search(
    p_tenant_id UUID,
    p_query TEXT,
    p_limit INTEGER DEFAULT 20
)
RETURNS SETOF widgets AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM widgets
    WHERE tenant_id = p_tenant_id
      AND deleted_at IS NULL
      AND (
          name ILIKE '%' || p_query || '%'
          OR description ILIKE '%' || p_query || '%'
      )
    ORDER BY created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;
```

## Java-Based Migration (Complex Logic)

```java
package com.example.app.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.UUID;

/**
 * Java-based migration for complex data transformations that cannot be
 * expressed in pure SQL (e.g., calling external services, conditional logic,
 * multi-step transforms with rollback).
 *
 * Naming: V5__ComplexDataMigration.java — follows Flyway conventions.
 */
public class V5__ComplexDataMigration extends BaseJavaMigration {

    private static final Logger log = LoggerFactory.getLogger(V5__ComplexDataMigration.class);
    private static final int BATCH_SIZE = 1000;

    @Override
    public void migrate(Context context) throws Exception {
        var connection = context.getConnection();

        // Step 1: Read data that needs transformation
        var selectStmt = connection.prepareStatement("""
            SELECT id, config FROM widgets
            WHERE deleted_at IS NULL
            AND config->>'legacy_format' IS NOT NULL
            ORDER BY id
            LIMIT ?
            """);

        var updateStmt = connection.prepareStatement("""
            UPDATE widgets
            SET config = ?::jsonb,
                updated_at = NOW()
            WHERE id = ?
            """);

        int totalUpdated = 0;
        boolean hasMore = true;

        while (hasMore) {
            selectStmt.setInt(1, BATCH_SIZE);
            ResultSet rs = selectStmt.executeQuery();

            int batchCount = 0;
            while (rs.next()) {
                var id = rs.getObject("id", UUID.class);
                var configJson = rs.getString("config");

                // Transform the config (example: migrate legacy format)
                var newConfig = transformConfig(configJson);

                updateStmt.setString(1, newConfig);
                updateStmt.setObject(2, id);
                updateStmt.addBatch();
                batchCount++;
            }

            if (batchCount > 0) {
                updateStmt.executeBatch();
                connection.commit();
                totalUpdated += batchCount;
                log.info("Migrated batch of {} records (total: {})", batchCount, totalUpdated);
            }

            hasMore = batchCount == BATCH_SIZE;
        }

        log.info("Migration complete: {} records transformed", totalUpdated);
    }

    private String transformConfig(String configJson) {
        // Complex transformation logic here
        // e.g., parse JSON, restructure fields, compute derived values
        return configJson.replace("\"legacy_format\"", "\"v2_format\"");
    }
}
```

## Seed Data (afterMigrate Callback)

```sql
-- src/main/resources/db/callback/afterMigrate__seed_demo_data.sql
-- Purpose: Seed demo data after all migrations complete
-- Only runs in local/dev profiles (configured via Flyway locations)

-- Idempotent: uses ON CONFLICT DO NOTHING

INSERT INTO widget_categories (id, tenant_id, name, slug, sort_order, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'General', 'general', 0, NOW(), NOW()),
    ('22222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'Premium', 'premium', 1, NOW(), NOW())
ON CONFLICT DO NOTHING;
```

## Flyway Configuration Bean (Advanced)

```java
package com.example.app.config;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.callback.Callback;
import org.flywaydb.core.api.callback.Context;
import org.flywaydb.core.api.callback.Event;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.flyway.FlywayConfigurationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FlywayConfig {

    private static final Logger log = LoggerFactory.getLogger(FlywayConfig.class);

    /**
     * Customize Flyway beyond what application.yml supports.
     */
    @Bean
    public FlywayConfigurationCustomizer flywayCustomizer() {
        return configuration -> configuration
            .callbacks(new FlywayLoggingCallback())
            .loggers("slf4j");
    }

    /**
     * Custom callback for logging migration events.
     */
    static class FlywayLoggingCallback implements Callback {
        @Override
        public boolean supports(Event event, Context context) {
            return event == Event.AFTER_EACH_MIGRATE
                || event == Event.AFTER_MIGRATE
                || event == Event.AFTER_EACH_MIGRATE_ERROR;
        }

        @Override
        public boolean canHandleInTransaction(Event event, Context context) {
            return true;
        }

        @Override
        public void handle(Event event, Context context) {
            switch (event) {
                case AFTER_EACH_MIGRATE -> {
                    var info = context.getMigrationInfo();
                    log.info("Applied migration: {} — {} ({}ms)",
                        info.getVersion(), info.getDescription(), info.getExecutionTime());
                }
                case AFTER_MIGRATE -> {
                    log.info("All migrations applied successfully");
                }
                case AFTER_EACH_MIGRATE_ERROR -> {
                    var info = context.getMigrationInfo();
                    log.error("Migration FAILED: {} — {}",
                        info.getVersion(), info.getDescription());
                }
                default -> {} // ignore other events
            }
        }

        @Override
        public String getCallbackName() {
            return "FlywayLoggingCallback";
        }
    }
}
```

## Undo / Rollback Patterns

```sql
-- Flyway Teams (paid) supports undo migrations: U1__undo_create_widgets.sql
-- For Flyway Community, use forward-only rollback migrations:

-- V6__rollback_add_category_column.sql
-- Purpose: Remove category_id column added in V2 (if feature is abandoned)

ALTER TABLE widgets DROP CONSTRAINT IF EXISTS fk_widgets_category;
DROP INDEX IF EXISTS idx_widgets_category;
ALTER TABLE widgets DROP COLUMN IF EXISTS category_id;

-- Note: This is a NEW forward migration, not an undo.
-- The migration history preserves the full audit trail.
```

## Multi-Tenant Schema Setup

```sql
-- V1__create_tenant_infrastructure.sql
-- Purpose: Create tenant table and shared infrastructure

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255)    NOT NULL,
    slug        VARCHAR(100)    NOT NULL UNIQUE,
    plan        VARCHAR(50)     NOT NULL DEFAULT 'FREE',
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants (slug);
CREATE INDEX idx_tenants_active ON tenants (id) WHERE is_active = TRUE;

-- Row-Level Security (optional — alternative to explicit tenant_id in queries)
-- Enable per-table as needed:
--
-- ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE widgets FORCE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON widgets
--     USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
--     WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

## Testing Migrations (@FlywayTest)

```java
package com.example.app.repository;

import org.flywaydb.test.annotation.FlywayTest;
import org.flywaydb.test.junit5.FlywayTestExtension;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import javax.sql.DataSource;
import java.sql.SQLException;

import static org.assertj.core.api.Assertions.*;

/**
 * Tests that Flyway migrations apply cleanly against a real PostgreSQL database.
 * Verifies schema correctness, constraint definitions, and index existence.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(TestcontainersConfig.class)
@ActiveProfiles("test")
class MigrationTest {

    @Autowired
    private DataSource dataSource;

    @Test
    void allMigrationsApplyCleanly() throws SQLException {
        // If we reach here without exception, all migrations applied successfully
        try (var conn = dataSource.getConnection()) {
            assertThat(conn.isValid(5)).isTrue();
        }
    }

    @Test
    void widgetsTableExists() throws SQLException {
        try (var conn = dataSource.getConnection();
             var rs = conn.getMetaData().getTables(null, "public", "widgets", null)) {
            assertThat(rs.next()).isTrue();
        }
    }

    @Test
    void widgetsTableHasExpectedColumns() throws SQLException {
        try (var conn = dataSource.getConnection();
             var rs = conn.getMetaData().getColumns(null, "public", "widgets", null)) {
            var columns = new java.util.HashSet<String>();
            while (rs.next()) {
                columns.add(rs.getString("COLUMN_NAME"));
            }
            assertThat(columns).containsAll(java.util.Set.of(
                "id", "tenant_id", "name", "description", "status",
                "created_at", "updated_at", "deleted_at",
                "created_by", "updated_by", "version"
            ));
        }
    }

    @Test
    void uniqueIndexExistsOnTenantAndName() throws SQLException {
        try (var conn = dataSource.getConnection();
             var rs = conn.getMetaData().getIndexInfo(null, "public", "widgets", true, false)) {
            var indexNames = new java.util.ArrayList<String>();
            while (rs.next()) {
                indexNames.add(rs.getString("INDEX_NAME"));
            }
            assertThat(indexNames).contains("idx_widgets_tenant_name_unique");
        }
    }

    @Test
    @FlywayTest(locationsForMigrate = "db/migration")
    void migrationsAreIdempotent() throws SQLException {
        // @FlywayTest re-runs all migrations from scratch
        // If this passes, migrations are safe to re-apply
        try (var conn = dataSource.getConnection()) {
            assertThat(conn.isValid(5)).isTrue();
        }
    }
}
```

## Data Migration — Batch Update Pattern

```sql
-- V4__backfill_widget_status.sql
-- Purpose: Backfill status for legacy widgets that have NULL status
-- For tables > 100K rows, use batched approach to avoid long locks

-- Small tables (< 100K rows): single UPDATE
UPDATE widgets
SET status = 'ACTIVE', updated_at = NOW()
WHERE status IS NULL AND deleted_at IS NULL;

-- Large tables (> 100K rows): batched approach
-- Run outside a single transaction to avoid holding locks
--
-- DO $$
-- DECLARE
--     batch_size INT := 5000;
--     rows_updated INT;
-- BEGIN
--     LOOP
--         UPDATE widgets
--         SET status = 'ACTIVE', updated_at = NOW()
--         WHERE id IN (
--             SELECT id FROM widgets
--             WHERE status IS NULL AND deleted_at IS NULL
--             LIMIT batch_size
--             FOR UPDATE SKIP LOCKED
--         );
--         GET DIAGNOSTICS rows_updated = ROW_COUNT;
--         RAISE NOTICE 'Updated % rows', rows_updated;
--         EXIT WHEN rows_updated = 0;
--         PERFORM pg_sleep(0.1);
--     END LOOP;
-- END $$;
```

## CREATE INDEX CONCURRENTLY

```sql
-- V7__add_search_index.sql
-- Purpose: Add full-text search index on large table
-- IMPORTANT: Cannot run inside a transaction block

-- Flyway must be configured to handle this:
-- spring.flyway.mixed=true (allows mixing transactional and non-transactional statements)

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_widgets_search
    ON widgets USING GIN (to_tsvector('english', name || ' ' || COALESCE(description, '')))
    WHERE deleted_at IS NULL;
```

## Critical Rules

- Every migration file MUST follow naming: `V{number}__{description}.sql` (double underscore).
- `ddl-auto: validate` in production — Flyway manages schema, Hibernate only validates.
- `clean-disabled: true` in production — NEVER allow Flyway clean on production databases.
- Schema migrations and seed data MUST be separate files — schema in `db/migration`, seeds in `db/seed`.
- Data migrations (backfills) MUST be separate from schema changes.
- Seed data MUST use `ON CONFLICT DO NOTHING` for idempotency — safe to re-run.
- `CREATE INDEX CONCURRENTLY` MUST be used for large tables (> 100K rows) — requires `flyway.mixed=true`.
- Every table MUST have `tenant_id`, `deleted_at`, `version` columns — see standard columns in `crud-repository-java.md`.
- Unique indexes MUST be scoped to tenant: `(tenant_id, LOWER(column)) WHERE deleted_at IS NULL`.
- Partial indexes (`WHERE deleted_at IS NULL`) reduce index size for soft-deleted tables.
- Java-based migrations for complex logic — use `BaseJavaMigration` with batch processing.
- Repeatable migrations (`R__`) for views, functions, and stored procedures that can be recreated.
- Forward-only rollbacks — create new migration to undo, never modify existing migration files.
- NEVER modify an already-applied migration — checksums will fail on next startup.
- Test migrations with `@DataJpaTest` + Testcontainers — verify schema correctness against real Postgres.
- `afterMigrate` callbacks for dev seed data — runs after all migrations complete.
- Foreign keys MUST specify `ON DELETE` behavior: `CASCADE`, `SET NULL`, or `RESTRICT`.
