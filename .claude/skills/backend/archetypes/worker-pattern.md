---
skill: worker-pattern
description: Language-neutral worker/background job archetype — job queue consumer, cron/scheduled jobs, event handlers, retry with backoff, graceful shutdown, health checks, observability
version: "1.0"
tags:
  - worker
  - background-job
  - queue
  - cron
  - archetype
  - backend
---

# Worker / Background Job Pattern

Complete production-ready worker pattern for background job processing. Every generated worker MUST follow this pattern.

> **Language-specific variants**: See `worker-pattern-go.md`, `worker-pattern-python.md`, `worker-pattern-java.md`, `worker-pattern-rust.md`, `worker-pattern-typescript.md` for idiomatic implementations.

## Core Concepts

Workers are long-running processes that consume jobs from a queue, execute scheduled tasks, or react to events. They run independently of the HTTP server and must handle failures gracefully.

```
                    +------------------+
                    |   Job Producer   |
                    |  (API handler,   |
                    |   cron trigger,  |
                    |   event bus)     |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |    Job Queue     |
                    | (Redis, SQS,    |
                    |  RabbitMQ, NATS) |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        +-----------+  +-----------+  +-----------+
        | Worker 1  |  | Worker 2  |  | Worker 3  |
        | (consumer)|  | (consumer)|  | (consumer)|
        +-----------+  +-----------+  +-----------+
              |              |              |
              v              v              v
        +-----------+  +-----------+  +-----------+
        |  Process  |  |  Process  |  |  Process  |
        |  + ACK    |  |  + ACK    |  |  + ACK    |
        +-----------+  +-----------+  +-----------+
              |
              v (on failure after max retries)
        +-----------+
        | Dead Letter|
        |   Queue   |
        +-----------+
```

## Job Queue Consumer Pattern

The consumer pulls jobs from a queue, processes them, and acknowledges or rejects them.

### Job Envelope

```
Job {
    id:             UUID        // unique job ID for idempotency
    type:           string      // "email.send", "report.generate"
    payload:        JSON        // job-specific data
    tenant_id:      UUID        // tenant scope
    created_at:     timestamp   // when the job was enqueued
    scheduled_at:   timestamp   // earliest execution time (for delayed jobs)
    attempt:        int         // current attempt number (starts at 1)
    max_retries:    int         // maximum retry attempts
    correlation_id: string      // trace correlation ID
    priority:       int         // 0 = normal, 1 = high, -1 = low
}
```

### Consumer Lifecycle

```
1. CONNECT    — Establish connection to queue broker
2. SUBSCRIBE  — Register as consumer for one or more job types
3. RECEIVE    — Pull/push job from queue (blocking or callback)
4. VALIDATE   — Check job envelope, verify tenant context
5. PROCESS    — Execute job handler (with timeout)
6. ACK/NACK   — Acknowledge success or reject for retry
7. REPEAT     — Go to step 3
8. SHUTDOWN   — Drain in-flight jobs, close connection
```

### Pseudocode

```
function consume(ctx, queue, handler):
    while not ctx.cancelled():
        job = queue.receive(ctx, timeout=30s)
        if job == null:
            continue  // no jobs available, loop back

        logger.info("job.received", job_id=job.id, type=job.type, attempt=job.attempt)
        span = tracer.start_span("worker.process", attributes={job.type, job.id})

        try:
            // Set timeout per job (prevent hung jobs)
            job_ctx = with_timeout(ctx, job_timeout)

            // Idempotency check
            if already_processed(job.id):
                queue.ack(job)
                continue

            // Process
            handler.handle(job_ctx, job)

            // Mark as processed (for idempotency)
            mark_processed(job.id, ttl=24h)

            queue.ack(job)
            metrics.increment("jobs.success", tags={type: job.type})

        catch error:
            span.record_error(error)
            logger.error("job.failed", job_id=job.id, error=error, attempt=job.attempt)
            metrics.increment("jobs.failure", tags={type: job.type})

            if job.attempt >= job.max_retries:
                queue.send_to_dlq(job, error)
                logger.warn("job.dead_lettered", job_id=job.id)
            else:
                delay = exponential_backoff(job.attempt)
                queue.nack(job, retry_after=delay)

        finally:
            span.end()
            metrics.histogram("jobs.duration", elapsed, tags={type: job.type})
```

