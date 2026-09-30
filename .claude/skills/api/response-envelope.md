# API response envelope — the one shape

**This is the only envelope.** Every HTTP API the framework generates uses it, and every agent writes
code, mocks, contract tests and generated types against it:
- `api_developer` and `backend_developer` (server)
- `ui_developer` and `mobile_developer` (clients)
- `integration_test_agent`, `ui_test_agent`, `mobile_test_agent` and `acceptance_test_agent` (tests)
- `spec_writer` (the `data-contracts.md` it publishes)

If any other file shows a different shape, this one wins, and the other file is a bug to fix.

`docs/design/phases/N/specs/data-contracts.md` (from `spec_writer`) defines the **payload types**
(`User`, `Order`, …). This file defines the **wrapper** around them. Before any UI or mobile work
starts, `api_developer` publishes the as-built contract (`specs/api-contracts.md`, plus OpenAPI where
the stack supports it).

## Success — single resource

`200` / `201`:

```json
{
  "data": { "id": "ord_01H…", "status": "open", "total_cents": 1299 },
  "meta": { "request_id": "b7e1c2…" }
}
```

## Success — collection (cursor pagination; never offset)

`200`:

```json
{
  "data": [ { "id": "ord_01H…" }, { "id": "ord_01J…" } ],
  "meta": {
    "request_id": "b7e1c2…",
    "pagination": { "next_cursor": "eyJpZCI6Im9yZF8wMUoifQ", "has_more": true, "limit": 20 }
  }
}
```

- `data` is **always an array**: `[]` when empty, never `null`.
- Request the next page with `?cursor=<next_cursor>&limit=<n>`. Cursors are opaque, from the server's
  stable sort key.
- `next_cursor` is `null` when `has_more` is `false`.
- `total_count` is optional. Include it only when it's cheap and the UI shows it.

## Error

The HTTP status carries the class; the body carries the detail:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Some fields are invalid.",
    "details": [ { "field": "email", "code": "invalid_format", "message": "Enter a valid email address." } ],
    "request_id": "b7e1c2…",
    "retryable": false
  }
}
```

| Status | `code` (examples) | When |
|---|---|---|
| 400 | `VALIDATION_FAILED`, `MALFORMED_REQUEST` | input fails schema/validation; `details[]` lists fields |
| 401 | `UNAUTHENTICATED` | missing/invalid/expired credentials |
| 403 | `FORBIDDEN` | authenticated but not allowed (function-level) |
| 404 | `NOT_FOUND` | doesn't exist **or** belongs to another tenant/owner (never 403 for foreign objects — don't confirm they exist) |
| 409 | `CONFLICT`, `IDEMPOTENCY_KEY_REUSED` | state conflict; idempotency key replayed with a different body |
| 422 | `BUSINESS_RULE_VIOLATION` | valid shape, rejected by a domain rule |
| 429 | `RATE_LIMITED` | with `Retry-After`; `retryable: true` |
| 500 | `INTERNAL` | generic message only; the cause goes to logs under `request_id` |
| 503 | `UNAVAILABLE` | dependency down; `retryable: true` |

## Rules

- **Success and error are exclusive.** A success body has no `error` key, and an error body has no
  `data` key. Clients branch on the HTTP status (or `"error" in body`), never on `error === null`.
- **Error bodies never carry stack traces, SQL, file paths, upstream messages or "technical detail".**
  The `request_id` links the client-visible error to the server log line that has them.
- **`code` values are UPPER_SNAKE, stable and documented** in `data-contracts.md`. `message` is safe
  to show a user. Field-level `details[].code` values are lower_snake.
- **Timestamps are RFC 3339 UTC strings. IDs are strings** (even if numeric in the DB), and money is
  in integer minor units.
- **Every response sets `X-Request-Id`,** which equals `meta.request_id` / `error.request_id`.
- **Writes (POST) accept an `Idempotency-Key` header** (see `core/api-excellence.md` §Idempotency).
- **Requests are wrapped too.** Request bodies are the resource payload, not `{"data": …}`: the
  envelope is for responses.

## Types

**TypeScript (clients, mocks):**

```ts
export type ApiSuccess<T> = { data: T; meta: { request_id: string; pagination?: Pagination } };
export type ApiErrorBody = { error: { code: string; message: string; details?: FieldError[]; request_id: string; retryable: boolean } };
export type Pagination = { next_cursor: string | null; has_more: boolean; limit: number; total_count?: number };
export type FieldError = { field: string; code: string; message: string };
```

**Go (server):**

```go
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
type ErrorBody struct {
	Error APIError `json:"error"`
}
type APIError struct {
	Code      string       `json:"code"`
	Message   string       `json:"message"`
	Details   []FieldError `json:"details,omitempty"`
	RequestID string       `json:"request_id"`
	Retryable bool         `json:"retryable"`
}
```

## What tests assert

These are the contract tests, owned by `integration_test_agent`, with shapes from `api-contracts.md`:

- For every endpoint, a success response matches the envelope exactly: the right keys, `data` of the
  documented type, and no extra top-level keys.
- For every list endpoint:
  - `data` is an array (including when empty);
  - `meta.pagination` is present;
  - following `next_cursor` returns the next page with no duplicates and no gaps under concurrent
    inserts.
- For every documented error code, the status and `error.code` match and `request_id` is present. The
  body contains no stack trace or SQL (assert the absence of `"stack"`, `"SELECT "`, file paths).
- **UI and mobile mocks** (MSW handlers, fixtures) are built from these types, so a mock that violates
  the envelope fails to type-check.
