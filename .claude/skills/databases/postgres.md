# PostgreSQL patterns for reliable, performant relational data storage.

## Schema Design
- Normalize to 3NF first; denormalize only with measured query performance issues
- `snake_case` for all identifiers (tables, columns, indexes, constraints)
- Explicit foreign key constraints always — don't rely on application enforcement
- `NOT NULL` by default; `NULL` only when absence is semantically meaningful
- `created_at TIMESTAMPTZ DEFAULT now()` and `updated_at TIMESTAMPTZ DEFAULT now()` on all tables

## Indexes
```sql
-- B-tree (default): equality and range queries
CREATE INDEX idx_users_email ON users(email);

-- Partial: filtered queries (saves space, faster for common filters)
CREATE INDEX idx_users_active ON users(created_at) WHERE is_active = true;

-- Composite: multi-column queries (order matters — most selective first)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- GIN: JSONB, arrays, full-text search
CREATE INDEX idx_metadata ON events USING gin(metadata);
```
Rule: index every foreign key column and every column in WHERE/ORDER BY clauses of frequent queries.

## Queries
```sql
-- Always parameterized — never string concatenation
SELECT id, email FROM users WHERE id = $1;

-- Use RETURNING to avoid second query
INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id, created_at;

-- CTEs for complex logic (readable, optimizable)
WITH active_users AS (
    SELECT id FROM users WHERE is_active = true
)
SELECT u.id, count(o.id) FROM active_users u LEFT JOIN orders o ON o.user_id = u.id GROUP BY u.id;
```

## Transactions
```sql
-- Use appropriate isolation level
BEGIN ISOLATION LEVEL READ COMMITTED;  -- default, fine for most ops
BEGIN ISOLATION LEVEL REPEATABLE READ; -- for aggregate consistency
```
- Keep transactions short — acquire locks late, release early
- Use `SELECT ... FOR UPDATE` for optimistic locking on specific rows

## Migrations
- Every migration: `up` (apply) + `down` (rollback) — never without rollback
- Never edit a deployed migration — create a new one
- Column additions: nullable or with DEFAULT (never add NOT NULL without DEFAULT to populated table)
- Use `goose`, `flyway`, `alembic`, or `prisma migrate` — not ad-hoc SQL scripts

## Performance
- `EXPLAIN (ANALYZE, BUFFERS)` before optimizing — measure first
- Connection pooling: PgBouncer (external) or pgx pool (in-app) — never unlimited connections
- Max connections: `100` per Postgres instance; set `pool_max_conns` accordingly

## Rules
- UUIDs vs serial: prefer `gen_random_uuid()` for distributed-safe IDs
- Store timestamps as `TIMESTAMPTZ` (UTC-aware), never `TIMESTAMP`
- JSONB for flexible attributes; avoid EAV anti-pattern
