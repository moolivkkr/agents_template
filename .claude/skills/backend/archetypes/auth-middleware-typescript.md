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

```typescript
// src/middleware/request-id.ts

import { randomUUID } from "node:crypto";
import type { Request, Response, NextFunction } from "express";

 * Generates or extracts a unique request ID for tracing.
 * Checks X-Request-ID header first (client correlation), generates UUID if absent.
 * Sets the ID on the response header for client-side correlation.
 * Mount EARLY in the middleware stack — before auth and logging.
export function requestId(req: Request, res: Response, next: NextFunction): void {
  const id = (req.headers["x-request-id"] as string) || randomUUID();

  // Attach to request for downstream access
  (req as any).requestId = id;

  // Set on response for client correlation
  res.setHeader("X-Request-ID", id);

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
import { UnauthorizedError } from "../errors/domain-errors";
import { logger } from "../lib/logger";

 * Express middleware that validates the Bearer token and injects AuthUser into req.
 * Mount AFTER requestId and body parser, BEFORE route handlers.
 * Usage:
 *   app.use(authMiddleware(jwtConfig));
export function authMiddleware(config: JwtConfig) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const requestId = (req as any).requestId ?? "";

    // 1. Extract token from Authorization header
    const token = extractBearerToken(req);
    if (!token) {
      throw new UnauthorizedError("missing or invalid Authorization header");
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
      logger.warn("JWT verification failed", {
        request_id: requestId,
        error: err instanceof Error ? err.message : "unknown",
      });
      throw new UnauthorizedError("invalid or expired token");
    }

    // 3. Validate required claims
    if (!payload.sub) {
      throw new UnauthorizedError("invalid token: missing subject claim");
    }
    if (!payload.tenant_id) {
      throw new UnauthorizedError("invalid token: missing tenant_id claim");
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

 * Extracts Bearer token from Authorization header.
 * Returns null if header is missing or malformed.
function extractBearerToken(req: Request): string | null {
  const auth = req.headers.authorization;
  if (!auth) return null;

  const parts = auth.split(" ");
  if (parts.length !== 2 || parts[0].toLowerCase() !== "bearer") return null;

  return parts[1];
}
```

---

## JWT Authentication — Express (using jose, for Edge/Cloudflare Workers)

```typescript
// src/middleware/auth-jose.ts

import type { Request, Response, NextFunction } from "express";
import { jwtVerify, importSPKI, type JWTPayload } from "jose";
import type { JwtConfig, AuthUser } from "../types/auth";
import { UnauthorizedError } from "../errors/domain-errors";

 * Express auth middleware using `jose` — works in Edge runtimes
 * (Cloudflare Workers, Vercel Edge, Deno) where `jsonwebtoken` is not available.
 * jose is also recommended for RS256/ES256 public key validation.
export function authMiddlewareJose(config: JwtConfig) {
  // Pre-import the key once at startup (not per-request)
  const keyPromise = config.algorithms[0]?.startsWith("RS")
    ? importSPKI(config.secret, config.algorithms[0])
    : Promise.resolve(new TextEncoder().encode(config.secret));

  return async (req: Request, _res: Response, next: NextFunction): Promise<void> => {
    const token = extractBearerToken(req);
    if (!token) {
      throw new UnauthorizedError("missing or invalid Authorization header");
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
        throw new UnauthorizedError("invalid token claims");
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
      if (err instanceof UnauthorizedError) throw err;
      throw new UnauthorizedError("invalid or expired token");
    }
  };
}

function extractBearerToken(req: Request): string | null {
  const auth = req.headers.authorization;
  if (!auth) return null;
  const parts = auth.split(" ");
  if (parts.length !== 2 || parts[0].toLowerCase() !== "bearer") return null;
  return parts[1];
}
```

---

## NestJS JWT Auth Guard

```typescript
// src/guards/jwt-auth.guard.ts

import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
  Logger,
} from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import jwt from "jsonwebtoken";
import type { JwtConfig, JwtCustomPayload, AuthUser } from "../types/auth";
import { IS_PUBLIC_KEY } from "../decorators/public.decorator";

@Injectable()
export class JwtAuthGuard implements CanActivate {
  private readonly logger = new Logger(JwtAuthGuard.name);

  constructor(
    private readonly jwtConfig: JwtConfig,
    private readonly reflector: Reflector,
  ) {}

  canActivate(context: ExecutionContext): boolean {
    // Check for @Public() decorator — skip auth for public endpoints
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest();
    const auth = request.headers.authorization;

    if (!auth?.startsWith("Bearer ")) {
      throw new UnauthorizedException("missing Authorization header");
    }

    const token = auth.split(" ")[1];

    try {
      const payload = jwt.verify(token, this.jwtConfig.secret, {
        issuer: this.jwtConfig.issuer,
        audience: this.jwtConfig.audience,
        algorithms: this.jwtConfig.algorithms as jwt.Algorithm[],
      }) as JwtCustomPayload;

      if (!payload.sub || !payload.tenant_id) {
        throw new UnauthorizedException("invalid token claims");
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
      this.logger.warn("JWT verification failed", {
        error: err instanceof Error ? err.message : "unknown",
        request_id: request.headers["x-request-id"],
      });
      throw new UnauthorizedException("invalid or expired token");
    }
  }
}
```

