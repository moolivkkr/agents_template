"""harness: the app-level names languages/python.md's general fragments leave to the reader (a database
handle and its errors, a user, an email validator, an image resizer, the fetchers a TaskGroup runs, the
resources a lifespan opens)."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import structlog

log = structlog.get_logger()


class DBConnectionError(Exception):
    pass


class RepositoryError(Exception):
    pass


@dataclass
class User:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    email: str = "someone@example.com"


user = User()


class UserNotFoundError(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id} not found")


class _Db:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.down = False

    def get(self, id: str) -> User | None:
        return self.users.get(id)

    async def get_user(self, user_id: str) -> User | None:
        if self.down:
            raise DBConnectionError("connection refused")
        return self.users.get(user_id)


db = _Db()


def validate_email(value: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", value) is not None


@dataclass
class Result:
    path: Path
    size: int


def resize_image(path: Path) -> Result:  # module level: picklable for multiprocessing.Pool
    return Result(path=path, size=len(path.name))


@dataclass
class UserProfile:
    profile: dict[str, str]
    orders: list[str]
    preferences: dict[str, bool]


async def fetch_profile(user_id: str) -> dict[str, str]:
    await asyncio.sleep(0.01)
    return {"id": user_id}


async def fetch_orders(user_id: str) -> list[str]:
    await asyncio.sleep(0.01)
    if user_id == "broken":
        raise RuntimeError("orders service down")
    return ["o1", "o2"]


async def fetch_preferences(user_id: str) -> dict[str, bool]:
    await asyncio.sleep(0.05)
    return {"dark": True}


class _Pool:
    closed = False

    async def close(self) -> None:
        self.closed = True


async def create_db_pool() -> _Pool:
    return _Pool()


def create_redis():  # the real client: lazy, connects on first command (none here)
    import redis.asyncio

    return redis.asyncio.Redis.from_url("redis://127.0.0.1:1/0")
