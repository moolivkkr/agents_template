# harness smoke: run the performance-python.md helpers whose behaviour the prose promises
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.cache.single_flight import SingleFlight
from harness_stubs.orders import Order
from perf.event_loop import hash_password, needs_rehash, verify_password
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

    # §1.1: argon2id, a fresh salt per hash, verify true only for the right password
    h1, h2 = await hash_password("correct horse"), await hash_password("correct horse")
    assert h1.startswith("$argon2id$") and h1 != h2, (h1, h2)  # same password, different salts
    assert await verify_password(h1, "correct horse") and await verify_password(h2, "correct horse")
    assert not await verify_password(h1, "wrong horse")
    assert not await verify_password("not-a-hash", "correct horse")  # corrupt stored value: fails closed
    assert not needs_rehash(h1)


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

# §6.3: the Celery task is a real task object (celery-types gives pyright the same view), retries a
# transient failure, and notifies once however often it runs
import harness_stubs.perf as world  # noqa: E402
from perf.celery_vs_processes import generate_monthly_report  # noqa: E402

assert callable(generate_monthly_report.delay)
world.FAIL_UPLOADS[:] = [ConnectionError("s3 blip")]
run = generate_monthly_report.apply(args=("t1", "2026-09"))
assert run.successful(), run.traceback
assert world.UPLOADS == {"reports/t1/2026-09.pdf": b"%PDF"} and not world.FAIL_UPLOADS
assert generate_monthly_report.apply(args=("t1", "2026-09")).successful()  # delivered twice
assert world.NOTIFIED == {"monthly-report:t1:2026-09:notified": "t1"}, world.NOTIFIED
world.FAIL_UPLOADS[:] = [ValueError("corrupt pdf"), ValueError("not reached")]
assert generate_monthly_report.apply(args=("t2", "2026-09")).failed()
assert len(world.FAIL_UPLOADS) == 1  # a non-transient error ran once
