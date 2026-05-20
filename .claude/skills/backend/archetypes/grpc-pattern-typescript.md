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
      - outputPartialMethods=true
      - useExactTypes=false
      - esModuleInterop=true

# Generate
buf generate
```

## Server Implementation (nice-grpc)

```typescript
// src/grpc/widget-server.ts

import { ServerError, Status, CallContext } from 'nice-grpc';
import { WidgetServiceImplementation } from '../gen/yourapp/v1/widget_service';
import {
  CreateWidgetRequest,
  CreateWidgetResponse,
  GetWidgetRequest,
  GetWidgetResponse,
  ListWidgetsRequest,
  ListWidgetsResponse,
  WatchWidgetsRequest,
  WidgetEvent,
  ImportWidgetRequest,
  ImportWidgetsResponse,
} from '../gen/yourapp/v1/widget_service';
import { WidgetService } from '../services/widget.service';
import { AuthContext, getAuthContext } from './context';
import { mapError } from './errors';

export function createWidgetServer(svc: WidgetService): WidgetServiceImplementation {
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
        const result = await svc.create({
          tenantId: auth.tenantId,
          userId: auth.userId,
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

    async listWidgets(
      request: ListWidgetsRequest,
      context: CallContext,
    ): Promise<ListWidgetsResponse> {
      const auth = getAuthContext(context);

      const pageSize = Math.max(1, Math.min(request.pageSize || 20, 100));

      try {
        const result = await svc.list({
          tenantId: auth.tenantId,
          cursor: request.pageToken || undefined,
          pageSize,
          orderBy: request.orderBy || 'created_at desc',
        });

        return {
          widgets: result.items.map(toProto),
          nextPageToken: result.nextCursor ?? '',
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

      const eventStream = svc.subscribe(auth.tenantId);

      try {
        for await (const event of eventStream) {
          if (context.signal.aborted) break; // Client disconnected
          yield eventToProto(event);
        }
      } finally {
        eventStream.return?.();
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
          await svc.create({
            tenantId: auth.tenantId,
            userId: auth.userId,
            name: req.name,
            description: req.description,
          });
          importedCount++;
        } catch (err) {
          failedCount++;
          const msg = err instanceof Error ? err.message : String(err);
          errors.push(`row ${importedCount + failedCount}: ${msg}`);
        }
      }

      return { importedCount, failedCount, errors };
    },
  };
}
```

## Middleware / Interceptors

```typescript
// src/grpc/middleware.ts

import {
  ServerMiddlewareCall,
  CallContext,
  ServerError,
  Status,
  Metadata,
} from 'nice-grpc';
import { Logger } from 'pino';
import { validateJwt } from '../auth/jwt';

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

  const metadata = context.metadata as Metadata;
  let token = metadata.get('authorization')?.[0] as string | undefined;

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
import {
  NotFoundError,
  ConflictError,
  ValidationError,
  ForbiddenError,
} from '../errors';

export function mapError(err: unknown): ServerError {
  if (err instanceof NotFoundError) {
    return new ServerError(Status.NOT_FOUND, err.message);
  }
  if (err instanceof ConflictError) {
    return new ServerError(Status.ALREADY_EXISTS, err.message);
  }
  if (err instanceof ValidationError) {
    return new ServerError(Status.INVALID_ARGUMENT, err.message);
  }
  if (err instanceof ForbiddenError) {
    return new ServerError(Status.PERMISSION_DENIED, err.message);
  }
  return new ServerError(Status.INTERNAL, 'internal error');
}
```

## Server Startup

```typescript
// src/grpc/server.ts

import { createServer } from 'nice-grpc';
import { HealthDefinition, HealthImplementation, ServingStatusMap } from 'nice-grpc-server-health';
import { ServerReflectionService } from '@grpc/reflection';
import { Logger } from 'pino';

import { WidgetServiceDefinition } from '../gen/yourapp/v1/widget_service';
import { createWidgetServer } from './widget-server';
import { authMiddleware, createLoggingMiddleware } from './middleware';

export async function startGrpcServer(
  port: number,
  widgetSvc: WidgetService,
  logger: Logger,
): Promise<void> {
  const server = createServer();

  // Middleware chain (first registered runs first)
  server.use(createLoggingMiddleware(logger));
  server.use(authMiddleware);

  // Register services
  server.add(WidgetServiceDefinition, createWidgetServer(widgetSvc));

  // Health check
  const statusMap: ServingStatusMap = {
    'yourapp.v1.WidgetService': 'SERVING',
    '': 'SERVING', // overall server health
  };
  server.add(HealthDefinition, HealthImplementation(statusMap));

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

// Unary call with metadata
const response = await client.getWidget(
  { id: 'uuid-here' },
  { metadata: new Metadata({ authorization: `Bearer ${token}` }) },
);

// Server streaming
for await (const event of client.watchWidgets({ statusFilter: 0 })) {
  console.log('event:', event);
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