## NestJS Public Decorator

```typescript
// src/decorators/public.decorator.ts

import { SetMetadata } from "@nestjs/common";

export const IS_PUBLIC_KEY = "isPublic";

 * Marks a route as public — skips JWT authentication.
 * Usage:
 *   @Public()
 *   @Get("health")
 *   healthCheck() { return { status: "ok" }; }
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);
```

---

## RBAC Middleware — Express

```typescript
// src/middleware/rbac.ts

import type { Request, Response, NextFunction } from "express";
import { ForbiddenError } from "../errors/domain-errors";
import type { AuthUser } from "../types/auth";

 * Express middleware that checks the user has at least one of the specified roles.
 * Usage:
 *   router.post("/admin/settings", requireRole("admin"), settingsHandler);
 *   router.put("/widgets/:id", requireRole("admin", "editor"), updateHandler);
export function requireRole(...requiredRoles: string[]) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const user = (req as any).user as AuthUser | undefined;
    if (!user) {
      throw new ForbiddenError("access", "resource");
    }

    const hasRole = requiredRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      throw new ForbiddenError(
        `requires one of roles: ${requiredRoles.join(", ")}`,
        "resource",
      );
    }

    next();
  };
}

 * Express middleware that checks the user has ALL specified permissions.
 * Usage:
 *   router.put("/users/:id", requirePermission("users:write"), updateUserHandler);
 *   router.delete("/widgets/:id", requirePermission("widgets:delete", "widgets:write"), deleteHandler);
export function requirePermission(...requiredPermissions: string[]) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const user = (req as any).user as AuthUser | undefined;
    if (!user) {
      throw new ForbiddenError("access", "resource");
    }

    const userPermSet = new Set(user.permissions);
    for (const perm of requiredPermissions) {
      if (!userPermSet.has(perm)) {
        throw new ForbiddenError(`missing permission: ${perm}`, "resource");
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
import { ForbiddenError } from "../errors/domain-errors";
import type { AuthUser } from "../types/auth";

export const ROLES_KEY = "roles";

 * NestJS guard that checks the user has at least one of the specified roles.
 * Usage:
 *   @UseGuards(JwtAuthGuard, RolesGuard)
 *   @Roles("admin", "editor")
 *   @Put(":id")
 *   update() { ... }
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
      throw new ForbiddenError("access", "resource");
    }

    const hasRole = requiredRoles.some((role) => user.roles.includes(role));
    if (!hasRole) {
      throw new ForbiddenError(
        `requires one of roles: ${requiredRoles.join(", ")}`,
        "resource",
      );
    }

    return true;
  }
}

// --- Roles decorator ---

import { SetMetadata } from "@nestjs/common";

 * Sets required roles metadata on a route handler.
 * Usage: @Roles("admin", "editor")
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

---

## Rate Limiting — Express (express-rate-limit)

```typescript
// src/middleware/rate-limit.ts

import rateLimit from "express-rate-limit";
import type { Request } from "express";
import type { AuthUser } from "../types/auth";

 * Per-tenant rate limiter using express-rate-limit.
 * Keys by tenant ID (from auth context) to prevent noisy neighbor abuse.
 * Falls back to IP-based limiting for unauthenticated requests.
 * Usage:
 *   app.use(tenantRateLimit({ windowMs: 60_000, max: 100 }));
export function tenantRateLimit(opts: { windowMs: number; max: number }) {
  return rateLimit({
    windowMs: opts.windowMs,
    max: opts.max,
    standardHeaders: true,  // Return rate limit info in RateLimit-* headers
    legacyHeaders: false,   // Disable X-RateLimit-* headers

    // Key by tenant ID (from auth) or IP (fallback)
    keyGenerator: (req: Request): string => {
      const user = (req as any).user as AuthUser | undefined;
      return user?.tenantId ?? req.ip ?? "unknown";
    },

    // Custom response matching the error envelope format
    handler: (_req, res) => {
      res.status(429).json({
        error: {
          code: "RATE_LIMITED",
          message: "too many requests — please retry later",
          details: {
            retry_after_seconds: Math.ceil(opts.windowMs / 1000),
          },
        },
      });
    },
  });
}

 * Stricter rate limit for sensitive endpoints (login, password reset, etc.).
 * Usage:
 *   router.post("/auth/login", sensitiveRateLimit(), loginHandler);
