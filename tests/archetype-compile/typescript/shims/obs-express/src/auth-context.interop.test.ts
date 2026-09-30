// HARNESS TEST (not from the archetypes): auth-middleware-typescript.md's authMiddleware sets req.user;
// observability-typescript.md's requestContextMiddleware must read the tenant from exactly there. Runs the
// real middleware from both docs plus error-handling-typescript.md's errorHandler.
import express from "express";
import jwt from "jsonwebtoken";
import request from "supertest";
import { expect, it } from "vitest";
import { authMiddleware } from "./middleware/auth";
import { errorHandler } from "./middleware/error-handler";
import { requestContextMiddleware } from "./middleware/request-context.middleware";
import type { JwtConfig } from "./types/auth";

const cfg: JwtConfig = { secret: "interop-test-only", issuer: "https://issuer.test", audience: "api", algorithms: ["HS256"] };

const app = express()
  .use(authMiddleware(cfg))
  .use(requestContextMiddleware)
  .get("/whoami", (req, res) => {
    res.json({ tenant: req.tenantId, user: req.userId, hasChildLogger: typeof req.log?.info === "function" });
  })
  .use(errorHandler);

it("the tenant flows from the verified token (req.user) to req.tenantId and the child logger", async () => {
  const token = jwt.sign({ sub: "u-1", tenant_id: "t-1", roles: ["member"], permissions: [] }, cfg.secret, {
    issuer: cfg.issuer,
    audience: cfg.audience,
    algorithm: "HS256",
    expiresIn: 60,
  });
  const res = await request(app).get("/whoami").set("Authorization", `Bearer ${token}`).expect(200);
  expect(res.body).toEqual({ tenant: "t-1", user: "u-1", hasChildLogger: true });
});

it("no token → 401 UNAUTHENTICATED in the one error envelope", async () => {
  const res = await request(app).get("/whoami").expect(401);
  expect(res.body.error).toMatchObject({ code: "UNAUTHENTICATED", retryable: false });
  expect(res.headers["www-authenticate"]).toBe("Bearer");
});

it("a client-sent X-Tenant-ID is ignored — the token's tenant wins", async () => {
  const token = jwt.sign({ sub: "u-2", tenant_id: "t-2" }, cfg.secret, {
    issuer: cfg.issuer, audience: cfg.audience, algorithm: "HS256", expiresIn: 60,
  });
  const res = await request(app).get("/whoami").set("Authorization", `Bearer ${token}`).set("X-Tenant-ID", "t-evil").expect(200);
  expect(res.body.tenant).toBe("t-2");
});
