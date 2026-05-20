# Page Archetype: Form Page (Create / Edit)

## When to Use
Any screen with a data entry form: create user, edit profile, new invoice, settings form.

## Component Tree — Desktop (1280px)
```
div.space-y-6
├── PageHeader
│   ├── h1.text-3xl.font-bold.tracking-tight → "Create User" | "Edit User"
│   └── p.text-muted-foreground → "Fill in the details below."
│
├── Card
│   ├── CardHeader
│   │   ├── CardTitle → "User Information"
│   │   └── CardDescription → "Basic profile details."
│   └── CardContent
│       └── Form (react-hook-form + zodResolver)
│           └── form.space-y-6
│               ├── div.grid.gap-6.sm:grid-cols-2
│               │   ├── FormField(name) > FormItem > FormLabel + Input + FormMessage
│               │   └── FormField(email) > FormItem > FormLabel + Input(type=email) + FormMessage
│               ├── FormField(role) > FormItem > FormLabel + Select + FormMessage
│               ├── FormField(bio) > FormItem > FormLabel + Textarea + FormDescription + FormMessage
│               └── div.flex.gap-4.justify-end
│                   ├── Button(outline, type=button) → "Cancel" → navigate back
│                   └── Button(type=submit, disabled=isSubmitting)
│                       ├── Loader2.animate-spin (if submitting)
│                       └── "Create User" | "Save Changes"
```

## Component Tree — Mobile (375px)
- Grid: single column (remove sm:grid-cols-2)
- Buttons: full-width, stacked
- Cancel button: top-left back arrow instead of form button

## Data Flow
```tsx
// Create mode
const form = useForm<CreateUserInput>({
  resolver: zodResolver(createUserSchema),
  defaultValues: { name: "", email: "", role: undefined, bio: "" },
});

// Edit mode — pre-populate from query
const { data: user, isLoading } = useQuery(userQueries.detail(id));
const form = useForm<UpdateUserInput>({
  resolver: zodResolver(updateUserSchema),
  values: user?.data, // pre-populate when data arrives
});

// Submit
async function onSubmit(data: CreateUserInput) {
  try {
    await createUser.mutateAsync(data);
    toast.success("User created");
    form.reset();
    router.push("/users");
  } catch (error: any) {
    if (error.status === 422 && error.details) {
      mapServerErrors(form, error.details); // field-level errors
    } else {
      toast.error("Failed to save");
    }
  }
}
```

## 4 States

### Loading (Edit mode only — loading existing data)
```tsx
<Card>
  <CardContent className="space-y-6 pt-6">
    {Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="space-y-2">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-10 w-full" />
      </div>
    ))}
    <Skeleton className="h-10 w-24 ml-auto" />
  </CardContent>
</Card>
```

### Error (Edit mode — failed to load existing data)
- Show error + retry, not the form
- "Failed to load user data" + Retry button

### Validation Errors (inline)
- `<FormMessage />` below each invalid field (red text, auto aria-describedby)
- Submit button stays enabled — shows errors on attempt
- Server 422 errors mapped to fields via `form.setError()`

### Success
- `toast.success("User created")` or `toast.success("Changes saved")`
- `form.reset()` (create) or keep form (edit)
- Redirect to detail or list page

## Dirty Form Warning
```tsx
// Warn user if navigating away with unsaved changes
useEffect(() => {
  const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    if (form.formState.isDirty) e.preventDefault();
  };
  window.addEventListener("beforeunload", handleBeforeUnload);
  return () => window.removeEventListener("beforeunload", handleBeforeUnload);
}, [form.formState.isDirty]);
```
