---
skill: auth-middleware-typescript
description: TypeScript auth middleware archetype — JWT verification (jsonwebtoken + jose), Express middleware, NestJS Guard, RBAC, rate limiting, CORS, request ID, structured logging
version: "1.0"
tags:
  - typescript
  - middleware
  - auth
  - jwt
  - rbac
  - express
  - nestjs
  - archetype
  - backend
---

# Auth Middleware Archetype — TypeScript

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Express 5.2, NestJS 12.1, jsonwebtoken 9.0, jose 6.2, express-rate-limit 8.7, cors 2.8; the NestJS guard's DI and the Express auth → request-context chain are also run. The request-id module is run too: hostile X-Request-Id values (CR/LF, oversize, non-matching, repeated) are replaced and never echoed, and pino-http, the middleware and the error body share one id; `configureApp()` is run over HTTP: a bad body is 400 VALIDATION_FAILED with details[] (tests/archetype-compile/typescript/run.sh).

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/auth-middleware.md` (Go). Both implement identical auth flows: JWT validation, tenant context injection, RBAC, rate limiting, and request ID propagation.

Complete authentication and authorization middleware for Express and NestJS. Every generated TypeScript auth layer MUST follow this pattern.

---

## Auth Types

```typescript
// src/types/auth.ts

/** Authenticated user context — populated by auth middleware. */
export interface AuthUser {
  id: string;
  tenantId: string;
  roles: string[];
  permissions: string[];
}

/** JWT custom claims — matches Go archetype CustomClaims. */
export interface JwtCustomPayload {
  sub: string;           // user ID
  tenant_id: string;     // tenant ID
  roles: string[];       // role names
  permissions: string[]; // permission strings
  iss: string;           // issuer
  aud: string | string[];// audience
  exp: number;           // expiration (unix timestamp)
  iat: number;           // issued at
}

/** JWT configuration. */
export interface JwtConfig {
  secret: string;        // HMAC secret or RSA public key
  issuer: string;        // expected issuer claim
  audience: string;      // expected audience claim
  algorithms: string[];  // e.g., ["HS256"] or ["RS256"]
}
```

---

## Request ID Middleware — Express

The ONE request-id source. The auth middleware, the error handler and NestJS filter, pino-http's
`genReqId`, the request-context logger and the NestJS `@RequestId()` decorator all read the id through
`requestIdOf()`, so log lines, `meta.request_id`, `error.request_id` and the `X-Request-Id` header carry
the same value — and the validation rule (the same as `core/observability-patterns.md`) exists once.

```typescript
// src/middleware/request-id.ts

import { randomUUID } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Request, Response, NextFunction } from "express";

declare global {
  namespace Express {
    interface Request {
      requestId?: string; // read it with requestIdOf(req)
    }
  }
}

/**
 * An inbound X-Request-Id is reused only when well formed: a bounded charset and length, so it can't
 * inject log lines (CR/LF), bloat every log record, or carry markup into a log viewer.
 */
export const VALID_REQUEST_ID = /^[A-Za-z0-9._-]{8,128}$/;

/** A well-formed inbound id, else a fresh one. A value that fails VALID_REQUEST_ID is never echoed. */
export function resolveRequestId(inbound: unknown): string {
  return typeof inbound === "string" && VALID_REQUEST_ID.test(inbound) ? inbound : `req_${randomUUID()}`;
}

/**
 * The request's id — resolved once per request and cached on it. Takes Express's req or the raw
 * IncomingMessage that pino-http's genReqId receives (the same object); sets X-Request-Id when given res.
 */
export function requestIdOf(req: IncomingMessage, res?: ServerResponse): string {
  const r = req as IncomingMessage & { requestId?: string };
  r.requestId ??= resolveRequestId(req.headers["x-request-id"]); // a repeated header (string[]) is replaced
  if (res && !res.headersSent) res.setHeader("X-Request-Id", r.requestId);
  return r.requestId;
}

/** Express middleware. Mount it FIRST — before CORS, auth, logging and the routes. */
export function requestId(req: Request, res: Response, next: NextFunction): void {
  requestIdOf(req, res);
  next();
}
```

---

## JWT Authentication — Express (using jsonwebtoken)

```typescript
// src/middleware/auth.ts

