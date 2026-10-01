---
skill: advanced-state-patterns
description: Complex UI state — optimistic updates, WebSocket integration, offline-first, URL state, cross-tab sync with TanStack Query + React
version: "1.0"
tags:
  - state
  - tanstack-query
  - websocket
  - optimistic
  - ui
---

# Advanced State Patterns — Complex UI State Management

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, TanStack Query 5.104, React Router 7.18 and Zod 4.6; the offline mutation queue also ran in 2 Vitest 5.0.3 tests on fake-indexeddb 6.2.5 + MSW 3.0.1 (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

Reference patterns for optimistic updates, WebSocket integration, offline-first, URL state, and cross-tab sync. All patterns use TanStack Query + React.

---

## 1. Optimistic Updates with TanStack Query

Optimistic updates show the result immediately, then reconcile with the server response.

### Pattern: Optimistic List Item Deletion
```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { ApiSuccess, Item } from "@/types/api"; // the one envelope (api/response-envelope.md)

export function useDeleteItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.items.delete(id),

    // Step 1: Optimistically update the cache BEFORE server responds
    onMutate: async (deletedId) => {
      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries({ queryKey: ["items", "list"] });

      // Snapshot the previous value for rollback
      const previousItems = queryClient.getQueryData<ApiSuccess<Item[]>>(["items", "list"]);

      // Optimistically remove the item from the cache. meta (request_id, pagination) stays as the server sent
      // it: there is no item count in the envelope to adjust, and onSettled refetches anyway.
      queryClient.setQueryData<ApiSuccess<Item[]>>(["items", "list"], (old) => {
        if (!old) return old;
        return { ...old, data: old.data.filter((item) => item.id !== deletedId) };
      });

      return { previousItems };
    },

    // Step 2: If the mutation fails, roll back to the previous value
    onError: (_err, _deletedId, context) => {
      if (context?.previousItems) {
        queryClient.setQueryData(["items", "list"], context.previousItems);
      }
      toast.error("Failed to delete item");
    },

    // Step 3: Always refetch after error or success to ensure cache is in sync
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },

    onSuccess: () => {
      toast.success("Item deleted");
    },
  });
}
```

### Pattern: Optimistic Create (add to list)
```typescript
export function useCreateItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (newItem: CreateItemInput) => api.items.create(newItem),

    onMutate: async (newItem) => {
      await queryClient.cancelQueries({ queryKey: ["items", "list"] });
      const previousItems = queryClient.getQueryData<ApiSuccess<Item[]>>(["items", "list"]);

      // Create a temporary item with a temp ID
      const optimisticItem: Item = {
        id: `temp-${Date.now()}`,
        ...newItem,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      queryClient.setQueryData<ApiSuccess<Item[]>>(["items", "list"], (old) => {
        if (!old) return old;
        return { ...old, data: [optimisticItem, ...old.data] };
      });

      return { previousItems };
    },

    onError: (_err, _newItem, context) => {
      if (context?.previousItems) {
        queryClient.setQueryData(["items", "list"], context.previousItems);
      }
      toast.error("Failed to create item");
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },

    onSuccess: () => {
      toast.success("Item created");
    },
  });
}
```

### Pattern: Optimistic Toggle (inline update)
```typescript
export function useToggleItemStatus(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (newStatus: "active" | "inactive") =>
      api.items.update(id, { status: newStatus }),

    onMutate: async (newStatus) => {
      await queryClient.cancelQueries({ queryKey: ["items", "detail", id] });
      const previousItem = queryClient.getQueryData<ApiSuccess<Item>>(["items", "detail", id]);

      queryClient.setQueryData<ApiSuccess<Item>>(["items", "detail", id], (old) => {
        if (!old) return old;
        return { ...old, data: { ...old.data, status: newStatus } };
      });

      return { previousItem };
    },

    onError: (_err, _newStatus, context) => {
      if (context?.previousItem) {
        queryClient.setQueryData(["items", "detail", id], context.previousItem);
      }
      toast.error("Failed to update status");
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}
```

---

## 2. WebSocket Integration — Real-Time Data Sync

### Pattern: WebSocket with TanStack Query Cache Sync
```typescript
import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { fetcher } from "@/lib/api-client";

interface WSMessage {
  type: "created" | "updated" | "deleted";
  resource: string;
  data: Record<string, unknown>;
}

// Same origin as the page (the ingress routes /api/ws to the backend): the session cookie is sent on the
// handshake and the server checks the Origin header (cross-site WebSocket hijacking).
const wsUrl = (path: string) =>
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${path}`;
const RECONNECT_BASE_MS = 1000;
const MAX_RECONNECT_ATTEMPTS = 10;

// Auth: NEVER a bearer token in the WebSocket URL — query strings land in proxy, ingress and access logs.
// Fetch a short-lived (≈30 s), single-use ticket over an authenticated request, and send a new one on
// every (re)connect. The server binds the ticket to the user/tenant and deletes it on first use.
async function fetchWsTicket(): Promise<string> {
  const res = await fetcher<{ ticket: string }>("/v1/ws-tickets", { method: "POST" });
  return res.data.ticket;
}

export function useWebSocket() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined); // React 19: useRef needs an initial value

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    let ticket: string;
    try {
      ticket = await fetchWsTicket();
    } catch {
      return scheduleReconnect(); // 401 already redirected to /login in fetcher
    }
    const ws = new WebSocket(`${wsUrl("/api/ws")}?ticket=${encodeURIComponent(ticket)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      console.log("[WS] Connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        handleWSMessage(queryClient, msg);
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };

    ws.onclose = (event) => {
      console.log("[WS] Disconnected:", event.code, event.reason);
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      console.error("[WS] Error:", error);
    };
    function scheduleReconnect() {
      if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) return;
      // Exponential backoff with FULL jitter, capped at 30 s: after a server restart, thousands of
      // clients must not reconnect in the same instant (thundering herd).
      const cap = Math.min(RECONNECT_BASE_MS * 2 ** reconnectAttempts.current, 30000);
      reconnectTimer.current = setTimeout(() => {
        reconnectAttempts.current++;
        void connect();
      }, Math.random() * cap);
    }
  }, [queryClient]);

  useEffect(() => {
    void connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close(1000, "Component unmounted");
    };
  }, [connect]);

  return wsRef;
}

function handleWSMessage(queryClient: ReturnType<typeof import("@tanstack/react-query").useQueryClient>, msg: WSMessage) {
  // Invalidate queries for the affected resource
  // This triggers a refetch, ensuring cache stays in sync
  queryClient.invalidateQueries({ queryKey: [msg.resource] });

  // For high-frequency updates, directly update the cache instead of invalidating:
  if (msg.type === "updated" && msg.data.id) {
    queryClient.setQueryData(
      [msg.resource, "detail", msg.data.id],
      (old: any) => old ? { ...old, data: { ...old.data, ...msg.data } } : old
    );
  }

  if (msg.type === "deleted" && msg.data.id) {
    // Lists are cursor-paginated infinite queries ({ pages: [{ data: T[], meta }] }): drop the item
    // from every loaded page, then let invalidation (above) reconcile.
    queryClient.setQueriesData({ queryKey: [msg.resource, "list"] }, (old: any) =>
      old?.pages
        ? { ...old, pages: old.pages.map((p: any) => ({ ...p, data: p.data.filter((i: any) => i.id !== msg.data.id) })) }
        : old
    );
  }
}
```

### State Reconciliation After Reconnect
```typescript
// After reconnecting, refetch all active queries to reconcile state
ws.onopen = () => {
  reconnectAttempts.current = 0;
  // Reconcile: invalidate all queries so they refetch fresh data
  queryClient.invalidateQueries();
};
```

---

## 3. Offline-First Patterns — IndexedDB Queue + Sync

### Pattern: Mutation Queue with Offline Support
```typescript
// lib/offline-queue.ts
import { onlineManager } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, fetcher } from "@/lib/api-client"; // session cookie + CSRF header + the envelope (api-integration-patterns.md)

// Track online status
onlineManager.setEventListener((setOnline) => {
  const onlineHandler = () => setOnline(true);
  const offlineHandler = () => setOnline(false);
  window.addEventListener("online", onlineHandler);
  window.addEventListener("offline", offlineHandler);
  return () => {
    window.removeEventListener("online", onlineHandler);
    window.removeEventListener("offline", offlineHandler);
  };
});

// Persist pending mutations to IndexedDB
const DB_NAME = "app-mutation-queue";
const STORE_NAME = "mutations";

type QueuedMutation = { id: number; endpoint: string; method: string; body: unknown; idempotencyKey: string; timestamp: number };

async function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function queueMutation(mutation: { endpoint: string; method: string; body: unknown }) {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readwrite");
  // One Idempotency-Key per queued action: a replay after a lost response is not applied twice
  tx.objectStore(STORE_NAME).add({ ...mutation, idempotencyKey: crypto.randomUUID(), timestamp: Date.now() });
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function flushMutationQueue() {
  const db = await openDB();
  // Read the queue in its own transaction. An IndexedDB transaction commits as soon as it has no pending
  // request, so it can't stay open across `await fetch(...)`: a delete after the await would throw
  // TransactionInactiveError and the sent mutation would stay queued, to be sent again.
  const queued = await new Promise<QueuedMutation[]>((resolve, reject) => {
    const request = db.transaction(STORE_NAME).objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  for (const mutation of queued) {
    try {
      await fetcher(mutation.endpoint, {
        method: mutation.method,
        body: JSON.stringify(mutation.body),
        headers: { "Idempotency-Key": mutation.idempotencyKey },
      });
    } catch (e) {
      // Still offline (fetch threw), or 429/503 (retryable): keep this and the rest for the next "online"
      if (!(e instanceof ApiError) || e.retryable) break;
      // Rejected (4xx/500): replaying won't help — tell the user and drop it so it can't block the queue
      toast.error(`A change made offline couldn't be saved: ${e.message}`);
    }
    db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME).delete(mutation.id);
  }
}

