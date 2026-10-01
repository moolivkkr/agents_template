// HARNESS STUB (app-level): a project's query-options factory for "resources", built the way
// ui/api-integration-patterns.md builds userQueries: a list is a cursor-paginated infinite query whose pages
// are the envelope ({ data: Resource[], meta: { request_id, pagination } }), through the pack's real fetcher.
import { infiniteQueryOptions } from "@tanstack/react-query";
import { fetcher } from "@/lib/api-client";
import type { Resource } from "@/types/api";

export const resourceQueries = {
  list: () =>
    infiniteQueryOptions({
      queryKey: ["resources", "list"] as const,
      queryFn: ({ pageParam }) =>
        fetcher<Resource[]>(`/v1/resources${pageParam ? `?cursor=${encodeURIComponent(pageParam)}` : ""}`),
      initialPageParam: undefined as string | undefined,
      getNextPageParam: (last) => (last.meta.pagination?.has_more ? (last.meta.pagination.next_cursor ?? undefined) : undefined),
    }),
};
