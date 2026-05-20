---
skill: crud-service-typescript
description: TypeScript service layer archetype — CRUD operations with cache-aside, audit logging, tenant isolation, transaction support (Prisma + Drizzle), typed errors, input validation
version: "1.0"
tags:
  - typescript
  - service
  - crud
  - prisma
  - drizzle
  - archetype
  - backend
---

# CRUD Service Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-service.md` (Go). Both implement identical business logic patterns: cache-aside, optimistic locking, audit logging, and tenant isolation.

Complete, production-ready TypeScript service layer template. Every generated TypeScript service MUST follow this pattern.

## Domain Types

```typescript
// src/domain/entity.ts

/** Base entity fields — all domain objects embed this. */
export interface Entity {
  id: string;
  tenantId: string;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
  createdBy: string;
  updatedBy: string;
  version: number;
}

/** Widget domain object. */
export interface Widget extends Entity {
  name: string;
  description: string;
  status: WidgetStatus;
}

export const WidgetStatus = {
  Active: "active",
  Archived: "archived",
  Draft: "draft",
} as const;

export type WidgetStatus = (typeof WidgetStatus)[keyof typeof WidgetStatus];

/** Audit entry for compliance logging. */
export interface AuditEntry {
  action: string;
  entityId: string;
  tenantId: string;
  actorId: string;
  timestamp: Date;
  changes?: unknown;
}
```

## Service Interface

```typescript
// src/services/widget.service.interface.ts

import type { Widget } from "../domain/entity";
import type { ListFilters, ListResult, OffsetListFilters, OffsetListResult } from "../types/pagination";

export interface CreateWidgetInput {
  name: string;
  description: string;
}

export interface UpdateWidgetInput {
  name: string;
  description: string;
  version: number;
}

/**
 * WidgetService defines the business operations for widgets.
 * Rule: Keep interfaces small (3-7 methods). Split if > 7.
 */
export interface IWidgetService {
  create(tenantId: string, userId: string, input: CreateWidgetInput): Promise<Widget>;
  get(tenantId: string, id: string): Promise<Widget>;
  update(tenantId: string, id: string, input: UpdateWidgetInput): Promise<Widget>;
  delete(tenantId: string, id: string): Promise<void>;
  list(tenantId: string, filters: ListFilters): Promise<ListResult<Widget>>;
  listOffset(tenantId: string, filters: OffsetListFilters): Promise<OffsetListResult<Widget>>;
}
```

## Repository Interface

```typescript
// src/repositories/widget.repository.interface.ts

import type { Widget } from "../domain/entity";
import type { ListFilters, ListResult, OffsetListFilters, OffsetListResult } from "../types/pagination";

/**
 * Repository defines the data access contract. Owned by the consumer (service).
 * Accept interfaces, return structs — constructor takes interfaces, returns concrete type.
 */
export interface IWidgetRepository {
  create(widget: Widget): Promise<Widget>;
  findById(tenantId: string, id: string): Promise<Widget | null>;
  findByName(tenantId: string, name: string): Promise<Widget | null>;
  update(widget: Widget): Promise<Widget>;
  softDelete(tenantId: string, id: string): Promise<void>;
  list(tenantId: string, filters: ListFilters): Promise<ListResult<Widget>>;
  listOffset(tenantId: string, filters: OffsetListFilters): Promise<OffsetListResult<Widget>>;
}
```

## Cache Interface

```typescript
// src/lib/cache.interface.ts

/** Cache abstracts the caching layer (Redis, Memcached, in-memory). */
export interface ICache {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, ttlSeconds: number): Promise<void>;
  delete(key: string): Promise<void>;
}
```

## Audit Writer Interface

```typescript
// src/lib/audit.interface.ts

import type { AuditEntry } from "../domain/entity";

/** AuditWriter abstracts audit log persistence (event bus, append-only table, etc.). */
export interface IAuditWriter {
  write(entry: AuditEntry): Promise<void>;
}
```

