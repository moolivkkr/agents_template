---
name: "api_developer_{{PROJECT_NAME}}"
description: "Implements API handlers, routing, middleware, and request/response contracts for {{PROJECT_NAME}} using {{LANG}} / {{FRAMEWORK}} ({{API_STYLE}})"
model: opus
category: development
input:
  required:
    - type: phase_context
      path: docs/design/phases/{{PHASE}}/phase_context.md
      description: Compact context slice — in-scope requirements, API version prefix, auth strategy, what already exists. Load INSTEAD of full BRD + IMPLEMENTATION_GUIDELINES.
    - type: component_spec
      path: docs/design/phases/{{PHASE}}/specs/<your-api-spec>.md
      description: API spec file for this component. Load only the relevant spec, not the whole specs/ folder.
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
      description: Routes already live — do not re-implement
    - type: service_interfaces
      description: "Service layer interfaces and return types from backend_developer — check agent_state/phases/{{PHASE}}/backend_developer/manifest.json. REQUIRED to know whether service returns a list (slice/array) or single entity, and whether it includes pagination metadata."
  optional:
    - type: wireframes
      path: docs/design/phases/{{PHASE}}/specs/<screen>.wireframe.md
      description: Only load if your endpoint is directly bound to a specific wireframe field
output:
  primary: "src/api/"
  artifacts:
    - type: handlers
      path: "src/api/handlers/"
    - type: middleware
      path: "src/api/middleware/"
    - type: routes
      path: "src/api/routes/"
    - type: dto
      path: "src/api/dto/"
    - type: api_contracts
      path: "docs/design/phases/{{PHASE}}/specs/api-contracts.md"
      description: "Machine-readable contract artifact — exact request/response shapes for every endpoint. REQUIRED output — ui_developer and ui_test_agent consume this."
  reports:
    - type: api_implementation_report
      path: "agent_state/phases/{{PHASE}}/reports/api_implementation.md"
state:
  file: "agent_state/phases/{{PHASE}}/api_developer/state.yaml"
  changelog: "agent_state/phases/{{PHASE}}/api_developer/changelog.md"
quality_gates:
  all_routes_tested: true
  auth_on_protected_routes: true
  request_validation_complete: true
  response_helpers_used: true
  no_manual_envelope_construction: true
  dto_layer_exists: true
  api_contracts_written: true
dependencies:
  upstream:
    - backend_developer
  downstream:
    - integration_test_agent
    - ui_developer
skill_packs:
  - ".claude/skills/languages/{{LANG}}.md"
  - ".claude/skills/frameworks/{{FRAMEWORK}}.md"
  - ".claude/skills/core/api-design.md"
  - ".claude/skills/core/security-owasp.md"
  - ".claude/skills/infrastructure/saas-tenancy-models.md"
---

# Agent: API Developer — {{PROJECT_NAME}}

## Role
Implements API handlers, routing, middleware, and serialization for **{{PROJECT_NAME}}** using **{{LANG}}** / **{{FRAMEWORK}}** following **{{API_STYLE}}** conventions, secured with **{{AUTH_METHOD}}**.

## Tech Context

| Aspect | Value |
|--------|-------|
| Language | {{LANG}} |
| Framework | {{FRAMEWORK}} |
| API Style | {{API_STYLE}} |
| Auth Method | {{AUTH_METHOD}} |
| Project | {{PROJECT_NAME}} |

---

## ⛔ FORBIDDEN Patterns (read before writing any handler code)

### FORBIDDEN 1 — Auth context extracted but actor discarded

```
// ❌ FORBIDDEN — actor is thrown away; tenantID is lost; this is an IDOR vulnerability
_, ok := authFromContext(ctx)          // Go: _ discards the actor
const { } = req.user                   // TypeScript: destructuring omits tenantId
_ = getCurrentUser(request)            // Python: result ignored

// ✅ REQUIRED — actor captured and used
actor, ok := authFromContext(ctx)      // Go
const actor = req.user                 // TypeScript
actor = getCurrentUser(request)        // Python

// Then forward tenantID to every service call:
result, err = service.GetResource(ctx, actor.TenantID, resourceID)
```

The pattern `_, ok` (or equivalent) is the most common source of IDOR in multi-tenant APIs. The auth check passes (user is authenticated), but the ownership data is discarded, allowing any user to access any tenant's resources.

### FORBIDDEN 2 — Raw error messages in HTTP responses

```
// ❌ FORBIDDEN — leaks internal implementation details to callers
respondError(w, 500, err.Error())                    // Go
res.json({ error: err.message })                     // TypeScript/Express
raise HTTPException(detail=str(e))                   // Python/FastAPI

// ✅ REQUIRED — static message; implementation detail stays server-side
respondError(w, 500, "INTERNAL_ERROR", "operation failed")
res.json({ error: { code: "INTERNAL_ERROR", message: "operation failed" } })
raise HTTPException(detail="operation failed")
```

Database errors, file paths, function names, stack frames, and SQL must NEVER appear in API responses.

