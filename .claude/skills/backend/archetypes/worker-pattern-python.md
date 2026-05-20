---
skill: worker-pattern-python
description: Python worker/background job archetype — Celery, dramatiq, asyncio.Queue, APScheduler, graceful shutdown, structured logging
version: "1.0"
tags:
  - python
  - worker
  - celery
  - dramatiq
  - background-job
  - archetype
  - backend
---

# Worker / Background Job Pattern — Python

> **Canonical reference**: This is the Python counterpart to `worker-pattern.md` (language-neutral). Read that first for concepts and contracts.

Python workers typically use Celery (Redis/RabbitMQ) or dramatiq for task queues, and APScheduler or Celery Beat for scheduled jobs.

## Celery Worker Setup

```python
# app/worker/celery_app.py

from celery import Celery
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_retry,
    worker_shutting_down,
)
import structlog

logger = structlog.get_logger(__name__)

app = Celery("myapp")
app.config_from_object("app.config.celery_config")

# Auto-discover tasks in app/tasks/ modules
app.autodiscover_tasks(["app.tasks"])
```

```python
# app/config/celery_config.py

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/1"

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# Retry and timeout settings
task_acks_late = True                  # ACK after processing (not before)
task_reject_on_worker_lost = True      # Re-queue if worker dies mid-task
worker_prefetch_multiplier = 1         # Fetch one task at a time per worker
task_time_limit = 300                  # Hard kill after 5 minutes
task_soft_time_limit = 270             # Raise SoftTimeLimitExceeded at 4.5 min

# Dead letter queue
task_default_queue = "default"
task_routes = {
    "app.tasks.email.*": {"queue": "email"},
    "app.tasks.reports.*": {"queue": "reports"},
}

# Retry policy
task_default_retry_delay = 1           # 1 second base delay
task_max_retries = 5
```

## Task Definition with Retry and Idempotency

```python
# app/tasks/email.py

import uuid
from datetime import datetime, timezone

from celery import Task
from celery.utils.log import get_task_logger

from app.services.email import EmailService
from app.services.idempotency import IdempotencyStore
from app.worker.celery_app import app

logger = get_task_logger(__name__)


class BaseTask(Task):
    """Base task with structured logging and error handling."""

    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True           # Exponential backoff
    retry_backoff_max = 300        # Max 5 minutes between retries
    retry_jitter = True            # Add jitter to prevent thundering herd
    max_retries = 5

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task.failed",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "error": str(exc),
                "attempt": self.request.retries + 1,
            },
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "task.retrying",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "error": str(exc),
                "attempt": self.request.retries + 1,
            },
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "task.completed",
            extra={
                "task_id": task_id,
                "task_name": self.name,
            },
        )


@app.task(base=BaseTask, bind=True, name="app.tasks.email.send_email")
def send_email(
    self,
    *,
    job_id: str,
    tenant_id: str,
    to: str,
    subject: str,
    template_id: str,
    variables: dict,
) -> dict:
    """Send a transactional email. Idempotent by job_id."""
    log = logger.bind(
        job_id=job_id,
        tenant_id=tenant_id,
        task_id=self.request.id,
        attempt=self.request.retries + 1,
    )

    # Idempotency check
    idem = IdempotencyStore()
    if idem.is_processed(job_id):
        log.info("task.duplicate_skipped")
        return {"status": "duplicate", "job_id": job_id}

    log.info("email.sending", to=to, template=template_id)

    try:
        svc = EmailService()
        html = svc.render_template(template_id, variables)
        result = svc.send(to=to, subject=subject, html=html)

        idem.mark_processed(job_id, ttl_seconds=86400)

        log.info("email.sent", provider_id=result.message_id)
        return {"status": "sent", "message_id": result.message_id}

    except Exception as exc:
        log.error("email.failed", error=str(exc))
        raise self.retry(exc=exc)
```

## Dramatiq Alternative