## Service Implementation

```typescript
// src/services/widget.service.ts

import { randomUUID } from "node:crypto";
import type { Widget, AuditEntry } from "../domain/entity";
import { WidgetStatus } from "../domain/entity";
import type { IWidgetRepository } from "../repositories/widget.repository.interface";
import type { ICache } from "../lib/cache.interface";
import type { IAuditWriter } from "../lib/audit.interface";
import type { IWidgetService, CreateWidgetInput, UpdateWidgetInput } from "./widget.service.interface";
import type { ListFilters, ListResult, OffsetListFilters, OffsetListResult } from "../types/pagination";
import {
  ValidationError,
  NotFoundError,
  ConflictError,
  InternalError,
} from "../errors/domain-errors";
import type { Logger } from "../lib/logger";

const CACHE_TTL_SECONDS = 300; // 5 minutes

export class WidgetService implements IWidgetService {
  private readonly cacheTTL = CACHE_TTL_SECONDS;

  constructor(
    private readonly repo: IWidgetRepository,
    private readonly cache: ICache,
    private readonly auditWriter: IAuditWriter,
    private readonly logger: Logger,
  ) {}

  // --- Create ---

  async create(tenantId: string, userId: string, input: CreateWidgetInput): Promise<Widget> {
    // 1. Validate input
    this.validateCreateInput(input);

    // 2. Check for duplicate name within tenant
    const existing = await this.repo.findByName(tenantId, input.name);
    if (existing) {
      throw new ConflictError("widget", `name '${input.name}' already exists`);
    }

    // 3. Build domain object
    const now = new Date();
    const widget: Widget = {
      id: randomUUID(),
      tenantId,
      name: input.name.trim(),
      description: input.description.trim(),
      status: WidgetStatus.Active,
      createdAt: now,
      updatedAt: now,
      deletedAt: null,
      createdBy: userId,
      updatedBy: userId,
      version: 1,
    };

    // 4. Persist
    const created = await this.repo.create(widget);

    // 5. Audit log (fire-and-forget — never block the business operation)
    this.auditLog("widget.created", created.id, tenantId, userId, created);

    this.logger.info("widget created", { widgetId: created.id, tenantId });
    return created;
  }

  // --- Get with Cache-Aside ---

  async get(tenantId: string, id: string): Promise<Widget> {
    const cacheKey = this.cacheKey(tenantId, id);

    // 1. Check cache
    const cached = await this.cache.get<Widget>(cacheKey);
    if (cached) {
      this.logger.debug("cache hit", { widgetId: id, tenantId });
      return cached;
    }
    this.logger.debug("cache miss, querying database", { widgetId: id, tenantId });

    // 2. Query DB
    const widget = await this.repo.findById(tenantId, id);
    if (!widget) {
      throw new NotFoundError("widget", id);
    }

    // 3. Populate cache
    await this.cache.set(cacheKey, widget, this.cacheTTL).catch((err) => {
      this.logger.warn("cache set failed", { error: err, widgetId: id });
    });

    return widget;
  }

  // --- Update with Optimistic Locking and Cache Invalidation ---

  async update(tenantId: string, id: string, input: UpdateWidgetInput): Promise<Widget> {
    // 1. Validate input
    this.validateUpdateInput(input);

    // 2. Fetch current (ensures tenant-scoping)
    const existing = await this.repo.findById(tenantId, id);
    if (!existing) {
      throw new NotFoundError("widget", id);
    }

    // 3. Optimistic lock check
    if (input.version !== existing.version) {
      throw new ConflictError("widget", "version mismatch — reload and retry");
    }

    // 4. Apply changes
    const updated: Widget = {
      ...existing,
      name: input.name.trim(),
      description: input.description.trim(),
      updatedAt: new Date(),
      version: existing.version + 1,
    };

    // 5. Persist
    const result = await this.repo.update(updated);

    // 6. Invalidate cache
    await this.cache.delete(this.cacheKey(tenantId, id)).catch((err) => {
      this.logger.warn("cache invalidation failed", { error: err, widgetId: id });
    });

    // 7. Audit log
    this.auditLog("widget.updated", id, tenantId, existing.updatedBy, input);

    this.logger.info("widget updated", { widgetId: id, tenantId });
    return result;
  }

  // --- Delete with Cache Invalidation ---

  async delete(tenantId: string, id: string): Promise<void> {
    // 1. Soft delete
    await this.repo.softDelete(tenantId, id);

    // 2. Invalidate cache
    await this.cache.delete(this.cacheKey(tenantId, id)).catch((err) => {
      this.logger.warn("cache invalidation failed", { error: err, widgetId: id });
    });

    // 3. Audit log
    this.auditLog("widget.deleted", id, tenantId, "", null);

    this.logger.info("widget deleted", { widgetId: id, tenantId });
  }

  // --- List with Cursor Pagination ---

  async list(tenantId: string, filters: ListFilters): Promise<ListResult<Widget>> {
    // Enforce pagination defaults and maximums
    const sanitized: ListFilters = {
      cursor: filters.cursor,
      pageSize: Math.min(Math.max(filters.pageSize || 20, 1), 100),
      sortBy: filters.sortBy || "created_at",
      sortDir: filters.sortDir || "desc",
      fields: filters.fields,
    };

    const result = await this.repo.list(tenantId, sanitized);
    this.logger.info("list completed", {
      tenantId,
      resultCount: result.items.length,
      hasMore: result.hasMore,
    });
    return result;
  }

  // --- List with Offset Pagination (Admin/Reporting) ---

  async listOffset(tenantId: string, filters: OffsetListFilters): Promise<OffsetListResult<Widget>> {
    const sanitized: OffsetListFilters = {
      page: Math.max(filters.page || 1, 1),
      perPage: Math.min(Math.max(filters.perPage || 20, 1), 100),
      sortBy: filters.sortBy || "created_at",
      sortDir: filters.sortDir || "desc",
      fields: filters.fields,
    };

    return this.repo.listOffset(tenantId, sanitized);
  }

  // --- Private Helpers ---

  private validateCreateInput(input: CreateWidgetInput): void {
    if (!input.name?.trim()) {
      throw new ValidationError("name", "name is required");
    }
    if (input.name.length > 255) {
      throw new ValidationError("name", "name must be 255 characters or fewer");
    }
    if (input.description && input.description.length > 2000) {
      throw new ValidationError("description", "description must be 2000 characters or fewer");
    }
  }

  private validateUpdateInput(input: UpdateWidgetInput): void {
    if (!input.name?.trim()) {
      throw new ValidationError("name", "name is required");
    }
    if (input.version == null || input.version < 0) {
      throw new ValidationError("version", "version is required and must be non-negative");
    }
  }

  private cacheKey(tenantId: string, id: string): string {
    return `widget:${tenantId}:${id}`;
  }

  private auditLog(action: string, entityId: string, tenantId: string, actorId: string, changes: unknown): void {
    const entry: AuditEntry = {
      action,
      entityId,
      tenantId,
      actorId,
      timestamp: new Date(),
      changes,
    };
    // Fire-and-forget — never block the business operation
    this.auditWriter.write(entry).catch((err) => {
      this.logger.error("audit log failed", { action, entityId, error: err });
    });
  }
}
```

