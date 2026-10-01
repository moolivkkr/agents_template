"""harness: the app-level names frameworks/fastapi.md's fragments leave to the reader — the database
handle the lifespan opens, the auth router and dependency, the user service/repository, the session
factory and the domain error."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Header
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.errors import UnauthenticatedError


@dataclass
class _Db:
    events: list[str] = field(default_factory=list)

    async def connect(self) -> None:
        self.events.append("connect")

    async def disconnect(self) -> None:
        self.events.append("disconnect")


db = _Db()


class _AuthModule:
    router = APIRouter(tags=["auth"])


auth = _AuthModule()

# Lazy engine: nothing connects unless a query runs (the stub repository never queries).
SessionLocal = async_sessionmaker(create_async_engine("postgresql+asyncpg://harness@127.0.0.1:1/harness"))

TENANT_A, TENANT_B = UUID(int=1), UUID(int=2)


@dataclass
class User:
    id: UUID
    tenant_id: UUID
    email: str
    created_at: datetime


_TOKENS = {"tok-a": User(uuid4(), TENANT_A, "a@example.com", datetime.now(timezone.utc))}


async def require_auth(authorization: str | None = Header(None)) -> User:
    user = _TOKENS.get((authorization or "").removeprefix("Bearer "))
    if user is None:
        raise UnauthenticatedError()
    return user


class UserNotFoundError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"user {user_id} not found")  # internal text: must never reach the client


USERS: dict[UUID, User] = {}


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, tenant_id: UUID, user_id: UUID) -> User | None:
        u = USERS.get(user_id)
        return u if u is not None and u.tenant_id == tenant_id else None


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def get(self, *, tenant_id: UUID, user_id: UUID) -> User:
        user = await self._repo.get(tenant_id, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
