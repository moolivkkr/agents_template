---
skill: grpc-pattern-typescript
description: TypeScript gRPC archetype — nice-grpc or @grpc/grpc-js, ts-proto, interceptors, streaming, health check
version: "1.0"
tags:
  - typescript
  - grpc
  - protobuf
  - nice-grpc
  - archetype
  - backend
---

# gRPC Pattern — TypeScript

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, nice-grpc 2.1, nice-grpc-server-health 2.0, against ts-proto 2.12 output of grpc-pattern.md's protos (tests/archetype-compile/typescript/run.sh).

> **Canonical reference**: This is the TypeScript counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

TypeScript gRPC uses `nice-grpc` (modern, ergonomic) or `@grpc/grpc-js` (official, lower-level). Code generation uses `ts-proto` or `@grpc/proto-loader`.

## Code Generation with ts-proto

```bash
# Install
npm install nice-grpc nice-grpc-server-health ts-proto

# buf.gen.yaml
version: v1
plugins:
  - plugin: ts_proto
    out: gen
    opt:
      - outputServices=nice-grpc
      - outputServices=generic-definitions   # required with nice-grpc: emits WidgetServiceDefinition
      - outputPartialMethods=true
      - useExactTypes=false
      - esModuleInterop=true

# Generate
buf generate
```

## Server Implementation (nice-grpc)

