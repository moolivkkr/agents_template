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

Production-grade API patterns that go beyond basic REST design. Every public API should follow these conventions for consistency, reliability, and developer experience.

## OpenAPI-First Development

Define the spec **before** writing code. Generate types from the spec. Validate at runtime.

```yaml
# openapi.yaml — single source of truth
openapi: 3.1.0
info:
  title: Users API
  version: "1.0"
paths:
  /api/v1/users:
    get:
      operationId: listUsers
      parameters:
        - name: cursor
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ListUsersResponse"
```

```typescript
// Generate types from spec — never hand-write API types
// npx openapi-typescript openapi.yaml -o src/api/types.ts
import type { paths } from "./api/types";

type ListUsersResponse = paths["/api/v1/users"]["get"]["responses"]["200"]["content"]["application/json"];
```

```go
// Validate requests against spec at runtime (middleware)
import "github.com/getkin/kin-openapi/openapi3filter"

func ValidateRequest(spec *openapi3.T) func(http.Handler) http.Handler {
    router, _ := gorillamux.NewRouter(spec)
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            route, pathParams, _ := router.FindRoute(r)
            input := &openapi3filter.RequestValidationInput{
                Request:    r,
                PathParams: pathParams,
                Route:      route,
            }
            if err := openapi3filter.ValidateRequest(r.Context(), input); err != nil {
                writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", err.Error())
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

- Spec is the contract — code must conform to spec, not the other way around
- Generate client SDKs from the spec for frontend and partner integrations
- Run spec validation in CI — breaking changes must bump the major version
- Every endpoint has request schema, response schema, and documented error codes

## Response Envelope

Consistent structure across all endpoints. Clients parse one shape.

```typescript
// Single resource
interface SingleResponse<T> {
  data: T;
}

// Collection with cursor pagination
interface ListResponse<T> {
  data: T[];
  meta: {
    cursor?: string;     // opaque cursor for next page
    has_more: boolean;   // whether more results exist
    total_count: number; // total matching records (when affordable to compute)
  };
}

// Error response
interface ErrorResponse {
  error: {
    code: string;         // machine-readable: "NOT_FOUND", "VALIDATION_ERROR"
    message: string;      // human-readable explanation
    details?: object;     // optional structured details (validation errors, etc.)
    request_id: string;   // for support/debugging correlation
  };
}
```

```go
// Go implementation
type ListResponse[T any] struct {
    Data []T          `json:"data"`
    Meta ListMeta     `json:"meta"`
}

type ListMeta struct {
    Cursor     *string `json:"cursor,omitempty"`
    HasMore    bool    `json:"has_more"`
    TotalCount int     `json:"total_count"`
}

type SingleResponse[T any] struct {
    Data T `json:"data"`
}

type ErrorBody struct {
    Code      string `json:"code"`
    Message   string `json:"message"`
    Details   any    `json:"details,omitempty"`
    RequestID string `json:"request_id"`
}

type ErrorResponse struct {
    Error ErrorBody `json:"error"`
}

// Helper to write consistent responses
func writeJSON[T any](w http.ResponseWriter, status int, payload T) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(payload)
}

func writeList[T any](w http.ResponseWriter, data []T, cursor *string, hasMore bool, total int) {
    writeJSON(w, http.StatusOK, ListResponse[T]{
        Data: data,
        Meta: ListMeta{Cursor: cursor, HasMore: hasMore, TotalCount: total},
    })
}

func writeError(w http.ResponseWriter, status int, code, message string) {
    writeJSON(w, status, ErrorResponse{
        Error: ErrorBody{Code: code, Message: message, RequestID: middleware.RequestID(w)},
    })
}
```

- Every success response wraps in `{ data: ... }`
- Every list wraps in `{ data: [...], meta: { cursor, has_more, total_count } }`
- Every error wraps in `{ error: { code, message, details?, request_id } }`
- Clients never guess the shape — one parser for success, one for error

## Cursor Pagination

Never use offset/limit for user-facing APIs. Cursors are stable under concurrent writes.

```go
// Cursor: base64-encoded "id:timestamp" for stable ordering
func EncodeCursor(id string, createdAt time.Time) string {
    raw := fmt.Sprintf("%s:%d", id, createdAt.UnixNano())
    return base64.URLEncoding.EncodeToString([]byte(raw))
}

func DecodeCursor(cursor string) (id string, createdAt time.Time, err error) {
    raw, err := base64.URLEncoding.DecodeString(cursor)
    if err != nil {
        return "", time.Time{}, fmt.Errorf("invalid cursor: %w", err)
    }
    parts := strings.SplitN(string(raw), ":", 2)
    if len(parts) != 2 {
        return "", time.Time{}, fmt.Errorf("malformed cursor")
    }
    nanos, err := strconv.ParseInt(parts[1], 10, 64)
    if err != nil {
        return "", time.Time{}, fmt.Errorf("invalid timestamp in cursor: %w", err)
    }
    return parts[0], time.Unix(0, nanos), nil
}

