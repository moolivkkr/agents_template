// HARNESS PROBE: runs ui/error-handling-patterns.md's submit handler (Idempotency-Key lifecycle + 400 details[]
// mapping) and its optimistic delete with rollback, through the pack's real api client and userQueries, against MSW.
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { delay, http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { api } from "@/lib/api-client";
import { userQueries } from "@/lib/queries/users";
import type { CreateUserRequest, User } from "@/types/api";
import { useCreateUserSubmit } from "@/samples/server-validation";
import { useDeleteUser } from "@/samples/optimistic-delete";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const user = (id: string, name: string): User => ({ id, name, email: `${id}@example.com`, role: "member", avatar_url: null,
  active: true, created_at: "2026-09-30T00:00:00Z", updated_at: "2026-09-30T00:00:00Z" });
const meta = { request_id: "r", pagination: { next_cursor: null, has_more: false, limit: 20 } };
const err = (status: number, code: string, message: string, details?: unknown[]) =>
  HttpResponse.json({ error: { code, message, request_id: "r", retryable: status >= 500, ...(details ? { details } : {}) } }, { status });

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
const freshClient = () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });

describe("error-handling-patterns.md — submit handler", () => {
  it("reuses the Idempotency-Key when a submit is retried, replaces it after a success, maps 400 details[]", async () => {
    const keys: (string | null)[] = [];
    const replies = [
      () => err(503, "UNAVAILABLE", "Try again shortly."),                                  // 1st action, attempt 1
      () => HttpResponse.json({ data: user("u1", "Ada"), meta: { request_id: "r" } }, { status: 201 }), // attempt 2
      () => err(400, "VALIDATION_FAILED", "Some fields are invalid.",                       // 2nd action, attempt 1
        [{ field: "email", code: "already_taken", message: "That email is already registered." }]),
      () => HttpResponse.json({ data: user("u2", "Bo"), meta: { request_id: "r" } }, { status: 201 }),  // attempt 2
    ];
    server.use(http.post("/api/v1/users", ({ request }) => {
      keys.push(request.headers.get("idempotency-key"));
      return replies[keys.length - 1]!();
    }));
    const { result } = renderHook(() => {
      const form = useForm<CreateUserRequest>({ defaultValues: { name: "", email: "", role: "member" } });
      const createUser = useMutation({ mutationFn: api.users.create });
      return { form, ...useCreateUserSubmit(form, createUser) };
    }, { wrapper: wrapper(freshClient()) });

    const ada: CreateUserRequest = { name: "Ada", email: "ada@example.com", role: "member" };
    const bo: CreateUserRequest = { name: "Bo", email: "taken@example.com", role: "member" };
    await act(() => result.current.onSubmit(ada)); // 503
    await act(() => result.current.onSubmit(ada)); // the same action retried → 201
    await act(() => result.current.onSubmit(bo));  // the next action → 400 on email
    expect(result.current.form.getFieldState("email").error?.message).toBe("That email is already registered.");
    await act(() => result.current.onSubmit({ ...bo, email: "bo@example.com" })); // fixed and re-submitted → 201

    expect(keys).toHaveLength(4);
    expect(keys.every((k) => typeof k === "string" && k.length > 0)).toBe(true);
    expect(keys[1]).toBe(keys[0]);    // retry of the same action: same key, the server can de-duplicate
    expect(keys[2]).not.toBe(keys[1]); // a new action after a success: a new key, not a replay of the first user
    expect(keys[3]).toBe(keys[2]);
  });
});

describe("error-handling-patterns.md — optimistic delete with rollback", () => {
  it("removes the user from every cached list at once, and puts it back when the delete fails", async () => {
    let hangReads = false;
    let release: () => void = () => {};
    const failDelete = new Promise<void>((resolve) => { release = resolve; });
    server.use(
      http.get("/api/v1/users", async () => {
        if (hangReads) await delay("infinite"); // the refetch after onSettled never answers: only rollback restores
        return HttpResponse.json({ data: [user("u1", "Ada"), user("u2", "Bo")], meta });
      }),
      http.delete("/api/v1/users/:id", async () => {
        await failDelete;
        return err(500, "INTERNAL", "Something went wrong.");
      }),
    );
    const client = freshClient();
    const lists = renderHook(() => ({
      all: useInfiniteQuery(userQueries.list()),
      admins: useInfiniteQuery(userQueries.list({ role: "admin" })),
    }), { wrapper: wrapper(client) });
    const ids = () => [lists.result.current.all, lists.result.current.admins].map((q) => q.data?.pages.flatMap((p) => p.data.map((u) => u.id)));
    await waitFor(() => expect(ids()).toEqual([["u1", "u2"], ["u1", "u2"]]));

    const del = renderHook(() => useDeleteUser(), { wrapper: wrapper(client) });
    hangReads = true;
    act(() => del.result.current.mutate("u1"));
    await waitFor(() => expect(ids()).toEqual([["u2"], ["u2"]])); // optimistic, in both cached lists
    release(); // the DELETE now fails with 500
    // Rolled back by onError while the onSettled refetch is still hanging, so this is the rollback, not a refetch.
    // (The mutation itself stays pending until that refetch ends: onSettled returns invalidateQueries' promise.)
    await waitFor(() => expect(ids()).toEqual([["u1", "u2"], ["u1", "u2"]]));
  });
});
