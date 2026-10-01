"""harness (--live): throwaway containers for the pack samples that talk to a real service. Session-scoped,
started only by the tests that ask for them; the images the framework uses elsewhere."""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    """libpq URL (postgresql://user:pass@host:port/db) of a throwaway PostgreSQL 16."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url(driver=None)


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """redis://host:port/0 of a throwaway Redis 7."""
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as r:
        yield f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}/0"