## Cron / Scheduled Job Pattern

Periodic jobs run on a schedule with leader election to prevent duplicate execution across replicas.

### Leader Election

```
function acquire_leader_lock(ctx, lock_name, ttl):
    // Use distributed lock (Redis SETNX, PostgreSQL advisory lock, etcd lease)
    acquired = lock_store.try_acquire(lock_name, holder=instance_id, ttl=ttl)
    if not acquired:
        logger.debug("leader_lock.not_acquired", lock=lock_name)
        return false

    logger.info("leader_lock.acquired", lock=lock_name, holder=instance_id)
    return true

function run_scheduled(ctx, schedule, job_fn):
    while not ctx.cancelled():
        wait_until_next_tick(schedule)

        if not acquire_leader_lock(ctx, job_fn.name, ttl=schedule.interval):
            continue  // another instance is running this job

        try:
            span = tracer.start_span("cron." + job_fn.name)
            job_fn(ctx)
            metrics.increment("cron.success", tags={job: job_fn.name})
        catch error:
            logger.error("cron.failed", job=job_fn.name, error=error)
            metrics.increment("cron.failure", tags={job: job_fn.name})
        finally:
            span.end()
            release_leader_lock(job_fn.name)
```

### Schedule Specification

```
Schedule Types:
    "@every 5m"       — run every 5 minutes
    "@hourly"         — run at the top of every hour
    "0 */6 * * *"     — cron expression: every 6 hours
    "@daily"          — run once per day at midnight UTC
```

## Event Handler Pattern

Subscribe to domain events and process them idempotently.

```
function handle_event(ctx, event):
    // Idempotency: check if this event was already processed
    if event_store.is_processed(event.id):
        logger.info("event.duplicate", event_id=event.id)
        return

    // Process based on event type
    switch event.type:
        case "order.created":
            send_confirmation_email(ctx, event.payload)
        case "order.cancelled":
            process_refund(ctx, event.payload)
        case "user.registered":
            send_welcome_email(ctx, event.payload)

    // Mark as processed
    event_store.mark_processed(event.id, processed_at=now())
```

## Retry with Exponential Backoff

```
function exponential_backoff(attempt, base=1s, max_delay=5m, jitter=true):
    delay = base * (2 ^ (attempt - 1))
    delay = min(delay, max_delay)

    if jitter:
        // Full jitter prevents thundering herd
        delay = random(0, delay)

    return delay

// Retry schedule example:
// Attempt 1: immediate
// Attempt 2: ~1s  (0-2s with jitter)
// Attempt 3: ~2s  (0-4s with jitter)
// Attempt 4: ~4s  (0-8s with jitter)
// Attempt 5: ~8s  (0-16s with jitter)
// After max retries: send to dead letter queue
```

### Dead Letter Queue Handling

```
DLQ Entry {
    original_job:   Job         // the failed job
    error:          string      // last error message
    failed_at:      timestamp   // when it was dead-lettered
    attempts:       int         // total attempts made
}

// DLQ monitoring: alert when DLQ depth > threshold
// DLQ replay: manual or automated reprocessing after fix
```

## Graceful Shutdown

Workers MUST drain in-flight jobs before exiting. Never kill a worker mid-job.

```
function run_worker(config):
    ctx = create_cancellable_context()

    // Register signal handlers
    on_signal(SIGTERM, SIGINT):
        logger.info("worker.shutdown_requested")
        ctx.cancel()  // signals all goroutines/tasks to stop

    // Start consumer(s)
    consumers = start_consumers(ctx, config.concurrency)

    // Wait for all consumers to finish draining
    wait_for_all(consumers, timeout=config.shutdown_timeout)

    logger.info("worker.shutdown_complete")

Shutdown sequence:
    1. Receive SIGTERM/SIGINT
    2. Stop accepting new jobs (stop pulling from queue)
    3. Wait for in-flight jobs to complete (with timeout)
    4. If timeout expires, log warning and force exit
    5. Close queue connections
    6. Flush metrics and traces
    7. Exit with code 0
```

