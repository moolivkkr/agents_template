"""harness-only stand-in for myapp/tickets.py (websocket-pattern-python.md's Channels consumer imports
redeem_ticket; a real project redeems from Redis like app/ws/tickets.py's RedisTicketStore)."""
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Claims:
    user_id: str
    tenant_id: str


_tickets: dict[str, Claims] = {}


def issue_for_test(user_id: str, tenant_id: str) -> str:
    ticket = secrets.token_urlsafe(16)
    _tickets[ticket] = Claims(user_id=user_id, tenant_id=tenant_id)
    return ticket


async def redeem_ticket(ticket: str) -> Claims | None:
    return _tickets.pop(ticket, None)  # single use
