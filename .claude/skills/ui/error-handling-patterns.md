# Error Handling Patterns — UI Reference

## Error Type → UI Pattern Lookup Table

| HTTP Status | Error Type | UI Pattern | User Message |
|---|---|---|---|
| — | Network timeout | Full-screen retry | "Taking longer than expected. Check your connection." + Retry button |
| — | Network error (no response) | Full-screen retry | "Unable to connect. Check your internet." + Retry button |
| 400 | Bad Request | Toast error | "Invalid request. Please check your input." |
| 401 | Unauthorized | Silent redirect | Redirect to `/login` — no error shown |
| 403 | Forbidden | Inline message | "You don't have permission to access this." |
| 404 | Not Found | Custom page | "This page doesn't exist." + navigation links |
| 409 | Conflict | Toast + refresh | "This was modified by someone else." + Refresh button |
| 422 | Validation | Field-level errors | Map each field error to its form field via `setError()` |
| 429 | Rate Limited | Toast with timer | "Too many requests. Try again in X seconds." |
| 500 | Server Error | Toast + retry | "Something went wrong." + Retry action |

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
// In query hooks — handle isError
function UserList() {
  const { data, isLoading, isError, error, refetch } = useQuery(userQueries.list());

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
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
  // ... loading and data states
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

## Server Validation Error Mapping (422 → Form Fields)

```tsx
// API returns: { error: "Validation failed", details: { email: "already taken", name: "too short" } }

import { UseFormReturn } from "react-hook-form";

function mapServerErrors(form: UseFormReturn<any>, serverErrors: Record<string, string>) {
  Object.entries(serverErrors).forEach(([field, message]) => {
    form.setError(field as any, { type: "server", message });
  });
}

// Usage in form submit handler:
async function onSubmit(data: FormData) {
  try {
    await api.users.create(data);
    toast.success("Created!");
    form.reset();
  } catch (error: any) {
    if (error.status === 422 && error.details) {
      mapServerErrors(form, error.details);
    } else {
      toast.error("Failed to save");
    }
  }
}
```

---

## Optimistic Update with Rollback

```tsx
const deleteUser = useMutation({
  mutationFn: (id: string) => api.users.delete(id),
  onMutate: async (id) => {
    await queryClient.cancelQueries({ queryKey: ["users"] });
    const previous = queryClient.getQueryData<User[]>(["users"]);

    // Optimistically remove
    queryClient.setQueryData<User[]>(["users"], (old) =>
      old?.filter((u) => u.id !== id)
    );

    return { previous };
  },
  onError: (_err, _id, context) => {
    // Rollback on failure
    queryClient.setQueryData(["users"], context?.previous);
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
  cancel: { label: "Cancel" },
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
