"""harness: the tenant-scoped model infrastructure/saas-tenancy-models.md's repository method queries."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(100))
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
