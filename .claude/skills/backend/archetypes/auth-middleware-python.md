---
skill: auth-middleware-python
description: Python FastAPI auth middleware archetype — JWT dependency, CurrentUser, role-based access, rate limiting, CORS, request ID (contextvars), API key authentication
version: "1.0"
tags:
  - python
  - fastapi
  - middleware
  - auth
  - jwt
  - rbac
  - archetype
  - backend
---

# Auth Middleware Archetype — Python (FastAPI)

> **Canonical reference**: This is the Python counterpart to `backend/archetypes/auth-middleware.md` (Go/chi). Both implement the same auth patterns: JWT validation, RBAC, tenant context, rate limiting, CORS, and request ID tracking.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): imported, type-checked, `create_app()` driven through TestClient with real PyJWT tokens, and the doc's own tests run (10 passed: wrong/missing issuer or audience → 401, settings refuse to start outside local/dev/test, rate limit: a tenant's 2nd request with burst=1 → 429 while another tenant passes). FastAPI 0.142.2, Starlette 1.7.0, PyJWT 2.15.1, pydantic-settings 2.15.0.

Complete authentication and authorization middleware for FastAPI. Every generated auth layer MUST follow this pattern.

## Settings — Fail Closed at Start-Up

```python
# app/config.py

from __future__ import annotations

import logging
import secrets
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_EPHEMERAL_OK = {"local", "dev", "test"}  # exact values; an unset APP_ENV is NOT dev


class Settings(BaseSettings):
    """
    Config from the environment only (APP_ENV, JWT_SECRET_KEY, JWT_ISSUER, JWT_AUDIENCE), checked at
    start-up. Outside APP_ENV=local|dev|test, a missing JWT secret, issuer or audience stops the
    process (security/secure-coding.md §5 — fail closed): without an issuer and audience to check,
    any token signed with the key would be accepted, including one minted for another service.
    """

    app_env: str = ""
    jwt_secret_key: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = ""

    @model_validator(mode="after")
    def _fail_closed(self) -> Self:
        local = self.app_env in _EPHEMERAL_OK
        if len(self.jwt_secret_key) < 32:
            if not local:
                raise ValueError("JWT_SECRET_KEY must be set (>= 32 bytes) when APP_ENV is not local|dev|test")
            self.jwt_secret_key = secrets.token_hex(32)
            logger.warning("JWT_SECRET_KEY unset; using an ephemeral per-process key (APP_ENV=%s)", self.app_env)
        if not (self.jwt_issuer and self.jwt_audience):
            if not local:
                raise ValueError("JWT_ISSUER and JWT_AUDIENCE must be set when APP_ENV is not local|dev|test")
            self.jwt_issuer = self.jwt_issuer or f"widget-api-{self.app_env}"
            self.jwt_audience = self.jwt_audience or f"widget-api-{self.app_env}"
        return self


settings = Settings()  # a misconfigured process fails here, at import, before it serves anything
```

## JWT Dependency — HTTPBearer + Decode

```python
# app/dependencies/auth.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.types import Options

from app.errors import ForbiddenError, UnauthenticatedError

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JWTConfig:
    """JWT validation configuration. Issuer and audience are always checked: a token from another
    issuer, or minted for another service with the same key, must not work here."""

    secret_key: str               # HMAC key or RSA public key
    issuer: str                   # expected 'iss' claim (required)
    audience: str                 # expected 'aud' claim (required)
    algorithm: str = "HS256"      # HS256, RS256, ES256

    def __post_init__(self) -> None:
        if not (self.secret_key and self.issuer and self.audience):
            raise ValueError("JWTConfig: secret_key, issuer and audience are all required")


# Module-level config — set during app startup
_jwt_config: JWTConfig | None = None


def configure_jwt(config: JWTConfig) -> None:
    """Call once during application startup to set JWT config."""
    global _jwt_config
    _jwt_config = config


# ---------------------------------------------------------------------------
# CurrentUser dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CurrentUser:
    """
    Authenticated user extracted from a validated JWT.
    Immutable and hashable — safe to pass through async contexts.
    """

    user_id: UUID
    tenant_id: UUID
    roles: list[str]
    permissions: list[str] | None = None


# ---------------------------------------------------------------------------
# JWT Decode
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises UnauthenticatedError (401) on any validation failure.
    """
    if _jwt_config is None:
        raise RuntimeError("JWT not configured — call configure_jwt() during startup")

    options: Options = {
        "require": ["exp", "iss", "aud", "sub", "tenant_id"],
        "verify_exp": True,
        "verify_iss": True,
        "verify_aud": True,
    }

    try:
        payload = jwt.decode(
            token,
            _jwt_config.secret_key,
            algorithms=[_jwt_config.algorithm],  # pinned: never taken from the token header
            issuer=_jwt_config.issuer,
            audience=_jwt_config.audience,
            options=options,
        )
        return payload
    except jwt.InvalidTokenError as exc:
        # ExpiredSignatureError, InvalidIssuerError, InvalidAudienceError, DecodeError, ... all subclass
        # InvalidTokenError. The client always gets the same 401; the reason stays in the exception
        # chain, which reaches only the log (error-handling-python.md).
        raise UnauthenticatedError(cause=exc) from exc


# ---------------------------------------------------------------------------
# FastAPI Dependency: get_current_user
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """
    FastAPI dependency that extracts and validates the JWT bearer token.
    Injects CurrentUser into the request state for downstream middleware/handlers.

    Usage:
        @router.get("/widgets")
        async def list_widgets(user: CurrentUser = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials
    payload = _decode_token(token)

    try:
        user = CurrentUser(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            roles=payload.get("roles", []),
            permissions=payload.get("permissions"),
        )
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError(cause=exc) from exc

    # Attach to request state for middleware / logging access
    request.state.current_user = user
    return user
```