---

## Transaction Support — Prisma

```typescript
// src/services/widget.service.prisma-tx.ts

import { PrismaClient } from "@prisma/client";
import type { Widget } from "../domain/entity";

/**
 * Multi-step creation within a Prisma transaction.
 * All operations succeed or all roll back.
 */
export async function createWithRelations(
  prisma: PrismaClient,
  input: {
    widget: { name: string; description: string; tenantId: string; userId: string };
    components: Array<{ name: string; type: string }>;
  },
): Promise<Widget> {
  return prisma.$transaction(async (tx) => {
    // Step 1: Create parent widget
    const widget = await tx.widget.create({
      data: {
        name: input.widget.name,
        description: input.widget.description,
        tenantId: input.widget.tenantId,
        status: "active",
        createdBy: input.widget.userId,
        updatedBy: input.widget.userId,
        version: 1,
      },
    });

    // Step 2: Create child components (all within same transaction)
    await tx.component.createMany({
      data: input.components.map((comp) => ({
        widgetId: widget.id,
        name: comp.name,
        type: comp.type,
        tenantId: input.widget.tenantId,
        createdBy: input.widget.userId,
        updatedBy: input.widget.userId,
      })),
    });

    return widget as Widget;
  });
}

/**
 * Prisma interactive transaction with custom timeout and isolation level.
 */
export async function updateWithInventoryCheck(
  prisma: PrismaClient,
  tenantId: string,
  widgetId: string,
  quantity: number,
): Promise<void> {
  await prisma.$transaction(
    async (tx) => {
      const inventory = await tx.inventory.findUnique({
        where: { widgetId_tenantId: { widgetId, tenantId } },
      });

      if (!inventory || inventory.quantity < quantity) {
        throw new Error("insufficient inventory");
      }

      await tx.inventory.update({
        where: { widgetId_tenantId: { widgetId, tenantId } },
        data: { quantity: { decrement: quantity } },
      });

      await tx.order.create({
        data: { widgetId, tenantId, quantity, status: "confirmed" },
      });
    },
    {
      maxWait: 5000,     // max time to wait to acquire a transaction slot
      timeout: 10000,    // max time the transaction can run
      isolationLevel: "Serializable",
    },
  );
}
```

