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
          description: A page of users   # required on every response object
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ListUsersResponse"
components:
  schemas:
    ListUsersResponse:   # the response envelope (api/response-envelope.md)
      type: object
      required: [data, meta]
      properties:
        data:
          type: array
          items: { $ref: "#/components/schemas/User" }
        meta:
          type: object
          required: [request_id, pagination]
          properties:
            request_id: { type: string }
            pagination:
              type: object
              required: [next_cursor, has_more, limit]
              properties:
                next_cursor: { type: [string, "null"] }   # null when has_more is false
                has_more: { type: boolean }
                limit: { type: integer }
    User:
      type: object
      required: [id, email]
      properties:
        id: { type: string }
        email: { type: string, format: email }
```

```typescript
// Generate types from spec — never hand-write API types
// npx openapi-typescript openapi.yaml -o src/api/types.ts
import type { paths } from "./api/types";

type ListUsersResponse = paths["/api/v1/users"]["get"]["responses"]["200"]["content"]["application/json"];
```

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, kin-openapi v0.149.0, against the archetype apperr + middleware packages (tests/archetype-compile/go/run.sh).

```go
// Validate requests against spec at runtime (middleware)
import (
    "github.com/getkin/kin-openapi/openapi3"
    "github.com/getkin/kin-openapi/openapi3filter"
    "github.com/getkin/kin-openapi/routers/gorillamux"
)

func ValidateRequest(spec *openapi3.T) (func(http.Handler) http.Handler, error) {
    router, err := gorillamux.NewRouter(spec)
    if err != nil {
        return nil, fmt.Errorf("openapi router: %w", err) // fail at startup, not per request
    }
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            route, pathParams, err := router.FindRoute(r)
            if err != nil { // not in the spec: deny by default
                writeError(w, r, http.StatusNotFound, "NOT_FOUND", "Not found.", false)
                return
            }
            input := &openapi3filter.RequestValidationInput{
                Request:    r,
                PathParams: pathParams,
                Route:      route,
            }
            if err := openapi3filter.ValidateRequest(r.Context(), input); err != nil {
                // details[] comes from the validator's field errors mapped to stable codes, never err.Error()
                writeError(w, r, http.StatusBadRequest, "VALIDATION_FAILED", "Some fields are invalid.", false)
                return
            }
            next.ServeHTTP(w, r)
        })
    }, nil
}
```

- Spec is the contract — code must conform to spec, not the other way around
- Generate client SDKs from the spec for frontend and partner integrations
- Run spec validation in CI — breaking changes must bump the major version
- Every endpoint has request schema, response schema, and documented error codes

## Response Envelope

**The shape is defined once, in `~/.claude/skills/api/response-envelope.md`; that file wins over
anything here.** Summary: success is `{data, meta}` and error is `{error}`, never both; list metadata
lives in `meta.pagination`.

```typescript
// Success — single resource (200/201)
type ApiSuccess<T> = { data: T; meta: { request_id: string; pagination?: Pagination } };

// Success — collection (cursor pagination; data is always an array, [] when empty)
type Pagination = {
  next_cursor: string | null; // opaque; null when has_more is false
  has_more: boolean;
  limit: number;
  total_count?: number;       // only when cheap to compute AND the UI shows it
};

// Error — no `data` key; the HTTP status carries the class
type ApiErrorBody = {
  error: {
    code: string;             // UPPER_SNAKE, stable, documented: "VALIDATION_FAILED", "NOT_FOUND"
    message: string;          // safe to show a user
    details?: { field: string; code: string; message: string }[];
    request_id: string;       // equals the X-Request-Id header
    retryable: boolean;
  };
};
```

```go
// Go implementation — the types from api/response-envelope.md
type Meta struct {
    RequestID  string      `json:"request_id"`
    Pagination *Pagination `json:"pagination,omitempty"`
}
type Pagination struct {
    NextCursor *string `json:"next_cursor"`
    HasMore    bool    `json:"has_more"`
    Limit      int     `json:"limit"`
    TotalCount *int    `json:"total_count,omitempty"`
}
type Success[T any] struct {
    Data T    `json:"data"`
    Meta Meta `json:"meta"`
}
type APIError struct {
    Code      string       `json:"code"`
    Message   string       `json:"message"`
    Details   []FieldError `json:"details,omitempty"`
    RequestID string       `json:"request_id"`
    Retryable bool         `json:"retryable"`
}
type FieldError struct {
    Field   string `json:"field"`
    Code    string `json:"code"` // lower_snake, stable
    Message string `json:"message"`
}
type ErrorBody struct {
    Error APIError `json:"error"`
}

