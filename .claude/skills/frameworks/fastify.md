# Fastify framework patterns for TypeScript high-performance HTTP APIs.

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Fastify 5.12, fastify-plugin 6.0, Prisma 7.10 + @prisma/adapter-pg. The `inject()` tests below are also run (node:test, 5/5) against this page's app, plugins, routes, schemas and error handler, with an in-memory widget service and test-token verifier standing in for the project's (tests/archetype-compile/typescript/run.sh).

## App Setup and Plugin Architecture
```typescript
// src/app.ts — the app factory: server.ts listens, tests call build() + app.inject()
import { randomUUID } from "node:crypto";
import Fastify, { type FastifyInstance } from "fastify";
import { AppError, errorBody, errorHandler } from "./errors";
import { authPlugin } from "./plugins/auth";
import { dbPlugin } from "./plugins/database";
import { servicesPlugin } from "./plugins/services";
import { widgetRoutes } from "./routes/widgets";

// An inbound X-Request-Id is reused only when well formed (bounded charset and length); else a new one
const VALID_ID = /^[A-Za-z0-9._-]{8,128}$/;

export async function build(opts: { testing?: boolean } = {}): Promise<FastifyInstance> {
  const app = Fastify({
    logger: opts.testing ? false : {
      level: process.env.LOG_LEVEL ?? "info",
      ...(process.env.NODE_ENV === "development" ? { transport: { target: "pino-pretty" } } : {}),
    },
    // requestIdHeader would take the client's header VERBATIM — read and validate it here instead
    requestIdHeader: false,
    genReqId: (req) => {
      const inbound = req.headers["x-request-id"];
      return typeof inbound === "string" && VALID_ID.test(inbound) ? inbound : randomUUID();
    },
    // Fastify's Ajv defaults to removeAdditional: true, which silently DROPS unknown body fields;
    // false makes `additionalProperties: false` reject them (400 VALIDATION_FAILED)
    ajv: { customOptions: { removeAdditional: false } },
  });

  // Register plugins (order matters — dependencies first)
  await app.register(dbPlugin);
  await app.register(authPlugin);
  await app.register(servicesPlugin);

  // Every response echoes the id its body carries (meta.request_id / error.request_id)
  app.addHook("onRequest", async (request, reply) => {
    reply.header("x-request-id", request.id);
  });

  // Global error handler + unknown routes — both answer with the error envelope (see Error Handling).
  // Set them before registering routes so every route plugin inherits them.
  app.setErrorHandler(errorHandler);
  app.setNotFoundHandler((request, reply) => {
    reply.status(404).send(errorBody(new AppError("NOT_FOUND", "Not found.", 404), request.id));
  });

  // Register route modules with prefix
  await app.register(widgetRoutes, { prefix: "/api/v1/widgets" });
  return app;
}

// src/server.ts
import { build } from "./app";

const app = await build();
await app.listen({ port: Number(process.env.PORT ?? 8080), host: "0.0.0.0" });
```
- Fastify uses a plugin-based architecture — everything is a plugin
- `register()` creates an encapsulated context — plugins don't leak to siblings
- Plugin order matters: database before auth, auth before routes
- Built-in Pino logger — structured JSON logging with zero overhead
- Request ids: don't set `requestIdHeader` to a header name — Fastify then uses the client's value verbatim
  (any length, any characters). Validate it in `genReqId`, as above

