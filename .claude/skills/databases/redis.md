# Redis patterns for caching, sessions, and ephemeral data.

## Key Naming Convention
```
app:entity:id         → myapp:user:uuid-here
app:entity:field      → myapp:user:email:alice@example.com
app:feature:id        → myapp:session:token-here
app:list:entity       → myapp:feed:user-id
```
Always namespace with app prefix. Colon-separated hierarchy. Lowercase.

## Data Structure Selection
| Use Case | Structure | Why |
|----------|-----------|-----|
| Single cached value | `STRING` | Simple GET/SET/DEL |
| Object/record | `HASH` | Field-level GET/SET, memory efficient |
| Recent items list | `LIST` (LPUSH+LTRIM) | Ordered, bounded |
| Unique members | `SET` | O(1) membership check |
| Sorted ranking | `SORTED SET` | Score-ordered, range queries |
| Event stream | `STREAM` | Persistent, consumer groups |
| Rate limiting | `STRING` + `INCR` + `EXPIRE` | Atomic counter |

## Cache-Aside Pattern
```python
# Read
value = redis.get(key)
if value is None:
    value = db.query(...)
    redis.setex(key, ttl_seconds, serialize(value))
return deserialize(value)

# Write
db.update(...)
redis.delete(key)  # invalidate, don't update (avoids race conditions)
```
Always set TTL on every key — no immortal cache keys.

## Session Storage
```python
redis.setex(
    f"session:{token}",
    SESSION_TTL_SECONDS,
    json.dumps({"user_id": str(user.id), "role": user.role})
)
```

## Rate Limiting
```lua
-- Atomic Lua script
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call("INCR", key)
if current == 1 then redis.call("EXPIRE", key, window) end
return current <= limit
```

## Connection Pool
```python
# Always use connection pool — never single connection
pool = redis.ConnectionPool.from_url(REDIS_URL, max_connections=20)
client = redis.Redis(connection_pool=pool)
```

## Rules
- TTL on every key — `SET key value EX ttl` not bare `SET`
- Never store sensitive data (passwords, tokens in plaintext) — encrypt or don't cache
- Pipeline multiple commands when doing batch operations
- `SCAN` not `KEYS` in production — KEYS blocks the server
- Test with `redis-cli monitor` to verify actual commands in dev
