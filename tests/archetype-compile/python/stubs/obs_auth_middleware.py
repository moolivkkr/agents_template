"""harness-only stand-in for the auth middleware observability-python.md's main.py installs: it
"verifies" a bearer token (fixed test token) and puts tenant_id/user_id on request.state and in the
structlog context, as the doc describes."""
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.headers.get("authorization") != "Bearer harness-token":
            return JSONResponse({"error": {"code": "UNAUTHENTICATED", "message": "Sign in to continue.",
                                           "request_id": "", "retryable": False}}, status_code=401)
        request.state.tenant_id = "tenant_a"
        request.state.user_id = "user_1"
        structlog.contextvars.bind_contextvars(tenant_id="tenant_a", user_id="user_1")
        return await call_next(request)
