---
skill: crud-handler-test-typescript
description: TypeScript HTTP handler test archetype — Express (vitest + supertest) and NestJS (jest + supertest) patterns, Zod validation tests, auth tests, error mapping, pagination, response envelope assertions
version: "1.0"
tags:
  - typescript
  - handler
  - http
  - unit-test
  - express
  - nestjs
  - vitest
  - jest
  - archetype
  - backend
  - testing
---

# CRUD Handler Test Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-handler-test.md` (Go). Both validate identical response envelopes, error codes, and pagination behavior.

Complete HTTP handler test template for Express (vitest + supertest) and NestJS (jest + supertest). Every generated TypeScript handler test MUST follow this pattern.

---

# Express Section (vitest + supertest)

## Test File Location

```
src/routes/
  widget.routes.ts           <- production code
  widget.routes.test.ts      <- THIS file
```

Rule: Test file lives next to production code with `.test.ts` suffix.

## Service Mock

```typescript
// src/routes/__mocks__/widget.service.mock.ts

import { vi } from "vitest";
import type { IWidgetService } from "../../services/widget.service.interface";
import type { Widget } from "../../domain/entity";
import type { ListResult, OffsetListResult } from "../../types/pagination";

/**
 * Creates a fully typed mock of the widget service.
 * Every method is a vi.fn() — configure return values per test.
 */
export function createMockWidgetService(): {
  [K in keyof IWidgetService]: ReturnType<typeof vi.fn>;
} {
  return {
    create: vi.fn<IWidgetService["create"]>(),
    get: vi.fn<IWidgetService["get"]>(),
    update: vi.fn<IWidgetService["update"]>(),
    delete: vi.fn<IWidgetService["delete"]>(),
    list: vi.fn<IWidgetService["list"]>(),
    listOffset: vi.fn<IWidgetService["listOffset"]>(),
  };
}
```

## Test App Setup

```typescript
// src/routes/widget.routes.test.ts

import { describe, it, expect, beforeEach, vi } from "vitest";
import express from "express";
import request from "supertest";
import { createWidgetRouter } from "./widget.routes";
import { createMockWidgetService } from "./__mocks__/widget.service.mock";
import { errorHandler } from "../middleware/error-handler";
import type { AuthenticatedRequest } from "../types/express";
import type { Widget } from "../domain/entity";
import type { ListResult } from "../types/pagination";

/** Factory: builds a test widget with sensible defaults. */
function makeWidget(overrides: Partial<Widget> = {}): Widget {
  return {
    id: "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
    tenantId: "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
    name: "Test Widget",
    description: "A test widget",
    status: "active",
    createdAt: new Date("2026-01-15T10:00:00Z"),
    updatedAt: new Date("2026-01-15T10:00:00Z"),
    deletedAt: null,
    createdBy: "cccccccc-cccc-4ccc-cccc-cccccccccccc",
    updatedBy: "cccccccc-cccc-4ccc-cccc-cccccccccccc",
    version: 1,
    ...overrides,
  };
}

/**
 * Creates an Express app with mocked auth middleware and widget routes.
 * Auth middleware injects userId, tenantId, requestId into the request.
 */
function createTestApp(svc: ReturnType<typeof createMockWidgetService>) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  // Mock auth middleware — injects default tenant/user context
  app.use((req, _res, next) => {
    const authReq = req as AuthenticatedRequest;
    authReq.userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";
    authReq.tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
    authReq.roles = ["user"];
    authReq.requestId = "test-request-id";
    next();
  });

  app.use("/api/v1/widgets", createWidgetRouter(svc as any));

  // Error handler MUST be last
  app.use(errorHandler);

  return app;
}

/**
 * Creates an Express app WITHOUT auth middleware — for testing missing auth.
 */
function createTestAppNoAuth(svc: ReturnType<typeof createMockWidgetService>) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));
  app.use("/api/v1/widgets", createWidgetRouter(svc as any));
  app.use(errorHandler);
  return app;
}
```

## Create Handler Tests

