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

## Rules
- Functional components only — no class components
- `React.memo` only with measured performance problem — don't pre-optimize
- `useContext` for global UI state only (theme, locale); React Query for server state
- Code split routes with `React.lazy + Suspense`
- Never fetch data in `useEffect` — use React Query
