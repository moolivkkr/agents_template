"""harness-only stand-ins for app/services/email.py and app/services/idempotency.py, which
worker-pattern-python.md imports (in-memory). The email "provider" deduplicates on idempotency_key the
way real providers do, and can be told to fail the next calls."""
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class SendResult:
    message_id: str


class EmailService:
    sent: ClassVar[list[str]] = []                  # every recipient actually delivered to
    by_key: ClassVar[dict[str, SendResult]] = {}   # provider-side dedup
    fail_next: ClassVar[list[BaseException]] = []  # raised (in order) by the next send() calls

    def render_template(self, template_id: str, variables: dict[str, Any]) -> str:
        return f"<p>{template_id}</p>"

    def send(self, *, to: str, subject: str, html: str, idempotency_key: str) -> SendResult:
        if EmailService.fail_next:
            raise EmailService.fail_next.pop(0)
        if idempotency_key in EmailService.by_key:
            return EmailService.by_key[idempotency_key]
        EmailService.sent.append(to)
        result = SendResult(message_id=f"msg-{len(EmailService.sent)}")
        EmailService.by_key[idempotency_key] = result
        return result


class IdempotencyStore:
    _done: ClassVar[set[str]] = set()

    def is_processed(self, job_id: str) -> bool:
        return job_id in IdempotencyStore._done

    def mark_processed(self, job_id: str, *, ttl_seconds: int) -> None:
        IdempotencyStore._done.add(job_id)