```typescript
describe("POST /api/v1/widgets", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 201 with created widget in envelope", async () => {
    const created = makeWidget({ name: "New Widget" });
    svc.create.mockResolvedValueOnce(created);

    const res = await request(app)
      .post("/api/v1/widgets")
      .send({ name: "New Widget", description: "A fine widget" })
      .expect("Content-Type", /json/)
      .expect(201);

    // Assert envelope structure: { data: {...}, meta: {...} }
    expect(res.body).toHaveProperty("data");
    expect(res.body).toHaveProperty("meta");
    expect(res.body.data.name).toBe("New Widget");
    expect(res.body.meta.request_id).toBe("test-request-id");
    expect(res.body.meta.timestamp).toBeDefined();

    // Verify service was called with correct tenant and input
    expect(svc.create).toHaveBeenCalledWith(
      "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
      "cccccccc-cccc-4ccc-cccc-cccccccccccc",
      expect.objectContaining({ name: "New Widget" }),
    );
  });

  it("returns 400 for malformed JSON", async () => {
    const res = await request(app)
      .post("/api/v1/widgets")
      .set("Content-Type", "application/json")
      .send("{invalid json")
      .expect(400);

    expect(res.body.error.code).toBe("BAD_REQUEST");
    expect(svc.create).not.toHaveBeenCalled();
  });

  it("returns 400 for empty body", async () => {
    const res = await request(app)
      .post("/api/v1/widgets")
      .send({})
      .expect(400);

    expect(res.body.error).toBeDefined();
    expect(svc.create).not.toHaveBeenCalled();
  });

  it("returns 422 for Zod validation failure — missing name", async () => {
    const res = await request(app)
      .post("/api/v1/widgets")
      .send({ description: "no name provided" })
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(res.body.error.message).toBeDefined();
    expect(svc.create).not.toHaveBeenCalled();
  });

  it("returns 422 for Zod validation failure — name too long", async () => {
    const res = await request(app)
      .post("/api/v1/widgets")
      .send({ name: "x".repeat(256), description: "ok" })
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(svc.create).not.toHaveBeenCalled();
  });

  it("returns 409 when service throws ConflictError (duplicate name)", async () => {
    const { ConflictError } = await import("../errors/domain-errors");
    svc.create.mockRejectedValueOnce(
      new ConflictError("widget", "name 'Existing' already exists"),
    );

    const res = await request(app)
      .post("/api/v1/widgets")
      .send({ name: "Existing", description: "dup" })
      .expect(409);

    expect(res.body.error.code).toBe("CONFLICT");
  });
});
```

## Get Handler Tests

```typescript
describe("GET /api/v1/widgets/:id", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 200 with widget in envelope", async () => {
    const widget = makeWidget();
    svc.get.mockResolvedValueOnce(widget);

    const res = await request(app)
      .get(`/api/v1/widgets/${widget.id}`)
      .expect("Content-Type", /json/)
      .expect(200);

    expect(res.body.data.id).toBe(widget.id);
    expect(res.body.meta.request_id).toBe("test-request-id");
    expect(res.body.meta.timestamp).toBeDefined();

    // Verify only "data" and "meta" keys exist
    expect(Object.keys(res.body)).toEqual(["data", "meta"]);
  });

  it("returns 422 for invalid UUID format", async () => {
    const res = await request(app)
      .get("/api/v1/widgets/not-a-uuid")
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(svc.get).not.toHaveBeenCalled();
  });

  it("returns 404 when widget not found", async () => {
    const { NotFoundError } = await import("../errors/domain-errors");
    svc.get.mockRejectedValueOnce(
      new NotFoundError("widget", "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"),
    );

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(404);

    expect(res.body.error.code).toBe("NOT_FOUND");
    expect(res.body.error.message).toBeDefined();
  });

  it("returns 500 with generic message for internal errors — no detail leak", async () => {
    svc.get.mockRejectedValueOnce(
      new Error("database connection pool exhausted"),
    );

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(500);

    expect(res.body.error.code).toBe("INTERNAL_ERROR");
    // CRITICAL: must NOT leak internal error details
    expect(res.body.error.message).not.toContain("database connection pool");
    expect(res.body.error.message).not.toContain("exhausted");
  });
});
```

