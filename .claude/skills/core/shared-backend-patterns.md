# Shared Backend Patterns — Language-Agnostic Contracts

> **Single source of truth** for cross-cutting backend concerns.
> Language-specific skill packs extend these patterns with idiomatic implementations.
> Every backend service — regardless of language — MUST follow these contracts.

---

## Multi-Tenancy Rules

Every SaaS backend enforces tenant isolation at every layer. No exceptions.

### Parameter Ordering
```
function DoSomething(context, tenant_id, ...other_params) -> result, error
```
- `context` (or request/ctx) is ALWAYS the first parameter
- `tenant_id` is ALWAYS the second parameter after context
- This convention is non-negotiable across all languages

### Database Queries
```
-- EVERY query MUST filter by tenant_id
SELECT * FROM orders WHERE tenant_id = ? AND id = ?

-- NEVER allow cross-tenant reads
-- BAD: SELECT * FROM orders WHERE id = ?

-- Indexes MUST lead with tenant_id
CREATE INDEX idx_orders_tenant_status ON orders(tenant_id, status)
```
- Every table that stores tenant data MUST have a `tenant_id` column
- Every query against tenant tables MUST include `tenant_id` in the WHERE clause
- Composite indexes MUST lead with `tenant_id` for query efficiency
- JOIN queries MUST filter by `tenant_id` on BOTH sides of the join

### Row-Level Security (Defense in Depth)
```sql
-- RLS policy as a safety net (PostgreSQL example)
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
```
- Application-level filtering is the PRIMARY mechanism
- RLS is the SECONDARY safety net — catches bugs in application code
- Set tenant context at connection/session level before any queries
- RLS policies MUST exist on every tenant-scoped table

### Logging
```
-- EVERY log line MUST include tenant_id
log.info("order_created", tenant_id=tid, order_id=oid, amount=amt)

-- NEVER log without tenant context in request-scoped code
-- BAD: log.info("order_created", order_id=oid)
```

### Metrics
```
-- EVERY metric MUST label with tenant_id
metrics.increment("orders.created", tags={tenant_id: tid})

-- For high-cardinality: use tenant tier instead of raw ID
metrics.histogram("request.latency", value, tags={tenant_tier: "enterprise"})
```

### Tenant Context Flow
```
Request → Auth Middleware → Extract tenant_id from JWT/API key
       → Store in request context
       → Pass explicitly to service layer
       → Pass explicitly to repository layer
       → Include in every DB query, log, and metric
```

---

## Service Layer Contract

The service layer contains business logic. It depends on abstractions (interfaces/protocols), never on concrete implementations.

### Constructor Pattern
```
ServiceConstructor(
    repository:     RepositoryInterface,
    cache:          CacheInterface,
    event_publisher: EventPublisherInterface,
    logger:         LoggerInterface,
) -> Service
```
- Accept interfaces/abstractions for ALL dependencies
- No `new` or construction of dependencies inside the service
- Dependencies are injected, making the service testable in isolation

### Method Signature
```
service.DoOperation(ctx, tenant_id, request) -> response, error
```
- `ctx` as first param (carries timeout, cancellation, trace context)
- `tenant_id` as second param (explicit, never implicit)
- Request object as third param (validated at handler layer)
- Return response + error (never panic/throw for expected failures)

### Audit Trail
Every mutation MUST log an audit entry:
```
audit_log(
    who:       user_id (from context),
    what:      "order.created",
    when:      timestamp (UTC),
    tenant:    tenant_id,
    before:    previous_state (for updates),
    after:     new_state,
    ip:        client_ip (from context),
)
```
- Audit logs are append-only — never update or delete
- Store in a dedicated audit table, not application logs
- Include both before/after state for updates

### Cache-Aside Pattern
```
function GetEntity(ctx, tenant_id, id):
    // 1. Check cache
    cached = cache.get(key(tenant_id, id))
    if cached != null:
        return cached

    // 2. Cache miss — query database
    entity = repository.find_by_id(ctx, tenant_id, id)
    if entity == null:
        return NotFoundError

    // 3. Populate cache
    cache.set(key(tenant_id, id), entity, ttl=5m)

    return entity
```

### Cache Invalidation
```
function UpdateEntity(ctx, tenant_id, id, updates):
    entity = repository.update(ctx, tenant_id, id, updates)

    // ALWAYS invalidate cache on write
    cache.delete(key(tenant_id, id))

    // Also invalidate list caches that may include this entity
    cache.delete(list_key(tenant_id, entity.type))

    publish_event("entity.updated", entity)
    return entity
```
- Invalidate on EVERY write (create, update, delete)
- Invalidate related list/aggregate caches too
- Use cache key namespacing: `{tenant_id}:{entity_type}:{entity_id}`