## Plugin Architecture
```typescript
// src/plugins/database.ts
import fp from "fastify-plugin";
import type { FastifyPluginAsync } from "fastify";
import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";

// Database plugin — exposes db on fastify instance
const dbPluginImpl: FastifyPluginAsync = async (fastify) => {
  // Prisma 7: a driver adapter is required — `new PrismaClient()` with no options throws at startup
  const prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL! }) });
  await prisma.$connect();

  fastify.decorate("db", prisma);

  fastify.addHook("onClose", async () => {
    await prisma.$disconnect();
  });
};

// fp() breaks encapsulation — makes the plugin available to parent scope
export const dbPlugin = fp(dbPluginImpl, {
  name: "database",
});

// src/plugins/auth.ts
import fp from "fastify-plugin";
import type { FastifyPluginAsync, FastifyReply, FastifyRequest } from "fastify";
import { AppError } from "../errors";
import { verifyJwt } from "../lib/jwt"; // signature, exp, iss, aud — backend/archetypes/auth-middleware-typescript.md

// Auth plugin — adds authenticate decorator
const authPluginImpl: FastifyPluginAsync = async (fastify) => {
  fastify.decorate("authenticate", async (request: FastifyRequest, _reply: FastifyReply) => {
    const [scheme, token] = request.headers.authorization?.split(" ") ?? [];
    if (scheme !== "Bearer" || !token) {
      throw new AppError("UNAUTHENTICATED", "Sign in to continue.", 401);
    }
    try {
      request.user = await verifyJwt(token);
    } catch {
      throw new AppError("UNAUTHENTICATED", "Sign in to continue.", 401); // bad signature, expired, wrong iss/aud
    }
  });
};

export const authPlugin = fp(authPluginImpl, {
  name: "auth",
  dependencies: ["database"],
});
```
- `fastify-plugin` (fp) breaks encapsulation — decorators become available to parent
- Without `fp()`, plugins are encapsulated — decorators only visible to child plugins
- Use `dependencies` array to declare plugin ordering requirements
- `addHook("onClose")` for cleanup — connection pools, graceful shutdown

## Type Augmentation
```typescript
// src/types/fastify.d.ts — extend Fastify types with custom decorators
import type { PrismaClient } from "@prisma/client";
import type { WidgetService } from "../services/widget.service";

declare module "fastify" {
  interface FastifyInstance {
    db: PrismaClient;
    widgetService: WidgetService;
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }

  interface FastifyRequest {
    user: {
      userId: string;
      tenantId: string;
      roles: string[];
    };
    startTime: number;
  }
}
```
- Always extend Fastify types when adding decorators — TypeScript will enforce usage
- Declare `user` on `FastifyRequest` for auth context

## Schema Validation (JSON Schema)
```typescript
// src/schemas/widget.ts
import type { FastifySchema } from "fastify";

export const createWidgetSchema: FastifySchema = {
  body: {
    type: "object",
    required: ["name"],
    properties: {
      name: { type: "string", minLength: 1, maxLength: 255 },
      description: { type: "string", maxLength: 2000 },
      status: { type: "string", enum: ["active", "draft"], default: "active" },
    },
    additionalProperties: false,
  },
  response: {
    201: {
      type: "object",
      properties: {
        data: {
          type: "object",
          properties: {
            id: { type: "string", format: "uuid" },
            name: { type: "string" },
            description: { type: "string" },
            status: { type: "string" },
            createdAt: { type: "string", format: "date-time" },
          },
        },
        meta: {
          type: "object",
          required: ["request_id"],
          properties: {
            request_id: { type: "string" },
          },
        },
      },
    },
  },
};

// List query params: cursor pagination only — ?cursor=<opaque>&limit=<n>
export const listWidgetsSchema: FastifySchema = {
  querystring: {
    type: "object",
    properties: {
      cursor: { type: "string" },
      limit: { type: "integer", minimum: 1, maximum: 100, default: 20 },
      sort_by: { type: "string", enum: ["created_at", "updated_at", "name"], default: "created_at" },
      sort_dir: { type: "string", enum: ["asc", "desc"], default: "desc" },
    },
  },
};

export const getWidgetSchema: FastifySchema = {
  params: {
    type: "object",
    required: ["id"],
    properties: {
      id: { type: "string", format: "uuid" },
    },
  },
};
```
- JSON Schema validation runs before the handler — invalid requests never reach business logic; the error
  handler turns a schema failure into 400 `VALIDATION_FAILED` with `details[]`
- A response schema strips any property it doesn't list — every envelope key (`meta.request_id`,
  `meta.pagination`) must be in it