## Update Handler Tests

```typescript
describe("PUT /api/v1/widgets/:id", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 200 with updated widget — version incremented", async () => {
    const updated = makeWidget({ name: "Updated Name", version: 2 });
    svc.update.mockResolvedValueOnce(updated);

    const res = await request(app)
      .put(`/api/v1/widgets/${updated.id}`)
      .send({ name: "Updated Name", description: "Updated desc", version: 1 })
      .expect(200);

    expect(res.body.data.name).toBe("Updated Name");
    expect(res.body.data.version).toBe(2);
    expect(res.body.meta.request_id).toBeDefined();
  });

  it("returns 409 on version conflict", async () => {
    const { ConflictError } = await import("../errors/domain-errors");
    svc.update.mockRejectedValueOnce(
      new ConflictError("widget", "version mismatch"),
    );

    const res = await request(app)
      .put("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .send({ name: "Updated", description: "desc", version: 1 })
      .expect(409);

    expect(res.body.error.code).toBe("CONFLICT");
  });

  it("returns 400 for malformed JSON body", async () => {
    const res = await request(app)
      .put("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .set("Content-Type", "application/json")
      .send("{bad")
      .expect(400);

    expect(res.body.error.code).toBe("BAD_REQUEST");
    expect(svc.update).not.toHaveBeenCalled();
  });

  it("returns 422 for missing version field", async () => {
    const res = await request(app)
      .put("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .send({ name: "Updated", description: "desc" }) // missing version
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(svc.update).not.toHaveBeenCalled();
  });

  it("returns 422 for invalid UUID in path", async () => {
    const res = await request(app)
      .put("/api/v1/widgets/xyz")
      .send({ name: "Updated", description: "desc", version: 1 })
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(svc.update).not.toHaveBeenCalled();
  });
});
```

## Delete Handler Tests

```typescript
describe("DELETE /api/v1/widgets/:id", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 204 No Content with empty body", async () => {
    svc.delete.mockResolvedValueOnce(undefined);

    const res = await request(app)
      .delete("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(204);

    // DELETE MUST return empty body
    expect(res.body).toEqual({});
    expect(res.text).toBe("");

    expect(svc.delete).toHaveBeenCalledWith(
      "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
      "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
    );
  });

  it("returns 404 when widget not found", async () => {
    const { NotFoundError } = await import("../errors/domain-errors");
    svc.delete.mockRejectedValueOnce(
      new NotFoundError("widget", "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"),
    );

    const res = await request(app)
      .delete("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(404);

    expect(res.body.error.code).toBe("NOT_FOUND");
  });

  it("returns 422 for invalid UUID", async () => {
    const res = await request(app)
      .delete("/api/v1/widgets/xyz")
      .expect(422);

    expect(res.body.error.code).toBe("VALIDATION_ERROR");
    expect(svc.delete).not.toHaveBeenCalled();
  });
});
```

## List Handler with Cursor Pagination Tests

