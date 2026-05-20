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

Complete authentication and authorization middleware for FastAPI. Every generated auth layer MUST follow this pattern.

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

from app.errors import ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JWTConfig:
    """JWT validation configuration."""

    secret_key: str               # HMAC key or RSA public key
    algorithm: str = "HS256"      # HS256, RS256, ES256
    issuer: str = ""              # Expected 'iss' claim
    audience: str = ""            # Expected 'aud' claim


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
    Raises UnauthorizedError on any validation failure.
    """
    if _jwt_config is None:
        raise RuntimeError("JWT not configured — call configure_jwt() during startup")

    options: dict[str, Any] = {
        "require": ["exp", "sub", "tenant_id"],
        "verify_exp": True,
        "verify_iss": bool(_jwt_config.issuer),
        "verify_aud": bool(_jwt_config.audience),
    }

    try:
        payload = jwt.decode(
            token,
            _jwt_config.secret_key,
            algorithms=[_jwt_config.algorithm],
            issuer=_jwt_config.issuer or None,
            audience=_jwt_config.audience or None,
            options=options,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("token has expired")
    except jwt.InvalidIssuerError:
        raise UnauthorizedError("invalid token issuer")
    except jwt.InvalidAudienceError:
        raise UnauthorizedError("invalid token audience")
    except jwt.DecodeError as exc:
        raise UnauthorizedError("malformed token") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("invalid token") from exc


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
        raise UnauthorizedError("invalid token claims") from exc

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
            raise ForbiddenError(
                action="access",
                resource=f"endpoint requiring roles: {', '.join(required_roles)}",
            )
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
            raise ForbiddenError(
                action="access",
                resource=f"endpoint requiring permissions: {', '.join(missing)}",
            )
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
from app.errors import UnauthorizedError

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
        raise UnauthorizedError("missing X-API-Key header")

    if _api_key_store is None:
        raise RuntimeError("API key store not configured")

    key_hash = _hash_api_key(api_key)
    user = await _api_key_store.lookup(key_hash)

    if user is None:
        raise UnauthorizedError("invalid API key")

    request.state.current_user = user
    return user
```

## Rate Limiting — Per-Tenant Token Bucket

```python
# app/middleware/rate_limit.py

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Simple token bucket rate limiter."""

    rate: float          # tokens per second
    burst: int           # max tokens
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

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


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-tenant rate limiting middleware.
    Each tenant gets an independent token bucket.

    Usage:
        app.add_middleware(TenantRateLimitMiddleware, rate=100.0, burst=200)
    """

    def __init__(self, app, rate: float = 100.0, burst: int = 200) -> None:
        super().__init__(app)
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

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only rate-limit if we have a tenant context (after auth)
        user = getattr(request.state, "current_user", None)
        if user is None:
            return await call_next(request)

        bucket = self._get_bucket(user.tenant_id)
        if not bucket.allow():
            logger.warning(
                "rate limit exceeded",
                extra={"tenant_id": str(user.tenant_id)},
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "too many requests — please retry later",
                        "details": {"retry_after_seconds": 1},
                    }
                },
                headers={
                    "Retry-After": "1",
                    "X-RateLimit-Limit": str(int(self._rate)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return await call_next(request)
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

from fastapi import FastAPI

from app.api.v1 import widgets
from app.dependencies.auth import JWTConfig, configure_jwt
from app.errors.handlers import register_exception_handlers
from app.middleware.cors import CORSConfig, setup_cors
from app.middleware.logging import AccessLogMiddleware
from app.middleware.rate_limit import TenantRateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Widget API", version="1.0.0")

    # ---------------------------------------------------------------------------
    # Middleware — order matters: outermost runs first
    # Stack (top = outermost):
    #   1. CORS (handles preflight before auth)
    #   2. RequestID (generate/extract before anything else)
    #   3. AccessLog (wraps everything for timing)
    #   4. RateLimit (per-tenant, after auth sets tenant context)
    # ---------------------------------------------------------------------------

    setup_cors(app, CORSConfig(
        allowed_origins=["http://localhost:3000", "https://app.example.com"],
    ))

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TenantRateLimitMiddleware, rate=100.0, burst=200)

    # ---------------------------------------------------------------------------
    # JWT configuration
    # ---------------------------------------------------------------------------

    configure_jwt(JWTConfig(
        secret_key="your-secret-key",  # load from env in production
        algorithm="HS256",
        issuer="widget-api",
        audience="widget-api",
    ))

    # ---------------------------------------------------------------------------
    # Exception handlers
    # ---------------------------------------------------------------------------

    register_exception_handlers(app)

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    app.include_router(widgets.router, prefix="/api/v1")

    return app
```

## Critical Rules

- JWT validation MUST check signature, expiration, issuer, AND audience — never skip any
- Tenant ID MUST come from the validated token, NEVER from request params or body
- API keys MUST be stored as hashes (SHA-256 minimum for lookup, bcrypt/argon2 for higher security)
- Rate limiters MUST be per-tenant — shared limits allow noisy neighbor abuse
- CORS MUST NOT use `allow_origins=["*"]` with `allow_credentials=True` — browsers reject this
- Request ID MUST be set on response headers for client-side correlation
- The structured logger MUST include: user_id, tenant_id, request_id, method, path, status, duration
- Middleware order matters: CORS -> RequestID -> AccessLog -> RateLimit
- RBAC checks (`require_role`, `require_permission`) are applied per-route via `dependencies=[]`, not globally
- Never log JWT tokens, API keys, or credentials — log only derived identifiers (user_id, tenant_id)
- `get_current_user` MUST attach the user to `request.state` for downstream middleware access
- `ContextVar` for request_id enables access from deeply nested async code without passing request objects
- 401 responses MUST include `WWW-Authenticate: Bearer` header (handled by error handler)
- 429 responses MUST include `Retry-After` header
