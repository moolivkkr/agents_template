---
skill: dockerfile-python
description: Python-optimized Docker build archetype — multi-stage builder, non-root user, virtualenv, UV/pip-compile deterministic deps, health check, .dockerignore, Docker Compose with DB dependency
version: "1.0"
tags:
  - python
  - docker
  - dockerfile
  - archetype
  - backend
  - deployment
---

# Dockerfile Archetype — Python

> **Canonical reference**: This is the Python counterpart to the Go multi-stage Dockerfile pattern. Both produce minimal, secure production images with non-root users, health checks, and deterministic dependencies.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): the Python block (/healthz, /readyz, /api/version) was imported, type-checked and called through TestClient (unreachable database → 503 within the timeout; draining → 503), and `/readyz` was run against PostgreSQL 16 across the migration-pattern-python.md revisions (`run.sh --live`). The Dockerfile and Compose blocks were not built. FastAPI 0.142.2, SQLAlchemy 2.1.1, alembic 1.20.0.

Complete Docker build setup for Python backend services. Every generated Dockerfile MUST follow this pattern.

## .dockerignore

```dockerignore
# .dockerignore

# Version control
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
*.egg
dist/
build/
.eggs/
*.whl

# Virtual environments
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# CI/CD
.github/
.gitlab-ci.yml
Jenkinsfile

# Docker
Dockerfile*
docker-compose*.yml
.dockerignore

# Documentation
docs/
*.md
LICENSE

# Environment files — NEVER include secrets in the image
.env
.env.*
*.env

# Misc
.DS_Store
Thumbs.db
tmp/
temp/
```

## Dockerfile — Multi-Stage with UV (Recommended)

```dockerfile
# =============================================================================
# Stage 1: Builder — install dependencies with UV (fast, deterministic)
# =============================================================================

FROM python:3.11-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install UV — the fast Python package manager
# Pin the version for reproducibility
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# Create a virtual environment in a well-known location
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Copy dependency files first — layer caching optimization
# Changes to source code won't invalidate the dependency layer
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev deps)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2: Runtime — minimal production image
# =============================================================================

FROM python:3.11-slim AS runtime

# Labels for container registry
LABEL maintainer="team@example.com" \
      org.opencontainers.image.title="widget-api" \
      org.opencontainers.image.version="1.0.0"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime-only system dependencies
# libpq is needed for asyncpg; curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user — NEVER run as root in production
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /build/app ./app
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini ./

# Set ownership to non-root user
RUN chown -R appuser:appgroup /app

# The deployed commit, for GET /api/version (docker build --build-arg GIT_SHA=$(git rev-parse HEAD))
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

# Switch to the non-root user by NUMBER: Kubernetes' runAsNonRoot rejects a named user
# (CreateContainerConfigError: image has non-numeric user). No trailing comment on the USER line.
USER 1001:1001

# Expose the application port
EXPOSE 8000

# Health check — liveness only (/healthz checks nothing external; /readyz is for load balancers)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run with uvicorn — production settings
CMD ["uvicorn", "app.main:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
```

## Dockerfile — Alternative with pip-compile (No UV)

```dockerfile
# =============================================================================
# Stage 1: Builder — install dependencies with pip-compile for determinism
# =============================================================================

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install pip-tools for deterministic dependency resolution
RUN pip install --no-cache-dir pip-tools

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency specification
COPY requirements.in ./

# Compile deterministic requirements (if not already committed)
# In CI, prefer using a committed requirements.txt
RUN pip-compile requirements.in \
    --output-file=requirements.txt \
    --strip-extras \
    --no-header \
    --quiet

# Install compiled dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./


# =============================================================================
# Stage 2: Runtime — minimal production image
# =============================================================================

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --create-home appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /build/app ./app
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini ./

RUN chown -R appuser:appgroup /app

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

USER 1001:1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
```

## Health and Version Endpoints (the Runtime Contract)

Three endpoints, plain JSON outside the response envelope (`core/resiliency-patterns.md` §Health Checks,
`core/implementation-guidelines-template.md` §Runtime contract):

| Endpoint | Answers | Checks |
|---|---|---|
| `GET /healthz` | liveness (a failure restarts the pod) | nothing external: a DB outage must not become a restart storm |
| `GET /readyz` | readiness (a failure takes the pod out of rotation) | draining, the database within 500 ms, and the schema at this release's newest migration; 503 otherwise. Never an optional dependency such as the cache |
| `GET /api/version` | what is deployed | `{"git_sha", "env"}` from `GIT_SHA` / `APP_ENV`, for smoke checks and deployed-sha preflights |