import type { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import type { JwtConfig, JwtCustomPayload, AuthUser } from "../types/auth";
import { unauthenticated } from "../errors/domain-errors";
import { logger } from "../lib/logger";
import { requestIdOf } from "./request-id";

/**
 * Express middleware that validates the Bearer token and injects AuthUser into req.
 * Mount AFTER requestId and body parser, BEFORE route handlers.
 *
 * Usage:
 *   app.use(authMiddleware(jwtConfig));
 */
export function authMiddleware(config: JwtConfig) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const requestId = requestIdOf(req);

    // 1. Extract token from Authorization header
    const token = extractBearerToken(req);
    if (!token) {
      throw unauthenticated(); // missing or invalid Authorization header
    }

    // 2. Verify and decode token
    let payload: JwtCustomPayload;
    try {
      payload = jwt.verify(token, config.secret, {
        issuer: config.issuer,
        audience: config.audience,
        algorithms: config.algorithms as jwt.Algorithm[],
      }) as JwtCustomPayload;
    } catch (err) {
      logger.warn(
        { request_id: requestId, error: err instanceof Error ? err.message : "unknown" },
        "JWT verification failed", // pino: fields first, message second
      );
      throw unauthenticated(); // invalid or expired token
    }

    // 3. Validate required claims
    if (!payload.sub) {
      throw unauthenticated(); // invalid token: missing subject claim
    }
    if (!payload.tenant_id) {
      throw unauthenticated(); // invalid token: missing tenant_id claim
    }

    // 4. Inject AuthUser into request
    const authUser: AuthUser = {
      id: payload.sub,
      tenantId: payload.tenant_id,
      roles: payload.roles ?? [],
      permissions: payload.permissions ?? [],
    };

    (req as any).userId = authUser.id;
    (req as any).tenantId = authUser.tenantId;
    (req as any).roles = authUser.roles;
    (req as any).user = authUser;

    next();
  };
}

/**
 * Extracts Bearer token from Authorization header.
 * Returns null if header is missing or malformed.
 */
function extractBearerToken(req: Request): string | null {
  const auth = req.headers.authorization;
  if (!auth) return null;

  const parts = auth.split(" ");
  if (parts.length !== 2 || parts[0]?.toLowerCase() !== "bearer") return null;

  return parts[1] ?? null;
}
```

---

## JWT Authentication — Express (using jose, for Edge/Cloudflare Workers)

```typescript
// src/middleware/auth-jose.ts

import type { Request, Response, NextFunction } from "express";
import { jwtVerify, importSPKI, type JWTPayload } from "jose";
import type { JwtConfig, AuthUser } from "../types/auth";
import { unauthenticated } from "../errors/domain-errors";
import { isAppError } from "../errors/app-error";

/**
 * Express auth middleware using `jose` — works in Edge runtimes
 * (Cloudflare Workers, Vercel Edge, Deno) where `jsonwebtoken` is not available.
 *
 * jose is also recommended for RS256/ES256 public key validation.
 */
export function authMiddlewareJose(config: JwtConfig) {
  // Pre-import the key once at startup (not per-request)
  const keyPromise = config.algorithms[0]?.startsWith("RS")
    ? importSPKI(config.secret, config.algorithms[0])
    : Promise.resolve(new TextEncoder().encode(config.secret));

  return async (req: Request, _res: Response, next: NextFunction): Promise<void> => {
    const token = extractBearerToken(req);
    if (!token) {
      throw unauthenticated(); // missing or invalid Authorization header
    }

    try {
      const key = await keyPromise;
      const { payload } = await jwtVerify(token, key, {
        issuer: config.issuer,
        audience: config.audience,
        algorithms: config.algorithms,
      });

      const tenantId = (payload as any).tenant_id as string;
      if (!payload.sub || !tenantId) {
        throw unauthenticated(); // invalid token claims
      }

      const authUser: AuthUser = {
        id: payload.sub,
        tenantId,
        roles: ((payload as any).roles as string[]) ?? [],
        permissions: ((payload as any).permissions as string[]) ?? [],
      };

      (req as any).userId = authUser.id;
      (req as any).tenantId = authUser.tenantId;
      (req as any).roles = authUser.roles;
      (req as any).user = authUser;

      next();
    } catch (err) {
      if (isAppError(err)) throw err;
      throw unauthenticated(); // invalid or expired token
    }
  };
}

function extractBearerToken(req: Request): string | null {
  const auth = req.headers.authorization;
  if (!auth) return null;
  const parts = auth.split(" ");
  if (parts.length !== 2 || parts[0]?.toLowerCase() !== "bearer") return null;
  return parts[1] ?? null;
}
```

---

## NestJS JWT Auth Guard

```typescript
// src/guards/jwt-auth.guard.ts

