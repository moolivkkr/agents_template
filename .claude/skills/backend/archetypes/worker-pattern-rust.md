---
skill: worker-pattern-rust
description: Rust worker/background job archetype — tokio::spawn, async channels, CancellationToken, graceful shutdown, tracing instrumentation
version: "1.0"
tags:
  - rust
  - worker
  - tokio
  - background-job
  - archetype
  - backend
---

# Worker / Background Job Pattern — Rust

> **Canonical reference**: This is the Rust counterpart to `worker-pattern.md` (language-neutral). Read that first for concepts and contracts.

Rust workers use `tokio` for async runtime, `tokio::sync::mpsc` for in-process channels, and `CancellationToken` for graceful shutdown. For external queues, use `lapin` (RabbitMQ), `rdkafka` (Kafka), or `redis` crate with streams.

## Job Domain Types

```rust
// src/worker/job.rs

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    pub id: String,
    pub job_type: String,
    pub payload: serde_json::Value,
    pub tenant_id: Uuid,
    pub attempt: u32,
    pub max_retries: u32,
    pub created_at: DateTime<Utc>,
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DlqEntry {
    pub original_job: Job,
    pub error: String,
    pub failed_at: DateTime<Utc>,
}
```

## Worker Traits

```rust
// src/worker/traits.rs

use async_trait::async_trait;
use std::time::Duration;

#[async_trait]
pub trait JobHandler: Send + Sync + 'static {
    fn job_type(&self) -> &str;
    async fn handle(&self, job: &Job) -> Result<(), WorkerError>;
}

#[async_trait]
pub trait Queue: Send + Sync + 'static {
    async fn receive(&self, timeout: Duration) -> Result<Option<Job>, WorkerError>;
    async fn ack(&self, job: &Job) -> Result<(), WorkerError>;
    async fn nack(&self, job: &Job, retry_after: Duration) -> Result<(), WorkerError>;
    async fn send_to_dlq(&self, job: &Job, reason: &str) -> Result<(), WorkerError>;
    async fn health_check(&self) -> Result<(), WorkerError>;
}

#[async_trait]
pub trait IdempotencyStore: Send + Sync + 'static {
    async fn is_processed(&self, job_id: &str) -> Result<bool, WorkerError>;
    async fn mark_processed(&self, job_id: &str, ttl: Duration) -> Result<(), WorkerError>;
}

#[derive(Debug, thiserror::Error)]
pub enum WorkerError {
    #[error("queue error: {0}")]
    Queue(String),
    #[error("handler error: {0}")]
    Handler(String),
    #[error("timeout")]
    Timeout,
    #[error("shutdown")]
    Shutdown,
}
```

## Worker Implementation

