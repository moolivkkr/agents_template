---
skill: query-optimization
description: Database query optimization — N+1 detection, index strategy, connection pooling, batch operations, query patterns, monitoring
version: "1.0"
tags:
  - database
  - performance
  - postgresql
  - indexing
  - connection-pool
  - monitoring
---

# Query Optimization

Patterns for writing fast, efficient database queries. Focused on PostgreSQL but principles apply broadly.

## N+1 Detection

The most common performance killer in ORM-heavy codebases. One query for the list, then N queries for related data.

### Identifying N+1 in Code

```go
// BAD — N+1: 1 query for users + N queries for orders
func (h *Handler) ListUsersWithOrders(ctx context.Context) ([]UserWithOrders, error) {
    users, err := h.userRepo.ListAll(ctx) // SELECT * FROM users → 1 query
    if err != nil {
        return nil, err
    }
    var result []UserWithOrders
    for _, user := range users {
        // SELECT * FROM orders WHERE user_id = $1 → N queries (one per user!)
        orders, err := h.orderRepo.FindByUserID(ctx, user.ID)
        if err != nil {
            return nil, err
        }
        result = append(result, UserWithOrders{User: user, Orders: orders})
    }
    return result, nil
}
```

### Fix 1: JOIN Query

```go
// GOOD — single query with JOIN
func (r *UserRepo) ListWithOrders(ctx context.Context) ([]UserWithOrders, error) {
    query := `
        SELECT u.id, u.email, u.name,
               o.id AS order_id, o.total, o.status, o.created_at AS order_created
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.id
        ORDER BY u.id, o.created_at DESC
    `
    rows, err := r.db.QueryContext(ctx, query)
    if err != nil {
        return nil, fmt.Errorf("list users with orders: %w", err)
    }
    defer rows.Close()

    // Group rows by user
    usersMap := make(map[string]*UserWithOrders)
    var order []string // preserve insertion order
    for rows.Next() {
        var userID, email, name string
        var orderID, status sql.NullString
        var total sql.NullFloat64
        var orderCreated sql.NullTime

        if err := rows.Scan(&userID, &email, &name, &orderID, &total, &status, &orderCreated); err != nil {
            return nil, err
        }
        if _, exists := usersMap[userID]; !exists {
            usersMap[userID] = &UserWithOrders{User: User{ID: userID, Email: email, Name: name}}
            order = append(order, userID)
        }
        if orderID.Valid {
            usersMap[userID].Orders = append(usersMap[userID].Orders, Order{
                ID: orderID.String, Total: total.Float64, Status: status.String,
            })
        }
    }
    result := make([]UserWithOrders, 0, len(order))
    for _, id := range order {
        result = append(result, *usersMap[id])
    }
    return result, nil
}
```

### Fix 2: Batch Loading (DataLoader Pattern)

```go
// GOOD — batch load related data in one query
func (r *OrderRepo) FindByUserIDs(ctx context.Context, userIDs []string) (map[string][]Order, error) {
    query := `
        SELECT user_id, id, total, status, created_at
        FROM orders
        WHERE user_id = ANY($1)
        ORDER BY created_at DESC
    `
    rows, err := r.db.QueryContext(ctx, query, pq.Array(userIDs))
    if err != nil {
        return nil, fmt.Errorf("batch load orders: %w", err)
    }
    defer rows.Close()

    result := make(map[string][]Order, len(userIDs))
    for rows.Next() {
        var userID string
        var o Order
        if err := rows.Scan(&userID, &o.ID, &o.Total, &o.Status, &o.CreatedAt); err != nil {
            return nil, err
        }
        result[userID] = append(result[userID], o)
    }
    return result, nil
}

// Usage: 2 queries total (1 for users + 1 for all their orders)
func (h *Handler) ListUsersWithOrders(ctx context.Context) ([]UserWithOrders, error) {
    users, err := h.userRepo.ListAll(ctx)
    if err != nil {
        return nil, err
    }
    userIDs := make([]string, len(users))
    for i, u := range users {
        userIDs[i] = u.ID
    }
    ordersByUser, err := h.orderRepo.FindByUserIDs(ctx, userIDs)
    if err != nil {
        return nil, err
    }
    result := make([]UserWithOrders, len(users))
    for i, u := range users {
        result[i] = UserWithOrders{User: u, Orders: ordersByUser[u.ID]}
    }
    return result, nil
}
```