// Flush queue when coming back online
window.addEventListener("online", () => {
  void flushMutationQueue();
});
```

### Conflict Resolution Strategy
```typescript
// Last-write-wins with timestamp comparison
interface VersionedResource {
  id: string;
  updated_at: string;
  version: number;
}

async function resolveConflict(
  local: VersionedResource,
  remote: VersionedResource
): Promise<"local" | "remote" | "merge"> {
  if (local.version === remote.version) return "local"; // No conflict
  if (new Date(local.updated_at) > new Date(remote.updated_at)) return "local";
  if (new Date(remote.updated_at) > new Date(local.updated_at)) return "remote";
  return "merge"; // Same timestamp, different versions — needs manual merge
}
```

---

## 4. URL State Management — Search Params as Source of Truth

### Pattern: Filters and Pagination in URL
```typescript
import { useSearchParams } from "react-router-dom"; // or next/navigation
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

// Define valid filter schema. Pagination is cursor-based (api/response-envelope.md): the URL holds the
// opaque cursor of the page being shown, never a page number.
const filterSchema = z.object({
  cursor: z.string().default(""),
  limit: z.coerce.number().min(10).max(100).default(25),
  search: z.string().default(""),
  status: z.enum(["all", "active", "inactive"]).default("all"),
  sort: z.enum(["name", "created_at", "updated_at"]).default("created_at"),
  order: z.enum(["asc", "desc"]).default("desc"),
});