func writeJSON[T any](w http.ResponseWriter, status int, payload T) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    _ = json.NewEncoder(w).Encode(payload)
}

func writeOne[T any](w http.ResponseWriter, r *http.Request, status int, v T) {
    writeJSON(w, status, Success[T]{Data: v, Meta: Meta{RequestID: middleware.RequestIDFromContext(r.Context())}})
}

func writeList[T any](w http.ResponseWriter, r *http.Request, items []T, next *string, hasMore bool, limit int) {
    if items == nil {
        items = []T{} // never null
    }
    writeJSON(w, http.StatusOK, Success[[]T]{Data: items, Meta: Meta{
        RequestID:  middleware.RequestIDFromContext(r.Context()),
        Pagination: &Pagination{NextCursor: next, HasMore: hasMore, Limit: limit},
    }})
}

func writeError(w http.ResponseWriter, r *http.Request, status int, code, message string, retryable bool) {
    writeJSON(w, status, ErrorBody{Error: APIError{
        Code: code, Message: message, RequestID: middleware.RequestIDFromContext(r.Context()), Retryable: retryable,
    }})
}
```

- Every success response is `{ data, meta: { request_id } }`; lists add `meta.pagination`
  `{ next_cursor, has_more, limit, total_count? }`
- Every error is `{ error: { code, message, details[], request_id, retryable } }` with no `data`
- Clients branch on the HTTP status (or `"error" in body`), never on `error === null`
- Clients never guess the shape — one parser for success, one for error

## Cursor Pagination

Never use offset/limit for user-facing APIs. Cursors are stable under concurrent writes. The request is
`?cursor=<next_cursor>&limit=<n>`; the repository below returns what `writeList` puts in
`meta.pagination`.

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

// Query with cursor. tenantID is the verified tenant from the auth middleware's context — never a
// request value. limit is 1..100 (the handler defaults a missing limit to 20); anything else is a
// 400 VALIDATION_FAILED, never clamped.
func (r *UserRepo) List(ctx context.Context, tenantID string, cursor *string, limit int) ([]User, *string, bool, error) {
    if limit < 1 || limit > 100 {
        return nil, nil, false, &DomainError{Code: CodeValidationFailed, Message: "Some fields are invalid.",
            Details: []FieldError{{Field: "limit", Code: "out_of_range", Message: "Limit must be a whole number from 1 to 100."}}}
    }
    // Fetch limit+1 to determine has_more
    fetchLimit := limit + 1

    args := []any{tenantID}
    query := "SELECT id, email, created_at FROM users WHERE tenant_id = $1"

    if cursor != nil {
        id, ts, err := DecodeCursor(*cursor)
        if err != nil {
            return nil, nil, false, &DomainError{Code: CodeValidationFailed, Message: "Some fields are invalid.",
                Details: []FieldError{{Field: "cursor", Code: "invalid_cursor", Message: "The page cursor is invalid."}}}
        }
        query += " AND (created_at, id) < ($2, $3)"
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
    if err := rows.Err(); err != nil {
        return nil, nil, false, err
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
// (the table in api/response-envelope.md is canonical)
const (
    CodeMalformedRequest = "MALFORMED_REQUEST"       // 400 — unreadable body: bad JSON, too large
    CodeValidationFailed = "VALIDATION_FAILED"       // 400 — input fails schema; details[] lists fields
    CodeUnauthenticated  = "UNAUTHENTICATED"         // 401 — missing/invalid/expired credentials
    CodeForbidden        = "FORBIDDEN"               // 403 — authenticated but not allowed
    CodeNotFound         = "NOT_FOUND"               // 404 — missing OR another tenant's/owner's object
    CodeConflict         = "CONFLICT"                // 409 — state conflict, duplicate, version mismatch
    CodeIdempotencyReuse = "IDEMPOTENCY_KEY_REUSED"  // 409 — same key, different request body
    CodeBusinessRule     = "BUSINESS_RULE_VIOLATION" // 422 — valid shape, rejected by a domain rule
    CodeRateLimited      = "RATE_LIMITED"            // 429 — with Retry-After; retryable
    CodeInternal         = "INTERNAL"                // 500 — generic message; cause in logs
    CodeUnavailable      = "UNAVAILABLE"             // 503 — dependency down; retryable
)

// Map domain codes to HTTP status (and whether a client may retry)
var codeToStatus = map[string]int{
    CodeMalformedRequest: http.StatusBadRequest,
    CodeValidationFailed: http.StatusBadRequest,
    CodeUnauthenticated:  http.StatusUnauthorized,
    CodeForbidden:        http.StatusForbidden,
    CodeNotFound:         http.StatusNotFound,
    CodeConflict:         http.StatusConflict,
    CodeIdempotencyReuse: http.StatusConflict,
    CodeBusinessRule:     http.StatusUnprocessableEntity,
    CodeRateLimited:      http.StatusTooManyRequests,
    CodeInternal:         http.StatusInternalServerError,
    CodeUnavailable:      http.StatusServiceUnavailable,
}
var retryableCodes = map[string]bool{CodeRateLimited: true, CodeUnavailable: true}

// Domain error type
type DomainError struct {
    Code    string
    Message string       // user-safe; never err.Error() from a driver or upstream
    Details []FieldError // field-level problems for VALIDATION_FAILED
}

func (e *DomainError) Error() string { return e.Message }

// Error handler middleware
func ErrorHandler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if err := recover(); err != nil {
                slog.ErrorContext(r.Context(), "panic", "panic", err, "request_id", middleware.RequestIDFromContext(r.Context()))
                writeError(w, r, http.StatusInternalServerError, CodeInternal, "Something went wrong.", false)
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

```text
GET /api/v1/users         # current stable version
GET /api/v2/users         # next version with breaking changes
```

```go
// Route versioned handlers:
//
//     mux.Handle("/api/v1/", DeprecationMiddleware(v1Sunset)(v1Router))
//     mux.Handle("/api/v2/", v2Router)

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

