# PostgreSQL patterns for application development.

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

## Parameterized Queries (MANDATORY)
```sql
-- ✅ CORRECT — parameterized
SELECT * FROM certificates WHERE tenant_id = $1 AND serial = $2
-- ❌ NEVER — string interpolation (SQL injection)
SELECT * FROM certificates WHERE tenant_id = '"+tenantID+"'
```
- ALL queries use `$1, $2, ...` placeholders — no exceptions
- Use `pgx.NamedArgs` for readability with many params

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

## Indexing Strategy
- One index per access pattern — no over-indexing
- Composite indexes: put equality columns first, range columns last
- `INCLUDE` columns for index-only scans: `CREATE INDEX ON certs(tenant_id, status) INCLUDE (serial, expires_at)`
- Partial indexes for common filters: `CREATE INDEX ON certs(tenant_id) WHERE status = 'active'`
- GIN for JSONB, array, and full-text search columns

## Pagination
```sql
-- Cursor-based (preferred for large datasets)
SELECT * FROM certificates
WHERE tenant_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC
LIMIT $4

-- Offset-based (simpler, OK for small datasets)
SELECT * FROM certificates WHERE tenant_id = $1
ORDER BY created_at DESC LIMIT $2 OFFSET $3
```
- Cursor-based avoids counting all rows — O(1) vs O(n)
- Always include a tie-breaker column (id) in cursor

## Migrations
- Forward-only in production — DOWN migrations are dev-only safety net
- One concern per migration file
- Test with `BEGIN; <migration>; ROLLBACK;` before applying
- Never `ALTER TABLE ... ADD COLUMN ... DEFAULT ...` on large tables in production — use three-step: add nullable → backfill → set not null

## JSONB Patterns
```sql
-- Store flexible config in JSONB
CREATE TABLE policies (id uuid, tenant_id uuid, config jsonb NOT NULL DEFAULT '{}');
-- Query JSONB
SELECT * FROM policies WHERE config->>'algorithm' = 'ECDSA-P256';
-- Index JSONB for queries
CREATE INDEX ON policies USING GIN (config jsonb_path_ops);
```

## Audit Fields (Mandatory)
```sql
created_at  timestamptz NOT NULL DEFAULT now(),
updated_at  timestamptz NOT NULL DEFAULT now(),
deleted_at  timestamptz  -- soft delete (nullable)
```
- All mutable tables MUST have `created_at`, `updated_at`
- Use trigger or application code to set `updated_at` on every UPDATE
