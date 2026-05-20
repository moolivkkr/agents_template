# Fastify framework patterns for TypeScript high-performance HTTP APIs.

## App Setup and Plugin Architecture
```typescript
import Fastify from "fastify";
import { widgetRoutes } from "./routes/widgets";
import { authPlugin } from "./plugins/auth";
import { dbPlugin } from "./plugins/database";

const app = Fastify({
  logger: {
    level: process.env.LOG_LEVEL ?? "info",
    transport: process.env.NODE_ENV === "development"
      ? { target: "pino-pretty" }
      : undefined,
  },
  requestIdHeader: "x-request-id",
  genReqId: () => crypto.randomUUID(),
});

// Register plugins (order matters — dependencies first)
await app.register(dbPlugin);
await app.register(authPlugin);

// Register route modules with prefix
await app.register(widgetRoutes, { prefix: "/api/v1/widgets" });

// Global error handler
app.setErrorHandler(errorHandler);

await app.listen({ port: 8080, host: "0.0.0.0" });
```
- Fastify uses a plugin-based architecture — everything is a plugin
- `register()` creates an encapsulated context — plugins don't leak to siblings
- Plugin order matters: database before auth, auth before routes
- Built-in Pino logger — structured JSON logging with zero overhead

## Plugin Architecture
```typescript
import fp from "fastify-plugin";
import { FastifyPluginAsync } from "fastify";
import { PrismaClient } from "@prisma/client";

// Database plugin — exposes db on fastify instance
const dbPluginImpl: FastifyPluginAsync = async (fastify) => {
  const prisma = new PrismaClient();
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

// Auth plugin — adds authenticate decorator
const authPluginImpl: FastifyPluginAsync = async (fastify) => {
  fastify.decorate("authenticate", async (request: FastifyRequest, reply: FastifyReply) => {
    const token = request.headers.authorization?.replace("Bearer ", "");
    if (!token) {
      throw new AppError("UNAUTHORIZED", "missing authorization header", 401);
    }
    const claims = await verifyJwt(token);
    request.user = claims;
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
// types/fastify.d.ts — extend Fastify types with custom decorators
import { PrismaClient } from "@prisma/client";

declare module "fastify" {
  interface FastifyInstance {
    db: PrismaClient;
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }

  interface FastifyRequest {
    user: {
      userId: string;
      tenantId: string;
      roles: string[];
    };
  }
}
```
- Always extend Fastify types when adding decorators — TypeScript will enforce usage
- Declare `user` on `FastifyRequest` for auth context

## Schema Validation (JSON Schema)
```typescript
import { FastifySchema } from "fastify";

const createWidgetSchema: FastifySchema = {
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
          properties: {
            requestId: { type: "string" },
            timestamp: { type: "string" },
          },
        },
      },
    },
  },
};

const listWidgetsSchema: FastifySchema = {
  querystring: {
    type: "object",
    properties: {
      cursor: { type: "string" },
      page_size: { type: "integer", minimum: 1, maximum: 100, default: 20 },
      sort_by: { type: "string", enum: ["created_at", "updated_at", "name"], default: "created_at" },
      sort_dir: { type: "string", enum: ["asc", "desc"], default: "desc" },
    },
  },
};

const getWidgetSchema: FastifySchema = {
  params: {
    type: "object",
    required: ["id"],
    properties: {
      id: { type: "string", format: "uuid" },
    },
  },
};
```
- JSON Schema validation runs before the handler — invalid requests never reach business logic
- `additionalProperties: false` rejects unexpected fields — catches typos early
- Response schemas enable serialization optimization — Fastify compiles fast serializers
- Ajv validates request schemas; fast-json-stringify serializes responses

