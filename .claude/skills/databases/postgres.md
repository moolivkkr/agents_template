# PostgreSQL patterns for reliable, performant relational data storage.

## Schema Design
- Normalize to 3NF first; denormalize only with measured query performance issues
- `snake_case` for all identifiers (tables, columns, indexes, constraints)
- Explicit foreign key constraints always — don't rely on application enforcement
- `NOT NULL` by default; `NULL` only when absence is semantically meaningful
- `created_at TIMESTAMPTZ DEFAULT now()` and `updated_at TIMESTAMPTZ DEFAULT now()` on all tables

## Audit Fields (Mandatory)
```sql
created_at  timestamptz NOT NULL DEFAULT now(),
updated_at  timestamptz NOT NULL DEFAULT now(),
deleted_at  timestamptz  -- soft delete (nullable)
```
- All mutable tables MUST have `created_at`, `updated_at`
- Use trigger or application code to set `updated_at` on every UPDATE

## Connection Pooling
> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, pgx v5.11.0 (tests/archetype-compile/go/run.sh).

```go
// pgxpool (Go) — sized from the connection-pool budget, not a constant
config, err := pgxpool.ParseConfig(connStr)
if err != nil {
    return nil, fmt.Errorf("db config: %w", err)
}
config.MaxConns = int32(cfg.DBMaxConns) // e.g. 7: see the budget in core/resiliency-patterns.md
config.MinConns = 1
config.MaxConnLifetime = 30 * time.Minute
config.MaxConnIdleTime = 5 * time.Minute
config.HealthCheckPeriod = 30 * time.Second
config.ConnConfig.RuntimeParams["statement_timeout"] = "5000"                  // ms: a runaway query can't hold a connection
config.ConnConfig.RuntimeParams["idle_in_transaction_session_timeout"] = "10000" // ms
pool, err := pgxpool.NewWithConfig(ctx, config)
```
- Always use connection pooling — never single connections
- **Size `MaxConns` from the budget:** `max replicas × pools per process × MaxConns + jobs + admin ≤
  max_connections − superuser_reserved_connections` (Postgres defaults: 100 − 3). Two replicas at
  `MaxConns = 50` already use all 100. See `core/resiliency-patterns.md` §Connection-Pool Budget.
- Pool acquisition waits count against the request's context deadline; keep acquire waits under ~1 s
- Health checks prevent stale connections
- PgBouncer (transaction mode) when the budget can't fit; pgxpool/HikariCP/asyncpg for in-app pooling

## Indexes
```sql
-- B-tree (default): equality and range queries
CREATE INDEX idx_users_email ON users(email);

-- Partial: filtered queries (saves space, faster for common filters)
CREATE INDEX idx_users_active ON users(created_at) WHERE is_active = true;

-- Composite: multi-column queries (order matters — equality columns first, then range/sort)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- INCLUDE columns for index-only scans
CREATE INDEX ON certs(tenant_id, status) INCLUDE (serial, expires_at);

-- GIN: JSONB, arrays, full-text search
CREATE INDEX idx_metadata ON events USING gin(metadata);
```
Rule: index every foreign key column and every column in WHERE/ORDER BY clauses of frequent queries.
- One index per access pattern — no over-indexing
- Composite indexes: put equality columns first, range columns last
- Partial indexes for common filters: `CREATE INDEX ON certs(tenant_id) WHERE status = 'active'`

## Queries
```sql
-- Always parameterized — never string concatenation
SELECT id, email FROM users WHERE id = $1;

-- ❌ NEVER — string interpolation (SQL injection)
-- SELECT * FROM certificates WHERE tenant_id = '"+tenantID+"'

-- Use RETURNING to avoid second query
INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id, created_at;

-- CTEs for complex logic (readable, optimizable)
WITH active_users AS (
    SELECT id FROM users WHERE is_active = true
)
SELECT u.id, count(o.id) FROM active_users u LEFT JOIN orders o ON o.user_id = u.id GROUP BY u.id;

-- Use pgx.NamedArgs for readability with many params (Go)
```
- ALL queries use `$1, $2, ...` placeholders — no exceptions