---

## Repository Layer Contract

The repository layer handles data persistence. It translates between domain entities and database rows.

### Parameterized Queries Only
```
-- ALWAYS: parameterized
query("SELECT * FROM users WHERE tenant_id = $1 AND email = $2", tenant_id, email)

-- NEVER: string concatenation
query("SELECT * FROM users WHERE email = '" + email + "'")  // SQL injection
```
- No string interpolation in queries — EVER
- Use query builders that enforce parameterization
- ORM queries must also be audited for injection safety

### Soft Delete
```
-- Mark as deleted, never physically remove
UPDATE orders SET deleted_at = NOW() WHERE tenant_id = $1 AND id = $2

-- EVERY read query MUST filter out soft-deleted records
SELECT * FROM orders WHERE tenant_id = $1 AND deleted_at IS NULL

-- Hard delete only via explicit purge job (for GDPR compliance, data retention)
```
- Default all reads to exclude `deleted_at IS NOT NULL`
- Apply soft-delete filter in the repository base, not in every query
- Provide explicit `include_deleted` parameter for admin/audit queries

### Optimistic Locking
```
-- Include version in update WHERE clause
UPDATE orders
SET status = $1, version = version + 1, updated_at = NOW()
WHERE tenant_id = $2 AND id = $3 AND version = $4

-- If affected_rows == 0: raise ConflictError (someone else modified it)
```
- Every mutable entity has a `version` column (integer, starts at 1)
- Every update checks AND increments the version
- Zero affected rows means a concurrent modification — return ConflictError

### Cursor-Based Pagination
```
-- Cursor-based (scalable, consistent with concurrent writes)
SELECT * FROM orders
WHERE tenant_id = $1 AND created_at < $2
ORDER BY created_at DESC
LIMIT $3

-- Return cursor for next page
response = { data: rows, next_cursor: last_row.created_at, has_more: len(rows) == limit }
```
- Default pagination strategy is cursor-based (not offset-based)
- Offset-based is acceptable ONLY for admin UIs with known-small datasets
- Cursor should be opaque to the client (encode timestamp + ID for uniqueness)

### Error Mapping
```
Database Error              → Domain Error
────────────────────────────────────────────
unique_violation            → ConflictError
foreign_key_violation       → ValidationError
check_constraint_violation  → ValidationError
not_found (no rows)         → NotFoundError
connection_error            → InternalError (retry)
timeout                     → InternalError (retry)
```
- Repository catches ALL database-specific errors
- Maps them to domain errors before returning to the service layer
- Service layer NEVER sees database-specific error types

---

## Handler Layer Contract

The handler layer (controller/endpoint) is the HTTP boundary. It is THIN — no business logic.

### Request Lifecycle
```
1. PARSE     — Extract data from HTTP request (body, path params, query params, headers)
2. VALIDATE  — Validate parsed data against schema (return 400 if invalid)
3. EXECUTE   — Call service layer method (pass ctx, tenant_id, validated request)
4. RESPOND   — Map service response to HTTP response (status code + envelope)
```

### Tenant Extraction
```
function handler(request):
    tenant_id = extract_tenant_from_context(request.context)
    // tenant_id was set by auth middleware after JWT validation
    // NEVER extract tenant_id from request body or query params
```

### Trace Span
```
function handler(request):
    span = tracer.start_span("handler.create_order")
    defer span.end()
    span.set_attribute("tenant_id", tenant_id)
    span.set_attribute("handler", "CreateOrder")
    // ... handler logic
```

### Response Envelope
```json
// Success
{
    "data": { ... },
    "meta": {
        "request_id": "uuid",
        "timestamp": "2024-01-01T00:00:00Z"
    }
}

// Success (list)
{
    "data": [ ... ],
    "meta": {
        "total": 142,
        "next_cursor": "encoded_cursor",
        "has_more": true
    }
}

// Error
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human-readable message",
        "details": [
            { "field": "email", "message": "invalid format" }
        ]
    },
    "meta": {
        "request_id": "uuid",
        "timestamp": "2024-01-01T00:00:00Z"
    }
}
```

### Error Mapping
```
Domain Error     → HTTP Status → Error Code
──────────────────────────────────────────────
ValidationError  → 400         → VALIDATION_ERROR
NotFoundError    → 404         → NOT_FOUND
ConflictError    → 409         → CONFLICT
UnauthorizedErr  → 401         → UNAUTHORIZED
ForbiddenError   → 403         → FORBIDDEN
RateLimitError   → 429         → RATE_LIMITED
UpstreamError    → 502         → UPSTREAM_ERROR
InternalError    → 500         → INTERNAL_ERROR
```

---

## Error Handling Contract

### Domain Error Taxonomy (8 Types)

