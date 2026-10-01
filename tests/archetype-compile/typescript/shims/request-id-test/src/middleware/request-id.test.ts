// HARNESS TEST (not from the archetypes): the ONE request-id source (auth-middleware-typescript.md
// §Request ID) never echoes a hostile X-Request-Id, and every consumer — the request-id middleware, pino-http's
// genReqId (observability-typescript.md) and the error handler (error-handling-typescript.md) — sees one id.
import type { IncomingMessage } from "node:http";
import express from "express";
import request from "supertest";
import { describe, expect, it } from "vitest";
import { notFound } from "../errors/domain-errors";
import { errorHandler } from "./error-handler";
import { httpLogger } from "./logging.middleware";
import { requestId, requestIdOf, resolveRequestId, VALID_REQUEST_ID } from "./request-id";

const GENERATED = /^req_[0-9a-f-]{36}$/;
const HOSTILE: [string, unknown][] = [
  ["newline (log injection)", "abcdefgh\nlevel=error msg=forged"],
  ["CRLF", "abcdefgh\r\nX-Injected: 1"],
  ["oversize (129 chars)", "a".repeat(129)],
  ["too short", "abc"],
  ["markup", "<script>alert(1)</script>"],
  ["spaces", "my request id"],
  ["repeated header (string[])", ["valid-id-0001", "valid-id-0002"]],
  ["empty", ""],
];

describe("resolveRequestId / requestIdOf", () => {
  it.each(HOSTILE)("replaces a hostile id: %s", (_label, hostile) => {
    const id = resolveRequestId(hostile);
    expect(id).not.toEqual(hostile);
    expect(id).toMatch(GENERATED);
    expect(id).toMatch(VALID_REQUEST_ID);
  });

  it("keeps a well-formed id", () => {
    expect(resolveRequestId("client-req.0001_abc")).toBe("client-req.0001_abc");
    expect(resolveRequestId("a".repeat(128))).toBe("a".repeat(128));
  });

  it("resolves once per request, even from a raw IncomingMessage with a CR/LF header", () => {
    // Node's HTTP client refuses to SEND CR/LF in a header, so this one is checked on a raw request object
    const req = { headers: { "x-request-id": "abcdefgh\r\nforged: yes" } } as unknown as IncomingMessage;
    const first = requestIdOf(req);
    expect(first).toMatch(GENERATED);
    expect(requestIdOf(req)).toBe(first); // cached: the log line and the error body agree
  });
});

describe("one id across middleware, pino-http and the error handler", () => {
  const app = express();
  app.use(httpLogger); // genReqId = requestIdOf
  app.use(requestId);
  app.get("/ok", (req, res) => {
    res.json({ data: { pino_req_id: req.id, request_id: requestIdOf(req) }, meta: { request_id: requestIdOf(req) } });
  });
  app.get("/missing", () => {
    throw notFound("Widget");
  });
  app.use(errorHandler);

  it.each([
    ["oversize", "b".repeat(200)],
    ["markup", "<img src=x onerror=alert(1)>"],
    ["too short", "x1"],
  ])("a hostile X-Request-Id (%s) is replaced in the header and the error body", async (_label, hostile) => {
    const res = await request(app).get("/missing").set("X-Request-Id", hostile);
    expect(res.status).toBe(404);
    expect(res.headers["x-request-id"]).not.toBe(hostile);
    expect(res.headers["x-request-id"]).toMatch(GENERATED);
    expect(res.body.error.request_id).toBe(res.headers["x-request-id"]);
    expect(JSON.stringify(res.body)).not.toContain(hostile);
  });

  it("a well-formed X-Request-Id is echoed, and pino-http's req.id is the same id", async () => {
    const res = await request(app).get("/ok").set("X-Request-Id", "client-req-0001");
    expect(res.headers["x-request-id"]).toBe("client-req-0001");
    expect(res.body.data).toEqual({ pino_req_id: "client-req-0001", request_id: "client-req-0001" });
    expect(res.body.meta.request_id).toBe("client-req-0001");
  });

  it("without an X-Request-Id, one generated id is used everywhere", async () => {
    const res = await request(app).get("/ok");
    const id = res.headers["x-request-id"];
    expect(id).toMatch(GENERATED);
    expect(res.body.data).toEqual({ pino_req_id: id, request_id: id });
  });
});