## Role-Based Access — require_role Dependency

```python
# app/dependencies/auth.py (continued)

def require_role(*required_roles: str):
    """
    Dependency factory that enforces role-based access.
    The user must have at least one of the specified roles.

    Usage:
        @router.post("/admin/settings", dependencies=[Depends(require_role("admin"))])
        async def admin_settings(...):
            ...

        @router.put("/widgets/{id}", dependencies=[Depends(require_role("admin", "editor"))])
        async def update_widget(...):
            ...
    """

    async def _check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(role in user.roles for role in required_roles):
            raise ForbiddenError()  # 403 FORBIDDEN; the body never names the missing role
        return user

    return _check_role


def require_permission(*required_permissions: str):
    """
    Dependency factory that enforces permission-based access.
    The user must have ALL of the specified permissions.

    Usage:
        @router.delete("/widgets/{id}", dependencies=[Depends(require_permission("widgets:delete"))])
    """

    async def _check_permission(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        user_perms = set(user.permissions or [])
        missing = [p for p in required_permissions if p not in user_perms]
        if missing:
            raise ForbiddenError()  # 403 FORBIDDEN; the body never names the missing permission
        return user

    return _check_permission
```

## API Key Authentication (Alternative to JWT)

```python
# app/dependencies/api_key.py

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Protocol
from uuid import UUID

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader

from app.dependencies.auth import CurrentUser
from app.errors import UnauthenticatedError

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyStore(Protocol):
    """Protocol for API key lookup. Implementations query a hashed key store."""

    async def lookup(self, key_hash: str) -> CurrentUser | None:
        """Resolve a hashed API key to a CurrentUser. Returns None if invalid."""
        ...


# Module-level store — set during app startup
_api_key_store: APIKeyStore | None = None


def configure_api_key_store(store: APIKeyStore) -> None:
    """Set the API key store during application startup."""
    global _api_key_store
    _api_key_store = store


def _hash_api_key(raw_key: str) -> str:
    """
    Hash an API key for storage/lookup.
    Use SHA-256 for lookup speed; keys themselves are generated with sufficient entropy.
    For higher security, use bcrypt/argon2 and compare on every request.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_current_user_from_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> CurrentUser:
    """
    FastAPI dependency for API key authentication.
    Use as an alternative to JWT for service-to-service calls.

    Usage:
        @router.get("/webhooks", dependencies=[Depends(get_current_user_from_api_key)])
    """
    if api_key is None:
        raise UnauthenticatedError()

    if _api_key_store is None:
        raise RuntimeError("API key store not configured")

    key_hash = _hash_api_key(api_key)
    user = await _api_key_store.lookup(key_hash)

    if user is None:
        raise UnauthenticatedError()

    request.state.current_user = user
    return user
```

## Rate Limiting — Per-Tenant Token Bucket (a Dependency After Auth)

A per-tenant limit needs the verified tenant, and only authentication knows it. A middleware can't do
this: it runs before any dependency, so `get_current_user` hasn't run yet. The limiter is therefore a
dependency with `get_current_user` as its sub-dependency, which FastAPI resolves once per request and
shares with the endpoint.

