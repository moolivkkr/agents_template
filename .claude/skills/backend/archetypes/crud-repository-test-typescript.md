---
skill: crud-repository-test-typescript
description: TypeScript repository integration test archetype — Prisma test DB, Drizzle test DB, testcontainers, transaction isolation, CRUD operations, pagination, soft delete, tenant isolation, optimistic locking, error mapping
version: "1.0"
tags:
  - typescript
  - repository
  - integration-test
  - prisma
  - drizzle
  - postgres
  - testcontainers
  - archetype
  - backend
  - testing
---

# CRUD Repository Test Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-repository-test.md` (Go). Both validate identical data access patterns: cursor pagination, soft delete, tenant isolation, optimistic locking, and error mapping against a real PostgreSQL database.

Complete integration test template for Prisma and Drizzle repositories. Every generated TypeScript repository test MUST follow this pattern.

---

# Prisma Section

## Test File Location

```
src/repositories/
  prisma-widget.repository.ts        <- production code
  prisma-widget.repository.test.ts   <- THIS file (integration tests)
```

## Test Infrastructure — Prisma + Test Database

```typescript
// src/repositories/prisma-widget.repository.test.ts

import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { PrismaClient } from "@prisma/client";
import { execSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { PrismaWidgetRepository } from "./prisma-widget.repository";
import type { Widget } from "../domain/entity";
import type { ListFilters } from "../types/pagination";
import {
  NotFoundError,
  ConflictError,
} from "../errors/domain-errors";

/**
 * Test database setup.
 *
 * Option A: Use TEST_DATABASE_URL env var pointing to a local/CI Postgres.
 * Option B: Use testcontainers (see testcontainers setup below).
 *
 * The test database is created fresh for each test run via `prisma migrate deploy`.
 */
let prisma: PrismaClient;
let repo: PrismaWidgetRepository;

beforeAll(async () => {
  // Use test database URL — CI sets this; locally, use docker-compose
  const testUrl = process.env.TEST_DATABASE_URL
    ?? "postgresql://test:test@localhost:5433/testdb?schema=public";

  // Run migrations against the test database
  execSync("npx prisma migrate deploy", {
    env: { ...process.env, DATABASE_URL: testUrl },
    stdio: "pipe",
  });

  prisma = new PrismaClient({
    datasources: { db: { url: testUrl } },
  });

  await prisma.$connect();
  repo = new PrismaWidgetRepository(prisma);
});

afterAll(async () => {
  await prisma.$disconnect();
});

// Clean up widgets table before each test for isolation
beforeEach(async () => {
  await prisma.widget.deleteMany({});
});
```

## Testcontainers Setup (Alternative)

```typescript
// src/test-utils/test-database.ts

import { PostgreSqlContainer, type StartedPostgreSqlContainer } from "@testcontainers/postgresql";
import { PrismaClient } from "@prisma/client";
import { execSync } from "node:child_process";

let container: StartedPostgreSqlContainer;
let prisma: PrismaClient;

/**
 * Starts a PostgreSQL container and runs Prisma migrations.
 * Call from beforeAll in your test suite.
 */
export async function setupTestDatabase(): Promise<{
  prisma: PrismaClient;
  connectionUrl: string;
}> {
  container = await new PostgreSqlContainer("postgres:16-alpine")
    .withDatabase("testdb")
    .withUsername("test")
    .withPassword("test")
    .start();

  const connectionUrl = container.getConnectionUri();

  // Run Prisma migrations
  execSync("npx prisma migrate deploy", {
    env: { ...process.env, DATABASE_URL: connectionUrl },
    stdio: "pipe",
  });

  prisma = new PrismaClient({
    datasources: { db: { url: connectionUrl } },
  });

  await prisma.$connect();
  return { prisma, connectionUrl };
}

/**
 * Tears down the test database and container.
 * Call from afterAll in your test suite.
 */
export async function teardownTestDatabase(): Promise<void> {
  await prisma.$disconnect();
  await container.stop();
}
```

## Test Factory

