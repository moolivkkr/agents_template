---
skill: worker-pattern-typescript
description: TypeScript worker/background job archetype — BullMQ, node-cron, graceful shutdown, structured logging, health checks
version: "1.0"
tags:
  - typescript
  - worker
  - bullmq
  - background-job
  - node-cron
  - archetype
  - backend
---

# Worker / Background Job Pattern — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `worker-pattern.md` (language-neutral). Read that first for concepts and contracts.

TypeScript workers use BullMQ (Redis-backed) for robust job queues, `node-cron` for scheduled tasks, and Node.js process signals for graceful shutdown.

## Job Types

```typescript
// src/worker/types.ts

export interface Job<T = Record<string, unknown>> {
  id: string;
  type: string;
  payload: T;
  tenantId: string;
  attempt: number;
  maxRetries: number;
  createdAt: string; // ISO 8601
  correlationId?: string;
}

export interface JobHandler<T = Record<string, unknown>> {
  readonly type: string;
  handle(job: Job<T>): Promise<void>;
}

export interface WorkerConfig {
  concurrency: number;       // default: 5
  jobTimeoutMs: number;      // default: 300_000 (5 min)
  shutdownTimeoutMs: number; // default: 30_000 (30s)
  maxRetries: number;        // default: 5
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  checks: {
    queueConnection: { status: string };
    lastJobProcessed: { status: string; timestamp?: string; secondsAgo?: number };
    inFlightJobs: { count: number; max: number };
  };
}
```

## BullMQ Worker Setup

```typescript
// src/worker/bull-worker.ts

import { Worker as BullWorker, Queue, Job as BullJob, QueueEvents } from 'bullmq';
import { Logger } from 'pino';
import { Redis } from 'ioredis';

export class WorkerService {
  private workers: BullWorker[] = [];
  private handlers = new Map<string, JobHandler>();
  private connection: Redis;
  private logger: Logger;
  private config: WorkerConfig;

  private inFlight = 0;
  private lastJobAt: Date | null = null;
  private shuttingDown = false;

  constructor(redisUrl: string, logger: Logger, config: Partial<WorkerConfig> = {}) {
    this.connection = new Redis(redisUrl, { maxRetriesPerRequest: null });
    this.logger = logger.child({ component: 'worker' });
    this.config = {
      concurrency: config.concurrency ?? 5,
      jobTimeoutMs: config.jobTimeoutMs ?? 300_000,
      shutdownTimeoutMs: config.shutdownTimeoutMs ?? 30_000,
      maxRetries: config.maxRetries ?? 5,
    };
  }

  register(handler: JobHandler): void {
    this.handlers.set(handler.type, handler);
  }

  /** Start processing jobs from the given queue names. */
  async start(queueNames: string[]): Promise<void> {
    this.logger.info({ queues: queueNames, concurrency: this.config.concurrency }, 'worker.starting');

    for (const queueName of queueNames) {
      const worker = new BullWorker(
        queueName,
        async (bullJob: BullJob) => {
          await this.processJob(bullJob);
        },
        {
          connection: this.connection,
          concurrency: this.config.concurrency,
          autorun: true,
          settings: {
            backoffStrategy: (attemptsMade: number) => {
              return exponentialBackoff(attemptsMade);
            },
          },
        },
      );

      worker.on('failed', (job, err) => {
        this.logger.error(
          { jobId: job?.id, jobType: job?.name, error: err.message, attempt: job?.attemptsMade },
          'job.failed',
        );
      });

      worker.on('error', (err) => {
        this.logger.error({ error: err.message }, 'worker.error');
      });

      this.workers.push(worker);
    }

    // Register signal handlers for graceful shutdown
    this.registerSignalHandlers();
  }

  private async processJob(bullJob: BullJob): Promise<void> {
    const jobId = bullJob.data.id ?? bullJob.id;
    const jobType = bullJob.name;
    const tenantId = bullJob.data.tenantId;
    const attempt = bullJob.attemptsMade + 1;

    const log = this.logger.child({ jobId, jobType, tenantId, attempt });

    this.inFlight++;
    const start = Date.now();

    try {
      // Find handler
      const handler = this.handlers.get(jobType);
      if (!handler) {
        log.error('job.unknown_type');
        throw new Error(`No handler for job type: ${jobType}`);
      }

      // Execute with timeout
      const job: Job = {
        id: jobId,
        type: jobType,
        payload: bullJob.data.payload ?? bullJob.data,
        tenantId,
        attempt,
        maxRetries: this.config.maxRetries,
        createdAt: bullJob.data.createdAt ?? new Date().toISOString(),
        correlationId: bullJob.data.correlationId,
      };

      await withTimeout(handler.handle(job), this.config.jobTimeoutMs);

      const elapsed = Date.now() - start;
      this.lastJobAt = new Date();
      log.info({ durationMs: elapsed }, 'job.completed');
    } catch (error) {
      const elapsed = Date.now() - start;
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error({ durationMs: elapsed, error: errorMessage }, 'job.processing_failed');
      throw error; // BullMQ handles retry via its built-in backoff
    } finally {
      this.inFlight--;
    }
  }

  private registerSignalHandlers(): void {
    const shutdown = async (signal: string) => {
      if (this.shuttingDown) return;
      this.shuttingDown = true;

      this.logger.info({ signal }, 'worker.shutdown_requested');

      // Close all workers gracefully
      const closePromises = this.workers.map((w) =>
        w.close().catch((err) => {
          this.logger.error({ error: err.message }, 'worker.close_error');
        }),
      );

      // Wait with timeout
      const timeout = new Promise<void>((resolve) => {
        setTimeout(() => {
          this.logger.warn('worker.shutdown_timeout');
          resolve();
        }, this.config.shutdownTimeoutMs);
      });

      await Promise.race([Promise.all(closePromises), timeout]);

      this.connection.disconnect();
      this.logger.info('worker.shutdown_complete');
      process.exit(0);
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));
  }

  /** Health status for liveness/readiness probes. */
  health(): HealthStatus {
    const secondsAgo = this.lastJobAt
      ? Math.floor((Date.now() - this.lastJobAt.getTime()) / 1000)
      : undefined;

    let status: HealthStatus['status'] = 'healthy';
    if (secondsAgo !== undefined && secondsAgo > 300) {
      status = 'degraded';
    }

    return {
      status,
      checks: {
        queueConnection: { status: this.connection.status === 'ready' ? 'up' : 'down' },
        lastJobProcessed: {
          status: this.lastJobAt ? 'up' : 'unknown',
          timestamp: this.lastJobAt?.toISOString(),
          secondsAgo,
        },
        inFlightJobs: { count: this.inFlight, max: this.config.concurrency },
      },
    };
  }
}
```