```python
# app/dependencies/rate_limit.py

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from fastapi import Depends, Response

from app.dependencies.auth import CurrentUser, get_current_user
from app.errors import RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket. It starts full, so a tenant's first `burst` requests go through."""

    rate: float          # tokens per second
    burst: int           # max tokens
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = float(self.burst)

    def allow(self) -> bool:
        """Check if a request is allowed. Consumes one token if so."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after(self) -> int:
        """Whole seconds until the next token (at least 1)."""
        return max(1, math.ceil((1.0 - self.tokens) / self.rate))


class TenantRateLimiter:
    """
    Per-tenant rate limiting; each tenant gets an independent token bucket.

    Buckets live in this process: with N workers or pods a tenant can get up to N times the limit.
    Use a shared store (e.g. Redis) when the limit must be global.

    Usage:
        limiter = TenantRateLimiter(rate=100.0, burst=200)
        app.include_router(widgets.router, prefix="/api/v1", dependencies=[Depends(limiter)])
    """

    def __init__(self, rate: float = 100.0, burst: int = 200) -> None:
        self._rate = rate
        self._burst = burst
        self._buckets: dict[UUID, TokenBucket] = {}
        self._lock = Lock()

    def _get_bucket(self, tenant_id: UUID) -> TokenBucket:
        if tenant_id not in self._buckets:
            with self._lock:
                if tenant_id not in self._buckets:
                    self._buckets[tenant_id] = TokenBucket(rate=self._rate, burst=self._burst)
        return self._buckets[tenant_id]

    async def __call__(self, response: Response, user: CurrentUser = Depends(get_current_user)) -> None:
        bucket = self._get_bucket(user.tenant_id)
        if not bucket.allow():
            logger.warning("rate limit exceeded", extra={"tenant_id": str(user.tenant_id)})
            # 429 RATE_LIMITED, retryable, with Retry-After — written by the one error writer
            raise RateLimitError(retry_after_seconds=bucket.retry_after())
        response.headers["X-RateLimit-Limit"] = str(self._burst)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
```

## CORS Configuration

```python
# app/middleware/cors.py

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@dataclass
class CORSConfig:
    """CORS configuration — mirrors the Go archetype's CORSConfig."""

    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    allowed_methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    allowed_headers: list[str] = field(default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"])
    exposed_headers: list[str] = field(default_factory=lambda: ["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"])
    allow_credentials: bool = True
    max_age: int = 3600  # preflight cache in seconds


def setup_cors(app: FastAPI, config: CORSConfig | None = None) -> None:
    """
    Configure CORS middleware on the FastAPI app.

    CRITICAL: Never use allow_origins=["*"] with allow_credentials=True.
    Browsers reject this combination.
    """
    cfg = config or CORSConfig()

    if cfg.allow_credentials and "*" in cfg.allowed_origins:
        raise ValueError(
            "CORS: allow_credentials=True cannot be used with allow_origins=['*']. "
            "Specify explicit origins instead."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_methods=cfg.allowed_methods,
        allow_headers=cfg.allowed_headers,
        expose_headers=cfg.exposed_headers,
        allow_credentials=cfg.allow_credentials,
        max_age=cfg.max_age,
    )
```

## Request ID Middleware (contextvars)

```python
# app/middleware/request_id.py

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ContextVar for request-scoped ID — accessible from any async frame
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Retrieve the current request ID from context. Safe to call from any coroutine."""
    return request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique request_id into every request and response.
    Checks X-Request-ID header first (client correlation), generates UUID if absent.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = rid

        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_ctx.reset(token)
```

## Structured Logging Middleware

```python
# app/middleware/logging.py

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_id import get_request_id

logger = logging.getLogger("app.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Structured access logging middleware.
    Logs method, path, status, duration, and auth context for every request.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        user = getattr(request.state, "current_user", None)
        req_id = get_request_id()

        logger.info(
            "request completed",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "tenant_id": str(user.tenant_id) if user else None,
                "user_id": str(user.user_id) if user else None,
                "remote_addr": request.client.host if request.client else None,
            },
        )

        return response
```

## Middleware Stack Assembly

```python
# app/main.py

from __future__ import annotations

from fastapi import Depends, FastAPI

from app.api.v1 import widgets
from app.config import settings
from app.dependencies.auth import JWTConfig, configure_jwt
from app.dependencies.rate_limit import TenantRateLimiter
from app.errors.handlers import register_exception_handlers
from app.middleware.cors import CORSConfig, setup_cors
from app.middleware.logging import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware


def create_app(*, rate_limiter: TenantRateLimiter | None = None) -> FastAPI:
    app = FastAPI(title="Widget API", version="1.0.0")

    # ---------------------------------------------------------------------------
    # Middleware — Starlette runs the LAST one added OUTERMOST, so add them innermost first.
    # Resulting stack (top = outermost):
    #   1. CORS (answers preflight before anything else runs)
    #   2. RequestID (sets the id before anything below logs)
    #   3. AccessLog (times the request and logs it with the request id)
    # Per-tenant rate limiting is not a middleware: it's a dependency after auth (Routes, below).
    # ---------------------------------------------------------------------------

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    setup_cors(app, CORSConfig(
        allowed_origins=["http://localhost:3000", "https://app.example.com"],
    ))

    # ---------------------------------------------------------------------------
    # JWT configuration
    # ---------------------------------------------------------------------------

    configure_jwt(JWTConfig(
        # From the environment, never a literal: Settings refuses to start without the key, issuer and
        # audience unless APP_ENV is exactly local/dev/test (security/secure-coding.md §5 — fail closed)
        secret_key=settings.jwt_secret_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm="HS256",
    ))

    # ---------------------------------------------------------------------------
    # Exception handlers
    # ---------------------------------------------------------------------------

    register_exception_handlers(app)

    # ---------------------------------------------------------------------------
    # Routes — every route of the router is rate-limited per tenant, after authentication
    # ---------------------------------------------------------------------------

    limiter = rate_limiter or TenantRateLimiter(rate=100.0, burst=200)
    app.include_router(widgets.router, prefix="/api/v1", dependencies=[Depends(limiter)])

    return app
```

