"""harness-only: the order domain that observability-python.md and performance-python.md fragments
assume (Order, OrderModel, CreateOrderRequest, a repository, ...). Plain app-level types built on the
real libraries (SQLAlchemy mapped classes, pydantic models); nothing here stands in for a library."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CustomerModel(Base):
    __tablename__ = "customers"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class OrderItemModel(Base):
    __tablename__ = "order_items"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    sku: Mapped[str] = mapped_column(String(64))


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[OrderItemModel]] = relationship()
    customer: Mapped[CustomerModel] = relationship()


class ProductModel(Base):
    __tablename__ = "products"
    sku: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderLineItem(BaseModel):
    sku: str
    qty: int = 1


class CreateOrderRequest(BaseModel):
    items: list[OrderLineItem] = Field(default_factory=list)
    total: Decimal = Decimal("0")

    def validate_business_rules(self) -> None: ...


class UpdateReq(BaseModel):
    status: str


class Order(BaseModel):
    id: str = Field(default_factory=lambda: f"ord_{uuid4().hex}")
    tenant_id: str = ""
    total: Decimal = Decimal("0")
    status: str = "active"
    payment_method: str = "card"
    items: list[OrderLineItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_request(cls, req: CreateOrderRequest, *, tenant_id: str = "") -> Order:
        return cls(tenant_id=tenant_id, total=req.total, items=req.items)

    @classmethod
    def from_model(cls, model: OrderModel) -> Order:
        return cls(id=model.id, tenant_id=model.tenant_id, total=model.total, status=model.status,
                   created_at=model.created_at)

    @classmethod
    def from_record(cls, record: Any) -> Order:
        return cls(id=record["id"], tenant_id=record["tenant_id"])

    def to_model(self) -> OrderModel:
        return OrderModel(id=self.id, tenant_id=self.tenant_id, total=self.total, status=self.status,
                          created_at=self.created_at)


@dataclass
class Charge:
    id: str


class PaymentClient:
    async def charge(self, ctx: Any, order: Order) -> Charge:
        return Charge(id="ch_1")


@dataclass
class CircuitBreaker:
    failure_count: int = 0
    reset_timeout: float = 30.0
