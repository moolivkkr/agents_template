"""harness: the app-level names languages/python.md's FastAPI blocks leave to the reader — the verified-JWT
dependency (a stand-in for auth-middleware-python.md's), the routers, the order and user services with
their response models, the session factory, cache and event publisher."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from app.tenancy import TokenClaims

orders_router = APIRouter()
users_router = APIRouter()

# token -> claims a verifier would have produced (signature, expiry and audience already checked)
TENANT_A, TENANT_B, TENANT_C = UUID(int=0xA), UUID(int=0xB), UUID(int=0xC)
TOKENS: dict[str, dict[str, Any]] = {
    "tok-a": {"sub": "u-a", "tenant_id": str(TENANT_A)},
    "tok-multi": {"sub": "u-m", "tenant_id": str(TENANT_A), "tenant_ids": [str(TENANT_B)]},
}


def claims_for(request: Request) -> TokenClaims | None:
    from app.tenancy import TokenClaims

    raw = TOKENS.get(request.headers.get("authorization", "").removeprefix("Bearer "))
    return TokenClaims(**raw) if raw else None


async def get_verified_claims(request: Request) -> TokenClaims:
    from app.errors import UnauthenticatedError

    claims = claims_for(request)
    if claims is None:
        raise UnauthenticatedError()
    return claims


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    total_cents: int


@dataclass
class OrderRow:
    id: UUID
    tenant_id: UUID
    total_cents: int
    created_at: datetime


ORDERS: list[OrderRow] = []


class OrderService:
    async def list_orders(self, tenant_id: UUID, *, cursor: str | None, limit: int) -> tuple[list[OrderRow], str | None]:
        rows = sorted((o for o in ORDERS if o.tenant_id == tenant_id), key=lambda o: (o.created_at, o.id), reverse=True)
        if cursor:
            at, oid = json.loads(base64.urlsafe_b64decode(cursor))
            rows = [o for o in rows if (o.created_at.isoformat(), str(o.id)) < (at, oid)]
        page, more = rows[:limit], len(rows) > limit
        nxt = base64.urlsafe_b64encode(json.dumps([page[-1].created_at.isoformat(), str(page[-1].id)]).encode()).decode()
        return page, (nxt if more else None)


def get_order_service() -> OrderService:
    return OrderService()


# ── users ──
class CreateUserRequest(BaseModel):
    email: str
    name: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


# Lazy engine: nothing connects (the session isn't used for queries here).
async_session_factory = async_sessionmaker(create_async_engine("postgresql+asyncpg://harness@127.0.0.1:1/x"))


class UserRepository:
    def __init__(self, session: Any) -> None:
        self.session = session


@dataclass
class CacheService:
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventPublisher:
    events: list[tuple[str, Any]] = field(default_factory=list)


_cache, _events = CacheService(), EventPublisher()


def get_cache() -> CacheService:
    return _cache


def get_event_publisher() -> EventPublisher:
    return _events


@dataclass
class CreatedUser:
    id: UUID
    email: str
    tenant_id: UUID


class UserService:
    def __init__(self, repo: UserRepository, cache: CacheService, events: EventPublisher) -> None:
        self._events = events

    async def create_user(self, tenant_id: UUID, request: CreateUserRequest) -> CreatedUser:
        user = CreatedUser(id=uuid4(), email=request.email, tenant_id=tenant_id)
        self._events.events.append(("user.created", user))
        return user


def now() -> datetime:
    return datetime.now(timezone.utc)