import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  Logger,
} from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import type { Request } from "express";
import jwt from "jsonwebtoken";
import type { JwtConfig, JwtCustomPayload, AuthUser } from "../types/auth";
import { IS_PUBLIC_KEY } from "../decorators/public.decorator";
import { unauthenticated } from "../errors/domain-errors";
import { requestIdOf } from "../middleware/request-id";

/**
 * DI token for the guard's JwtConfig. JwtConfig is an interface — it doesn't exist at runtime, so Nest
 * can't inject it by type ("Nest can't resolve dependencies of the JwtAuthGuard (?, Reflector)").
 * Provide it once, from env, failing closed (no default secret), e.g. in AppModule:
 *   providers: [{ provide: JWT_CONFIG, useFactory: (): JwtConfig => ({ secret: requiredEnv("JWT_SECRET"), … }) }]
 */
export const JWT_CONFIG = Symbol("JWT_CONFIG");

@Injectable()
export class JwtAuthGuard implements CanActivate {
  private readonly logger = new Logger(JwtAuthGuard.name);

  constructor(
    @Inject(JWT_CONFIG) private readonly jwtConfig: JwtConfig,
    private readonly reflector: Reflector,
  ) {}

  canActivate(context: ExecutionContext): boolean {
    // Check for @Public() decorator — skip auth for public endpoints
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest<Request & { user?: AuthUser }>();
    const auth = request.headers.authorization;

    if (!auth?.startsWith("Bearer ")) {
      throw unauthenticated(); // AppErrorFilter writes the 401 envelope
    }

    const token = auth.slice("Bearer ".length);

    try {
      const payload = jwt.verify(token, this.jwtConfig.secret, {
        issuer: this.jwtConfig.issuer,
        audience: this.jwtConfig.audience,
        algorithms: this.jwtConfig.algorithms as jwt.Algorithm[],
      }) as JwtCustomPayload;

      if (!payload.sub || !payload.tenant_id) {
        throw unauthenticated(); // invalid token claims
      }

      const authUser: AuthUser = {
        id: payload.sub,
        tenantId: payload.tenant_id,
        roles: payload.roles ?? [],
        permissions: payload.permissions ?? [],
      };

      // Attach to request for @CurrentUser() decorator
      request.user = authUser;
      return true;
    } catch (err) {
      // the validated request id — never the raw X-Request-Id header (it can carry CR/LF into the log)
      this.logger.warn(
        `JWT verification failed (${err instanceof Error ? err.name : "unknown"}) request_id=${requestIdOf(request)}`,
      );
      throw unauthenticated(); // invalid or expired token
    }
  }
}
```

## NestJS Public Decorator

```typescript
// src/decorators/public.decorator.ts

import { SetMetadata } from "@nestjs/common";

export const IS_PUBLIC_KEY = "isPublic";

/**
 * Marks a route as public — skips JWT authentication.
 *
 * Usage:
 *   @Public()
 *   @Get("health")
 *   healthCheck() { return { status: "ok" }; }
 */
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);
```

---

## RBAC Middleware — Express

```typescript
// src/middleware/rbac.ts

import type { Request, Response, NextFunction } from "express";
import { forbidden } from "../errors/domain-errors";
import type { AuthUser } from "../types/auth";

/**
 * Express middleware that checks the user has at least one of the specified roles.
 *
 * Usage:
 *   router.post("/admin/settings", requireRole("admin"), settingsHandler);
 *   router.put("/widgets/:id", requireRole("admin", "editor"), updateHandler);
 */
export function requireRole(...requiredRoles: string[]) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const user = (req as any).user as AuthUser | undefined;
    if (!user) {
      throw forbidden(); // no authenticated user on the request
    }

    const hasRole = requiredRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      throw forbidden(); // none of requiredRoles — the role list stays out of the client message
    }

    next();
  };
}

/**
 * Express middleware that checks the user has ALL specified permissions.
 *
 * Usage:
 *   router.put("/users/:id", requirePermission("users:write"), updateUserHandler);
 *   router.delete("/widgets/:id", requirePermission("widgets:delete", "widgets:write"), deleteHandler);
 */
export function requirePermission(...requiredPermissions: string[]) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const user = (req as any).user as AuthUser | undefined;
    if (!user) {
      throw forbidden(); // no authenticated user on the request
    }

    const userPermSet = new Set(user.permissions);
    for (const perm of requiredPermissions) {
      if (!userPermSet.has(perm)) {
        throw forbidden(); // missing perm — never named in the client message
      }
    }

    next();
  };
}
```

---

## RBAC Guard — NestJS

```typescript
// src/guards/roles.guard.ts