```typescript
/** Builds a test widget with sensible defaults for DB insertion. */
function makeWidget(overrides: Partial<Widget> = {}): Widget {
  const now = new Date();
  return {
    id: randomUUID(),
    tenantId: randomUUID(),
    name: `widget-${randomUUID().slice(0, 8)}`,
    description: "Test widget description",
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

/** Seeds multiple widgets into the test database. */
async function seedWidgets(...widgets: Widget[]): Promise<void> {
  for (const w of widgets) {
    await repo.create(w);
  }
}
```

## CRUD Tests with Real Database

```typescript
describe("PrismaWidgetRepository — CRUD", () => {
  it("create inserts and returns widget with all fields", async () => {
    const w = makeWidget();
    const created = await repo.create(w);

    expect(created.id).toBe(w.id);
    expect(created.tenantId).toBe(w.tenantId);
    expect(created.name).toBe(w.name);
    expect(created.description).toBe(w.description);
    expect(created.version).toBe(1);
    expect(created.deletedAt).toBeNull();

    // Verify it was persisted
    const found = await repo.findById(w.tenantId, w.id);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(w.id);
  });

  it("findById returns widget for matching tenant", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const found = await repo.findById(w.tenantId, w.id);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(w.id);
    expect(found!.name).toBe(w.name);
  });

  it("findById returns null when not found", async () => {
    const result = await repo.findById(randomUUID(), randomUUID());
    expect(result).toBeNull();
  });

  it("findByName returns widget for matching tenant + name", async () => {
    const w = makeWidget({ name: "unique-test-name" });
    await seedWidgets(w);

    const found = await repo.findByName(w.tenantId, "unique-test-name");
    expect(found).not.toBeNull();
    expect(found!.id).toBe(w.id);
  });

  it("findByName returns null for non-matching tenant", async () => {
    const w = makeWidget({ name: "tenant-specific" });
    await seedWidgets(w);

    const found = await repo.findByName(randomUUID(), "tenant-specific");
    expect(found).toBeNull();
  });

  it("update persists changes and increments version", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const updated: Widget = {
      ...w,
      name: "Updated Name",
      description: "Updated description",
      updatedAt: new Date(),
      version: 2, // increment
    };

    const result = await repo.update(updated);
    expect(result.name).toBe("Updated Name");
    expect(result.version).toBe(2);

    // Verify persisted
    const found = await repo.findById(w.tenantId, w.id);
    expect(found!.name).toBe("Updated Name");
    expect(found!.version).toBe(2);
  });

  it("softDelete sets deletedAt — record excluded from findById", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    await repo.softDelete(w.tenantId, w.id);

    // findById should NOT find it (filtered by deletedAt IS NULL)
    const found = await repo.findById(w.tenantId, w.id);
    expect(found).toBeNull();

    // But the raw row still exists with deletedAt set
    const raw = await prisma.widget.findUnique({ where: { id: w.id } });
    expect(raw).not.toBeNull();
    expect(raw!.deletedAt).not.toBeNull();
  });

  it("softDelete throws NotFoundError for non-existent widget", async () => {
    await expect(
      repo.softDelete(randomUUID(), randomUUID()),
    ).rejects.toThrow(NotFoundError);
  });
});
```

## Pagination Tests

