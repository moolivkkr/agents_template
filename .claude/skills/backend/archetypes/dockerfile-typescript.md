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

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Express 5.2, Prisma 7.10 (the health route; its /healthz, /readyz and /api/version were also run against Postgres 16) (tests/archetype-compile/typescript/run.sh).
> The npm, pnpm and Bun Dockerfiles were built and run once on 2026-09-30 (not part of run.sh): `node:26-slim` from `.nvmrc` (npm 11, pnpm 12.8.1) and `oven/bun:1.4.2-slim` from `.bun-version`, on a service made of these archetypes (migration-pattern-typescript.md's schema and `prisma.config.ts`, this health router). Each image loads the generated client, runs as uid 65532 on a read-only root filesystem, answers `/healthz` 200 with the Docker HEALTHCHECK `healthy`, runs `prisma migrate deploy` itself, and `/readyz` turns 200 after it against Postgres 16. The development compose was run too: the `migrate` one-shot exits 0, the `dev` target serves through the project's `tsx watch` as uid 65532 with `/readyz` 200, and editing the mounted source restarts it.

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/dockerfile.md` (Go, if it exists). Covers multi-stage builds for npm, pnpm, and Bun runtimes.

Complete, production-optimized Dockerfile templates for TypeScript/Node.js applications. Every generated Dockerfile MUST follow this pattern.

---

## npm Variant (Default)

```dockerfile
# Dockerfile — TypeScript/Node.js with npm
# Multi-stage build: deps → dev (docker compose, watch mode) | builder → production
#   docker build --build-arg NODE_VERSION="$(cat .nvmrc)" --build-arg GIT_SHA="$(git rev-parse HEAD)" .

# The Node major from the project's version file (.nvmrc / engines) — the same value as
# IMPLEMENTATION_GUIDELINES §Commands and versions. No default: a missing build arg fails the build.
ARG NODE_VERSION

# =============================================================================
# Stage 1: Dependencies — every dependency + the generated Prisma client (shared by dev and builder)
# =============================================================================
FROM node:${NODE_VERSION}-slim AS deps

WORKDIR /app

# Dependency manifests first (layer caching); lifecycle scripts off
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Prisma client: generate from the schema + prisma.config.ts, no DATABASE_URL needed at build time
# (prisma.config.ts reads process.env, not env() — see migration-pattern-typescript.md). No `|| true`:
# a failed generate must fail the build, not ship an image without a client.
COPY prisma.config.ts ./
COPY prisma/ ./prisma/
RUN npx prisma generate

COPY tsconfig.json ./
COPY src/ ./src/

# =============================================================================
# Stage 2: Development — `docker compose` target. Keeps devDependencies; compose mounts src/ over the copy.
# =============================================================================
FROM deps AS dev

ENV NODE_ENV=development
ENV PORT=3000
# npm writes its cache and logs under $HOME; the numeric user has no home directory of its own
ENV HOME=/tmp
USER 65532:65532
EXPOSE 3000
# The project's watch command, e.g. "dev": "tsx watch src/index.ts" in package.json
CMD ["npm", "run", "dev"]

# =============================================================================
# Stage 3: Build
# =============================================================================
FROM deps AS builder

RUN npm run build

# Drop devDependencies IN PLACE. Never `npm ci --omit=dev` here: re-installing deletes node_modules/.prisma,
# the client generated above, and the image then fails at startup ("Cannot find module '.prisma/client/default'").
RUN npm prune --omit=dev && npm cache clean --force

# =============================================================================
# Stage 4: Production
# =============================================================================
FROM node:${NODE_VERSION}-slim AS production

ENV NODE_ENV=production
ENV PORT=3000
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

WORKDIR /app

# Root-owned and read-only for the app user: the image works with a read-only root filesystem
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
# prisma/migrations: /readyz waits for the newest one. prisma.config.ts: the migrate Job runs this image
# (`npx prisma migrate deploy`), which needs "prisma" and "dotenv" in dependencies, not devDependencies.
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/prisma.config.ts ./prisma.config.ts

# Numeric non-root user (runAsNonRoot needs a numeric UID); no trailing comment on this line
USER 65532:65532

EXPOSE 3000

# Liveness only (the runtime contract's /healthz). node:*-slim has no wget/curl, so node probes itself.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:' + (process.env.PORT || 3000) + '/healthz').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "dist/index.js"]
```

---

## pnpm Variant

```dockerfile
# Dockerfile — TypeScript/Node.js with pnpm
# Multi-stage build: build → production
#   docker build --build-arg NODE_VERSION="$(cat .nvmrc)" --build-arg GIT_SHA="$(git rev-parse HEAD)" .

# The Node major from the project's version file (.nvmrc / engines). No default: a missing build arg fails.
ARG NODE_VERSION

# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:${NODE_VERSION}-slim AS builder

WORKDIR /app

# pnpm at the version package.json "packageManager" pins (Node 25+ images ship no corepack)
COPY package.json pnpm-*.yaml ./
RUN npm install -g "pnpm@$(node -p "require('./package.json').packageManager.split('@')[1].split('+')[0]")"

# Install all dependencies (frozen lockfile; lifecycle scripts off — prisma generate runs explicitly below)
RUN pnpm install --frozen-lockfile --ignore-scripts

# Prisma client: generated from the schema + prisma.config.ts, no DATABASE_URL at build time. No `|| true`.
COPY prisma.config.ts ./
COPY prisma/ ./prisma/
RUN pnpm exec prisma generate

# Build
COPY tsconfig.json ./
COPY src/ ./src/
RUN pnpm run build

# Drop devDependencies in place (the generated client lives in the virtual store and survives this)
RUN pnpm prune --prod --ignore-scripts

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM node:${NODE_VERSION}-slim AS production

ENV NODE_ENV=production
ENV PORT=3000
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

WORKDIR /app

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/prisma.config.ts ./prisma.config.ts

USER 65532:65532

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:' + (process.env.PORT || 3000) + '/healthz').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "dist/index.js"]
```

---

## Bun Variant (Alternative Runtime)

```dockerfile
# Dockerfile — TypeScript with Bun runtime
# Bun runs TypeScript directly — no separate build step needed
#   docker build --build-arg BUN_VERSION="$(cat .bun-version)" --build-arg GIT_SHA="$(git rev-parse HEAD)" .

# The Bun version from the project's version file (.bun-version) — the same value as
# IMPLEMENTATION_GUIDELINES §Commands and versions. No default: a missing build arg fails the build.
ARG BUN_VERSION

# =============================================================================
# Stage 1: Production dependencies + the generated Prisma client
# =============================================================================
FROM oven/bun:${BUN_VERSION}-slim AS deps

WORKDIR /app

# bun.lock (text, Bun >= 1.2) or bun.lockb (older Bun)
COPY package.json bun.lock* ./

# Bun has no `prune`: install production dependencies FIRST, then generate the client into them. A later
# `bun install --production` would re-create node_modules without the generated client. Scripts off.
# ("prisma" and "dotenv" are dependencies when this image also runs the migrate Job.)
RUN bun install --frozen-lockfile --production --ignore-scripts
COPY prisma.config.ts ./
COPY prisma/ ./prisma/
RUN bunx prisma generate

# Bun runs TypeScript without type-checking it: run `bunx tsc --noEmit` in CI, not in this image

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM oven/bun:${BUN_VERSION}-slim AS production

ENV NODE_ENV=production
ENV PORT=3000
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/prisma ./prisma
COPY --from=deps /app/prisma.config.ts ./prisma.config.ts
COPY package.json tsconfig.json ./
COPY src/ ./src/

# Numeric non-root user (runAsNonRoot needs a numeric UID); no trailing comment on this line
USER 65532:65532

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["bun", "-e", "fetch('http://127.0.0.1:' + (process.env.PORT || 3000) + '/healthz').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

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
# Run: NODE_VERSION="$(cat .nvmrc)" docker compose up

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: dev  # devDependencies + the project's `npm run dev` watcher (the builder stage ends pruned)
      args:
        NODE_VERSION: ${NODE_VERSION:?set NODE_VERSION from .nvmrc}
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
      migrate:
        condition: service_completed_successfully
      cache:
        condition: service_healthy
    restart: unless-stopped

  # One-shot: apply migrations before the app starts (so /readyz can pass), then exit
  migrate:
    build:
      context: .
      dockerfile: Dockerfile
      target: deps  # has the prisma CLI and prisma.config.ts
      args:
        NODE_VERSION: ${NODE_VERSION:?set NODE_VERSION from .nvmrc}
    command: ["npx", "prisma", "migrate", "deploy"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/appdb
    volumes:
      - ./prisma:/app/prisma:ro
    depends_on:
      db:
        condition: service_healthy

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
      args:
        NODE_VERSION: ${NODE_VERSION:?set NODE_VERSION from .nvmrc}
        GIT_SHA: ${GIT_SHA:-unknown}
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
      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/healthz').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
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
// src/routes/health.ts — the runtime contract (core/implementation-guidelines-template.md §Runtime contract):
// /healthz (liveness), /readyz (readiness), /api/version. Plain JSON, outside the response envelope.

import { readdirSync } from "node:fs";
import { Router } from "express";
import type { PrismaClient } from "@prisma/client";

/** The newest migration this image ships (prisma/migrations/<timestamp>_<name>) — read once at startup. */
export function latestShippedMigration(dir = "prisma/migrations"): string | undefined {
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()
    .at(-1);
}

export function createHealthRouter(deps: {
  prisma: PrismaClient;
  requiredMigration: string | undefined; // latestShippedMigration()
}): Router {
  const router = Router();

  // Liveness — the process can answer. Never touches a dependency: a DB outage must not restart pods.
  router.get("/healthz", (_req, res) => {
    res.json({ status: "ok" });
  });

  // Readiness — hard dependencies the release needs: the DB, at this image's schema version. Never an
  // optional one (the Redis cache): losing it degrades the service; it doesn't make it unready.
  // New pods stay unready until the migrate Job lands this image's migrations; old pods keep serving.
  router.get("/readyz", async (_req, res) => {
    try {
      const applied = await deps.prisma.$queryRaw<Array<{ applied: boolean }>>`
        SELECT EXISTS (
          SELECT 1 FROM _prisma_migrations
          WHERE migration_name = ${deps.requiredMigration ?? ""}
            AND finished_at IS NOT NULL AND rolled_back_at IS NULL
        ) AS applied`;
      if (deps.requiredMigration && applied[0]?.applied) {
        res.json({ status: "ready" });
        return;
      }
    } catch {
      // DB unreachable, or no _prisma_migrations table yet — not ready (the cause stays out of the body)
    }
    res.status(503).json({ status: "not_ready" });
  });

  // Build identity — the deployed-sha preflights and smoke.sh read it
  router.get("/api/version", (_req, res) => {
    res.json({ git_sha: process.env.GIT_SHA ?? "unknown", env: process.env.APP_ENV ?? "unknown" });
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
ARG NODE_VERSION
FROM node:${NODE_VERSION}-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts
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
- Use `--frozen-lockfile` (pnpm) or `--frozen-lockfile` (bun) for reproducibility; Bun >= 1.2 writes a text `bun.lock` (older: `bun.lockb`), so copy `bun.lock*`
- Development runs the `dev` stage (all devDependencies + the project's watch script) — never the `builder` stage, which ends pruned; the compose `migrate` one-shot applies migrations before the app starts
- Non-root user is MANDATORY — a numeric `USER 65532:65532` on its own line (a named user fails `runAsNonRoot`)
- The Node base image is `node:${NODE_VERSION}-slim`, with `NODE_VERSION` from the project's version file (`.nvmrc` / `engines`), passed as a build arg — never a hard-coded tag
- `NODE_ENV=production` MUST be set — frameworks use it for optimizations and security
- Health check is MANDATORY — Docker and orchestrators need it for container lifecycle
- `.dockerignore` MUST exclude: `node_modules/`, `.git/`, `.env*`, `dist/`, test files
- NEVER copy `.env` files into the image — use environment variables at runtime
- Copy `package.json` + lockfile BEFORE source code to leverage Docker layer caching
- Prisma Client MUST be generated during build (`npx prisma generate`) with `prisma.config.ts` copied in, and never behind `|| true` — a failed generate must fail the build
- Remove devDependencies with `npm prune --omit=dev` / `pnpm prune --prod`, never a second `npm ci --omit=dev`: re-installing deletes the generated client (`node_modules/.prisma`) and the image crashes at startup
- If the migrate Job runs the app image (`npx prisma migrate deploy`), `prisma` and `dotenv` are `dependencies`, and the image carries `prisma/` and `prisma.config.ts`
- `COPY` takes no shell syntax — `COPY x ./ 2>/dev/null || true` treats `2>/dev/null`, `||` and `true` as source paths and fails the build
- `read_only: true` in production compose prevents filesystem writes (use `tmpfs` for temp files)
- Resource limits MUST be set in production — prevent OOM and CPU starvation
- `node:*-slim` has neither `wget` nor `curl`: the HEALTHCHECK runs `node -e "fetch(…/healthz)"` against the runtime contract's liveness path
- Bun variant runs TypeScript directly — no transpilation step needed
