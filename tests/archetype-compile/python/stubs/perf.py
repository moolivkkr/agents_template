"""harness-only: app-level names performance-python.md fragments assume (a repository, a request
context, dashboard loaders, ...). The repository's find_by_id returns `Order | None`, the contract the
same doc's OrderRepository (§3.4) declares."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from harness_stubs.orders import Order, OrderModel, ProductModel, UpdateReq  # noqa: F401 (re-exported)


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str = ""
    request_id: str = ""


@dataclass
class TenantConfig:
    tenant_id: str
    flags: dict[str, bool]


@dataclass
class DashboardData:
    stats: dict[str, int] | None
    alerts: list[str] | None
    recent: list[Order] | None


@dataclass
class Item:
    id: str


@dataclass
class Result:
    id: str


@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: str
    quantity: int
    unit_price: Decimal


class OrderRepo:
    async def save(self, order: Order) -> None: ...

    async def find_by_id(self, ctx: RequestContext, order_id: str) -> Order | None:
        return None

    async def update(self, ctx: RequestContext, order_id: str, req: UpdateReq) -> Order:
        return Order(id=order_id)

    async def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        return TenantConfig(tenant_id=tenant_id, flags={})

    async def iter_orders(self, tenant_id: str, batch_size: int = 1000) -> AsyncIterator[list[Order]]:
        yield [Order(tenant_id=tenant_id)]


class _Indexer:
    async def index(self, order: Order) -> None: ...


class _Analytics:
    async def track(self, event: str, entity_id: str) -> None: ...


repo = OrderRepo()
search_index = _Indexer()
analytics = _Analytics()
session: AsyncSession  # the fragment's module-level session


async def fetch_stats(tenant_id: str) -> dict[str, int]:
    return {}


async def fetch_alerts(tenant_id: str) -> list[str]:
    return []


async def fetch_recent_orders(tenant_id: str) -> list[Order]:
    return []


async def process_item(item: Item) -> Result:
    return Result(id=item.id)


def calculate_discount(items: list[OrderLine]) -> Decimal:
    return Decimal("0")


def create_order_sync(data: Any) -> Order:
    return Order()


def cpu_task() -> int:
    return 0


def fetch_month_data(tenant_id: str, month: str) -> list[dict[str, Any]]:
    return []


def build_pdf(data: list[dict[str, Any]]) -> bytes:
    return b"%PDF"


UPLOADS: dict[str, bytes] = {}     # object key -> body (what the smoke inspects)
NOTIFIED: dict[str, str] = {}      # idempotency key -> tenant (provider-side dedup)
FAIL_UPLOADS: list[BaseException] = []


def upload_to_s3(key: str, pdf: bytes) -> None:
    if FAIL_UPLOADS:
        raise FAIL_UPLOADS.pop(0)
    UPLOADS[key] = pdf


def send_notification(tenant_id: str, *, idempotency_key: str) -> None:
    NOTIFIED.setdefault(idempotency_key, tenant_id)


class IdempotencyRecord:
    """The job's own record of side effects already done (a table or Redis set in an app)."""

    def __init__(self) -> None:
        self._done: set[str] = set()

    def is_done(self, key: str) -> bool:
        return key in self._done

    def mark_done(self, key: str) -> None:
        self._done.add(key)


idempotency = IdempotencyRecord()


async def main() -> None:
    """The app's entry coroutine (the fragments start the loop with it)."""
