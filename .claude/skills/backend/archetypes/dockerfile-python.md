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

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Health check — verify the service is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

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
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
```

## Health Check Endpoint

```python
# app/api/health.py

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = APIRouter(tags=["health"])

# Module-level reference — set during app startup
_session_factory: async_sessionmaker[AsyncSession] | None = None

def configure_health(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for health check DB ping."""
    global _session_factory
    _session_factory = session_factory

@router.get("/health")
async def health_check() -> dict:
    """
    Liveness + readiness probe.
    Returns 200 if the service can respond and reach the database.
    Used by Docker HEALTHCHECK and Kubernetes probes.
    """
    db_ok = False
    if _session_factory is not None:
        try:
            async with _session_factory() as session:
                await session.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            db_ok = False

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "checks": {
            "database": "ok" if db_ok else "unreachable",
        },
    }
```

## Docker Compose — Full Stack with DB

```yaml
# docker-compose.yml

services:
  # PostgreSQL
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

  # Redis (cache)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Application
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
      JWT_SECRET_KEY: "dev-secret-change-in-production"
      LOG_LEVEL: "info"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      start_period: 15s
      retries: 3

  # Migration runner (one-shot)
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
- Non-root user is REQUIRED — `USER appuser` must be set before CMD
- Virtual environment MUST be used even in Docker — isolates from system Python
- Dependencies MUST be installed before copying source code — Docker layer caching
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` MUST be set
- Health check MUST be configured — Docker and orchestrators depend on it
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
