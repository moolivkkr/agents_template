---
skill: error-handling-patterns
description: UI error handling — HTTP-status-to-UI mapping, error boundaries, toast/inline patterns, retry, and user-facing messages
version: "1.0"
tags:
  - errors
  - error-boundary
  - ux
  - resilience
  - ui
---

# Error Handling Patterns — UI Reference

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, TanStack Query 5.104, react-hook-form 7.89 and sonner 2.0; `error.tsx` also in a `next build` (Next.js 16.3.8) (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Error Type → UI Pattern Lookup Table

| HTTP Status | Error Type | UI Pattern | User Message |
|---|---|---|---|
| — | Network timeout | Full-screen retry | "Taking longer than expected. Check your connection." + Retry button |
| — | Network error (no response) | Full-screen retry | "Unable to connect. Check your internet." + Retry button |
| 400 | `VALIDATION_FAILED` | Field-level errors | Map each `error.details[]` entry to its form field via `setError()`; toast only if no field matched |
| 400 | `MALFORMED_REQUEST` | Toast error | "Invalid request. Please check your input." |
| 401 | `UNAUTHENTICATED` | Silent redirect | Redirect to `/login` — no error shown |
| 403 | `FORBIDDEN` | Inline message | "You don't have permission to access this." |
| 404 | `NOT_FOUND` | Custom page | "This page doesn't exist." + navigation links (also shown for another tenant's/user's object) |
| 409 | `CONFLICT` | Toast + refresh | "This was modified by someone else." + Refresh button |
| 422 | `BUSINESS_RULE_VIOLATION` | Inline/toast with `error.message` | The server's user-safe message (e.g. "Orders can't be cancelled after shipping.") |
| 429 | `RATE_LIMITED` | Toast with timer | "Too many requests. Try again in X seconds." (from `Retry-After`) |
| 500 | `INTERNAL` | Toast + retry | "Something went wrong." + Retry action + "Reference: {request_id}" |
| 503 | `UNAVAILABLE` | Toast + retry | "The service is busy. Try again shortly." (`retryable: true`) |

The body is always the envelope from `~/.claude/skills/api/response-envelope.md`:
`{ "error": { code, message, details[], request_id, retryable } }`. The client (`ApiError` in
`ui/api-integration-patterns.md`) exposes those fields. Show `request_id` on unexpected errors so support
can find the server log line. Never render a server message as HTML.

---

## Error Boundary Pattern (React)

```tsx
// app/(dashboard)/error.tsx — route-level error boundary
"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <div className="rounded-full bg-destructive/10 p-4">
        <AlertCircle className="size-8 text-destructive" />
      </div>
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>
      <Button onClick={reset} variant="outline">Try again</Button>
    </div>
  );
}
```

Create `error.tsx` at EVERY route segment that fetches data.

---

## TanStack Query Error Handling

```tsx
// In query hooks — handle isError (lists are cursor-paginated: useInfiniteQuery, api-integration-patterns.md)
function UserList() {
  const { data, isLoading, isError, error, refetch } = useInfiniteQuery(userQueries.list());

  if (isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-12">
        <AlertCircle className="size-8 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "Failed to load users"}
        </p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-2 size-4" /> Retry
        </Button>
      </div>
    );
  }
  // ... loading and data states (rows: data?.pages.flatMap((p) => p.data))
}
```

```tsx
// In mutations — toast on error
const createUser = useMutation({
  mutationFn: api.users.create,
  onSuccess: () => {
    toast.success("User created");
    queryClient.invalidateQueries({ queryKey: ["users"] });
  },
  onError: (error) => {
    toast.error("Failed to create user", {
      description: error instanceof Error ? error.message : "Please try again",
    });
  },
});
```

---

## Server Validation Error Mapping (400 `VALIDATION_FAILED` → Form Fields)

```tsx
// API returns 400:
// { "error": { "code": "VALIDATION_FAILED", "message": "Some fields are invalid.",
//              "details": [ { "field": "email", "code": "already_taken", "message": "That email is already registered." } ],
//              "request_id": "b7e1c2…", "retryable": false } }

import type { FieldValues, Path, UseFormReturn } from "react-hook-form";
import type { FieldError } from "@/types/api";
import { ApiError } from "@/lib/api-client";

function mapServerErrors<T extends FieldValues>(form: UseFormReturn<T>, details: FieldError[]): boolean {
  let mapped = false;
  for (const d of details) {
    if (d.field in form.getValues()) {
      form.setError(d.field as Path<T>, { type: "server", message: d.message });
      mapped = true;
    }
  }
  return mapped; // false → no field matched; show a toast instead
}

// Usage in form submit handler. One Idempotency-Key per user action: a retried submit (after a timeout or an
// error) reuses it; a successful create replaces it, so the NEXT user created from this form gets a new key.
const idempotencyKey = useRef(crypto.randomUUID());
async function onSubmit(input: CreateUserRequest) {
  try {
    await createUser.mutateAsync({ input, idempotencyKey: idempotencyKey.current });
    idempotencyKey.current = crypto.randomUUID();
    toast.success("Created!");
    form.reset();
  } catch (error) {
    if (error instanceof ApiError && error.code === "VALIDATION_FAILED" && mapServerErrors(form, error.details)) return;
    toast.error(error instanceof ApiError ? error.message : "Failed to save");
  }
}
```

---

## Optimistic Update with Rollback

```tsx
// Cached lists are infinite queries under ["users", "list", filters]: pages of { data: User[], meta }
type UserPages = InfiniteData<ApiSuccess<User[]>>;

const deleteUser = useMutation({
  mutationFn: (id: string) => api.users.delete(id),
  onMutate: async (id) => {
    await queryClient.cancelQueries({ queryKey: ["users", "list"] });
    const previous = queryClient.getQueriesData<UserPages>({ queryKey: ["users", "list"] });

    // Optimistically remove it from every loaded page of every cached list
    queryClient.setQueriesData<UserPages>({ queryKey: ["users", "list"] }, (old) =>
      old && { ...old, pages: old.pages.map((p) => ({ ...p, data: p.data.filter((u) => u.id !== id) })) }
    );

    return { previous };
  },
  onError: (_err, _id, context) => {
    // Rollback on failure
    context?.previous.forEach(([key, data]) => queryClient.setQueryData(key, data));
    toast.error("Failed to delete user");
  },
  onSuccess: () => toast.success("User deleted"),
  onSettled: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
});
```

---

## Toast Patterns (Sonner)

```tsx
import { toast } from "sonner";

// Success — after successful mutation
toast.success("Changes saved");

// Error — after failed mutation
toast.error("Failed to save", {
  description: "Check your connection and try again.",
  action: { label: "Retry", onClick: () => retry() },
});

// Promise — wrap async operations
toast.promise(saveData(payload), {
  loading: "Saving...",
  success: "Saved successfully",
  error: "Could not save",
});

// Destructive confirmation toast
toast("Delete this item?", {
  action: { label: "Delete", onClick: () => deleteItem(id) },
  cancel: { label: "Cancel", onClick: () => {} },   // sonner 2 requires onClick on cancel too
});
```

### When to Use Toast vs Inline Error

| Scenario | Pattern |
|----------|---------|
| Form field validation | Inline — `<FormMessage />` below the field |
| Form submission failure | Toast error + keep form open |
| Mutation success | Toast success |
| Mutation failure | Toast error with retry action |
| Route-level data load error | Inline error component with retry |
| Auth failure (401) | Silent redirect to /login |
| Permission denied (403) | Inline message in content area |