## Route Definitions with TypeScript Generics
```typescript
import { FastifyPluginAsync } from "fastify";

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
  page_size?: number;
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
      const widget = await WidgetService.create(
        fastify.db,
        request.user.tenantId,
        request.user.userId,
        request.body,
      );
      return reply.status(201).send({
        data: widget,
        meta: { requestId: request.id, timestamp: new Date().toISOString() },
      });
    },
  );

  fastify.get<{ Params: WidgetParams }>(
    "/:id",
    { schema: getWidgetSchema },
    async (request, reply) => {
      const widget = await WidgetService.get(
        fastify.db,
        request.user.tenantId,
        request.params.id,
      );
      if (!widget) {
        throw new AppError("NOT_FOUND", `widget '${request.params.id}' not found`, 404);
      }
      return { data: widget, meta: { requestId: request.id, timestamp: new Date().toISOString() } };
    },
  );

  fastify.get<{ Querystring: ListWidgetsQuery }>(
    "/",
    { schema: listWidgetsSchema },
    async (request, reply) => {
      const { cursor, page_size = 20, sort_by = "created_at", sort_dir = "desc" } = request.query;
      const result = await WidgetService.list(
        fastify.db,
        request.user.tenantId,
        { cursor, pageSize: page_size, sortBy: sort_by, sortDir: sort_dir },
      );
      return {
        data: result.items,
        meta: {
          cursor: result.cursor,
          hasMore: result.hasMore,
          total: result.total,
          requestId: request.id,
          timestamp: new Date().toISOString(),
        },
      };
    },
  );

  fastify.delete<{ Params: WidgetParams }>(
    "/:id",
    { schema: getWidgetSchema },
    async (request, reply) => {
      await WidgetService.softDelete(
        fastify.db,
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
  // Add request metadata to all responses
  if (typeof payload === "object" && payload !== null) {
    (payload as Record<string, unknown>).meta = {
      ...(payload as Record<string, unknown>).meta,
      requestId: request.id,
    };
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
- `preSerialization` hooks can transform response before JSON encoding

## Decorators (DI Pattern)
```typescript
// Decorate fastify instance with services
fastify.decorate("widgetService", new WidgetService(fastify.db));
fastify.decorate("cacheService", new CacheService(redisClient));

// Decorate request with per-request context
fastify.decorateRequest("startTime", 0);
fastify.addHook("onRequest", async (request) => {
  request.startTime = Date.now();
});
```
- `fastify.decorate()` for instance-level singletons (services, DB connections)
- `fastify.decorateRequest()` for per-request values
- Decorators must be registered before routes that use them

## Error Handling
```typescript
class AppError extends Error {
  constructor(
    public code: string,
    message: string,
    public statusCode: number,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "AppError";
  }
}

function errorHandler(error: Error, request: FastifyRequest, reply: FastifyReply): void {
  if (error instanceof AppError) {
    reply.status(error.statusCode).send({
      error: {
        code: error.code,
        message: error.statusCode >= 500 ? "an unexpected error occurred" : error.message,
        details: error.details,
      },
    });
    return;
  }

  // Fastify validation errors (from JSON Schema)
  if ("validation" in error) {
    reply.status(422).send({
      error: {
        code: "VALIDATION_ERROR",
        message: "request validation failed",
        details: { issues: (error as any).validation },
      },
    });
    return;
  }

  // Unknown errors — never expose internals
  request.log.error({ err: error }, "unhandled error");
  reply.status(500).send({
    error: {
      code: "INTERNAL_ERROR",
      message: "an unexpected error occurred",
    },
  });
}

// Register globally
app.setErrorHandler(errorHandler);
```
- `setErrorHandler` catches all thrown/rejected errors from handlers and hooks
- Fastify validation errors have a `validation` property — map to 422
- Never expose internal error details in 500 responses

## Testing with inject()
```typescript
import { build } from "./app"; // factory function that creates Fastify instance
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert";

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
    assert.ok(body.meta.requestId);
  });

  test("GET /api/v1/widgets/:id — not found returns 404", async () => {
    const response = await app.inject({
      method: "GET",
      url: `/api/v1/widgets/${crypto.randomUUID()}`,
      headers: { authorization: `Bearer ${testToken()}` },
    });

    assert.strictEqual(response.statusCode, 404);
    const body = JSON.parse(response.body);
    assert.strictEqual(body.error.code, "NOT_FOUND");
  });

  test("POST /api/v1/widgets — validation error on missing name", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/api/v1/widgets",
      headers: { authorization: `Bearer ${testToken()}` },
      payload: { description: "no name" },
    });

    assert.strictEqual(response.statusCode, 422);
  });

  test("GET /api/v1/widgets — unauthenticated returns 401", async () => {
    const response = await app.inject({
      method: "GET",
      url: "/api/v1/widgets",
    });

    assert.strictEqual(response.statusCode, 401);
  });
});
```
- `app.inject()` sends requests without starting an HTTP server — fast, no port conflicts
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

fastify.addSchema({
  $id: "meta",
  type: "object",
  properties: {
    requestId: { type: "string" },
    timestamp: { type: "string" },
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
- `setErrorHandler` for global error mapping — one handler catches all errors
- `inject()` for testing — no HTTP server needed, no port conflicts
- TypeScript generics on routes for type-safe `request.body`, `request.params`, `request.query`
- Decorators for DI — `decorate()` for singletons, `decorateRequest()` for per-request state
- Always extend Fastify types in `.d.ts` when adding decorators
