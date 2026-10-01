# TanStack Query v5 patterns for React data fetching.

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against TanStack Query 5.104 and React 19.3; the list, infinite-list and optimistic-delete hooks also ran in 2 Vitest 5.0.3 tests against MSW 3.0.1 (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Query Setup
```typescript
// Provider in App.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, gcTime: 5 * 60_000, retry: 2 },
    mutations: { retry: 0 },
  },
});
<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
```

## Query Key Factory
```typescript
export const resourceKeys = {
  all: ['resources'] as const,
  lists: () => [...resourceKeys.all, 'list'] as const,
  list: (filters: Filters) => [...resourceKeys.lists(), filters] as const,
  infinite: (filters: Filters) => [...resourceKeys.all, 'infinite', filters] as const,
  details: () => [...resourceKeys.all, 'detail'] as const,
  detail: (id: string) => [...resourceKeys.details(), id] as const,
};
```
- Use factory pattern — consistent invalidation
- Keys are arrays — TanStack matches by prefix for invalidation
- `queryClient.invalidateQueries({ queryKey: resourceKeys.all })` invalidates everything
- A `useQuery` and a `useInfiniteQuery` never share a key: one caches a page (`{ data, meta }`), the other
  `{ pages, pageParams }`, and on a shared key one of them reads the other's shape

## List Query Hook
```typescript
export function useResources(filters: Filters) {
  return useQuery({
    queryKey: resourceKeys.list(filters),
    queryFn: () => api.listResources(filters),
    staleTime: 30_000,
    placeholderData: keepPreviousData,  // no flash on filter/page change
  });
}
```
- `placeholderData: keepPreviousData` — keeps old data visible during refetch
- Return value: `{ data, isLoading, isError, error, isFetching }`
- `isLoading` = first load (no cache), `isFetching` = any fetch (including refetch)

## Detail Query Hook
```typescript
export function useResource(id: string) {
  return useQuery({
    queryKey: resourceKeys.detail(id),
    queryFn: () => api.getResource(id),
    enabled: !!id,  // don't fetch if id is empty
  });
}
```

## Mutation Hook
```typescript
export function useCreateResource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateResourceInput) => api.createResource(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: resourceKeys.lists() });
    },
  });
}
```
- Invalidate related queries on success — don't manually update cache unless optimistic
- Use `onError` for toast notifications

## Optimistic Updates
```typescript
export function useDeleteResource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteResource(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: resourceKeys.lists() });
      // Every cached list, whatever its filters: lists() is a key PREFIX, so use the *Queries* variants
      // (getQueryData/setQueryData match one exact key). Each entry is the envelope { data: Resource[], meta }.
      const prev = queryClient.getQueriesData<ApiSuccess<Resource[]>>({ queryKey: resourceKeys.lists() });
      queryClient.setQueriesData<ApiSuccess<Resource[]>>({ queryKey: resourceKeys.lists() }, (old) =>
        old && { ...old, data: old.data.filter((r) => r.id !== id) }
      );
      return { prev };
    },
    onError: (_err, _id, context) => {
      context?.prev.forEach(([key, data]) => queryClient.setQueryData(key, data));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: resourceKeys.lists() });
    },
  });
}
```

## Cursor-Based Pagination
```typescript
export function useResourcesInfinite(filters: Filters) {
  return useInfiniteQuery({
    queryKey: resourceKeys.infinite(filters),   // not list(filters): that key holds useResources' single page
    queryFn: ({ pageParam }) => api.listResources({ ...filters, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    // Each page is the envelope (api/response-envelope.md): { data: T[], meta: { request_id, pagination } }
    getNextPageParam: (lastPage) =>
      lastPage.meta.pagination?.has_more ? lastPage.meta.pagination.next_cursor ?? undefined : undefined,
  });
}
```

## Anti-Patterns
- Never `await queryClient.fetchQuery()` in event handlers — use `useMutation`
- Never store server state in `useState` — let TanStack Query own it
- Never disable the cache with `gcTime: 0` unless you have a specific reason
- Don't refetch on window focus for data that changes rarely: `refetchOnWindowFocus: false`