```typescript
describe("GET /api/v1/widgets (cursor pagination)", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 200 with paginated list in envelope", async () => {
    const widgets = [makeWidget(), makeWidget({ id: "dddddddd-dddd-4ddd-dddd-dddddddddddd" })];
    svc.list.mockResolvedValueOnce({
      items: widgets,
      cursor: "next-cursor-token",
      hasMore: true,
      total: 25,
    } satisfies ListResult<Widget>);

    const res = await request(app)
      .get("/api/v1/widgets?page_size=2&sort_by=created_at&sort_dir=desc")
      .expect(200);

    // Assert data array
    expect(res.body.data).toHaveLength(2);

    // Assert pagination meta
    expect(res.body.meta.cursor).toBe("next-cursor-token");
    expect(res.body.meta.has_more).toBe(true);
    expect(res.body.meta.total).toBe(25);
    expect(res.body.meta.request_id).toBe("test-request-id");
    expect(res.body.meta.timestamp).toBeDefined();
  });

  it("returns empty array for no results", async () => {
    svc.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    const res = await request(app)
      .get("/api/v1/widgets")
      .expect(200);

    expect(res.body.data).toHaveLength(0);
    expect(res.body.meta.has_more).toBe(false);
    expect(res.body.meta.total).toBe(0);
  });

  it("passes cursor to service for next page", async () => {
    svc.list.mockResolvedValueOnce({
      items: [makeWidget()],
      cursor: "",
      hasMore: false,
      total: 25,
    });

    await request(app)
      .get("/api/v1/widgets?cursor=some-cursor-token&page_size=10")
      .expect(200);

    expect(svc.list).toHaveBeenCalledWith(
      "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
      expect.objectContaining({
        cursor: "some-cursor-token",
        pageSize: 10,
      }),
    );
  });

  it("clamps page_size to defaults and maximums", async () => {
    const testCases = [
      { query: "", expectedPageSize: 20 },       // default when missing
      { query: "page_size=0", expectedPageSize: 1 },  // min 1 from Zod
      { query: "page_size=500", expectedPageSize: 100 }, // clamped to max
      { query: "page_size=50", expectedPageSize: 50 },   // respected
    ];

    for (const { query, expectedPageSize } of testCases) {
      svc.list.mockResolvedValueOnce({
        items: [],
        cursor: "",
        hasMore: false,
        total: 0,
      });

      const url = query
        ? `/api/v1/widgets?${query}`
        : "/api/v1/widgets";

      await request(app).get(url).expect(200);

      expect(svc.list).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ pageSize: expectedPageSize }),
      );

      svc.list.mockClear();
    }
  });

  it("parses filter[field] query params — allowed fields only", async () => {
    svc.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await request(app)
      .get("/api/v1/widgets?filter[status]=active&filter[priority]=high")
      .expect(200);

    expect(svc.list).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        fields: expect.objectContaining({ status: "active", priority: "high" }),
      }),
    );
  });

  it("ignores disallowed filter fields", async () => {
    svc.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await request(app)
      .get("/api/v1/widgets?filter[password]=secret")
      .expect(200);

    const callArgs = svc.list.mock.calls[0]?.[1];
    expect(callArgs?.fields).not.toHaveProperty("password");
  });

  it("defaults sort params to safe values for invalid input", async () => {
    svc.list.mockResolvedValueOnce({
      items: [],
      cursor: "",
      hasMore: false,
      total: 0,
    });

    await request(app)
      .get("/api/v1/widgets?sort_by=drop_table&sort_dir=invalid")
      .expect(200);

    expect(svc.list).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        sortBy: "created_at",
        sortDir: "desc",
      }),
    );
  });
});
```

## Offset Pagination Tests

```typescript
describe("GET /api/v1/widgets/admin (offset pagination)", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("returns 200 with offset-paginated list and page links", async () => {
    svc.listOffset.mockResolvedValueOnce({
      items: [makeWidget()],
      total: 50,
    });

    const res = await request(app)
      .get("/api/v1/widgets/admin?page=2&per_page=10")
      .expect(200);

    expect(res.body.data).toHaveLength(1);
    expect(res.body.meta.page).toBe(2);
    expect(res.body.meta.per_page).toBe(10);
    expect(res.body.meta.total).toBe(50);
    expect(res.body.meta.total_pages).toBe(5);
    expect(res.body.links).toBeDefined();
    expect(res.body.links.self).toContain("page=2");
    expect(res.body.links.first).toContain("page=1");
    expect(res.body.links.last).toContain("page=5");
    expect(res.body.links.next).toContain("page=3");
    expect(res.body.links.prev).toContain("page=1");
  });

  it("omits next link on last page", async () => {
    svc.listOffset.mockResolvedValueOnce({ items: [], total: 10 });

    const res = await request(app)
      .get("/api/v1/widgets/admin?page=1&per_page=20")
      .expect(200);

    expect(res.body.links.next).toBeUndefined();
  });

  it("omits prev link on first page", async () => {
    svc.listOffset.mockResolvedValueOnce({ items: [], total: 10 });

    const res = await request(app)
      .get("/api/v1/widgets/admin?page=1&per_page=10")
      .expect(200);

    expect(res.body.links.prev).toBeUndefined();
  });
});
```