```typescript
// src/grpc/widget-server.ts

import { ServerError, Status, type CallContext } from 'nice-grpc';
import type { WidgetServiceImplementation } from '../gen/yourapp/v1/widget_service';
// ts-proto emits one module per .proto file — messages come from the file that declares them
import {
  WidgetStatus,
  type Widget as WidgetMessage,
  type CreateWidgetRequest,
  type CreateWidgetResponse,
  type GetWidgetRequest,
  type GetWidgetResponse,
  type UpdateWidgetRequest,
  type UpdateWidgetResponse,
  type DeleteWidgetRequest,
  type DeleteWidgetResponse,
  type ListWidgetsRequest,
  type ListWidgetsResponse,
} from '../gen/yourapp/v1/widget';
import {
  WidgetEventType,
  type WatchWidgetsRequest,
  type WidgetEvent,
  type ImportWidgetRequest,
  type ImportWidgetsResponse,
  type EditWidgetResponse,
} from '../gen/yourapp/v1/common';
import type { WidgetService } from '../services/widget.service';
import type { Widget } from '../domain/entity';
import { isAppError } from '../errors';
import { getAuthContext } from './middleware';
import { mapError } from './errors';

/** Change feed behind WatchWidgets (Redis pub/sub, Postgres LISTEN/NOTIFY, …) — not part of WidgetService. */
export interface WidgetEventSource {
  subscribe(tenantId: string): AsyncIterableIterator<{ type: 'created' | 'updated' | 'deleted'; widget: Widget }>;
}

export function createWidgetServer(svc: WidgetService, events: WidgetEventSource): WidgetServiceImplementation {
  return {
    async createWidget(
      request: CreateWidgetRequest,
      context: CallContext,
    ): Promise<CreateWidgetResponse> {
      const auth = getAuthContext(context);

      if (!request.name) {
        throw new ServerError(Status.INVALID_ARGUMENT, 'name is required');
      }

      try {
        // tenant and user come from the verified token (auth middleware), never from the request
        const result = await svc.create(auth.tenantId, auth.userId, {
          name: request.name,
          description: request.description,
        });

        return { widget: toProto(result) };
      } catch (err) {
        throw mapError(err);
      }
    },

    async getWidget(
      request: GetWidgetRequest,
      context: CallContext,
    ): Promise<GetWidgetResponse> {
      const auth = getAuthContext(context);

      try {
        const result = await svc.get(auth.tenantId, request.id);
        return { widget: toProto(result) };
      } catch (err) {
        throw mapError(err);
      }
    },

    async updateWidget(
      request: UpdateWidgetRequest,
      context: CallContext,
    ): Promise<UpdateWidgetResponse> {
      const auth = getAuthContext(context);

      try {
        const result = await svc.update(auth.tenantId, request.id, {
          name: request.name,
          description: request.description,
          version: request.version, // optimistic lock — a stale version maps to a gRPC error
        });
        return { widget: toProto(result) };
      } catch (err) {
        throw mapError(err);
      }
    },

    async deleteWidget(
      request: DeleteWidgetRequest,
      context: CallContext,
    ): Promise<DeleteWidgetResponse> {
      const auth = getAuthContext(context);

      try {
        await svc.delete(auth.tenantId, request.id);
        return {};
      } catch (err) {
        throw mapError(err);
      }
    },

    async listWidgets(
      request: ListWidgetsRequest,
      context: CallContext,
    ): Promise<ListWidgetsResponse> {
      const auth = getAuthContext(context);

      // AIP-158: 0 means the default, above the maximum is coerced to it, negative is an error.
      if (request.pageSize < 0) throw new ServerError(Status.INVALID_ARGUMENT, 'page_size must not be negative');
      const pageSize = Math.min(request.pageSize || 20, 100);
      const [sortBy = 'created_at', sortDir] = (request.orderBy || 'created_at desc').split(' ');

      try {
        const result = await svc.list(auth.tenantId, {
          cursor: request.pageToken, // opaque cursor; "" = first page
          pageSize,
          sortBy, // allow-listed by the repository
          sortDir: sortDir === 'asc' ? 'asc' : 'desc',
          fields: {},
        });

        return {
          widgets: result.items.map(toProto),
          nextPageToken: result.hasMore ? result.cursor : '',
          totalCount: result.total,
        };
      } catch (err) {
        throw mapError(err);
      }
    },

    // Server streaming
    async *watchWidgets(
      request: WatchWidgetsRequest,
      context: CallContext,
    ): AsyncIterable<WidgetEvent> {
      const auth = getAuthContext(context);

      const eventStream = events.subscribe(auth.tenantId);

      try {
        for await (const event of eventStream) {
          if (context.signal.aborted) break; // Client disconnected
          yield eventToProto(event);
        }
      } finally {
        await eventStream.return?.();
      }
    },

    // Client streaming
    async importWidgets(
      request: AsyncIterable<ImportWidgetRequest>,
      context: CallContext,
    ): Promise<ImportWidgetsResponse> {
      const auth = getAuthContext(context);

      let importedCount = 0;
      let failedCount = 0;
      const errors: string[] = [];

      for await (const req of request) {
        try {
          await svc.create(auth.tenantId, auth.userId, {
            name: req.name,
            description: req.description,
          });
          importedCount++;
        } catch (err) {
          failedCount++;
          // AppError messages are user-safe; anything else stays in the server log
          const msg = isAppError(err) ? err.message : 'internal error';
          errors.push(`row ${importedCount + failedCount}: ${msg}`);
        }
      }

      return { importedCount, failedCount, errors };
    },

    // Bidirectional streaming (EditWidget in grpc-pattern.md) — not implemented by this archetype
    // eslint-disable-next-line require-yield
    async *editWidget(): AsyncIterable<EditWidgetResponse> {
      throw new ServerError(Status.UNIMPLEMENTED, 'EditWidget is not implemented');
    },
  };
}

// Domain → proto. The proto has no DRAFT status; add one to widget.proto if clients need it.
const STATUS_TO_PROTO: Record<Widget['status'], WidgetStatus> = {
  active: WidgetStatus.WIDGET_STATUS_ACTIVE,
  draft: WidgetStatus.WIDGET_STATUS_INACTIVE,
  archived: WidgetStatus.WIDGET_STATUS_ARCHIVED,
};

function toProto(w: Widget): WidgetMessage {
  return {
    id: w.id,
    tenantId: w.tenantId,
    name: w.name,
    description: w.description,
    status: STATUS_TO_PROTO[w.status],
    createdAt: w.createdAt,
    updatedAt: w.updatedAt,
    createdBy: w.createdBy,
    version: w.version,
  };
}

const EVENT_TYPE_TO_PROTO = {
  created: WidgetEventType.WIDGET_EVENT_TYPE_CREATED,
  updated: WidgetEventType.WIDGET_EVENT_TYPE_UPDATED,
  deleted: WidgetEventType.WIDGET_EVENT_TYPE_DELETED,
} as const;

function eventToProto(e: { type: keyof typeof EVENT_TYPE_TO_PROTO; widget: Widget }): WidgetEvent {
  return { type: EVENT_TYPE_TO_PROTO[e.type], widget: toProto(e.widget), timestamp: new Date() };
}
```

