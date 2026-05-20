---
skill: crud-service-test-typescript
description: TypeScript service layer unit test archetype — vitest, mocked repository/cache/audit, table-driven tests, cache-aside verification, optimistic locking, tenant isolation, Prisma + Drizzle mock patterns
version: "1.0"
tags:
  - typescript
  - service
  - unit-test
  - vitest
  - archetype
  - backend
  - testing
---

# CRUD Service Test Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-service-test.md` (Go). Both verify identical business logic patterns: cache-aside, optimistic locking, audit logging, and tenant isolation.

Complete unit test template for the service layer using vitest. Every generated TypeScript service test MUST follow this pattern.

---

## Test File Location

```
src/services/
  widget.service.ts           <- production code
  widget.service.test.ts      <- THIS file
```

Rule: Test file lives next to production code with `.test.ts` suffix.

---

## Test Factory Pattern

```typescript
// src/test-utils/widget.factory.ts

import { randomUUID } from "node:crypto";
import type { Widget } from "../domain/entity";
import type { CreateWidgetInput, UpdateWidgetInput } from "../services/widget.service.interface";
import type { ListFilters } from "../types/pagination";

/** Builds a test widget with sensible defaults. Override with partial. */
export function makeWidget(overrides: Partial<Widget> = {}): Widget {
  const now = new Date();
  return {
    id: randomUUID(),
    tenantId: randomUUID(),
    name: `widget-${randomUUID().slice(0, 8)}`,
    description: "A test widget",
    status: "active",
    createdAt: now,
    updatedAt: now,
    deletedAt: null,
    createdBy: randomUUID(),
    updatedBy: randomUUID(),
    version: 1,
    ...overrides,
  };
}

/** Builds a valid CreateWidgetInput with defaults. */
export function makeCreateInput(overrides: Partial<CreateWidgetInput> = {}): CreateWidgetInput {
  return {
    name: "New Widget",
    description: "Description for new widget",
    ...overrides,
  };
}

/** Builds a valid UpdateWidgetInput with defaults. */
export function makeUpdateInput(
  version: number,
  overrides: Partial<Omit<UpdateWidgetInput, "version">> = {},
): UpdateWidgetInput {
  return {
    name: "Updated Widget",
    description: "Updated description",
    version,
    ...overrides,
  };
}

/** Builds default list filters. */
export function makeListFilters(overrides: Partial<ListFilters> = {}): ListFilters {
  return {
    cursor: "",
    pageSize: 20,
    sortBy: "created_at",
    sortDir: "desc",
    fields: {},
    ...overrides,
  };
}
```

---

## Mock Definitions

```typescript
// src/services/__mocks__/widget.mocks.ts

import { vi } from "vitest";
import type { IWidgetRepository } from "../../repositories/widget.repository.interface";
import type { ICache } from "../../lib/cache.interface";
import type { IAuditWriter } from "../../lib/audit.interface";
import type { Logger } from "../../lib/logger";

/** Creates a fully typed mock repository with vi.fn() for every method. */
export function createMockRepository(): {
  [K in keyof IWidgetRepository]: ReturnType<typeof vi.fn>;
} {
  return {
    create: vi.fn(),
    findById: vi.fn(),
    findByName: vi.fn(),
    update: vi.fn(),
    softDelete: vi.fn(),
    list: vi.fn(),
    listOffset: vi.fn(),
  };
}

/** Creates a fully typed mock cache. */
export function createMockCache(): {
  [K in keyof ICache]: ReturnType<typeof vi.fn>;
} {
  return {
    get: vi.fn(),
    set: vi.fn(),
    delete: vi.fn(),
  };
}

/** Creates a mock audit writer that captures entries. */
export function createMockAuditWriter(): {
  write: ReturnType<typeof vi.fn>;
  entries: Array<{ action: string; entityId: string; tenantId: string }>;
} {
  const entries: Array<{ action: string; entityId: string; tenantId: string }> = [];
  return {
    write: vi.fn().mockImplementation(async (entry) => {
      entries.push(entry);
    }),
    entries,
  };
}

/** Creates a no-op logger for tests — suppresses output. */
export function createMockLogger(): Logger {
  return {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };
}
```

---

## Service Unit Tests — Suite Pattern

