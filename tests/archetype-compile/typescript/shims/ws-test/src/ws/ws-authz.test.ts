// HARNESS TEST (not from the archetypes): runs websocket-pattern-typescript.md's ws and Socket.IO servers
// over real sockets and checks the authorization rules — Origin allowlist, single-use tickets, and
// tenant rooms (deny by default; a tenant can neither join nor post to another tenant's room).
import http from "node:http";
import type { AddressInfo } from "node:net";
import pino from "pino";
import WebSocket from "ws";
import { io as ioClient, type Socket as ClientSocket } from "socket.io-client";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { ConnectionManager } from "./manager";
import { createWebSocketServer, type TicketStore } from "./server";
import { createSocketIOServer } from "./socket-io-server";

// The project's JWT verifier (shims/project-auth only declares it): token → claims
vi.mock("../auth/jwt", () => ({
  validateJwt: async (token: string) => {
    const claims: Record<string, { userId: string; tenantId: string; roles: string[] }> = {
      "tok-a": { userId: "u-a", tenantId: "A", roles: [] },
      "tok-b": { userId: "u-b", tenantId: "B", roles: [] },
    };
    const c = claims[token];
    if (!c) throw new Error("invalid token");
    return c;
  },
}));

const ALLOWED = "https://app.example.com";
const FOREIGN = "https://evil.example";
const logger = pino({ level: "silent" });

/** In-memory single-use tickets: redeem() deletes, like Redis GETDEL. */
function ticketStore(): TicketStore & { issue(t: string, tenantId: string, userId: string): void } {
  const m = new Map<string, { userId: string; tenantId: string; roles: string[] }>();
  return {
    issue: (t, tenantId, userId) => void m.set(t, { userId, tenantId, roles: [] }),
    redeem: async (t) => {
      const v = m.get(t) ?? null;
      m.delete(t);
      return v;
    },
  };
}

const listen = (s: http.Server) =>
  new Promise<number>((r) => s.listen(0, "127.0.0.1", () => r((s.address() as AddressInfo).port)));

