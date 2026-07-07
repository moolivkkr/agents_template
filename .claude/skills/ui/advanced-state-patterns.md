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

Reference patterns for optimistic updates, WebSocket integration, offline-first, URL state, and cross-tab sync. All patterns use TanStack Query + React.

---

## 1. Optimistic Updates with TanStack Query

Optimistic updates show the result immediately, then reconcile with the server response.

### Pattern: Optimistic List Item Deletion
```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export function useDeleteItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.items.delete(id),

    // Step 1: Optimistically update the cache BEFORE server responds
    onMutate: async (deletedId) => {
      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries({ queryKey: ["items", "list"] });

      // Snapshot the previous value for rollback
      const previousItems = queryClient.getQueryData<ApiResponse<Item[]>>(["items", "list"]);

      // Optimistically remove the item from the cache
      queryClient.setQueryData<ApiResponse<Item[]>>(["items", "list"], (old) => {
        if (!old) return old;
        return {
          ...old,
          data: old.data.filter((item) => item.id !== deletedId),
          meta: old.meta ? { ...old.meta, total: old.meta.total - 1 } : old.meta,
        };
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
      const previousItems = queryClient.getQueryData<ApiResponse<Item[]>>(["items", "list"]);

      // Create a temporary item with a temp ID
      const optimisticItem: Item = {
        id: `temp-${Date.now()}`,
        ...newItem,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      queryClient.setQueryData<ApiResponse<Item[]>>(["items", "list"], (old) => {
        if (!old) return old;
        return {
          ...old,
          data: [optimisticItem, ...old.data],
          meta: old.meta ? { ...old.meta, total: old.meta.total + 1 } : old.meta,
        };
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
      const previousItem = queryClient.getQueryData<ApiResponse<Item>>(["items", "detail", id]);

      queryClient.setQueryData<ApiResponse<Item>>(["items", "detail", id], (old) => {
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

interface WSMessage {
  type: "created" | "updated" | "deleted";
  resource: string;
  data: Record<string, unknown>;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8080/ws";
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useWebSocket() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = localStorage.getItem("auth_token");
    const ws = new WebSocket(`${WS_URL}?token=${token}`);
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
      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts.current);
        reconnectTimer.current = setTimeout(() => {
          reconnectAttempts.current++;
          connect();
        }, Math.min(delay, 30000)); // Cap at 30s
      }
    };

    ws.onerror = (error) => {
      console.error("[WS] Error:", error);
    };
  }, [queryClient]);

  useEffect(() => {
    connect();
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
    queryClient.setQueryData(
      [msg.resource, "list"],
      (old: any) => old ? {
        ...old,
        data: old.data.filter((item: any) => item.id !== msg.data.id),
      } : old
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
import { onlineManager, MutationCache } from "@tanstack/react-query";

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

async function queueMutation(mutation: { endpoint: string; method: string; body: unknown }) {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).add({
    ...mutation,
    timestamp: Date.now(),
    status: "pending",
  });
}

async function flushMutationQueue() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const store = tx.objectStore(STORE_NAME);
  const allMutations = await new Promise<any[]>((resolve) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
  });

  for (const mutation of allMutations.filter((m) => m.status === "pending")) {
    try {
      await fetch(mutation.endpoint, {
        method: mutation.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mutation.body),
      });
      store.delete(mutation.id);
    } catch {
      // Will retry on next sync
      break; // Stop processing if network still failing
    }
  }
}

// Flush queue when coming back online
window.addEventListener("online", () => {
  flushMutationQueue();
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

// Define valid filter schema
const filterSchema = z.object({
  page: z.coerce.number().min(1).default(1),
  per_page: z.coerce.number().min(10).max(100).default(25),
  search: z.string().default(""),
  status: z.enum(["all", "active", "inactive"]).default("all"),
  sort: z.enum(["name", "created_at", "updated_at"]).default("created_at"),
  order: z.enum(["asc", "desc"]).default("desc"),
});

type Filters = z.infer<typeof filterSchema>;

export function useURLFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse and validate current URL params
  const filters: Filters = filterSchema.parse(
    Object.fromEntries(searchParams.entries())
  );

  // Update URL params (replaces history entry — no back-button spam)
  function setFilters(updates: Partial<Filters>) {
    const merged = { ...filters, ...updates };
    // Reset page to 1 when filters change (except when explicitly setting page)
    if (!("page" in updates)) merged.page = 1;

    const params = new URLSearchParams();
    Object.entries(merged).forEach(([key, value]) => {
      const defaultValue = filterSchema.shape[key as keyof Filters]._def.defaultValue?.();
      if (value !== defaultValue) {
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
    queryFn: () => api.items.list(filters),
  });

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
      {/* Data table with pagination */}
      <Pagination
        page={filters.page}
        perPage={filters.per_page}
        total={data?.meta?.total ?? 0}
        onChange={(page) => setFilters({ page })}
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
```typescript
const AUTH_CHANNEL = "auth-sync";

export function useAuthSync() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const channel = new BroadcastChannel(AUTH_CHANNEL);

    channel.onmessage = (event) => {
      switch (event.data.type) {
        case "LOGOUT":
          // Another tab logged out — clear local state and redirect
          localStorage.removeItem("auth_token");
          queryClient.clear();
          window.location.href = "/login";
          break;

        case "LOGIN":
          // Another tab logged in — refresh auth state
          queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
          break;

        case "TOKEN_REFRESH":
          // Another tab refreshed the token — update local storage
          localStorage.setItem("auth_token", event.data.token);
          break;
      }
    };

    return () => channel.close();
  }, [queryClient]);
}

// Broadcast auth events
export function broadcastAuth(type: "LOGIN" | "LOGOUT" | "TOKEN_REFRESH", token?: string) {
  try {
    const channel = new BroadcastChannel(AUTH_CHANNEL);
    channel.postMessage({ type, token });
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

// Fallback: use localStorage events for older browsers
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