```python
# app/tasks/email_dramatiq.py

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage, Retries, TimeLimits
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

# Configure broker
broker = RedisBroker(url="redis://localhost:6379/0")
broker.add_middleware(CurrentMessage())
broker.add_middleware(Retries(max_retries=5, min_backoff=1000, max_backoff=300_000))
broker.add_middleware(TimeLimits())
dramatiq.set_broker(broker)


@dramatiq.actor(
    queue_name="email",
    max_retries=5,
    min_backoff=1_000,    # 1 second
    max_backoff=300_000,  # 5 minutes
    time_limit=300_000,   # 5 minute hard limit
)
def send_email(
    job_id: str,
    tenant_id: str,
    to: str,
    subject: str,
    template_id: str,
    variables: dict,
) -> None:
    """Send email via dramatiq. Same idempotency contract as Celery version."""
    msg = CurrentMessage.get_current_message()
    attempt = (msg.options.get("retries", 0) if msg else 0) + 1

    logger.info("email.processing", job_id=job_id, attempt=attempt, tenant_id=tenant_id)

    idem = IdempotencyStore()
    if idem.is_processed(job_id):
        logger.info("task.duplicate_skipped", job_id=job_id)
        return

    svc = EmailService()
    html = svc.render_template(template_id, variables)
    svc.send(to=to, subject=subject, html=html)

    idem.mark_processed(job_id, ttl_seconds=86400)
    logger.info("email.sent", job_id=job_id, to=to)
```

## Asyncio Queue Worker (No External Broker)

```python
# app/worker/async_worker.py

import asyncio
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Job:
    id: str
    type: str
    payload: dict[str, Any]
    tenant_id: str
    attempt: int = 1
    max_retries: int = 5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AsyncWorker:
    """In-process async worker using asyncio.Queue. For single-process apps."""

    def __init__(self, concurrency: int = 5, job_timeout: float = 300.0):
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=1000)
        self._handlers: dict[str, Callable] = {}
        self._concurrency = concurrency
        self._job_timeout = job_timeout
        self._shutdown_event = asyncio.Event()
        self._in_flight = 0

    def register(self, job_type: str, handler: Callable[..., Coroutine]) -> None:
        self._handlers[job_type] = handler

    async def enqueue(self, job: Job) -> None:
        await self._queue.put(job)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)

        tasks = [
            asyncio.create_task(self._consume(f"consumer-{i}"))
            for i in range(self._concurrency)
        ]

        await self._shutdown_event.wait()
        logger.info("worker.shutdown_requested")

        # Drain: wait for in-flight to finish
        while self._in_flight > 0:
            await asyncio.sleep(0.1)

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("worker.shutdown_complete")

    async def _consume(self, consumer_id: str) -> None:
        while not self._shutdown_event.is_set():
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            self._in_flight += 1
            try:
                await self._process(consumer_id, job)
            finally:
                self._in_flight -= 1
                self._queue.task_done()

    async def _process(self, consumer_id: str, job: Job) -> None:
        log = logger.bind(
            consumer=consumer_id,
            job_id=job.id,
            job_type=job.type,
            tenant_id=job.tenant_id,
            attempt=job.attempt,
        )

        handler = self._handlers.get(job.type)
        if handler is None:
            log.error("job.unknown_type")
            return

        try:
            await asyncio.wait_for(handler(job), timeout=self._job_timeout)
            log.info("job.completed")
        except asyncio.TimeoutError:
            log.error("job.timeout")
        except Exception as exc:
            log.error("job.failed", error=str(exc))
            if job.attempt < job.max_retries:
                job.attempt += 1
                await self.enqueue(job)  # re-enqueue for retry
```

## Scheduled Jobs with APScheduler