```typescript
// src/services/widget.service.test.ts

import { describe, it, expect, beforeEach, vi } from "vitest";
import { WidgetService } from "./widget.service";
import {
  createMockRepository,
  createMockCache,
  createMockAuditWriter,
  createMockLogger,
} from "./__mocks__/widget.mocks";
import { makeWidget, makeCreateInput, makeUpdateInput, makeListFilters } from "../test-utils/widget.factory";
import {
  ValidationError,
  NotFoundError,
  ConflictError,
} from "../errors/domain-errors";
import type { ListResult } from "../types/pagination";
import type { Widget } from "../domain/entity";

describe("WidgetService", () => {
  let svc: WidgetService;
  let repo: ReturnType<typeof createMockRepository>;
  let cache: ReturnType<typeof createMockCache>;
  let audit: ReturnType<typeof createMockAuditWriter>;
  let logger: ReturnType<typeof createMockLogger>;

  const tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
  const userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";

  beforeEach(() => {
    // Fresh mocks for every test — no cross-test contamination
    repo = createMockRepository();
    cache = createMockCache();
    audit = createMockAuditWriter();
    logger = createMockLogger();

    svc = new WidgetService(repo as any, cache as any, audit as any, logger);
  });

  // =========================================================================
  // Create Tests
  // =========================================================================

  describe("create", () => {
    it("creates widget with correct fields and version 1", async () => {
      const input = makeCreateInput();

      repo.findByName.mockResolvedValueOnce(null); // no duplicate
      repo.create.mockImplementationOnce(async (w: Widget) => w); // return same widget

      const result = await svc.create(tenantId, userId, input);

      expect(result.name).toBe(input.name);
      expect(result.tenantId).toBe(tenantId);
      expect(result.createdBy).toBe(userId);
      expect(result.version).toBe(1);
      expect(result.id).toBeDefined();
      expect(result.deletedAt).toBeNull();

      // Verify repo was called
      expect(repo.create).toHaveBeenCalledOnce();
      expect(repo.findByName).toHaveBeenCalledWith(tenantId, input.name);
    });

    it("throws ValidationError for empty name", async () => {
      const input = makeCreateInput({ name: "" });

      await expect(svc.create(tenantId, userId, input)).rejects.toThrow(
        ValidationError,
      );

      // Repo should NOT be called when validation fails
      expect(repo.create).not.toHaveBeenCalled();
      expect(repo.findByName).not.toHaveBeenCalled();
    });

    it("throws ValidationError for name exceeding 255 characters", async () => {
      const input = makeCreateInput({ name: "x".repeat(256) });

      await expect(svc.create(tenantId, userId, input)).rejects.toThrow(
        ValidationError,
      );

      expect(repo.create).not.toHaveBeenCalled();
    });

    it("throws ConflictError when duplicate name exists within tenant", async () => {
      const input = makeCreateInput({ name: "Existing Widget" });
      repo.findByName.mockResolvedValueOnce(makeWidget({ name: "Existing Widget" }));

      await expect(svc.create(tenantId, userId, input)).rejects.toThrow(
        ConflictError,
      );

      expect(repo.create).not.toHaveBeenCalled();
    });

    it("propagates repository errors with context", async () => {
      const input = makeCreateInput();
      repo.findByName.mockResolvedValueOnce(null);
      repo.create.mockRejectedValueOnce(new Error("connection refused"));

      await expect(svc.create(tenantId, userId, input)).rejects.toThrow(
        /connection refused/,
      );
    });

    it("fires audit log on successful create (fire-and-forget)", async () => {
      const input = makeCreateInput();
      repo.findByName.mockResolvedValueOnce(null);
      repo.create.mockImplementationOnce(async (w: Widget) => w);

      const result = await svc.create(tenantId, userId, input);

      // Allow microtask to settle (audit is fire-and-forget)
      await vi.waitFor(() => {
        expect(audit.write).toHaveBeenCalledOnce();
      });

      expect(audit.write).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "widget.created",
          tenantId,
          entityId: result.id,
        }),
      );
    });
  });

  // =========================================================================
  // Get Tests — Cache-Aside Pattern
  // =========================================================================

  describe("get", () => {
    it("returns cached widget on cache hit — does NOT query DB", async () => {
      const widget = makeWidget({ tenantId });
      cache.get.mockResolvedValueOnce(widget);

      const result = await svc.get(tenantId, widget.id);

      expect(result.id).toBe(widget.id);
      expect(repo.findById).not.toHaveBeenCalled(); // DB never queried
      expect(cache.get).toHaveBeenCalledWith(`widget:${tenantId}:${widget.id}`);
    });

    it("queries DB on cache miss and populates cache", async () => {
      const widget = makeWidget({ tenantId });
      const cacheKey = `widget:${tenantId}:${widget.id}`;

      cache.get.mockResolvedValueOnce(null); // cache miss
      repo.findById.mockResolvedValueOnce(widget);
      cache.set.mockResolvedValueOnce(undefined);

      const result = await svc.get(tenantId, widget.id);

      expect(result.id).toBe(widget.id);
      expect(repo.findById).toHaveBeenCalledWith(tenantId, widget.id);
      expect(cache.set).toHaveBeenCalledWith(
        cacheKey,
        widget,
        expect.any(Number), // TTL
      );
    });

    it("throws NotFoundError when widget does not exist", async () => {
      cache.get.mockResolvedValueOnce(null);
      repo.findById.mockResolvedValueOnce(null);

      await expect(svc.get(tenantId, "nonexistent-id")).rejects.toThrow(
        NotFoundError,
      );
    });

    it("cache set failure does NOT propagate — logs warning instead", async () => {
      const widget = makeWidget({ tenantId });
      cache.get.mockResolvedValueOnce(null);
      repo.findById.mockResolvedValueOnce(widget);
      cache.set.mockRejectedValueOnce(new Error("Redis connection lost"));

      // Should NOT throw despite cache failure
      const result = await svc.get(tenantId, widget.id);
      expect(result.id).toBe(widget.id);

      // Warning should be logged
      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("cache"),
        expect.any(Object),
      );
    });
  });

  // =========================================================================
  // Update Tests — Optimistic Locking
  // =========================================================================

  describe("update", () => {
    it("updates widget and increments version", async () => {
      const existing = makeWidget({ tenantId, version: 1 });
      const input = makeUpdateInput(1); // matches existing.version

      repo.findById.mockResolvedValueOnce(existing);
      repo.update.mockImplementationOnce(async (w: Widget) => w);
      cache.delete.mockResolvedValueOnce(undefined);

      const result = await svc.update(tenantId, existing.id, input);

      expect(result.name).toBe(input.name);
      expect(result.version).toBe(2); // incremented
      expect(repo.update).toHaveBeenCalledWith(
        expect.objectContaining({ version: 2 }),
      );
    });

    it("throws ConflictError on version mismatch (optimistic lock)", async () => {
      const existing = makeWidget({ tenantId, version: 3 });
      const input = makeUpdateInput(1); // stale version

      repo.findById.mockResolvedValueOnce(existing);

      await expect(
        svc.update(tenantId, existing.id, input),
      ).rejects.toThrow(ConflictError);

      // Repo.update should NOT be called
      expect(repo.update).not.toHaveBeenCalled();
    });

    it("throws NotFoundError when widget does not exist", async () => {
      repo.findById.mockResolvedValueOnce(null);

      await expect(
        svc.update(tenantId, "nonexistent", makeUpdateInput(1)),
      ).rejects.toThrow(NotFoundError);

      expect(repo.update).not.toHaveBeenCalled();
    });

    it("invalidates cache after successful update", async () => {
      const existing = makeWidget({ tenantId, version: 1 });
      const cacheKey = `widget:${tenantId}:${existing.id}`;

      repo.findById.mockResolvedValueOnce(existing);
      repo.update.mockImplementationOnce(async (w: Widget) => w);
      cache.delete.mockResolvedValueOnce(undefined);

      await svc.update(tenantId, existing.id, makeUpdateInput(1));

      expect(cache.delete).toHaveBeenCalledWith(cacheKey);
    });

    it("cache invalidation failure does NOT propagate", async () => {
      const existing = makeWidget({ tenantId, version: 1 });

      repo.findById.mockResolvedValueOnce(existing);
      repo.update.mockImplementationOnce(async (w: Widget) => w);
      cache.delete.mockRejectedValueOnce(new Error("Redis down"));

      // Should NOT throw despite cache failure
      const result = await svc.update(tenantId, existing.id, makeUpdateInput(1));
      expect(result).toBeDefined();
    });

    it("throws ValidationError for empty name", async () => {
      await expect(
        svc.update(tenantId, "some-id", makeUpdateInput(1, { name: "" })),
      ).rejects.toThrow(ValidationError);

      expect(repo.findById).not.toHaveBeenCalled();
    });

    it("throws ValidationError for missing version", async () => {
      await expect(
        svc.update(tenantId, "some-id", {
          name: "Valid",
          description: "desc",
          version: -1,
        }),
      ).rejects.toThrow(ValidationError);

      expect(repo.findById).not.toHaveBeenCalled();
    });

    it("fires audit log on successful update", async () => {
      const existing = makeWidget({ tenantId, version: 1 });
      repo.findById.mockResolvedValueOnce(existing);
      repo.update.mockImplementationOnce(async (w: Widget) => w);
      cache.delete.mockResolvedValueOnce(undefined);

      await svc.update(tenantId, existing.id, makeUpdateInput(1));

      await vi.waitFor(() => {
        expect(audit.write).toHaveBeenCalledWith(
          expect.objectContaining({
            action: "widget.updated",
            entityId: existing.id,
            tenantId,
          }),
        );
      });
    });
  });

  // =========================================================================
  // Delete Tests
  // =========================================================================

  describe("delete", () => {
    it("soft deletes widget and invalidates cache", async () => {
      const widgetId = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa";
      const cacheKey = `widget:${tenantId}:${widgetId}`;

      repo.softDelete.mockResolvedValueOnce(undefined);
      cache.delete.mockResolvedValueOnce(undefined);

      await svc.delete(tenantId, widgetId);

      expect(repo.softDelete).toHaveBeenCalledWith(tenantId, widgetId);
      expect(cache.delete).toHaveBeenCalledWith(cacheKey);
    });

    it("propagates NotFoundError from repository", async () => {
      repo.softDelete.mockRejectedValueOnce(
        new NotFoundError("widget", "nonexistent"),
      );

      await expect(svc.delete(tenantId, "nonexistent")).rejects.toThrow(
        NotFoundError,
      );
    });

    it("fires audit log on successful delete", async () => {
      const widgetId = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa";
      repo.softDelete.mockResolvedValueOnce(undefined);
      cache.delete.mockResolvedValueOnce(undefined);

      await svc.delete(tenantId, widgetId);

      await vi.waitFor(() => {
        expect(audit.write).toHaveBeenCalledWith(
          expect.objectContaining({
            action: "widget.deleted",
            entityId: widgetId,
            tenantId,
          }),
        );
      });
    });
  });

  // =========================================================================
  // List Tests
  // =========================================================================

  describe("list", () => {
    it("returns paginated results from repository", async () => {
      const widgets = [makeWidget({ tenantId }), makeWidget({ tenantId })];
      const listResult: ListResult<Widget> = {
        items: widgets,
        cursor: "next-cursor",
        hasMore: true,
        total: 25,
      };

      repo.list.mockResolvedValueOnce(listResult);

      const result = await svc.list(tenantId, makeListFilters());

      expect(result.items).toHaveLength(2);
      expect(result.hasMore).toBe(true);
      expect(result.total).toBe(25);
      expect(result.cursor).toBe("next-cursor");
    });

    it("clamps pageSize to 100 when exceeding max", async () => {
      repo.list.mockResolvedValueOnce({
        items: [],
        cursor: "",
        hasMore: false,
        total: 0,
      });

      await svc.list(tenantId, makeListFilters({ pageSize: 500 }));

      expect(repo.list).toHaveBeenCalledWith(
        tenantId,
        expect.objectContaining({ pageSize: 100 }),
      );
    });

    it("defaults pageSize to 20 when zero or missing", async () => {
      repo.list.mockResolvedValueOnce({
        items: [],
        cursor: "",
        hasMore: false,
        total: 0,
      });

      await svc.list(tenantId, makeListFilters({ pageSize: 0 }));

      expect(repo.list).toHaveBeenCalledWith(
        tenantId,
        expect.objectContaining({ pageSize: 20 }),
      );
    });

    it("returns empty list without error", async () => {
      repo.list.mockResolvedValueOnce({
        items: [],
        cursor: "",
        hasMore: false,
        total: 0,
      });

      const result = await svc.list(tenantId, makeListFilters());

      expect(result.items).toHaveLength(0);
      expect(result.total).toBe(0);
    });

    it("propagates repository error", async () => {
      repo.list.mockRejectedValueOnce(new Error("timeout"));

      await expect(
        svc.list(tenantId, makeListFilters()),
      ).rejects.toThrow(/timeout/);
    });
  });
});
```

