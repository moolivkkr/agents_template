# Edge Case Taxonomy — Systematic Framework for spec_writer

## How to Use

For each spec, check EVERY applicable category below and generate at least 1 edge case per category. The spec must document expected behavior for each edge case.

## By Data Type

| Input Type | Edge Cases to Check |
|---|---|
| **String** | Empty `""`, single char, max length, Unicode/emoji, HTML/script tags, SQL injection chars, leading/trailing whitespace |
| **Number** | Zero, negative, max int, decimal, NaN, Infinity |
| **Email** | Invalid format, valid but non-existent, disposable email domains, very long local part |
| **Date** | Past dates, far future, timezone boundaries, DST transitions, leap year (Feb 29), epoch (1970-01-01) |
| **UUID/ID** | Non-existent ID, malformed UUID, ID from different tenant, empty string, `null` |
| **Array/List** | Empty `[]`, single item, max items, duplicates, null items within array |
| **File** | 0 bytes, max size, wrong MIME type, malicious filename, special chars in name |
| **Boolean** | `true`, `false`, `null`, `undefined`, string `"true"` |

## By Operation Type

### List / Search Endpoints
```
□ Empty result set (no items match)
□ Exactly 1 result
□ Exactly at page size boundary (e.g., 20 items when page size = 20)
□ More than max page size
□ Concurrent deletion (item deleted while paginating)
□ Filter + sort + pagination combined
□ Search with special characters (quotes, wildcards, SQL chars)
□ Search returning partial matches vs exact matches
```

### Single Resource (GET by ID)
```
□ Resource exists → 200 + data
□ Resource doesn't exist → 404
□ Resource exists but belongs to different tenant → 404 (not 403)
□ Resource is soft-deleted → 404 or 410
□ ID is malformed → 400
□ Resource has null optional relations → null fields, not crash
```

### Create (POST)
```
□ All required fields present → 201
□ Missing required field → 422 with field error
□ Duplicate unique field (e.g., email already exists) → 409
□ Invalid field format → 422 with specific message
□ Exceeds field max length → 422
□ Empty request body → 400
□ Extra unknown fields → ignored (not error)
□ Concurrent creates with same unique key → one succeeds, one 409
```

### Update (PATCH/PUT)
```
□ Valid partial update → 200
□ Update non-existent resource → 404
□ Update resource from different tenant → 404
□ No-op update (same values) → 200 (idempotent)
□ Update with invalid field → 422
□ Concurrent updates → last-write-wins or conflict detection
□ Update read-only field → 422 or ignored
```

### Delete
```
□ Delete existing resource → 204
□ Delete non-existent resource → 404 or 204 (idempotent)
□ Delete resource from different tenant → 404
□ Delete resource with dependencies → 409 or cascade
□ Double-delete (already deleted) → 404 or 204
□ Soft delete → resource no longer appears in list, GET returns 404
```

## By System Concern

### Authentication
```
□ No token → 401
□ Expired token → 401
□ Malformed token → 401
□ Valid token but user deactivated → 401 or 403
□ Token from different environment → 401
□ Concurrent sessions (same user, multiple devices)
```

### Authorization
```
□ User accesses own resource → 200
□ User accesses other user's resource → 404 (not 403)
□ Admin accesses any resource → 200
□ Role changed mid-session → next request reflects new role
□ Downgraded permissions → previously accessible resources now 404
```

### Concurrency
```
□ Two users edit same resource simultaneously
□ Resource deleted while another user is editing
□ Bulk operation partially fails (3 of 5 items succeed)
□ Race condition: create + immediate read (eventually consistent)
```

### Rate Limiting
```
□ Under limit → normal response
□ At limit → 429 with Retry-After header
□ Burst above limit → queued or rejected
□ Different limits per endpoint (auth stricter than read)
```

## Minimum Edge Cases Per Spec Type

| Spec Type | Minimum Edge Cases |
|---|---|
| List/Search endpoint | 8 (empty, pagination, sort, filter, concurrent, boundary) |
| CRUD resource | 12 (create: 4, read: 3, update: 3, delete: 2) |
| Authentication flow | 6 (no token, expired, malformed, deactivated, concurrent, refresh) |
| Form/Wizard | 8 (validation per field, server errors, dirty state, multi-step) |
| Bulk operation | 5 (empty set, partial failure, all fail, max items, duplicates) |

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Only happy path | Misses 80% of bugs | Check every category above |
| "Invalid input" as one edge case | Too vague — which field? what input? | One edge case per field per validation rule |
| Edge cases without expected behavior | Developer guesses | "Input: empty string → Expected: 422 with 'Name is required'" |
| Edge cases that can't happen | Wastes dev time | Only include edge cases that are reachable in production |