type Filters = z.infer<typeof filterSchema>;
const DEFAULTS: Filters = filterSchema.parse({});

export function useURLFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse and validate current URL params. The URL is user input: a hand-edited ?limit=5 falls back to the
  // defaults instead of throwing during render.
  const parsed = filterSchema.safeParse(Object.fromEntries(searchParams.entries()));
  const filters: Filters = parsed.success ? parsed.data : DEFAULTS;

  // Update URL params (replaces history entry — no back-button spam)
  function setFilters(updates: Partial<Filters>) {
    const merged = { ...filters, ...updates };
    // Back to the first page when filters change (except when explicitly paging)
    if (!("cursor" in updates)) merged.cursor = "";

    const params = new URLSearchParams();
    Object.entries(merged).forEach(([key, value]) => {
      if (value !== DEFAULTS[key as keyof Filters]) {   // keep the URL short: defaults are implied
        params.set(key, String(value));
      }
    });
    setSearchParams(params, { replace: true });
  }

  return { filters, setFilters };
}

// Usage in component
function ItemList() {
  const { filters, setFilters } = useURLFilters();

  const { data, isLoading } = useQuery({
    queryKey: ["items", "list", filters],
    queryFn: () => api.items.list({ ...filters, cursor: filters.cursor || undefined }),
  });
  const pagination = data?.meta.pagination;

  return (
    <div>
      <SearchInput
        value={filters.search}
        onChange={(search) => setFilters({ search })}
      />
      <StatusFilter
        value={filters.status}
        onChange={(status) => setFilters({ status })}
      />
      <SortSelect
        value={filters.sort}
        order={filters.order}
        onChange={(sort, order) => setFilters({ sort, order })}
      />
      {/* Data table with cursor pagination: "Next" follows meta.pagination.next_cursor;
          "First page" clears the cursor (browser Back returns to earlier pages) */}
      <CursorPager
        hasMore={pagination?.has_more ?? false}
        onNext={() => pagination?.next_cursor && setFilters({ cursor: pagination.next_cursor })}
        onFirst={filters.cursor ? () => setFilters({ cursor: "" }) : undefined}
      />
    </div>
  );
}
```

### Benefits of URL State
- **Shareable** — copy URL sends exact filter state to another user
- **Bookmarkable** — save filtered views
- **Back/Forward** — browser history works correctly
- **Server-renderable** — filters available on initial server render
- **No state duplication** — URL is the single source of truth

---

## 5. Cross-Tab Synchronization — BroadcastChannel API

### Pattern: Sync Auth State Across Tabs

Tabs share the session cookie, so they only need to hear about **events** (logged out, logged in).
Never send a token over BroadcastChannel and never write one to `localStorage`: any script on the
origin, including an XSS payload, can listen to the channel and read storage. With in-memory bearer
tokens each tab refreshes its own access token through the httpOnly refresh cookie.

```typescript
const AUTH_CHANNEL = "auth-sync";