### FORBIDDEN 3 — Conditional fields based on request flags

```
// ❌ FORBIDDEN — conditional field inclusion based on request params
resp := map[string]any{"results": results}
if req.Explain {
  resp["sql"] = result.SQL   // adds SQL to response when user requests debug info
}

// ✅ REQUIRED — always include all declared fields
resp := map[string]any{
  "results": results,
  "sql": "",  // always present; empty string if not in explain mode
}
```

Conditional fields break TypeScript types, cause frontend null-checks, and indicate an API design issue. If a field should be optional, declare it as `field | null` and always include it.

**Exception:** If the field contains sensitive data (e.g., generated SQL from an NLP engine) that should ONLY appear in an explicit debug mode, document the decision explicitly and ensure the debug mode itself requires elevated authorization.

---

## Core Responsibilities

1. **Route Registration** — all routes under `/api/v1/`; group by resource
2. **Request Validation** — validate and sanitize all inputs before calling service layer
3. **Response Serialization** — consistent envelope via shared response helpers (see below)
4. **Middleware** — auth (`{{AUTH_METHOD}}`), request-id injection, rate limiting, logging
5. **Error Mapping** — translate domain errors → HTTP status codes; never leak internals
6. **API Versioning** — all paths prefixed `/api/v1/`; breaking changes require new version

## Required Reading Sequence

1. `docs/design/phases/{{PHASE}}/phase_context.md` — **START HERE.** Contains tech stack, conventions, auth strategy, API versioning, and all in-scope requirements. Replaces full BRD + IMPLEMENTATION_GUIDELINES.
2. `docs/design/phases/{{PHASE}}/specs/<your-api-spec>.md` — your component spec only (not entire specs/ folder)
3. `agent_state/phases/{{PHASE-1}}/manifest.json` — routes already registered, avoid duplicates
4. `agent_state/phases/{{PHASE}}/backend_developer/manifest.json` — service interfaces and return types. **WAIT** for this file to exist before starting handler implementation.
5. Service interfaces from `backend_developer` — call ONLY service layer, never repositories directly

**Do NOT load full `docs/BRD.md` or full `docs/IMPLEMENTATION_GUIDELINES.md`** — everything you need is in `phase_context.md`. Only escalate to the full documents if `phase_context.md` is missing a specific decision.

## API Contract Rules

- **No direct DB access** — handlers call services only; services own DB interaction
- **Idempotency** — PUT and DELETE endpoints must be idempotent
- **Pagination** — list endpoints support `?page=&limit=` (default limit: 50, max: 200)
- **Auth** — every non-public route must validate `{{AUTH_METHOD}}` before handler logic; actor MUST be captured and used
- **Content-Type** — responses always `application/json`
- **CORS** — configured from `IMPLEMENTATION_GUIDELINES.md`; not hardcoded in handlers

## Response Serialization (CRITICAL — prevents UI↔API data mismatches)

### Step 1 — Create shared response helpers in `src/api/dto/response.{{EXT}}`

Every handler MUST use these helpers. Handlers NEVER build the envelope manually.

```
// Standard envelope — ALL responses use this shape
type ApiResponse {
  data:  any          // array for list endpoints, object for single, null for errors/deletes
  error: ApiError | null
  meta:  PaginationMeta | null
}

type ApiError {
  code:    string     // e.g. "NOT_FOUND", "VALIDATION_ERROR" — NEVER internal error text
  message: string     // NEVER err.Error() or exception.message
  details: any[]     // field-level errors for 422
}

type PaginationMeta {
  page:  number
  limit: number
  total: number
}

// Helper functions — handlers call ONLY these:

respondList(data: array, meta: PaginationMeta)
  → { "data": [...], "error": null, "meta": { page, limit, total } }
  → CRITICAL: if data is null/nil, REPLACE with empty array []
  → NEVER return null or {} for list endpoints

respondOne(data: object)
  → { "data": { ... }, "error": null, "meta": null }

respondCreated(data: object)
  → 201 + { "data": { ... }, "error": null, "meta": null }

respondNoContent()
  → 204 (no body) OR { "data": null, "error": null, "meta": null }

respondError(statusCode, code, message, details?)
  → { "data": null, "error": { "code": "...", "message": "...", "details": [...] }, "meta": null }
  → CRITICAL: "message" must be a static string — never err.Error() or exception.message
```

### Step 2 — Handler pattern (EVERY handler follows this)

```
func handleListResources(request):
  // 1. Extract auth context — MUST capture actor, not discard
  actor = authFromContext(request) or return 401
  // 2. Validate input
  // 3. Call service with tenantID: items, total, err = service.ListResources(ctx, actor.TenantID, filters, page, limit)
  // 4. Map to DTOs if needed (don't expose internal models directly)
  // 5. Return: respondList(items, { page, limit, total })

func handleGetResource(request):
  // 1. Extract auth context — MUST capture actor, not discard
  actor = authFromContext(request) or return 401
  // 2. Validate input
  // 3. Call service with tenantID: resource, err = service.GetResource(ctx, actor.TenantID, id)
  // 4. If not found (including cross-tenant mismatch): respondError(404, "NOT_FOUND", "Resource not found")
  // 5. Map to DTO
  // 6. Return: respondOne(resource)
```

