// HARNESS PROBE: runs ui/api-integration-patterns.md's fetch client and Axios client against MSW, so the
// envelope handling, cursor params, CSRF echo and Idempotency-Key the pack teaches are executed, not just typed.
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { api, ApiError, csrfToken } from "@/lib/api-client";
import { apiClient } from "@/lib/axios-client";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  document.cookie = "csrf_token=; max-age=0; path=/";
});
afterAll(() => server.close());

const user = { id: "u1", name: "Ada", email: "ada@example.com", role: "admin" as const, avatar_url: null, active: true,
  created_at: "2026-09-30T00:00:00Z", updated_at: "2026-09-30T00:00:00Z" };

describe("api-integration-patterns.md — fetcher / api", () => {
  it("unwraps a list envelope and sends cursor + limit, never page/offset", async () => {
    let seen = new URL("http://x/");
    server.use(http.get("/api/v1/users", ({ request }) => {
      seen = new URL(request.url);
      return HttpResponse.json({ data: [user], meta: { request_id: "r1", pagination: { next_cursor: "c2", has_more: true, limit: 20 } } });
    }));
    const page = await api.users.list({ cursor: "c1", limit: 20 });
    expect(page.data).toEqual([user]);
    expect(page.meta.pagination?.next_cursor).toBe("c2");
    expect(Object.fromEntries(seen.searchParams)).toEqual({ cursor: "c1", limit: "20" });
  });

  it("throws ApiError with details[] for a 400 VALIDATION_FAILED envelope", async () => {
    server.use(http.post("/api/v1/users", () => HttpResponse.json({ error: { code: "VALIDATION_FAILED", message: "Some fields are invalid.",
      details: [{ field: "email", code: "invalid_format", message: "Enter a valid email address." }], request_id: "r2", retryable: false } }, { status: 400 })));
    const err = await api.users.create({ input: { name: "Ada", email: "nope", role: "admin" }, idempotencyKey: "k1" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 400, code: "VALIDATION_FAILED", requestId: "r2", retryable: false,
      details: [{ field: "email", code: "invalid_format", message: "Enter a valid email address." }] });
  });

  it("sends the Idempotency-Key and echoes the csrf_token cookie (base64 with '=' padding) in X-CSRF-Token", async () => {
    document.cookie = "csrf_token=dG9rZW4=; path=/";   // base64 of "token=" — '=' padding is common in CSRF tokens
    let headers = new Headers();
    server.use(http.post("/api/v1/users", ({ request }) => {
      headers = request.headers;
      return HttpResponse.json({ data: user, meta: { request_id: "r3" } }, { status: 201 });
    }));
    const created = await api.users.create({ input: { name: "Ada", email: "ada@example.com", role: "admin" }, idempotencyKey: "key-1" });
    expect(created.data.id).toBe("u1");
    expect(csrfToken()).toBe("dG9rZW4=");
    expect(headers.get("x-csrf-token")).toBe("dG9rZW4=");
    expect(headers.get("idempotency-key")).toBe("key-1");
  });

  it("resolves a 204 DELETE without parsing a body", async () => {
    server.use(http.delete("/api/v1/users/:id", () => new HttpResponse(null, { status: 204, headers: { "X-Request-Id": "r4" } })));
    const res = await api.users.delete("u1");
    expect(res.meta.request_id).toBe("r4");
  });
});

describe("api-integration-patterns.md — Axios client", () => {
  it("normalizes the error envelope to ApiError and echoes the CSRF cookie on a same-origin POST", async () => {
    document.cookie = "csrf_token=abc123; path=/";
    let csrf: string | null = null;
    server.use(http.post("/api/v1/things", ({ request }) => {
      csrf = request.headers.get("x-csrf-token");
      return HttpResponse.json({ error: { code: "CONFLICT", message: "Already exists.", request_id: "r5", retryable: false } }, { status: 409 });
    }));
    const err = await apiClient.post("/v1/things", { name: "x" }).catch((e: unknown) => e);
    expect(csrf).toBe("abc123");
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: "CONFLICT", requestId: "r5", details: [] });
  });
});
