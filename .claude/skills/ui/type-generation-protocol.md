# Type Generation Protocol — data-contracts.md → types/api.ts

## Rule: All API response types MUST be auto-generated from data-contracts.md

During `/plan` Step 2b, after `data-contracts.md` is written, the planning agent MUST generate a `types/api.ts` file that exports TypeScript types for every response interface defined in the data contracts.

---

## Generation Process

### Step 1 — Read data-contracts.md
Parse every response interface in `docs/design/phases/{{PHASE}}/specs/data-contracts.md`.

### Step 2 — Generate types/api.ts
Create `src/types/api.ts` (or `types/api.ts` at project root depending on project structure) with:

```typescript
// AUTO-GENERATED from data-contracts.md — DO NOT EDIT MANUALLY
// Regenerate by running /plan Step 2b or updating data-contracts.md
// Phase: {{PHASE}}
// Generated: {{TIMESTAMP}}

// ─── Response Envelopes ─────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  error: ApiError | null;
  meta?: PaginationMeta;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// ─── Resource Types ─────────────────────────────────────────────────

// Every type below corresponds 1:1 to a TypeScript interface in data-contracts.md.
// Type names MUST match data-contracts.md exactly.

export interface UserResponse {
  id: string;
  name: string;
  email: string;
  role: "admin" | "member" | "viewer";
  created_at: string;
  updated_at: string;
}

// List response = ApiResponse<UserResponse[]>
export type ListUsersResponse = ApiResponse<UserResponse[]>;

// Single response = ApiResponse<UserResponse>
export type GetUserResponse = ApiResponse<UserResponse>;

// ─── Request Types ──────────────────────────────────────────────────

export interface CreateUserRequest {
  name: string;
  email: string;
  role: "admin" | "member" | "viewer";
}

export interface UpdateUserRequest {
  name?: string;
  email?: string;
  role?: "admin" | "member" | "viewer";
}

// ... (repeat for every resource in data-contracts.md)
```

### Step 3 — Validate completeness
After generation, verify:
- Every response interface in data-contracts.md has a corresponding exported type in types/api.ts
- Every request interface in data-contracts.md has a corresponding exported type in types/api.ts
- Type names match exactly (e.g., `UserResponse` in contract = `UserResponse` in types/api.ts)
- Field names, types, and optionality match exactly

---

## Usage Rules

### UI Components MUST import from types/api.ts
```typescript
// ✅ CORRECT — import from generated types
import { UserResponse, ListUsersResponse } from "@/types/api";

function UserList() {
  const { data } = useQuery<ListUsersResponse>(...);
  return data?.data.map((user: UserResponse) => <UserCard user={user} />);
}

// ❌ BANNED — never define response types inline
function UserList() {
  interface User { id: string; name: string; } // INLINE TYPE — BLOCKED
  const { data } = useQuery<{ data: User[] }>(...);
}
```

### Type Validation at Compile Time
If a component references a field that doesn't exist in the generated types, the TypeScript compiler catches it:
```typescript
import { UserResponse } from "@/types/api";

// TypeScript error: Property 'avatar' does not exist on type 'UserResponse'
const avatar = user.avatar; // ← Compile error if 'avatar' not in data-contracts.md
```

### NEVER use `any` or `unknown` for API data
```typescript
// ❌ BANNED
const data: any = response.data;
const users = response.data as unknown[];

// ✅ REQUIRED
const data: UserResponse[] = response.data;
```

### Missing Type = Uncontracted Endpoint
If a component needs a type that doesn't exist in `types/api.ts`:
1. The endpoint is NOT in data-contracts.md
2. STOP — do not invent the type
3. Report: `⛔ Blocked: type <TypeName> not found in types/api.ts — endpoint not contracted in data-contracts.md`
4. Route back to spec_writer to add the endpoint to data-contracts.md
5. Regenerate types/api.ts

---

## Regeneration Triggers

types/api.ts MUST be regenerated when:
- data-contracts.md is updated with new endpoints
- data-contracts.md fields are renamed or retyped
- A new phase adds endpoints to data-contracts.md

The regeneration is idempotent — re-running produces the same output for the same input.

---

## Agent References

- `ux_designer` — references types/api.ts field names in wireframe API bindings
- `ui_developer` — imports all types from types/api.ts (see Type Safety Protocol in agent template)
- `ui_test_agent` — mock data shapes must match types/api.ts interfaces
- `design_quality_reviewer` — validates wireframe field references against types/api.ts
- `spec_impl_reconciler` — verifies types/api.ts is in sync with data-contracts.md