## Row-Level Security (Multi-Tenancy)
```sql
-- ONCE, in the project's first migration (before any tenant table): the migrator-policy helper (D-001).
-- It gives a table a PERMISSIVE policy TO the table's owner only, USING (true) WITH CHECK (true). The
-- owner is the migrator (it owns every object: db-roles.sh), so cross-tenant migrations, backfills and
-- seeds see and write every tenant's rows under FORCE, with or without BYPASSRLS.
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
        EXECUTE format('ALTER POLICY %I ON %s TO %I', pol, tbl, owner_role);   -- idempotent re-run
    ELSE
        EXECUTE format('CREATE POLICY %I ON %s AS PERMISSIVE FOR ALL TO %I USING (true) WITH CHECK (true)',
                       pol, tbl, owner_role);
    END IF;
END
$fn$;
REVOKE ALL ON FUNCTION app_grant_migrator(regclass) FROM PUBLIC;

-- EVERY tenant table, in the migration that creates it:
ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE certificates FORCE ROW LEVEL SECURITY;  -- without FORCE the table owner bypasses the policy
CREATE POLICY tenant_isolation ON certificates
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
SELECT app_grant_migrator('certificates');           -- policy certificates_migrator_all TO the owner only
```
```go
// Set RLS context before every query, inside the transaction. SET LOCAL cannot take a bind parameter
// ("SET LOCAL ... = $1" is a syntax error); set_config(..., true) is its transaction-local form.
if _, err := tx.Exec(ctx, "SELECT set_config('app.current_tenant_id', $1, true)", tenantID); err != nil {
    return fmt.Errorf("set tenant context: %w", err)
}
```
- RLS is defense-in-depth — always ALSO use explicit `WHERE tenant_id = $1`
- `SET LOCAL` scopes to current transaction only

### The migrator policy (decision D-001, both deploy paths)
Two roles touch a tenant table (`infrastructure/saas-tenancy-models.md`): the **migrator** owns it and runs
migrations and seeds; the **runtime** role the services use owns nothing and has no `BYPASSRLS`, so
`FORCE ROW LEVEL SECURITY` binds it. The migrator must still reach every tenant's rows (backfills, seeds,
data fixes, foreign-key validation). How:
- **Lab / self-hosted Postgres:** the migrator is `BYPASSRLS` (db-roles.sh, run as a superuser).
- **Amazon RDS / Aurora:** the master user is not a superuser and cannot grant `BYPASSRLS`, so the
  migrator is `NOBYPASSRLS`, and FORCE applies to it as the owner (`infrastructure/eks.md`).
- **Both:** every FORCE-RLS table gets the migrator policy above, in the migration that creates it. On
  the lab it is redundant with `BYPASSRLS` and harmless; on RDS it is what makes migrations work.
  Permissive policies are OR'ed, so the migrator sees every row while the runtime role, which is neither
  the owner nor a member of it, gets only the tenant policy. Data migrations never lift `FORCE`
  (`ALTER TABLE ... NO FORCE` takes an `ACCESS EXCLUSIVE` lock that blocks the application).

Rules:
- **Who it targets.** The helper reads the target from the catalog, the table owner. No role name in
  the SQL and no templating, so the same SQL runs unchanged under golang-migrate, sqlx, Flyway, Liquibase,
  Alembic, Django, Prisma, Drizzle and TypeORM. The name's single source of truth stays
  `DB_MIGRATOR_USER` (db-credentials secret → db-roles.sh, which makes that role the owner of the
  database and every object, and re-points `*_migrator_all` policies to it if ownership changed).
- **Helper not wanted?** The inline form is the same policy:
  `DO $$ BEGIN EXECUTE format('CREATE POLICY widgets_migrator_all ON widgets TO %I USING (true) WITH CHECK (true)', (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'widgets'::regclass)); END $$;`
- **Never** `TO PUBLIC`, `TO <runtime role>`, or a role name typed into a policy: an unconditional policy
  that reaches the runtime role hands it every tenant's rows. A review finds that BLOCKING
  (`migration_safety_reviewer`), and the deploy's `db-rls-check` Job (run as the runtime role after every
  migrate) fails on it, on a FORCE-RLS table with no migrator policy, and on a runtime role that reads
  any row with no tenant set.
- **Existing schema (adopting D-001):** one new migration creates the helper and calls it for every
  FORCE-RLS table that lacks the policy. Never edit an applied migration.