export function useAuthSync() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const channel = new BroadcastChannel(AUTH_CHANNEL);

    channel.onmessage = (event) => {
      switch (event.data.type) {
        case "LOGOUT":
          // Another tab logged out (the server cleared the cookie) — drop cached data and redirect
          queryClient.clear();
          window.location.href = "/login";
          break;

        case "LOGIN":
          // Another tab logged in — refresh auth state
          queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
          break;
      }
    };

    return () => channel.close();
  }, [queryClient]);
}

// Broadcast auth EVENTS only — never a token value
export function broadcastAuth(type: "LOGIN" | "LOGOUT") {
  try {
    const channel = new BroadcastChannel(AUTH_CHANNEL);
    channel.postMessage({ type });
    channel.close();
  } catch {
    // BroadcastChannel not supported — degrade gracefully
  }
}
```

### Pattern: Sync Data Mutations Across Tabs
```typescript
const DATA_CHANNEL = "data-sync";

export function useDataSync() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const channel = new BroadcastChannel(DATA_CHANNEL);

    channel.onmessage = (event) => {
      const { queryKey } = event.data;
      if (queryKey) {
        // Another tab mutated data — invalidate our cache
        queryClient.invalidateQueries({ queryKey });
      }
    };

    return () => channel.close();
  }, [queryClient]);
}

// After any successful mutation, broadcast to other tabs
function broadcastMutation(queryKey: readonly unknown[]) {
  try {
    const channel = new BroadcastChannel(DATA_CHANNEL);
    channel.postMessage({ queryKey: [...queryKey] });
    channel.close();
  } catch {
    // Degrade gracefully
  }
}

// Integrate with TanStack Query global mutation cache
export function createSyncedQueryClient() {
  return new QueryClient({
    mutationCache: new MutationCache({
      onSuccess: (_data, _variables, _context, mutation) => {
        // Extract the query key to invalidate from mutation meta
        const queryKey = (mutation.options.meta as any)?.invalidateKey;
        if (queryKey) broadcastMutation(queryKey);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        gcTime: 5 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: true, // Refetch when tab gains focus
      },
    },
  });
}
```

### Feature Detection
```typescript
function isBroadcastChannelSupported(): boolean {
  return typeof BroadcastChannel !== "undefined";
}

// Fallback: use localStorage events for older browsers (an event flag only — never a token)
function useLegacyTabSync() {
  useEffect(() => {
    const handler = (event: StorageEvent) => {
      if (event.key === "auth-sync" && event.newValue === "logout") {
        window.location.href = "/login";
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);
}
```

---

## When to Use Each Pattern

| Scenario | Pattern | Complexity |
|----------|---------|------------|
| Delete/toggle with instant feedback | Optimistic Update | Low |
| Live dashboard, notifications | WebSocket + Query Sync | Medium |
| Field workers, poor connectivity | Offline-First + IndexedDB | High |
| Filtered lists, search pages | URL State Management | Low |
| Multi-tab admin dashboards | Cross-Tab Sync | Medium |

### Decision Rules
1. **Default:** TanStack Query with `staleTime` — covers 80% of use cases
2. **Need instant feedback?** Add optimistic updates to mutations
3. **Need real-time?** Add WebSocket layer that invalidates query cache
4. **Need offline?** Add IndexedDB mutation queue + sync-on-reconnect
5. **Need shareable views?** Put filters/pagination in URL params
6. **Need multi-tab consistency?** Add BroadcastChannel sync