---

## Transaction Support — Drizzle

```typescript
// src/services/widget.service.drizzle-tx.ts

import { type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import { widgets, components } from "../db/schema";
import type { Widget } from "../domain/entity";

/**
 * Multi-step creation within a Drizzle transaction.
 * All operations succeed or all roll back.
 */
export async function createWithRelations(
  db: PostgresJsDatabase,
  input: {
    widget: { name: string; description: string; tenantId: string; userId: string };
    components: Array<{ name: string; type: string }>;
  },
): Promise<Widget> {
  return db.transaction(async (tx) => {
    // Step 1: Create parent widget
    const [widget] = await tx
      .insert(widgets)
      .values({
        name: input.widget.name,
        description: input.widget.description,
        tenantId: input.widget.tenantId,
        status: "active",
        createdBy: input.widget.userId,
        updatedBy: input.widget.userId,
        version: 1,
      })
      .returning();

    // Step 2: Create child components
    if (input.components.length > 0) {
      await tx.insert(components).values(
        input.components.map((comp) => ({
          widgetId: widget.id,
          name: comp.name,
          type: comp.type,
          tenantId: input.widget.tenantId,
          createdBy: input.widget.userId,
          updatedBy: input.widget.userId,
        })),
      );
    }

    return widget as Widget;
  });
}

/**
 * Drizzle transaction with savepoints for partial rollback.
 */
export async function transferWidget(
  db: PostgresJsDatabase,
  tenantId: string,
  widgetId: string,
  fromUserId: string,
  toUserId: string,
): Promise<void> {
  await db.transaction(async (tx) => {
    // Verify ownership
    const [widget] = await tx
      .select()
      .from(widgets)
      .where(
        and(
          eq(widgets.id, widgetId),
          eq(widgets.tenantId, tenantId),
          eq(widgets.createdBy, fromUserId),
          isNull(widgets.deletedAt),
        ),
      );

    if (!widget) {
      throw new NotFoundError("widget", widgetId);
    }

    // Transfer ownership
    await tx
      .update(widgets)
      .set({
        updatedBy: toUserId,
        updatedAt: new Date(),
        version: widget.version + 1,
      })
      .where(
        and(
          eq(widgets.id, widgetId),
          eq(widgets.version, widget.version), // optimistic lock
        ),
      );
  });
}
```

