# Next.js (App Router) patterns for full-stack React applications.

## App Router Directory Structure
```
app/
  (auth)/
    login/page.tsx
    register/page.tsx
  (dashboard)/
    layout.tsx         # shared dashboard shell
    page.tsx           # dashboard home
    users/
      page.tsx         # list
      [id]/page.tsx    # detail
  api/
    users/route.ts
  layout.tsx           # root layout
  globals.css
components/            # shared components (always client or server explicit)
lib/                   # utilities, API client
```

## Server vs Client Components
```typescript
// Server component (default) — data fetching, no interactivity
export default async function UsersPage() {
    const users = await db.getUsers()  // direct DB access OK
    return <UserList users={users} />
}

// Client component — interactivity, hooks, browser APIs
"use client"
export function UserList({ users }: { users: User[] }) {
    const [filter, setFilter] = useState("")
    ...
}
```
- Default to server components — add `"use client"` only when needed
- Never import server-only code (DB, secrets) into client components

## Data Fetching
```typescript
// Server component: direct async/await
const user = await fetch(`/api/users/${id}`, { next: { revalidate: 60 } })

// Client component: React Query
const { data } = useQuery({ queryKey: ["user", id], queryFn: () => api.getUser(id) })
```

## Server Actions
```typescript
"use server"
export async function createUser(formData: FormData) {
    const data = CreateUserSchema.parse(Object.fromEntries(formData))
    await db.users.create(data)
    revalidatePath("/users")
}
```
Use Server Actions for form mutations — no API route needed.

## Environment Variables
- `NEXT_PUBLIC_*` — exposed to browser (API URLs only, never secrets)
- All others — server-only

## Rules
- `next/image` for all images — auto optimization
- `next/link` for all internal navigation — prefetching
- Middleware for auth protection — not inside page components
- `loading.tsx` and `error.tsx` alongside every page route
