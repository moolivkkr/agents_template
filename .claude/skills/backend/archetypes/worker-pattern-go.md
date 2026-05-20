---
skill: worker-pattern-go
description: Go worker/background job archetype — goroutines, channels, signal handling, graceful shutdown, context cancellation, errgroup coordination
version: "1.0"
tags:
  - go
  - worker
  - background-job
  - goroutines
  - channels
  - archetype
  - backend
---

# Worker / Background Job Pattern — Go

> **Canonical reference**: This is the Go counterpart to `worker-pattern.md` (language-neutral). Read that first for concepts and contracts.

Go workers leverage goroutines, channels, and `context.Context` for cancellation. Use `errgroup` for coordinating multiple concurrent consumers.

## Worker Struct and Constructor

```go
package worker

import (
    "context"
    "fmt"
    "log/slog"
    "math"
    "math/rand"
    "sync"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/trace"
    "golang.org/x/sync/errgroup"

    "yourapp/internal/domain"
)

// JobHandler processes a single job. Implementations must be idempotent.
type JobHandler interface {
    Handle(ctx context.Context, job *domain.Job) error
    Type() string // e.g., "email.send"
}

// Queue abstracts the message broker (Redis, SQS, RabbitMQ, NATS).
type Queue interface {
    Receive(ctx context.Context, timeout time.Duration) (*domain.Job, error)
    Ack(ctx context.Context, job *domain.Job) error
    Nack(ctx context.Context, job *domain.Job, retryAfter time.Duration) error
    SendToDLQ(ctx context.Context, job *domain.Job, reason string) error
    HealthCheck(ctx context.Context) error
}

// IdempotencyStore tracks processed job IDs to prevent duplicate execution.
type IdempotencyStore interface {
    IsProcessed(ctx context.Context, jobID string) (bool, error)
    MarkProcessed(ctx context.Context, jobID string, ttl time.Duration) error
}

type Worker struct {
    queue       Queue
    handlers    map[string]JobHandler
    idempotency IdempotencyStore
    logger      *slog.Logger
    tracer      trace.Tracer

    concurrency     int
    jobTimeout      time.Duration
    shutdownTimeout time.Duration
    maxRetries      int

    mu        sync.Mutex
    inFlight  int
    lastJobAt time.Time
}

type Config struct {
    Concurrency     int           // number of concurrent consumers (default: 5)
    JobTimeout      time.Duration // max time per job (default: 5m)
    ShutdownTimeout time.Duration // max time to drain on shutdown (default: 30s)
    MaxRetries      int           // max retry attempts (default: 5)
}

func New(queue Queue, idem IdempotencyStore, logger *slog.Logger, cfg Config) *Worker {
    if cfg.Concurrency <= 0 {
        cfg.Concurrency = 5
    }
    if cfg.JobTimeout <= 0 {
        cfg.JobTimeout = 5 * time.Minute
    }
    if cfg.ShutdownTimeout <= 0 {
        cfg.ShutdownTimeout = 30 * time.Second
    }
    if cfg.MaxRetries <= 0 {
        cfg.MaxRetries = 5
    }

    return &Worker{
        queue:           queue,
        handlers:        make(map[string]JobHandler),
        idempotency:     idem,
        logger:          logger.With("component", "worker"),
        tracer:          otel.Tracer("worker"),
        concurrency:     cfg.Concurrency,
        jobTimeout:      cfg.JobTimeout,
        shutdownTimeout: cfg.ShutdownTimeout,
        maxRetries:      cfg.MaxRetries,
    }
}

// Register adds a handler for a job type. Call before Run.
func (w *Worker) Register(handler JobHandler) {
    w.handlers[handler.Type()] = handler
}
```

## Main Run Loop with Graceful Shutdown

```go
// Run starts the worker and blocks until ctx is cancelled.
// Use signal.NotifyContext in main() to wire OS signals.
func (w *Worker) Run(ctx context.Context) error {
    w.logger.InfoContext(ctx, "worker.starting",
        "concurrency", w.concurrency,
        "handlers", len(w.handlers),
    )

    g, gCtx := errgroup.WithContext(ctx)

    for i := 0; i < w.concurrency; i++ {
        consumerID := fmt.Sprintf("consumer-%d", i)
        g.Go(func() error {
            return w.consumeLoop(gCtx, consumerID)
        })
    }

    // Wait for all consumers to finish
    err := g.Wait()
    w.logger.InfoContext(ctx, "worker.shutdown_complete")
    return err
}

func (w *Worker) consumeLoop(ctx context.Context, consumerID string) error {
    logger := w.logger.With("consumer", consumerID)
    logger.InfoContext(ctx, "consumer.started")

    for {
        select {
        case <-ctx.Done():
            logger.InfoContext(ctx, "consumer.stopping")
            return nil
        default:
        }

        job, err := w.queue.Receive(ctx, 30*time.Second)
        if err != nil {
            if ctx.Err() != nil {
                return nil // context cancelled during receive
            }
            logger.ErrorContext(ctx, "queue.receive_error", "error", err)
            time.Sleep(time.Second) // back off on queue errors
            continue
        }
        if job == nil {
            continue // no jobs available
        }

        w.processJob(ctx, logger, job)
    }
}
```

