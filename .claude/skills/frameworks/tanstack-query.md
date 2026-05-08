# TanStack Query v5 patterns for React data fetching.

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
  details: () => [...resourceKeys.all, 'detail'] as const,
  detail: (id: string) => [...resourceKeys.details(), id] as const,
};
```
- Use factory pattern — consistent invalidation
- Keys are arrays — TanStack matches by prefix for invalidation
- `queryClient.invalidateQueries({ queryKey: resourceKeys.all })` invalidates everything

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
      const prev = queryClient.getQueryData(resourceKeys.lists());
      queryClient.setQueryData(resourceKeys.lists(), (old: Resource[]) =>
        old?.filter(r => r.id !== id)
      );
      return { prev };
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(resourceKeys.lists(), context?.prev);
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
    queryKey: resourceKeys.list(filters),
    queryFn: ({ pageParam }) => api.listResources({ ...filters, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.has_more ? lastPage.next_cursor : undefined,
  });
}
```

## Anti-Patterns
- Never `await queryClient.fetchQuery()` in event handlers — use `useMutation`
- Never store server state in `useState` — let TanStack Query own it
- Never disable the cache with `gcTime: 0` unless you have a specific reason
- Don't refetch on window focus for data that changes rarely: `refetchOnWindowFocus: false`