---

## Table-Driven Test Pattern

```typescript
// src/services/widget.service.table-driven.test.ts

import { describe, it, expect, vi } from "vitest";
import { WidgetService } from "./widget.service";
import {
  createMockRepository,
  createMockCache,
  createMockAuditWriter,
  createMockLogger,
} from "./__mocks__/widget.mocks";
import { makeCreateInput } from "../test-utils/widget.factory";
import {
  ValidationError,
  ConflictError,
} from "../errors/domain-errors";
import type { Widget } from "../domain/entity";

describe("WidgetService.create — table-driven", () => {
  const tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
  const userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";

  const testCases = [
    {
      name: "valid input creates widget with version 1",
      input: makeCreateInput(),
      setupMocks: (repo: any, cache: any, audit: any) => {
        repo.findByName.mockResolvedValueOnce(null);
        repo.create.mockImplementationOnce(async (w: Widget) => w);
        audit.write.mockResolvedValueOnce(undefined);
      },
      assertResult: (result: Widget | null, error: unknown) => {
        expect(error).toBeUndefined();
        expect(result).not.toBeNull();
        expect(result!.name).toBe("New Widget");
        expect(result!.version).toBe(1);
      },
    },
    {
      name: "empty name returns ValidationError",
      input: makeCreateInput({ name: "" }),
      setupMocks: () => { /* no mock setup — validation fails before calls */ },
      assertResult: (_result: Widget | null, error: unknown) => {
        expect(error).toBeInstanceOf(ValidationError);
      },
    },
    {
      name: "name > 255 chars returns ValidationError",
      input: makeCreateInput({ name: "x".repeat(256) }),
      setupMocks: () => {},
      assertResult: (_result: Widget | null, error: unknown) => {
        expect(error).toBeInstanceOf(ValidationError);
      },
    },
    {
      name: "repo error propagates",
      input: makeCreateInput(),
      setupMocks: (repo: any) => {
        repo.findByName.mockResolvedValueOnce(null);
        repo.create.mockRejectedValueOnce(new Error("db down"));
      },
      assertResult: (_result: Widget | null, error: unknown) => {
        expect(error).toBeInstanceOf(Error);
        expect((error as Error).message).toContain("db down");
      },
    },
  ];

  for (const tc of testCases) {
    it(tc.name, async () => {
      const repo = createMockRepository();
      const cache = createMockCache();
      const audit = createMockAuditWriter();
      const logger = createMockLogger();
      const svc = new WidgetService(repo as any, cache as any, audit as any, logger);

      tc.setupMocks(repo, cache, audit);

      let result: Widget | null = null;
      let error: unknown;

      try {
        result = await svc.create(tenantId, userId, tc.input);
      } catch (err) {
        error = err;
      }

      tc.assertResult(result, error);
    });
  }
});
```