```typescript
describe("PrismaWidgetRepository — Pagination", () => {
  it("cursor pagination returns correct pages with no duplicates", async () => {
    const tenantId = randomUUID();
    const baseTime = new Date("2026-01-15T10:00:00Z");

    // Insert 25 widgets with staggered creation times
    for (let i = 0; i < 25; i++) {
      const w = makeWidget({
        tenantId,
        name: `widget-${String(i).padStart(3, "0")}`,
        createdAt: new Date(baseTime.getTime() + i * 1000),
      });
      await repo.create(w);
    }

    // Page 1: fetch first 20
    const page1 = await repo.list(tenantId, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(page1.items).toHaveLength(20);
    expect(page1.hasMore).toBe(true);
    expect(page1.cursor).toBeTruthy();
    expect(page1.total).toBe(25);

    // Page 2: fetch remaining using cursor
    const page2 = await repo.list(tenantId, {
      cursor: page1.cursor,
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(page2.items).toHaveLength(5);
    expect(page2.hasMore).toBe(false);

    // Verify no duplicates between pages
    const page1Ids = new Set(page1.items.map((w) => w.id));
    for (const w of page2.items) {
      expect(page1Ids.has(w.id)).toBe(false);
    }
  });

  it("empty result returns zero items", async () => {
    const result = await repo.list(randomUUID(), {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(result.items).toHaveLength(0);
    expect(result.hasMore).toBe(false);
    expect(result.cursor).toBe("");
    expect(result.total).toBe(0);
  });

  it("sort order is respected — ascending and descending", async () => {
    const tenantId = randomUUID();
    const baseTime = new Date("2026-01-15T10:00:00Z");

    const w1 = makeWidget({ tenantId, name: "alpha", createdAt: baseTime });
    const w2 = makeWidget({
      tenantId,
      name: "bravo",
      createdAt: new Date(baseTime.getTime() + 1000),
    });
    const w3 = makeWidget({
      tenantId,
      name: "charlie",
      createdAt: new Date(baseTime.getTime() + 2000),
    });
    await seedWidgets(w1, w2, w3);

    // Ascending
    const asc = await repo.list(tenantId, {
      cursor: "",
      pageSize: 10,
      sortBy: "created_at",
      sortDir: "asc",
      fields: {},
    });
    expect(asc.items[0].id).toBe(w1.id);
    expect(asc.items[2].id).toBe(w3.id);

    // Descending
    const desc = await repo.list(tenantId, {
      cursor: "",
      pageSize: 10,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });
    expect(desc.items[0].id).toBe(w3.id);
    expect(desc.items[2].id).toBe(w1.id);
  });

  it("offset pagination returns correct page with total", async () => {
    const tenantId = randomUUID();
    for (let i = 0; i < 15; i++) {
      await repo.create(
        makeWidget({ tenantId, name: `widget-${String(i).padStart(3, "0")}` }),
      );
    }

    const result = await repo.listOffset(tenantId, {
      page: 2,
      perPage: 5,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(result.items).toHaveLength(5);
    expect(result.total).toBe(15);
  });
});
```

## Tenant Isolation Tests

```typescript
describe("PrismaWidgetRepository — Tenant Isolation", () => {
  it("findById — tenant B cannot see tenant A's widget", async () => {
    const tenantA = randomUUID();
    const tenantB = randomUUID();
    const w = makeWidget({ tenantId: tenantA });
    await seedWidgets(w);

    // Tenant A sees their widget
    const foundA = await repo.findById(tenantA, w.id);
    expect(foundA).not.toBeNull();

    // Tenant B does NOT see it
    const foundB = await repo.findById(tenantB, w.id);
    expect(foundB).toBeNull();
  });

  it("list — each tenant sees only their own widgets", async () => {
    const tenantA = randomUUID();
    const tenantB = randomUUID();

    for (let i = 0; i < 3; i++) {
      await repo.create(makeWidget({ tenantId: tenantA, name: `a-${i}` }));
    }
    for (let i = 0; i < 2; i++) {
      await repo.create(makeWidget({ tenantId: tenantB, name: `b-${i}` }));
    }

    const filters: ListFilters = {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    };

    const resultA = await repo.list(tenantA, filters);
    expect(resultA.items).toHaveLength(3);
    expect(resultA.total).toBe(3);
    for (const w of resultA.items) {
      expect(w.tenantId).toBe(tenantA);
    }

    const resultB = await repo.list(tenantB, filters);
    expect(resultB.items).toHaveLength(2);
    expect(resultB.total).toBe(2);
    for (const w of resultB.items) {
      expect(w.tenantId).toBe(tenantB);
    }
  });

  it("update — wrong tenant causes version/tenant mismatch", async () => {
    const tenantA = randomUUID();
    const tenantB = randomUUID();
    const w = makeWidget({ tenantId: tenantA });
    await seedWidgets(w);

    // Attempt update with wrong tenant
    const tampered: Widget = {
      ...w,
      tenantId: tenantB,
      name: "hijacked",
      version: 2,
    };

    await expect(repo.update(tampered)).rejects.toThrow();
  });

  it("softDelete — tenant B cannot delete tenant A's widget", async () => {
    const tenantA = randomUUID();
    const tenantB = randomUUID();
    const w = makeWidget({ tenantId: tenantA });
    await seedWidgets(w);

    // Tenant B cannot delete
    await expect(repo.softDelete(tenantB, w.id)).rejects.toThrow(NotFoundError);

    // Widget still exists for tenant A
    const found = await repo.findById(tenantA, w.id);
    expect(found).not.toBeNull();
  });
});
```

