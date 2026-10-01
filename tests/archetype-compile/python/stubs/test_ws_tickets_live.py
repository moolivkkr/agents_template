"""harness-only (--live): websocket-pattern-python.md's ticket stores on a real Redis — FastAPI's
RedisTicketStore and the Channels myapp/tickets.py: a ticket redeems once, even when redemptions race,
carries the ~30 s TTL and expires; the Channels application admits a real ticket once."""
import asyncio
from collections.abc import AsyncIterator, Iterator

import django
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.community.redis import RedisContainer

from app.ws.tickets import TICKET_TTL_SECONDS, RedisTicketStore, TicketClaims

django.setup()  # DJANGO_SETTINGS_MODULE=harness_django_settings
from channels.testing import WebsocketCommunicator  # noqa: E402
from django.test import override_settings  # noqa: E402

import myapp.tickets as django_tickets  # noqa: E402
from myapp.asgi import application  # noqa: E402


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"


@pytest_asyncio.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url)
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_ticket_is_single_use_with_ttl(redis: Redis) -> None:
    store = RedisTicketStore(redis)
    claims = TicketClaims(user_id="u1", tenant_id="t1", roles=("user",))
    ticket = await store.issue(claims)
    assert 0 < await redis.ttl(f"ws-ticket:{ticket}") <= TICKET_TTL_SECONDS
    assert await store.redeem(ticket) == claims
    assert await store.redeem(ticket) is None
    assert await store.redeem("never-issued") is None


@pytest.mark.asyncio
async def test_racing_redemptions_get_one_winner(redis: Redis) -> None:
    store = RedisTicketStore(redis)
    ticket = await store.issue(TicketClaims(user_id="u1", tenant_id="t1", roles=()))
    results = await asyncio.gather(*(store.redeem(ticket) for _ in range(20)))
    assert sum(r is not None for r in results) == 1


ALLOWED = [(b"origin", b"http://localhost:3000")]


@pytest.mark.asyncio
async def test_channels_tickets_on_redis(redis_url: str, redis: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    with override_settings(REDIS_URL=redis_url):
        claims = django_tickets.TicketClaims(user_id="u1", tenant_id="t1", roles=("user",))
        ticket = await django_tickets.issue_ticket(claims)
        assert 0 < await redis.ttl(f"ws-ticket:{ticket}") <= django_tickets.TICKET_TTL_SECONDS

        # through the Channels application: the real ticket gets in once, then it's gone from Redis
        comm = WebsocketCommunicator(application, f"/ws/notifications/?ticket={ticket}", headers=ALLOWED)
        connected, _ = await comm.connect()
        assert connected
        await comm.send_json_to({"type": "subscribe", "id": "1", "payload": {"room": "tenant:t1"}})
        assert await comm.receive_json_from() == {"type": "ack", "ref": "1"}
        await comm.disconnect()
        assert await redis.exists(f"ws-ticket:{ticket}") == 0
        reused = WebsocketCommunicator(application, f"/ws/notifications/?ticket={ticket}", headers=ALLOWED)
        await reused.connect()
        assert (await reused.receive_output())["code"] == 4001

        raced = await django_tickets.issue_ticket(claims)
        results = await asyncio.gather(*(django_tickets.redeem_ticket(raced) for _ in range(20)))
        assert [r for r in results if r is not None] == [claims]  # one winner, with the claims intact

        monkeypatch.setattr(django_tickets, "TICKET_TTL_SECONDS", 1)
        expiring = await django_tickets.issue_ticket(claims)
        await asyncio.sleep(1.2)
        assert await django_tickets.redeem_ticket(expiring) is None  # expired in Redis