---

## Prisma Mock Pattern

```typescript
// Pattern for mocking Prisma Client in service tests

import { vi } from "vitest";
import { PrismaClient } from "@prisma/client";
import { mockDeep, mockReset, type DeepMockProxy } from "vitest-mock-extended";

// Create a deeply mocked Prisma client
export const prismaMock = mockDeep<PrismaClient>();

// Reset between tests
beforeEach(() => {
  mockReset(prismaMock);
});

// Usage in test:
// prismaMock.widget.findFirst.mockResolvedValueOnce(makeWidgetRecord());
// prismaMock.widget.create.mockResolvedValueOnce(makeWidgetRecord());
// prismaMock.$transaction.mockImplementation(async (fn) => fn(prismaMock));

/**
 * Mock Prisma transaction — executes callback with the mock client.
 */
function mockTransaction() {
  prismaMock.$transaction.mockImplementation(async (fn: any) => {
    if (typeof fn === "function") {
      return fn(prismaMock);
    }
    // Array form: execute each promise
    return Promise.all(fn);
  });
}

// Example test using Prisma mock:
it("creates widget within transaction", async () => {
  mockTransaction();
  prismaMock.widget.create.mockResolvedValueOnce({
    id: "test-id",
    tenantId: "tenant-1",
    name: "Widget",
    description: "",
    status: "active",
    createdAt: new Date(),
    updatedAt: new Date(),
    deletedAt: null,
    createdBy: "user-1",
    updatedBy: "user-1",
    version: 1,
  });

  // ... test service method that uses prisma.$transaction
});
```