## Error Mapping Tests (Table-Driven)

```typescript
describe("Error mapping — service errors to HTTP status codes", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  const errorCases = [
    {
      name: "NotFoundError maps to 404",
      errorFactory: async () => {
        const { NotFoundError } = await import("../errors/domain-errors");
        return new NotFoundError("widget", "123");
      },
      wantStatus: 404,
      wantCode: "NOT_FOUND",
    },
    {
      name: "ConflictError maps to 409",
      errorFactory: async () => {
        const { ConflictError } = await import("../errors/domain-errors");
        return new ConflictError("widget", "version mismatch");
      },
      wantStatus: 409,
      wantCode: "CONFLICT",
    },
    {
      name: "ValidationError maps to 422",
      errorFactory: async () => {
        const { ValidationError } = await import("../errors/domain-errors");
        return new ValidationError("name", "required");
      },
      wantStatus: 422,
      wantCode: "VALIDATION_ERROR",
    },
    {
      name: "Unknown error maps to 500 with generic message",
      errorFactory: async () => new Error("unexpected: pool exhausted"),
      wantStatus: 500,
      wantCode: "INTERNAL_ERROR",
    },
  ];

  for (const tc of errorCases) {
    it(tc.name, async () => {
      const err = await tc.errorFactory();
      svc.get.mockRejectedValueOnce(err);

      const res = await request(app)
        .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        .expect(tc.wantStatus);

      expect(res.body.error.code).toBe(tc.wantCode);
      expect(res.body.error.message).toBeDefined();

      // CRITICAL: 500 errors must NOT leak details
      if (tc.wantStatus === 500) {
        expect(res.body.error.message).not.toContain("pool exhausted");
        expect(res.body.error.message).not.toContain("unexpected");
      }
    });
  }
});
```

## Auth Tests (Express)

```typescript
describe("Auth — Express middleware tests", () => {
  it("returns 401 when auth middleware is missing (no tenantId)", async () => {
    const svc = createMockWidgetService();
    const app = createTestAppNoAuth(svc);

    // Without auth middleware, tenantId is undefined
    // Service should receive undefined tenantId and reject
    svc.get.mockRejectedValueOnce(
      new (await import("../errors/domain-errors")).UnauthorizedError(
        "missing authentication",
      ),
    );

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(401);

    expect(res.body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 for invalid JWT token", async () => {
    const svc = createMockWidgetService();
    // App with real auth middleware that rejects bad tokens
    const app = express();
    app.use(express.json());

    // Simulated auth middleware that validates JWT
    app.use((req, _res, next) => {
      const token = req.headers.authorization?.replace("Bearer ", "");
      if (!token || token === "invalid-token") {
        const err = new Error("invalid token");
        (err as any).statusCode = 401;
        (err as any).code = "UNAUTHORIZED";
        return next(err);
      }
      next();
    });

    app.use("/api/v1/widgets", createWidgetRouter(svc as any));
    app.use(errorHandler);

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .set("Authorization", "Bearer invalid-token")
      .expect(401);

    expect(res.body.error.code).toBe("UNAUTHORIZED");
    expect(svc.get).not.toHaveBeenCalled();
  });

  it("wrong tenant sees 404, not 403 — prevents entity enumeration", async () => {
    const svc = createMockWidgetService();
    const app = createTestApp(svc);

    // Service returns NotFound (not Forbidden) for wrong tenant
    const { NotFoundError } = await import("../errors/domain-errors");
    svc.get.mockRejectedValueOnce(
      new NotFoundError("widget", "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"),
    );

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(404);

    // CRITICAL: wrong tenant sees 404, not 403
    expect(res.body.error.code).toBe("NOT_FOUND");
  });

  it("returns 403 for insufficient role", async () => {
    const svc = createMockWidgetService();
    const app = express();
    app.use(express.json());

    // Auth middleware that injects viewer role
    app.use((req, _res, next) => {
      const authReq = req as AuthenticatedRequest;
      authReq.userId = "cccccccc-cccc-4ccc-cccc-cccccccccccc";
      authReq.tenantId = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb";
      authReq.roles = ["viewer"]; // viewer cannot create
      authReq.requestId = "test-req";
      next();
    });

    // Role guard middleware for write operations
    app.use("/api/v1/widgets", (req, _res, next) => {
      const authReq = req as AuthenticatedRequest;
      if (req.method === "POST" && !authReq.roles.includes("user")) {
        const err = new Error("insufficient permissions");
        (err as any).statusCode = 403;
        (err as any).code = "FORBIDDEN";
        return next(err);
      }
      next();
    });

    app.use("/api/v1/widgets", createWidgetRouter(svc as any));
    app.use(errorHandler);

    const res = await request(app)
      .post("/api/v1/widgets")
      .send({ name: "New Widget", description: "desc" })
      .expect(403);

    expect(res.body.error.code).toBe("FORBIDDEN");
    expect(svc.create).not.toHaveBeenCalled();
  });
});
```