## Job Processing with Timeout and Idempotency

```go
func (w *Worker) processJob(ctx context.Context, logger *slog.Logger, job *domain.Job) {
    jobLogger := logger.With(
        "job_id", job.ID,
        "job_type", job.Type,
        "tenant_id", job.TenantID,
        "attempt", job.Attempt,
    )

    ctx, span := w.tracer.Start(ctx, "worker.process."+job.Type,
        trace.WithAttributes(
            attribute.String("job.id", job.ID),
            attribute.String("job.type", job.Type),
            attribute.String("tenant.id", job.TenantID),
            attribute.Int("job.attempt", job.Attempt),
        ),
    )
    defer span.End()

    w.mu.Lock()
    w.inFlight++
    w.mu.Unlock()
    defer func() {
        w.mu.Lock()
        w.inFlight--
        w.mu.Unlock()
    }()

    start := time.Now()

    // Idempotency check
    processed, err := w.idempotency.IsProcessed(ctx, job.ID)
    if err != nil {
        jobLogger.ErrorContext(ctx, "idempotency.check_failed", "error", err)
        // Continue processing — better to duplicate than to drop
    }
    if processed {
        jobLogger.InfoContext(ctx, "job.duplicate_skipped")
        _ = w.queue.Ack(ctx, job)
        return
    }

    // Find handler
    handler, ok := w.handlers[job.Type]
    if !ok {
        jobLogger.ErrorContext(ctx, "job.unknown_type")
        _ = w.queue.SendToDLQ(ctx, job, "unknown job type: "+job.Type)
        return
    }

    // Execute with timeout
    jobCtx, cancel := context.WithTimeout(ctx, w.jobTimeout)
    defer cancel()

    if err := handler.Handle(jobCtx, job); err != nil {
        span.RecordError(err)
        elapsed := time.Since(start)
        jobLogger.ErrorContext(ctx, "job.failed",
            "error", err,
            "duration", elapsed,
        )

        // Retry or dead-letter
        if job.Attempt >= w.maxRetries {
            _ = w.queue.SendToDLQ(ctx, job, err.Error())
            jobLogger.WarnContext(ctx, "job.dead_lettered")
        } else {
            delay := exponentialBackoff(job.Attempt)
            _ = w.queue.Nack(ctx, job, delay)
        }
        return
    }

    // Success
    elapsed := time.Since(start)
    _ = w.idempotency.MarkProcessed(ctx, job.ID, 24*time.Hour)
    _ = w.queue.Ack(ctx, job)

    w.mu.Lock()
    w.lastJobAt = time.Now()
    w.mu.Unlock()

    jobLogger.InfoContext(ctx, "job.completed", "duration", elapsed)
}
```

## Exponential Backoff with Jitter

```go
func exponentialBackoff(attempt int) time.Duration {
    base := time.Second
    maxDelay := 5 * time.Minute

    delay := base * time.Duration(math.Pow(2, float64(attempt-1)))
    if delay > maxDelay {
        delay = maxDelay
    }

    // Full jitter to prevent thundering herd
    jitter := time.Duration(rand.Int63n(int64(delay)))
    return jitter
}
```

## Cron / Scheduled Job with Leader Election

```go
package cron

import (
    "context"
    "log/slog"
    "time"
)

// LockStore provides distributed locking for leader election.
type LockStore interface {
    TryAcquire(ctx context.Context, key string, holder string, ttl time.Duration) (bool, error)
    Release(ctx context.Context, key string, holder string) error
}

type ScheduledJob struct {
    Name     string
    Interval time.Duration
    Fn       func(ctx context.Context) error
}

type Scheduler struct {
    lockStore  LockStore
    instanceID string
    logger     *slog.Logger
}

func NewScheduler(lockStore LockStore, instanceID string, logger *slog.Logger) *Scheduler {
    return &Scheduler{
        lockStore:  lockStore,
        instanceID: instanceID,
        logger:     logger.With("component", "scheduler"),
    }
}

// RunAll starts all scheduled jobs. Blocks until ctx is cancelled.
func (s *Scheduler) RunAll(ctx context.Context, jobs []ScheduledJob) error {
    g, gCtx := errgroup.WithContext(ctx)

    for _, job := range jobs {
        job := job
        g.Go(func() error {
            return s.runScheduled(gCtx, job)
        })
    }

    return g.Wait()
}

func (s *Scheduler) runScheduled(ctx context.Context, job ScheduledJob) error {
    ticker := time.NewTicker(job.Interval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return nil
        case <-ticker.C:
            s.executeWithLock(ctx, job)
        }
    }
}

func (s *Scheduler) executeWithLock(ctx context.Context, job ScheduledJob) {
    acquired, err := s.lockStore.TryAcquire(ctx, "cron:"+job.Name, s.instanceID, job.Interval)
    if err != nil {
        s.logger.ErrorContext(ctx, "cron.lock_error", "job", job.Name, "error", err)
        return
    }
    if !acquired {
        return // another instance is running this job
    }

    defer func() {
        _ = s.lockStore.Release(ctx, "cron:"+job.Name, s.instanceID)
    }()

    start := time.Now()
    s.logger.InfoContext(ctx, "cron.started", "job", job.Name)

    if err := job.Fn(ctx); err != nil {
        s.logger.ErrorContext(ctx, "cron.failed", "job", job.Name, "error", err, "duration", time.Since(start))
        return
    }

    s.logger.InfoContext(ctx, "cron.completed", "job", job.Name, "duration", time.Since(start))
}
```

