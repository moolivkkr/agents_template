---
skill: api-integration-patterns
description: UI data-fetching layer — TanStack Query hooks, HTTP client setup (cookie session + CSRF, never tokens in web storage), request/response typing against the one envelope; bans direct fetch in components
version: "1.1"
tags:
  - api
  - tanstack-query
  - http
  - data-fetching
  - ui
---

# API Integration Patterns — HTTP Client + TanStack Query

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, TanStack Query 5.104 and axios 1.20; the fetch and Axios clients ran in 5 Vitest 5.0.3 tests against MSW 3.0.1, and the providers + prefetching page in a `next build` (Next.js 16.3.8) (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

The response shape is defined once, in `~/.claude/skills/api/response-envelope.md`; the TypeScript types
below are generated from it (`ui/type-generation-protocol.md`). Token handling follows
`~/.claude/skills/security/secure-coding.md` §3 and `~/.claude/skills/infrastructure/auth-session-flows.md`.

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
- `useInfiniteQuery()` for paginated lists (cursor pagination)
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

**Where the session lives.** The server sets the session in an **httpOnly, Secure, SameSite=Lax (or
Strict) cookie**. JavaScript never reads, stores or forwards a token. Never put a token in
`localStorage` or `sessionStorage`: any XSS, including one from a compromised dependency, can read
them. Never put one in a URL either, because URLs end up in logs.

```tsx
// lib/api-client.ts
// Envelope types + the contract's payload types, generated (ui/type-generation-protocol.md)
import type { ApiErrorBody, ApiSuccess, CreateUserRequest, FieldError, UpdateUserRequest, User } from "@/types/api";

// Same-origin by default: the ingress routes /api to the backend, so one build runs in dev, qa and prod.
// If the API is on another origin, the base URL is a build-time value named the way the bundler exposes
// it: process.env.NEXT_PUBLIC_API_URL in Next.js, import.meta.env.VITE_API_URL in Vite (process.env is
// undefined in a Vite browser bundle). Cross-origin cookies also need CORS with an explicit origin.
const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,              // UPPER_SNAKE, e.g. VALIDATION_FAILED, NOT_FOUND
    message: string,                  // safe to show the user
    public details: FieldError[] = [],// field errors for VALIDATION_FAILED
    public requestId?: string,        // show it in the error UI so support can find the log line
    public retryable = false,
  ) {
    super(message);
  }
}

// CSRF (cookie sessions): the server sets a readable csrf_token cookie; state-changing requests echo it
// in a header the server requires. SameSite alone is not enough for every browser/flow.
export function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const pair = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="));
  // Everything after the first "=": base64 tokens end in "=" padding, and the value may be URL-encoded.
  return pair ? decodeURIComponent(pair.slice("csrf_token=".length)) : undefined;
}

export async function fetcher<T>(path: string, init: RequestInit = {}): Promise<ApiSuccess<T>> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, method, headers, credentials: "same-origin" });

  if (res.status === 204) {
    return { data: undefined as T, meta: { request_id: res.headers.get("X-Request-Id") ?? "" } };
  }
  const body: unknown = await res.json().catch(() => null);

  // Success and error are exclusive: branch on the status, never on `error === null`.
  if (!res.ok) {
    const e = (body as ApiErrorBody | null)?.error;
    if (res.status === 401 && typeof window !== "undefined") {
      // The login page only accepts a same-origin path in returnTo (open-redirect guard).
      window.location.assign(`/login?returnTo=${encodeURIComponent(window.location.pathname)}`);
    }
    throw new ApiError(res.status, e?.code ?? "UNKNOWN", e?.message ?? `Request failed (${res.status})`,
      e?.details ?? [], e?.request_id, e?.retryable ?? false);
  }
  return body as ApiSuccess<T>;
}

const toQuery = (p: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(p).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]),
  ).toString();

// Typed resource API — matches api-contracts.md exactly
export const api = {
  users: {
    // Cursor pagination: pass meta.pagination.next_cursor back as ?cursor=; never page/offset.
    list: (params: { cursor?: string; limit?: number; search?: string; role?: string } = {}) =>
      fetcher<User[]>(`/v1/users?${toQuery(params)}`),
    get: (id: string) => fetcher<User>(`/v1/users/${encodeURIComponent(id)}`),
    // One Idempotency-Key per user action, reused if the same submit is retried.
    create: ({ input, idempotencyKey }: { input: CreateUserRequest; idempotencyKey: string }) =>
      fetcher<User>("/v1/users", {
        method: "POST",
        body: JSON.stringify(input),
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    update: (id: string, input: UpdateUserRequest) =>
      fetcher<User>(`/v1/users/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(input) }),
    delete: (id: string) => fetcher<void>(`/v1/users/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },
};
```

### Bearer-token APIs (only when IMPLEMENTATION_GUIDELINES §4.1 says so)

Keep the short-lived **access token in memory** (a module variable, or React state/context). The
**refresh token is an httpOnly cookie** scoped to the refresh endpoint. After a reload the app calls
refresh once to get a new access token. Nothing is persisted in web storage.

```tsx
// lib/auth-token.ts
import { csrfToken } from "@/lib/api-client";
let accessToken: string | null = null;            // memory only: gone on reload, unreadable to other origins
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const authHeader = (): Record<string, string> => (accessToken ? { Authorization: `Bearer ${accessToken}` } : {});

let refreshing: Promise<boolean> | null = null;   // one refresh at a time, shared by concurrent 401s
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrfToken() ?? "" },   // the refresh cookie is SameSite=Strict + this header
  })
    .then(async (r) => (r.ok ? (setAccessToken((await r.json()).data.access_token), true) : false))
    .finally(() => { refreshing = null; });
  return refreshing;
}
// In fetcher: merge authHeader() into headers; on the FIRST 401, await refreshAccessToken() and retry the
// request once; a second 401 goes to /login. Never log the token, never put it in a URL.
```

WebSockets never carry a token in the URL (`?token=` ends up in proxy and access logs). See
`ui/advanced-state-patterns.md` §WebSocket: fetch a short-lived single-use ticket over an authenticated
request, or rely on the session cookie the handshake already sends.

## TanStack Query Setup

```tsx
// lib/query-client.ts
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api-client";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,       // 1 minute
        gcTime: 5 * 60 * 1000,      // 5 minutes (was cacheTime in v4)
        // Queries are GETs (idempotent): retry once, but not on 4xx — they won't change on retry.
        retry: (count, err) => count < 1 && !(err instanceof ApiError && err.status < 500 && err.status !== 429),
        refetchOnWindowFocus: false,
      },
      // Mutations are not retried automatically: a retried POST without the same Idempotency-Key can
      // create a duplicate. Retry only by re-submitting the same variables (same key).
      mutations: { retry: 0 },
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
import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

type UserFilters = { search?: string; role?: string };

export const userQueries = {
  all: () => ["users"] as const,
  list: (filters: UserFilters = {}) =>
    infiniteQueryOptions({
      queryKey: ["users", "list", filters],
      queryFn: ({ pageParam }) => api.users.list({ ...filters, cursor: pageParam, limit: 20 }),
      initialPageParam: undefined as string | undefined,
      getNextPageParam: (last) =>
        last.meta.pagination?.has_more ? last.meta.pagination.next_cursor ?? undefined : undefined,
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
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userQueries } from "@/lib/queries/users";
import { api, ApiError } from "@/lib/api-client";
import type { UpdateUserRequest } from "@/types/api";
import { toast } from "sonner";

// READ (list) — pages of { data: User[], meta.pagination }
export function useUsers(filters?: Parameters<typeof userQueries.list>[0]) {
  return useInfiniteQuery(userQueries.list(filters));
}
// consumer: const users = query.data?.pages.flatMap((p) => p.data) ?? [];
//           <LoadMore disabled={!query.hasNextPage} onClick={() => query.fetchNextPage()} />

// READ (single)
export function useUser(id: string) {
  return useQuery(userQueries.detail(id));
}

// CREATE — the caller creates the Idempotency-Key once per submit: crypto.randomUUID()
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.users.create,
    onSuccess: () => {
      toast.success("User created");
      queryClient.invalidateQueries({ queryKey: userQueries.all() });
    },
    onError: (error) => {
      // VALIDATION_FAILED: the form maps error.details[] onto its fields (error-handling-patterns.md)
      if (error instanceof ApiError && error.code === "VALIDATION_FAILED") return;
      toast.error(error instanceof ApiError ? error.message : "Failed to create user");
    },
  });
}

// UPDATE
export function useUpdateUser(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateUserRequest) => api.users.update(id, input),
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
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: userQueries.all() });
      const previous = queryClient.getQueriesData({ queryKey: ["users", "list"] });
      // Optimistic removal handled in component or via setQueryData
      return { previous };
    },
    onError: (_err, _id, context) => {
      context?.previous.forEach(([key, data]) => queryClient.setQueryData(key, data));
      toast.error("Failed to delete user");
    },
    onSuccess: () => toast.success("User deleted"),
    onSettled: () => queryClient.invalidateQueries({ queryKey: userQueries.all() }),
  });
}
```

## Response Shape — TypeScript Types

Import the generated types; never hand-write an envelope (`ui/type-generation-protocol.md`).

```tsx
import type { ApiSuccess, ApiErrorBody, Pagination, User } from "@/types/api";

// Single:  { data: User, meta: { request_id } }
// List:    { data: User[], meta: { request_id, pagination: { next_cursor, has_more, limit, total_count? } } }
// Error:   { error: { code, message, details[], request_id, retryable } }   ← thrown as ApiError, no `data`
```

## Server Component Prefetching (Next.js)

```tsx
// app/(dashboard)/users/page.tsx — Server Component
import { cookies } from "next/headers";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import type { ApiSuccess, User } from "@/types/api";
import { makeQueryClient } from "@/lib/query-client";
import { userQueries } from "@/lib/queries/users";
import { UserList } from "@/components/features/user-list";

// On the server `fetcher`'s "/api" has no page origin to resolve against, and there is no browser cookie
// jar: call your own API by its internal URL and forward ONLY the session cookie.
async function firstUsersPage(): Promise<ApiSuccess<User[]>> {
  const session = (await cookies()).get("session")?.value;
  const res = await fetch(`${process.env.API_INTERNAL_URL}/api/v1/users?limit=20`, {
    headers: session ? { Cookie: `session=${session}` } : {},
    cache: "no-store", // per-user data: never in a shared cache
  });
  if (!res.ok) throw new Error(`GET /api/v1/users failed: ${res.status}`);
  return res.json();
}

export default async function UsersPage() {
  const queryClient = makeQueryClient();
  // Same queryKey as the client's useUsers(), so the client hydrates instead of refetching
  await queryClient.prefetchInfiniteQuery({ ...userQueries.list(), queryFn: firstUsersPage });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UserList />
    </HydrationBoundary>
  );
}
```

A server-side prefetch runs without the browser's cookies unless you forward them explicitly (Next.js
`cookies()`, as above). Forward only the session cookie, and only to your own API origin. A prefetch that
fails is swallowed by `prefetchInfiniteQuery` and the client fetches instead, so check the server log rather
than assuming the page was prefetched.