## Optimistic Locking Tests

```typescript
describe("PrismaWidgetRepository — Optimistic Locking", () => {
  it("concurrent update — second write fails with ConflictError", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    // Simulate two concurrent reads
    const read1 = await repo.findById(w.tenantId, w.id);
    const read2 = await repo.findById(w.tenantId, w.id);

    // First update succeeds (version 1 -> 2)
    const update1: Widget = {
      ...read1!,
      name: "Update A",
      version: 2,
      updatedAt: new Date(),
    };
    await repo.update(update1);

    // Second update fails — version already incremented
    const update2: Widget = {
      ...read2!,
      name: "Update B",
      version: 2, // expects version 1, but it's now 2
      updatedAt: new Date(),
    };
    await expect(repo.update(update2)).rejects.toThrow(ConflictError);

    // Verify first update persisted
    const final = await repo.findById(w.tenantId, w.id);
    expect(final!.name).toBe("Update A");
    expect(final!.version).toBe(2);
  });

  it("stale version number is rejected", async () => {
    const w = makeWidget({ version: 5 });
    await repo.create(w);

    const stale: Widget = {
      ...w,
      name: "Stale Update",
      version: 3, // far behind actual version 5
      updatedAt: new Date(),
    };
    await expect(repo.update(stale)).rejects.toThrow(ConflictError);
  });
});
```

## Soft Delete Tests

```typescript
describe("PrismaWidgetRepository — Soft Delete", () => {
  it("soft-deleted widgets excluded from list results", async () => {
    const tenantId = randomUUID();
    const visible = makeWidget({ tenantId, name: "visible" });
    const deleted = makeWidget({ tenantId, name: "deleted" });
    await seedWidgets(visible, deleted);

    await repo.softDelete(tenantId, deleted.id);

    const result = await repo.list(tenantId, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(result.items).toHaveLength(1);
    expect(result.items[0].id).toBe(visible.id);
  });

  it("soft-deleted widget still exists in raw DB", async () => {
    const w = makeWidget();
    await seedWidgets(w);
    await repo.softDelete(w.tenantId, w.id);

    const raw = await prisma.widget.findUnique({ where: { id: w.id } });
    expect(raw).not.toBeNull();
    expect(raw!.deletedAt).not.toBeNull();
  });
});
```

## Filter Tests

```typescript
describe("PrismaWidgetRepository — Filters", () => {
  it("filters by status field", async () => {
    const tenantId = randomUUID();
    await seedWidgets(
      makeWidget({ tenantId, name: "active-1", status: "active" }),
      makeWidget({ tenantId, name: "active-2", status: "active" }),
      makeWidget({ tenantId, name: "archived-1", status: "archived" }),
    );

    const result = await repo.list(tenantId, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: { status: "active" },
    });

    expect(result.items).toHaveLength(2);
    for (const w of result.items) {
      expect(w.status).toBe("active");
    }
  });
});
```

## Error Mapping Tests

```typescript
describe("PrismaWidgetRepository — Error Mapping", () => {
  it("duplicate name within tenant returns ConflictError", async () => {
    const tenantId = randomUUID();
    const w1 = makeWidget({ tenantId, name: "unique-name" });
    await seedWidgets(w1);

    const w2 = makeWidget({ tenantId, name: "unique-name" });
    await expect(repo.create(w2)).rejects.toThrow(ConflictError);
  });

  it("duplicate primary key returns ConflictError", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const dup = makeWidget({ id: w.id, tenantId: w.tenantId, name: "different" });
    await expect(repo.create(dup)).rejects.toThrow(ConflictError);
  });

  it("update non-existent widget returns ConflictError (zero rows)", async () => {
    const w = makeWidget({ version: 2 });
    await expect(repo.update(w)).rejects.toThrow(ConflictError);
  });
});
```

---

# Drizzle Section

## Test File Location

```
src/repositories/
  drizzle-widget.repository.ts        <- production code
  drizzle-widget.repository.test.ts   <- THIS file (integration tests)
```