## Health Check Endpoint

```go
// HealthStatus returns the worker health for liveness/readiness probes.
func (w *Worker) HealthStatus(ctx context.Context) HealthResponse {
    w.mu.Lock()
    inFlight := w.inFlight
    lastJob := w.lastJobAt
    w.mu.Unlock()

    status := "healthy"
    checks := map[string]CheckResult{}

    // Queue connection
    if err := w.queue.HealthCheck(ctx); err != nil {
        status = "unhealthy"
        checks["queue_connection"] = CheckResult{Status: "down", Error: err.Error()}
    } else {
        checks["queue_connection"] = CheckResult{Status: "up"}
    }

    // Last job recency
    if !lastJob.IsZero() {
        ago := time.Since(lastJob)
        checks["last_job_processed"] = CheckResult{
            Status:    "up",
            Timestamp: lastJob.Format(time.RFC3339),
            SecondsAgo: int(ago.Seconds()),
        }
        if ago > 5*time.Minute {
            status = "degraded"
        }
    }

    // In-flight count
    checks["in_flight_jobs"] = CheckResult{
        Count: inFlight,
        Max:   w.concurrency,
    }

    return HealthResponse{Status: status, Checks: checks}
}

type HealthResponse struct {
    Status string                  `json:"status"`
    Checks map[string]CheckResult  `json:"checks"`
}

type CheckResult struct {
    Status     string `json:"status,omitempty"`
    Error      string `json:"error,omitempty"`
    Timestamp  string `json:"timestamp,omitempty"`
    SecondsAgo int    `json:"seconds_ago,omitempty"`
    Count      int    `json:"count,omitempty"`
    Max        int    `json:"max,omitempty"`
}
```

## Main Entrypoint with Signal Handling

```go
package main

import (
    "context"
    "log/slog"
    "os"
    "os/signal"
    "syscall"

    "yourapp/internal/worker"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

    // Graceful shutdown via OS signals
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()

    // Wire dependencies
    queue := newRedisQueue(cfg.RedisURL)       // your queue implementation
    idem := newRedisIdempotency(cfg.RedisURL)  // your idempotency store
    emailSvc := newEmailService(cfg)
    reportSvc := newReportService(cfg)

    w := worker.New(queue, idem, logger, worker.Config{
        Concurrency:     cfg.WorkerConcurrency,
        JobTimeout:      cfg.JobTimeout,
        ShutdownTimeout: cfg.ShutdownTimeout,
        MaxRetries:      5,
    })

    // Register handlers
    w.Register(&EmailSendHandler{svc: emailSvc})
    w.Register(&ReportGenerateHandler{svc: reportSvc})

    // Run (blocks until SIGTERM/SIGINT)
    if err := w.Run(ctx); err != nil {
        logger.Error("worker.fatal", "error", err)
        os.Exit(1)
    }
}
```

## Example: Email Send Handler

```go
type EmailSendHandler struct {
    svc EmailService
}

func (h *EmailSendHandler) Type() string { return "email.send" }

func (h *EmailSendHandler) Handle(ctx context.Context, job *domain.Job) error {
    var payload EmailPayload
    if err := json.Unmarshal(job.Payload, &payload); err != nil {
        return fmt.Errorf("unmarshal email payload: %w", err)
    }

    html, err := h.svc.RenderTemplate(ctx, payload.TemplateID, payload.Variables)
    if err != nil {
        return fmt.Errorf("render template %s: %w", payload.TemplateID, err)
    }

    if err := h.svc.Send(ctx, payload.To, payload.Subject, html); err != nil {
        return fmt.Errorf("send email to %s: %w", payload.To, err)
    }

    return nil
}
```

## Critical Rules

- Use `signal.NotifyContext` for OS signal handling — never `os.Signal` channels manually
- Use `errgroup.Group` to coordinate multiple goroutines — propagates first error
- Use `context.WithTimeout` per job — prevents hung jobs from blocking the worker
- Channel sends/receives MUST always have a `ctx.Done()` select case to prevent goroutine leaks
- Never use `sync.WaitGroup` when `errgroup` suffices — errgroup handles errors
- Worker struct fields accessed from multiple goroutines MUST use `sync.Mutex`
- Idempotency check failures should NOT prevent job processing — log and continue
- All logging MUST include `job_id`, `job_type`, `tenant_id`, and `attempt`
