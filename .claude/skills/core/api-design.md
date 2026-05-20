---
skill: api-design
description: REST/GraphQL/gRPC design principles — versioning, pagination, error formats, status codes, idempotency, rate limiting, OpenAPI
version: "1.0"
tags:
  - api
  - rest
  - graphql
  - grpc
  - openapi
---

# API Design

Generalized API design principles for building consistent, evolvable, and well-documented APIs.

## Versioning

- Version via URL path: `/api/v1/`, `/api/v2/` — never via headers or query params
- Breaking changes increment the major version; additive changes do not
- Run two versions in parallel during migration; deprecate with `Sunset` header
- Never remove fields from responses without a major version bump

## URL Structure

```
GET    /api/v1/users              # list
GET    /api/v1/users/{id}         # single resource
POST   /api/v1/users              # create
PUT    /api/v1/users/{id}         # full replace
PATCH  /api/v1/users/{id}         # partial update
DELETE /api/v1/users/{id}         # delete
GET    /api/v1/users/{id}/orders  # nested sub-resource
POST   /api/v1/users/search       # complex search (body payload)
```

- Use nouns, not verbs (`/users`, not `/getUsers`)
- Use plural for collections (`/orders`, not `/order`)
- Use `kebab-case` for multi-word resources (`/payment-methods`)

## Response Envelope

### Success — single resource
```json
{
  "data": { "id": "usr_01", "name": "Alice" },
  "meta": { "request_id": "req_abc123", "timestamp": "2024-01-01T00:00:00Z" }
}
```

### Success — collection
```json
{
  "data": [ ... ],
  "meta": {
    "total": 500,
    "page": 2,
    "per_page": 20,
    "total_pages": 25
  },
  "links": {
    "self":  "/api/v1/users?page=2",
    "next":  "/api/v1/users?page=3",
    "prev":  "/api/v1/users?page=1",
    "first": "/api/v1/users?page=1",
    "last":  "/api/v1/users?page=25"
  }
}
```

### Error (RFC 7807 Problem Details)

> **Canonical reference**: For the definitive backend error type taxonomy, HTTP status mapping, and implementation patterns, see `backend/archetypes/error-handling.md` (Go) and `backend/archetypes/error-handling-typescript.md` (TypeScript).
```json
{
  "type": "https://api.example.com/errors/validation-failed",
  "title": "Validation Failed",
  "status": 422,
  "detail": "Field 'email' must be a valid email address",
  "instance": "/api/v1/users",
  "request_id": "req_abc123",
  "errors": [
    { "field": "email", "message": "invalid format" }
  ]
}
```

## HTTP Status Codes

| Scenario | Code |
|----------|------|
| GET / PATCH success | 200 |
| POST created | 201 + `Location` header |
| DELETE / async accepted | 202 or 204 |
| Bad request / invalid body | 400 |
| Unauthenticated | 401 |
| Authenticated but forbidden | 403 |
| Resource not found | 404 |
| Method not allowed | 405 |
| Conflict (duplicate) | 409 |
| Validation error | 422 |
| Rate limited | 429 |
| Server error | 500 |
| Downstream unavailable | 503 |

## Pagination

- Default: cursor-based for large/real-time datasets; offset for admin/reporting UIs
- Always cap `limit`/`per_page` (e.g., max 100); default to 20
- Cursor pagination: return opaque `next_cursor` in meta, accept `cursor=` query param
- Never return unbounded collections — even internal APIs

## Idempotency

- `PUT` and `DELETE` must be idempotent by definition
- `POST` for creation: accept `Idempotency-Key` header; cache result for 24h
- Return same response for duplicate idempotency key within TTL window
- Store idempotency records in Redis: `idempotency:{key}` → response payload

## Rate Limiting

- Return `429 Too Many Requests` with `Retry-After` header
- Always include headers on every response:
  ```
  X-RateLimit-Limit: 1000
  X-RateLimit-Remaining: 847
  X-RateLimit-Reset: 1700000000
  ```
- Use token bucket or sliding window algorithm
- Rate limit by API key, then by IP as fallback

## GraphQL Conventions

- Single endpoint: `POST /graphql`
- Use persisted queries in production to prevent abuse
- Implement query depth limit (max 7) and complexity scoring
- Return errors in `errors[]` array alongside partial `data`
- Use `DataLoader` pattern to batch N+1 queries

## gRPC Conventions

- Define `.proto` files in a shared `proto/` directory
- Use `google.rpc.Status` for error details
- Implement deadlines on every client call (`ctx` with timeout)
- Use server-side streaming for large datasets, not repeated unary calls
- Version packages: `package myservice.v1;`

## OpenAPI / Documentation

- Maintain `openapi.yaml` at repo root, generated from code annotations
- Every endpoint: summary, description, request body schema, response schemas, error codes
- Use `$ref` for shared schemas — never inline duplicate definitions
- Publish docs at `/api/docs` (Swagger UI or Redoc)
- Include example request/response in every operation

## API Versioning Strategy

### When to Version
- **DO version:** Breaking changes to response shapes, removed fields, changed field types, removed endpoints
- **DON'T version:** Additive changes (new fields, new endpoints, new optional query params)

### Versioning Approach: URL Path Versioning
Default strategy: `/api/v1/`, `/api/v2/`

**Rules:**
1. All endpoints start at `/api/v1/`
2. When a breaking change is needed:
   a. Keep the old endpoint at `/api/v1/<resource>` (unchanged)
   b. Create new endpoint at `/api/v2/<resource>` with the breaking change
   c. Mark old endpoint as deprecated in api-contracts.md: `@deprecated — use /api/v2/<resource>`
   d. Old endpoint continues to work for minimum 2 phases after deprecation
3. Deprecation timeline:
   - Phase N: deprecation announced, v2 created
   - Phase N+1: deprecation warning header added to v1 responses (`Deprecation: true`, `Sunset: <date>`)
   - Phase N+2: v1 can be removed (with acceptance test confirming no consumers)

### Version Coexistence
- Both v1 and v2 share the same service layer
- Version differences handled at the handler/controller level (response serialization)
- Database schema supports both versions simultaneously
- Never duplicate business logic for versioning — only transform at the API boundary

### api-contracts.md Versioning
When versioned endpoints exist:
```yaml
# api-contracts.md
GET /api/v1/users/:id
  Response: { data: { id, name, email } }
  Status: deprecated (sunset: Phase 5)

GET /api/v2/users/:id
  Response: { data: { id, full_name, email, created_at } }
  Status: active
```

---

## Critical Rules

- Always include `request_id` in every response and every log line
- Validate all inputs at the API boundary — reject early, fail fast
- Never expose internal error messages or stack traces to clients
- Return consistent envelope shape for all success and error responses
- Use HTTPS everywhere; redirect HTTP to HTTPS with 301
