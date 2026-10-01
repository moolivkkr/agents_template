"""harness: auth-middleware-python.md's create_app() as an ASGI app for uvicorn, with the widget service
stood in (every lookup is a 404, so a 404 means auth and the limiter let the request through) and the
limiter under test. HARNESS_LIMITER=redis: RedisTenantRateLimiter on REDIS_URL; =memory:
TenantRateLimiter. Both burst 4 with ~no refill, so the 5th request of a tenant is the first 429."""
import os
import uuid

from redis.asyncio import Redis

from app.api.v1.widgets import get_widget_service
from app.dependencies.rate_limit import TenantRateLimiter
from app.dependencies.rate_limit_redis import RedisTenantRateLimiter
from app.errors import NotFoundError
from app.main import RateLimiter, create_app


class NoWidgets:
    async def get(self, *, tenant_id: uuid.UUID, widget_id: uuid.UUID) -> None:
        raise NotFoundError("Widget")


limiter: RateLimiter
if os.environ["HARNESS_LIMITER"] == "redis":
    limiter = RedisTenantRateLimiter(Redis.from_url(os.environ["REDIS_URL"]), rate=0.001, burst=4)
else:
    limiter = TenantRateLimiter(rate=0.001, burst=4)
app = create_app(rate_limiter=limiter)
app.dependency_overrides[get_widget_service] = NoWidgets