## Health Check for Workers

Workers expose a health endpoint separate from the HTTP server.

```
Health Check Response:
{
    "status": "healthy",          // healthy | degraded | unhealthy
    "checks": {
        "queue_connection": {
            "status": "up",
            "latency_ms": 2
        },
        "last_job_processed": {
            "status": "up",
            "timestamp": "2024-01-15T09:30:00Z",
            "seconds_ago": 45
        },
        "in_flight_jobs": {
            "count": 3,
            "max": 10
        }
    }
}

Health rules:
    - "unhealthy" if queue connection is down
    - "degraded" if no jobs processed in last 5 minutes (and queue is not empty)
    - "unhealthy" if in-flight jobs stuck for > job_timeout
```

## Observability

### Metrics

```
# Counters
jobs_processed_total{type, status=success|failure}
jobs_dead_lettered_total{type}
jobs_retried_total{type}

# Histograms
job_duration_seconds{type}
job_queue_wait_seconds{type}   // time from enqueue to dequeue

# Gauges
jobs_in_flight{type}
queue_depth{queue_name}
```

### Structured Logging

```
Every job log MUST include:
    - job_id
    - job_type
    - tenant_id
    - attempt number
    - correlation_id (for tracing)
    - duration (on completion)
    - error (on failure)
```

### Distributed Tracing

```
Each job creates a span linked to the producer's trace:
    - span name: "worker.{job_type}"
    - parent: extracted from job.correlation_id
    - attributes: job_id, tenant_id, attempt
```

## Example: Email Sending Worker

```
EmailJob {
    to:          string
    subject:     string
    template_id: string
    variables:   map[string]any
    tenant_id:   UUID
}

function handle_email_job(ctx, job):
    // 1. Validate
    validate_email(job.payload.to)

    // 2. Render template
    html = template_engine.render(job.payload.template_id, job.payload.variables)

    // 3. Send via provider (SendGrid, SES, Postmark)
    result = email_provider.send(ctx, {
        to:      job.payload.to,
        subject: job.payload.subject,
        html:    html,
    })

    // 4. Log delivery
    logger.info("email.sent",
        job_id=job.id,
        to=job.payload.to,
        template=job.payload.template_id,
        provider_id=result.message_id,
    )
```

## Example: Report Generation Worker

```
ReportJob {
    report_type:  string     // "monthly_summary", "usage_export"
    tenant_id:    UUID
    params:       map        // date range, filters
    requested_by: UUID
}

function handle_report_job(ctx, job):
    // 1. Query data (may be slow — use read replica)
    data = report_service.query(ctx, job.payload)

    // 2. Generate file (CSV, PDF)
    file = report_generator.generate(job.payload.report_type, data)

    // 3. Upload to storage
    url = storage.upload(ctx, "reports/{tenant}/{job.id}.csv", file)

    // 4. Notify requester
    notification_service.send(ctx, {
        user_id: job.payload.requested_by,
        type:    "report.ready",
        payload: { report_url: url },
    })
```

## Critical Rules

- Every job MUST have a unique ID for idempotency tracking
- Every job MUST include `tenant_id` — workers respect tenant isolation
- Job handlers MUST be idempotent — processing the same job twice produces the same result
- Workers MUST handle graceful shutdown — never kill mid-job
- Workers MUST implement retry with exponential backoff and jitter
- Failed jobs MUST go to a dead letter queue after max retries
- Workers MUST expose health checks for orchestrator liveness probes
- Job timeout MUST be enforced — no job runs forever
- Workers MUST emit metrics: success/failure counts, duration histograms, queue depth
- Workers MUST propagate trace context from producer to consumer
- Never put business logic in the worker main loop — delegate to handler functions
- Workers MUST NOT share state across job executions (stateless processing)