describe("ws server", () => {
  const server = http.createServer();
  const tickets = ticketStore();
  let port = 0;
  beforeAll(async () => {
    createWebSocketServer(server, new ConnectionManager(logger), tickets, new Set([ALLOWED]), logger);
    port = await listen(server);
  });
  afterAll(() => new Promise<void>((r) => server.close(() => r())));

  function connect(ticket: string, origin?: string): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}/ws?ticket=${ticket}`, origin ? { origin } : {});
      ws.once("open", () => resolve(ws));
      ws.once("unexpected-response", (_req, res) => reject(new Error(`HTTP ${res.statusCode}`)));
      ws.once("error", reject);
    });
  }
  const frames = (ws: WebSocket) => {
    const got: any[] = [];
    ws.on("message", (d) => got.push(JSON.parse(d.toString())));
    return got;
  };
  const send = (ws: WebSocket, msg: object) => ws.send(JSON.stringify(msg));
  const settle = () => new Promise((r) => setTimeout(r, 150));

  it("refuses a foreign Origin (403) and accepts the allowlisted one", async () => {
    tickets.issue("t-evil", "A", "u-a");
    await expect(connect("t-evil", FOREIGN)).rejects.toThrow("HTTP 403");
    tickets.issue("t-ok", "A", "u-a");
    const ws = await connect("t-ok", ALLOWED);
    ws.close();
  });

  it("refuses a missing or reused ticket (401)", async () => {
    await expect(connect("never-issued", ALLOWED)).rejects.toThrow("HTTP 401");
    tickets.issue("t-once", "A", "u-a");
    (await connect("t-once", ALLOWED)).close();
    await expect(connect("t-once", ALLOWED)).rejects.toThrow("HTTP 401");
  });

  it("tenant rooms: no cross-tenant join or post; same-tenant traffic flows", async () => {
    for (const [t, tenant, user] of [["a1", "A", "u-a1"], ["a2", "A", "u-a2"], ["b1", "B", "u-b1"]] as const) {
      tickets.issue(t, tenant, user);
    }
    const [a1, a2, b1] = await Promise.all([connect("a1", ALLOWED), connect("a2", ALLOWED), connect("b1", ALLOWED)]);
    const [ga1, ga2, gb1] = [frames(a1), frames(a2), frames(b1)];

    send(a1, { type: "subscribe", ref: "1", payload: { room: "tenant:B:chat" } }); // another tenant's room
    send(a1, { type: "subscribe", ref: "2", payload: { room: "global" } });        // not a tenant room
    send(a1, { type: "subscribe", ref: "3", payload: { room: "tenant:A:chat" } });  // own tenant
    send(a2, { type: "subscribe", ref: "4", payload: { room: "tenant:A:chat" } });
    send(b1, { type: "subscribe", ref: "5", payload: { room: "tenant:B:chat" } });
    await settle();
    expect(ga1).toContainEqual(expect.objectContaining({ type: "error", ref: "1", code: "FORBIDDEN" }));
    expect(ga1).toContainEqual(expect.objectContaining({ type: "error", ref: "2", code: "FORBIDDEN" }));
    expect(ga1).toContainEqual({ type: "ack", ref: "3" });

    send(a1, { type: "message", ref: "6", payload: { room: "tenant:B:chat", data: "hi B" } }); // post across
    send(a1, { type: "message", ref: "7", payload: { room: "tenant:A:chat", data: "hi A" } });
    await settle();
    expect(ga1).toContainEqual(expect.objectContaining({ type: "error", ref: "6", code: "FORBIDDEN" }));
    expect(gb1.filter((f) => f.type === "message")).toEqual([]); // tenant B received nothing
    expect(ga2).toContainEqual(expect.objectContaining({ type: "message", room: "tenant:A:chat", payload: "hi A" }));
    for (const ws of [a1, a2, b1]) ws.close();
  });
});

describe("Socket.IO server", () => {
  const server = http.createServer();
  let url = "";
  beforeAll(async () => {
    createSocketIOServer(server, new Set([ALLOWED]), logger);
    url = `http://127.0.0.1:${await listen(server)}`;
  });
  afterAll(() => new Promise<void>((r) => server.close(() => r())));

  const connect = (token: string, origin: string): Promise<ClientSocket> =>
    new Promise((resolve, reject) => {
      const s = ioClient(url, { transports: ["websocket"], auth: { token }, extraHeaders: { origin }, reconnection: false });
      s.once("connect", () => resolve(s));
      s.once("connect_error", (e) => {
        s.close();
        reject(e);
      });
    });
  const call = (s: ClientSocket, ev: string, data: object) =>
    new Promise<any>((r) => s.emit(ev, data, (resp: unknown) => r(resp)));

  it("refuses a foreign Origin even over the websocket transport", async () => {
    await expect(connect("tok-a", FOREIGN)).rejects.toThrow();
    (await connect("tok-a", ALLOWED)).close();
  });

  it("tenant rooms: cross-tenant subscribe and post are FORBIDDEN", async () => {
    const [a, b] = await Promise.all([connect("tok-a", ALLOWED), connect("tok-b", ALLOWED)]);
    const seenByB: unknown[] = [];
    b.on("message", (m) => seenByB.push(m));
    expect(await call(b, "subscribe", { room: "tenant:B:chat" })).toEqual({ status: "ok" });
    expect(await call(a, "subscribe", { room: "tenant:B:chat" })).toEqual({ error: "FORBIDDEN" });
    expect(await call(a, "message", { room: "tenant:B:chat", payload: "x" })).toEqual({ error: "FORBIDDEN" });
    expect(await call(a, "message", { room: "user:u-b", payload: "x" })).toEqual({ error: "FORBIDDEN" });
    expect(await call(a, "subscribe", { room: "tenant:A:chat" })).toEqual({ status: "ok" });
    await new Promise((r) => setTimeout(r, 150));
    expect(seenByB).toEqual([]);
    a.close();
    b.close();
  });
});
