# MySQL (InnoDB) patterns for relational data storage.

## Configuration Essentials
- `ENGINE=InnoDB` always — never MyISAM
- `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` on all tables — supports full Unicode including emoji
- Explicit `NOT NULL` with defaults; avoid nullable columns unless semantically required

## Schema
```sql
CREATE TABLE users (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(255) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Indexes
```sql
-- Always index FK columns
ALTER TABLE orders ADD INDEX idx_orders_user_id (user_id);

-- Covering index: include all columns needed by query
CREATE INDEX idx_orders_user_status ON orders(user_id, status, created_at);

-- Prefix index for long VARCHAR (use full-text for search)
CREATE INDEX idx_name ON users(name(50));
```
Rule: every FK must have an index — MySQL doesn't create them automatically.

## Queries
```sql
-- Parameterized always
SELECT id, email FROM users WHERE id = ?;

-- Use EXPLAIN to check index usage
EXPLAIN SELECT * FROM orders WHERE user_id = 1 AND status = 'completed';
-- Look for: type=ref or better (avoid type=ALL = full table scan)
```

## Transactions
```sql
START TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```
- Default isolation: `READ COMMITTED` — appropriate for most OLTP
- `REPEATABLE READ` for operations that must see a consistent snapshot

## Migrations
- Use Flyway, Liquibase, or Goose — versioned, repeatable
- Never drop columns immediately — mark deprecated, remove in next release (zero-downtime)
- Column additions: `DEFAULT NULL` or explicit `DEFAULT value` — never bare NOT NULL on populated table

## Rules
- `BIGINT UNSIGNED` for IDs (not INT — prevents future overflow)
- `DATETIME(6)` not `DATETIME` — microsecond precision
- Connection pool: set `max_open_conns` and `max_idle_conns` explicitly
- Avoid `SELECT *` — list columns explicitly in application queries
