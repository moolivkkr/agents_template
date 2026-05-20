# Form Patterns — React Hook Form + Zod + shadcn/ui

## Canonical Form Setup

```tsx
"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
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
  email: z.string().email("Enter a valid email address"),
  role: z.enum(["admin", "member", "viewer"], {
    required_error: "Select a role",
  }),
});
type CreateUserInput = z.infer<typeof createUserSchema>;

// 2. Form component
export function CreateUserForm({ onSuccess }: { onSuccess?: () => void }) {
  const form = useForm<CreateUserInput>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { name: "", email: "", role: undefined },
  });

  async function onSubmit(data: CreateUserInput) {
    try {
      await api.users.create(data);
      toast.success("User created");
      form.reset();
      onSuccess?.();
    } catch (error: any) {
      // error.details is already unwrapped from the backend envelope
      // by the HTTP client (see api-integration-patterns.md).
      // Backend sends: {"error": {"code": "VALIDATION_ERROR", "details": {"fields": {...}}}}
      // HTTP client normalizes to: error.status, error.code, error.details
      if (error.status === 422 && error.details?.fields) {
        mapServerErrors(form, error.details.fields);
      } else if (error.status === 422 && error.details?.field) {
        // Single field validation error
        form.setError(error.details.field as any, {
          type: "server",
          message: error.details.reason ?? error.message,
        });
      } else {
        toast.error(error.message ?? "Failed to create user");
      }
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

## Server Error Mapping (422 → Field Errors)

The backend error envelope is `{"error": {"code": "VALIDATION_ERROR", "details": {"fields": {...}}}}`.
The HTTP client in `api-integration-patterns.md` unwraps the outer `.error` layer, so by the time
errors reach these functions, `error.details` already contains the inner details object.

```tsx
import { UseFormReturn } from "react-hook-form";

// Maps multi-field validation errors from backend to react-hook-form field errors.
// Backend sends: details.fields = { "email": "invalid format", "name": "required" }
function mapServerErrors(form: UseFormReturn<any>, fieldErrors: Record<string, string>) {
  Object.entries(fieldErrors).forEach(([field, message]) => {
    form.setError(field as any, { type: "server", message });
  });
}
```

## CRUD Form Patterns

### Edit Form (pre-populated)
```tsx
function EditUserForm({ userId }: { userId: string }) {
  const { data: user, isLoading } = useQuery(userQueries.detail(userId));
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