```rust
// src/worker/mod.rs

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

use tokio::sync::Mutex;
use tokio_util::sync::CancellationToken;
use tracing::{error, info, warn, instrument, Instrument};

pub struct Worker {
    queue: Arc<dyn Queue>,
    handlers: HashMap<String, Arc<dyn JobHandler>>,
    idempotency: Arc<dyn IdempotencyStore>,
    config: WorkerConfig,
    state: Arc<Mutex<WorkerState>>,
}

pub struct WorkerConfig {
    pub concurrency: usize,
    pub job_timeout: Duration,
    pub shutdown_timeout: Duration,
    pub max_retries: u32,
}

impl Default for WorkerConfig {
    fn default() -> Self {
        Self {
            concurrency: 5,
            job_timeout: Duration::from_secs(300),
            shutdown_timeout: Duration::from_secs(30),
            max_retries: 5,
        }
    }
}

struct WorkerState {
    in_flight: u32,
    last_job_at: Option<Instant>,
}

impl Worker {
    pub fn new(
        queue: Arc<dyn Queue>,
        idempotency: Arc<dyn IdempotencyStore>,
        config: WorkerConfig,
    ) -> Self {
        Self {
            queue,
            handlers: HashMap::new(),
            idempotency,
            config,
            state: Arc::new(Mutex::new(WorkerState {
                in_flight: 0,
                last_job_at: None,
            })),
        }
    }

    pub fn register(&mut self, handler: Arc<dyn JobHandler>) {
        self.handlers
            .insert(handler.job_type().to_string(), handler);
    }

    /// Run the worker until the cancellation token is triggered.
    pub async fn run(&self, cancel: CancellationToken) -> Result<(), WorkerError> {
        info!(
            concurrency = self.config.concurrency,
            handlers = self.handlers.len(),
            "worker.starting"
        );

        let mut tasks = Vec::new();

        for i in 0..self.config.concurrency {
            let consumer_id = format!("consumer-{i}");
            let cancel = cancel.clone();
            let queue = self.queue.clone();
            let handlers = self.handlers.clone();
            let idempotency = self.idempotency.clone();
            let config = WorkerConfig {
                concurrency: self.config.concurrency,
                job_timeout: self.config.job_timeout,
                shutdown_timeout: self.config.shutdown_timeout,
                max_retries: self.config.max_retries,
            };
            let state = self.state.clone();

            let task = tokio::spawn(async move {
                consume_loop(
                    consumer_id, cancel, queue, handlers, idempotency, config, state,
                )
                .await
            });
            tasks.push(task);
        }

        // Wait for cancellation
        cancel.cancelled().await;
        info!("worker.shutdown_requested");

        // Wait for tasks to finish with timeout
        let drain = async {
            for task in tasks {
                let _ = task.await;
            }
        };

        tokio::select! {
            _ = drain => info!("worker.drained"),
            _ = tokio::time::sleep(self.config.shutdown_timeout) => {
                warn!("worker.shutdown_timeout");
            }
        }

        info!("worker.shutdown_complete");
        Ok(())
    }
}

async fn consume_loop(
    consumer_id: String,
    cancel: CancellationToken,
    queue: Arc<dyn Queue>,
    handlers: HashMap<String, Arc<dyn JobHandler>>,
    idempotency: Arc<dyn IdempotencyStore>,
    config: WorkerConfig,
    state: Arc<Mutex<WorkerState>>,
) {
    info!(consumer = %consumer_id, "consumer.started");

    loop {
        if cancel.is_cancelled() {
            info!(consumer = %consumer_id, "consumer.stopping");
            return;
        }

        let job = tokio::select! {
            _ = cancel.cancelled() => return,
            result = queue.receive(Duration::from_secs(30)) => {
                match result {
                    Ok(Some(job)) => job,
                    Ok(None) => continue,
                    Err(e) => {
                        error!(consumer = %consumer_id, error = %e, "queue.receive_error");
                        tokio::time::sleep(Duration::from_secs(1)).await;
                        continue;
                    }
                }
            }
        };

        process_job(&job, &queue, &handlers, &idempotency, &config, &state).await;
    }
}

#[instrument(skip_all, fields(job_id = %job.id, job_type = %job.job_type, tenant_id = %job.tenant_id, attempt = job.attempt))]
async fn process_job(
    job: &Job,
    queue: &Arc<dyn Queue>,
    handlers: &HashMap<String, Arc<dyn JobHandler>>,
    idempotency: &Arc<dyn IdempotencyStore>,
    config: &WorkerConfig,
    state: &Arc<Mutex<WorkerState>>,
) {
    {
        let mut s = state.lock().await;
        s.in_flight += 1;
    }

    let start = Instant::now();

    // Idempotency check
    match idempotency.is_processed(&job.id).await {
        Ok(true) => {
            info!("job.duplicate_skipped");
            let _ = queue.ack(job).await;
            let mut s = state.lock().await;
            s.in_flight -= 1;
            return;
        }
        Err(e) => {
            warn!(error = %e, "idempotency.check_failed");
            // Continue processing — duplicates are better than drops
        }
        _ => {}
    }

    // Find handler
    let handler = match handlers.get(&job.job_type) {
        Some(h) => h,
        None => {
            error!("job.unknown_type");
            let _ = queue.send_to_dlq(job, &format!("unknown type: {}", job.job_type)).await;
            let mut s = state.lock().await;
            s.in_flight -= 1;
            return;
        }
    };

    // Execute with timeout
    let result = tokio::time::timeout(config.job_timeout, handler.handle(job)).await;

    match result {
        Ok(Ok(())) => {
            let elapsed = start.elapsed();
            let _ = idempotency.mark_processed(&job.id, Duration::from_secs(86400)).await;
            let _ = queue.ack(job).await;

            let mut s = state.lock().await;
            s.last_job_at = Some(Instant::now());
            s.in_flight -= 1;

            info!(duration_ms = elapsed.as_millis() as u64, "job.completed");
        }
        Ok(Err(e)) => {
            error!(error = %e, "job.failed");
            retry_or_dlq(job, queue, config, &e.to_string()).await;
            let mut s = state.lock().await;
            s.in_flight -= 1;
        }
        Err(_) => {
            error!("job.timeout");
            retry_or_dlq(job, queue, config, "timeout").await;
            let mut s = state.lock().await;
            s.in_flight -= 1;
        }
    }
}

async fn retry_or_dlq(job: &Job, queue: &Arc<dyn Queue>, config: &WorkerConfig, reason: &str) {
    if job.attempt >= config.max_retries {
        let _ = queue.send_to_dlq(job, reason).await;
        warn!("job.dead_lettered");
    } else {
        let delay = exponential_backoff(job.attempt);
        let _ = queue.nack(job, delay).await;
    }
}

fn exponential_backoff(attempt: u32) -> Duration {
    use rand::Rng;
    let base_ms: u64 = 1000;
    let max_ms: u64 = 300_000;
    let delay_ms = (base_ms * 2u64.pow(attempt.saturating_sub(1))).min(max_ms);
    let jitter_ms = rand::thread_rng().gen_range(0..=delay_ms);
    Duration::from_millis(jitter_ms)
}
```

