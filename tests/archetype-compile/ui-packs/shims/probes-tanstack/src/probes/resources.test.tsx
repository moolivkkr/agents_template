// HARNESS PROBE: runs frameworks/tanstack-query.md's hooks against MSW: the optimistic delete must change what
// a mounted list renders, and the list + infinite-list hooks must be usable side by side.
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useDeleteResource, useResources, useResourcesInfinite } from "@/lib/queries/resources";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const list = HttpResponse.json({
  data: [{ id: "r1", name: "One", status: "active" }, { id: "r2", name: "Two", status: "active" }],
  meta: { request_id: "r", pagination: { next_cursor: null, has_more: false, limit: 20 } },
});

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}

describe("tanstack-query.md — hooks", () => {
  it("useDeleteResource removes the row from the mounted list before the server answers", async () => {
    let release: () => void = () => {};
    const pending = new Promise<void>((resolve) => { release = resolve; });
    server.use(
      http.get("/api/v1/resources", () => list.clone()),
      http.delete("/api/v1/resources/:id", async () => {
        await pending;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { wrapper } = setup();
    const rows = renderHook(() => useResources({}), { wrapper });
    await waitFor(() => expect(rows.result.current.data?.data.map((r) => r.id)).toEqual(["r1", "r2"]));
    const del = renderHook(() => useDeleteResource(), { wrapper });
    act(() => del.result.current.mutate("r1"));
    await waitFor(() => expect(rows.result.current.data?.data.map((r) => r.id)).toEqual(["r2"]));
    release();
    await waitFor(() => expect(del.result.current.isSuccess).toBe(true));
  });

  it("useResources and useResourcesInfinite with the same filters each get their own data shape", async () => {
    server.use(http.get("/api/v1/resources", () => list.clone()));
    const { wrapper } = setup();
    const both = renderHook(() => ({ page: useResources({}), pages: useResourcesInfinite({}) }), { wrapper });
    await waitFor(() => {
      expect(both.result.current.page.data?.data).toHaveLength(2);
      expect(both.result.current.pages.data?.pages[0]?.data).toHaveLength(2);
    });
  });
});
