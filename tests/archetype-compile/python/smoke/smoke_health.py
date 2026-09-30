# harness smoke: dockerfile-python.md's /healthz, /readyz and /api/version without a database.
# (--live adds tests/test_health_live.py: the schema-revision check against a real PostgreSQL.)
import os
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.api.health as health

app = FastAPI()
app.include_router(health.router)
os.environ["GIT_SHA"] = "0123abc"
os.environ["APP_ENV"] = "qa"

with TestClient(app) as c:
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "alive"}, r.text
    assert r.headers["cache-control"] == "no-store"

    r = c.get("/readyz")
    assert r.status_code == 503 and r.json() == {"status": "starting"}, r.text  # no DB configured yet

    # a database that refuses connections: 503 quickly, and the body names no host or user
    health.configure_health(async_sessionmaker(create_async_engine("postgresql+asyncpg://app@127.0.0.1:1/app")))
    t0 = time.monotonic()
    r = c.get("/readyz")
    assert r.status_code == 503 and r.json() == {"status": "database_unavailable"}, r.text
    assert time.monotonic() - t0 < 2, "readiness must answer within its own short timeout"
    assert "127.0.0.1" not in r.text and "app@" not in r.text

    assert c.get("/healthz").status_code == 200  # liveness doesn't care about the database

    r = c.get("/api/version")
    assert r.json() == {"git_sha": "0123abc", "env": "qa"}, r.text

    health.start_draining()
    assert c.get("/readyz").json() == {"status": "draining"}

# schema-revision rule, against the migration-pattern-python.md revisions in this build
assert health._REQUIRED_REVISION == "d4e5f6a7b8c9", health._REQUIRED_REVISION
assert health._schema_ready("d4e5f6a7b8c9") is True     # at this release's newest migration
assert health._schema_ready("a1b2c3d4e5f6") is False    # older: this release's migration hasn't run
assert health._schema_ready("ffffffffffff") is True     # unknown here: a newer release migrated first
assert health._schema_ready(None) is False              # never migrated