```python
# app/worker/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import structlog

logger = structlog.get_logger(__name__)


def create_scheduler(lock_store) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Register scheduled jobs
    scheduler.add_job(
        run_with_lock(lock_store, cleanup_expired_sessions),
        trigger=IntervalTrigger(minutes=15),
        id="cleanup_expired_sessions",
        name="Cleanup expired sessions",
        replace_existing=True,
    )

    scheduler.add_job(
        run_with_lock(lock_store, generate_daily_report),
        trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM UTC
        id="generate_daily_report",
        name="Generate daily report",
        replace_existing=True,
    )

    return scheduler


def run_with_lock(lock_store, fn):
    """Wrapper that acquires a distributed lock before executing."""

    async def wrapper():
        lock_key = f"cron:{fn.__name__}"
        acquired = await lock_store.try_acquire(lock_key, ttl_seconds=300)
        if not acquired:
            logger.debug("cron.lock_not_acquired", job=fn.__name__)
            return

        try:
            logger.info("cron.started", job=fn.__name__)
            await fn()
            logger.info("cron.completed", job=fn.__name__)
        except Exception as exc:
            logger.error("cron.failed", job=fn.__name__, error=str(exc))
        finally:
            await lock_store.release(lock_key)

    return wrapper


async def cleanup_expired_sessions() -> None:
    """Remove sessions older than 24 hours."""
    # implementation here
    pass


async def generate_daily_report() -> None:
    """Generate and store daily usage report."""
    # implementation here
    pass
```

## Health Check

```python
# app/worker/health.py

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@dataclass
class WorkerHealth:
    queue_connected: bool
    last_job_at: datetime | None
    in_flight: int
    max_concurrency: int

    def status(self) -> str:
        if not self.queue_connected:
            return "unhealthy"
        if self.last_job_at:
            age = (datetime.now(timezone.utc) - self.last_job_at).total_seconds()
            if age > 300:
                return "degraded"
        return "healthy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status(),
            "checks": {
                "queue_connection": {
                    "status": "up" if self.queue_connected else "down",
                },
                "last_job_processed": {
                    "status": "up" if self.last_job_at else "unknown",
                    "timestamp": self.last_job_at.isoformat() if self.last_job_at else None,
                },
                "in_flight_jobs": {
                    "count": self.in_flight,
                    "max": self.max_concurrency,
                },
            },
        }


# Expose as FastAPI endpoint for k8s probes
@router.get("/health/worker")
async def worker_health() -> dict:
    health = get_worker_health()  # inject or resolve from app state
    return health.to_dict()
```

## Producing Jobs

```python
# app/services/job_producer.py

import uuid
from datetime import datetime, timezone


def enqueue_email(
    tenant_id: str,
    to: str,
    subject: str,
    template_id: str,
    variables: dict,
) -> str:
    """Enqueue an email sending job. Returns the job ID."""
    job_id = str(uuid.uuid4())

    send_email.apply_async(
        kwargs={
            "job_id": job_id,
            "tenant_id": tenant_id,
            "to": to,
            "subject": subject,
            "template_id": template_id,
            "variables": variables,
        },
        task_id=job_id,
        queue="email",
    )

    return job_id
```

## Critical Rules

- Use `task_acks_late = True` in Celery — acknowledge AFTER processing, not before
- Use `worker_prefetch_multiplier = 1` — fetch one task at a time per worker process
- Use `task_reject_on_worker_lost = True` — re-queue if the worker crashes mid-task
- Set both `task_time_limit` (hard) and `task_soft_time_limit` (soft) — prevent hung tasks
- Use `retry_backoff = True` with `retry_jitter = True` for exponential backoff with jitter
- Every task MUST accept keyword arguments only — positional args break serialization on schema change
- Every task MUST log `job_id`, `tenant_id`, `task_id`, and `attempt` — use `structlog.bind()`
- Idempotency check MUST happen inside the task, not at enqueue time
- Use `bind=True` on Celery tasks to access `self.request` for retry metadata
- Signal handlers in asyncio workers use `loop.add_signal_handler` — never `signal.signal` in async code
