"""harness: the app-level names core/testing-principles.md's tests leave to the reader (an order with a
discount rule, a user record)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Item:
    price: int


@dataclass(frozen=True)
class Discount:
    code: str
    percent: int


@dataclass(frozen=True)
class Order:
    items: list[Item]
    subtotal: int
    total: int = -1
    discount_applied: str | None = None

    def __post_init__(self) -> None:
        if self.total < 0:
            object.__setattr__(self, "total", self.subtotal)

    def apply_discount(self, discount: Discount) -> Order:
        return replace(self, total=self.subtotal * (100 - discount.percent) // 100, discount_applied=discount.code)


@dataclass
class User:
    email: str
    role: str
    active: bool
    permissions: list[str] = field(default_factory=list)