## Middleware / Interceptors

```typescript
// src/grpc/middleware.ts

import {
  ServerError,
  Status,
  type ServerMiddlewareCall,
  type CallContext,
} from 'nice-grpc';
import type { Logger } from 'pino';
import { validateJwt } from '../auth/jwt'; // your JWT verifier (auth-middleware-typescript.md)

export interface AuthContext {
  tenantId: string;
  userId: string;
  roles: string[];
}

const AUTH_CONTEXT_KEY = Symbol('authContext');

const SKIP_AUTH_METHODS = new Set([
  '/grpc.health.v1.Health/Check',
  '/grpc.health.v1.Health/Watch',
]);

/** Auth middleware: validates JWT from metadata, injects auth context. */
export async function* authMiddleware<Request, Response>(
  call: ServerMiddlewareCall<Request, Response>,
  context: CallContext,
): AsyncGenerator<Response, Response | void, undefined> {
  const method = call.method.path;

  if (SKIP_AUTH_METHODS.has(method)) {
    return yield* call.next(call.request, context);
  }

  // Metadata.get returns the value itself (a string for text keys) — not an array
  let token = context.metadata.get('authorization');

  if (!token) {
    throw new ServerError(Status.UNAUTHENTICATED, 'missing authorization');
  }

  if (token.startsWith('Bearer ')) {
    token = token.slice(7);
  }

  try {
    const claims = await validateJwt(token);
    (context as any)[AUTH_CONTEXT_KEY] = {
      tenantId: claims.tenantId,
      userId: claims.userId,
      roles: claims.roles,
    } as AuthContext;
  } catch {
    throw new ServerError(Status.UNAUTHENTICATED, 'invalid token');
  }

  return yield* call.next(call.request, context);
}

/** Logging middleware: logs every RPC with duration and status. */
export function createLoggingMiddleware(logger: Logger) {
  return async function* loggingMiddleware<Request, Response>(
    call: ServerMiddlewareCall<Request, Response>,
    context: CallContext,
  ): AsyncGenerator<Response, Response | void, undefined> {
    const method = call.method.path;
    const start = Date.now();

    try {
      const result = yield* call.next(call.request, context);
      logger.info({ method, durationMs: Date.now() - start, status: 'OK' }, 'grpc.request');
      return result;
    } catch (err) {
      const status = err instanceof ServerError ? err.code : Status.INTERNAL;
      logger.error(
        { method, durationMs: Date.now() - start, status: Status[status] },
        'grpc.request',
      );
      throw err;
    }
  };
}

/** Extract auth context from call context. */
export function getAuthContext(context: CallContext): AuthContext {
  const auth = (context as any)[AUTH_CONTEXT_KEY] as AuthContext | undefined;
  if (!auth) {
    throw new ServerError(Status.UNAUTHENTICATED, 'missing auth context');
  }
  return auth;
}
```

## Error Mapping

