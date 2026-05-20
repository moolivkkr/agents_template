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

## Versioning

- URL path: `/api/v1/`, `/api/v2/` — never headers or query params
- Breaking changes = major version bump; additive changes don't version
- Run two versions in parallel during migration; deprecate with `Sunset` header

## URL Structure

```
GET    /api/v1/users              # list
GET    /api/v1/users/{id}         # single
POST   /api/v1/users              # create
PUT    /api/v1/users/{id}         # full replace
PATCH  /api/v1/users/{id}         # partial update
DELETE /api/v1/users/{id}         # delete
GET    /api/v1/users/{id}/orders  # sub-resource
POST   /api/v1/users/search       # complex search (body)
```

- Nouns not verbs; plural collections; `kebab-case` for multi-word

## Response Envelope

**Success (single):** `{ "data": {...}, "meta": { "request_id", "timestamp" } }`

**Success (collection):** `{ "data": [...], "meta": { "total", "page", "per_page", "total_pages" }, "links": { "self", "next", "prev", "first", "last" } }`

**Error (RFC 7807):** `{ "type", "title", "status", "detail", "instance", "request_id", "errors": [{ "field", "message" }] }`

> See `backend/archetypes/error-handling.md` for definitive error taxonomy.

## HTTP Status Codes

| Scenario | Code | Scenario | Code |
|----------|------|----------|------|
| GET/PATCH success | 200 | Unauthenticated | 401 |
| POST created | 201 + Location | Forbidden | 403 |
| DELETE/async | 202/204 | Not found | 404 |
| Bad request | 400 | Conflict | 409 |
| Validation | 422 | Rate limited | 429 |
| Server error | 500 | Downstream unavailable | 503 |

## Pagination

- Cursor-based for large/real-time; offset for admin/reporting
- Cap `per_page` (max 100, default 20); return opaque `next_cursor`
- Never return unbounded collections

## Idempotency

- PUT/DELETE idempotent by definition
- POST: accept `Idempotency-Key` header; cache result 24h in Redis `idempotency:{key}`

## Rate Limiting

- 429 with `Retry-After`; include `X-RateLimit-Limit/Remaining/Reset` on every response
- Token bucket or sliding window; rate limit by API key then IP fallback

## GraphQL

- Single `POST /graphql`; persisted queries in prod; depth limit 7 + complexity scoring
- `DataLoader` for N+1; errors in `errors[]` alongside partial `data`

## gRPC

- `.proto` in shared `proto/`; `google.rpc.Status` for errors; deadlines on every call
- Server-side streaming for large datasets; package versioning: `package myservice.v1;`

## OpenAPI

- `openapi.yaml` at repo root, generated from annotations; `$ref` for shared schemas
- Every operation: summary, request/response schemas, error codes, examples
- Publish at `/api/docs`

## API Versioning Strategy

- **DO version:** Breaking response shape changes, removed fields/endpoints, changed types
- **DON'T version:** New fields, new endpoints, new optional params
- Both versions share service layer; version differences at handler level only
- Deprecation: Phase N announce → Phase N+1 sunset header → Phase N+2 remove

## Critical Rules

- `request_id` in every response and log line
- Validate all inputs at boundary — reject early
- Never expose internal errors or stack traces
- Consistent envelope for all responses
- HTTPS everywhere; redirect HTTP with 301
