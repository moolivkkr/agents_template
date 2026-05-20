---
skill: observability-typescript
description: TypeScript observability archetype — OpenTelemetry traces/metrics, pino structured logging, Express/NestJS instrumentation, Prisma/Redis spans, log-trace correlation, Docker Compose observability stack
version: "1.0"
tags:
  - typescript
  - observability
  - opentelemetry
  - tracing
  - metrics
  - logging
  - pino
  - archetype
  - backend
  - express
  - nestjs
---

# Observability Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `core/observability-patterns.md`. Both produce identical metric names, span naming conventions, and structured log formats so dashboards and alerts work across polyglot services.

Complete observability setup for TypeScript backend services (Express, NestJS). Every generated TypeScript service MUST follow this pattern.

---

## Table of Contents

1. [OpenTelemetry SDK Setup](#opentelemetry-sdk-setup)
2. [Auto-Instrumentation](#auto-instrumentation)
3. [Manual Traces](#manual-traces)
4. [Express Middleware for HTTP Spans](#express-middleware-for-http-spans)
5. [NestJS Interceptor for Controller Spans](#nestjs-interceptor-for-controller-spans)
6. [Prisma Query Span Instrumentation](#prisma-query-span-instrumentation)
7. [Drizzle Query Span Instrumentation](#drizzle-query-span-instrumentation)
8. [Redis Span Instrumentation](#redis-span-instrumentation)
9. [Error Recording on Spans](#error-recording-on-spans)
10. [Metrics — MeterProvider and OTLP Exporter](#metrics--meterprovider-and-otlp-exporter)
11. [Standard Metrics](#standard-metrics)
12. [Node.js Runtime Metrics](#nodejs-runtime-metrics)
13. [Custom Business Metrics](#custom-business-metrics)
14. [Prometheus Endpoint](#prometheus-endpoint)
15. [Structured Logging with pino](#structured-logging-with-pino)
16. [pino-http for Express](#pino-http-for-express)
17. [NestJS PinoLogger Integration](#nestjs-pinologger-integration)
18. [Log-Trace Correlation](#log-trace-correlation)
19. [Child Loggers for Request-Scoped Context](#child-loggers-for-request-scoped-context)
20. [PII Redaction](#pii-redaction)
21. [Full Setup — instrumentation.ts](#full-setup--instrumentationts)
22. [Full Setup — Express Application](#full-setup--express-application)
23. [Full Setup — NestJS Module](#full-setup--nestjs-module)
24. [Environment-Based Configuration](#environment-based-configuration)
25. [Docker Compose — Jaeger + Grafana](#docker-compose--jaeger--grafana)
26. [Graceful Shutdown](#graceful-shutdown)
27. [Critical Rules](#critical-rules)

---

## OpenTelemetry SDK Setup

The OTel SDK MUST be initialized before any other imports. Create `src/instrumentation.ts` and import it as the very first line in your entrypoint.

```typescript
// src/instrumentation.ts
// IMPORTANT: This file MUST be imported before ANY application code.
// In your entrypoint: import './instrumentation';

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-grpc';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { Resource } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_DEPLOYMENT_ENVIRONMENT_NAME,
} from '@opentelemetry/semantic-conventions';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';

// Enable OTel debug logging in development
if (process.env.OTEL_LOG_LEVEL === 'debug') {
  diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
}

const serviceName = process.env.OTEL_SERVICE_NAME || 'my-service';
const serviceVersion = process.env.APP_VERSION || '0.0.0';
const environment = process.env.NODE_ENV || 'development';

const sdk = new NodeSDK({
  resource: new Resource({
    [ATTR_SERVICE_NAME]: serviceName,
    [ATTR_SERVICE_VERSION]: serviceVersion,
    [ATTR_DEPLOYMENT_ENVIRONMENT_NAME]: environment,
  }),

  // Trace exporter — OTLP over gRPC to collector/Jaeger
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
  }),

  // Metric reader — periodic export to OTLP endpoint
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
    }),
    exportIntervalMillis: 15_000,
  }),

  // Auto-instrumentations (HTTP, Express, pg, Redis, etc.)
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': { enabled: false }, // too noisy
  })],
});

sdk.start();

// Graceful shutdown — flush all telemetry before exit
const shutdown = async () => {
  try {
    await sdk.shutdown();
  } catch (err) {
    console.error('OTel SDK shutdown error', err);
  }
};

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

export { sdk };
```

**Package dependencies:**

```json
{
  "@opentelemetry/sdk-node": "^0.57.0",
  "@opentelemetry/api": "^1.9.0",
  "@opentelemetry/auto-instrumentations-node": "^0.56.0",
  "@opentelemetry/exporter-trace-otlp-grpc": "^0.57.0",
  "@opentelemetry/exporter-metrics-otlp-grpc": "^0.57.0",
  "@opentelemetry/sdk-metrics": "^1.30.0",
  "@opentelemetry/resources": "^1.30.0",
  "@opentelemetry/semantic-conventions": "^1.28.0"
}
```

---

## Auto-Instrumentation

`@opentelemetry/auto-instrumentations-node` automatically instruments:

| Library | What it captures |
|---------|-----------------|
| `http` / `https` | Inbound and outbound HTTP requests |
| `express` | Route-level spans with route pattern |
| `@nestjs/core` | Controller and handler spans |
| `pg` / `mysql2` | Database query spans |
| `ioredis` / `redis` | Redis command spans |
| `@prisma/client` | Prisma query spans (via `prisma-instrumentation`) |
| `graphql` | GraphQL resolver spans |
| `grpc` | gRPC call spans |

For Prisma, add the dedicated instrumentation:

```typescript
import { PrismaInstrumentation } from '@prisma/instrumentation';

// Add to instrumentations array in NodeSDK config:
instrumentations: [
  getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': { enabled: false },
  }),
  new PrismaInstrumentation(),
],
```

---

## Manual Traces

Use manual spans when auto-instrumentation does not cover a code path (business logic, complex processing, external SDK calls).

```typescript
// src/lib/tracer.ts
import { trace, Span, SpanStatusCode, context } from '@opentelemetry/api';

// One tracer per service — reuse everywhere
export const tracer = trace.getTracer('my-service');

// Helper: wrap async work in a span
export async function withSpan<T>(
  name: string,
  attributes: Record<string, string | number | boolean>,
  fn: (span: Span) => Promise<T>,
): Promise<T> {
  return tracer.startActiveSpan(name, async (span) => {
    try {
      for (const [key, value] of Object.entries(attributes)) {
        span.setAttribute(key, value);
      }
      const result = await fn(span);
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: (err as Error).message,
      });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

**Usage in service layer:**

```typescript
// src/services/order.service.ts
import { withSpan, tracer } from '../lib/tracer';

export class OrderService {
  async createOrder(tenantId: string, req: CreateOrderDto): Promise<Order> {
    return withSpan(
      'OrderService.createOrder',
      { tenant_id: tenantId },
      async (span) => {
        // Validate
        const validated = this.validate(req);

        // Save — creates a child span automatically (Prisma instrumentation)
        const order = await this.orderRepo.create(tenantId, validated);

        // Add result attributes
        span.setAttribute('order_id', order.id);
        span.setAttribute('order_total', order.total);

        // Publish event — manual child span
        await withSpan(
          'EventBus.publish',
          { event_type: 'order.created', order_id: order.id },
          async () => {
            await this.eventBus.publish('order.created', order);
          },
        );

        return order;
      },
    );
  }
}
```

**Span attributes to always include:**

| Attribute | When | Example |
|-----------|------|---------|
| `tenant_id` | Every span | `"tenant_abc"` |
| `user_id` | When available | `"user_123"` |
| `request_id` | HTTP handlers | `"req_xyz"` |
| `order_id`, `entity_id` | After entity creation/lookup | `"ord_456"` |
| `db.system` | DB spans | `"postgresql"` |
| `db.operation` | DB spans | `"INSERT"` |
| `db.sql.table` | DB spans | `"orders"` |

**Span naming convention (same as Go archetype):**

- HTTP handlers: `HTTP {METHOD} {path}` (e.g., `HTTP POST /api/v1/orders`)
- Service methods: `{ServiceName}.{methodName}` (e.g., `OrderService.createOrder`)
- Repository calls: `{system}.{table}.{operation}` (e.g., `postgres.orders.insert`)
- External calls: `{service}.{endpoint}` (e.g., `payment-gateway.charge`)
- Events: `EventBus.publish` or `EventBus.consume`

---

## Express Middleware for HTTP Spans

Auto-instrumentation handles basic HTTP spans. This middleware enriches them with tenant and business context.

```typescript
// src/middleware/tracing.middleware.ts
import { trace, SpanStatusCode } from '@opentelemetry/api';
import { Request, Response, NextFunction } from 'express';

export function tracingMiddleware(req: Request, res: Response, next: NextFunction): void {
  const span = trace.getActiveSpan();
  if (!span) {
    next();
    return;
  }

  // Enrich auto-instrumented span with business attributes
  span.setAttribute('tenant_id', req.tenantId || 'unknown');
  span.setAttribute('request_id', req.id);
  if (req.userId) {
    span.setAttribute('user_id', req.userId);
  }

  // Update span name to include route pattern (more useful than raw URL)
  // This runs after route matching, so req.route is available
  res.on('finish', () => {
    const routePattern = req.route?.path || req.path;
    span.updateName(`HTTP ${req.method} ${routePattern}`);
    span.setAttribute('http.status_code', res.statusCode);

    if (res.statusCode >= 500) {
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: `HTTP ${res.statusCode}`,
      });
    }
  });

  next();
}
```

---

## NestJS Interceptor for Controller Spans

```typescript
// src/interceptors/tracing.interceptor.ts
import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable, tap } from 'rxjs';
import { trace, SpanStatusCode } from '@opentelemetry/api';

@Injectable()
export class TracingInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const span = trace.getActiveSpan();
    if (!span) {
      return next.handle();
    }

    const req = context.switchToHttp().getRequest();
    const controllerName = context.getClass().name;
    const handlerName = context.getHandler().name;

    // Enrich span
    span.updateName(`${controllerName}.${handlerName}`);
    span.setAttribute('tenant_id', req.tenantId || 'unknown');
    span.setAttribute('request_id', req.id);
    span.setAttribute('nestjs.controller', controllerName);
    span.setAttribute('nestjs.handler', handlerName);

    if (req.userId) {
      span.setAttribute('user_id', req.userId);
    }

    return next.handle().pipe(
      tap({
        error: (err: Error) => {
          span.recordException(err);
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: err.message,
          });
        },
      }),
    );
  }
}
```

**Register globally in `app.module.ts`:**

```typescript
import { APP_INTERCEPTOR } from '@nestjs/core';
import { TracingInterceptor } from './interceptors/tracing.interceptor';

@Module({
  providers: [
    { provide: APP_INTERCEPTOR, useClass: TracingInterceptor },
  ],
})
export class AppModule {}
```

---

## Prisma Query Span Instrumentation

Prisma query tracing via `@prisma/instrumentation` is set up in the SDK config above. To add query-level logging and slow-query detection:

```typescript
// src/lib/prisma.ts
import { PrismaClient } from '@prisma/client';
import { trace } from '@opentelemetry/api';
import pino from 'pino';

const logger = pino({ name: 'prisma' });

export const prisma = new PrismaClient({
  log: [
    { level: 'query', emit: 'event' },
    { level: 'error', emit: 'event' },
    { level: 'warn', emit: 'event' },
  ],
});

// Log slow queries
const SLOW_QUERY_THRESHOLD_MS = 500;

prisma.$on('query', (e) => {
  const span = trace.getActiveSpan();
  if (span) {
    span.setAttribute('db.statement', e.query);
    span.setAttribute('db.duration_ms', e.duration);
  }

  if (e.duration > SLOW_QUERY_THRESHOLD_MS) {
    logger.warn({
      query: e.query,
      duration_ms: e.duration,
      params: e.params,
      target: e.target,
    }, 'slow query detected');
  }
});

prisma.$on('error', (e) => {
  logger.error({ target: e.target, message: e.message }, 'prisma error');
});
```

---

## Drizzle Query Span Instrumentation

Drizzle does not have built-in OTel integration. Wrap the query execution with manual spans:

```typescript
// src/lib/drizzle.ts
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import { tracer } from './tracer';
import { SpanStatusCode } from '@opentelemetry/api';
import pino from 'pino';

const logger = pino({ name: 'drizzle' });
const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// The pg pool is auto-instrumented by @opentelemetry/instrumentation-pg,
// so basic query spans are created automatically.
// For Drizzle-specific context, wrap repository methods:

export const db = drizzle(pool);

// Repository pattern with manual spans for Drizzle
export async function findOrderById(tenantId: string, orderId: string) {
  return tracer.startActiveSpan('postgres.orders.select', async (span) => {
    try {
      span.setAttribute('db.system', 'postgresql');
      span.setAttribute('db.operation', 'SELECT');
      span.setAttribute('db.sql.table', 'orders');
      span.setAttribute('tenant_id', tenantId);

      const result = await db
        .select()
        .from(orders)
        .where(and(eq(orders.tenantId, tenantId), eq(orders.id, orderId)));

      span.setAttribute('db.rows_affected', result.length);
      return result[0] ?? null;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: (err as Error).message });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

---

## Redis Span Instrumentation

`@opentelemetry/instrumentation-ioredis` auto-instruments ioredis commands. Add business context:

```typescript
// src/lib/redis.ts
import Redis from 'ioredis';
import { tracer } from './tracer';
import pino from 'pino';

const logger = pino({ name: 'redis' });

export const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    const delay = Math.min(times * 100, 3000);
    logger.warn({ attempt: times, delay_ms: delay }, 'redis reconnecting');
    return delay;
  },
});

redis.on('error', (err) => {
  logger.error({ err }, 'redis connection error');
});

redis.on('connect', () => {
  logger.info('redis connected');
});

// Cache helper with manual span for business context
export async function cacheGet<T>(
  tenantId: string,
  key: string,
): Promise<T | null> {
  return tracer.startActiveSpan('redis.cache.get', async (span) => {
    try {
      span.setAttribute('tenant_id', tenantId);
      span.setAttribute('cache.key', key);
      const raw = await redis.get(`${tenantId}:${key}`);
      span.setAttribute('cache.hit', raw !== null);
      return raw ? (JSON.parse(raw) as T) : null;
    } finally {
      span.end();
    }
  });
}

export async function cacheSet(
  tenantId: string,
  key: string,
  value: unknown,
  ttlSeconds: number,
): Promise<void> {
  return tracer.startActiveSpan('redis.cache.set', async (span) => {
    try {
      span.setAttribute('tenant_id', tenantId);
      span.setAttribute('cache.key', key);
      span.setAttribute('cache.ttl_seconds', ttlSeconds);
      await redis.set(`${tenantId}:${key}`, JSON.stringify(value), 'EX', ttlSeconds);
    } finally {
      span.end();
    }
  });
}
```

---

## Error Recording on Spans

Every span that encounters an error MUST record it. Never silently fail.

```typescript
import { Span, SpanStatusCode } from '@opentelemetry/api';

// Pattern 1: recordException + setStatus (use for caught errors you re-throw)
function recordSpanError(span: Span, err: Error): void {
  span.recordException(err);
  span.setStatus({
    code: SpanStatusCode.ERROR,
    message: err.message,
  });
}

// Pattern 2: Add error attributes for domain errors (use for expected errors like 404)
function recordDomainError(span: Span, err: AppError): void {
  span.setAttribute('error.code', err.code);
  span.setAttribute('error.category', err.category);
  // Only set span status to ERROR for unexpected errors (5xx)
  if (err.httpStatus >= 500) {
    span.recordException(err);
    span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
  }
}

// Pattern 3: withSpan helper (preferred — handles errors automatically)
// See withSpan() in Manual Traces section above.
```

---

## Metrics — MeterProvider and OTLP Exporter

The MeterProvider is configured in `instrumentation.ts` above. Access the meter throughout the app:

```typescript
// src/lib/metrics.ts
import { metrics, ValueType } from '@opentelemetry/api';

const meter = metrics.getMeter('my-service');

// --- HTTP metrics (augment auto-instrumented metrics with business attributes) ---

export const requestTotal = meter.createCounter('http.server.request.total', {
  description: 'Total HTTP requests',
  unit: '{request}',
  valueType: ValueType.INT,
});

export const requestDuration = meter.createHistogram('http.server.request.duration', {
  description: 'HTTP request duration in seconds',
  unit: 's',
  advice: {
    explicitBucketBoundaries: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  },
});

export const activeRequests = meter.createUpDownCounter('http.server.active_requests', {
  description: 'Currently active HTTP requests',
  unit: '{request}',
  valueType: ValueType.INT,
});

// --- Database metrics ---

export const dbQueryDuration = meter.createHistogram('db.query.duration', {
  description: 'Database query duration in seconds',
  unit: 's',
  advice: {
    explicitBucketBoundaries: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
  },
});

// --- External call metrics ---

export const externalRequestDuration = meter.createHistogram('external.request.duration', {
  description: 'External service call duration in seconds',
  unit: 's',
});
```

---

## Standard Metrics

Express metrics middleware:

```typescript
// src/middleware/metrics.middleware.ts
import { Request, Response, NextFunction } from 'express';
import { requestTotal, requestDuration, activeRequests } from '../lib/metrics';

export function metricsMiddleware(req: Request, res: Response, next: NextFunction): void {
  const start = process.hrtime.bigint();
  const attrs = {
    tenant_id: req.tenantId || 'unknown',
    method: req.method,
  };

  activeRequests.add(1, attrs);

  res.on('finish', () => {
    const durationNs = Number(process.hrtime.bigint() - start);
    const durationSec = durationNs / 1e9;

    const finalAttrs = {
      ...attrs,
      endpoint: req.route?.path || req.path,
      status_code: res.statusCode,
    };

    requestTotal.add(1, finalAttrs);
    requestDuration.record(durationSec, finalAttrs);
    activeRequests.add(-1, attrs);
  });

  next();
}
```

---

## Node.js Runtime Metrics

Expose event loop lag, active handles, and heap usage as observable gauges.

```typescript
// src/lib/runtime-metrics.ts
import { metrics, ValueType } from '@opentelemetry/api';
import { monitorEventLoopDelay } from 'node:perf_hooks';

const meter = metrics.getMeter('nodejs.runtime');

// --- Event Loop Lag ---
const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

meter.createObservableGauge('nodejs.eventloop.lag.p50', {
  description: 'Event loop lag p50 in milliseconds',
  unit: 'ms',
  valueType: ValueType.DOUBLE,
}).addCallback((gauge) => {
  gauge.observe(histogram.percentile(50) / 1e6); // ns to ms
});

meter.createObservableGauge('nodejs.eventloop.lag.p99', {
  description: 'Event loop lag p99 in milliseconds',
  unit: 'ms',
  valueType: ValueType.DOUBLE,
}).addCallback((gauge) => {
  gauge.observe(histogram.percentile(99) / 1e6);
});

meter.createObservableGauge('nodejs.eventloop.lag.max', {
  description: 'Event loop lag max in milliseconds',
  unit: 'ms',
  valueType: ValueType.DOUBLE,
}).addCallback((gauge) => {
  gauge.observe(histogram.max / 1e6);
});

// --- Heap Memory ---
meter.createObservableGauge('nodejs.heap.used', {
  description: 'V8 heap used bytes',
  unit: 'By',
  valueType: ValueType.INT,
}).addCallback((gauge) => {
  gauge.observe(process.memoryUsage().heapUsed);
});

meter.createObservableGauge('nodejs.heap.total', {
  description: 'V8 heap total bytes',
  unit: 'By',
  valueType: ValueType.INT,
}).addCallback((gauge) => {
  gauge.observe(process.memoryUsage().heapTotal);
});

meter.createObservableGauge('nodejs.rss', {
  description: 'Resident set size bytes',
  unit: 'By',
  valueType: ValueType.INT,
}).addCallback((gauge) => {
  gauge.observe(process.memoryUsage().rss);
});

// --- Active Handles & Requests ---
meter.createObservableGauge('nodejs.active_handles', {
  description: 'Number of active handles',
  unit: '{handle}',
  valueType: ValueType.INT,
}).addCallback((gauge) => {
  // @ts-expect-error — _getActiveHandles is not in the type definitions
  gauge.observe(process._getActiveHandles().length);
});

meter.createObservableGauge('nodejs.active_requests', {
  description: 'Number of active libuv requests',
  unit: '{request}',
  valueType: ValueType.INT,
}).addCallback((gauge) => {
  // @ts-expect-error — _getActiveRequests is not in the type definitions
  gauge.observe(process._getActiveRequests().length);
});
```

Import this module once in your entrypoint (after `instrumentation.ts`):

```typescript
// src/main.ts
import './instrumentation';
import './lib/runtime-metrics';
// ... rest of app
```

---

## Custom Business Metrics

```typescript
// src/lib/business-metrics.ts
import { metrics, ValueType } from '@opentelemetry/api';

const meter = metrics.getMeter('business');

export const orderTotal = meter.createCounter('business.order.total', {
  description: 'Total order value processed',
  unit: 'USD',
  valueType: ValueType.DOUBLE,
});

export const orderCount = meter.createCounter('business.order.count', {
  description: 'Total orders created',
  unit: '{order}',
  valueType: ValueType.INT,
});

export const signupCount = meter.createCounter('business.signup.count', {
  description: 'Total user signups',
  unit: '{user}',
  valueType: ValueType.INT,
});

export const activeUsers = meter.createObservableGauge('business.active_users', {
  description: 'Currently active users (from session store)',
  unit: '{user}',
  valueType: ValueType.INT,
});

// Usage in service:
// orderTotal.add(order.total, { tenant_id: tenantId, payment_method: 'card' });
// orderCount.add(1, { tenant_id: tenantId });
```

---

## Prometheus Endpoint

If your infrastructure scrapes Prometheus instead of using OTLP for metrics, use the OTel Prometheus exporter:

```typescript
// src/lib/prometheus.ts
import { PrometheusExporter } from '@opentelemetry/exporter-prometheus';

// Replace the PeriodicExportingMetricReader in instrumentation.ts with:
const prometheusExporter = new PrometheusExporter({
  port: 9464, // default Prometheus port
  endpoint: '/metrics',
});

// In NodeSDK config:
// metricReader: prometheusExporter,
```

Alternatively, if you need both OTLP and Prometheus, use `prom-client` alongside OTel:

```typescript
// src/routes/metrics.ts
import { Router } from 'express';
import promClient from 'prom-client';

// Collect default Node.js metrics
promClient.collectDefaultMetrics({ prefix: 'nodejs_' });

const router = Router();

router.get('/metrics', async (_req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.end(await promClient.register.metrics());
});

export { router as metricsRouter };
```

**Package dependencies for Prometheus:**

```json
{
  "@opentelemetry/exporter-prometheus": "^0.57.0",
  "prom-client": "^15.1.0"
}
```

---

## Structured Logging with pino

```typescript
// src/lib/logger.ts
import pino, { Logger } from 'pino';

const isProduction = process.env.NODE_ENV === 'production';

export const logger: Logger = pino({
  level: process.env.LOG_LEVEL || (isProduction ? 'info' : 'debug'),

  // JSON output in production, pretty-printed in development
  ...(isProduction
    ? {}
    : { transport: { target: 'pino-pretty', options: { colorize: true } } }),

  // Consistent field names
  formatters: {
    level: (label) => ({ level: label }),
  },

  // Base fields on every log line
  base: {
    service: process.env.OTEL_SERVICE_NAME || 'my-service',
    version: process.env.APP_VERSION || '0.0.0',
    env: process.env.NODE_ENV || 'development',
  },

  // ISO timestamp
  timestamp: pino.stdTimeFunctions.isoTime,

  // Redact sensitive fields (see PII Redaction section)
  redact: {
    paths: [
      'req.headers.authorization',
      'req.headers.cookie',
      'password',
      'ssn',
      'creditCard',
      'token',
      'secret',
      '*.password',
      '*.token',
      '*.secret',
      '*.ssn',
      '*.creditCard',
    ],
    censor: '[REDACTED]',
  },
});

// Log level reference:
// trace  — ultra-verbose, never in production
// debug  — troubleshooting, off in production by default
// info   — business events (one per state transition)
// warn   — handled degradation (circuit breaker, retry, fallback)
// error  — needs investigation, triggers alerts
// fatal  — process is crashing
```

---

## pino-http for Express

```typescript
// src/middleware/logging.middleware.ts
import pinoHttp from 'pino-http';
import { logger } from '../lib/logger';
import { randomUUID } from 'node:crypto';

export const httpLogger = pinoHttp({
  logger,

  // Generate request ID if not provided
  genReqId: (req) => {
    return (req.headers['x-request-id'] as string) || `req_${randomUUID()}`;
  },

  // Custom log message
  customLogLevel: (_req, res, err) => {
    if (err || (res.statusCode >= 500)) return 'error';
    if (res.statusCode >= 400) return 'warn';
    return 'info';
  },

  // Customize what's serialized from request/response
  serializers: {
    req: (req) => ({
      method: req.method,
      url: req.url,
      query: req.query,
      // Do NOT log headers or body at info level
    }),
    res: (res) => ({
      statusCode: res.statusCode,
    }),
  },

  // Add custom attributes to every request log
  customProps: (req) => ({
    tenant_id: (req as any).tenantId || 'unknown',
    request_id: req.id,
  }),

  // Quiet health check endpoints
  autoLogging: {
    ignore: (req) => {
      return req.url === '/healthz' || req.url === '/readyz';
    },
  },
});
```

**Usage in Express app:**

```typescript
app.use(httpLogger);
```

This automatically logs every request completion with method, URL, status code, response time, and the custom props (tenant_id, request_id).

---

## NestJS PinoLogger Integration

```typescript
// src/logger/logger.module.ts
import { Module } from '@nestjs/common';
import { LoggerModule as PinoLoggerModule } from 'nestjs-pino';

@Module({
  imports: [
    PinoLoggerModule.forRoot({
      pinoHttp: {
        level: process.env.LOG_LEVEL || 'info',
        transport:
          process.env.NODE_ENV !== 'production'
            ? { target: 'pino-pretty', options: { colorize: true } }
            : undefined,
        formatters: {
          level: (label) => ({ level: label }),
        },
        base: {
          service: process.env.OTEL_SERVICE_NAME || 'my-service',
          version: process.env.APP_VERSION || '0.0.0',
        },
        timestamp: () => `,"time":"${new Date().toISOString()}"`,
        redact: {
          paths: [
            'req.headers.authorization',
            'req.headers.cookie',
            '*.password',
            '*.token',
            '*.secret',
          ],
          censor: '[REDACTED]',
        },
        autoLogging: {
          ignore: (req) => req.url === '/healthz' || req.url === '/readyz',
        },
      },
    }),
  ],
})
export class LoggerModule {}
```

**Usage in `main.ts`:**

```typescript
import { Logger } from 'nestjs-pino';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bufferLogs: true });
  app.useLogger(app.get(Logger));
  // ...
}
```

**Usage in services:**

```typescript
import { PinoLogger, InjectPinoLogger } from 'nestjs-pino';

@Injectable()
export class OrderService {
  constructor(
    @InjectPinoLogger(OrderService.name)
    private readonly logger: PinoLogger,
  ) {}

  async createOrder(tenantId: string, req: CreateOrderDto): Promise<Order> {
    this.logger.info({ tenant_id: tenantId, order: req }, 'creating order');
    // ...
  }
}
```

**Package dependencies for NestJS:**

```json
{
  "nestjs-pino": "^4.1.0",
  "pino-http": "^10.3.0",
  "pino-pretty": "^13.0.0"
}
```

---

## Log-Trace Correlation

Connect every log line to its trace span using `trace_id` and `span_id`. Use `pino-opentelemetry-transport` for automatic injection.

```typescript
// src/lib/logger.ts (production version with trace correlation)
import pino from 'pino';

const isProduction = process.env.NODE_ENV === 'production';

export const logger = pino({
  level: process.env.LOG_LEVEL || (isProduction ? 'info' : 'debug'),

  formatters: {
    level: (label) => ({ level: label }),
  },

  base: {
    service: process.env.OTEL_SERVICE_NAME || 'my-service',
    version: process.env.APP_VERSION || '0.0.0',
  },

  timestamp: pino.stdTimeFunctions.isoTime,

  // In production, use pino-opentelemetry-transport to inject trace_id/span_id
  transport: isProduction
    ? {
        target: 'pino-opentelemetry-transport',
        options: {
          // Injects trace_id and span_id from active OTel context
          // into every log line automatically
        },
      }
    : {
        target: 'pino-pretty',
        options: { colorize: true },
      },

  // Mixin adds trace context to every log line (alternative to transport approach)
  mixin() {
    const { trace, context } = require('@opentelemetry/api');
    const span = trace.getSpan(context.active());
    if (span) {
      const spanContext = span.spanContext();
      return {
        trace_id: spanContext.traceId,
        span_id: spanContext.spanId,
        trace_flags: spanContext.traceFlags,
      };
    }
    return {};
  },

  redact: {
    paths: [
      'req.headers.authorization',
      'req.headers.cookie',
      '*.password',
      '*.token',
      '*.secret',
    ],
    censor: '[REDACTED]',
  },
});
```

**Package dependency:**

```json
{
  "pino-opentelemetry-transport": "^0.5.0"
}
```

**Resulting log output (JSON):**

```json
{
  "level": "info",
  "time": "2024-01-15T10:30:00.000Z",
  "service": "order-service",
  "version": "1.2.3",
  "trace_id": "abc123def456789012345678abcdef01",
  "span_id": "1234567890abcdef",
  "tenant_id": "tenant_abc",
  "request_id": "req_xyz",
  "order_id": "ord_123",
  "msg": "order created"
}
```

In Grafana, clicking on a log line's `trace_id` opens the corresponding trace in Jaeger/Tempo.

---

## Child Loggers for Request-Scoped Context

Create a child logger per request. This avoids passing tenant_id/request_id to every log call.

```typescript
// src/middleware/request-context.middleware.ts
import { Request, Response, NextFunction } from 'express';
import { logger } from '../lib/logger';
import { randomUUID } from 'node:crypto';

declare global {
  namespace Express {
    interface Request {
      tenantId: string;
      userId?: string;
      log: pino.Logger;
      id: string;
    }
  }
}

export function requestContextMiddleware(req: Request, res: Response, next: NextFunction): void {
  // Extract or generate request ID
  const requestId = (req.headers['x-request-id'] as string) || `req_${randomUUID()}`;
  req.id = requestId;
  res.setHeader('X-Request-ID', requestId);

  // Extract tenant
  const tenantId = req.headers['x-tenant-id'] as string;
  if (!tenantId) {
    res.status(400).json({ error: { code: 'MISSING_TENANT_ID', message: 'X-Tenant-ID header is required' } });
    return;
  }
  req.tenantId = tenantId;

  // Extract user (set by auth middleware)
  req.userId = (req as any).auth?.userId;

  // Child logger with request context — all subsequent logs include these fields
  req.log = logger.child({
    request_id: requestId,
    tenant_id: tenantId,
    ...(req.userId && { user_id: req.userId }),
  });

  next();
}

// Usage in handlers and services:
// req.log.info({ order_id: order.id }, 'order created');
// req.log.warn({ retries: 3 }, 'payment retry succeeded');
// req.log.error({ err }, 'failed to process order');
```

---

## PII Redaction

pino's `redact` option removes sensitive fields before serialization. Configure at logger creation:

```typescript
const logger = pino({
  redact: {
    paths: [
      // Auth headers
      'req.headers.authorization',
      'req.headers.cookie',
      'req.headers["x-api-key"]',

      // Common PII field names (at any depth)
      '*.password',
      '*.newPassword',
      '*.oldPassword',
      '*.token',
      '*.refreshToken',
      '*.accessToken',
      '*.secret',
      '*.apiKey',
      '*.ssn',
      '*.creditCard',
      '*.creditCardNumber',
      '*.cvv',
      '*.email',           // redact if your policy requires it
      '*.phoneNumber',     // redact if your policy requires it

      // Specific paths
      'body.password',
      'body.creditCard',
      'user.ssn',
    ],
    censor: '[REDACTED]',
  },
});
```

**Test redaction works:**

```typescript
logger.info({
  user: { name: 'Alice', password: 'secret123', email: 'alice@example.com' },
}, 'user signup');

// Output:
// { "user": { "name": "Alice", "password": "[REDACTED]", "email": "[REDACTED]" }, "msg": "user signup" }
```

---

## Full Setup — instrumentation.ts

This is the complete instrumentation file. Copy this as-is into `src/instrumentation.ts`.

```typescript
// src/instrumentation.ts
// ============================================================
// MUST be the first import in src/main.ts:
//   import './instrumentation';
// ============================================================

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-grpc';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { Resource } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_DEPLOYMENT_ENVIRONMENT_NAME,
} from '@opentelemetry/semantic-conventions';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';

// Optional: Prisma instrumentation
// import { PrismaInstrumentation } from '@prisma/instrumentation';

if (process.env.OTEL_LOG_LEVEL === 'debug') {
  diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
}

const otlpEndpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317';

const sdk = new NodeSDK({
  resource: new Resource({
    [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'my-service',
    [ATTR_SERVICE_VERSION]: process.env.APP_VERSION || '0.0.0',
    [ATTR_DEPLOYMENT_ENVIRONMENT_NAME]: process.env.NODE_ENV || 'development',
  }),

  traceExporter: new OTLPTraceExporter({ url: otlpEndpoint }),

  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({ url: otlpEndpoint }),
    exportIntervalMillis: Number(process.env.OTEL_METRIC_EXPORT_INTERVAL || 15_000),
  }),

  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false },
      '@opentelemetry/instrumentation-dns': { enabled: false },
    }),
    // new PrismaInstrumentation(), // Uncomment if using Prisma
  ],
});

sdk.start();

async function shutdown(): Promise<void> {
  try {
    await sdk.shutdown();
    console.log('OTel SDK shut down successfully');
  } catch (err) {
    console.error('OTel SDK shutdown error:', err);
  } finally {
    process.exit(0);
  }
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

export { sdk };
```

---

## Full Setup — Express Application

```typescript
// src/main.ts
import './instrumentation';       // MUST be first
import './lib/runtime-metrics';    // Register Node.js runtime metrics

import express from 'express';
import { logger } from './lib/logger';
import { httpLogger } from './middleware/logging.middleware';
import { requestContextMiddleware } from './middleware/request-context.middleware';
import { tracingMiddleware } from './middleware/tracing.middleware';
import { metricsMiddleware } from './middleware/metrics.middleware';
import { errorHandler } from './middleware/error-handler.middleware';
import { healthRouter } from './routes/health';
import { orderRouter } from './routes/orders';

const app = express();
const port = Number(process.env.PORT) || 3000;

// --- Middleware order matters ---

// 1. Body parsing
app.use(express.json({ limit: '1mb' }));

// 2. HTTP request/response logging (pino-http)
app.use(httpLogger);

// 3. Health checks (before auth/tenant — no tenant_id required)
app.use(healthRouter);

// 4. Request context (request ID, tenant ID, child logger)
app.use(requestContextMiddleware);

// 5. Tracing enrichment (adds tenant_id to active span)
app.use(tracingMiddleware);

// 6. Metrics (request counters, duration histograms)
app.use(metricsMiddleware);

// 7. Routes
app.use('/api/v1/orders', orderRouter);

// 8. Error handler (must be last)
app.use(errorHandler);

// --- Start server ---
const server = app.listen(port, () => {
  logger.info({ port, env: process.env.NODE_ENV }, 'server started');
});

// Graceful shutdown
async function gracefulShutdown(signal: string): Promise<void> {
  logger.info({ signal }, 'shutting down gracefully');

  server.close(() => {
    logger.info('HTTP server closed');
    // OTel SDK shutdown is handled in instrumentation.ts
  });

  // Force exit after 30 seconds
  setTimeout(() => {
    logger.error('forced shutdown after timeout');
    process.exit(1);
  }, 30_000).unref();
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

---

## Full Setup — NestJS Module

```typescript
// src/main.ts
import './instrumentation';       // MUST be first
import './lib/runtime-metrics';

import { NestFactory } from '@nestjs/core';
import { Logger } from 'nestjs-pino';
import { AppModule } from './app.module';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, { bufferLogs: true });
  app.useLogger(app.get(Logger));
  app.enableShutdownHooks();

  const port = Number(process.env.PORT) || 3000;
  await app.listen(port);

  const logger = app.get(Logger);
  logger.log(`Server running on port ${port}`);
}

bootstrap();
```

```typescript
// src/app.module.ts
import { Module } from '@nestjs/common';
import { APP_INTERCEPTOR } from '@nestjs/core';
import { LoggerModule } from './logger/logger.module';
import { TracingInterceptor } from './interceptors/tracing.interceptor';
import { OrderModule } from './modules/order/order.module';
import { HealthModule } from './modules/health/health.module';

@Module({
  imports: [
    LoggerModule,       // pino logging for NestJS
    HealthModule,
    OrderModule,
  ],
  providers: [
    { provide: APP_INTERCEPTOR, useClass: TracingInterceptor },
  ],
})
export class AppModule {}
```

---

## Environment-Based Configuration

```bash
# .env.example

# --- OpenTelemetry ---
OTEL_SERVICE_NAME=order-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_LOG_LEVEL=info                          # Set to "debug" for OTel SDK debug logs
OTEL_METRIC_EXPORT_INTERVAL=15000            # Metric export interval in ms

# --- Application ---
APP_VERSION=1.0.0
NODE_ENV=production
PORT=3000
LOG_LEVEL=info                               # pino log level: trace|debug|info|warn|error|fatal

# --- Database ---
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb

# --- Redis ---
REDIS_URL=redis://localhost:6379
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_SERVICE_NAME` | `my-service` | Service name in traces/metrics |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTel collector endpoint (gRPC) |
| `OTEL_LOG_LEVEL` | `info` | OTel SDK internal logging level |
| `OTEL_METRIC_EXPORT_INTERVAL` | `15000` | How often to export metrics (ms) |
| `LOG_LEVEL` | `info` (prod), `debug` (dev) | pino log level |
| `NODE_ENV` | `development` | Controls pretty-printing, debug logging |

---

## Docker Compose — Jaeger + Grafana

```yaml
# docker-compose.observability.yml
# Start alongside your app: docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d

services:
  # --- Jaeger (traces) ---
  jaeger:
    image: jaegertracing/all-in-one:1.62
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC receiver
      - "4318:4318"     # OTLP HTTP receiver
    environment:
      COLLECTOR_OTLP_ENABLED: "true"

  # --- Prometheus (metrics) ---
  prometheus:
    image: prom/prometheus:v2.54.0
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=7d'

  # --- Grafana (dashboards) ---
  grafana:
    image: grafana/grafana:11.3.0
    ports:
      - "3001:3000"     # Grafana UI (3001 to avoid conflict with app)
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
    volumes:
      - grafana-data:/var/lib/grafana
      - ./observability/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
      - jaeger

  # --- Loki (logs — optional) ---
  loki:
    image: grafana/loki:3.3.0
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml

volumes:
  grafana-data:
```

```yaml
# observability/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['host.docker.internal:9464']   # Prometheus exporter port
    metrics_path: /metrics
```

**Access points after `docker compose up`:**

| Service | URL | Purpose |
|---------|-----|---------|
| Jaeger UI | http://localhost:16686 | View traces |
| Prometheus | http://localhost:9090 | Query metrics |
| Grafana | http://localhost:3001 | Dashboards |
| Loki | http://localhost:3100 | Log aggregation |

---

## Graceful Shutdown

Ensure all telemetry is flushed before the process exits. This is handled in `instrumentation.ts` but the application must also close its HTTP server cleanly.

```typescript
// Shutdown sequence:
// 1. SIGTERM received
// 2. Stop accepting new connections (server.close())
// 3. Wait for in-flight requests to complete (timeout: 30s)
// 4. Flush OTel SDK (traces, metrics)
// 5. Close database connections
// 6. Exit

import { sdk } from './instrumentation';
import { prisma } from './lib/prisma';
import { redis } from './lib/redis';
import { logger } from './lib/logger';

async function gracefulShutdown(signal: string): Promise<void> {
  logger.info({ signal }, 'graceful shutdown initiated');

  // Stop HTTP server
  await new Promise<void>((resolve) => server.close(() => resolve()));
  logger.info('HTTP server closed');

  // Close database
  await prisma.$disconnect();
  logger.info('database disconnected');

  // Close Redis
  await redis.quit();
  logger.info('redis disconnected');

  // Flush OTel (ensures last traces/metrics are exported)
  await sdk.shutdown();
  logger.info('OTel SDK shut down');

  process.exit(0);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

---

## Critical Rules

1. **`instrumentation.ts` is imported FIRST** — before Express, Prisma, or any other import. OTel must patch modules before they are loaded.
2. **`tenant_id` on every log, metric, and trace** — zero exceptions. Use child loggers and span attributes.
3. **JSON logs in production** — `pino-pretty` is for development only. Never enable it in production.
4. **Redact PII** — configure pino `redact` paths for passwords, tokens, SSNs, credit cards.
5. **Log-trace correlation** — every log line includes `trace_id` and `span_id` so you can jump from logs to traces.
6. **ERROR means wake someone up** — do not use `logger.error()` for expected conditions (404, validation failures). Use `warn` for handled degradation.
7. **Never log request/response bodies at INFO level** — use DEBUG. Bodies can contain PII and are verbose.
8. **Record errors on spans** — every `catch` block that re-throws must call `span.recordException(err)` and `span.setStatus(ERROR)`.
9. **Health check endpoints are silent** — `/healthz` and `/readyz` are excluded from request logging to avoid noise.
10. **Graceful shutdown flushes telemetry** — handle SIGTERM, close server, flush OTel SDK, then exit. Never lose the last batch of traces/metrics.
11. **Metrics at every boundary** — HTTP handlers, service methods, repository calls, external API calls. Use the standard metric names from `core/observability-patterns.md`.
12. **Span naming follows convention** — `HTTP {METHOD} {path}`, `{Service}.{method}`, `{system}.{table}.{operation}`. Consistent naming enables cross-service dashboards.
