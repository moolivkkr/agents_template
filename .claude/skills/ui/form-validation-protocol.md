---
skill: form-validation-protocol
description: Protocol — derive Zod validation schemas from data-contracts.md request types so client validation matches the API contract
version: "1.0"
tags:
  - forms
  - zod
  - validation
  - data-contracts
  - ui
---

# Form Validation Protocol — Zod Schema Generation

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against Zod 4.6 and react-hook-form 7.89; the user schema also in a `next build` (Next.js 16.3.8) (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Rule: Zod schemas MUST derive from data-contracts.md

When a form submits to an API endpoint, the Zod validation schema MUST match the request type in data-contracts.md.

---

## Schema Derivation Example

### data-contracts.md says:
```typescript
type CreateUserRequest = {
  name: string;       // min: 2, max: 50
  email: string;      // valid email
  role: "admin" | "member" | "viewer";
}
```

### Generated Zod schema (in lib/validations/user.ts):
```typescript
import { z } from "zod";

export const createUserSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters").max(50, "Name must be at most 50 characters"),
  email: z.email("Enter a valid email address"),
  role: z.enum(["admin", "member", "viewer"], { error: "Select a role" }), // Zod 4 removed required_error
});

export type CreateUserInput = z.infer<typeof createUserSchema>;
```

### Update schema (partial — all fields optional):
```typescript
export const updateUserSchema = createUserSchema.partial();

export type UpdateUserInput = z.infer<typeof updateUserSchema>;
```

---

## Rules

### Field Name Matching
- Field names in Zod schema MUST match data-contracts.md exactly
- If contract says `first_name`, schema says `first_name` — not `firstName`
- Casing must be identical (snake_case, camelCase — whatever the contract uses)

### Constraint Matching
- Constraints (min, max, format, enum values) MUST match contract annotations
- If contract says `min: 2, max: 50` for name, Zod schema says `.min(2).max(50)`
- If contract says `valid email`, Zod schema says `z.email()` (Zod 4; `z.string().email()` is deprecated)
- If contract says enum values, Zod schema uses `z.enum([...])` with the exact values

### File Organization
- Zod schemas live in `lib/validations/` — one file per resource (e.g., `lib/validations/user.ts`)
- NEVER inline Zod schemas in component files
- Forms import from `lib/validations/`, not define their own schemas
- Export both the schema (`createUserSchema`) and the inferred type (`CreateUserInput`)

### Contract Sync
- If data-contracts.md changes, the corresponding Zod schema MUST be updated in the same commit
- Adding a required field to the contract = adding it to the Zod schema
- Removing a field from the contract = removing it from the Zod schema
- Changing constraints = updating Zod validators

---

## Server Error Mapping

When the API returns **400 `VALIDATION_FAILED`** with field errors, map them to react-hook-form using this
exact pattern:

```typescript
// The one error envelope (api/response-envelope.md):
// { error: { code: "VALIDATION_FAILED", message, details: [{ field, code, message }], request_id, retryable } }
// The HTTP client (api-integration-patterns.md) throws it as ApiError: error.code, error.details (FieldError[])

import type { FieldValues, Path, UseFormReturn } from "react-hook-form";
import type { ApiError } from "@/lib/api-client";

export function mapServerErrors<T extends FieldValues>(form: UseFormReturn<T>, error: ApiError): boolean {
  if (error.code !== "VALIDATION_FAILED") return false;
  const formValues = form.getValues();
  let mapped = false;
  for (const d of error.details) {
    // Only set an error on a field the form has: details[].field is the contract's (snake_case) name
    if (d.field in formValues) {
      form.setError(d.field as Path<T>, { type: "server", message: d.message });
      mapped = true;
    }
  }
  return mapped; // false → nothing matched: show error.message instead
}
```

### Usage in form submit handler:
```typescript
async function onSubmit(data: CreateUserInput) {
  try {
    // idempotencyKey: a useRef(crypto.randomUUID()), replaced after each success (api-integration-patterns.md)
    await api.users.create({ input: data, idempotencyKey: idempotencyKey.current });
    idempotencyKey.current = crypto.randomUUID();
    toast.success("User created");
    form.reset();
    onSuccess?.();
  } catch (error) {
    if (error instanceof ApiError && mapServerErrors(form, error)) return;
    toast.error(error instanceof ApiError ? error.message : "Failed to create user");
  }
}
```

---

## Common Validation Patterns

### String constraints
```typescript
z.string().min(1, "Required")           // required string
z.string().min(2).max(100)               // length range
z.email("Invalid email")                 // email format (Zod 4)
z.url("Invalid URL")                     // URL format (Zod 4)
z.string().regex(/^[A-Z]{2,3}$/, "Invalid code")  // pattern
z.string().trim()                         // auto-trim whitespace
```

### Number constraints
```typescript
z.number().min(0, "Must be positive")    // minimum
z.number().max(100, "Too large")          // maximum
z.number().int("Must be whole number")    // integer only
z.coerce.number()                         // coerce from string input
```

### Enum / union
```typescript
z.enum(["admin", "member", "viewer"])     // string enum
z.union([z.literal("active"), z.literal("inactive")])  // union
```

### Optional vs nullable
```typescript
z.string().optional()                     // field can be omitted
z.string().nullable()                     // field can be null
z.string().nullish()                      // omitted or null
```

### Conditional validation
```typescript
const schema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("email"), email: z.email() }),
  z.object({ type: z.literal("phone"), phone: z.string().min(10) }),
]);
```

### Cross-field validation
```typescript
const schema = z.object({
  password: z.string().min(8),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});
```

---

## Reconciliation Check

`spec_impl_reconciler` should verify:
1. Every form in the codebase has a Zod schema in `lib/validations/`
2. Every Zod schema matches the corresponding request type in data-contracts.md
3. No inline schemas exist in component files
4. Field names and constraints are in sync between contract and schema
5. Server error mapping is implemented for every form that submits to an API
