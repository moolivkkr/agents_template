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

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): imported and type-checked; the Celery task applied in-process (transient failure retried, one email per idempotency key, permanent failure not retried), the dramatiq actor function called, the asyncio worker's idempotent-only backoff retries and APScheduler jobs exercised. No broker was used. celery 5.6.3, dramatiq 2.2.1, APScheduler 3.11.3.

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

import structlog
from celery import Task

from app.services.email import EmailService
from app.services.idempotency import IdempotencyStore
from app.worker.celery_app import app

# structlog, not celery's get_task_logger(): that is a stdlib Logger, with no .bind() and no
# keyword fields
logger = structlog.get_logger(__name__)


class BaseTask(Task):
    """Base task with structured logging and error handling."""

    # Retry transient failures only. A bad template or a rejected address fails once: retrying repeats it.
    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True           # Exponential backoff
    retry_backoff_max = 300        # Max 5 minutes between retries
    retry_jitter = True            # Add jitter to prevent thundering herd
    max_retries = 5

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task.failed",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            attempt=self.request.retries + 1,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "task.retrying",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            attempt=self.request.retries + 1,
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "task.completed",
            task_id=task_id,
            task_name=self.name,
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

    # A ConnectionError/TimeoutError propagates and BaseTask retries it with backoff and jitter; any
    # other error fails the task once (on_failure logs it). No catch-all self.retry().
    svc = EmailService()
    html = svc.render_template(template_id, variables)
    # Sending is not idempotent by itself: the provider deduplicates on idempotency_key, so a retry
    # after a timeout that did deliver doesn't send a second email.
    result = svc.send(to=to, subject=subject, html=html, idempotency_key=job_id)

    idem.mark_processed(job_id, ttl_seconds=86400)

    log.info("email.sent", provider_id=result.message_id)
    return {"status": "sent", "message_id": result.message_id}
```

## Dramatiq Alternative

```python
# app/tasks/email_dramatiq.py

import dramatiq
import structlog
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

from app.services.email import EmailService
from app.services.idempotency import IdempotencyStore

logger = structlog.get_logger(__name__)

# Configure broker. Retries and TimeLimit are already in the broker's default middleware (the actor
# options below tune them); adding them again would run each twice. CurrentMessage isn't a default.
broker = RedisBroker(url="redis://localhost:6379/0")
broker.add_middleware(CurrentMessage())
dramatiq.set_broker(broker)


def retry_transient(retries: int, exc: BaseException) -> bool:
    """Retry a dependency hiccup, up to 5 times; a bug or bad input fails once."""
    return isinstance(exc, (ConnectionError, TimeoutError)) and retries < 5


@dramatiq.actor(
    queue_name="email",
    retry_when=retry_transient,  # replaces max_retries; the backoff is exponential with jitter
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
    svc.send(to=to, subject=subject, html=html, idempotency_key=job_id)  # the provider deduplicates

    idem.mark_processed(job_id, ttl_seconds=86400)
    logger.info("email.sent", job_id=job_id, to=to)
```

## Asyncio Queue Worker (No External Broker)

```python
# app/worker/async_worker.py

import asyncio
import random
import signal
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Worth another try: a dependency hiccup, or the job's own timeout. Anything else is a bug or bad input.
TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)


@dataclass
class Job:
    id: str
    type: str
    payload: dict[str, Any]
    tenant_id: str
    attempt: int = 1
    max_retries: int = 5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Handler = Callable[[Job], Coroutine[Any, Any, None]]


class AsyncWorker:
    """In-process async worker using asyncio.Queue. For single-process apps: queued jobs and pending
    retries live in memory and are lost on restart; use Celery or dramatiq when they must survive."""

    def __init__(
        self,
        concurrency: int = 5,
        job_timeout: float = 300.0,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 60.0,
    ):
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=1000)
        self._handlers: dict[str, tuple[Handler, bool]] = {}
        self._concurrency = concurrency
        self._job_timeout = job_timeout
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._pending_retries: set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()
        self._in_flight = 0

    def register(self, job_type: str, handler: Handler, *, idempotent: bool) -> None:
        """idempotent=True only when running the handler twice for the same job has the effect of
        running it once: it upserts, or checks job.id in an idempotency store before its side effect.
        Only idempotent jobs are retried."""
        self._handlers[job_type] = (handler, idempotent)

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

        pending = [*tasks, *self._pending_retries]  # scheduled retries are dropped (in-memory queue)
        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)
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

        entry = self._handlers.get(job.type)
        if entry is None:
            log.error("job.unknown_type")
            return
        handler, idempotent = entry

        try:
            await asyncio.wait_for(handler(job), timeout=self._job_timeout)
            log.info("job.completed")
        except TRANSIENT_ERRORS as exc:
            if idempotent and job.attempt < job.max_retries:
                delay = self._backoff(job.attempt)
                log.warning("job.retrying", error=type(exc).__name__, delay_s=round(delay, 3))
                job.attempt += 1
                self._schedule_retry(job, delay)
            else:
                log.error("job.failed", error=type(exc).__name__, retryable=idempotent)
        except Exception as exc:  # a bug or bad input: retrying would repeat it
            log.error("job.failed", error=str(exc))

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter: uniform(0, min(max, base * 2^(attempt - 1)))."""
        return random.uniform(0, min(self._retry_max_delay, self._retry_base_delay * 2 ** (attempt - 1)))

    def _schedule_retry(self, job: Job, delay: float) -> None:
        """Re-enqueue after the delay without holding a consumer."""

        async def later() -> None:
            await asyncio.sleep(delay)
            await self.enqueue(job)

        task = asyncio.create_task(later())
        self._pending_retries.add(task)
        task.add_done_callback(self._pending_retries.discard)
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

from app.tasks.email import send_email


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
- Retry only transient errors (`ConnectionError`, `TimeoutError`) and only idempotent work: a job is safe to retry when running it twice has the effect of running it once. A non-idempotent side effect (an email, a charge) goes out with an idempotency key the provider deduplicates on, and the job's own idempotency record skips it on a re-run. Never a catch-all `self.retry()`
- Every task MUST accept keyword arguments only — positional args break serialization on schema change
- Every task MUST log `job_id`, `tenant_id`, `task_id`, and `attempt` — use `structlog.bind()`
- Idempotency check MUST happen inside the task, not at enqueue time
- Use `bind=True` on Celery tasks to access `self.request` for retry metadata
- Signal handlers in asyncio workers use `loop.add_signal_handler` — never `signal.signal` in async code
