---
skill: api-integration-patterns
description: UI data-fetching layer — TanStack Query hooks, HTTP client setup, request/response typing; bans direct fetch in components
version: "1.0"
tags:
  - api
  - tanstack-query
  - http
  - data-fetching
  - ui
---

# API Integration Patterns — HTTP Client + TanStack Query

## CRITICAL RULE: No Raw Data Fetching in Components

Components MUST use the project's data fetching layer (TanStack Query hooks). These patterns are BANNED in component files:

**BANNED:**
- `fetch()` or `axios.get()` directly in components
- `useEffect(() => { fetch(...) }, [])` pattern
- `useState` + `useEffect` for data loading
- `useSWR` unless it's the project's chosen library

**REQUIRED:**
- `useQuery()` from TanStack Query with query key factory
- `useMutation()` for state-changing operations
- `useInfiniteQuery()` for paginated lists
- Custom hooks in `lib/api/` that wrap the above

**WHY:** Raw fetch bypasses query caching, deduplication, retry logic, and invalidation. It causes:
- Duplicate requests (no deduplication)
- Stale data (no automatic refetch)
- No loading/error states (must implement manually)
- Broken optimistic updates (no cache to update)

### Enforcement
`code_reviewer_I` MUST flag any `fetch()`, `axios`, or `useEffect` data fetching in component files as BLOCKING.

---

## HTTP Client Setup

```tsx
// lib/api-client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function fetcher<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("auth_token")
    : null;

  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    ...init,
  });

  // 401 → redirect to login
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // Backend returns: {"error": {"code": "...", "message": "...", "details": {...}}}
    // Unwrap the error envelope so consumers can access .code, .message, .details directly.
    const envelope = body.error ?? body;
    const error: any = new Error(envelope.message ?? `Request failed: ${res.status}`);
    error.status = res.status;
    error.code = envelope.code;
    error.details = envelope.details; // For 422 field-level validation errors
    throw error;
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Typed resource API — matches api-contracts.md exactly
export const api = {
  users: {
    list: (params?: { page?: number; search?: string; role?: string }) =>
      fetcher<{ data: User[]; meta: { total: number; page: number } }>(
        `/v1/users?${new URLSearchParams(params as any)}`
      ),
    get: (id: string) => fetcher<{ data: User }>(`/v1/users/${id}`),
    create: (data: CreateUserInput) =>
      fetcher<{ data: User }>("/v1/users", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<User>) =>
      fetcher<{ data: User }>(`/v1/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) =>
      fetcher<void>(`/v1/users/${id}`, { method: "DELETE" }),
  },
};
```

## TanStack Query Setup

```tsx
// lib/query-client.ts
import { QueryClient } from "@tanstack/react-query";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,       // 1 minute
        gcTime: 5 * 60 * 1000,      // 5 minutes (was cacheTime in v4)
        retry: 1,                    // Retry once on failure
        refetchOnWindowFocus: false,
      },
    },
  });
}

// components/providers.tsx
"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";
import { makeQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

## Query Key Factory Pattern

```tsx
// lib/queries/users.ts
import { queryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export const userQueries = {
  all: () => ["users"] as const,
  list: (filters?: { page?: number; search?: string; role?: string }) =>
    queryOptions({
      queryKey: ["users", "list", filters ?? {}],
      queryFn: () => api.users.list(filters),
    }),
  detail: (id: string) =>
    queryOptions({
      queryKey: ["users", "detail", id],
      queryFn: () => api.users.get(id),
      enabled: !!id,
    }),
};
```

## CRUD Hooks

```tsx
// hooks/use-users.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userQueries } from "@/lib/queries/users";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

// READ (list)
export function useUsers(filters?: Parameters<typeof api.users.list>[0]) {
  return useQuery(userQueries.list(filters));
}

// READ (single)
export function useUser(id: string) {
  return useQuery(userQueries.detail(id));
}

// CREATE
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.users.create,
    onSuccess: () => {
      toast.success("User created");
      queryClient.invalidateQueries({ queryKey: userQueries.all() });
    },
    onError: (error: any) => {
      if (error.status !== 422) toast.error("Failed to create user");
      // 422 errors handled by form's mapServerErrors
    },
  });
}

// UPDATE
export function useUpdateUser(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<User>) => api.users.update(id, data),
    onSuccess: () => {
      toast.success("User updated");
      queryClient.invalidateQueries({ queryKey: userQueries.all() });
    },
    onError: () => toast.error("Failed to update user"),
  });
}

// DELETE (with optimistic update)
export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.users.delete,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: userQueries.all() });
      const previous = queryClient.getQueryData(["users", "list"]);
      // Optimistic removal handled in component or via setQueryData
      return { previous };
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(["users", "list"], context?.previous);
      toast.error("Failed to delete user");
    },
    onSuccess: () => toast.success("User deleted"),
    onSettled: () => queryClient.invalidateQueries({ queryKey: userQueries.all() }),
  });
}
```

## Response Shape — TypeScript Types

```tsx
// Types match api-contracts.md EXACTLY
interface ApiResponse<T> {
  data: T;
  error: string | null;
  meta?: { total: number; page: number; per_page: number };
}

interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "member" | "viewer";
  created_at: string;
  updated_at: string;
}

// When consuming:
const { data: response } = useUsers();
// response.data = User[]  (the array)
// response.meta = { total, page }  (pagination)
```

## Server Component Prefetching (Next.js)

```tsx
// app/(dashboard)/users/page.tsx — Server Component
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { makeQueryClient } from "@/lib/query-client";
import { userQueries } from "@/lib/queries/users";
import { UserList } from "@/components/features/user-list";

export default async function UsersPage() {
  const queryClient = makeQueryClient();
  await queryClient.prefetchQuery(userQueries.list());

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UserList />
    </HydrationBoundary>
  );
}
```

## HTTP Client Error Interceptor

The `fetcher` function above already unwraps the backend error envelope (`{"error": {"code": "...", ...}}`). If you use a different HTTP client (e.g., Axios), add an interceptor to normalize the error shape:

```tsx
// lib/axios-client.ts — alternative to fetch-based client
import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "/api",
});

// Response interceptor: unwrap error envelope from backend
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Backend returns: {"error": {"code": "...", "message": "...", "details": {...}}}
      const envelope = error.response.data?.error ?? error.response.data;
      const normalized: any = new Error(envelope?.message ?? error.message);
      normalized.status = error.response.status;
      normalized.code = envelope?.code;
      normalized.details = envelope?.details;
      return Promise.reject(normalized);
    }
    return Promise.reject(error);
  },
);

export { apiClient };
```

This ensures that regardless of HTTP client, error consumers always see the same shape:
- `error.status` — HTTP status code (e.g., 422, 404, 409)
- `error.code` — machine-readable code (e.g., `"VALIDATION_ERROR"`, `"NOT_FOUND"`)
- `error.message` — human-readable message
- `error.details` — structured details (field errors for 422, resource info for 404, etc.)

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Fetch in `useEffect` | `useQuery` from TanStack Query |
| Store API data in `useState` | Let Query cache manage it |
| Hardcode API URLs | Use `process.env.NEXT_PUBLIC_API_URL` |
| Ignore `isLoading`/`isError` | Handle ALL 3 states in every query consumer |
| Duplicate query keys as strings | Query key factory in `lib/queries/` |
| `new QueryClient()` outside useState | `useState(() => makeQueryClient())` |
| `cacheTime` | `gcTime` (renamed in TanStack Query v5) |
| Skip invalidation after mutation | `onSettled: () => queryClient.invalidateQueries(...)` |
| Fetch all data on page load | Paginate + prefetch next page |