import { CanActivate, ExecutionContext, Injectable } from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import { forbidden } from "../errors/domain-errors";
import type { AuthUser } from "../types/auth";

export const ROLES_KEY = "roles";

/**
 * NestJS guard that checks the user has at least one of the specified roles.
 *
 * Usage:
 *   @UseGuards(JwtAuthGuard, RolesGuard)
 *   @Roles("admin", "editor")
 *   @Put(":id")
 *   update() { ... }
 */
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    // No roles required — allow access
    if (!requiredRoles || requiredRoles.length === 0) return true;

    const request = context.switchToHttp().getRequest();
    const user = request.user as AuthUser | undefined;
    if (!user) {
      throw forbidden(); // no authenticated user on the request
    }

    const hasRole = requiredRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      throw forbidden(); // none of requiredRoles — the role list stays out of the client message
    }

    return true;
  }
}

// --- Roles decorator ---

import { SetMetadata } from "@nestjs/common";

/**
 * Sets required roles metadata on a route handler.
 *
 * Usage: @Roles("admin", "editor")
 */
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

---

## Rate Limiting — Express (express-rate-limit)

```typescript
// src/middleware/rate-limit.ts

import rateLimit, { ipKeyGenerator } from "express-rate-limit";
import type { Request } from "express";
import type { AuthUser } from "../types/auth";
import { rateLimited } from "../errors/domain-errors";

/**
 * Per-tenant rate limiter using express-rate-limit.
 * Keys by tenant ID (from auth context) to prevent noisy neighbor abuse.
 * Falls back to IP-based limiting for unauthenticated requests.
 *
 * Usage:
 *   app.use(tenantRateLimit({ windowMs: 60_000, limit: 100 }));
 */
export function tenantRateLimit(opts: { windowMs: number; limit: number }) {
  return rateLimit({
    windowMs: opts.windowMs,
    limit: opts.limit,      // `max` was renamed `limit` in express-rate-limit 7
    standardHeaders: true,  // Return rate limit info in RateLimit-* headers
    legacyHeaders: false,   // Disable X-RateLimit-* headers

    // Key by tenant ID (from auth) or IP (fallback). ipKeyGenerator groups an IPv6 /56, so a
    // client can't dodge the limit by rotating addresses inside its own prefix.
    keyGenerator: (req: Request): string => {
      const user = (req as any).user as AuthUser | undefined;
      return user?.tenantId ?? ipKeyGenerator(req.ip ?? "");
    },

    // 429 RATE_LIMITED goes through the error middleware: envelope, request_id, Retry-After
    handler: (_req, _res, next) => next(rateLimited(Math.ceil(opts.windowMs / 1000))),
  });
}

/**
 * Stricter rate limit for sensitive endpoints (login, password reset, etc.).
 *
 * Usage:
 *   router.post("/auth/login", sensitiveRateLimit(), loginHandler);
 */
export function sensitiveRateLimit() {
  return rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    limit: 10,                 // 10 attempts per window
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: (req: Request): string => ipKeyGenerator(req.ip ?? ""),
    handler: (_req, _res, next) => next(rateLimited(900)),
  });
}
```

---

## CORS Configuration — Express

```typescript
// src/middleware/cors.ts

import cors from "cors";
import type { CorsOptions } from "cors";

export interface CorsConfig {
  allowedOrigins: string[];
  allowCredentials: boolean;
  maxAge: number; // preflight cache duration in seconds
}

/**
 * CORS middleware factory.
 * Mount FIRST in the middleware stack — before auth, before body parser.
 *
 * Usage:
 *   app.use(corsMiddleware({ allowedOrigins: ["https://app.example.com"], ... }));
 */
export function corsMiddleware(config: CorsConfig) {
  const originSet = new Set(config.allowedOrigins);

  const options: CorsOptions = {
    origin: (origin, callback) => {
      // Allow requests with no origin (server-to-server, CLI tools)
      if (!origin) return callback(null, true);

      if (originSet.has(origin) || originSet.has("*")) {
        return callback(null, true);
      }

      callback(new Error(`Origin ${origin} not allowed by CORS`));
    },
    credentials: config.allowCredentials,
    methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: [
      "Content-Type",
      "Authorization",
      "X-Request-ID",
      "X-API-Key",
    ],
    exposedHeaders: [
      "X-Request-ID",
      "X-RateLimit-Limit",
      "X-RateLimit-Remaining",
      "Retry-After",
    ],
    maxAge: config.maxAge,
  };

  return cors(options);
}
```

