---
skill: performance-typescript
description: TypeScript/Node.js performance archetype — event loop management, connection pooling, memory management, database optimization, profiling, caching, TypeScript-specific patterns
version: "1.0"
tags:
  - typescript
  - performance
  - nodejs
  - caching
  - profiling
  - connection-pooling
  - archetype
  - backend
---

# Performance Archetype — TypeScript / Node.js

> **Canonical reference**: Performance patterns specific to Node.js and TypeScript. Apply these alongside `core/observability-patterns.md` for measurable, monitored performance.

Every generated TypeScript service MUST follow these patterns. Performance is not an afterthought — it is a first-class requirement from day one.

---

## Table of Contents

1. [Event Loop — Don't Block It](#event-loop--dont-block-it)
2. [Detect Event Loop Lag](#detect-event-loop-lag)
3. [Worker Threads for CPU-Intensive Work](#worker-threads-for-cpu-intensive-work)
4. [setImmediate vs process.nextTick vs setTimeout](#setimmediate-vs-processnexttick-vs-settimeout)
5. [Stream Processing for Large Data](#stream-processing-for-large-data)
6. [Connection Pooling — Prisma](#connection-pooling--prisma)
7. [Connection Pooling — node-postgres (pg)](#connection-pooling--node-postgres-pg)
8. [Connection Pooling — ioredis](#connection-pooling--ioredis)
9. [HTTP Keep-Alive](#http-keep-alive)
10. [Memory Management — V8 Heap Limits](#memory-management--v8-heap-limits)
11. [Avoid Memory Leaks](#avoid-memory-leaks)
12. [Stream Large Responses](#stream-large-responses)
13. [Buffer Pooling](#buffer-pooling)
14. [Garbage Collection Awareness](#garbage-collection-awareness)
15. [Database Performance — Prisma](#database-performance--prisma)
16. [Batch Operations](#batch-operations)
17. [Read Replicas](#read-replicas)
18. [Query Logging and Slow Query Detection](#query-logging-and-slow-query-detection)
19. [N+1 Detection](#n1-detection)
20. [Profiling — Chrome DevTools](#profiling--chrome-devtools)
21. [Profiling — clinic.js](#profiling--clinicjs)
22. [Profiling — 0x Flamegraphs](#profiling--0x-flamegraphs)
23. [Load Testing — autocannon](#load-testing--autocannon)
24. [V8 Profiling](#v8-profiling)
25. [Caching — In-Process LRU](#caching--in-process-lru)
26. [Caching — Redis with ioredis](#caching--redis-with-ioredis)
27. [Cache Stampede Prevention](#cache-stampede-prevention)
28. [CDN Caching Headers](#cdn-caching-headers)
29. [ETags for Conditional Requests](#etags-for-conditional-requests)
30. [TypeScript-Specific Performance](#typescript-specific-performance)
31. [Critical Rules](#critical-rules)

---

## Event Loop — Don't Block It

Node.js is single-threaded. If you block the event loop, every request queues behind the blocking operation. This is the number one performance killer in Node.js.

**What blocks the event loop:**

| Blocker | Example | Fix |
|---------|---------|-----|
| Synchronous I/O | `fs.readFileSync()` | Use `fs.promises.readFile()` |
| CPU-intensive computation | Hashing, JSON parsing large payloads, image processing | Move to `worker_threads` |
| Tight loops over large arrays | `array.map()` on 1M elements | Use streams or batch with `setImmediate` |
| `JSON.parse()` / `JSON.stringify()` on huge objects | Parsing 100MB JSON | Use streaming JSON parser (`stream-json`) |
| RegExp on untrusted input | ReDoS-vulnerable patterns | Use `re2` or validate input length first |

```typescript
// BAD — blocks event loop for 500ms+ on large files
const data = fs.readFileSync('/path/to/large-file.csv', 'utf8');
const parsed = JSON.parse(data);

// GOOD — non-blocking
const data = await fs.promises.readFile('/path/to/large-file.csv', 'utf8');
const parsed = JSON.parse(data); // Still blocks if file is huge — see streaming section

// BEST — streaming for truly large files
import { createReadStream } from 'node:fs';
import { parser } from 'stream-json';
import { streamArray } from 'stream-json/streamers/StreamArray';

const pipeline = createReadStream('/path/to/large-file.json')
  .pipe(parser())
  .pipe(streamArray());

for await (const { value } of pipeline) {
  await processItem(value);
}
```

---

## Detect Event Loop Lag

Monitor event loop lag and alert when it exceeds thresholds.

```typescript
// src/lib/event-loop-monitor.ts
import { monitorEventLoopDelay } from 'node:perf_hooks';
import pino from 'pino';

const logger = pino({ name: 'event-loop' });

const histogram = monitorEventLoopDelay({ resolution: 20 }); // 20ms sampling
histogram.enable();

// Check every 5 seconds
const WARN_THRESHOLD_MS = 100;
const ERROR_THRESHOLD_MS = 500;

setInterval(() => {
  const p50 = histogram.percentile(50) / 1e6;   // ns to ms
  const p99 = histogram.percentile(99) / 1e6;
  const max = histogram.max / 1e6;

  if (max > ERROR_THRESHOLD_MS) {
    logger.error({ p50, p99, max }, 'event loop lag critically high');
  } else if (p99 > WARN_THRESHOLD_MS) {
    logger.warn({ p50, p99, max }, 'event loop lag elevated');
  }

  // Reset for next interval
  histogram.reset();
}, 5_000).unref(); // .unref() so this timer doesn't prevent process exit

// Expose as OTel metrics (see observability-typescript.md, runtime-metrics section)
```

---

## Worker Threads for CPU-Intensive Work

Move CPU-bound work to a worker thread pool. Never run it on the main thread.

```typescript
// src/lib/worker-pool.ts
import { Worker } from 'node:worker_threads';
import { cpus } from 'node:os';
import pino from 'pino';

const logger = pino({ name: 'worker-pool' });

interface WorkerTask<T> {
  resolve: (value: T) => void;
  reject: (reason: Error) => void;
}

export class WorkerPool {
  private workers: Worker[] = [];
  private queue: Array<{ data: unknown; task: WorkerTask<unknown> }> = [];
  private freeWorkers: Worker[] = [];

  constructor(
    private readonly workerPath: string,
    private readonly poolSize: number = Math.max(cpus().length - 1, 1),
  ) {
    for (let i = 0; i < this.poolSize; i++) {
      this.addWorker();
    }
    logger.info({ poolSize: this.poolSize, workerPath }, 'worker pool initialized');
  }

  private addWorker(): void {
    const worker = new Worker(this.workerPath);

    worker.on('message', (result) => {
      const task = (worker as any).__task as WorkerTask<unknown>;
      task.resolve(result);
      this.freeWorkers.push(worker);
      this.processQueue();
    });

    worker.on('error', (err) => {
      const task = (worker as any).__task as WorkerTask<unknown>;
      if (task) task.reject(err);
      logger.error({ err }, 'worker error');
      // Replace dead worker
      this.workers = this.workers.filter((w) => w !== worker);
      this.addWorker();
    });

    this.workers.push(worker);
    this.freeWorkers.push(worker);
  }

  async execute<T>(data: unknown): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const task = { resolve, reject } as WorkerTask<T>;
      if (this.freeWorkers.length > 0) {
        const worker = this.freeWorkers.pop()!;
        (worker as any).__task = task;
        worker.postMessage(data);
      } else {
        this.queue.push({ data, task: task as WorkerTask<unknown> });
      }
    });
  }

  private processQueue(): void {
    if (this.queue.length === 0 || this.freeWorkers.length === 0) return;
    const { data, task } = this.queue.shift()!;
    const worker = this.freeWorkers.pop()!;
    (worker as any).__task = task;
    worker.postMessage(data);
  }

  async shutdown(): Promise<void> {
    await Promise.all(this.workers.map((w) => w.terminate()));
    logger.info('worker pool shut down');
  }
}
```

**Worker file example:**

```typescript
// src/workers/hash.worker.ts
import { parentPort } from 'node:worker_threads';
import { createHash } from 'node:crypto';

parentPort?.on('message', (data: { algorithm: string; input: string }) => {
  const hash = createHash(data.algorithm).update(data.input).digest('hex');
  parentPort?.postMessage(hash);
});
```

**Usage:**

```typescript
const hashPool = new WorkerPool('./dist/workers/hash.worker.js');
const hash = await hashPool.execute<string>({ algorithm: 'sha256', input: largePayload });
```

---

## setImmediate vs process.nextTick vs setTimeout

| Function | When it runs | Use case |
|----------|-------------|----------|
| `process.nextTick()` | Before any I/O or timers | Ensure callback runs before next event loop tick. Use sparingly — can starve I/O. |
| `setImmediate()` | After I/O callbacks in current iteration | Yield to event loop between batches of CPU work. **Preferred for batching.** |
| `setTimeout(fn, 0)` | Next event loop iteration (min 1ms) | General deferral. Slightly slower than setImmediate. |

**Batching CPU work to avoid blocking:**

```typescript
// Process a large array without blocking the event loop
async function processInBatches<T>(
  items: T[],
  batchSize: number,
  processor: (item: T) => void,
): Promise<void> {
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    batch.forEach(processor);

    // Yield to event loop after each batch
    if (i + batchSize < items.length) {
      await new Promise<void>((resolve) => setImmediate(resolve));
    }
  }
}

// Usage: process 1M items in batches of 1000
await processInBatches(hugeArray, 1000, (item) => {
  // CPU work per item
});
```

---

## Stream Processing for Large Data

Never load an entire large file or dataset into memory. Use Node.js streams.

```typescript
// src/lib/csv-processor.ts
import { createReadStream } from 'node:fs';
import { Transform, pipeline } from 'node:stream';
import { promisify } from 'node:util';
import { parse as csvParse } from 'csv-parse';

const pipelineAsync = promisify(pipeline);

export async function processLargeCSV(filePath: string): Promise<{ processed: number }> {
  let processed = 0;

  const transformer = new Transform({
    objectMode: true,
    transform(record, _encoding, callback) {
      // Process each row — runs in constant memory
      processed++;
      // Push transformed result downstream (or discard if aggregating)
      callback(null, record);
    },
  });

  await pipelineAsync(
    createReadStream(filePath),
    csvParse({ columns: true, skip_empty_lines: true }),
    transformer,
    // Optionally pipe to a writable stream (DB, file, etc.)
  );

  return { processed };
}

// Stream a large JSON array from DB to HTTP response
import { Readable } from 'node:stream';

export function streamJsonResponse(res: Response, cursor: AsyncIterable<unknown>): void {
  res.setHeader('Content-Type', 'application/json');
  res.write('[');

  let first = true;
  const readable = Readable.from(cursor);

  readable.on('data', (item) => {
    if (!first) res.write(',');
    res.write(JSON.stringify(item));
    first = false;
  });

  readable.on('end', () => {
    res.write(']');
    res.end();
  });

  readable.on('error', (err) => {
    res.destroy(err);
  });
}
```

---

## Connection Pooling — Prisma

```typescript
// prisma/schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// Connection pool settings via DATABASE_URL query params:
// postgresql://user:pass@host:5432/db?connection_limit=20&pool_timeout=10

// Or set programmatically:
// src/lib/prisma.ts
import { PrismaClient } from '@prisma/client';

export const prisma = new PrismaClient({
  // Prisma manages its own connection pool.
  // Configure via DATABASE_URL query params:
  //   connection_limit: Max pool size (default: num_cpus * 2 + 1)
  //   pool_timeout:     Seconds to wait for connection (default: 10)
  //
  // For a 4-core machine, default pool = 9.
  // For high-concurrency services, increase:
  //   ?connection_limit=20&pool_timeout=15
  //
  // WARNING: Total connections across all instances must not exceed
  // PostgreSQL max_connections (default: 100).
  // Formula: connection_limit * num_instances < max_connections
});

// Reuse a single PrismaClient across the entire process.
// NEVER create a new PrismaClient per request.

// Shutdown hook
process.on('SIGTERM', async () => {
  await prisma.$disconnect();
});
```

**Connection pool sizing guide:**

| Scenario | `connection_limit` | Notes |
|----------|-------------------|-------|
| Single instance, light load | 5 | Default is fine |
| Single instance, heavy load | 20 | Monitor `db.pool.waiting` metric |
| 10 instances behind LB | 5-10 each | Total = 50-100 (watch `max_connections`) |
| Serverless (Lambda) | 1-2 | Use Prisma Accelerate or PgBouncer |

---

## Connection Pooling — node-postgres (pg)

```typescript
// src/lib/pg-pool.ts
import { Pool, PoolConfig } from 'pg';
import pino from 'pino';

const logger = pino({ name: 'pg-pool' });

const poolConfig: PoolConfig = {
  connectionString: process.env.DATABASE_URL,

  // Pool size
  max: Number(process.env.PG_POOL_MAX || 20),             // Max connections
  min: Number(process.env.PG_POOL_MIN || 2),              // Min idle connections

  // Timeouts
  idleTimeoutMillis: 30_000,        // Close idle connections after 30s
  connectionTimeoutMillis: 5_000,   // Fail if can't connect in 5s
  allowExitOnIdle: true,            // Allow process to exit when pool is idle

  // Statement timeout (prevent long-running queries)
  statement_timeout: 30_000,        // 30s max query time
};

export const pool = new Pool(poolConfig);

// Monitor pool health
pool.on('error', (err) => {
  logger.error({ err }, 'unexpected pool error');
});

pool.on('connect', (client) => {
  logger.debug('new client connected to pool');
});

// Expose pool stats for monitoring
export function getPoolStats() {
  return {
    totalCount: pool.totalCount,      // Total connections (active + idle)
    idleCount: pool.idleCount,        // Idle connections
    waitingCount: pool.waitingCount,  // Queued requests waiting for a connection
  };
}

// Usage in repository:
export async function query<T>(sql: string, params: unknown[]): Promise<T[]> {
  const client = await pool.connect();
  try {
    const result = await client.query(sql, params);
    return result.rows as T[];
  } finally {
    client.release(); // ALWAYS release back to pool
  }
}

// Shutdown
process.on('SIGTERM', async () => {
  await pool.end();
  logger.info('pg pool closed');
});
```

---

## Connection Pooling — ioredis

```typescript
// src/lib/redis.ts
import Redis from 'ioredis';
import pino from 'pino';

const logger = pino({ name: 'redis' });

export const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  // Connection pool (ioredis uses a single persistent connection by default,
  // which is fine for most workloads. Use Cluster for multiple connections.)
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    if (times > 10) {
      logger.error({ attempts: times }, 'redis: max retries exceeded, giving up');
      return null; // stop retrying
    }
    return Math.min(times * 200, 3_000); // exponential backoff, max 3s
  },
  connectTimeout: 5_000,
  commandTimeout: 5_000,

  // Enable offline queue — commands are queued while reconnecting
  enableOfflineQueue: true,

  // Lazy connect — don't connect until first command
  lazyConnect: false,
});

// For high-throughput workloads, use a cluster or pool:
// const cluster = new Redis.Cluster([{ host: 'redis-1', port: 6379 }]);
// Or use ioredis pool: https://github.com/luin/ioredis#autopipelining

// Enable auto-pipelining for batch reads (sends multiple commands in one round trip)
export const redisPipelined = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  enableAutoPipelining: true,
});

redis.on('error', (err) => logger.error({ err }, 'redis connection error'));
redis.on('connect', () => logger.info('redis connected'));
redis.on('reconnecting', () => logger.warn('redis reconnecting'));
```

---

## HTTP Keep-Alive

Enable keep-alive on outbound HTTP connections to reuse TCP sockets.

```typescript
// src/lib/http-client.ts
import { Agent } from 'undici';

// undici (recommended — faster than node:http)
const agent = new Agent({
  keepAliveTimeout: 30_000,     // Keep idle connections alive for 30s
  keepAliveMaxTimeout: 60_000,  // Max lifetime of a keep-alive connection
  connections: 50,              // Max connections per origin
  pipelining: 1,                // HTTP pipelining depth (1 = disabled)
});

// Use with fetch (Node.js 18+)
const response = await fetch('https://api.example.com/data', {
  // @ts-expect-error — undici dispatcher not in global fetch types yet
  dispatcher: agent,
});

// Or use node:http Agent for legacy code
import { Agent as HttpAgent } from 'node:http';
import { Agent as HttpsAgent } from 'node:https';

const httpAgent = new HttpAgent({
  keepAlive: true,
  keepAliveMsecs: 30_000,
  maxSockets: 50,         // Max concurrent connections per host
  maxFreeSockets: 10,     // Max idle connections to keep
});

const httpsAgent = new HttpsAgent({
  keepAlive: true,
  keepAliveMsecs: 30_000,
  maxSockets: 50,
  maxFreeSockets: 10,
});

// Use with axios
import axios from 'axios';
const client = axios.create({
  httpAgent,
  httpsAgent,
  timeout: 10_000,
});
```

---

## Memory Management — V8 Heap Limits

```bash
# Default V8 heap limit: ~1.5GB on 64-bit systems
# Set explicitly for predictable OOM behavior:
node --max-old-space-size=2048 dist/main.js   # 2GB heap

# In Dockerfile:
CMD ["node", "--max-old-space-size=2048", "dist/main.js"]

# Rule of thumb: set to 75% of container memory limit
# Container: 4GB → --max-old-space-size=3072
# Container: 2GB → --max-old-space-size=1536
# Container: 1GB → --max-old-space-size=768
```

**Monitor heap usage:**

```typescript
// src/lib/memory-monitor.ts
import pino from 'pino';

const logger = pino({ name: 'memory' });
const HEAP_WARN_RATIO = 0.85;

setInterval(() => {
  const mem = process.memoryUsage();
  const heapRatio = mem.heapUsed / mem.heapTotal;

  if (heapRatio > HEAP_WARN_RATIO) {
    logger.warn({
      heapUsed: `${(mem.heapUsed / 1024 / 1024).toFixed(1)}MB`,
      heapTotal: `${(mem.heapTotal / 1024 / 1024).toFixed(1)}MB`,
      rss: `${(mem.rss / 1024 / 1024).toFixed(1)}MB`,
      ratio: heapRatio.toFixed(2),
    }, 'high memory usage');
  }
}, 30_000).unref();
```

---

## Avoid Memory Leaks

Common memory leaks in Node.js and how to prevent them:

```typescript
// 1. Event listener leaks — always clean up listeners
import { EventEmitter } from 'node:events';

class OrderProcessor extends EventEmitter {
  constructor() {
    super();
    // Set max listeners if you genuinely need many
    this.setMaxListeners(20);
  }

  // BAD — adds a new listener on every call, never removes
  processOrder_BAD(handler: () => void): void {
    someExternalEmitter.on('data', handler);
  }

  // GOOD — clean up when done
  processOrder(handler: () => void): void {
    someExternalEmitter.on('data', handler);
    // Return cleanup function
    return () => someExternalEmitter.removeListener('data', handler);
  }
}

// 2. Timer leaks — always call clearInterval / clearTimeout
class Poller {
  private timer: NodeJS.Timeout | null = null;

  start(): void {
    this.timer = setInterval(() => this.poll(), 5_000);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

// 3. Closure leaks — avoid capturing large objects in long-lived closures
// BAD
function createHandler() {
  const hugeBuffer = Buffer.alloc(100 * 1024 * 1024); // 100MB
  return () => {
    // hugeBuffer is captured and never freed
    return hugeBuffer.length;
  };
}

// GOOD — use WeakRef for cache-like patterns
const cache = new Map<string, WeakRef<object>>();
const registry = new FinalizationRegistry<string>((key) => {
  cache.delete(key);
});

function cacheObject(key: string, obj: object): void {
  cache.set(key, new WeakRef(obj));
  registry.register(obj, key);
}

function getCached(key: string): object | undefined {
  const ref = cache.get(key);
  if (!ref) return undefined;
  const obj = ref.deref();
  if (!obj) {
    cache.delete(key); // Already garbage collected
    return undefined;
  }
  return obj;
}

// 4. Promise leaks — always handle rejections
// BAD — unhandled rejection can leak memory
someAsyncOp();

// GOOD
someAsyncOp().catch((err) => logger.error({ err }, 'async op failed'));

// Global safety net (not a fix — find the source)
process.on('unhandledRejection', (reason, promise) => {
  logger.error({ reason }, 'unhandled rejection');
});
```

---

## Stream Large Responses

Never buffer an entire large response in memory. Stream it directly to the client.

```typescript
// src/routes/export.ts
import { Router, Request, Response } from 'express';
import { Readable, Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const router = Router();

// Stream database rows as NDJSON (Newline Delimited JSON)
router.get('/api/v1/export/orders', async (req: Request, res: Response) => {
  const tenantId = req.tenantId;

  res.setHeader('Content-Type', 'application/x-ndjson');
  res.setHeader('Transfer-Encoding', 'chunked');

  // Prisma cursor-based streaming
  let cursor: string | undefined;
  const batchSize = 1000;

  const readable = new Readable({
    objectMode: true,
    async read() {
      const orders = await prisma.order.findMany({
        where: { tenantId },
        take: batchSize,
        skip: cursor ? 1 : 0,
        ...(cursor && { cursor: { id: cursor } }),
        orderBy: { id: 'asc' },
        select: { id: true, total: true, status: true, createdAt: true },
      });

      for (const order of orders) {
        this.push(order);
      }

      if (orders.length < batchSize) {
        this.push(null); // Signal end of stream
      } else {
        cursor = orders[orders.length - 1].id;
      }
    },
  });

  const toNdjson = new Transform({
    objectMode: true,
    transform(chunk, _encoding, callback) {
      callback(null, JSON.stringify(chunk) + '\n');
    },
  });

  await pipeline(readable, toNdjson, res);
});
```

---

## Buffer Pooling

Reuse buffers for repeated binary operations instead of allocating new ones.

```typescript
// src/lib/buffer-pool.ts
export class BufferPool {
  private pool: Buffer[] = [];

  constructor(
    private readonly bufferSize: number,
    private readonly maxPoolSize: number = 100,
  ) {}

  acquire(): Buffer {
    const buf = this.pool.pop();
    if (buf) {
      buf.fill(0); // Clear before reuse
      return buf;
    }
    return Buffer.allocUnsafe(this.bufferSize);
  }

  release(buf: Buffer): void {
    if (buf.length === this.bufferSize && this.pool.length < this.maxPoolSize) {
      this.pool.push(buf);
    }
    // Else let it be garbage collected
  }
}

// Usage
const pool = new BufferPool(4096); // 4KB buffers

function processChunk(data: Buffer): void {
  const buf = pool.acquire();
  try {
    data.copy(buf);
    // ... process buf ...
  } finally {
    pool.release(buf);
  }
}
```

---

## Garbage Collection Awareness

```typescript
// Avoid creating short-lived objects in hot loops

// BAD — creates a new object per iteration (GC pressure)
function sumBad(items: Array<{ value: number }>): number {
  return items.reduce((acc, item) => {
    return { total: acc.total + item.value }; // New object every iteration!
  }, { total: 0 }).total;
}

// GOOD — use primitive accumulator
function sumGood(items: Array<{ value: number }>): number {
  let total = 0;
  for (const item of items) {
    total += item.value;
  }
  return total;
}

// BAD — string concatenation in hot loop (creates intermediates)
function buildBad(parts: string[]): string {
  let result = '';
  for (const part of parts) {
    result += part; // New string per iteration
  }
  return result;
}

// GOOD — use array join
function buildGood(parts: string[]): string {
  return parts.join('');
}

// Monitor GC pauses (requires --expose-gc flag or perf_hooks)
import { PerformanceObserver } from 'node:perf_hooks';

const gcObserver = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.duration > 50) { // GC pause > 50ms
      logger.warn({
        kind: (entry as any).detail?.kind,
        duration_ms: entry.duration.toFixed(1),
      }, 'long GC pause');
    }
  }
});

gcObserver.observe({ type: 'gc', buffered: false });
```

---

## Database Performance — Prisma

```typescript
// 1. Select only needed fields — avoid SELECT *
// BAD
const orders = await prisma.order.findMany({ where: { tenantId } });

// GOOD — select specific fields
const orders = await prisma.order.findMany({
  where: { tenantId },
  select: {
    id: true,
    status: true,
    total: true,
    createdAt: true,
    // Omit: updatedAt, metadata, internalNotes, etc.
  },
});

// 2. Use include sparingly — it generates JOINs
// BAD — includes everything
const order = await prisma.order.findUnique({
  where: { id: orderId },
  include: { items: true, customer: true, payments: true, shipments: true },
});

// GOOD — include only what you need, with select inside
const order = await prisma.order.findUnique({
  where: { id: orderId },
  select: {
    id: true,
    status: true,
    total: true,
    items: {
      select: { id: true, name: true, quantity: true, price: true },
    },
    customer: {
      select: { id: true, name: true, email: true },
    },
  },
});

// 3. Pagination — always use cursor-based for large datasets
// BAD — offset pagination is O(n) in PostgreSQL
const page3 = await prisma.order.findMany({ skip: 200, take: 100 });

// GOOD — cursor-based pagination is O(1)
const nextPage = await prisma.order.findMany({
  take: 100,
  skip: 1,              // Skip the cursor itself
  cursor: { id: lastOrderId },
  orderBy: { id: 'asc' },
});

// 4. Use raw queries for complex aggregations
const stats = await prisma.$queryRaw<Array<{ status: string; count: bigint; total: number }>>`
  SELECT status, COUNT(*)::int as count, SUM(total)::float as total
  FROM orders
  WHERE tenant_id = ${tenantId}
  GROUP BY status
`;
```

---

## Batch Operations

```typescript
// 1. createMany for bulk inserts (single query, much faster than loop)
await prisma.orderItem.createMany({
  data: items.map((item) => ({
    orderId: order.id,
    productId: item.productId,
    quantity: item.quantity,
    price: item.price,
  })),
  skipDuplicates: true,
});

// 2. Interactive transactions for multi-step operations
const result = await prisma.$transaction(async (tx) => {
  const order = await tx.order.create({ data: orderData });
  await tx.orderItem.createMany({
    data: items.map((item) => ({ ...item, orderId: order.id })),
  });
  await tx.inventory.updateMany({
    where: { productId: { in: items.map((i) => i.productId) } },
    data: { /* decrement stock */ },
  });
  return order;
}, {
  maxWait: 5_000,       // Max time to wait for a connection from pool
  timeout: 10_000,      // Max time for the entire transaction
  isolationLevel: 'ReadCommitted',
});

// 3. Batch reads with Promise.all (parallel queries)
const [orders, stats, recentActivity] = await Promise.all([
  prisma.order.findMany({ where: { tenantId }, take: 20 }),
  prisma.order.aggregate({ where: { tenantId }, _count: true, _sum: { total: true } }),
  prisma.auditLog.findMany({ where: { tenantId }, take: 10, orderBy: { createdAt: 'desc' } }),
]);
```

---

## Read Replicas

```typescript
// Using Prisma read replicas extension
import { PrismaClient } from '@prisma/client';
import { readReplicas } from '@prisma/extension-read-replicas';

const prisma = new PrismaClient().$extends(
  readReplicas({
    url: process.env.DATABASE_REPLICA_URL!,
    // Multiple replicas:
    // url: [process.env.REPLICA_1_URL!, process.env.REPLICA_2_URL!],
  }),
);

// Reads go to replica automatically
const orders = await prisma.order.findMany({ where: { tenantId } });

// Writes go to primary automatically
const newOrder = await prisma.order.create({ data: orderData });

// Force read from primary (after a write, to avoid stale reads)
const freshOrder = await prisma.$primary().order.findUnique({ where: { id: orderId } });
```

---

## Query Logging and Slow Query Detection

```typescript
// src/lib/prisma.ts
import { PrismaClient } from '@prisma/client';
import pino from 'pino';

const logger = pino({ name: 'prisma' });
const SLOW_QUERY_MS = 500;

export const prisma = new PrismaClient({
  log: [
    { level: 'query', emit: 'event' },
    { level: 'error', emit: 'event' },
    { level: 'warn', emit: 'event' },
  ],
});

prisma.$on('query', (e) => {
  if (e.duration > SLOW_QUERY_MS) {
    logger.warn({
      query: e.query,
      params: e.params,
      duration_ms: e.duration,
      target: e.target,
    }, 'slow query detected');
  } else if (process.env.LOG_LEVEL === 'debug') {
    logger.debug({
      query: e.query,
      duration_ms: e.duration,
    }, 'prisma query');
  }
});

prisma.$on('error', (e) => {
  logger.error({ message: e.message, target: e.target }, 'prisma error');
});

prisma.$on('warn', (e) => {
  logger.warn({ message: e.message, target: e.target }, 'prisma warning');
});
```

---

## N+1 Detection

N+1 queries are the most common Prisma performance issue. Detect them in development.

```typescript
// src/lib/n-plus-one-detector.ts (development only)
import pino from 'pino';

const logger = pino({ name: 'n+1-detector' });

interface QueryRecord {
  query: string;
  count: number;
  firstSeen: number;
}

const queryWindow = new Map<string, QueryRecord>();
const WINDOW_MS = 1_000;        // 1-second window
const THRESHOLD = 5;            // More than 5 similar queries = N+1

// Call this from prisma.$on('query')
export function detectNPlusOne(query: string): void {
  if (process.env.NODE_ENV === 'production') return;

  const now = Date.now();

  // Normalize query (remove specific IDs)
  const normalized = query.replace(/"[0-9a-f-]{36}"/g, '"?"')
                          .replace(/\d+/g, '?');

  const existing = queryWindow.get(normalized);
  if (existing && now - existing.firstSeen < WINDOW_MS) {
    existing.count++;
    if (existing.count === THRESHOLD) {
      logger.warn({
        query: normalized,
        count: existing.count,
        window_ms: WINDOW_MS,
      }, 'possible N+1 query detected');
    }
  } else {
    queryWindow.set(normalized, { query: normalized, count: 1, firstSeen: now });
  }

  // Clean old entries
  for (const [key, record] of queryWindow) {
    if (now - record.firstSeen > WINDOW_MS) {
      queryWindow.delete(key);
    }
  }
}

// Wire up:
// prisma.$on('query', (e) => { detectNPlusOne(e.query); });
```

**Common N+1 fixes in Prisma:**

```typescript
// N+1: Loading orders then loading items for each order
// BAD
const orders = await prisma.order.findMany({ where: { tenantId } });
for (const order of orders) {
  order.items = await prisma.orderItem.findMany({ where: { orderId: order.id } }); // N queries!
}

// GOOD — single query with include
const orders = await prisma.order.findMany({
  where: { tenantId },
  include: { items: true }, // 1 query with JOIN
});

// GOOD — if you need more control, use $queryRaw or two queries + manual join
const [orders, allItems] = await Promise.all([
  prisma.order.findMany({ where: { tenantId } }),
  prisma.orderItem.findMany({ where: { order: { tenantId } } }),
]);

const itemsByOrder = new Map<string, OrderItem[]>();
for (const item of allItems) {
  const list = itemsByOrder.get(item.orderId) || [];
  list.push(item);
  itemsByOrder.set(item.orderId, list);
}
// Now: itemsByOrder.get(order.id) — zero extra queries
```

---

## Profiling — Chrome DevTools

```bash
# Start with inspector
node --inspect dist/main.js

# Or attach to a running process
kill -USR1 <pid>    # Enables inspector on running Node.js process

# Connect from Chrome:
# 1. Open chrome://inspect
# 2. Click "inspect" on your Node.js process
# 3. Go to "Performance" tab → Record → reproduce the issue → Stop
# 4. Analyze flamechart
```

```typescript
// Programmatic CPU profiling (take a profile on demand)
import { Session } from 'node:inspector';
import { writeFileSync } from 'node:fs';

export async function captureProfile(durationMs: number = 5_000): Promise<string> {
  const session = new Session();
  session.connect();

  session.post('Profiler.enable');
  session.post('Profiler.start');

  await new Promise((resolve) => setTimeout(resolve, durationMs));

  return new Promise((resolve, reject) => {
    session.post('Profiler.stop', (err, { profile }) => {
      if (err) return reject(err);
      const filename = `/tmp/profile-${Date.now()}.cpuprofile`;
      writeFileSync(filename, JSON.stringify(profile));
      session.disconnect();
      resolve(filename);
    });
  });
}

// Expose as admin endpoint (never in production public API)
router.post('/admin/profile', async (req, res) => {
  const duration = Number(req.query.duration) || 5_000;
  const filename = await captureProfile(duration);
  res.json({ filename, duration_ms: duration });
});
```

---

## Profiling — clinic.js

```bash
# Install globally
npm install -g clinic

# Doctor — overall health check (event loop, memory, GC, I/O)
clinic doctor -- node dist/main.js
# Then send traffic, Ctrl+C, and it opens a browser with analysis

# Flame — CPU flamegraph (where is time spent?)
clinic flame -- node dist/main.js

# Bubbleprof — async operations visualization (where is time waiting?)
clinic bubbleprof -- node dist/main.js
```

**When to use each tool:**

| Tool | Symptom | What it shows |
|------|---------|---------------|
| `clinic doctor` | "Something is slow" (no idea what) | Event loop delay, CPU, memory, I/O — identifies the category |
| `clinic flame` | High CPU usage | CPU flamegraph — which functions use the most CPU |
| `clinic bubbleprof` | Slow responses but CPU is low | Async bottlenecks — where is the code waiting? |

---

## Profiling — 0x Flamegraphs

```bash
# Install
npm install -g 0x

# Generate flamegraph
0x dist/main.js
# Send traffic, then Ctrl+C — opens SVG flamegraph in browser

# With specific flags
0x --output-dir /tmp/flamegraphs -- node --max-old-space-size=2048 dist/main.js
```

**Reading a flamegraph:**
- **Wide bars** = functions that use a lot of CPU time (or are called frequently)
- **Tall stacks** = deep call chains (not necessarily bad)
- **Look for**: wide bars in your application code (not in Node internals or V8)
- **Common findings**: JSON serialization, regex, lodash deep clone, ORM overhead

---

## Load Testing — autocannon

```bash
# Install
npm install -g autocannon

# Basic load test
autocannon -c 100 -d 30 http://localhost:3000/api/v1/orders
# -c 100: 100 concurrent connections
# -d 30:  30 seconds duration

# With custom headers (tenant ID, auth)
autocannon -c 50 -d 60 \
  -H 'X-Tenant-ID=tenant_abc' \
  -H 'Authorization=Bearer <token>' \
  http://localhost:3000/api/v1/orders

# POST with body
autocannon -c 50 -d 30 -m POST \
  -H 'Content-Type=application/json' \
  -b '{"name":"test","quantity":1}' \
  http://localhost:3000/api/v1/orders

# Pipeline requests (multiple requests per connection)
autocannon -c 50 -d 30 -p 10 http://localhost:3000/api/v1/orders
```

**Programmatic usage (in test files):**

```typescript
import autocannon from 'autocannon';

const result = await autocannon({
  url: 'http://localhost:3000/api/v1/orders',
  connections: 100,
  duration: 30,
  headers: {
    'X-Tenant-ID': 'tenant_abc',
    'Authorization': 'Bearer test-token',
  },
});

console.log('Requests/sec:', result.requests.average);
console.log('Latency p99:', result.latency.p99, 'ms');
console.log('Errors:', result.errors);
```

**Target benchmarks:**

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| p50 latency | < 100ms | < 50ms | < 10ms |
| p99 latency | < 500ms | < 200ms | < 50ms |
| Requests/sec | > 100 | > 1000 | > 5000 |
| Error rate | < 1% | < 0.1% | 0% |

---

## V8 Profiling

```bash
# Generate V8 profiling log
node --prof dist/main.js
# Produces isolate-*.log file

# Process the log into readable text
node --prof-process isolate-*.log > profile.txt

# Key sections in profile.txt:
# [JavaScript]: Time in JS functions
# [C++]: Time in V8/native code
# [GC]: Time in garbage collection
# [Summary]: Overall breakdown
```

---

## Caching — In-Process LRU

```typescript
// src/lib/cache.ts
import { LRUCache } from 'lru-cache';

// Type-safe LRU cache factory
export function createLRUCache<V>(options: {
  maxItems: number;
  ttlMs: number;
  name: string;
}): LRUCache<string, V> {
  return new LRUCache<string, V>({
    max: options.maxItems,
    ttl: options.ttlMs,

    // Optional: track size in bytes (for memory-bounded caches)
    // maxSize: 50 * 1024 * 1024, // 50MB
    // sizeCalculation: (value) => JSON.stringify(value).length,

    // Dispose callback — useful for cleanup
    dispose: (value, key, reason) => {
      if (reason === 'evict' || reason === 'delete') {
        // Optional: log evictions for monitoring
      }
    },
  });
}

// Usage
interface TenantConfig {
  features: string[];
  limits: Record<string, number>;
}

const tenantConfigCache = createLRUCache<TenantConfig>({
  maxItems: 1000,
  ttlMs: 5 * 60 * 1000, // 5 minutes
  name: 'tenant-config',
});

export async function getTenantConfig(tenantId: string): Promise<TenantConfig> {
  const cached = tenantConfigCache.get(tenantId);
  if (cached) return cached;

  const config = await prisma.tenantConfig.findUniqueOrThrow({
    where: { tenantId },
  });

  tenantConfigCache.set(tenantId, config);
  return config;
}
```

**Package dependency:**

```json
{
  "lru-cache": "^11.0.0"
}
```

---

## Caching — Redis with ioredis

```typescript
// src/lib/redis-cache.ts
import { redis } from './redis';
import pino from 'pino';

const logger = pino({ name: 'redis-cache' });

export async function cacheGet<T>(key: string): Promise<T | null> {
  const raw = await redis.get(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    logger.warn({ key }, 'cache: invalid JSON, deleting key');
    await redis.del(key);
    return null;
  }
}

export async function cacheSet(
  key: string,
  value: unknown,
  ttlSeconds: number,
): Promise<void> {
  await redis.set(key, JSON.stringify(value), 'EX', ttlSeconds);
}

export async function cacheDel(key: string): Promise<void> {
  await redis.del(key);
}

// Batch reads with pipeline (single round trip for multiple keys)
export async function cacheGetMany<T>(keys: string[]): Promise<Map<string, T>> {
  if (keys.length === 0) return new Map();

  const pipeline = redis.pipeline();
  for (const key of keys) {
    pipeline.get(key);
  }

  const results = await pipeline.exec();
  const map = new Map<string, T>();

  if (results) {
    for (let i = 0; i < results.length; i++) {
      const [err, raw] = results[i];
      if (!err && raw) {
        try {
          map.set(keys[i], JSON.parse(raw as string) as T);
        } catch {
          // Skip invalid entries
        }
      }
    }
  }

  return map;
}

// Cache-aside pattern with type-safe loader
export async function cacheThrough<T>(
  key: string,
  ttlSeconds: number,
  loader: () => Promise<T>,
): Promise<T> {
  const cached = await cacheGet<T>(key);
  if (cached !== null) return cached;

  const value = await loader();
  await cacheSet(key, value, ttlSeconds);
  return value;
}
```

---

## Cache Stampede Prevention

When a popular cache key expires, many concurrent requests hit the database simultaneously. Prevent this with single-flight (coalescing).

```typescript
// src/lib/single-flight.ts
import { Sema } from 'async-sema';

// Map of in-flight requests: key → promise
const inflight = new Map<string, Promise<unknown>>();

/**
 * Ensures only one execution of `fn` per key at a time.
 * Concurrent callers with the same key share the same promise.
 */
export async function singleFlight<T>(
  key: string,
  fn: () => Promise<T>,
): Promise<T> {
  const existing = inflight.get(key);
  if (existing) {
    return existing as Promise<T>;
  }

  const promise = fn().finally(() => {
    inflight.delete(key);
  });

  inflight.set(key, promise);
  return promise;
}

// Usage with cache
export async function getCachedOrder(tenantId: string, orderId: string): Promise<Order> {
  const cacheKey = `order:${tenantId}:${orderId}`;

  // Check cache first
  const cached = await cacheGet<Order>(cacheKey);
  if (cached) return cached;

  // Single-flight: only one DB query per key, even with 100 concurrent requests
  return singleFlight(cacheKey, async () => {
    // Double-check cache (another request may have populated it)
    const rechecked = await cacheGet<Order>(cacheKey);
    if (rechecked) return rechecked;

    const order = await prisma.order.findUniqueOrThrow({
      where: { id_tenantId: { id: orderId, tenantId } },
    });

    await cacheSet(cacheKey, order, 300); // 5min TTL
    return order;
  });
}
```

**Package dependency:**

```json
{
  "async-sema": "^3.1.0"
}
```

---

## CDN Caching Headers

```typescript
// src/middleware/cache-headers.middleware.ts
import { Request, Response, NextFunction } from 'express';

interface CacheOptions {
  maxAge: number;          // seconds
  staleWhileRevalidate?: number;
  isPrivate?: boolean;     // true for user-specific content
  noStore?: boolean;       // true for sensitive data
}

export function cacheControl(options: CacheOptions) {
  return (_req: Request, res: Response, next: NextFunction): void => {
    if (options.noStore) {
      res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
      next();
      return;
    }

    const directives: string[] = [];
    directives.push(options.isPrivate ? 'private' : 'public');
    directives.push(`max-age=${options.maxAge}`);

    if (options.staleWhileRevalidate) {
      directives.push(`stale-while-revalidate=${options.staleWhileRevalidate}`);
    }

    res.setHeader('Cache-Control', directives.join(', '));
    next();
  };
}

// Usage
app.get('/api/v1/products',
  cacheControl({ maxAge: 300, staleWhileRevalidate: 60 }),  // 5min cache, 1min stale
  productsHandler,
);

app.get('/api/v1/me',
  cacheControl({ maxAge: 0, isPrivate: true }),              // No caching for user data
  meHandler,
);

app.get('/api/v1/auth/token',
  cacheControl({ noStore: true }),                           // Never cache auth tokens
  tokenHandler,
);
```

---

## ETags for Conditional Requests

```typescript
// src/middleware/etag.middleware.ts
import { createHash } from 'node:crypto';
import { Request, Response, NextFunction } from 'express';

// Generate ETag from response body
export function generateETag(body: string | Buffer): string {
  const hash = createHash('md5').update(body).digest('hex');
  return `"${hash}"`;
}

// Middleware: automatic ETag generation + conditional response
export function etagMiddleware(req: Request, res: Response, next: NextFunction): void {
  const originalJson = res.json.bind(res);

  res.json = (body: unknown) => {
    const bodyStr = JSON.stringify(body);
    const etag = generateETag(bodyStr);
    res.setHeader('ETag', etag);

    // Check If-None-Match header
    const ifNoneMatch = req.headers['if-none-match'];
    if (ifNoneMatch === etag) {
      res.status(304).end();
      return res;
    }

    return originalJson(body);
  };

  next();
}

// Entity-level ETags (based on updated_at timestamp or version)
export function entityETag(entity: { updatedAt: Date; id: string }): string {
  return `"${entity.id}-${entity.updatedAt.getTime()}"`;
}

// Usage in handler
router.get('/api/v1/orders/:id', async (req, res) => {
  const order = await orderService.getById(req.tenantId, req.params.id);
  const etag = entityETag(order);
  res.setHeader('ETag', etag);

  if (req.headers['if-none-match'] === etag) {
    return res.status(304).end();
  }

  res.json(order);
});
```

---

## TypeScript-Specific Performance

### Avoid Runtime Type Checks in Hot Paths

```typescript
// BAD — runtime validation on every call in a hot loop
import { z } from 'zod';

const OrderSchema = z.object({ id: z.string(), total: z.number() });

function processOrders(orders: unknown[]): void {
  for (const order of orders) {
    const parsed = OrderSchema.parse(order); // zod validation on every item!
    // ...
  }
}

// GOOD — validate at boundary, trust internally
function processOrders(orders: Order[]): void {
  // Input was already validated at the API boundary (controller/handler)
  // Trust the type system internally — no runtime checks
  for (const order of orders) {
    // TypeScript knows order.id is string, order.total is number
    total += order.total;
  }
}

// Rule: validate at entry points (HTTP handlers, message consumers, file readers),
// then use TypeScript types internally without re-validation.
```

### Barrel Export Performance Impact

```typescript
// BAD — barrel exports can import the entire module tree
// src/index.ts
export * from './orders';
export * from './users';
export * from './payments';
export * from './analytics';
export * from './notifications';

// When you import { OrderService } from './', Node.js may evaluate ALL exports.

// GOOD — import directly from the specific module
import { OrderService } from './orders/order.service';

// For libraries you publish: use barrel exports with "sideEffects: false" in package.json
// For application code: prefer direct imports
```

### ESM vs CJS Bundling for Production

```typescript
// tsconfig.json for production Node.js service
{
  "compilerOptions": {
    "target": "ES2022",        // Modern Node.js supports ES2022
    "module": "NodeNext",       // ESM with .js extensions
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "declaration": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,    // Required for esbuild/swc compatibility
  }
}

// For faster builds (10-100x faster than tsc for transpilation):
// Use esbuild or swc for transpilation, tsc for type checking only

// package.json
{
  "scripts": {
    "build": "esbuild src/main.ts --bundle --platform=node --target=node20 --outdir=dist --format=esm",
    "typecheck": "tsc --noEmit",
    "dev": "tsx watch src/main.ts"
  }
}
```

### Bundle Size Awareness

```typescript
// Server-side bundle size matters less than client-side, BUT it affects:
// 1. Cold start time (serverless / Lambda)
// 2. Docker image size
// 3. Memory usage at startup

// Find large dependencies
// npx depcheck — finds unused dependencies
// npx bundlephobia <package> — check package size before installing

// Common heavy packages and lighter alternatives:
// moment.js (300KB) → dayjs (2KB) or date-fns (tree-shakeable)
// lodash (72KB) → lodash-es (tree-shakeable) or native JS
// uuid (30KB) → crypto.randomUUID() (built-in, Node.js 19+)
// axios (30KB) → native fetch (Node.js 18+)
// express-validator → zod (already in your stack, no extra dep)

// Check what you're shipping
// npx source-map-explorer dist/main.js — visualize bundle contents
```

---

## Critical Rules

1. **Never block the event loop** — no synchronous I/O, no CPU-intensive work on the main thread. Use `worker_threads` for CPU work, streams for large data.
2. **Reuse connections** — one PrismaClient, one Redis client, one HTTP agent per process. Never create connections per request.
3. **Select only needed fields** — `select` in Prisma, column lists in raw SQL. Avoid `SELECT *`.
4. **Detect N+1 queries** — use Prisma `include`, or batch with `Promise.all`. Wire up the N+1 detector in development.
5. **Stream large responses** — never buffer an entire dataset in memory. Use cursor-based pagination and streaming.
6. **Set heap limits** — `--max-old-space-size` at 75% of container memory. Monitor heap usage.
7. **Profile before optimizing** — use `clinic doctor` to identify the bottleneck category, then `clinic flame` or `bubbleprof` for specifics. Never guess.
8. **Cache aggressively, invalidate carefully** — LRU for hot data, Redis for shared state, CDN headers for static responses. Use single-flight to prevent stampedes.
9. **Validate at the boundary, trust internally** — Zod/class-validator at HTTP handlers and message consumers. No runtime type checks in service/repository layers.
10. **Prefer direct imports over barrel exports** — avoid importing the entire module tree when you need one function.
11. **Monitor event loop lag** — expose as a metric, alert when p99 > 100ms. This is the single most important Node.js health signal.
12. **Load test before deploying** — use autocannon to establish baseline throughput and latency. Compare after every significant change.