// Query with cursor
func (r *UserRepo) List(ctx context.Context, cursor *string, limit int) ([]User, *string, bool, error) {
    if limit <= 0 || limit > 100 {
        limit = 20 // default page size, max 100
    }
    // Fetch limit+1 to determine has_more
    fetchLimit := limit + 1

    var args []any
    query := "SELECT id, email, created_at FROM users"

    if cursor != nil {
        id, ts, err := DecodeCursor(*cursor)
        if err != nil {
            return nil, nil, false, err
        }
        query += " WHERE (created_at, id) < ($1, $2)"
        args = append(args, ts, id)
    }
    query += " ORDER BY created_at DESC, id DESC LIMIT $" + strconv.Itoa(len(args)+1)
    args = append(args, fetchLimit)

    rows, err := r.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, nil, false, err
    }
    defer rows.Close()

    var users []User
    for rows.Next() {
        var u User
        if err := rows.Scan(&u.ID, &u.Email, &u.CreatedAt); err != nil {
            return nil, nil, false, err
        }
        users = append(users, u)
    }

    hasMore := len(users) > limit
    if hasMore {
        users = users[:limit] // trim the extra row
    }

    var nextCursor *string
    if hasMore {
        last := users[len(users)-1]
        c := EncodeCursor(last.ID, last.CreatedAt)
        nextCursor = &c
    }
    return users, nextCursor, hasMore, nil
}
```

- Encode cursor as base64 of `id:timestamp` — opaque to clients
- Default page size 20, maximum 100 — reject larger requests
- Fetch `limit + 1` rows to determine `has_more` without a separate COUNT query
- Stable ordering required: `ORDER BY created_at DESC, id DESC` (tiebreaker on id)
- Never expose raw IDs or timestamps in the cursor — always encode

## Domain Error Codes

Machine-readable codes that clients switch on. Human-readable messages for display.

```go
// Domain error codes — clients switch on these, not HTTP status codes
const (
    CodeValidationError = "VALIDATION_ERROR"  // 400/422 — invalid input
    CodeNotFound        = "NOT_FOUND"         // 404 — resource doesn't exist
    CodeConflict        = "CONFLICT"          // 409 — duplicate, version mismatch
    CodeRateLimited     = "RATE_LIMITED"      // 429 — too many requests
    CodeUpstreamError   = "UPSTREAM_ERROR"    // 502 — dependency failed
    CodeUnauthorized    = "UNAUTHORIZED"      // 401 — missing/invalid auth
    CodeForbidden       = "FORBIDDEN"         // 403 — authenticated but not allowed
    CodeInternalError   = "INTERNAL_ERROR"    // 500 — unexpected server error
)

// Map domain codes to HTTP status
var codeToStatus = map[string]int{
    CodeValidationError: http.StatusUnprocessableEntity,
    CodeNotFound:        http.StatusNotFound,
    CodeConflict:        http.StatusConflict,
    CodeRateLimited:     http.StatusTooManyRequests,
    CodeUpstreamError:   http.StatusBadGateway,
    CodeUnauthorized:    http.StatusUnauthorized,
    CodeForbidden:       http.StatusForbidden,
    CodeInternalError:   http.StatusInternalServerError,
}

// Domain error type
type DomainError struct {
    Code    string
    Message string
    Details any
}

func (e *DomainError) Error() string { return e.Message }

// Error handler middleware
func ErrorHandler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if err := recover(); err != nil {
                writeError(w, http.StatusInternalServerError, CodeInternalError, "internal error")
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

- Every error response includes a machine-readable `code` string
- Clients switch on `error.code`, not HTTP status — more precise
- Keep the set small and well-documented — add new codes in the OpenAPI spec
- Never expose internal error messages to clients — log them server-side

## API Versioning

```
GET /api/v1/users         # current stable version
GET /api/v2/users         # next version with breaking changes
```

```go
// Route versioned handlers
mux.Handle("/api/v1/", v1Router)
mux.Handle("/api/v2/", v2Router)

// Deprecation header on old versions
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
- Breaking changes = new major version (field removal, type change, behavior change)
- Additive changes are backwards-compatible: new fields, new endpoints, new optional params
- Set `Deprecation` and `Sunset` headers on old versions with migration timeline
- Run old and new versions in parallel during transition period

## Idempotency

POST operations must support idempotency keys for safe retries.

```go
// Client sends: POST /api/v1/orders  Idempotency-Key: <uuid>
func IdempotencyMiddleware(store IdempotencyStore) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            if r.Method != http.MethodPost {
                next.ServeHTTP(w, r)
                return
            }
            key := r.Header.Get("Idempotency-Key")
            if key == "" {
                next.ServeHTTP(w, r) // no key = no idempotency
                return
            }

            // Check for cached response
            if cached, found := store.Get(r.Context(), key); found {
                w.Header().Set("Idempotent-Replayed", "true")
                w.WriteHeader(cached.StatusCode)
                w.Write(cached.Body)
                return
            }

            // Capture response
            rec := httptest.NewRecorder()
            next.ServeHTTP(rec, r)

            // Cache for 24h
            store.Set(r.Context(), key, CachedResponse{
                StatusCode: rec.Code,
                Body:       rec.Body.Bytes(),
                Headers:    rec.Header(),
            }, 24*time.Hour)

            // Write actual response
            for k, v := range rec.Header() {
                w.Header()[k] = v
            }
            w.WriteHeader(rec.Code)
            w.Write(rec.Body.Bytes())
        })
    }
}