```typescript
// src/grpc/errors.ts

import { ServerError, Status } from 'nice-grpc';
import { isAppError } from '../errors'; // AppError + codes — error-handling-typescript.md

/** AppError code → gRPC status (grpc-pattern.md §Error Handling). */
const STATUS_BY_CODE: Record<string, Status> = {
  VALIDATION_FAILED: Status.INVALID_ARGUMENT,
  MALFORMED_REQUEST: Status.INVALID_ARGUMENT,
  UNAUTHENTICATED: Status.UNAUTHENTICATED,
  FORBIDDEN: Status.PERMISSION_DENIED,
  NOT_FOUND: Status.NOT_FOUND,
  CONFLICT: Status.ALREADY_EXISTS,
  BUSINESS_RULE_VIOLATION: Status.FAILED_PRECONDITION,
  RATE_LIMITED: Status.RESOURCE_EXHAUSTED,
  UNAVAILABLE: Status.UNAVAILABLE,
};

export function mapError(err: unknown): ServerError {
  const status = isAppError(err) ? STATUS_BY_CODE[err.code] : undefined;
  if (isAppError(err) && status !== undefined) {
    return new ServerError(status, err.message); // AppError messages are user-safe
  }
  return new ServerError(Status.INTERNAL, 'internal error'); // the cause goes to the log, not the client
}
```

## Server Startup

```typescript
// src/grpc/server.ts

import { createServer } from 'nice-grpc';
import { HealthDefinition, HealthServiceImpl, HealthState } from 'nice-grpc-server-health';
import type { Logger } from 'pino';

import { WidgetServiceDefinition } from '../gen/yourapp/v1/widget_service';
import type { WidgetService } from '../services/widget.service';
import { createWidgetServer, type WidgetEventSource } from './widget-server';
import { authMiddleware, createLoggingMiddleware } from './middleware';

export async function startGrpcServer(
  port: number,
  widgetSvc: WidgetService,
  widgetEvents: WidgetEventSource,
  logger: Logger,
): Promise<void> {
  // Middleware chain: each .use() wraps the ones added after it (logging sees auth failures)
  const server = createServer().use(createLoggingMiddleware(logger)).use(authMiddleware);

  // Register services
  server.add(WidgetServiceDefinition, createWidgetServer(widgetSvc, widgetEvents));

  // Health check (grpc.health.v1) — flip to 'unhealthy' when a dependency is down
  const health = HealthState();
  health.setStatus('healthy', 'yourapp.v1.WidgetService');
  health.setStatus('healthy'); // overall server health (service "")
  server.add(HealthDefinition, HealthServiceImpl(health));

  // Reflection (development only)
  if (process.env.ENABLE_REFLECTION === 'true') {
    // @grpc/reflection requires the raw grpc-js server
    // For nice-grpc, use the underlying server if available
    logger.info('gRPC reflection enabled');
  }

  const address = `0.0.0.0:${port}`;
  await server.listen(address);
  logger.info({ address }, 'gRPC server listening');

  // Graceful shutdown
  const shutdown = async () => {
    logger.info('shutting down gRPC server');
    await server.shutdown();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}
```

## Client Usage

```typescript
// src/grpc/client.ts

import { createChannel, createClient, Metadata } from 'nice-grpc';
import { WidgetServiceDefinition } from '../gen/yourapp/v1/widget_service';

const channel = createChannel('localhost:50051');
const client = createClient(WidgetServiceDefinition, channel);

export async function watchWidget(id: string, token: string): Promise<void> {
  const metadata = new Metadata({ authorization: `Bearer ${token}` });

  // Unary call with metadata
  const response = await client.getWidget({ id }, { metadata });
  console.log('widget:', response.widget?.name);

  // Server streaming
  for await (const event of client.watchWidgets({ statusFilter: 0 }, { metadata })) {
    console.log('event:', event);
  }
}
```

## Critical Rules

- Use `nice-grpc` over raw `@grpc/grpc-js` — much better TypeScript ergonomics
- Use `ts-proto` with `outputServices=nice-grpc` — generates typed service definitions
- Middleware uses `yield*` delegation — this is how nice-grpc composes middleware
- Use `ServerError` (not plain `Error`) for gRPC errors — nice-grpc maps them to status codes
- Server streaming uses `async *` generators — `yield` each message
- Client streaming receives `AsyncIterable<T>` — use `for await` to iterate
- Check `context.signal.aborted` in streaming loops — detect client disconnection
- Use `nice-grpc-server-health` for standard health check implementation
- Metadata keys MUST be lowercase — gRPC spec requirement
- Always call `server.shutdown()` on signal — waits for in-flight RPCs