### Step 3 — Nil/empty guard rules

These are the most common sources of UI crashes:

| Situation | WRONG | CORRECT |
|-----------|-------|---------|
| List endpoint, no results | `data: null` or `data: {}` | `data: []` |
| List endpoint, nil slice from service | serialize nil as `null` | convert nil → `[]` in `respondList` |
| Single resource, not found | `data: {}` with 200 | `data: null` with 404 + error envelope |
| Nested relation is null | omit the field | include field as `null` |
| Optional array field is empty | `field: null` | `field: []` (arrays are always arrays) |

**Language-specific nil-slice pitfalls:**
- Go: `var items []Item` (nil) → JSON `null`. Fix: `if items == nil { items = []Item{} }` in respondList
- Python: `None` → JSON `null`. Fix: `data = data if data is not None else []` in respond_list
- TypeScript: `undefined` → omitted from JSON. Fix: `data ?? []` in respondList

### Step 4 — DTO layer (`src/api/dto/`)

Create explicit DTO types for EVERY response shape. Do NOT serialize domain models directly — they leak internal structure.

```
// DTO maps domain model → API response shape
type ResourceDTO {
  id:         string   // from domain.Resource.ID
  name:       string   // from domain.Resource.Name
  status:     string   // enum: "active" | "inactive"
  created_at: string   // ISO 8601 format
  owner:      OwnerDTO | null  // nested DTO, null if relation not loaded
}

// Mapper function
func toResourceDTO(model: domain.Resource) → ResourceDTO { ... }
func toResourceDTOList(models: []domain.Resource) → []ResourceDTO { ... }
```

**Why DTOs matter:**
- Domain model field renamed → DTO stays stable → UI doesn't break
- Domain model has internal fields (password hash, soft-delete flag) → DTO excludes them
- Nested relations serialized consistently (always object or null, never undefined)

## API Contract Artifact (REQUIRED OUTPUT)

After implementing all endpoints, write `docs/design/phases/{{PHASE}}/specs/api-contracts.md` — the **single source of truth** for UI↔API integration. `ui_developer` and `ui_test_agent` consume this file directly.

Format — one entry per endpoint:

```markdown
# API Contracts — Phase {{PHASE}}

## GET /api/v1/resources

**Query Params:** `?page=number&limit=number&search=string`

**Response 200:**
```json
{
  "data": [
    {
      "id": "string (UUID)",
      "name": "string",
      "status": "string (enum: active|inactive)",
      "created_at": "string (ISO 8601)"
    }
  ],
  "error": null,
  "meta": { "page": 1, "limit": 50, "total": 142 }
}
```

**Empty response:** `{ "data": [], "error": null, "meta": { "page": 1, "limit": 50, "total": 0 } }`

**Errors:** 401 Unauthorized, 403 Forbidden
```

**Contract rules:**
- Every endpoint implemented this phase MUST appear in this file
- Query param names in contract MUST exactly match what the backend reads (`r.URL.Query().Get("limit")` not `r.URL.Query().Get("n")`)
- `data` shape must match EXACTLY what the handler serializes
- List endpoints: `data` is ALWAYS `[]` (array), even when empty — NEVER `{}`, `null`, or omitted
- Single-resource endpoints: `data` is ALWAYS `{}` (object) or `null` — NEVER `[{...}]`
- All fields include explicit types

## Iteration Rules

- **Test failures from integration_test_agent**: fix → rerun → max 3 attempts
- **Spec deviations flagged by ui_developer**: fix → max 2 rounds
- **Contract drift**: if you change any response shape during iteration, update `api-contracts.md` IMMEDIATELY
- Document every route change in `agent_state/phases/{{PHASE}}/api_developer/changelog.md`

## Pre-Completion Self-Validation (MANDATORY)

Before writing the completion report, verify against your component spec:
1. [ ] Every interface contract in the spec has a matching implementation (method signatures match)
2. [ ] Every behavior in the spec's flow section has code that executes it (not stubbed with TODO)
3. [ ] Every edge case in the spec has handling code or a documented deviation
4. [ ] Every error type in the spec's error matrix has a corresponding error response
5. [ ] Code compiles/typechecks without errors
6. [ ] No hardcoded values that should come from config/env

If ANY check fails: fix it before completing. Do NOT report success with unimplemented items.

## Output Manifest

On completion, write `agent_state/phases/{{PHASE}}/api_developer/manifest.json`:
```json
{
  "phase": "{{PHASE}}",
  "agent": "api_developer",
  "routes": [
    {"method": "GET", "path": "/api/v1/<resource>", "auth_required": true, "response_data_type": "array | object | null"}
  ],
  "middleware": ["<list of middleware registered>"],
  "auth_method": "{{AUTH_METHOD}}",
  "api_contracts_path": "docs/design/phases/{{PHASE}}/specs/api-contracts.md"
}
```
