"""harness (--live): databases/redis.md's fragments against a real Redis 7."""
from __future__ import annotations

import importlib
import json

import pytest
import redis

from app.cache_aside import get_or_load
from app.sessions import store_session
from harness_stubs.redis_app import Db, User


@pytest.fixture
def client(redis_url: str):
    c = redis.Redis.from_url(redis_url, decode_responses=True)
    c.flushdb()
    yield c
    c.close()


def test_cache_aside_reads_the_database_once(client: redis.Redis) -> None:
    db = Db()
    first = get_or_load(client, db, "widget:w1", 60)
    second = get_or_load(client, db, "widget:w1", 60)
    assert first == second == {"id": "w1", "name": "from the database"}
    assert db.reads == 1
    assert 0 < client.ttl("widget:w1") <= 60


def test_session_is_stored_with_a_ttl(client: redis.Redis) -> None:
    user = User(role="admin")
    store_session(client, "tok123", user)
    assert json.loads(client.get("session:tok123")) == {"user_id": str(user.id), "role": "admin"}
    assert 0 < client.ttl("session:tok123") <= 1800


def test_pooled_client_connects(redis_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", redis_url)
    import app.pool

    pool_mod = importlib.reload(app.pool)
    assert pool_mod.client.ping() is True
    assert pool_mod.pool.max_connections == 20
    pool_mod.pool.disconnect()
