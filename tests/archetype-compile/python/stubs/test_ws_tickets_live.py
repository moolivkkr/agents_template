"""harness-only (--live): websocket-pattern-python.md's RedisTicketStore on a real Redis — a ticket
redeems once, even when two redemptions race, and carries the ~30 s TTL."""
import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.community.redis import RedisContainer

from app.ws.tickets import TICKET_TTL_SECONDS, RedisTicketStore, TicketClaims


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