## Response Shape Tests

```typescript
describe("Response shape validation", () => {
  let svc: ReturnType<typeof createMockWidgetService>;
  let app: express.Application;

  beforeEach(() => {
    svc = createMockWidgetService();
    app = createTestApp(svc);
  });

  it("single resource response has exactly data + meta keys", async () => {
    svc.get.mockResolvedValueOnce(makeWidget());

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(200);

    expect(Object.keys(res.body).sort()).toEqual(["data", "meta"]);

    // data must contain expected fields
    expect(res.body.data).toHaveProperty("id");
    expect(res.body.data).toHaveProperty("tenant_id");
    expect(res.body.data).toHaveProperty("name");
    expect(res.body.data).toHaveProperty("version");
    expect(res.body.data).toHaveProperty("created_at");
    expect(res.body.data).toHaveProperty("updated_at");

    // meta must contain tracking fields
    expect(res.body.meta).toHaveProperty("request_id");
    expect(res.body.meta).toHaveProperty("timestamp");
  });

  it("list response has data array + meta with pagination", async () => {
    svc.list.mockResolvedValueOnce({
      items: [makeWidget()],
      cursor: "abc",
      hasMore: true,
      total: 10,
    });

    const res = await request(app)
      .get("/api/v1/widgets")
      .expect(200);

    expect(Array.isArray(res.body.data)).toBe(true);
    expect(res.body.meta).toHaveProperty("cursor");
    expect(res.body.meta).toHaveProperty("has_more");
    expect(res.body.meta).toHaveProperty("total");
    expect(res.body.meta).toHaveProperty("request_id");
    expect(res.body.meta).toHaveProperty("timestamp");
  });

  it("error response has error object with code and message", async () => {
    const { NotFoundError } = await import("../errors/domain-errors");
    svc.get.mockRejectedValueOnce(new NotFoundError("widget", "123"));

    const res = await request(app)
      .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
      .expect(404);

    expect(res.body).toHaveProperty("error");
    expect(res.body.error).toHaveProperty("code");
    expect(res.body.error).toHaveProperty("message");
  });
});
```

---

# NestJS Section (jest + supertest)

## Test File Location

```
src/modules/widget/
  widget.controller.ts        <- production code
  widget.controller.spec.ts   <- THIS file (NestJS convention)
```

## NestJS Controller Tests

