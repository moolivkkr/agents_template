// HARNESS PROBE: runs ui/advanced-state-patterns.md's offline mutation queue against a real IndexedDB
// implementation (fake-indexeddb, which models transaction auto-commit) and MSW, through the pack's fetcher.
import "fake-indexeddb/auto";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { delay, http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { flushMutationQueue, queueMutation } from "@/lib/offline-queue";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const created = (name: string) =>
  HttpResponse.json({ data: { id: name, name, status: "active", created_at: "", updated_at: "" }, meta: { request_id: "r" } }, { status: 201 });

describe("advanced-state-patterns.md — offline mutation queue", () => {
  it("replays each queued mutation once, with its own Idempotency-Key, and empties the queue", async () => {
    const seen: { key: string | null; body: unknown }[] = [];
    server.use(http.post("/api/v1/items", async ({ request }) => {
      const body = (await request.json()) as { name: string };
      await delay(20); // real network latency: an IndexedDB transaction commits while the request is in flight
      seen.push({ key: request.headers.get("idempotency-key"), body });
      return created(body.name);
    }));
    await queueMutation({ endpoint: "/v1/items", method: "POST", body: { name: "a" } });
    await queueMutation({ endpoint: "/v1/items", method: "POST", body: { name: "b" } });
    await flushMutationQueue();
    expect(seen.map((s) => s.body)).toEqual([{ name: "a" }, { name: "b" }]);
    expect(new Set(seen.map((s) => s.key)).size).toBe(2);
    expect(seen.every((s) => typeof s.key === "string" && s.key.length > 0)).toBe(true);
    await flushMutationQueue(); // the queue is empty now: nothing is sent twice
    expect(seen).toHaveLength(2);
  });

  it("keeps the queue on a retryable 503 and on a network error, drops what the server rejects with a 400", async () => {
    let mode: "503" | "network" | "400" | "ok" = "503";
    let sent = 0;
    server.use(http.post("/api/v1/items", async ({ request }) => {
      sent++;
      const body = (await request.json()) as { name: string };
      await delay(20); // real network latency: an IndexedDB transaction commits while the request is in flight
      if (mode === "503") return HttpResponse.json({ error: { code: "UNAVAILABLE", message: "Try again shortly.", request_id: "r", retryable: true } }, { status: 503 });
      if (mode === "network") return HttpResponse.error();
      if (mode === "400") return HttpResponse.json({ error: { code: "VALIDATION_FAILED", message: "Invalid.", details: [], request_id: "r", retryable: false } }, { status: 400 });
      return created(body.name);
    }));
    await queueMutation({ endpoint: "/v1/items", method: "POST", body: { name: "c" } });
    await flushMutationQueue();          // 503: kept
    mode = "network";
    await flushMutationQueue();          // fetch throws: kept
    mode = "400";
    await flushMutationQueue();          // rejected: dropped
    mode = "ok";
    await flushMutationQueue();          // nothing left to send
    expect(sent).toBe(3);
  });
});