## Tests — Issuer/Audience, Settings and the Rate Limit

```python
# tests/test_auth.py

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError

from app.api.v1.widgets import get_widget_service
from app.config import Settings, settings
from app.dependencies.rate_limit import TenantRateLimiter
from app.errors import NotFoundError
from app.main import create_app


def make_token(tenant_id: uuid.UUID, **overrides: object) -> str:
    claims: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, settings.jwt_secret_key, algorithm="HS256")


class NoWidgets:
    """Stands in for WidgetService: every lookup is a 404, so a 404 means auth and the limiter let it through."""

    async def get(self, *, tenant_id: uuid.UUID, widget_id: uuid.UUID) -> None:
        raise NotFoundError("Widget")


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(rate_limiter=TenantRateLimiter(rate=0.001, burst=1))  # one request, then ~no refill
    app.dependency_overrides[get_widget_service] = NoWidgets
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def get_widget(client: AsyncClient, token: str) -> Response:
    return await client.get(f"/api/v1/widgets/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.asyncio
async def test_rate_limit_is_per_tenant(client: AsyncClient) -> None:
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()

    assert (await get_widget(client, make_token(tenant_a))).status_code == 404  # through the limiter

    limited = await get_widget(client, make_token(tenant_a))
    assert limited.status_code == 429, limited.text
    err = limited.json()["error"]
    assert err["code"] == "RATE_LIMITED" and err["retryable"] is True
    assert err["request_id"] == limited.headers["x-request-id"]
    assert int(limited.headers["retry-after"]) >= 1

    assert (await get_widget(client, make_token(tenant_b))).status_code == 404  # its own bucket


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [{"iss": "https://someone-else.example"}, {"aud": "another-service"}, {"iss": None}, {"aud": None}],
    ids=["wrong-issuer", "wrong-audience", "no-issuer", "no-audience"],
)
async def test_issuer_and_audience_are_always_checked(client: AsyncClient, overrides: dict[str, object]) -> None:
    resp = await get_widget(client, make_token(uuid.uuid4(), **overrides))
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("app_env", ["qa", "staging", "production", ""])
def test_settings_refuse_to_start_without_jwt_config(monkeypatch: pytest.MonkeyPatch, app_env: str) -> None:
    for name in ("JWT_SECRET_KEY", "JWT_ISSUER", "JWT_AUDIENCE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", app_env)
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings()


def test_settings_need_issuer_and_audience_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "k" * 64)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    with pytest.raises(ValidationError, match="JWT_ISSUER and JWT_AUDIENCE"):
        Settings()
```

## Critical Rules

- JWT validation MUST check signature, expiration, issuer, AND audience — never skip any. Issuer and audience are required settings: `Settings` refuses to start without them unless `APP_ENV` is exactly local/dev/test
- Tenant ID MUST come from the validated token, NEVER from request params or body
- API keys MUST be stored as hashes (SHA-256 minimum for lookup, bcrypt/argon2 for higher security)
- Rate limiters MUST be per-tenant — shared limits allow noisy neighbor abuse — and run as a dependency after authentication (a middleware runs before auth and never sees the tenant)
- CORS MUST NOT use `allow_origins=["*"]` with `allow_credentials=True` — browsers reject this
- Request ID MUST be set on response headers for client-side correlation
- The structured logger MUST include: user_id, tenant_id, request_id, method, path, status, duration
- Middleware order, outermost first: CORS -> RequestID -> AccessLog. Starlette runs the LAST middleware added outermost, so add them in reverse
- RBAC checks (`require_role`, `require_permission`) are applied per-route via `dependencies=[]`, not globally
- Never log JWT tokens, API keys, or credentials — log only derived identifiers (user_id, tenant_id)
- `get_current_user` MUST attach the user to `request.state` for downstream middleware access
- `ContextVar` for request_id enables access from deeply nested async code without passing request objects
- 401 responses MUST include `WWW-Authenticate: Bearer` header (handled by error handler)
- 429 responses MUST include `Retry-After` header
