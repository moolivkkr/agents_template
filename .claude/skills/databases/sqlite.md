# SQLite patterns for embedded, testing, and single-writer use cases.

## When to Use SQLite
✅ Good fit:
- Unit/integration test databases (in-memory for isolation)
- CLI tools and desktop applications
- Embedded databases (single process, low concurrency)
- Development environments (zero-setup)
- Read-heavy applications with infrequent writes

❌ Not appropriate for:
- Multi-writer web applications (serialized writes)
- Large datasets requiring advanced indexing
- Horizontal scaling requirements

## WAL Mode (always enable for apps)
```sql
PRAGMA journal_mode=WAL;      -- concurrent reads during writes
PRAGMA synchronous=NORMAL;    -- good durability/performance balance
PRAGMA foreign_keys=ON;       -- not enabled by default!
PRAGMA busy_timeout=5000;     -- wait 5s instead of immediate SQLITE_BUSY
```
Set these pragmas at connection open time.

## Test Isolation
```python
# In-memory DB per test — zero cleanup needed
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    # connection closes, memory freed automatically
```

## Migrations
Same tools as other SQL databases work: Alembic, Goose, Flyway (with SQLite driver).

```sql
-- Column addition safe (SQLite supports ADD COLUMN)
ALTER TABLE users ADD COLUMN phone TEXT;

-- Column removal: NOT supported directly — recreate table
-- CREATE TABLE users_new AS SELECT id, email FROM users;
-- DROP TABLE users;
-- ALTER TABLE users_new RENAME TO users;
```

## Indexes (same principles as PostgreSQL)
```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

## Rules
- Always `PRAGMA foreign_keys=ON` — SQLite ignores FK constraints by default
- WAL mode for any app with concurrent reads
- In-memory (`:memory:`) for test databases — never share between test cases
- File-based SQLite: ensure only one process writes at a time
- Use parameterized queries — same SQL injection risks as any DB
