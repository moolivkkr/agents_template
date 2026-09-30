"""harness-only stand-in for app/db.py (observability-python.md's lifespan calls create_engine()).
The URL comes from the environment; create_async_engine doesn't connect until first use."""
import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine() -> AsyncEngine:
    return create_async_engine(os.environ["DATABASE_URL"])