Every backend defines exactly these 8 domain error types:

| Error Type     | Meaning                                  | HTTP | Retryable |
|---------------|------------------------------------------|------|-----------|
| Validation    | Input failed validation rules            | 400  | No        |
| NotFound      | Requested entity does not exist          | 404  | No        |
| Conflict      | State conflict (duplicate, version)      | 409  | No        |
| Unauthorized  | Missing or invalid credentials           | 401  | No        |
| Forbidden     | Valid credentials, insufficient perms    | 403  | No        |
| RateLimit     | Too many requests                        | 429  | Yes       |
| Upstream      | External dependency failed               | 502  | Yes       |
| Internal      | Unexpected server error                  | 500  | Maybe     |

### Error Wrapping
```
// At each boundary, wrap with context
Repository: "find user abc123: connection refused"
Service:    "get user profile: find user abc123: connection refused"
Handler:    logs full chain, returns generic message to client

// NEVER expose internal error details to clients
// Client sees: { "error": { "code": "INTERNAL_ERROR", "message": "Something went wrong" } }
// Server logs: full error chain with stack trace
```

### Rules
- Errors wrap with context at EACH boundary crossing
- Never swallow errors (catch without logging or re-raising)
- Never expose internal details (stack traces, DB errors) to clients
- Log the full error chain server-side with structured logging
- Include request_id in error responses for correlation
- Retryable errors include `Retry-After` header when possible

---

## Testing Contract

### Test Pyramid
```
                    /  E2E  \           — Few, slow, expensive
                   / Integration \      — Some, medium speed
                  /   Unit Tests   \    — Many, fast, cheap
```

### Unit Tests
- Mock ALL external dependencies (DB, cache, HTTP clients, message queues)
- Test business logic in isolation
- One assertion concept per test (may be multiple assert statements)
- Test names describe behavior: `test_create_order_rejects_negative_quantity`

### Integration Tests
- Use REAL databases (via containers like testcontainers)
- Test data flow through actual infrastructure
- Reset database state between tests (truncate or transaction rollback)
- Skip in CI fast lane with a flag (`-short`, `@Tag("integration")`, `@pytest.mark.integration`)

### Table-Driven / Parameterized Tests
```
// Default test style — enumerate inputs and expected outputs
test_cases = [
    { name: "valid email",     input: "a@b.com",  expected: true  },
    { name: "missing @",       input: "ab.com",   expected: false },
    { name: "empty string",    input: "",          expected: false },
    { name: "unicode domain",  input: "a@b.co.jp", expected: true },
]
for each case in test_cases:
    run_test(case.name, () => assert(validate(case.input) == case.expected))
```

### Factory Functions
```
// Create test entities with sensible defaults, override what matters
function build_user(overrides = {}):
    return User(
        id:         overrides.id        ?? random_uuid(),
        tenant_id:  overrides.tenant_id ?? "test-tenant",
        email:      overrides.email     ?? "test@example.com",
        name:       overrides.name      ?? "Test User",
        created_at: overrides.created_at ?? now(),
    )

// Usage in tests — only specify what the test cares about
user = build_user({ email: "duplicate@example.com" })
```

### Assert Behavior, Not Implementation
```
// GOOD: assert the outcome
result = service.create_order(ctx, tenant_id, request)
assert result.status == "confirmed"
assert result.total == 150.00

// BAD: assert implementation details
assert repository.save.was_called_with(expected_entity)
assert cache.set.was_called_once()
```
- Test WHAT the code does, not HOW it does it
- Implementation assertions make refactoring impossible
- Only assert on collaborator calls when the call IS the behavior (e.g., "sends email")

---

## Data Contract Standards

### Entity Base Fields
Every entity MUST include:
```
id:          UUID (primary key, generated server-side)
tenant_id:   UUID (foreign key to tenants table)
created_at:  TIMESTAMP WITH TIME ZONE (set on insert, never modified)
updated_at:  TIMESTAMP WITH TIME ZONE (set on every update)
deleted_at:  TIMESTAMP WITH TIME ZONE (null = active, set on soft delete)
version:     INTEGER (optimistic locking, starts at 1)
created_by:  UUID (user who created, from auth context)
updated_by:  UUID (user who last modified, from auth context)
```

### Timestamp Rules
- ALL timestamps in UTC — no local time zones
- Store as `TIMESTAMP WITH TIME ZONE` in the database
- Serialize as ISO 8601 in API responses: `2024-01-15T09:30:00Z`
- Parse with timezone-aware libraries — never naive datetime

### ID Rules
- Use UUIDv7 for primary keys (time-sortable, index-friendly)
- Never expose auto-increment IDs externally (information leakage)
- External-facing IDs may use prefixed format: `usr_abc123`, `ord_xyz789`