// Redis-backed idempotency store
type RedisIdempotencyStore struct {
    client *redis.Client
}

func (s *RedisIdempotencyStore) Get(ctx context.Context, key string) (CachedResponse, bool) {
    val, err := s.client.Get(ctx, "idempotency:"+key).Bytes()
    if err != nil {
        return CachedResponse{}, false
    }
    var cached CachedResponse
    json.Unmarshal(val, &cached)
    return cached, true
}

func (s *RedisIdempotencyStore) Set(ctx context.Context, key string, resp CachedResponse, ttl time.Duration) {
    data, _ := json.Marshal(resp)
    s.client.Set(ctx, "idempotency:"+key, data, ttl)
}
```

- POST operations accept `Idempotency-Key` header (client-generated UUID)
- Cache and return the same response for duplicate keys within 24h TTL
- Set `Idempotent-Replayed: true` header when returning cached response
- PUT and DELETE are idempotent by HTTP semantics — no key needed
- Store idempotency records in Redis: `idempotency:{key}` -> response

## HATEOAS Links

Include action links in responses to reduce client-side URL construction.

```json
{
  "data": {
    "id": "order_123",
    "status": "pending",
    "total": 99.99
  },
  "links": {
    "self": "/api/v1/orders/order_123",
    "cancel": "/api/v1/orders/order_123/cancel",
    "payment": "/api/v1/orders/order_123/payment",
    "items": "/api/v1/orders/order_123/items"
  }
}
```

```go
type Links map[string]string

func OrderLinks(orderID string, status string) Links {
    links := Links{
        "self":  fmt.Sprintf("/api/v1/orders/%s", orderID),
        "items": fmt.Sprintf("/api/v1/orders/%s/items", orderID),
    }
    // Conditional links based on state
    if status == "pending" {
        links["cancel"] = fmt.Sprintf("/api/v1/orders/%s/cancel", orderID)
        links["payment"] = fmt.Sprintf("/api/v1/orders/%s/payment", orderID)
    }
    if status == "shipped" {
        links["tracking"] = fmt.Sprintf("/api/v1/orders/%s/tracking", orderID)
    }
    return links
}
```

- Include `self` link on every resource
- Add action links based on resource state — clients discover available actions
- Clients follow links instead of constructing URLs — decouples client from URL structure
- Use relative paths — let the client prepend the base URL

## URL & Resource Naming

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

## HTTP Status Codes

Domain error codes (above) are what clients switch on; these are the transport-level status codes each
code maps to. See `backend/archetypes/error-handling-go.md` for the canonical error taxonomy.

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
| Downstream unavailable | 502 / 503 |

## Rate Limiting

- Return `429 Too Many Requests` with a `Retry-After` header
- Include rate-limit headers on every response:
  ```
  X-RateLimit-Limit: 1000
  X-RateLimit-Remaining: 847
  X-RateLimit-Reset: 1700000000
  ```
- Use a token bucket or sliding window algorithm
- Rate limit by API key first, then by IP as a fallback

## GraphQL Conventions

- Single endpoint: `POST /graphql`
- Use persisted queries in production to prevent abuse
- Enforce a query depth limit (max 7) and complexity scoring
- Return errors in the `errors[]` array alongside any partial `data`
- Use the `DataLoader` pattern to batch N+1 queries

## gRPC Conventions

- Define `.proto` files in a shared `proto/` directory; version packages: `package myservice.v1;`
- Use `google.rpc.Status` for error details
- Set deadlines on every client call (`ctx` with timeout)
- Use server-side streaming for large datasets, not repeated unary calls

## OpenAPI Documentation Delivery

- Maintain `openapi.yaml` at the repo root (see OpenAPI-First above — it is the contract)
- Every endpoint documents: summary, request body schema, response schemas, and error codes
- Use `$ref` for shared schemas — never inline duplicate definitions
- Publish rendered docs at `/api/docs` (Swagger UI or Redoc), with an example request/response per operation

## Critical Rules

- Spec first, code second — OpenAPI is the contract, not an afterthought
- Every response uses the standard envelope — no ad-hoc shapes
- Cursor pagination for all user-facing lists — never offset/limit
- Machine-readable error codes in every error response — clients switch on codes, not messages
- Idempotency keys on all POST endpoints — safe retries are mandatory
- Version in URL path — breaking changes require a new major version
- Include `request_id` in every response for debugging correlation