---

## Request Logger Enrichment — Express

```typescript
// src/middleware/log-enrichment.ts

import type { Request, Response, NextFunction } from "express";
import { logger } from "../lib/logger";
import { requestIdOf } from "./request-id";

/**
 * Logs request start/finish with timing and attaches enriched logger to request.
 * Mount AFTER requestId and auth.
 */
export function logEnrichment(req: Request, res: Response, next: NextFunction): void {
  const start = Date.now();
  const requestId = requestIdOf(req);
  const userId = (req as any).userId ?? "";
  const tenantId = (req as any).tenantId ?? "";

  // Log request start
  logger.info(
    {
      request_id: requestId,
      method: req.method,
      path: req.path,
      user_id: userId,
      tenant_id: tenantId,
      user_agent: req.headers["user-agent"],
      remote_addr: req.ip,
    },
    "request started", // pino: fields first, message second
  );

  // Log response on finish
  res.on("finish", () => {
    const duration = Date.now() - start;
    logger.info(
      {
        request_id: requestId,
        method: req.method,
        path: req.path,
        status: res.statusCode,
        duration_ms: duration,
        user_id: userId,
        tenant_id: tenantId,
      },
      "request completed",
    );
  });

  next();
}
```

---

## Middleware Stack Assembly — Express

```typescript
// src/middleware/setup.ts

import express, { type Application } from "express";
import { corsMiddleware, type CorsConfig } from "./cors";
import { requestId } from "./request-id";
import { authMiddleware } from "./auth";
import { tenantRateLimit } from "./rate-limit";
import { logEnrichment } from "./log-enrichment";
import { errorHandler } from "./error-handler";
import type { JwtConfig } from "../types/auth";

interface MiddlewareConfig {
  cors: CorsConfig;
  jwt: JwtConfig;
  rateLimit: { windowMs: number; limit: number };
}

/**
 * Assembles the full middleware stack in correct order.
 * Order matters: outermost middleware runs first.
 *
 *   1. Request ID   — first: even a CORS rejection carries the id
 *   2. CORS         — before auth, to handle preflight
 *   3. Body parser  — with size limit to prevent abuse
 *   4. Auth         — JWT validation, sets tenant/user context
 *   5. Rate limit   — per-tenant, after auth so we know the tenant
 *   6. Log enrich   — after auth so we have user/tenant context
 *   ... routes ...
 *   7. Error handler — MUST be last
 */
export function setupMiddleware(app: Application, config: MiddlewareConfig): void {
  // 1. Request ID (the one source: ./request-id)
  app.use(requestId);

  // 2. CORS
  app.use(corsMiddleware(config.cors));

  // 3. Body parser with size limit
  app.use(express.json({ limit: "1mb" }));

  // 4. Auth
  app.use(authMiddleware(config.jwt));

  // 5. Rate limiting (per-tenant)
  app.use(tenantRateLimit(config.rateLimit));

  // 6. Log enrichment
  app.use(logEnrichment);
}

/**
 * Mount error handler AFTER all routes.
 *
 *   setupMiddleware(app, config);
 *   app.use("/api/v1/widgets", widgetRouter);
 *   setupErrorHandler(app);
 */
export function setupErrorHandler(app: Application): void {
  app.use(errorHandler);
}
```

---

## Middleware Stack Assembly — NestJS

`configureApp()` is the one place the NestJS app is configured. `main.ts` calls it, and so does every
e2e/controller test (`crud-handler-test-typescript.md`), so tests run the production request id, body
limit, CORS, `ValidationPipe` and error filter — not a hand-built copy.