## Job Timeout Utility

```typescript
// src/worker/utils.ts

export function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Job timed out after ${ms}ms`));
    }, ms);

    promise
      .then((val) => {
        clearTimeout(timer);
        resolve(val);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

export function exponentialBackoff(attempt: number): number {
  const baseMs = 1000;
  const maxMs = 300_000; // 5 minutes
  const delay = Math.min(baseMs * Math.pow(2, attempt - 1), maxMs);
  // Full jitter
  return Math.floor(Math.random() * delay);
}
```

## Job Producer

```typescript
// src/worker/producer.ts

import { Queue } from 'bullmq';
import { v4 as uuidv4 } from 'uuid';

export class JobProducer {
  private queues = new Map<string, Queue>();
  private connection: Redis;

  constructor(redisUrl: string) {
    this.connection = new Redis(redisUrl);
  }

  private getQueue(name: string): Queue {
    if (!this.queues.has(name)) {
      this.queues.set(name, new Queue(name, { connection: this.connection }));
    }
    return this.queues.get(name)!;
  }

  async enqueue<T>(
    queueName: string,
    jobType: string,
    payload: T & { tenantId: string },
    options: { delay?: number; priority?: number } = {},
  ): Promise<string> {
    const jobId = uuidv4();
    const queue = this.getQueue(queueName);

    await queue.add(jobType, {
      id: jobId,
      tenantId: payload.tenantId,
      payload,
      createdAt: new Date().toISOString(),
    }, {
      jobId,
      delay: options.delay,
      priority: options.priority,
      attempts: 5,
      backoff: { type: 'custom' },
      removeOnComplete: { count: 1000 },
      removeOnFail: { count: 5000 },
    });

    return jobId;
  }
}
```

## Scheduled Jobs with node-cron

```typescript
// src/worker/scheduler.ts

import cron from 'node-cron';
import { Logger } from 'pino';

interface ScheduledJob {
  name: string;
  schedule: string; // cron expression
  fn: () => Promise<void>;
}

interface LockStore {
  tryAcquire(key: string, ttlMs: number): Promise<boolean>;
  release(key: string): Promise<void>;
}

export class Scheduler {
  private tasks: cron.ScheduledTask[] = [];

  constructor(
    private lockStore: LockStore,
    private logger: Logger,
  ) {}

  register(jobs: ScheduledJob[]): void {
    for (const job of jobs) {
      const task = cron.schedule(job.schedule, async () => {
        await this.executeWithLock(job);
      });
      this.tasks.push(task);
      this.logger.info({ job: job.name, schedule: job.schedule }, 'cron.registered');
    }
  }

  private async executeWithLock(job: ScheduledJob): Promise<void> {
    const lockKey = `cron:${job.name}`;
    const acquired = await this.lockStore.tryAcquire(lockKey, 300_000);
    if (!acquired) {
      this.logger.debug({ job: job.name }, 'cron.lock_not_acquired');
      return;
    }

    const start = Date.now();
    this.logger.info({ job: job.name }, 'cron.started');

    try {
      await job.fn();
      this.logger.info({ job: job.name, durationMs: Date.now() - start }, 'cron.completed');
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      this.logger.error({ job: job.name, error: msg }, 'cron.failed');
    } finally {
      await this.lockStore.release(lockKey);
    }
  }

  stop(): void {
    this.tasks.forEach((t) => t.stop());
    this.tasks = [];
    this.logger.info('scheduler.stopped');
  }
}
```

## Example: Email Send Handler

```typescript
// src/handlers/email-send.handler.ts

import { JobHandler, Job } from '../worker/types';
import { EmailService } from '../services/email.service';
import { IdempotencyStore } from '../services/idempotency.store';

interface EmailPayload {
  tenantId: string;
  to: string;
  subject: string;
  templateId: string;
  variables: Record<string, unknown>;
}

export class EmailSendHandler implements JobHandler<EmailPayload> {
  readonly type = 'email.send';

  constructor(
    private emailService: EmailService,
    private idempotency: IdempotencyStore,
  ) {}

  async handle(job: Job<EmailPayload>): Promise<void> {
    // Idempotency check
    if (await this.idempotency.isProcessed(job.id)) {
      return; // Already sent
    }

    const { to, subject, templateId, variables } = job.payload;

    const html = await this.emailService.renderTemplate(templateId, variables);
    await this.emailService.send({ to, subject, html });

    await this.idempotency.markProcessed(job.id, 86_400_000); // 24h TTL
  }
}
```

## Main Entrypoint

```typescript
// src/worker/main.ts

import pino from 'pino';
import { WorkerService } from './bull-worker';
import { EmailSendHandler } from '../handlers/email-send.handler';
import { ReportGenerateHandler } from '../handlers/report-generate.handler';

async function main(): Promise<void> {
  const logger = pino({ level: 'info' });
  const config = loadConfig();

  const worker = new WorkerService(config.redisUrl, logger, {
    concurrency: config.workerConcurrency,
    jobTimeoutMs: config.jobTimeoutMs,
    maxRetries: 5,
  });

  // Register handlers
  worker.register(new EmailSendHandler(emailService, idempotencyStore));
  worker.register(new ReportGenerateHandler(reportService));

  // Start consuming
  await worker.start(['email', 'reports', 'default']);

  logger.info('worker.running');
}

main().catch((err) => {
  console.error('Worker fatal error:', err);
  process.exit(1);
});
```

## Critical Rules

- Use `BullMQ` (not legacy `Bull`) — it supports streams, groups, and modern Redis features
- Set `maxRetriesPerRequest: null` on Redis connection — required for BullMQ blocking commands
- Use `worker.close()` for graceful shutdown — it waits for in-flight jobs to finish
- Set `removeOnComplete` and `removeOnFail` limits — prevent Redis memory exhaustion
- Use `backoff: { type: 'custom' }` with a `backoffStrategy` — BullMQ invokes it per retry
- Idempotency check MUST happen inside the handler, not at enqueue time
- Every handler MUST be stateless — no mutable instance state shared across jobs
- Signal handlers (`SIGTERM`, `SIGINT`) MUST call `process.exit()` after cleanup — Node won't exit on its own
- Use `pino` for structured JSON logging — include `jobId`, `jobType`, `tenantId`, `attempt` in every log
- Queue names should match job categories: `email`, `reports`, `notifications` — not one mega-queue
