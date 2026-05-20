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
```go
// pgxpool (Go) — production config
config, _ := pgxpool.ParseConfig(connStr)
config.MaxConns = 50
config.MinConns = 10
config.MaxConnLifetime = 30 * time.Minute
config.MaxConnIdleTime = 5 * time.Minute
config.HealthCheckPeriod = 30 * time.Second
pool, _ := pgxpool.NewWithConfig(ctx, config)
```
- Always use connection pooling — never single connections
- Set `MaxConns` based on `(CPU cores * 2) + effective_spindle_count`
- Health checks prevent stale connections
- PgBouncer for external pooling, pgxpool/HikariCP/asyncpg for in-app pooling

## Indexes
```sql
-- B-tree (default): equality and range queries
CREATE INDEX idx_users_email ON users(email);

-- Partial: filtered queries (saves space, faster for common filters)
CREATE INDEX idx_users_active ON users(created_at) WHERE is_active = true;

-- Composite: multi-column queries (order matters — most selective first)
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
ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON certificates
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```
```go
// Set RLS context before every query
tx.Exec(ctx, "SET LOCAL app.current_tenant_id = $1", tenantID)
```
- RLS is defense-in-depth — always ALSO use explicit `WHERE tenant_id = $1`
- `SET LOCAL` scopes to current transaction only

## Transactions
```sql
-- Use appropriate isolation level
BEGIN ISOLATION LEVEL READ COMMITTED;  -- default, fine for most ops
BEGIN ISOLATION LEVEL REPEATABLE READ; -- for aggregate consistency
```
- Keep transactions short — acquire locks late, release early
- Use `SELECT ... FOR UPDATE` for optimistic locking on specific rows

## Pagination
```sql
-- Cursor-based (preferred for large datasets)
SELECT * FROM certificates
WHERE tenant_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC
LIMIT $4

-- Offset-based (simpler, OK for small datasets / admin UIs)
SELECT * FROM certificates WHERE tenant_id = $1
ORDER BY created_at DESC LIMIT $2 OFFSET $3
```
- Cursor-based avoids counting all rows — O(1) vs O(n)
- Always include a tie-breaker column (id) in cursor

## JSONB Patterns
```sql
-- Store flexible config in JSONB
CREATE TABLE policies (id uuid, tenant_id uuid, config jsonb NOT NULL DEFAULT '{}');
-- Query JSONB
SELECT * FROM policies WHERE config->>'algorithm' = 'ECDSA-P256';
-- Index JSONB for queries
CREATE INDEX ON policies USING GIN (config jsonb_path_ops);
```

## Migrations
- Every migration: `up` (apply) + `down` (rollback) — never without rollback
- Never edit a deployed migration — create a new one
- Column additions: nullable or with DEFAULT (never add NOT NULL without DEFAULT to populated table)
- Forward-only in production — DOWN migrations are dev-only safety net
- One concern per migration file
- Test with `BEGIN; <migration>; ROLLBACK;` before applying
- Never `ALTER TABLE ... ADD COLUMN ... DEFAULT ...` on large tables in production — use three-step: add nullable, backfill, set not null
- Use `goose`, `flyway`, `alembic`, or `prisma migrate` — not ad-hoc SQL scripts

## Performance
- `EXPLAIN (ANALYZE, BUFFERS)` before optimizing — measure first
- Connection pooling: PgBouncer (external) or pgx pool (in-app) — never unlimited connections
- Max connections: `100` per Postgres instance; set `pool_max_conns` accordingly

## Rules
- UUIDs vs serial: prefer `gen_random_uuid()` for distributed-safe IDs
- Store timestamps as `TIMESTAMPTZ` (UTC-aware), never `TIMESTAMP`
- JSONB for flexible attributes; avoid EAV anti-pattern
- ALL queries use parameterized placeholders — no exceptions, no interpolation
- RLS for multi-tenant isolation — defense-in-depth alongside application WHERE clauses
- Cursor-based pagination for APIs; offset for admin/reporting UIs only