```typescript
// src/app.setup.ts

import type { NestExpressApplication } from "@nestjs/platform-express";
import { AppErrorFilter, appValidationPipe } from "./filters/app-error.filter";
import { requestId } from "./middleware/request-id";

export function configureApp(app: NestExpressApplication): void {
  // 1. Request ID — first, so every log line, envelope and X-Request-Id header carry the same validated id
  app.use(requestId);

  // 2. CORS — an explicit allowlist from config; none configured means no cross-origin access
  app.enableCors({
    origin: process.env.ALLOWED_ORIGINS?.split(",") ?? [],
    credentials: true,
    methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization", "X-Request-Id"],
    exposedHeaders: ["X-Request-Id", "Retry-After"],
    maxAge: 86400,
  });

  // 3. Body size limit — replaces Nest's default JSON parser (100 KB). Parser errors (malformed JSON, over the
  //    limit) reach AppErrorFilter too: its toAppError() maps them to 400 MALFORMED_REQUEST in the envelope
  app.useBodyParser("json", { limit: "1mb" });

  // 4. Global validation pipe — class-validator failures are 400 VALIDATION_FAILED with details[] in the
  //    envelope (exceptionFactory), never Nest's default { statusCode, message, error } body
  app.useGlobalPipes(appValidationPipe());

  // 5. Global error filter — every exception from guards, pipes and handlers becomes the error envelope
  app.useGlobalFilters(new AppErrorFilter());
}
```

```typescript
// src/main.ts — NestJS bootstrap

import { NestFactory } from "@nestjs/core";
import type { NestExpressApplication } from "@nestjs/platform-express";
import { AppModule } from "./app.module";
import { configureApp } from "./app.setup";

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  configureApp(app);
  await app.listen(process.env.PORT ?? 3000);
}

void bootstrap();
```

---

## API Key Authentication — Express (Alternative to JWT)

```typescript
// src/middleware/api-key-auth.ts

import { timingSafeEqual } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import type { AuthUser } from "../types/auth";
import { unauthenticated } from "../errors/domain-errors";

export interface ApiKeyIdentity {
  tenantId: string;
  userId: string;
  roles: string[];
  permissions: string[];
}

export interface ApiKeyConfig {
  /**
   * Resolves an API key to identity.
   * In production, this queries a hashed key store (bcrypt/argon2).
   * NEVER store API keys in plaintext.
   */
  lookupFn: (key: string) => Promise<ApiKeyIdentity | null>;
}

/**
 * API key authentication middleware.
 * Reads key from X-API-Key header.
 *
 * Usage:
 *   router.use(apiKeyAuth({ lookupFn: keyStore.lookup }));
 */
export function apiKeyAuth(config: ApiKeyConfig) {
  return async (req: Request, _res: Response, next: NextFunction): Promise<void> => {
    const apiKey = req.headers["x-api-key"] as string | undefined;
    if (!apiKey) {
      throw unauthenticated(); // missing X-API-Key header
    }

    const identity = await config.lookupFn(apiKey);
    if (!identity) {
      throw unauthenticated(); // invalid API key
    }

    const authUser: AuthUser = {
      id: identity.userId,
      tenantId: identity.tenantId,
      roles: identity.roles,
      permissions: identity.permissions,
    };

    (req as any).userId = authUser.id;
    (req as any).tenantId = authUser.tenantId;
    (req as any).roles = authUser.roles;
    (req as any).user = authUser;

    next();
  };
}

/**
 * Timing-safe comparison for API key validation.
 * Prevents timing attacks when comparing keys in the lookup function.
 */
export function safeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
```

---

## Critical Rules

- JWT validation MUST check signature, expiration, issuer, AND audience — never skip any
- Tenant ID MUST come from the validated token, NEVER from request params or body
- API keys MUST be stored as hashes (bcrypt/argon2) — never compare plaintext
- Use `timingSafeEqual` (Node.js `crypto`) for any secret comparison to prevent timing attacks
- Rate limiters MUST be per-tenant — shared limits allow noisy neighbor abuse
- CORS MUST NOT use wildcard `*` with `credentials: true` — browsers reject this combination
- Request ID MUST be set on response headers for client-side correlation
- Auth middleware MUST populate `req.user` with typed `AuthUser` — not raw JWT payload
- Middleware order matters: CORS -> RequestID -> BodyParser -> Auth -> RateLimit -> LogEnrichment
- RBAC checks (requireRole, requirePermission) are applied per-route, not globally
- Never log JWT tokens, API keys, or credentials — log only derived identifiers (userId, tenantId)
- Context helpers MUST throw typed errors when values are missing — never return `undefined` silently
- Use `jose` instead of `jsonwebtoken` for Edge/Worker runtimes where Node.js `crypto` is unavailable
- The `@Public()` decorator (NestJS) or route-level opt-out is the ONLY way to skip auth — never disable the global guard
- Rate limit responses MUST include `Retry-After` header and match the error envelope format
- 401 responses MUST include `WWW-Authenticate: Bearer` header (handled by error middleware from `error-handling-typescript.md`)