```typescript
// src/modules/widget/widget.controller.spec.ts

import { Test, TestingModule } from "@nestjs/testing";
import { INestApplication, ValidationPipe, HttpStatus } from "@nestjs/common";
import * as request from "supertest";
import { WidgetController } from "./widget.controller";
import { WidgetService } from "./widget.service";
import { JwtAuthGuard } from "../../guards/jwt-auth.guard";
import type { Widget } from "../../domain/widget";

/** Factory: builds a test widget with defaults. */
function makeWidget(overrides: Partial<Widget> = {}): Widget {
  return {
    id: "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
    tenantId: "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
    name: "Test Widget",
    description: "A test widget",
    status: "active",
    createdAt: new Date("2026-01-15T10:00:00Z"),
    updatedAt: new Date("2026-01-15T10:00:00Z"),
    deletedAt: null,
    createdBy: "cccccccc-cccc-4ccc-cccc-cccccccccccc",
    updatedBy: "cccccccc-cccc-4ccc-cccc-cccccccccccc",
    version: 1,
    ...overrides,
  };
}

describe("WidgetController (e2e)", () => {
  let app: INestApplication;
  let widgetService: jest.Mocked<Partial<WidgetService>>;

  beforeEach(async () => {
    // Create mock service
    widgetService = {
      create: jest.fn(),
      get: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
      list: jest.fn(),
      listOffset: jest.fn(),
    };

    const module: TestingModule = await Test.createTestingModule({
      controllers: [WidgetController],
      providers: [
        { provide: WidgetService, useValue: widgetService },
      ],
    })
      // Override the auth guard to inject a mock user
      .overrideGuard(JwtAuthGuard)
      .useValue({
        canActivate: (context: any) => {
          const req = context.switchToHttp().getRequest();
          req.user = {
            id: "cccccccc-cccc-4ccc-cccc-cccccccccccc",
            tenantId: "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
            roles: ["user"],
          };
          req.headers["x-request-id"] = "test-request-id";
          return true;
        },
      })
      .compile();

    app = module.createNestApplication();

    // Apply the same ValidationPipe as production
    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        transform: true,
        forbidNonWhitelisted: true,
      }),
    );

    await app.init();
  });

  afterEach(async () => {
    await app.close();
  });

  // --- Create ---

  describe("POST /api/v1/widgets", () => {
    it("returns 201 with created widget", async () => {
      const created = makeWidget({ name: "New Widget" });
      (widgetService.create as jest.Mock).mockResolvedValueOnce(created);

      const res = await request(app.getHttpServer())
        .post("/api/v1/widgets")
        .send({ name: "New Widget", description: "desc" })
        .expect(HttpStatus.CREATED);

      expect(res.body.data.name).toBe("New Widget");
      expect(res.body.meta.request_id).toBe("test-request-id");
    });

    it("returns 400 for invalid body — empty name", async () => {
      await request(app.getHttpServer())
        .post("/api/v1/widgets")
        .send({ name: "", description: "desc" })
        .expect(HttpStatus.BAD_REQUEST);

      expect(widgetService.create).not.toHaveBeenCalled();
    });

    it("returns 400 for extra fields when forbidNonWhitelisted", async () => {
      await request(app.getHttpServer())
        .post("/api/v1/widgets")
        .send({ name: "Valid", description: "desc", hackerField: "injected" })
        .expect(HttpStatus.BAD_REQUEST);

      expect(widgetService.create).not.toHaveBeenCalled();
    });
  });

  // --- Get ---

  describe("GET /api/v1/widgets/:id", () => {
    it("returns 200 with widget", async () => {
      const widget = makeWidget();
      (widgetService.get as jest.Mock).mockResolvedValueOnce(widget);

      const res = await request(app.getHttpServer())
        .get(`/api/v1/widgets/${widget.id}`)
        .expect(HttpStatus.OK);

      expect(res.body.data.id).toBe(widget.id);
    });

    it("returns 422 for non-UUID id — ParseUUIDPipe", async () => {
      await request(app.getHttpServer())
        .get("/api/v1/widgets/not-a-uuid")
        .expect(HttpStatus.UNPROCESSABLE_ENTITY);

      expect(widgetService.get).not.toHaveBeenCalled();
    });
  });

  // --- Update ---

  describe("PUT /api/v1/widgets/:id", () => {
    it("returns 200 with updated widget", async () => {
      const updated = makeWidget({ name: "Updated", version: 2 });
      (widgetService.update as jest.Mock).mockResolvedValueOnce(updated);

      const res = await request(app.getHttpServer())
        .put(`/api/v1/widgets/${updated.id}`)
        .send({ name: "Updated", description: "new desc", version: 1 })
        .expect(HttpStatus.OK);

      expect(res.body.data.version).toBe(2);
    });

    it("rejects missing version field", async () => {
      await request(app.getHttpServer())
        .put("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        .send({ name: "Updated", description: "desc" })
        .expect(HttpStatus.BAD_REQUEST);

      expect(widgetService.update).not.toHaveBeenCalled();
    });
  });

  // --- Delete ---

  describe("DELETE /api/v1/widgets/:id", () => {
    it("returns 204 with empty body", async () => {
      (widgetService.delete as jest.Mock).mockResolvedValueOnce(undefined);

      const res = await request(app.getHttpServer())
        .delete("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        .expect(HttpStatus.NO_CONTENT);

      expect(res.body).toEqual({});
    });

    it("rejects non-UUID id", async () => {
      await request(app.getHttpServer())
        .delete("/api/v1/widgets/xyz")
        .expect(HttpStatus.UNPROCESSABLE_ENTITY);

      expect(widgetService.delete).not.toHaveBeenCalled();
    });
  });

  // --- List ---

  describe("GET /api/v1/widgets (list)", () => {
    it("returns paginated results", async () => {
      (widgetService.list as jest.Mock).mockResolvedValueOnce({
        items: [makeWidget()],
        cursor: "abc",
        hasMore: true,
        total: 10,
      });

      const res = await request(app.getHttpServer())
        .get("/api/v1/widgets?page_size=5")
        .expect(HttpStatus.OK);

      expect(res.body.data).toHaveLength(1);
      expect(res.body.meta.has_more).toBe(true);
      expect(res.body.meta.cursor).toBe("abc");
    });
  });

  // --- Guard Tests ---

  describe("JwtAuthGuard", () => {
    it("returns 401 when guard rejects", async () => {
      // Rebuild app with a guard that rejects
      const module = await Test.createTestingModule({
        controllers: [WidgetController],
        providers: [{ provide: WidgetService, useValue: widgetService }],
      })
        .overrideGuard(JwtAuthGuard)
        .useValue({ canActivate: () => false })
        .compile();

      const restrictedApp = module.createNestApplication();
      restrictedApp.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
      await restrictedApp.init();

      await request(restrictedApp.getHttpServer())
        .get("/api/v1/widgets/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        .expect(HttpStatus.FORBIDDEN); // NestJS returns 403 when guard returns false

      await restrictedApp.close();
    });
  });
});
```

