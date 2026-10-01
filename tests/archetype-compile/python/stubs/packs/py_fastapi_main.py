"""harness: the app the doc's FastAPI blocks make up — app.handlers' FastAPI() with the orders and users
routers, the tenant middleware, an auth middleware that sets request.state.claims (the doc: it must run
first, so it is added after the tenant middleware) and a request-id middleware."""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

import app.users  # noqa: F401 — registers POST /users on the users router
from app.handlers import app
from app.tenancy import router as orders_router
from app.tenant_middleware import TenantMiddleware
from harness_stubs.py_fastapi import claims_for, users_router


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.claims = claims_for(request)
        return await call_next(request)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response


@app.get("/boom")
async def boom() -> None:
    raise RuntimeError("internal detail that must stay in the log")


app.include_router(orders_router)
app.include_router(users_router)
app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestIdMiddleware)