export function sensitiveRateLimit() {
  return rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10,                   // 10 attempts per window
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: (req: Request): string => req.ip ?? "unknown",
    handler: (_req, res) => {
      res.status(429).json({
        error: {
          code: "RATE_LIMITED",
          message: "too many attempts — please try again later",
          details: { retry_after_seconds: 900 },
        },
      });
    },
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

 * CORS middleware factory.
 * Mount FIRST in the middleware stack — before auth, before body parser.
 * Usage:
 *   app.use(corsMiddleware({ allowedOrigins: ["https://app.example.com"], ... }));
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

 * Logs request start/finish with timing and attaches enriched logger to request.
 * Mount AFTER requestId and auth.
export function logEnrichment(req: Request, res: Response, next: NextFunction): void {
  const start = Date.now();
  const requestId = (req as any).requestId ?? "";
  const userId = (req as any).userId ?? "";
  const tenantId = (req as any).tenantId ?? "";

  // Log request start
  logger.info("request started", {
    request_id: requestId,
    method: req.method,
    path: req.path,
    user_id: userId,
    tenant_id: tenantId,
    user_agent: req.headers["user-agent"],
    remote_addr: req.ip,
  });

  // Log response on finish
  res.on("finish", () => {
    const duration = Date.now() - start;
    logger.info("request completed", {
      request_id: requestId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
      user_id: userId,
      tenant_id: tenantId,
    });
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
  rateLimit: { windowMs: number; max: number };
}

 * Assembles the full middleware stack in correct order.
 * Order matters: outermost middleware runs first.
 *   1. CORS         — must be outermost to handle preflight before auth
 *   2. Request ID   — generate/extract before anything else
 *   3. Body parser  — with size limit to prevent abuse
 *   4. Auth         — JWT validation, sets tenant/user context
 *   5. Rate limit   — per-tenant, after auth so we know the tenant
 *   6. Log enrich   — after auth so we have user/tenant context
 *   ... routes ...
 *   7. Error handler — MUST be last
export function setupMiddleware(app: Application, config: MiddlewareConfig): void {
  // 1. CORS
  app.use(corsMiddleware(config.cors));

  // 2. Request ID
  app.use(requestId);

  // 3. Body parser with size limit
  app.use(express.json({ limit: "1mb" }));

  // 4. Auth
  app.use(authMiddleware(config.jwt));

  // 5. Rate limiting (per-tenant)
  app.use(tenantRateLimit(config.rateLimit));

  // 6. Log enrichment
  app.use(logEnrichment);
}

 * Mount error handler AFTER all routes.
 *   setupMiddleware(app, config);
 *   app.use("/api/v1/widgets", widgetRouter);
 *   setupErrorHandler(app);
export function setupErrorHandler(app: Application): void {
  app.use(errorHandler);
}
```

---

## Middleware Stack Assembly — NestJS

```typescript
// src/main.ts — NestJS bootstrap showing middleware and guard wiring

import { NestFactory } from "@nestjs/core";
import { ValidationPipe } from "@nestjs/common";
import { AppModule } from "./app.module";
import { AppErrorFilter } from "./filters/app-error.filter";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // 1. CORS
  app.enableCors({
    origin: process.env.ALLOWED_ORIGINS?.split(",") ?? [],
    credentials: true,
    methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization", "X-Request-ID"],
    exposedHeaders: ["X-Request-ID", "Retry-After"],
    maxAge: 86400,
  });

  // 2. Global validation pipe (class-validator)
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );

  // 3. Global error filter (maps AppError to HTTP responses)
  app.useGlobalFilters(new AppErrorFilter());

  // 4. Request size limit
  app.use(require("express").json({ limit: "1mb" }));

  await app.listen(process.env.PORT ?? 3000);
}

bootstrap();
```

---

## API Key Authentication — Express (Alternative to JWT)

```typescript
// src/middleware/api-key-auth.ts

import { timingSafeEqual } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import type { AuthUser } from "../types/auth";
import { UnauthorizedError } from "../errors/domain-errors";

export interface ApiKeyIdentity {
  tenantId: string;
  userId: string;
  roles: string[];
  permissions: string[];
}

export interface ApiKeyConfig {
   * Resolves an API key to identity.
   * In production, this queries a hashed key store (bcrypt/argon2).
   * NEVER store API keys in plaintext.
  lookupFn: (key: string) => Promise<ApiKeyIdentity | null>;
}

 * API key authentication middleware.
 * Reads key from X-API-Key header.
 * Usage:
 *   router.use(apiKeyAuth({ lookupFn: keyStore.lookup }));
export function apiKeyAuth(config: ApiKeyConfig) {
  return async (req: Request, _res: Response, next: NextFunction): Promise<void> => {
    const apiKey = req.headers["x-api-key"] as string | undefined;
    if (!apiKey) {
      throw new UnauthorizedError("missing X-API-Key header");
    }

    const identity = await config.lookupFn(apiKey);
    if (!identity) {
      throw new UnauthorizedError("invalid API key");
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

 * Timing-safe comparison for API key validation.
 * Prevents timing attacks when comparing keys in the lookup function.
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