## Test Infrastructure — Drizzle + Test Database

```typescript
// src/repositories/drizzle-widget.repository.test.ts

import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import postgres from "postgres";
import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import { sql } from "drizzle-orm";
import { randomUUID } from "node:crypto";
import * as schema from "../db/schema";
import { DrizzleWidgetRepository } from "./drizzle-widget.repository";
import type { Widget } from "../domain/entity";
import type { ListFilters } from "../types/pagination";
import {
  NotFoundError,
  ConflictError,
} from "../errors/domain-errors";

let client: ReturnType<typeof postgres>;
let db: PostgresJsDatabase;
let repo: DrizzleWidgetRepository;

beforeAll(async () => {
  const testUrl = process.env.TEST_DATABASE_URL
    ?? "postgresql://test:test@localhost:5433/testdb";

  client = postgres(testUrl, { max: 5 });
  db = drizzle(client, { schema });

  // Run Drizzle migrations
  await migrate(db, { migrationsFolder: "./drizzle" });

  repo = new DrizzleWidgetRepository(db);
});

afterAll(async () => {
  await client.end();
});

// Clean up before each test
beforeEach(async () => {
  await db.delete(schema.widgets);
});
```

## Drizzle Test Factory

```typescript
function makeWidget(overrides: Partial<Widget> = {}): Widget {
  const now = new Date();
  return {
    id: randomUUID(),
    tenantId: randomUUID(),
    name: `widget-${randomUUID().slice(0, 8)}`,
    description: "Test widget",
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

async function seedWidgets(...widgets: Widget[]): Promise<void> {
  for (const w of widgets) {
    await repo.create(w);
  }
}
```

## Drizzle CRUD Tests

```typescript
describe("DrizzleWidgetRepository — CRUD", () => {
  it("create inserts and returns widget", async () => {
    const w = makeWidget();
    const created = await repo.create(w);

    expect(created.id).toBe(w.id);
    expect(created.name).toBe(w.name);
    expect(created.version).toBe(1);
  });

  it("findById returns widget for matching tenant", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const found = await repo.findById(w.tenantId, w.id);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(w.id);
  });

  it("findById returns null for wrong tenant", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const found = await repo.findById(randomUUID(), w.id);
    expect(found).toBeNull();
  });

  it("update with optimistic lock persists changes", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const updated: Widget = {
      ...w,
      name: "Updated via Drizzle",
      version: 2,
      updatedAt: new Date(),
    };

    const result = await repo.update(updated);
    expect(result.name).toBe("Updated via Drizzle");
    expect(result.version).toBe(2);
  });

  it("softDelete marks widget as deleted", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    await repo.softDelete(w.tenantId, w.id);

    const found = await repo.findById(w.tenantId, w.id);
    expect(found).toBeNull(); // excluded by soft delete filter
  });
});
```

## Drizzle Pagination Tests

```typescript
describe("DrizzleWidgetRepository — Pagination", () => {
  it("cursor pagination pages through all results", async () => {
    const tenantId = randomUUID();
    for (let i = 0; i < 15; i++) {
      await repo.create(
        makeWidget({
          tenantId,
          name: `drizzle-${String(i).padStart(3, "0")}`,
          createdAt: new Date(Date.now() + i * 1000),
        }),
      );
    }

    const page1 = await repo.list(tenantId, {
      cursor: "",
      pageSize: 10,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(page1.items).toHaveLength(10);
    expect(page1.hasMore).toBe(true);
    expect(page1.total).toBe(15);

    const page2 = await repo.list(tenantId, {
      cursor: page1.cursor,
      pageSize: 10,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(page2.items).toHaveLength(5);
    expect(page2.hasMore).toBe(false);

    // No duplicates
    const page1Ids = new Set(page1.items.map((w) => w.id));
    for (const w of page2.items) {
      expect(page1Ids.has(w.id)).toBe(false);
    }
  });
});
```

## Drizzle Transaction Rollback for Isolation