- `additionalProperties: false` rejects unexpected fields — catches typos early — but only with
  `ajv: { customOptions: { removeAdditional: false } }` (App Setup). Fastify's default (`removeAdditional:
  true`) silently strips them and the request succeeds
- Response schemas enable serialization optimization — Fastify compiles fast serializers
- Ajv validates request schemas; fast-json-stringify serializes responses

## Route Definitions with TypeScript Generics
```typescript
// src/routes/widgets.ts
import type { FastifyPluginAsync } from "fastify";
import { AppError } from "../errors";
import { createWidgetSchema, getWidgetSchema, listWidgetsSchema } from "../schemas/widget";

// Type-safe route definition
interface CreateWidgetBody {
  name: string;
  description?: string;
  status?: "active" | "draft";
}

interface WidgetParams {
  id: string;
}

interface ListWidgetsQuery {
  cursor?: string;
  limit?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const widgetRoutes: FastifyPluginAsync = async (fastify) => {
  // Apply auth to all routes in this plugin
  fastify.addHook("onRequest", fastify.authenticate);

  fastify.post<{ Body: CreateWidgetBody }>(
    "/",
    { schema: createWidgetSchema },
    async (request, reply) => {
      const widget = await fastify.widgetService.create(
        request.user.tenantId,
        request.user.userId,
        request.body,
      );
      return reply.status(201).send({
        data: widget,
        meta: { request_id: request.id },
      });
    },
  );

  fastify.get<{ Params: WidgetParams }>(
    "/:id",
    { schema: getWidgetSchema },
    async (request, reply) => {
      const widget = await fastify.widgetService.get(
        request.user.tenantId,
        request.params.id,
      );
      if (!widget) {
        // also when it belongs to another tenant — never 403, don't confirm it exists
        throw new AppError("NOT_FOUND", "Widget not found.", 404);
      }
      return { data: widget, meta: { request_id: request.id } };
    },
  );

  fastify.get<{ Querystring: ListWidgetsQuery }>(
    "/",
    { schema: listWidgetsSchema },
    async (request, reply) => {
      const { cursor, limit = 20, sort_by = "created_at", sort_dir = "desc" } = request.query;
      const result = await fastify.widgetService.list(
        request.user.tenantId,
        { cursor, limit, sortBy: sort_by, sortDir: sort_dir },
      );
      return {
        data: result.items, // always an array — [] when empty
        meta: {
          request_id: request.id,
          pagination: {
            next_cursor: result.nextCursor, // null on the last page
            has_more: result.nextCursor !== null,
            limit,
          },
        },
      };
    },
  );

  fastify.delete<{ Params: WidgetParams }>(
    "/:id",
    { schema: getWidgetSchema },
    async (request, reply) => {
      await fastify.widgetService.softDelete(
        request.user.tenantId,
        request.params.id,
      );
      return reply.status(204).send();
    },
  );
};
```
- Generic type parameters (`<{ Body, Params, Querystring }>`) provide type-safe request access
- `RouteGenericInterface` is the underlying type — specify `Body`, `Querystring`, `Params`, `Headers`
- Return values are auto-serialized — no need to call `reply.send()` for simple responses
- Use `reply.status(201).send()` for non-200 status codes

## Hooks Lifecycle
```typescript
// Hook order: onRequest → preParsing → preValidation → preHandler → handler → preSerialization → onSend → onResponse

// onRequest: auth, rate limiting, request logging
fastify.addHook("onRequest", async (request, reply) => {
  request.log.info({ method: request.method, url: request.url }, "request started");
});

// preHandler: authorization checks, tenant context setup
fastify.addHook("preHandler", async (request, reply) => {
  // Set tenant context for database queries
  await setTenantContext(fastify.db, request.user.tenantId);
});

// preSerialization: transform response data before JSON serialization
fastify.addHook("preSerialization", async (request, reply, payload) => {
  // Stamp meta.request_id on success bodies only — an error body carries error.request_id and has no meta
  if (typeof payload === "object" && payload !== null && "data" in payload) {
    const body = payload as { data: unknown; meta?: Record<string, unknown> };
    body.meta = { ...body.meta, request_id: request.id };
  }
  return payload;
});

// onResponse: request logging, metrics
fastify.addHook("onResponse", async (request, reply) => {
  request.log.info(
    { statusCode: reply.statusCode, responseTime: reply.elapsedTime },
    "request completed",
  );
});

// onError: error logging (does NOT replace setErrorHandler)
fastify.addHook("onError", async (request, reply, error) => {
  request.log.error({ err: error }, "request error");
});
```
- Hooks run in registration order within each lifecycle stage
- `onRequest` hooks run before parsing — use for auth, rate limiting
- `preHandler` hooks run after validation — use for authorization
- `preSerialization` hooks can transform response before JSON encoding (e.g. stamp `meta.request_id` on
  success bodies — never add `meta` to an error body)

## Decorators (DI Pattern)
```typescript
// src/plugins/services.ts — decorate the instance with services (one per app, shared by every route)
import fp from "fastify-plugin";
import type { FastifyPluginAsync } from "fastify";
import { WidgetService } from "../services/widget.service";

const servicesPluginImpl: FastifyPluginAsync = async (fastify) => {
  fastify.decorate("widgetService", new WidgetService(fastify.db));

  // Per-request value: declare it with an initial primitive (or null — never a shared object), so every
  // request object has the same shape
  fastify.decorateRequest("startTime", 0);
  fastify.addHook("onRequest", async (request) => {
    request.startTime = Date.now();
  });
};

export const servicesPlugin = fp(servicesPluginImpl, { name: "services", dependencies: ["database"] });
```
- `fastify.decorate()` for instance-level singletons (services, DB connections)
- `fastify.decorateRequest()` for per-request values
- Decorators must be registered before routes that use them

## Error Handling
Every error body is the envelope in `api/response-envelope.md`:
`{ error: { code, message, details?, request_id, retryable } }` — no `data`, no `meta`, no exception text.
```typescript
// src/errors.ts
import type { FastifyError, FastifyReply, FastifyRequest, FastifySchemaValidationError } from "fastify";

// details[].code: exactly the closed set in api/response-envelope.md (a stray code is a compile error)
export type FieldCode =
  | "required" | "invalid_type" | "invalid_format" | "invalid_value" | "out_of_range"
  | "too_short" | "too_long" | "unknown_field" | "invalid_cursor" | "already_exists";
export type FieldError = { field: string; code: FieldCode; message: string };

export class AppError extends Error {
  constructor(
    public code: string,                // UPPER_SNAKE, stable: NOT_FOUND, CONFLICT, …
    message: string,                    // user-safe catalog text — never a caught error's message
    public statusCode: number,
    public details: FieldError[] = [],  // VALIDATION_FAILED only
    public retryable = false,           // true for RATE_LIMITED / UNAVAILABLE
  ) {
    super(message);
    this.name = "AppError";
  }
}

// The only shape an error body takes
export function errorBody(err: AppError, requestId: string) {
  return {
    error: {
      code: err.code,
      message: err.message,
      ...(err.details.length > 0 ? { details: err.details } : {}),
      request_id: requestId,
      retryable: err.retryable,
    },
  };
}

// Ajv keyword → a code from the closed set + catalog message. Ajv's own `message` is not sent.
const AJV_FIELD_ERRORS: Record<string, { code: FieldCode; message: string }> = {
  required: { code: "required", message: "This field is required." },
  minLength: { code: "too_short", message: "This value is too short." },
  maxLength: { code: "too_long", message: "This value is too long." },
  minimum: { code: "out_of_range", message: "This value is out of range." },
  maximum: { code: "out_of_range", message: "This value is out of range." },
  exclusiveMinimum: { code: "out_of_range", message: "This value is out of range." },
  exclusiveMaximum: { code: "out_of_range", message: "This value is out of range." },
  minItems: { code: "too_short", message: "This list is too short." },
  maxItems: { code: "too_long", message: "This list is too long." },
  format: { code: "invalid_format", message: "This value has the wrong format." },
  pattern: { code: "invalid_format", message: "This value has the wrong format." },
  enum: { code: "invalid_value", message: "Choose one of the allowed values." },
  type: { code: "invalid_type", message: "This value has the wrong type." },
  additionalProperties: { code: "unknown_field", message: "This field is not allowed." },
};

function toFieldErrors(validation: FastifySchemaValidationError[]): FieldError[] {
  return validation.map((v) => {
    // "/address/city" → "address.city"; `required`/`additionalProperties` name the field in params
    const path = v.instancePath.replace(/^\//, "").replaceAll("/", ".");
    const named = (v.params.missingProperty ?? v.params.additionalProperty) as string | undefined;
    const field = [path, named].filter(Boolean).join(".");
    return { field, ...(AJV_FIELD_ERRORS[v.keyword] ?? { code: "invalid_value", message: "This value isn't allowed." }) };
  });
}

// Fastify's and plugins' own 4xx errors, by status (their message is parser/plugin text — never sent)
function fromStatus(status: number): AppError {
  switch (status) {
    case 401: return new AppError("UNAUTHENTICATED", "Sign in to continue.", 401);
    case 403: return new AppError("FORBIDDEN", "You don't have permission to do this.", 403);
    case 404: return new AppError("NOT_FOUND", "Not found.", 404);
    case 429: return new AppError("RATE_LIMITED", "Too many requests. Try again shortly.", 429, [], true);
    default:  return new AppError("MALFORMED_REQUEST", "The request could not be read.", 400); // bad JSON, 413, 415 …
  }
}

export function errorHandler(error: FastifyError, request: FastifyRequest, reply: FastifyReply): void {
  let appErr: AppError;
  if (error instanceof AppError) {
    appErr = error;
  } else if (error.validation) {
    // JSON Schema (Ajv) failure on body/querystring/params → 400 VALIDATION_FAILED with details[]
    appErr = new AppError("VALIDATION_FAILED", "Some fields are invalid.", 400, toFieldErrors(error.validation));
  } else if (error.statusCode !== undefined && error.statusCode < 500) {
    request.log.info({ err: error }, "request rejected");
    appErr = fromStatus(error.statusCode);
  } else {
    appErr = new AppError("INTERNAL", "Something went wrong.", 500); // unknown: generic message only
  }

  if (appErr.statusCode >= 500) {
    request.log.error({ err: error }, "request failed"); // cause + stack: logs only, under request.id
  }
  if (appErr.statusCode === 401) reply.header("www-authenticate", "Bearer");
  reply.status(appErr.statusCode).send(errorBody(appErr, request.id));
}
// Registered globally in build(): app.setErrorHandler(errorHandler) — before the routes
```
- `setErrorHandler` catches all thrown/rejected errors from handlers and hooks
- Fastify validation errors have a `validation` property — map to 400 `VALIDATION_FAILED` with `details[]`
  (not 422, and not Ajv's raw error objects)
- `setNotFoundHandler` too — unknown routes also answer with the envelope
- Never expose internal error details — no exception, parser or plugin text in any error body

## Testing with inject()
```typescript
// src/widgets.test.ts
import { randomUUID } from "node:crypto";
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert";
import type { FastifyInstance } from "fastify";
import { build } from "./app"; // the app factory (App Setup)
import { testToken } from "./test/helpers"; // signs a JWT for the seeded test user

describe("Widget API", () => {
  let app: FastifyInstance;

  beforeEach(async () => {
    app = await build({ testing: true });
  });

  afterEach(async () => {
    await app.close();
  });

  test("POST /api/v1/widgets — creates widget", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/api/v1/widgets",
      headers: { authorization: `Bearer ${testToken()}` },
      payload: { name: "New Widget", description: "Test" },
    });

    assert.strictEqual(response.statusCode, 201);
    const body = JSON.parse(response.body);
    assert.strictEqual(body.data.name, "New Widget");
    assert.ok(body.meta.request_id);
    assert.strictEqual(response.headers["x-request-id"], body.meta.request_id);
  });

