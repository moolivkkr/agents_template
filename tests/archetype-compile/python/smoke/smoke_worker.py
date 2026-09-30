# harness smoke: run worker-pattern-python.md's tasks and workers without a broker
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.email import EmailService
from app.tasks import email_dramatiq
from app.tasks.email import send_email
from app.worker.async_worker import AsyncWorker, Job
from app.worker.health import router as health_router
from app.worker.scheduler import create_scheduler

# Celery: run the bound task in-process (apply) — idempotent by job_id
job = dict(job_id="job-1", tenant_id="t1", to="a@example.com", subject="Hi", template_id="welcome", variables={})
first = send_email.apply(kwargs=job)
assert first.successful(), first.traceback
assert first.get() == {"status": "sent", "message_id": "msg-1"}, first.get()
again = send_email.apply(kwargs=job)
assert again.get() == {"status": "duplicate", "job_id": "job-1"}, again.get()
assert EmailService.sent == ["a@example.com"], EmailService.sent

# dramatiq: each middleware once (the broker's defaults include Retries and TimeLimit), then call the
# actor's function directly (no broker round trip)
kinds = [type(m).__name__ for m in email_dramatiq.broker.middleware]
assert all(kinds.count(k) == 1 for k in kinds) and "CurrentMessage" in kinds and "Retries" in kinds, kinds
email_dramatiq.send_email.fn(job_id="job-2", tenant_id="t1", to="b@example.com", subject="Hi",
                             template_id="welcome", variables={})
assert EmailService.sent[-1] == "b@example.com"


# asyncio worker: a job is consumed, a failing one is retried up to max_retries
async def run_worker() -> list[str]:
    worker = AsyncWorker(concurrency=1, job_timeout=1.0)
    seen: list[str] = []

    async def ok(j: Job) -> None:
        seen.append(j.id)

    async def flaky(j: Job) -> None:
        seen.append(f"{j.id}#{j.attempt}")
        raise ConnectionError("down")

    worker.register("ok", ok)
    worker.register("flaky", flaky)
    await worker.enqueue(Job(id="1", type="ok", payload={}, tenant_id="t1"))
    await worker.enqueue(Job(id="2", type="flaky", payload={}, tenant_id="t1", max_retries=2))
    consumer = asyncio.create_task(worker._consume("c0"))
    await asyncio.sleep(0.3)
    worker._shutdown_event.set()
    await asyncio.wait_for(consumer, timeout=3)
    return seen


assert asyncio.run(run_worker()) == ["1", "2#1", "2#2"]


# APScheduler: both cron jobs registered
class Locks:
    async def try_acquire(self, key: str, ttl_seconds: int) -> bool:
        return True

    async def release(self, key: str) -> None: ...


scheduler = create_scheduler(Locks())
assert {j.id for j in scheduler.get_jobs()} == {"cleanup_expired_sessions", "generate_daily_report"}

# health endpoint
app = FastAPI()
app.include_router(health_router)
r = TestClient(app).get("/health/worker")
assert r.status_code == 200 and r.json()["status"] == "healthy", r.text
