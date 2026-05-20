---
skill: dockerfile-typescript
description: TypeScript/Node.js optimized Dockerfile archetype — multi-stage builds, npm/pnpm/bun variants, non-root user, health checks, .dockerignore, Docker Compose snippet
version: "1.0"
tags:
  - typescript
  - docker
  - nodejs
  - dockerfile
  - archetype
  - backend
  - devops
---

# Dockerfile Archetype — TypeScript / Node.js

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/dockerfile.md` (Go, if it exists). Covers multi-stage builds for npm, pnpm, and Bun runtimes.

Complete, production-optimized Dockerfile templates for TypeScript/Node.js applications. Every generated Dockerfile MUST follow this pattern.

---

## npm Variant (Default)

```dockerfile
# Dockerfile — TypeScript/Node.js with npm
# Multi-stage build: build → production

# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:22-alpine AS builder

# Set working directory
WORKDIR /app

# Copy dependency manifests first (leverage Docker layer caching)
COPY package.json package-lock.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci

# Copy source code
COPY tsconfig.json ./
COPY src/ ./src/

# Copy Prisma schema if using Prisma (generate client during build)
COPY prisma/ ./prisma/ 2>/dev/null || true
RUN npx prisma generate 2>/dev/null || true

# Build TypeScript → JavaScript
RUN npm run build

# Remove devDependencies after build
RUN npm ci --omit=dev && npm cache clean --force

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM node:22-alpine AS production

# Security: non-root user
# node:22-alpine includes 'node' user (uid 1000)
USER node

WORKDIR /app

# Copy production dependencies and built output from builder
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/dist ./dist
COPY --from=builder --chown=node:node /app/package.json ./package.json

# Copy Prisma client if present
COPY --from=builder --chown=node:node /app/prisma ./prisma 2>/dev/null || true
COPY --from=builder --chown=node:node /app/node_modules/.prisma ./node_modules/.prisma 2>/dev/null || true

# Environment
ENV NODE_ENV=production
ENV PORT=3000

# Expose the application port
EXPOSE 3000

# Health check — verify the app responds
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Start the application
CMD ["node", "dist/index.js"]
```

---

## pnpm Variant

```dockerfile
# Dockerfile — TypeScript/Node.js with pnpm
# Multi-stage build: build → production

# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:22-alpine AS builder

# Install pnpm globally
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy dependency manifests (pnpm uses pnpm-lock.yaml)
COPY package.json pnpm-lock.yaml ./

# Install all dependencies (frozen lockfile for reproducibility)
RUN pnpm install --frozen-lockfile

# Copy source
COPY tsconfig.json ./
COPY src/ ./src/
COPY prisma/ ./prisma/ 2>/dev/null || true
RUN npx prisma generate 2>/dev/null || true

# Build
RUN pnpm run build

# Remove devDependencies
RUN pnpm prune --prod

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM node:22-alpine AS production

USER node
WORKDIR /app

COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/dist ./dist
COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/prisma ./prisma 2>/dev/null || true
COPY --from=builder --chown=node:node /app/node_modules/.prisma ./node_modules/.prisma 2>/dev/null || true

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/index.js"]
```

---

## Bun Variant (Alternative Runtime)

```dockerfile
# Dockerfile — TypeScript with Bun runtime
# Bun compiles TypeScript natively — no separate build step needed

# =============================================================================
# Stage 1: Install dependencies
# =============================================================================
FROM oven/bun:1 AS builder

WORKDIR /app

# Copy dependency manifests
COPY package.json bun.lockb ./

# Install all dependencies
RUN bun install --frozen-lockfile

# Copy source
COPY tsconfig.json ./
COPY src/ ./src/

# Optional: type-check (Bun runs TS directly but doesn't type-check)
# RUN bun run tsc --noEmit

# Install production dependencies only (separate layer)
RUN bun install --frozen-lockfile --production

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM oven/bun:1-alpine AS production

# Bun images include a non-root 'bun' user
USER bun
WORKDIR /app

COPY --from=builder --chown=bun:bun /app/node_modules ./node_modules
COPY --from=builder --chown=bun:bun /app/src ./src
COPY --from=builder --chown=bun:bun /app/package.json ./package.json
COPY --from=builder --chown=bun:bun /app/tsconfig.json ./tsconfig.json

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD bun --eval "fetch('http://localhost:3000/health').then(r => { if (!r.ok) process.exit(1) })" || exit 1

# Bun runs TypeScript directly — no transpilation needed
CMD ["bun", "run", "src/index.ts"]
```

---

## .dockerignore

```dockerignore
# .dockerignore — keep build context small and secure

# Dependencies (installed inside container)
node_modules/
.pnpm-store/

# Build output (built inside container)
dist/
build/
.next/

# Source control
.git/
.gitignore

# IDE and editor files
.vscode/
.idea/
*.swp
*.swo