  test("GET /api/v1/widgets/:id — not found returns 404", async () => {
    const response = await app.inject({
      method: "GET",
      url: `/api/v1/widgets/${randomUUID()}`,
      headers: { authorization: `Bearer ${testToken()}` },
    });

    assert.strictEqual(response.statusCode, 404);
    const body = JSON.parse(response.body);
    assert.strictEqual(body.error.code, "NOT_FOUND");
    assert.ok(body.error.request_id);
    assert.strictEqual(body.data, undefined); // error bodies never carry data
  });

  test("POST /api/v1/widgets — validation error on missing name", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/api/v1/widgets",
      headers: { authorization: `Bearer ${testToken()}` },
      payload: { description: "no name" },
    });

    assert.strictEqual(response.statusCode, 400);
    const body = JSON.parse(response.body);
    assert.strictEqual(body.error.code, "VALIDATION_FAILED");
    assert.deepStrictEqual(body.error.details, [
      { field: "name", code: "required", message: "This field is required." },
    ]);
  });

  test("POST /api/v1/widgets — an unknown field is rejected, not silently dropped", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/api/v1/widgets",
      headers: { authorization: `Bearer ${testToken()}` },
      payload: { name: "New Widget", nmae: "typo" },
    });

    assert.strictEqual(response.statusCode, 400);
    assert.deepStrictEqual(JSON.parse(response.body).error.details, [
      { field: "nmae", code: "unknown_field", message: "This field is not allowed." },
    ]);
  });

  test("GET /api/v1/widgets — unauthenticated returns 401", async () => {
    const response = await app.inject({
      method: "GET",
      url: "/api/v1/widgets",
    });

    assert.strictEqual(response.statusCode, 401);
    assert.strictEqual(JSON.parse(response.body).error.code, "UNAUTHENTICATED");
  });
});
```
- `app.inject()` sends requests without starting an HTTP server — fast, no port conflicts
- Test that an unknown field gets 400: with Fastify's default Ajv options it is stripped and the request passes
- Returns a `Response` object with `statusCode`, `body`, `headers`
- Build a factory function that creates the Fastify instance — inject test config
- Close the app after each test to clean up hooks and connections

## Performance Patterns
```typescript
// Response serialization — compile-time JSON serializer
// Defining response schema enables fast-json-stringify (2-5x faster than JSON.stringify)
const getSchema = {
  response: {
    200: {
      type: "object",
      properties: {
        data: { $ref: "widget#" },
        meta: { $ref: "meta#" },
      },
    },
  },
};

