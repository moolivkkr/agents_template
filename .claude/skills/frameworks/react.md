# React patterns for functional, accessible, maintainable UIs.

## Component Structure
```typescript
// Keep components focused: presentational vs container
// Presentational: receives data via props, no data fetching
// Container/Page: orchestrates data fetching + passes to presentational

interface UserCardProps {
    user: User
    onEdit: (id: string) => void
}

export function UserCard({ user, onEdit }: UserCardProps) {
    return (
        <article aria-label={`User: ${user.name}`}>
            <h2>{user.name}</h2>
            <button onClick={() => onEdit(user.id)}>Edit</button>
        </article>
    )
}
```

## Server State: React Query
```typescript
// Fetch
const { data: user, isLoading, error } = useQuery({
    queryKey: ["users", userId],
    queryFn: () => api.getUser(userId),
})

// Mutate
const { mutate: updateUser } = useMutation({
    mutationFn: api.updateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
})
```
- React Query for all server state — not `useEffect` + `useState`
- Always handle `isLoading`, `error`, and empty states

## Custom Hooks
```typescript
// Extract logic from components
function useUserForm(userId: string) {
    const { data } = useQuery(...)
    const { mutate } = useMutation(...)
    const [form, setForm] = useState(...)
    // return only what the component needs
    return { form, handleSubmit, isSubmitting }
}
```

## Forms
```typescript
// react-hook-form + zod
const schema = z.object({ email: z.string().email() })
const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(schema)
})
```

## Accessibility
- Semantic HTML: `<button>` not `<div onClick>`, `<nav>`, `<main>`, `<article>`
- Every interactive element: keyboard navigable, visible focus ring
- `aria-label` on icon-only buttons; `aria-live` on dynamic status regions
- Color: never convey meaning by color alone (WCAG 1.4.1)

## Accessibility Enforcement (MANDATORY)

### Required ESLint Plugin
Every React project MUST include `eslint-plugin-jsx-a11y` in its ESLint config:

```json
{
  "extends": ["plugin:jsx-a11y/recommended"],
  "rules": {
    "jsx-a11y/anchor-is-valid": "error",
    "jsx-a11y/click-events-have-key-events": "error",
    "jsx-a11y/no-static-element-interactions": "error",
    "jsx-a11y/img-redundant-alt": "error",
    "jsx-a11y/label-has-associated-control": "error",
    "jsx-a11y/heading-has-content": "error"
  }
}
```

### Mandatory Patterns
- Icon-only buttons MUST have `aria-label`: `<Button aria-label="Delete item"><Trash2 /></Button>`
- All form inputs MUST have associated `<Label>`: `<Label htmlFor="email">Email</Label><Input id="email" />`
- Heading hierarchy NEVER skips levels (h1 → h2 → h3, never h1 → h3)
- Images MUST have `alt` text (decorative images: `alt=""`)
- Modals/dialogs MUST trap focus and return focus on close
- Lists of interactive items MUST be keyboard navigable (arrow keys)

### Review Gate
`code_reviewer_I` MUST flag missing accessibility attributes as BLOCKING, not WARNING.

## Rules
- Functional components only — no class components
- `React.memo` only with measured performance problem — don't pre-optimize
- `useContext` for global UI state only (theme, locale); React Query for server state
- Code split routes with `React.lazy + Suspense`
- Never fetch data in `useEffect` — use React Query