---

## Drizzle Mock Pattern

```typescript
// Pattern for mocking Drizzle ORM in service tests

import { vi } from "vitest";
import type { PostgresJsDatabase } from "drizzle-orm/postgres-js";

/**
 * Creates a mock Drizzle database client.
 * Chain methods return `this` for fluent API.
 */
export function createMockDrizzle() {
  const mockQuery = {
    select: vi.fn().mockReturnThis(),
    from: vi.fn().mockReturnThis(),
    where: vi.fn().mockReturnThis(),
    orderBy: vi.fn().mockReturnThis(),
    limit: vi.fn().mockReturnThis(),
    offset: vi.fn().mockReturnThis(),
    returning: vi.fn().mockResolvedValue([]),
    then: vi.fn(),
  };

  const db = {
    select: vi.fn(() => mockQuery),
    insert: vi.fn(() => ({
      values: vi.fn(() => ({
        returning: vi.fn().mockResolvedValue([]),
        onConflictDoNothing: vi.fn().mockReturnThis(),
        onConflictDoUpdate: vi.fn().mockReturnThis(),
      })),
    })),
    update: vi.fn(() => ({
      set: vi.fn(() => ({
        where: vi.fn(() => ({
          returning: vi.fn().mockResolvedValue([]),
        })),
      })),
    })),
    delete: vi.fn(() => ({
      where: vi.fn(() => ({
        returning: vi.fn().mockResolvedValue([]),
      })),
    })),
    transaction: vi.fn(async (fn: (tx: any) => Promise<any>) => {
      // Execute callback with the same mock for transaction
      return fn(db);
    }),
    _mockQuery: mockQuery, // exposed for assertion access
  };

  return db as unknown as PostgresJsDatabase & { _mockQuery: typeof mockQuery };
}

// Example test using Drizzle mock:
it("creates widget via Drizzle insert", async () => {
  const db = createMockDrizzle();
  const widget = makeWidget();

  (db.insert as any).mockReturnValue({
    values: vi.fn().mockReturnValue({
      returning: vi.fn().mockResolvedValue([widget]),
    }),
  });

  // ... test repository method
});
```

