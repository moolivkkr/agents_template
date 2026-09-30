"""harness-only stand-ins for app/services/email.py and app/services/idempotency.py, which
worker-pattern-python.md imports (in-memory, so the smoke can run a task twice)."""
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class SendResult:
    message_id: str


class EmailService:
    sent: ClassVar[list[str]] = []

    def render_template(self, template_id: str, variables: dict[str, Any]) -> str:
        return f"<p>{template_id}</p>"

    def send(self, *, to: str, subject: str, html: str) -> SendResult:
        EmailService.sent.append(to)
        return SendResult(message_id=f"msg-{len(EmailService.sent)}")


class IdempotencyStore:
    _done: ClassVar[set[str]] = set()

    def is_processed(self, job_id: str) -> bool:
        return job_id in IdempotencyStore._done

    def mark_processed(self, job_id: str, *, ttl_seconds: int) -> None:
        IdempotencyStore._done.add(job_id)
