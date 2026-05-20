# Fastify framework patterns for TypeScript high-performance HTTP APIs.

## App Setup
```typescript
const app = Fastify({
  logger: { level: process.env.LOG_LEVEL ?? "info", transport: process.env.NODE_ENV === "development" ? { target: "pino-pretty" } : undefined },
  requestIdHeader: "x-request-id",
  genReqId: () => crypto.randomUUID(),
});

await app.register(dbPlugin);           // dependencies first
await app.register(authPlugin);
await app.register(widgetRoutes, { prefix: "/api/v1/widgets" });
app.setErrorHandler(errorHandler);
await app.listen({ port: 8080, host: "0.0.0.0" });
```
- Plugin-based architecture; `register()` creates encapsulated context
- Plugin order matters: database -> auth -> routes

## Plugins
```typescript
import fp from "fastify-plugin";

const dbPluginImpl: FastifyPluginAsync = async (fastify) => {
  const prisma = new PrismaClient();
  await prisma.$connect();
  fastify.decorate("db", prisma);
  fastify.addHook("onClose", async () => { await prisma.$disconnect(); });
};
export const dbPlugin = fp(dbPluginImpl, { name: "database" });

const authPluginImpl: FastifyPluginAsync = async (fastify) => {
  fastify.decorate("authenticate", async (request: FastifyRequest, reply: FastifyReply) => {
    const token = request.headers.authorization?.replace("Bearer ", "");
    if (!token) throw new AppError("UNAUTHORIZED", "missing authorization header", 401);
    request.user = await verifyJwt(token);
  });
};
export const authPlugin = fp(authPluginImpl, { name: "auth", dependencies: ["database"] });
```
- `fp()` breaks encapsulation — decorators available to parent scope
- Without `fp()`, decorators only visible to child plugins
- `addHook("onClose")` for cleanup (connection pools, graceful shutdown)

## Type Augmentation
```typescript
declare module "fastify" {
  interface FastifyInstance {
    db: PrismaClient;
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }
  interface FastifyRequest {
    user: { userId: string; tenantId: string; roles: string[] };
  }
}
```

## Schema Validation (JSON Schema)
```typescript
const createWidgetSchema: FastifySchema = {
  body: {
    type: "object", required: ["name"], additionalProperties: false,
    properties: {
      name: { type: "string", minLength: 1, maxLength: 255 },
      description: { type: "string", maxLength: 2000 },
      status: { type: "string", enum: ["active", "draft"], default: "active" },
    },
  },
  response: { 201: { type: "object", properties: { data: { $ref: "widget#" }, meta: { $ref: "meta#" } } } },
};
const listWidgetsSchema: FastifySchema = {
  querystring: {
    type: "object", properties: {
      cursor: { type: "string" },
      page_size: { type: "integer", minimum: 1, maximum: 100, default: 20 },
      sort_by: { type: "string", enum: ["created_at", "updated_at", "name"], default: "created_at" },
    },
  },
};
```
- JSON Schema validates before handler; `additionalProperties: false` rejects unexpected fields
- Response schemas enable fast-json-stringify (2-5x faster than JSON.stringify)

## Routes with TypeScript Generics
```typescript
export const widgetRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.addHook("onRequest", fastify.authenticate);

  fastify.post<{ Body: CreateWidgetBody }>("/", { schema: createWidgetSchema }, async (request, reply) => {
    const widget = await WidgetService.create(fastify.db, request.user.tenantId, request.user.userId, request.body);
    return reply.status(201).send({ data: widget, meta: { requestId: request.id, timestamp: new Date().toISOString() } });
  });

  fastify.get<{ Params: { id: string } }>("/:id", { schema: getWidgetSchema }, async (request) => {
    const widget = await WidgetService.get(fastify.db, request.user.tenantId, request.params.id);
    if (!widget) throw new AppError("NOT_FOUND", `widget '${request.params.id}' not found`, 404);
    return { data: widget, meta: { requestId: request.id, timestamp: new Date().toISOString() } };
  });

  fastify.get<{ Querystring: ListWidgetsQuery }>("/", { schema: listWidgetsSchema }, async (request) => {
    const { cursor, page_size = 20, sort_by = "created_at", sort_dir = "desc" } = request.query;
    const result = await WidgetService.list(fastify.db, request.user.tenantId, { cursor, pageSize: page_size, sortBy: sort_by, sortDir: sort_dir });
    return { data: result.items, meta: { cursor: result.cursor, hasMore: result.hasMore, total: result.total, requestId: request.id } };
  });

  fastify.delete<{ Params: { id: string } }>("/:id", { schema: getWidgetSchema }, async (request, reply) => {
    await WidgetService.softDelete(fastify.db, request.user.tenantId, request.params.id);
    return reply.status(204).send();
  });
};
```

## Hooks Lifecycle
```
onRequest -> preParsing -> preValidation -> preHandler -> handler -> preSerialization -> onSend -> onResponse
```
- `onRequest`: auth, rate limiting
- `preHandler`: authorization, tenant context
- `preSerialization`: transform response (add metadata envelope)
- `onError`: logging (does NOT replace `setErrorHandler`)

## Error Handling
```typescript
function errorHandler(error: Error, request: FastifyRequest, reply: FastifyReply): void {
  if (error instanceof AppError) {
    reply.status(error.statusCode).send({
      error: { code: error.code, message: error.statusCode >= 500 ? "an unexpected error occurred" : error.message, details: error.details },
    });
    return;
  }
  if ("validation" in error) {
    reply.status(422).send({ error: { code: "VALIDATION_ERROR", message: "request validation failed", details: { issues: (error as any).validation } } });
    return;
  }
  request.log.error({ err: error }, "unhandled error");
  reply.status(500).send({ error: { code: "INTERNAL_ERROR", message: "an unexpected error occurred" } });
}
```

## Testing with inject()
```typescript
test("POST /api/v1/widgets — creates widget", async () => {
  const response = await app.inject({
    method: "POST", url: "/api/v1/widgets",
    headers: { authorization: `Bearer ${testToken()}` },
    payload: { name: "New Widget", description: "Test" },
  });
  assert.strictEqual(response.statusCode, 201);
  assert.strictEqual(JSON.parse(response.body).data.name, "New Widget");
});
```
- `inject()` sends requests without HTTP server -- fast, no port conflicts
- Close app after each test to clean up hooks/connections

## Performance
```typescript
// Shared schemas for $ref reuse + fast-json-stringify
fastify.addSchema({ $id: "widget", type: "object", properties: { id: { type: "string" }, name: { type: "string" } } });
```

## Rules
- Plugin architecture: every feature is a `register()` plugin
- JSON Schema on every route -- validates input + optimizes serialization
- `additionalProperties: false` on request schemas
- `fp()` for shared decorators (db, auth); plain plugins for encapsulated features
- Hooks for cross-cutting concerns
- TypeScript generics on routes for type-safe request access
- Always extend Fastify types in `.d.ts` when adding decorators
