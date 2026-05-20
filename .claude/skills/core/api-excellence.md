---
skill: api-excellence
description: Production API patterns — OpenAPI-first, cursor pagination, domain error codes, idempotency, response envelopes, HATEOAS, versioning strategy
version: "1.0"
tags:
  - api
  - rest
  - pagination
  - errors
  - idempotency
  - openapi
---

# API Excellence

Production-grade API patterns beyond basic REST design.

## OpenAPI-First Development

Define spec before code. Generate types from spec. Validate at runtime.

```yaml
# openapi.yaml — single source of truth
openapi: 3.1.0
paths:
  /api/v1/users:
    get:
      operationId: listUsers
      parameters:
        - name: cursor
          in: query
          schema: { type: string }
        - name: limit
          in: query
          schema: { type: integer, minimum: 1, maximum: 100, default: 20 }
      responses:
        "200":
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ListUsersResponse" }
```

```go
// Validate requests against spec at runtime (middleware)
func ValidateRequest(spec *openapi3.T) func(http.Handler) http.Handler {
    router, _ := gorillamux.NewRouter(spec)
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            route, pathParams, _ := router.FindRoute(r)
            input := &openapi3filter.RequestValidationInput{Request: r, PathParams: pathParams, Route: route}
            if err := openapi3filter.ValidateRequest(r.Context(), input); err != nil {
                writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", err.Error())
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

- Spec is the contract — code conforms to spec
- Generate client SDKs from spec; run spec validation in CI
- Breaking changes must bump major version

## Response Envelope

```go
type ListResponse[T any] struct {
    Data []T      `json:"data"`
    Meta ListMeta `json:"meta"`
}
type ListMeta struct {
    Cursor     *string `json:"cursor,omitempty"`
    HasMore    bool    `json:"has_more"`
    TotalCount int     `json:"total_count"`
}
type ErrorResponse struct {
    Error ErrorBody `json:"error"`
}
type ErrorBody struct {
    Code      string `json:"code"`
    Message   string `json:"message"`
    Details   any    `json:"details,omitempty"`
    RequestID string `json:"request_id"`
}

func writeList[T any](w http.ResponseWriter, data []T, cursor *string, hasMore bool, total int) {
    writeJSON(w, http.StatusOK, ListResponse[T]{Data: data, Meta: ListMeta{Cursor: cursor, HasMore: hasMore, TotalCount: total}})
}
func writeError(w http.ResponseWriter, status int, code, message string) {
    writeJSON(w, status, ErrorResponse{Error: ErrorBody{Code: code, Message: message, RequestID: middleware.RequestID(w)}})
}
```

- Every success: `{ data: ... }` | Every list: `{ data: [...], meta: { cursor, has_more, total_count } }`
- Every error: `{ error: { code, message, details?, request_id } }`

## Cursor Pagination

Never use offset/limit for user-facing APIs. Cursors are stable under concurrent writes.

```go
// Cursor: base64("id:timestamp") — opaque to clients
func (r *UserRepo) List(ctx context.Context, cursor *string, limit int) ([]User, *string, bool, error) {
    if limit <= 0 || limit > 100 { limit = 20 }
    fetchLimit := limit + 1 // fetch limit+1 to determine has_more
    // ... query with WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC
    hasMore := len(users) > limit
    if hasMore { users = users[:limit] }
    // Return nextCursor from last item if hasMore
}
```

- Default 20, max 100 | Fetch `limit+1` for has_more | Stable ordering with tiebreaker on id
- Never expose raw IDs/timestamps in cursor

## Domain Error Codes

```go
const (
    CodeValidationError = "VALIDATION_ERROR"  // 400/422
    CodeNotFound        = "NOT_FOUND"         // 404
    CodeConflict        = "CONFLICT"          // 409
    CodeRateLimited     = "RATE_LIMITED"      // 429
    CodeUpstreamError   = "UPSTREAM_ERROR"    // 502
    CodeUnauthorized    = "UNAUTHORIZED"      // 401
    CodeForbidden       = "FORBIDDEN"         // 403
    CodeInternalError   = "INTERNAL_ERROR"    // 500
)
```

- Clients switch on `error.code`, not HTTP status
- Keep set small and documented in OpenAPI spec
- Never expose internal error messages to clients

## API Versioning

```go
mux.Handle("/api/v1/", v1Router)
mux.Handle("/api/v2/", v2Router)

func DeprecationMiddleware(sunset time.Time) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            w.Header().Set("Deprecation", "true")
            w.Header().Set("Sunset", sunset.Format(http.TimeFormat))
            w.Header().Set("Link", `</api/v2/>; rel="successor-version"`)
            next.ServeHTTP(w, r)
        })
    }
}
```

- URL path versioning: `/v1/`, `/v2/` — simple, visible, cacheable
- Breaking = new version; additive = backwards-compatible
- Run old + new in parallel during transition

## Idempotency

POST operations accept `Idempotency-Key` header. Cache response for 24h TTL.

```go
func IdempotencyMiddleware(store IdempotencyStore) func(http.Handler) http.Handler {
    // On POST: check store for key → if found, replay cached response with Idempotent-Replayed header
    // If not found: capture response, cache it, return
}
```

- Store in Redis: `idempotency:{key}` → response payload
- PUT/DELETE idempotent by HTTP semantics — no key needed

## HATEOAS Links

```json
{
  "data": { "id": "order_123", "status": "pending" },
  "links": {
    "self": "/api/v1/orders/order_123",
    "cancel": "/api/v1/orders/order_123/cancel",
    "payment": "/api/v1/orders/order_123/payment"
  }
}
```

- `self` link on every resource; conditional action links based on state
- Clients follow links instead of constructing URLs

## Critical Rules

- Spec first, code second — OpenAPI is the contract
- Standard envelope for every response — no ad-hoc shapes
- Cursor pagination for all user-facing lists
- Machine-readable error codes in every error
- Idempotency keys on all POST endpoints
- Version in URL path; breaking changes = new major version
- `request_id` in every response
