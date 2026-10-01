"""harness: the app-level names languages/python.md's test samples exercise — a user service that mails,
an order service with optimistic locking (one of several concurrent creates wins), and config loading."""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

TENANT_ID = UUID(int=7)


class ConflictError(Exception):
    pass


class Mailer:
    async def send(self, to: str, subject: str) -> None:
        raise NotImplementedError("tests use a mock")


class CreateUserRequest(BaseModel):
    email: str
    name: str


@dataclass
class User:
    id: UUID
    email: str


class UserService:
    def __init__(self, mailer: Mailer) -> None:
        self._mailer = mailer

    async def create_user(self, tenant_id: UUID, request: CreateUserRequest) -> User:
        user = User(id=uuid4(), email=request.email)
        await self._mailer.send(request.email, "Welcome")
        return user


def make_order_request() -> dict[str, Any]:
    return {"sku": "W-1", "quantity": 1}


class OrderService:
    """Spends from one balance with an optimistic version check: concurrent writers that read the same
    version conflict instead of double-spending."""

    def __init__(self) -> None:
        self.version = 0
        self.balance = 1

    async def create_order(self, tenant_id: UUID, request: dict[str, Any]) -> dict[str, Any]:
        seen = self.version
        await asyncio.sleep(0)  # let the other writers read the same version
        if self.version != seen or self.balance < request["quantity"]:
            raise ConflictError("changed by someone else")
        self.version += 1
        self.balance -= request["quantity"]
        return {"id": str(uuid4()), **request}


@dataclass
class Config:
    database_url: str


def load_config() -> Config:
    return Config(database_url=os.environ["DATABASE_URL"])