POST operations must support idempotency keys so a client (or an upstream service) can retry safely.
This is the **inbound** half. The outbound half — never retrying a non-idempotent call that timed out
unless it carries a key — is in `core/resiliency-patterns.md` §Retry.

```go
// Client sends: POST /api/v1/orders  Idempotency-Key: <uuid>
func IdempotencyMiddleware(store IdempotencyStore) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            key := r.Header.Get("Idempotency-Key")
            if r.Method != http.MethodPost || key == "" {
                next.ServeHTTP(w, r)
                return
            }
            // Scope the key to the caller: one tenant's key must never replay another's response.
            tenantID, err := middleware.TenantIDFromContext(r.Context()) // from the verified token
            if err != nil {
                writeError(w, r, http.StatusUnauthorized, CodeUnauthenticated, "Sign in to continue.", false)
                return
            }
            userID, _ := middleware.UserIDFromContext(r.Context())
            body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
            if err != nil {
                writeError(w, r, http.StatusBadRequest, CodeMalformedRequest, "The request could not be read.", false)
                return
            }
            r.Body = io.NopCloser(bytes.NewReader(body))
            scoped := tenantID.String() + ":" + userID.String() + ":" + key
            hash := sha256.Sum256(append([]byte(r.Method+" "+r.URL.Path+"\n"), body...))

            // Claim the key atomically (SET NX with a short lock TTL): a concurrent duplicate waits or gets 409.
            rec, state, err := store.Claim(r.Context(), scoped, hash[:], 30*time.Second)
            switch {
            case err != nil:
                writeError(w, r, http.StatusServiceUnavailable, CodeUnavailable, "Try again shortly.", true)
                return
            case state == ClaimReplay && !bytes.Equal(rec.RequestHash, hash[:]):
                writeError(w, r, http.StatusConflict, CodeIdempotencyReuse, "This Idempotency-Key was used for a different request.", false)
                return
            case state == ClaimReplay:
                w.Header().Set("Idempotent-Replayed", "true")
                w.WriteHeader(rec.StatusCode)
                _, _ = w.Write(rec.Body)
                return
            case state == ClaimInFlight:
                writeError(w, r, http.StatusConflict, CodeConflict, "The same request is still being processed.", true)
                return
            }

            cw := newCaptureWriter(w) // tees status + body to the real writer
            next.ServeHTTP(cw, r)
            if cw.status >= 500 {
                store.Release(r.Context(), scoped) // a failed attempt must stay retryable
                return
            }
            store.Complete(r.Context(), scoped, CachedResponse{RequestHash: hash[:], StatusCode: cw.status, Body: cw.body.Bytes()}, 24*time.Hour)
        })
    }
}
```

