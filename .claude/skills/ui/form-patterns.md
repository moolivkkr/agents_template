---
skill: form-patterns
description: Form patterns — React Hook Form + Zod + shadcn/ui, validation, field arrays, submission states, and accessible error display
version: "1.0"
tags:
  - forms
  - react-hook-form
  - zod
  - validation
  - ui
---

# Form Patterns — React Hook Form + Zod + shadcn/ui

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, react-hook-form 7.89, @hookform/resolvers 5.9, Zod 4.6 and shadcn/ui Form stubs; type-checked only (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Canonical Form Setup

```tsx
"use client";
import { useRef } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { mapServerErrors } from "@/lib/form-errors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form, FormControl, FormDescription, FormField,
  FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

// 1. Schema — shared between client and server
const createUserSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters").max(50),
  email: z.email("Enter a valid email address"),               // Zod 4: z.email(), not z.string().email()
  role: z.enum(["admin", "member", "viewer"], { error: "Select a role" }), // Zod 4: `error`, not required_error
});
type CreateUserInput = z.infer<typeof createUserSchema>;

// 2. Form component
export function CreateUserForm({ onSuccess }: { onSuccess?: () => void }) {
  const form = useForm<CreateUserInput>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { name: "", email: "", role: undefined },
  });
  // One Idempotency-Key per user action: reused if this submit is retried, replaced after a success
  const idempotencyKey = useRef(crypto.randomUUID());

  async function onSubmit(data: CreateUserInput) {
    try {
      await api.users.create({ input: data, idempotencyKey: idempotencyKey.current });
      idempotencyKey.current = crypto.randomUUID();
      toast.success("User created");
      form.reset();
      onSuccess?.();
    } catch (error) {
      // The HTTP client (api-integration-patterns.md) throws the error envelope as ApiError. A 400
      // VALIDATION_FAILED carries error.details: [{ field, code, message }] (api/response-envelope.md).
      if (error instanceof ApiError && error.code === "VALIDATION_FAILED" && mapServerErrors(form, error.details)) return;
      toast.error(error instanceof ApiError ? error.message : "Failed to create user");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField control={form.control} name="name" render={({ field }) => (
          <FormItem>
            <FormLabel>Name</FormLabel>
            <FormControl><Input placeholder="Jane Doe" {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />

        <FormField control={form.control} name="email" render={({ field }) => (
          <FormItem>
            <FormLabel>Email</FormLabel>
            <FormControl><Input type="email" placeholder="jane@company.com" {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />

        <FormField control={form.control} name="role" render={({ field }) => (
          <FormItem>
            <FormLabel>Role</FormLabel>
            <Select onValueChange={field.onChange} defaultValue={field.value}>
              <FormControl>
                <SelectTrigger><SelectValue placeholder="Select role" /></SelectTrigger>
              </FormControl>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="member">Member</SelectItem>
                <SelectItem value="viewer">Viewer</SelectItem>
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )} />

        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="mr-2 size-4 animate-spin" />}
          Create User
        </Button>
      </form>
    </Form>
  );
}
```

## Server Error Mapping (400 `VALIDATION_FAILED` → Field Errors)

The error envelope is the one in `api/response-envelope.md`: a 400 with
`{"error": {"code": "VALIDATION_FAILED", "message": "…", "details": [{"field": "email", "code": "invalid_format", "message": "…"}], "request_id": "…", "retryable": false}}`.
The HTTP client in `api-integration-patterns.md` throws it as `ApiError`, so `error.details` is that
`FieldError[]`. `details[].field` is the contract's wire name (snake_case), the same name the form field uses
(`form-validation-protocol.md` §Field Name Matching).

```tsx
// lib/form-errors.ts
import type { FieldValues, Path, UseFormReturn } from "react-hook-form";
import type { FieldError } from "@/types/api";

// Puts each details[] entry on its form field. Returns false when no field matched, so the caller shows
// error.message in a toast instead.
export function mapServerErrors<T extends FieldValues>(form: UseFormReturn<T>, details: FieldError[]): boolean {
  const values = form.getValues();
  let mapped = false;
  for (const d of details) {
    if (d.field in values) {
      form.setError(d.field as Path<T>, { type: "server", message: d.message });
      mapped = true;
    }
  }
  return mapped;
}
```

## CRUD Form Patterns

### Edit Form (pre-populated)
```tsx
function EditUserForm({ userId }: { userId: string }) {
  // The query caches the envelope { data, meta }; `select` hands the form the user itself
  const { data: user, isLoading } = useQuery({ ...userQueries.detail(userId), select: (res) => res.data });
  const form = useForm<UpdateUserInput>({
    resolver: zodResolver(updateUserSchema),
    values: user, // Pre-populate when data arrives
  });
  if (isLoading) return <FormSkeleton fields={3} />;
  // ... same form structure as create
}
```

### Form States Checklist
- **Submitting:** Button disabled + spinner icon + text changes ("Save" → "Saving...")
- **Success:** `toast.success()` + `form.reset()` + close dialog or redirect
- **Server error:** `toast.error()` + form stays open with user input preserved
- **Validation error:** Red text below field via `<FormMessage />`
- **Dirty tracking:** Warn on navigate away if `form.formState.isDirty`

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Validate only on submit | Validate on blur (`mode: "onBlur"` or default) |
| Show generic "Error" | Show specific field-level message |
| Disable submit until all valid | Allow submit, show validation errors on attempt |
| Clear form on error | Preserve user input, highlight errors |
| Build custom form field wrappers | Use shadcn `FormField/FormItem/FormLabel/FormControl/FormMessage` |
| Inline Zod schema in component | Extract to `lib/validations/` and share with server |