---

## Edge Case and Isolation Tests

```typescript
describe("Edge cases and isolation", () => {
  let svc: WidgetService;
  let repo: ReturnType<typeof createMockRepository>;
  let cache: ReturnType<typeof createMockCache>;
  let audit: ReturnType<typeof createMockAuditWriter>;
  let logger: ReturnType<typeof createMockLogger>;

  const tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
  const userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";

  beforeEach(() => {
    repo = createMockRepository();
    cache = createMockCache();
    audit = createMockAuditWriter();
    logger = createMockLogger();
    svc = new WidgetService(repo as any, cache as any, audit as any, logger);
  });

  it("zero-value input (empty object) throws ValidationError", async () => {
    await expect(
      svc.create(tenantId, userId, { name: "", description: "" }),
    ).rejects.toThrow(ValidationError);

    expect(repo.create).not.toHaveBeenCalled();
  });

  it("whitespace-only name throws ValidationError", async () => {
    await expect(
      svc.create(tenantId, userId, { name: "   ", description: "desc" }),
    ).rejects.toThrow(ValidationError);

    expect(repo.create).not.toHaveBeenCalled();
  });

  it("description exceeding 2000 chars throws ValidationError", async () => {
    await expect(
      svc.create(tenantId, userId, {
        name: "Valid",
        description: "x".repeat(2001),
      }),
    ).rejects.toThrow(ValidationError);
  });

  it("audit writer failure does NOT propagate to caller", async () => {
    const input = makeCreateInput();
    repo.findByName.mockResolvedValueOnce(null);
    repo.create.mockImplementationOnce(async (w: Widget) => w);
    audit.write.mockRejectedValueOnce(new Error("audit service down"));

    // Should NOT throw despite audit failure
    const result = await svc.create(tenantId, userId, input);
    expect(result).toBeDefined();
    expect(result.name).toBe(input.name);
  });

  it("concurrent version conflict — second update fails", async () => {
    const existing = makeWidget({ tenantId, version: 1 });

    // Simulate two reads
    repo.findById.mockResolvedValueOnce(existing);
    repo.update.mockImplementationOnce(async (w: Widget) => w);
    cache.delete.mockResolvedValue(undefined);

    // First update succeeds (version 1 -> 2)
    await svc.update(tenantId, existing.id, makeUpdateInput(1));

    // Second update with stale version fails
    repo.findById.mockResolvedValueOnce({ ...existing, version: 2 }); // re-read shows v2

    await expect(
      svc.update(tenantId, existing.id, makeUpdateInput(1)), // still sending v1
    ).rejects.toThrow(ConflictError);
  });

  it("list enforces minimum pageSize of 1", async () => {
    repo.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await svc.list(tenantId, makeListFilters({ pageSize: -5 }));

    expect(repo.list).toHaveBeenCalledWith(
      tenantId,
      expect.objectContaining({ pageSize: expect.any(Number) }),
    );
    const actualPageSize = (repo.list.mock.calls[0]?.[1] as any).pageSize;
    expect(actualPageSize).toBeGreaterThanOrEqual(1);
  });

  it("list defaults sortBy to 'created_at' when empty", async () => {
    repo.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await svc.list(tenantId, makeListFilters({ sortBy: "" }));

    expect(repo.list).toHaveBeenCalledWith(
      tenantId,
      expect.objectContaining({ sortBy: "created_at" }),
    );
  });

  it("list defaults sortDir to 'desc' when empty", async () => {
    repo.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await svc.list(tenantId, makeListFilters({ sortDir: "" as any }));

    expect(repo.list).toHaveBeenCalledWith(
      tenantId,
      expect.objectContaining({ sortDir: "desc" }),
    );
  });
});
```