# Environment and secrets — NEVER include in image
.env
.env.*
!.env.example
*.pem
*.key

# Test files — not needed in production
**/*.test.ts
**/*.spec.ts
**/__tests__/
**/__mocks__/
coverage/
.nyc_output/

# Documentation
*.md
LICENSE
docs/

# Docker files (prevent recursive context)
Dockerfile*
docker-compose*.yml
.dockerignore

# OS files
.DS_Store
Thumbs.db

# Prisma migrations (applied separately in CI)
# prisma/migrations/  # Uncomment if migrations run separately from the app image

# Temporary files
tmp/
temp/
*.log
```

---

## Docker Compose — Development Stack

```yaml
# docker-compose.yml — Local development stack

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: builder  # Use builder stage for development (includes devDeps)
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://app:app@db:5432/appdb
      REDIS_URL: redis://cache:6379
      PORT: "3000"
      LOG_LEVEL: debug
    volumes:
      # Mount source for hot-reload (dev only)
      - ./src:/app/src:ro
      - ./prisma:/app/prisma:ro
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: appdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 10

  cache:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

---

## Docker Compose — Production

```yaml
# docker-compose.production.yml — Production deployment

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: production
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      PORT: "3000"
      LOG_LEVEL: info
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
        reservations:
          memory: 256M
          cpus: "0.25"
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      start_period: 15s
      retries: 3
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
```

---

## Health Check Endpoint

```typescript
// src/routes/health.ts — required by the Docker HEALTHCHECK

import { Router } from "express";
import type { PrismaClient } from "@prisma/client";
import type { Redis } from "ioredis";

export function createHealthRouter(deps: {
  prisma: PrismaClient;
  redis: Redis;
}): Router {
  const router = Router();

  router.get("/health", async (_req, res) => {
    const checks: Record<string, "ok" | "error"> = {};

    // Database check
    try {
      await deps.prisma.$queryRaw`SELECT 1`;
      checks.database = "ok";
    } catch {
      checks.database = "error";
    }

    // Redis check
    try {
      await deps.redis.ping();
      checks.redis = "ok";
    } catch {
      checks.redis = "error";
    }

    const allHealthy = Object.values(checks).every((v) => v === "ok");

    res.status(allHealthy ? 200 : 503).json({
      status: allHealthy ? "healthy" : "degraded",
      checks,
      timestamp: new Date().toISOString(),
    });
  });

  // Liveness probe — always returns 200 if the process is running
  router.get("/health/live", (_req, res) => {
    res.status(200).json({ status: "alive" });
  });

  // Readiness probe — returns 200 only when dependencies are ready
  router.get("/health/ready", async (_req, res) => {
    try {
      await deps.prisma.$queryRaw`SELECT 1`;
      await deps.redis.ping();
      res.status(200).json({ status: "ready" });
    } catch {
      res.status(503).json({ status: "not ready" });
    }
  });

  return router;
}
```

---

## Build Optimization Tips

```dockerfile
# 1. Use .dockerignore aggressively — smaller context = faster builds
# 2. Copy package.json + lockfile BEFORE source code for layer caching
# 3. Use --mount=type=cache for npm/pnpm cache (BuildKit)

# BuildKit cache mount example:
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .
RUN npm run build

# 4. Final image size comparison:
# | Base Image          | Approx. Size |
# |---------------------|-------------|
# | node:22             | ~1.1 GB     |
# | node:22-slim        | ~200 MB     |
# | node:22-alpine      | ~130 MB     |
# | oven/bun:1-alpine   | ~100 MB     |
#
# Always use -alpine or -slim for production images.

# 5. Security scanning:
# docker scout cves <image>
# trivy image <image>
```

---

## Critical Rules

- Multi-stage builds are MANDATORY — never ship devDependencies or source TypeScript in production images
- Use `npm ci` (not `npm install`) for reproducible builds from lockfile
- Use `--frozen-lockfile` (pnpm) or `--frozen-lockfile` (bun) for reproducibility
- Non-root user is MANDATORY — use the built-in `node` user (Alpine images include it)
- `NODE_ENV=production` MUST be set — frameworks use it for optimizations and security
- Health check is MANDATORY — Docker and orchestrators need it for container lifecycle
- `.dockerignore` MUST exclude: `node_modules/`, `.git/`, `.env*`, `dist/`, test files
- NEVER copy `.env` files into the image — use environment variables at runtime
- Copy `package.json` + lockfile BEFORE source code to leverage Docker layer caching
- Prisma Client MUST be generated during build (`npx prisma generate`) if using Prisma
- `read_only: true` in production compose prevents filesystem writes (use `tmpfs` for temp files)
- Resource limits MUST be set in production — prevent OOM and CPU starvation
- Use `wget` (not `curl`) for health checks in Alpine images — `wget` is pre-installed, `curl` is not
- Bun variant runs TypeScript directly — no transpilation step needed