### Fix 3: DataLoader (GraphQL / TypeScript)

```typescript
import DataLoader from "dataloader";

// DataLoader batches individual loads into a single query
const orderLoader = new DataLoader<string, Order[]>(async (userIds) => {
  const orders = await db.query(
    `SELECT * FROM orders WHERE user_id = ANY($1) ORDER BY created_at DESC`,
    [userIds],
  );
  // Group by user_id, return in same order as input
  const grouped = new Map<string, Order[]>();
  for (const order of orders.rows) {
    const existing = grouped.get(order.user_id) ?? [];
    existing.push(order);
    grouped.set(order.user_id, existing);
  }
  return userIds.map((id) => grouped.get(id) ?? []);
});

// Each resolver calls .load() — DataLoader batches them
const resolvers = {
  User: {
    orders: (user: User) => orderLoader.load(user.id),
  },
};
```

- Always test with realistic data volumes (100+ parent records)
- Enable query logging in development: `log_min_duration_statement = 0`
- Count queries per request in tests — assert the expected count

## Index Strategy

Choose the right index type for your query pattern.

### B-tree (Default) — Equality and Range

```sql
-- Equality: WHERE email = $1
CREATE UNIQUE INDEX idx_users_email ON users(email);

-- Range: WHERE created_at > $1 AND created_at < $2
CREATE INDEX idx_users_created_at ON users(created_at);

-- Composite: WHERE user_id = $1 AND status = $2 ORDER BY created_at
-- Leftmost prefix rule: index is used for (user_id), (user_id, status),
-- (user_id, status, created_at) — but NOT for (status) alone
CREATE INDEX idx_orders_user_status_created
    ON orders(user_id, status, created_at DESC);
```

### GIN — JSONB, Arrays, Full-Text Search

```sql
-- JSONB containment: WHERE metadata @> '{"type": "premium"}'
CREATE INDEX idx_events_metadata ON events USING gin(metadata);

-- Array contains: WHERE tags @> ARRAY['urgent']
CREATE INDEX idx_tickets_tags ON tickets USING gin(tags);

-- Full-text search
CREATE INDEX idx_articles_search ON articles USING gin(
    to_tsvector('english', title || ' ' || body)
);
-- Query: WHERE to_tsvector('english', title || ' ' || body) @@ plainto_tsquery('search term')
```

### Partial Indexes — Filtered Queries

```sql
-- Only index active users — smaller index, faster for common query
CREATE INDEX idx_users_active_email ON users(email)
    WHERE deleted_at IS NULL;

-- Only index pending orders — most queries filter by status
CREATE INDEX idx_orders_pending ON orders(created_at DESC)
    WHERE status = 'pending';

-- Query planner uses this index automatically when WHERE clause matches
SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;
```

### Covering Indexes (INCLUDE)

```sql
-- INCLUDE columns are stored in the index but not used for lookup
-- Enables index-only scans — avoids heap table access entirely
CREATE INDEX idx_orders_user_covering ON orders(user_id)
    INCLUDE (status, total, created_at);

-- This query can be satisfied entirely from the index:
SELECT status, total, created_at FROM orders WHERE user_id = $1;
```

### Index Guidelines