---

## Audit Logging Verification

```typescript
describe("Audit logging", () => {
  let svc: WidgetService;
  let repo: ReturnType<typeof createMockRepository>;
  let cache: ReturnType<typeof createMockCache>;
  let audit: ReturnType<typeof createMockAuditWriter>;

  const tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
  const userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";

  beforeEach(() => {
    repo = createMockRepository();
    cache = createMockCache();
    audit = createMockAuditWriter();
    const logger = createMockLogger();
    svc = new WidgetService(repo as any, cache as any, audit as any, logger);
  });

  it("create logs widget.created with correct fields", async () => {
    repo.findByName.mockResolvedValueOnce(null);
    repo.create.mockImplementationOnce(async (w: Widget) => w);

    const result = await svc.create(tenantId, userId, makeCreateInput());

    await vi.waitFor(() => {
      expect(audit.write).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "widget.created",
          tenantId,
          entityId: result.id,
          timestamp: expect.any(Date),
        }),
      );
    });
  });

  it("update logs widget.updated with entity id and tenant", async () => {
    const existing = makeWidget({ tenantId, version: 1 });
    repo.findById.mockResolvedValueOnce(existing);
    repo.update.mockImplementationOnce(async (w: Widget) => w);
    cache.delete.mockResolvedValueOnce(undefined);

    await svc.update(tenantId, existing.id, makeUpdateInput(1));

    await vi.waitFor(() => {
      expect(audit.write).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "widget.updated",
          entityId: existing.id,
          tenantId,
        }),
      );
    });
  });

  it("delete logs widget.deleted with entity id", async () => {
    const widgetId = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa";
    repo.softDelete.mockResolvedValueOnce(undefined);
    cache.delete.mockResolvedValueOnce(undefined);

    await svc.delete(tenantId, widgetId);

    await vi.waitFor(() => {
      expect(audit.write).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "widget.deleted",
          entityId: widgetId,
        }),
      );
    });
  });
});
```

---

## Critical Rules

- Every test MUST use fresh mocks via `beforeEach` — no shared mock state between tests
- Mocks MUST be typed: use `ReturnType<typeof createMockRepository>` for full type safety
- `vi.fn()` MUST be used for all mock methods — enables `toHaveBeenCalledWith` assertions
- Cache tests MUST verify both hit and miss paths
- Cache failures MUST NOT propagate — verify with `mockRejectedValueOnce` + expect no throw
- Audit failures MUST NOT propagate — verify with `mockRejectedValueOnce` + expect no throw
- Audit tests MUST verify action, entityId, tenantId, and timestamp
- Version conflict test: set existing.version = 3, input.version = 1 — assert ConflictError
- Validation tests MUST verify that repo methods are NOT called when input is invalid
- Use `expect.objectContaining()` for partial matching of complex objects
- Use `vi.waitFor()` to assert on fire-and-forget audit calls
- Table-driven tests MUST use `for...of` loop (not `it.each`) for better TypeScript inference
- Prisma mocks use `vitest-mock-extended` with `mockDeep<PrismaClient>()`
- Drizzle mocks create a chainable query builder with `vi.fn().mockReturnThis()`
- Every test MUST be independent — no shared state or execution order dependencies