## Main Entrypoint with Signal Handling

```rust
// src/main.rs

use tokio_util::sync::CancellationToken;
use tracing::info;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let cancel = CancellationToken::new();

    // Wire dependencies
    let queue = Arc::new(RedisQueue::new(&config.redis_url).await?);
    let idempotency = Arc::new(RedisIdempotency::new(&config.redis_url).await?);

    let mut worker = Worker::new(queue, idempotency, WorkerConfig::default());
    worker.register(Arc::new(EmailSendHandler::new(email_svc)));
    worker.register(Arc::new(ReportGenerateHandler::new(report_svc)));

    // Signal handling
    let cancel_clone = cancel.clone();
    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        info!("received SIGINT");
        cancel_clone.cancel();
    });

    worker.run(cancel).await?;

    Ok(())
}
```

## Example: Email Send Handler

```rust
pub struct EmailSendHandler {
    email_svc: Arc<EmailService>,
}

impl EmailSendHandler {
    pub fn new(email_svc: Arc<EmailService>) -> Self {
        Self { email_svc }
    }
}

#[async_trait]
impl JobHandler for EmailSendHandler {
    fn job_type(&self) -> &str {
        "email.send"
    }

    async fn handle(&self, job: &Job) -> Result<(), WorkerError> {
        let payload: EmailPayload = serde_json::from_value(job.payload.clone())
            .map_err(|e| WorkerError::Handler(format!("invalid payload: {e}")))?;

        let html = self
            .email_svc
            .render_template(&payload.template_id, &payload.variables)
            .await
            .map_err(|e| WorkerError::Handler(format!("template render: {e}")))?;

        self.email_svc
            .send(&payload.to, &payload.subject, &html)
            .await
            .map_err(|e| WorkerError::Handler(format!("send email: {e}")))?;

        Ok(())
    }
}
```

## Health Check

```rust
use axum::{Json, extract::State};
use serde::Serialize;

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub in_flight: u32,
    pub last_job_seconds_ago: Option<u64>,
}

pub async fn worker_health(State(state): State<Arc<Mutex<WorkerState>>>) -> Json<HealthResponse> {
    let s = state.lock().await;
    let seconds_ago = s.last_job_at.map(|t| t.elapsed().as_secs());
    let status = if seconds_ago.map_or(false, |s| s > 300) {
        "degraded"
    } else {
        "healthy"
    };

    Json(HealthResponse {
        status: status.to_string(),
        in_flight: s.in_flight,
        last_job_seconds_ago: seconds_ago,
    })
}
```

## Critical Rules

- Use `CancellationToken` from `tokio-util` for cooperative shutdown — not raw channels
- Use `tokio::time::timeout` per job — prevents any single job from blocking forever
- Use `tokio::select!` with cancellation in receive loops — ensures consumers stop promptly
- Use `#[instrument]` from `tracing` for automatic span creation — include `job_id`, `tenant_id`
- Use `Arc<dyn Trait>` for handler and queue abstractions — enables testing with mocks
- Use `Mutex` from `tokio::sync` (not `std::sync`) when holding locks across `.await` points
- `async_trait` is required for async trait methods — Rust does not support them natively yet
- All error types MUST implement `thiserror::Error` for structured error propagation
- Handlers MUST be `Send + Sync + 'static` — required for `tokio::spawn`
