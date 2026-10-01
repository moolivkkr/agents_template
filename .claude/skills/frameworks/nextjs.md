# Next.js (App Router) patterns for full-stack React applications.

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess), then `next build` (Next.js 16.3.8, Turbopack) of an App Router app holding all three blocks (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

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
```tsx
// app/users/page.tsx — Server Component (the default): data fetching, no interactivity
import { requireSession } from "@/lib/auth"   // your session check
import { db } from "@/lib/db"                 // server-only module: direct DB access is fine here
import { UserList } from "./user-list"

export default async function UsersPage() {
    const session = await requireSession()
    const users = await db.getUsers({ tenantId: session.tenantId })
    // Everything passed to a Client Component is serialized into the page: pass only what it renders
    return <UserList users={users.map(({ id, name }) => ({ id, name }))} />
}

// app/users/user-list.tsx — Client Component: interactivity, hooks, browser APIs
"use client"                                  // the file's first statement (comments may precede it)
import { useState } from "react"

export function UserList({ users }: { users: { id: string; name: string }[] }) {
    const [filter, setFilter] = useState("")
    const shown = users.filter((u) => u.name.toLowerCase().includes(filter.toLowerCase()))
    return (
        <>
            <input aria-label="Filter users" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <ul>{shown.map((u) => <li key={u.id}>{u.name}</li>)}</ul>
        </>
    )
}
```
- Default to server components — add `"use client"` only when needed, as the first statement of its own file
- Never import server-only code (DB, secrets) into client components; mark such modules with `import "server-only"`

## Data Fetching
```typescript
// Server Component: direct async/await. A server-side fetch has no page origin: call the API by an absolute
// (internal) URL. `revalidate` puts the response in a cache shared by every visitor — only for data that is
// the same for everyone (here, a public product); per-user data is fetched with the session cookie, no-store.
const res = await fetch(`${process.env.API_INTERNAL_URL}/api/v1/products/${encodeURIComponent(id)}`, { next: { revalidate: 60 } })
if (!res.ok) throw new Error(`GET /api/v1/products/${id} failed: ${res.status}`)   // → the nearest error.tsx
const { data: product } = (await res.json()) as ApiSuccess<Product>              // the one envelope

// Client Component: React Query
const { data } = useQuery({ queryKey: ["user", id], queryFn: () => api.getUser(id) })
```

## Server Actions
```typescript
// app/users/actions.ts
"use server"
import { revalidatePath } from "next/cache"
import { requireSession } from "@/lib/auth"
import { db } from "@/lib/db"
import { createUserSchema } from "@/lib/validations/user"   // ui/form-validation-protocol.md
import type { FieldError } from "@/types/api"

export type CreateUserState = { details: FieldError[] }

// A Server Action is a public POST endpoint: authenticate and authorize inside it, every time.
export async function createUser(_prev: CreateUserState, formData: FormData): Promise<CreateUserState> {
    const session = await requireSession({ role: "admin" })
    const parsed = createUserSchema.safeParse(Object.fromEntries(formData))
    if (!parsed.success) {
        // the same details[] shape as the API's 400 VALIDATION_FAILED, so the form maps it the same way
        return { details: parsed.error.issues.map((i) => ({ field: i.path.join("."), code: i.code, message: i.message })) }
    }
    await db.users.create({ ...parsed.data, tenant_id: session.tenantId })
    revalidatePath("/users")
    return { details: [] }
}
```
Use Server Actions for form mutations — no API route needed. A client form calls one through
`const [state, formAction, pending] = useActionState(createUser, { details: [] })` and `<form action={formAction}>`.

## Environment Variables
- `NEXT_PUBLIC_*` — exposed to browser (API URLs only, never secrets)
- All others — server-only

## Rules
- `next/image` for all images — auto optimization
- `next/link` for all internal navigation — prefetching
- `proxy.ts` (Next 16 renamed `middleware.ts`; the old name logs a deprecation warning) only for optimistic
  redirects such as "no session cookie → /login". Verify the session again where data is read or written: in
  the Server Component, Server Action or Route Handler itself (as `UsersPage` and `createUser` do above)
- `loading.tsx` and `error.tsx` alongside every page route