---

## Critical Rules

- Every handler test MUST use `supertest` to exercise the full middleware chain (validation, auth, error handling)
- Express tests MUST mount the `errorHandler` middleware last — without it, unhandled errors crash the test
- Mock auth middleware MUST inject `tenantId`, `userId`, `requestId` into the request (mirrors production)
- Malformed JSON MUST return 400 Bad Request, not 422 Validation Error
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Internal errors MUST NOT leak error details to the client — assert generic message in 500 responses
- Every response MUST follow the envelope format: `{"data": T, "meta": {...}}` for success, `{"error": {...}}` for failure
- DELETE MUST return 204 with empty body
- POST create MUST return 201 Created with the created resource in the body
- List responses MUST include `cursor`, `has_more`, `total` in meta
- Page size MUST be clamped: default to 20 when missing, cap at 100
- Sort and filter fields MUST be validated — invalid values default to safe values
- NestJS tests MUST use `Test.createTestingModule` with `overrideGuard` / `overrideProvider` for isolation
- NestJS `ValidationPipe` MUST be configured with `whitelist: true` and `transform: true` in tests — matching production
- Use `vi.fn()` (vitest) for Express mocks, `jest.fn()` for NestJS mocks
- Every mock MUST be reset in `beforeEach` to prevent cross-test contamination
- Zod validation tests (Express) MUST verify that invalid input is rejected BEFORE calling the service
- class-validator tests (NestJS) MUST verify that `forbidNonWhitelisted: true` strips extra fields