- Index every foreign key column (PostgreSQL doesn't auto-index FKs)
- Index every column that appears in WHERE, JOIN ON, or ORDER BY of frequent queries
- Composite indexes: put equality columns first, then range, then sort columns
- Don't over-index: each index slows writes and consumes storage
- Use `pg_stat_user_indexes` to find unused indexes (remove them)

```sql
-- Find unused indexes
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;
```

## Connection Pooling

Every database connection costs memory (~10MB per connection in PostgreSQL). Pool them.

### Go (pgxpool)

```go
import "github.com/jackc/pgx/v5/pgxpool"

func NewPool(dsn string) (*pgxpool.Pool, error) {
    config, err := pgxpool.ParseConfig(dsn)
    if err != nil {
        return nil, fmt.Errorf("parse dsn: %w", err)
    }

    config.MinConns = 2              // keep 2 warm connections
    config.MaxConns = 20             // max 20 per service instance
    config.MaxConnIdleTime = 5 * time.Minute  // close idle connections after 5m
    config.MaxConnLifetime = 30 * time.Minute // recycle connections after 30m
    config.HealthCheckPeriod = 30 * time.Second

    pool, err := pgxpool.NewWithConfig(context.Background(), config)
    if err != nil {
        return nil, fmt.Errorf("create pool: %w", err)
    }
    return pool, nil
}

// Monitor pool health
func MonitorPool(pool *pgxpool.Pool, logger *slog.Logger) {
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        stat := pool.Stat()
        logger.Info("pool_stats",
            "total_conns", stat.TotalConns(),
            "idle_conns", stat.IdleConns(),
            "acquired_conns", stat.AcquiredConns(),
            "constructing_conns", stat.ConstructingConns(),
            "max_conns", stat.MaxConns(),
        )
    }
}
```

### Node.js (pg)

```typescript
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  min: 2,                 // minimum idle connections
  max: 20,                // maximum connections
  idleTimeoutMillis: 300000,  // 5 minutes
  connectionTimeoutMillis: 5000, // fail fast if pool is exhausted
  maxLifetimeMillis: 1800000,   // 30 minutes
});

// Monitor pool events
pool.on("error", (err) => {
  logger.error("Pool error", { error: err.message });
});

pool.on("connect", () => {
  logger.debug("New connection established");
});

// Health check endpoint
app.get("/health/db", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({
      status: "healthy",
      total: pool.totalCount,
      idle: pool.idleCount,
      waiting: pool.waitingCount,
    });
  } catch (err) {
    res.status(503).json({ status: "unhealthy", error: err.message });
  }
});
```

### Pool Sizing Rules

- **Min connections**: 2 per service instance (keeps connections warm)
- **Max connections**: 20 per service instance (bound by `max_connections / number_of_instances`)
- **Idle timeout**: 5 minutes (close unused connections)
- **Max lifetime**: 30 minutes (recycle to rebalance after failover)
- **Formula**: `max_connections = (total_pg_max_connections - reserved) / num_service_instances`
- Monitor: alert when `waiting_count > 0` (pool exhaustion)

## Query Patterns

### EXISTS Over COUNT

```sql
-- BAD: counts ALL matching rows, then checks > 0
SELECT COUNT(*) FROM orders WHERE user_id = $1;
-- Then in code: if count > 0 { ... }

-- GOOD: stops at first match — O(1) vs O(n)
SELECT EXISTS(SELECT 1 FROM orders WHERE user_id = $1);
```

### Explicit Column Lists

```sql
-- BAD: fetches all columns including large JSONB/text fields
SELECT * FROM users WHERE id = $1;

-- GOOD: only fetch what you need
SELECT id, email, name, created_at FROM users WHERE id = $1;
```

### EXPLAIN ANALYZE Before Deploying

```sql
-- Run EXPLAIN ANALYZE on every new query before deploying
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.id, u.email, count(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id
ORDER BY order_count DESC
LIMIT 20;

-- Look for:
-- Seq Scan (on large tables) → needs an index
-- Nested Loop with high row count → consider hash/merge join
-- Sort with high memory → add index matching ORDER BY
-- Buffers: shared read (high) → data not cached, might need more shared_buffers
```

### CTEs: Readability vs Performance

```sql
-- CTEs are optimization barriers in PostgreSQL < 12
-- In PostgreSQL 12+, CTEs can be inlined by the planner

-- Use CTE for readability when performance is acceptable
WITH active_users AS (
    SELECT id, email FROM users WHERE is_active = true
),
recent_orders AS (
    SELECT user_id, count(*) AS cnt FROM orders
    WHERE created_at > now() - interval '30 days'
    GROUP BY user_id
)
SELECT au.email, coalesce(ro.cnt, 0) AS recent_order_count
FROM active_users au
LEFT JOIN recent_orders ro ON ro.user_id = au.id;

-- For hot paths, use subqueries if the CTE prevents optimization
SELECT u.email, coalesce(sub.cnt, 0) AS recent_order_count
FROM users u
LEFT JOIN (
    SELECT user_id, count(*) AS cnt FROM orders
    WHERE created_at > now() - interval '30 days'
    GROUP BY user_id
) sub ON sub.user_id = u.id
WHERE u.is_active = true;
```

### Prepared Statements

```go
// Prepare once, execute many — avoids repeated parsing and planning
func (r *UserRepo) prepareStatements(ctx context.Context) error {
    var err error
    r.stmtFindByID, err = r.db.PrepareContext(ctx,
        "SELECT id, email, name, created_at FROM users WHERE id = $1")
    if err != nil {
        return fmt.Errorf("prepare find_by_id: %w", err)
    }
    r.stmtFindByEmail, err = r.db.PrepareContext(ctx,
        "SELECT id, email, name, created_at FROM users WHERE email = $1")
    if err != nil {
        return fmt.Errorf("prepare find_by_email: %w", err)
    }
    return nil
}

func (r *UserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    var u User
    err := r.stmtFindByID.QueryRowContext(ctx, id).Scan(&u.ID, &u.Email, &u.Name, &u.CreatedAt)
    if errors.Is(err, sql.ErrNoRows) {
        return nil, ErrNotFound
    }
    return &u, err
}
```

## Batch Operations

### Bulk Inserts with COPY

```go
// COPY is 10-100x faster than individual INSERTs for bulk loading
func (r *EventRepo) BulkInsert(ctx context.Context, events []Event) error {
    conn, err := r.pool.Acquire(ctx)
    if err != nil {
        return fmt.Errorf("acquire conn: %w", err)
    }
    defer conn.Release()

    _, err = conn.Conn().CopyFrom(
        ctx,
        pgx.Identifier{"events"},
        []string{"id", "type", "payload", "created_at"},
        pgx.CopyFromSlice(len(events), func(i int) ([]any, error) {
            return []any{
                events[i].ID,
                events[i].Type,
                events[i].Payload,
                events[i].CreatedAt,
            }, nil
        }),
    )
    return err
}
```

### Batch Parameter Binding with unnest()

```sql
-- Insert multiple rows with unnest — single query, parameterized
INSERT INTO tags (name, category)
SELECT unnest($1::text[]), unnest($2::text[]);

-- Batch update
UPDATE users
SET status = data.new_status
FROM (
    SELECT unnest($1::text[]) AS id,
           unnest($2::text[]) AS new_status
) data
WHERE users.id = data.id;
```

```go
// Go implementation
func (r *TagRepo) BulkCreate(ctx context.Context, tags []Tag) error {
    names := make([]string, len(tags))
    categories := make([]string, len(tags))
    for i, t := range tags {
        names[i] = t.Name
        categories[i] = t.Category
    }
    _, err := r.db.ExecContext(ctx,
        "INSERT INTO tags (name, category) SELECT unnest($1::text[]), unnest($2::text[])",
        pq.Array(names), pq.Array(categories),
    )
    return err
}
```

### Batch Size Limits

```go
// Process in batches of 1000 to avoid memory pressure and lock contention
const batchSize = 1000

func (r *EventRepo) BulkInsertBatched(ctx context.Context, events []Event) error {
    for i := 0; i < len(events); i += batchSize {
        end := i + batchSize
        if end > len(events) {
            end = len(events)
        }
        batch := events[i:end]
        if err := r.BulkInsert(ctx, batch); err != nil {
            return fmt.Errorf("batch %d-%d: %w", i, end, err)
        }
    }
    return nil
}
```

- Use `COPY` for bulk inserts (Go: `pgx.CopyFrom`, Python: `copy_from`)
- Use `unnest()` for batch parameter binding in single queries
- Limit batch size to 1000 rows per operation
- Wrap multi-batch operations in a transaction for atomicity
- Individual INSERTs in a loop are almost always wrong

## Monitoring

### pg_stat_statements — Slow Query Tracking

```sql
-- Enable the extension (once per database)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 slowest queries by total time
SELECT
    calls,
    round(total_exec_time::numeric, 2) AS total_ms,
    round(mean_exec_time::numeric, 2) AS mean_ms,
    round(max_exec_time::numeric, 2) AS max_ms,
    rows,
    query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- Queries with highest mean execution time (potential optimization targets)
SELECT
    calls,
    round(mean_exec_time::numeric, 2) AS mean_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    query
FROM pg_stat_statements
WHERE calls > 100  -- ignore rarely-used queries
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### Cache Hit Ratios

```sql
-- Table cache hit ratio — should be > 99%
SELECT
    schemaname, tablename,
    heap_blks_hit * 100.0 / NULLIF(heap_blks_hit + heap_blks_read, 0) AS cache_hit_ratio
FROM pg_statio_user_tables
WHERE heap_blks_hit + heap_blks_read > 0
ORDER BY cache_hit_ratio ASC
LIMIT 10;

-- Index cache hit ratio
SELECT
    schemaname, tablename, indexrelname,
    idx_blks_hit * 100.0 / NULLIF(idx_blks_hit + idx_blks_read, 0) AS cache_hit_ratio
FROM pg_statio_user_indexes
WHERE idx_blks_hit + idx_blks_read > 0
ORDER BY cache_hit_ratio ASC
LIMIT 10;
```

### Alerting Thresholds

```go
// Application-level query monitoring
type QueryMonitor struct {
    slowThreshold time.Duration
    logger        *slog.Logger
}

func (m *QueryMonitor) WrapQuery(ctx context.Context, query string, args ...any) func() {
    start := time.Now()
    return func() {
        elapsed := time.Since(start)
        if elapsed > m.slowThreshold {
            m.logger.Warn("slow_query",
                "query", query,
                "duration_ms", elapsed.Milliseconds(),
                "threshold_ms", m.slowThreshold.Milliseconds(),
            )
        }
    }
}

// Usage
func (r *UserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    done := r.monitor.WrapQuery(ctx, "users.find_by_id")
    defer done()

    var u User
    err := r.db.GetContext(ctx, &u, "SELECT id, email FROM users WHERE id = $1", id)
    return &u, err
}
```

### Key Metrics to Track

| Metric | Warning | Critical |
|--------|---------|----------|
| Query p95 latency | > 50ms | > 100ms |
| Connection pool waiting | > 0 | > 5 |
| Cache hit ratio | < 99% | < 95% |
| Active connections | > 70% of max | > 90% of max |
| Deadlocks per minute | > 0 | > 1 |
| Rows returned per query (avg) | > 1000 | > 10000 |

## Critical Rules

- Detect and fix N+1 queries — they are the #1 database performance issue
- Choose the right index type: B-tree for equality/range, GIN for JSONB/arrays/FTS, partial for filtered queries
- Pool connections: min 2, max 20 per instance, monitor pool saturation
- `EXPLAIN ANALYZE` every new query before deploying — no exceptions
- Use `EXISTS` over `COUNT(*)` for existence checks
- List columns explicitly — never `SELECT *` in production code
- Use `COPY` for bulk inserts, `unnest()` for batch operations
- Monitor slow queries with pg_stat_statements, alert on p95 > 100ms