- POST operations accept an `Idempotency-Key` header (client-generated UUID)
- The key is scoped to tenant + user; the stored record carries a hash of method, path and body
- Same key + same request within 24h → the stored response, with `Idempotent-Replayed: true`
- Same key + a different body → `409 IDEMPOTENCY_KEY_REUSED`
- A duplicate while the first is still running → `409 CONFLICT` with `retryable: true`, never a second execution
- 5xx outcomes are not stored, so the client's retry runs again
- A store error fails closed (503), never "process without idempotency"
- PUT and DELETE are idempotent by HTTP semantics — no key needed
- Store records in Redis (`idempotency:{tenant}:{user}:{key}`) or a table with a unique constraint

## HATEOAS Links

Include action links in responses to reduce client-side URL construction.

Links live **inside the resource** (`data.links`), so the envelope keeps exactly `data` and `meta` at
the top level.

```json
{
  "data": {
    "id": "order_123",
    "status": "pending",
    "total_cents": 9999,
    "links": {
      "self": "/api/v1/orders/order_123",
      "cancel": "/api/v1/orders/order_123/cancel",
      "payment": "/api/v1/orders/order_123/payment",
      "items": "/api/v1/orders/order_123/items"
    }
  },
  "meta": { "request_id": "b7e1c2…" }
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

```text
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
| Invalid body / validation failed (`VALIDATION_FAILED`) | 400 |
| Unauthenticated (`UNAUTHENTICATED`) | 401 |
| Authenticated but forbidden (`FORBIDDEN`) | 403 |
| Not found, or another tenant's/owner's object (`NOT_FOUND`) | 404 |
| Method not allowed | 405 |
| Conflict / duplicate / idempotency key reused | 409 |
| Business rule rejected a valid request (`BUSINESS_RULE_VIOLATION`) | 422 |
| Rate limited (`RATE_LIMITED`, `Retry-After`) | 429 |
| Server error (`INTERNAL`) | 500 |
| Downstream unavailable (`UNAVAILABLE`) | 503 |

## Rate Limiting

- Return `429 Too Many Requests` with a `Retry-After` header
- Include rate-limit headers on every response:
  ```text
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
- Every response uses the envelope in `api/response-envelope.md` — no ad-hoc shapes
- Cursor pagination for all user-facing lists — never offset/limit
- Machine-readable error codes in every error response — clients switch on codes, not messages
- Idempotency keys on all POST endpoints — safe retries are mandatory
- Version in URL path — breaking changes require a new major version
- Include `request_id` in every response for debugging correlation

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 YAML block parsed (duplicate keys fail), openapi-spec-validator (OpenAPI 3.1); 1 JSON block parsed + response-envelope rules.