```typescript
describe("DrizzleWidgetRepository — Transaction Rollback", () => {
  it("transaction rollback undoes all changes", async () => {
    const tenantId = randomUUID();
    const w1 = makeWidget({ tenantId, name: "committed" });
    await seedWidgets(w1);

    // Attempt a transaction that fails midway
    try {
      await db.transaction(async (tx) => {
        const txRepo = new DrizzleWidgetRepository(tx as any);
        await txRepo.create(makeWidget({ tenantId, name: "will-rollback" }));

        // Force rollback
        throw new Error("simulated failure");
      });
    } catch {
      // Expected
    }

    // Only the committed widget should exist
    const result = await repo.list(tenantId, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(result.items).toHaveLength(1);
    expect(result.items[0].name).toBe("committed");
  });

  it("successful transaction persists all changes", async () => {
    const tenantId = randomUUID();

    await db.transaction(async (tx) => {
      const txRepo = new DrizzleWidgetRepository(tx as any);
      await txRepo.create(makeWidget({ tenantId, name: "tx-widget-1" }));
      await txRepo.create(makeWidget({ tenantId, name: "tx-widget-2" }));
    });

    const result = await repo.list(tenantId, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });

    expect(result.items).toHaveLength(2);
  });
});
```

## Drizzle Tenant Isolation Tests

```typescript
describe("DrizzleWidgetRepository — Tenant Isolation", () => {
  it("each tenant sees only their own data", async () => {
    const tenantA = randomUUID();
    const tenantB = randomUUID();

    await seedWidgets(
      makeWidget({ tenantId: tenantA, name: "a-1" }),
      makeWidget({ tenantId: tenantA, name: "a-2" }),
      makeWidget({ tenantId: tenantB, name: "b-1" }),
    );

    const resultA = await repo.list(tenantA, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });
    expect(resultA.items).toHaveLength(2);
    expect(resultA.total).toBe(2);

    const resultB = await repo.list(tenantB, {
      cursor: "",
      pageSize: 20,
      sortBy: "created_at",
      sortDir: "desc",
      fields: {},
    });
    expect(resultB.items).toHaveLength(1);
    expect(resultB.total).toBe(1);
  });
});
```

## Drizzle Error Mapping Tests

```typescript
describe("DrizzleWidgetRepository — Error Mapping", () => {
  it("unique constraint violation returns ConflictError", async () => {
    const tenantId = randomUUID();
    const w1 = makeWidget({ tenantId, name: "dup-name" });
    await seedWidgets(w1);

    const w2 = makeWidget({ tenantId, name: "dup-name" });
    await expect(repo.create(w2)).rejects.toThrow(ConflictError);
  });

  it("optimistic lock conflict returns ConflictError", async () => {
    const w = makeWidget();
    await seedWidgets(w);

    const stale: Widget = {
      ...w,
      name: "Stale",
      version: 99, // wrong version
      updatedAt: new Date(),
    };
    await expect(repo.update(stale)).rejects.toThrow(ConflictError);
  });
});
```

---

## Docker Compose for Test Database

```yaml
# docker-compose.test.yml — run with: docker compose -f docker-compose.test.yml up -d

services:
  test-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: testdb
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data  # RAM-backed for speed
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 2s
      timeout: 5s
      retries: 10
```

---

## Critical Rules

- Repository integration tests MUST run against a real PostgreSQL database — never mock the DB
- Use `testcontainers` for CI or `docker-compose.test.yml` for local development
- Every test MUST clean up data in `beforeEach` (truncate or delete) for isolation
- Test factories MUST generate unique names/IDs with `randomUUID()` to prevent constraint collisions
- Pagination tests MUST verify: item count, hasMore flag, cursor presence, no duplicates between pages
- Tenant isolation tests MUST verify: findById returns null, list returns empty, update fails, delete fails for wrong tenant
- Optimistic locking tests MUST simulate two concurrent reads and verify second update fails with ConflictError
- Soft delete tests MUST verify: record excluded from queries but raw row exists with deletedAt set
- Error mapping tests MUST verify: unique violation -> ConflictError, zero rows -> ConflictError/NotFoundError
- Never use `test.concurrent` for integration tests sharing the same database — sequential execution prevents flakes
- Test database MUST be disposable — never run integration tests against production or staging databases
- Prisma tests use `deleteMany({})` for cleanup; Drizzle tests use `db.delete(schema.widgets)`
- Transaction rollback tests MUST verify that failed transactions leave the database unchanged