## HTTP Client Error Interceptor

The `fetcher` above already turns the error envelope into an `ApiError`. If the project uses Axios
instead, normalize to the same class:

```tsx
// lib/axios-client.ts — alternative to fetch-based client
import axios from "axios";
import { ApiError } from "@/lib/api-client";

const apiClient = axios.create({
  baseURL: "/api",                 // same-origin; see API_BASE above
  xsrfCookieName: "csrf_token",    // Axios echoes this cookie…
  xsrfHeaderName: "X-CSRF-Token",  // …in this header on state-changing requests
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const e = error.response?.data?.error;
    if (error.response) {
      return Promise.reject(new ApiError(error.response.status, e?.code ?? "UNKNOWN",
        e?.message ?? error.message, e?.details ?? [], e?.request_id, e?.retryable ?? false));
    }
    return Promise.reject(error);
  },
);

export { apiClient };
```

This way every error consumer sees the same shape, whatever the HTTP client:
- `error.status` — HTTP status (400, 401, 403, 404, 409, 422, 429, 5xx)
- `error.code` — machine-readable code (`"VALIDATION_FAILED"`, `"NOT_FOUND"`, `"BUSINESS_RULE_VIOLATION"`)
- `error.message` — user-safe message
- `error.details` — `FieldError[]` for `VALIDATION_FAILED`, otherwise `[]`
- `error.requestId` / `error.retryable`

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Fetch in `useEffect` | `useQuery` from TanStack Query |
| Store API data in `useState` | Let Query cache manage it |
| Token in `localStorage` / `sessionStorage` | httpOnly Secure SameSite cookie, or an in-memory access token |
| Token in a URL (`?token=`, WS URL) | Cookie, `Authorization` header, or a single-use WS ticket |
| Cookie auth without CSRF protection | SameSite + `X-CSRF-Token` on state-changing requests |
| Hardcode API URLs / `process.env` in a Vite app | Same-origin `/api`, or the bundler's public env var |
| `page` / `per_page` / `offset` params | `cursor` + `limit`, next page from `meta.pagination.next_cursor` |
| Check `if (body.error === null)` | Branch on `res.ok` / `"error" in body` |
| Retry a POST without the same `Idempotency-Key` | One key per user action, reused on re-submit |
| Ignore `isLoading`/`isError` | Handle ALL 3 states in every query consumer |
| Duplicate query keys as strings | Query key factory in `lib/queries/` |
| `new QueryClient()` outside useState | `useState(() => makeQueryClient())` |
| `cacheTime` | `gcTime` (renamed in TanStack Query v5) |
| Skip invalidation after mutation | `onSettled: () => queryClient.invalidateQueries(...)` |
| Fetch all data on page load | Paginate + prefetch next page |
