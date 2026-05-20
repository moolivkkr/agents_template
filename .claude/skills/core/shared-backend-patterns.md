# Shared Backend Patterns — Language-Agnostic Contracts

> Single source of truth for cross-cutting backend concerns. Every backend service MUST follow these contracts.

---

## Multi-Tenancy Rules

### Parameter Ordering
```
function DoSomething(context, tenant_id, ...other_params) -> result, error
```
- `context` ALWAYS first, `tenant_id` ALWAYS second — non-negotiable

### Database Queries
```sql
-- EVERY query MUST filter by tenant_id
SELECT * FROM orders WHERE tenant_id = ? AND id = ?
-- Indexes MUST lead with tenant_id
CREATE INDEX idx_orders_tenant_status ON orders(tenant_id, status)
-- JOINs MUST filter tenant_id on BOTH sides
```

### RLS (Defense in Depth)
```sql
CREATE POLICY tenant_isolation ON orders USING (tenant_id = current_setting('app.current_tenant')::uuid);
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
```
Application-level filtering is PRIMARY; RLS is safety net.

### Logging & Metrics
Every log line and metric MUST include `tenant_id`. For high-cardinality, use tenant tier instead of raw ID.

### Tenant Context Flow
`Request → Auth Middleware → Extract tenant_id → Store in context → Pass to service → Pass to repo → Include in every query/log/metric`

---

## Service Layer Contract

### Constructor: `ServiceConstructor(repo: Interface, cache: Interface, publisher: Interface, logger: Interface) -> Service`
- Accept interfaces for ALL deps; no internal construction; dependencies injected

### Method Signature: `service.DoOp(ctx, tenant_id, request) -> response, error`
- ctx first, tenant_id second, request third; return response + error

### Audit Trail
Every mutation logs: who, what, when, tenant, before/after state, client IP. Append-only dedicated table.

### Cache-Aside Pattern
1. Check cache → 2. Miss: query DB → 3. Populate cache with TTL
- Invalidate on EVERY write (create/update/delete) + related list caches
- Key format: `{tenant_id}:{entity_type}:{entity_id}`

---

## Repository Layer Contract

### Parameterized Queries Only
```
query("SELECT * FROM users WHERE tenant_id = $1 AND email = $2", tenant_id, email)
-- NEVER string concatenation
```

### Soft Delete
```sql
UPDATE orders SET deleted_at = NOW() WHERE tenant_id = $1 AND id = $2
-- Every read: WHERE deleted_at IS NULL (apply in repo base, not every query)
```

### Optimistic Locking
```sql
UPDATE orders SET status = $1, version = version + 1 WHERE tenant_id = $2 AND id = $3 AND version = $4
-- affected_rows == 0 → ConflictError
```

### Cursor-Based Pagination
Default strategy. Offset acceptable only for admin UIs with small datasets. Cursor opaque to client (encode timestamp + ID).

### Error Mapping
`unique_violation → Conflict | foreign_key/check_constraint → Validation | no rows → NotFound | connection/timeout → Internal (retry)`
Repository catches ALL DB-specific errors, maps to domain errors. Service never sees DB types.

---

## Handler Layer Contract

### Request Lifecycle: PARSE → VALIDATE → EXECUTE → RESPOND

### Tenant Extraction
Extract from context (set by auth middleware after JWT validation). NEVER from request body or query params.

### Response Envelope
```json
// Success: { "data": {...}, "meta": { "request_id", "timestamp" } }
// List: { "data": [...], "meta": { "total", "next_cursor", "has_more" } }
// Error: { "error": { "code", "message", "details" }, "meta": { "request_id" } }
```

### Error Mapping
`Validation→400 | NotFound→404 | Conflict→409 | Unauthorized→401 | Forbidden→403 | RateLimit→429 | Upstream→502 | Internal→500`

---

## Error Handling Contract

### 8 Domain Error Types

| Type | HTTP | Retryable |
|------|------|-----------|
| Validation | 400 | No |
| NotFound | 404 | No |
| Conflict | 409 | No |
| Unauthorized | 401 | No |
| Forbidden | 403 | No |
| RateLimit | 429 | Yes |
| Upstream | 502 | Yes |
| Internal | 500 | Maybe |

- Wrap with context at each boundary; never swallow; never expose internals to clients
- Include request_id in responses; retryable errors include `Retry-After`

---

## Testing Contract

### Test Pyramid: Unit (many, fast, mocked) → Integration (real DB via containers) → E2E (few, critical paths)

### Table-Driven Tests as default style; factory functions with sensible defaults (override only what matters)

### Assert behavior, not implementation. Only assert collaborator calls when the call IS the behavior.

---

## Data Contract Standards

### Entity Base Fields
`id` (UUIDv7), `tenant_id`, `created_at`, `updated_at`, `deleted_at`, `version` (int, starts 1), `created_by`, `updated_by`

### Timestamps: ALL UTC, `TIMESTAMP WITH TIME ZONE`, serialize ISO 8601
### IDs: UUIDv7 for PKs (time-sortable); never expose auto-increment; external format: `usr_abc123`