// Shared schemas (reusable $ref targets)
fastify.addSchema({
  $id: "widget",
  type: "object",
  properties: {
    id: { type: "string" },
    name: { type: "string" },
    status: { type: "string" },
  },
});

// The envelope's meta (api/response-envelope.md). fast-json-stringify drops unlisted keys, so pagination
// must be declared here for list responses to keep it.
fastify.addSchema({
  $id: "meta",
  type: "object",
  required: ["request_id"],
  properties: {
    request_id: { type: "string" },
    pagination: {
      type: "object",
      required: ["next_cursor", "has_more", "limit"],
      properties: {
        next_cursor: { type: ["string", "null"] },
        has_more: { type: "boolean" },
        limit: { type: "integer" },
        total_count: { type: "integer" }, // optional
      },
    },
  },
});
```

## Rules
- Plugin architecture for modularity — every feature is a plugin registered with `fastify.register()`
- JSON Schema on every route — validates input and optimizes serialization
- `additionalProperties: false` on request schemas — reject unexpected fields
- Response schemas enable fast-json-stringify — define them for performance
- `fastify-plugin` (fp) to break encapsulation — use for shared decorators (db, auth)
- Hooks for cross-cutting concerns — `onRequest` for auth, `preSerialization` for envelope
- `setErrorHandler` for global error mapping — one handler catches all errors and writes the envelope
- List endpoints take `?cursor=` + `?limit=` and answer `meta.pagination` (`next_cursor`, `has_more`, `limit`)
- `inject()` for testing — no HTTP server needed, no port conflicts
- TypeScript generics on routes for type-safe `request.body`, `request.params`, `request.query`
- Decorators for DI — `decorate()` for singletons, `decorateRequest()` for per-request state
- Always extend Fastify types in `.d.ts` when adding decorators
