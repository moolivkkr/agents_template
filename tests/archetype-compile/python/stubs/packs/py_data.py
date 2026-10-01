"""harness: the app-level names languages/python.md's data blocks leave to the reader — settings, the
declarative Base and models, the order repository and request, and the opaque cursor helpers."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _Settings:
    @property
    def DATABASE_URL(self) -> str:  # noqa: N802 — the doc's name
        return os.environ["DATABASE_URL"]


settings = _Settings()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class Note(Base):
    """A tenant-owned model with BaseRepository's columns (TenantModel)."""

    __tablename__ = "notes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    body: Mapped[str] = mapped_column(String(100), default="")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    sku: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer)

    @property
    def items(self) -> list[tuple[str, int]]:
        return [(self.sku, self.quantity)]


class Stock(Base):
    __tablename__ = "stock"
    sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    on_hand: Mapped[int] = mapped_column(Integer)


class CreateOrderRequest(BaseModel):
    sku: str
    quantity: int


class InsufficientStock(Exception):
    pass


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: Order) -> Order:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update_inventory(self, tenant_id: UUID, items: list[tuple[str, int]]) -> None:
        for sku, qty in items:
            stock = await self._session.get(Stock, sku)
            if stock is None or stock.on_hand < qty:
                raise InsufficientStock(sku)
            stock.on_hand -= qty
        await self._session.flush()


def encode_cursor(created_at: datetime, last_id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([created_at.isoformat(), str(last_id)]).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    at, last = json.loads(base64.urlsafe_b64decode(cursor))
    return datetime.fromisoformat(at), UUID(last)