- **Restrictive tenant policies** (`AS RESTRICTIVE`) are AND'ed and would bind the migrator too; keep the
  tenant policy permissive, or exempt the owner in its expression.
- **Proof:** `tests/eks-db-roles.sh` (stock PostgreSQL 17 set up like RDS: master NOSUPERUSER, migrator
  NOBYPASSRLS) and `tests/k8s-db-roles.sh` (lab: migrator BYPASSRLS) create a table with this block,
  backfill two tenants as the migrator, and show the runtime role reads and writes only its own tenant.

## Transactions
```sql
-- Use appropriate isolation level
BEGIN ISOLATION LEVEL READ COMMITTED;  -- default, fine for most ops
BEGIN ISOLATION LEVEL REPEATABLE READ; -- for aggregate consistency
```
- Keep transactions short — acquire locks late, release early
- Use `SELECT ... FOR UPDATE` to lock specific rows (pessimistic); optimistic locking is a `version`
  column checked in the `UPDATE ... WHERE version = $n`

## Pagination
```sql
-- Cursor-based (keyset) — the only pagination: the cursor encodes the last row's (created_at, id)
SELECT id, serial, status, created_at FROM certificates
WHERE tenant_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC
LIMIT $4;

-- ❌ NEVER — OFFSET: rows shift between pages under concurrent writes, and every page re-reads and
-- discards all the rows before it
-- SELECT * FROM certificates WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3;
```
- An index on `(tenant_id, created_at DESC, id DESC)` serves the cursor query: each page is a short
  index range scan, whatever its depth (OFFSET reads and throws away every row it skips)
- Always include a tie-breaker column (id) in cursor

## JSONB Patterns
```sql
-- Store flexible config in JSONB
CREATE TABLE policies (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  config    jsonb NOT NULL DEFAULT '{}'
);
-- Index JSONB for containment queries
CREATE INDEX ON policies USING GIN (config jsonb_path_ops);
-- Query with containment (@>): the jsonb_path_ops index serves @>, @? and @@ only
SELECT id, config FROM policies WHERE tenant_id = $1 AND config @> '{"algorithm": "ECDSA-P256"}';
-- config->>'algorithm' = '…' can't use that index; it needs an expression index:
-- CREATE INDEX ON policies ((config->>'algorithm'));
```

## Migrations
- Every migration: `up` (apply) + `down` (rollback) — never without rollback
- Never edit a deployed migration — create a new one
- Column additions: nullable or with DEFAULT (never add NOT NULL without DEFAULT to populated table)
- Forward-only in production — DOWN migrations are dev-only safety net
- One concern per migration file
- Test with `BEGIN; <migration>; ROLLBACK;` before applying
- `ADD COLUMN ... DEFAULT <constant>` (even `NOT NULL`) is metadata-only since PostgreSQL 11 — no table
  rewrite. A volatile default (`DEFAULT gen_random_uuid()`, `clock_timestamp()`) rewrites the whole table
  under an exclusive lock: on large tables use three steps (add nullable, backfill in batches, then
  `NOT NULL` via a validated `CHECK` constraint)
- Use `goose`, `flyway`, `alembic`, or `prisma migrate` — not ad-hoc SQL scripts

## Performance
- `EXPLAIN (ANALYZE, BUFFERS)` before optimizing — measure first
- Connection pooling: PgBouncer (external) or pgx pool (in-app) — never unlimited connections
- `max_connections` defaults to 100 (3 reserved for superusers): budget every pool against it

## Rules
- UUIDs vs serial: prefer `gen_random_uuid()` for distributed-safe IDs
- Store timestamps as `TIMESTAMPTZ` (UTC-aware), never `TIMESTAMP`
- JSONB for flexible attributes; avoid EAV anti-pattern
- ALL queries use parameterized placeholders — no exceptions, no interpolation
- RLS for multi-tenant isolation — defense-in-depth alongside application WHERE clauses
- Cursor-based pagination for every list — APIs and admin UIs alike; no OFFSET

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 7 SQL blocks parsed with libpg_query 17.7 and executed on PostgreSQL 17.11; 4 claims in the text proven on PostgreSQL 17.11.