```python
# app/api/health.py

from __future__ import annotations

import asyncio
import logging
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_READY_TIMEOUT_S = 0.5  # well under the probe's timeoutSeconds

# The newest migration this release ships. alembic/ and alembic.ini are in the image (WORKDIR /app).
_scripts = ScriptDirectory.from_config(Config("alembic.ini"))
_REQUIRED_REVISION = _scripts.get_current_head()

_session_factory: async_sessionmaker[AsyncSession] | None = None
_draining = False


def configure_health(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory readiness pings. Call during application startup."""
    global _session_factory
    _session_factory = session_factory


def start_draining() -> None:
    """Call first on SIGTERM (the lifespan shutdown): /readyz answers 503 while in-flight requests
    finish, so the load balancer stops routing here before the pools close."""
    global _draining
    _draining = True


def _plain(status: int, body: dict[str, str]) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


@router.get("/healthz")
async def healthz() -> JSONResponse:
    """Liveness: the process answers. Nothing external is checked."""
    return _plain(200, {"status": "alive"})


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """Readiness: hard dependencies only. The reason for a 503 goes to the log, never the body."""
    if _draining:
        return _plain(503, {"status": "draining"})
    if _session_factory is None:
        return _plain(503, {"status": "starting"})
    try:
        revision = await asyncio.wait_for(_db_revision(_session_factory), _READY_TIMEOUT_S)
    except Exception:  # refused, timed out, bad credentials, ...
        logger.warning("readiness: database unavailable", exc_info=True)
        return _plain(503, {"status": "database_unavailable"})
    if not _schema_ready(revision):
        return _plain(503, {"status": "schema_not_ready"})  # this release waits for its migration
    return _plain(200, {"status": "ready"})


@router.get("/api/version")
async def version() -> dict[str, str]:
    return {"git_sha": os.environ.get("GIT_SHA", "unknown"), "env": os.environ.get("APP_ENV", "unknown")}


async def _db_revision(session_factory: async_sessionmaker[AsyncSession]) -> str | None:
    async with session_factory() as session:
        # a database that was never migrated has no alembic_version table
        if (await session.execute(text("SELECT to_regclass('alembic_version')"))).scalar() is None:
            return None
        return (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar()


def _schema_ready(db_revision: str | None) -> bool:
    """At this release's newest migration, or at one this release doesn't ship (a newer release
    migrated first; migrations are forward-only and backward compatible, so this code still works)."""
    if db_revision is None:
        return False
    if db_revision == _REQUIRED_REVISION:
        return True
    try:
        _scripts.get_revision(db_revision)
    except CommandError:  # unknown here: newer than this release
        return True
    return False  # an older revision: this release's migration hasn't run yet
```

## Docker Compose — Full Stack with DB

```yaml
# docker-compose.yml

services:
  # ---------------------------------------------------------------------------
  # PostgreSQL
  # ---------------------------------------------------------------------------
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: appdb
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ---------------------------------------------------------------------------
  # Redis (cache)
  # ---------------------------------------------------------------------------
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # ---------------------------------------------------------------------------
  # Application
  # ---------------------------------------------------------------------------
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:postgres@db:5432/appdb"
      REDIS_URL: "redis://redis:6379/0"
      # generated once into a gitignored .env:  printf 'JWT_SECRET_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
      JWT_SECRET_KEY: "${JWT_SECRET_KEY:?generate JWT_SECRET_KEY into .env (gitignored)}"
      LOG_LEVEL: "info"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/readyz"]
      interval: 10s
      timeout: 5s
      start_period: 15s
      retries: 3

  # ---------------------------------------------------------------------------
  # Migration runner (one-shot)
  # ---------------------------------------------------------------------------
  migrate:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:postgres@db:5432/appdb"
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

volumes:
  pgdata:
```

## Docker Compose — Development Override

```yaml
# docker-compose.override.yml
# Auto-loaded by docker compose — adds dev-specific settings

services:
  api:
    build:
      target: builder  # Use builder stage for dev (has dev deps)
    command: ["uvicorn", "app.main:create_app",
              "--factory",
              "--host", "0.0.0.0",
              "--port", "8000",
              "--reload",
              "--reload-dir", "/app/app"]
    volumes:
      # Mount source for hot-reload
      - ./app:/app/app:ro
      - ./alembic:/app/alembic:ro
    environment:
      LOG_LEVEL: "debug"
```

## requirements.in (for pip-compile approach)

```
# requirements.in — top-level dependencies only
# Run: pip-compile requirements.in --output-file=requirements.txt

fastapi>=0.109.0,<1.0
uvicorn[standard]>=0.27.0,<1.0
uvloop>=0.19.0
httptools>=0.6.0
pydantic>=2.5.0,<3.0
sqlalchemy[asyncio]>=2.0.25,<3.0
asyncpg>=0.29.0,<1.0
alembic>=1.13.0,<2.0
redis>=5.0.0,<6.0
PyJWT>=2.8.0,<3.0
structlog>=24.1.0,<25.0
```

## Critical Rules

- Multi-stage build is REQUIRED — builder stage has build tools, runtime stage is minimal
- Non-root user is REQUIRED, by number — `USER 1001:1001` before CMD, on a line with no trailing comment (Kubernetes `runAsNonRoot` rejects a named user)
- Virtual environment MUST be used even in Docker — isolates from system Python
- Dependencies MUST be installed before copying source code — Docker layer caching
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` MUST be set
- Health endpoints follow the runtime contract: `/healthz` (liveness, no dependencies), `/readyz` (503 while draining, the DB is unreachable or the schema is behind), `/api/version` (`git_sha` from the `GIT_SHA` build arg). Never a `/health` that answers 200 with the database down
- The image `HEALTHCHECK` probes `/healthz`; Compose `depends_on` waits on `/readyz`
- `.env` files MUST be in `.dockerignore` — never bake secrets into images
- `requirements.txt` or `uv.lock` MUST be deterministic — use `pip-compile` or `uv lock`
- Prefer UV over pip for 10-50x faster installs — fall back to pip-compile if UV is unavailable
- `--no-cache-dir` MUST be used with pip to reduce image size
- `apt-get` MUST include `rm -rf /var/lib/apt/lists/*` to clean package cache
- Docker Compose services MUST use `depends_on` with `condition: service_healthy`
- Migration runner MUST be a separate one-shot service (`restart: "no"`)
- Development override MUST mount source code for hot-reload
- uvicorn MUST use `--factory` flag when the app is created by a factory function
- uvicorn MUST use `--workers` > 1 in production (typically 2*CPU + 1)
- uvicorn MUST use `uvloop` and `httptools` for performance in production
