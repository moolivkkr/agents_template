# harness smoke: run the performance-python.md helpers whose behaviour the prose promises
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.cache.single_flight import SingleFlight
from harness_stubs.orders import Order
from perf.event_loop import hash_password
from perf.intermediate_lists import get_active_order_ids, get_top_active_ids

calls = 0


async def slow() -> int:
    global calls
    calls += 1
    await asyncio.sleep(0.05)
    return 42


async def main() -> None:
    sf = SingleFlight()
    results = await asyncio.gather(*(sf.do("order:1", slow) for _ in range(20)))
    assert results == [42] * 20 and calls == 1, (results, calls)  # one call for 20 concurrent callers

    digest = await hash_password("pw")
    assert isinstance(digest, str) and len(digest) == 64, digest


asyncio.run(main())

t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
orders = [
    Order(id="b", status="active", total=Decimal("5"), created_at=t0 + timedelta(seconds=2)),
    Order(id="a", status="active", total=Decimal("9"), created_at=t0 + timedelta(seconds=1)),
    Order(id="c", status="cancelled", total=Decimal("7"), created_at=t0),
]
assert get_active_order_ids(orders) == ["a", "b"], get_active_order_ids(orders)
assert get_top_active_ids(orders, limit=1) == ["a"]

# §5.4: to_cache() returns bytes and round-trips (pyright can't infer msgpack.packb's type)
from perf.serialization import Order as CachedOrder  # noqa: E402

packed = CachedOrder().to_cache()
assert isinstance(packed, bytes) and isinstance(CachedOrder.from_cache(packed), CachedOrder), packed

# §6.3: the Celery task is a real task object (celery-types gives pyright the same view)
from perf.celery_vs_processes import generate_monthly_report  # noqa: E402

assert callable(generate_monthly_report.delay)
