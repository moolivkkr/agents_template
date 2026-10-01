"""harness-only (--live): auth-middleware-python.md's RedisTenantRateLimiter in two uvicorn processes
sharing one Redis 7: a tenant gets `burst` requests in total, whichever process serves them, also when
they arrive concurrently (the Lua script is atomic), and another tenant has its own bucket. The same two
processes with the in-process TenantRateLimiter let the tenant through `burst` times EACH."""
import asyncio
import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import jwt
import pytest
from redis import Redis
from testcontainers.community.redis import RedisContainer

SECRET, ISSUER, AUDIENCE = "k" * 64, "harness-issuer", "harness-audience"
BURST = 4  # harness_ratelimit_app.py


@pytest.fixture(scope="module")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"


def token(tenant: uuid.UUID) -> str:
    claims = {"sub": str(uuid.uuid4()), "tenant_id": str(tenant), "iss": ISSUER, "aud": AUDIENCE,
              "exp": int(time.time()) + 300}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def two_processes(limiter: str, redis_url: str) -> Iterator[list[str]]:
    env = {**os.environ, "APP_ENV": "production", "JWT_SECRET_KEY": SECRET, "JWT_ISSUER": ISSUER,
           "JWT_AUDIENCE": AUDIENCE, "HARNESS_LIMITER": limiter, "REDIS_URL": redis_url}
    ports = [_free_port(), _free_port()]
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "harness_ratelimit_app:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            cwd=os.getcwd(), env=env,
        )
        for port in ports
    ]
    urls = [f"http://127.0.0.1:{port}" for port in ports]
    try:
        for url in urls:  # up when an unauthenticated request gets its 401
            deadline = time.monotonic() + 30
            while True:
                try:
                    if httpx.get(f"{url}/api/v1/widgets/{uuid.uuid4()}").status_code == 401:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline, f"{url} did not start"
                time.sleep(0.1)
        yield urls
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(10)


async def _get(client: httpx.AsyncClient, url: str, tenant: uuid.UUID) -> httpx.Response:
    return await client.get(f"{url}/api/v1/widgets/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token(tenant)}"})


def test_redis_bucket_is_shared_by_both_processes(redis_url: str) -> None:
    async def run(urls: list[str]) -> None:
        async with httpx.AsyncClient() as client:
            # sequential, alternating processes: 4 through in total, then 429 from either process
            tenant = uuid.uuid4()
            served = [(i % 2, (await _get(client, urls[i % 2], tenant))) for i in range(2 * BURST)]
            codes = [r.status_code for _, r in served]
            assert codes == [404] * BURST + [429] * BURST, codes
            assert {p for p, r in served if r.status_code == 429} == {0, 1}  # both processes refuse
            limited = served[-1][1]
            assert int(limited.headers["retry-after"]) >= 1 and limited.json()["error"]["code"] == "RATE_LIMITED"

            other = await _get(client, urls[1], uuid.uuid4())  # another tenant: its own bucket
            assert other.status_code == 404, other.text

            # concurrent: 20 requests at once across both processes; the script is atomic
            burst_tenant = uuid.uuid4()
            results = await asyncio.gather(*(_get(client, urls[i % 2], burst_tenant) for i in range(20)))
            concurrent = sorted(r.status_code for r in results)
            assert concurrent == [404] * BURST + [429] * (20 - BURST), concurrent
            print(f"redis limiter, 2 processes: sequential {codes}; 20 concurrent -> "
                  f"{concurrent.count(404)} through, {concurrent.count(429)} limited")

        ttl = Redis.from_url(redis_url).pttl(f"ratelimit:{tenant}")
        assert isinstance(ttl, int) and ttl > 0, ttl  # idle buckets expire

    with two_processes("redis", redis_url) as urls:
        asyncio.run(run(urls))


def test_in_process_buckets_multiply_the_limit(redis_url: str) -> None:
    async def run(urls: list[str]) -> list[int]:
        async with httpx.AsyncClient() as client:
            tenant = uuid.uuid4()
            return [(await _get(client, urls[i % 2], tenant)).status_code for i in range(2 * BURST + 2)]

    with two_processes("memory", redis_url) as urls:
        codes = asyncio.run(run(urls))
    # each process has its own bucket of 4: the tenant gets 8 through two processes
    assert codes == [404] * (2 * BURST) + [429, 429], codes
    print(f"in-process limiter, 2 processes: {codes}")
