// HARNESS PROBE (not from the archetypes): builds a Nest app with the archetype's OWN configureApp()
// (auth-middleware-typescript.md, src/app.setup.ts) — the setup main.ts runs — and drives it over HTTP. The
// probe controller has no pipe of its own, so whatever validates its archetype DTO (CreateWidgetDto) comes from
// configureApp(). Compiled with decorator metadata (class-validator/Nest read it at runtime) and RUN.
import "reflect-metadata";
import { Body, Controller, Post } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import type { NestExpressApplication } from "@nestjs/platform-express";
import request from "supertest";
import { configureApp } from "./app.setup";
import { CreateWidgetDto } from "./modules/widget/dto/widget.dto";

@Controller("probe")
class ProbeController {
  @Post()
  create(@Body() dto: CreateWidgetDto) {
    return { name: dto.name };
  }
}

const failures: string[] = [];
function check(ok: boolean, what: string, got: unknown): void {
  if (!ok) failures.push(`${what} — got ${JSON.stringify(got)}`);
}
const GENERATED = /^req_[0-9a-f-]{36}$/;

/** The error envelope (api/response-envelope.md): error only, request_id = X-Request-Id, retryable present. */
function checkEnvelope(res: request.Response, status: number, code: string, label: string): void {
  check(res.status === status, `${label}: status ${status}`, res.status);
  check(JSON.stringify(Object.keys(res.body ?? {})) === '["error"]', `${label}: body has only "error"`, res.body);
  check(res.body?.error?.code === code, `${label}: error.code ${code}`, res.body?.error?.code);
  check(typeof res.body?.error?.message === "string", `${label}: error.message`, res.body?.error);
  check(res.body?.error?.retryable === false, `${label}: error.retryable false`, res.body?.error?.retryable);
  check(
    typeof res.body?.error?.request_id === "string" && res.body.error.request_id === res.headers["x-request-id"],
    `${label}: error.request_id = X-Request-Id header`,
    [res.body?.error?.request_id, res.headers["x-request-id"]],
  );
}

async function main(): Promise<void> {
  const moduleRef = await Test.createTestingModule({ controllers: [ProbeController] }).compile();
  const app = moduleRef.createNestApplication<NestExpressApplication>({ logger: false });
  configureApp(app);
  await app.init();
  const server = app.getHttpServer();

  // 1. An invalid body: 400 VALIDATION_FAILED in the envelope, details[] per field (not Nest's own body)
  const bad = await request(server).post("/probe").set("X-Request-Id", "probe-request-0001").send({ name: "" });
  checkEnvelope(bad, 400, "VALIDATION_FAILED", "empty name");
  const details = bad.body?.error?.details as { field: string; code: string; message: string }[] | undefined;
  check(Array.isArray(details) && details.length > 0, "empty name: details[] present", details);
  check(
    (details ?? []).every((d) => typeof d.field === "string" && typeof d.code === "string" && typeof d.message === "string"),
    "empty name: every detail is {field, code, message}",
    details,
  );
  check((details ?? []).some((d) => d.field === "name" && d.code === "required"), 'empty name: {field:"name", code:"required"}', details);
  check(!JSON.stringify(bad.body).includes("name is required"), "empty name: the validator's own message is not sent", bad.body);
  check(bad.headers["x-request-id"] === "probe-request-0001", "a well-formed X-Request-Id is kept", bad.headers["x-request-id"]);

  // 2. An unknown field: rejected (forbidNonWhitelisted), not silently dropped
  const extra = await request(server).post("/probe").send({ name: "ok", isAdmin: true });
  checkEnvelope(extra, 400, "VALIDATION_FAILED", "unknown field");
  check(
    (extra.body?.error?.details ?? []).some((d: { field: string; code: string }) => d.field === "isAdmin" && d.code === "unknown_field"),
    'unknown field: {field:"isAdmin", code:"unknown_field"}',
    extra.body?.error?.details,
  );

  // 3. A valid body passes the pipe (trimmed by the DTO's @Transform)
  const good = await request(server).post("/probe").send({ name: "  Widget  " });
  check(good.status === 201 && good.body?.name === "Widget", "valid body: 201 and the transformed DTO", [good.status, good.body]);

  // 4. Malformed JSON and an oversize body: parser errors, before any Nest filter — still the envelope
  const malformed = await request(server).post("/probe").set("Content-Type", "application/json").send('{"name": ');
  checkEnvelope(malformed, 400, "MALFORMED_REQUEST", "malformed JSON");
  // 500 KB is under configureApp()'s 1 MB limit (Nest's default parser stops at 100 KB): it reaches the pipe,
  // which rejects the 255-character name rule — VALIDATION_FAILED, not MALFORMED_REQUEST
  const mid = await request(server).post("/probe").send({ name: "x".repeat(500 * 1024) });
  checkEnvelope(mid, 400, "VALIDATION_FAILED", "500 KB body (under the 1 MB limit)");

  // 5. Hostile request ids are replaced, not echoed (oversize, non-matching charset, too short)
  for (const hostile of ["x".repeat(129), "<script>alert(1)</script>", "abc"]) {
    const r = await request(server).post("/probe").set("X-Request-Id", hostile).send({ name: "" });
    const id = r.headers["x-request-id"];
    check(id !== hostile && GENERATED.test(String(id)), `hostile id ${JSON.stringify(hostile.slice(0, 20))} replaced`, id);
    check(r.body?.error?.request_id === id, `hostile id ${JSON.stringify(hostile.slice(0, 20))}: body uses the replacement`, r.body?.error);
  }

  // 6. Last, on its own connection: the server answers an over-limit body before reading all of it, so that
  //    connection can't be reused by a following request
  const big = await request(server).post("/probe").set("Connection", "close").send({ name: "x".repeat(2 * 1024 * 1024) });
  checkEnvelope(big, 400, "MALFORMED_REQUEST", "2 MB body (over the 1 MB limit)");

  await app.close();
  if (failures.length > 0) {
    console.error(`Nest validation FAILED (${failures.length}):\n  - ${failures.join("\n  - ")}`);
    process.exit(1);
  }
  console.log("Nest configureApp(): bad body → 400 VALIDATION_FAILED + details[]; unknown field, malformed JSON, 2 MB body and hostile request ids → envelope (all checks passed)");
}

main().catch((e: unknown) => {
  console.error("Nest validation probe crashed:", e instanceof Error ? e.stack : e);
  process.exit(1);
});