---

## Logger Interface

```typescript
// src/lib/logger.ts

/**
 * Structured logger interface — compatible with pino, winston, or console.
 * Every service accepts this via constructor injection.
 */
export interface Logger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
}

/** Pino-based implementation example. */
import pino from "pino";

export function createLogger(name: string): Logger {
  const base = pino({ name });
  return {
    debug: (msg, meta) => base.debug(meta, msg),
    info: (msg, meta) => base.info(meta, msg),
    warn: (msg, meta) => base.warn(meta, msg),
    error: (msg, meta) => base.error(meta, msg),
  };
}
```

---

## Redis Cache Implementation

```typescript
// src/lib/redis-cache.ts

import type { Redis } from "ioredis";
import type { ICache } from "./cache.interface";

export class RedisCache implements ICache {
  constructor(private readonly redis: Redis) {}

  async get<T>(key: string): Promise<T | null> {
    const data = await this.redis.get(key);
    if (!data) return null;
    try {
      return JSON.parse(data) as T;
    } catch {
      // Corrupted cache entry — treat as miss
      await this.redis.del(key);
      return null;
    }
  }

  async set<T>(key: string, value: T, ttlSeconds: number): Promise<void> {
    await this.redis.set(key, JSON.stringify(value), "EX", ttlSeconds);
  }

  async delete(key: string): Promise<void> {
    await this.redis.del(key);
  }
}
```

---

## Service Wiring (Composition Root)

```typescript
// src/composition-root.ts

import { PrismaClient } from "@prisma/client";
import Redis from "ioredis";
import { WidgetService } from "./services/widget.service";
import { PrismaWidgetRepository } from "./repositories/prisma-widget.repository";
import { RedisCache } from "./lib/redis-cache";
import { AuditWriter } from "./lib/audit-writer";
import { createLogger } from "./lib/logger";

/**
 * Composition root — wire all dependencies.
 * Every dependency is explicit. No global state.
 */
export function createServices() {
  const prisma = new PrismaClient();
  const redis = new Redis(process.env.REDIS_URL!);

  const cache = new RedisCache(redis);
  const auditWriter = new AuditWriter(prisma);
  const widgetLogger = createLogger("widget-service");

  const widgetRepo = new PrismaWidgetRepository(prisma);
  const widgetService = new WidgetService(widgetRepo, cache, auditWriter, widgetLogger);

  return {
    prisma,
    redis,
    widgetService,
    shutdown: async () => {
      await prisma.$disconnect();
      redis.disconnect();
    },
  } as const;
}
```

---

## Critical Rules

- Every operation MUST receive `tenantId` as an explicit parameter — no cross-tenant data leaks
- Every mutation MUST produce an audit log entry (fire-and-forget — never block business ops)
- Cache invalidation MUST happen on every write (Update, Delete)
- Cache misses MUST populate the cache before returning
- Optimistic locking via `version` field — reject stale writes with `ConflictError`
- Input validation MUST happen before any side effects (DB, cache, external calls)
- Errors MUST be typed `AppError` subclasses from `error-handling-typescript.md`
- Max 40 lines of logic per function — extract helpers for complex steps
- Accept interfaces, return concrete types — constructor takes interfaces via DI
- Never return unbounded lists — always enforce `pageSize` max (100)
- Transaction boundaries MUST be explicit — use `$transaction` (Prisma) or `db.transaction` (Drizzle)
- Cache failures MUST NOT propagate — catch and log, never throw from cache operations
- Audit failures MUST NOT propagate — catch and log, never block the caller
- All async methods MUST return typed `Promise<T>` — never use `any` return types
