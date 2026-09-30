---
skill: crud-repository-typescript
description: TypeScript repository archetype — Prisma and Drizzle patterns, cursor pagination, soft delete, optimistic locking, multi-tenant filtering, error mapping
version: "1.0"
tags:
  - typescript
  - repository
  - prisma
  - drizzle
  - postgres
  - archetype
  - backend
---

# CRUD Repository Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-repository.md` (Go). Both implement identical data access patterns: cursor pagination, soft delete, optimistic locking, and tenant isolation.

Complete TypeScript data access layer for Prisma and Drizzle. Every generated TypeScript repository MUST follow this pattern.

---

# Prisma Section

## Prisma Schema (Reference)

```prisma
// prisma/schema.prisma

model Widget {
  id          String    @id @default(uuid()) @db.Uuid
  tenantId    String    @map("tenant_id") @db.Uuid
  name        String    @db.VarChar(255)
  description String    @default("") @db.VarChar(2000)
  status      String    @default("active") @db.VarChar(50)
  createdAt   DateTime  @default(now()) @map("created_at")
  updatedAt   DateTime  @updatedAt @map("updated_at")
  deletedAt   DateTime? @map("deleted_at")
  createdBy   String    @map("created_by") @db.Uuid
  updatedBy   String    @map("updated_by") @db.Uuid
  version     Int       @default(1)

  components Component[]

  @@unique([tenantId, name], map: "widgets_tenant_name_unique")
  @@index([tenantId, createdAt])
  @@index([tenantId, status])
  @@map("widgets")
}

model Component {
  id        String   @id @default(uuid()) @db.Uuid
  widgetId  String   @map("widget_id") @db.Uuid
  tenantId  String   @map("tenant_id") @db.Uuid
  name      String   @db.VarChar(255)
  type      String   @db.VarChar(100)
  createdBy String   @map("created_by") @db.Uuid
  updatedBy String   @map("updated_by") @db.Uuid
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  widget Widget @relation(fields: [widgetId], references: [id])

  @@index([widgetId])
  @@map("components")
}
```

## Prisma Repository Implementation

```typescript
// src/repositories/prisma-widget.repository.ts

import { PrismaClient, Prisma } from "@prisma/client";
import type { IWidgetRepository } from "./widget.repository.interface";
import type { Widget } from "../domain/entity";
import type { ListFilters, ListResult } from "../types/pagination";
import { AppError } from "../errors/app-error";
import {
  notFound,
  conflict,
  businessRule,
  internal,
  unavailable,
} from "../errors/domain-errors";

/** Allowed sort columns — prevents injection via dynamic orderBy. */
const ALLOWED_SORT_COLUMNS = new Set(["created_at", "updated_at", "name"]);

/** Maps external sort column names to Prisma field names. */
const SORT_COLUMN_MAP: Record<string, string> = {
  created_at: "createdAt",
  updated_at: "updatedAt",
  name: "name",
} as const;

export class PrismaWidgetRepository implements IWidgetRepository {
  constructor(private readonly prisma: PrismaClient) {}

  // --- Create ---

  async create(widget: Widget): Promise<Widget> {
    try {
      const result = await this.prisma.widget.create({
        data: {
          id: widget.id,
          tenantId: widget.tenantId,
          name: widget.name,
          description: widget.description,
          status: widget.status,
          createdBy: widget.createdBy,
          updatedBy: widget.updatedBy,
          version: widget.version,
        },
      });
      return this.toDomain(result);
    } catch (err) {
      throw this.mapError(err, "create");
    }
  }

  // --- Find by ID (tenant-scoped, soft-delete filtered) ---

  async findById(tenantId: string, id: string): Promise<Widget | null> {
    const result = await this.prisma.widget.findFirst({
      where: {
        id,
        tenantId,
        deletedAt: null, // soft delete filter
      },
    });
    return result ? this.toDomain(result) : null;
  }

  // --- Find by Name (for duplicate checking) ---

  async findByName(tenantId: string, name: string): Promise<Widget | null> {
    const result = await this.prisma.widget.findFirst({
      where: {
        tenantId,
        name,
        deletedAt: null,
      },
    });
    return result ? this.toDomain(result) : null;
  }

  // --- Update with Optimistic Locking ---

  async update(widget: Widget): Promise<Widget> {
    try {
      const result = await this.prisma.widget.updateMany({
        where: {
          id: widget.id,
          tenantId: widget.tenantId,
          version: widget.version - 1, // optimistic lock: expect previous version
          deletedAt: null,
        },
        data: {
          name: widget.name,
          description: widget.description,
          status: widget.status,
          updatedBy: widget.updatedBy,
          updatedAt: widget.updatedAt,
          version: widget.version,
        },
      });

      if (result.count === 0) {
        throw conflict("This widget was changed by someone else. Reload and try again.");
      }

      // Fetch the updated record to return full entity
      const updated = await this.prisma.widget.findUnique({
        where: { id: widget.id },
      });
      return this.toDomain(updated!);
    } catch (err) {
      if (err instanceof AppError) throw err;
      throw this.mapError(err, "update");
    }
  }

  // --- Soft Delete ---

  async softDelete(tenantId: string, id: string): Promise<void> {
    const result = await this.prisma.widget.updateMany({
      where: {
        id,
        tenantId,
        deletedAt: null,
      },
      data: {
        deletedAt: new Date(),
        updatedAt: new Date(),
      },
    });

    if (result.count === 0) {
      throw notFound("Widget"); // also when it belongs to another tenant
    }
  }

  // --- List with Cursor Pagination ---

  async list(tenantId: string, filters: ListFilters): Promise<ListResult<Widget>> {
    const sortField = this.safeSortColumn(filters.sortBy);
    const sortDir = filters.sortDir === "asc" ? "asc" : "desc";

    // Build where clause
    const where: Prisma.WidgetWhereInput = {
      tenantId,
      deletedAt: null,
      ...this.buildFieldFilters(filters.fields),
    };

    // Cursor-based pagination: decode cursor, apply to where clause
    if (filters.cursor) {
      const cursorData = decodeCursor(filters.cursor);
      if (cursorData) {
        const op = sortDir === "desc" ? "lt" : "gt";
        where.OR = [
          { [sortField]: { [op]: cursorData.sortValue } },
          {
            [sortField]: cursorData.sortValue,
            id: { [op]: cursorData.id },
          },
        ];
      }
    }

    // Request limit+1 to detect has_more without extra count query
    const items = await this.prisma.widget.findMany({
      where,
      orderBy: [{ [sortField]: sortDir }, { id: sortDir }],
      take: filters.pageSize + 1,
    });

    const hasMore = items.length > filters.pageSize;
    const pageItems = hasMore ? items.slice(0, filters.pageSize) : items;

    // Build next cursor from last item
    let cursor = "";
    if (hasMore && pageItems.length > 0) {
      const last = pageItems[pageItems.length - 1];
      cursor = encodeCursor(last[sortField as keyof typeof last], last.id);
    }

    // Count total (for UI display — skip on huge tables if not needed)
    const total = await this.prisma.widget.count({
      where: { tenantId, deletedAt: null, ...this.buildFieldFilters(filters.fields) },
    });

    return {
      items: pageItems.map((item) => this.toDomain(item)),
      cursor,
      hasMore,
      total,
    };
  }

  // --- Private Helpers ---

  /**
   * Maps Prisma errors to AppErrors with generic client messages. The Prisma error — with the
   * constraint/field names in err.meta — stays in `cause` for the server log only.
   */
  private mapError(err: unknown, operation: string): AppError {
    if (err instanceof Prisma.PrismaClientKnownRequestError) {
      switch (err.code) {
        case "P2002": // Unique constraint violation → 409, constraint name only in the log
          return conflict("This widget already exists.").withCause(err);
        case "P2003": // Foreign key constraint violation → 422
          return businessRule("A referenced item doesn't exist.").withCause(err);
        case "P2025": // Record not found
          return notFound("Widget");
        case "P2024": // Timed out fetching a connection from the pool → 503, retryable
          return unavailable("postgres", err);
      }
    }

    // Anything else — including PrismaClientValidationError, which is a bug in the query we built,
    // not bad client input — is 500 INTERNAL with a generic message.
    return internal(err);
  }

  /** Validates and maps sort column to Prisma field. */
  private safeSortColumn(col: string): string {
    if (!ALLOWED_SORT_COLUMNS.has(col)) return "createdAt";
    return SORT_COLUMN_MAP[col] ?? "createdAt";
  }

  /** Builds Prisma where clause from dynamic field filters. */
  private buildFieldFilters(fields: Record<string, string>): Prisma.WidgetWhereInput {
    const where: Prisma.WidgetWhereInput = {};
    const allowedFields = new Set(["status", "priority", "category"]);

    for (const [key, value] of Object.entries(fields)) {
      if (allowedFields.has(key)) {
        (where as any)[key] = value;
      }
    }
    return where;
  }

  /** Maps Prisma model to domain entity. */
  private toDomain(record: any): Widget {
    return {
      id: record.id,
      tenantId: record.tenantId,
      name: record.name,
      description: record.description,
      status: record.status,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt,
      deletedAt: record.deletedAt,
      createdBy: record.createdBy,
      updatedBy: record.updatedBy,
      version: record.version,
    };
  }
}
```

## Prisma Soft Delete Middleware

```typescript
// src/lib/prisma-soft-delete.middleware.ts

import { Prisma } from "@prisma/client";

/**
 * Prisma middleware that automatically filters soft-deleted records
 * on find operations and converts delete to soft delete.
 *
 * Apply in main.ts:
 *   prisma.$use(softDeleteMiddleware);
 *
 * NOTE: Prisma Client Extensions (v4.16+) are preferred over $use middleware.
 * This middleware is shown for compatibility with older Prisma versions.
 */
export const softDeleteMiddleware: Prisma.Middleware = async (params, next) => {
  // Models that support soft delete
  const softDeleteModels = new Set(["Widget", "Component"]);

  if (!params.model || !softDeleteModels.has(params.model)) {
    return next(params);
  }

  // Intercept find operations — add deletedAt: null filter
  if (params.action === "findFirst" || params.action === "findMany") {
    if (!params.args) params.args = {};
    if (!params.args.where) params.args.where = {};

    // Only add filter if not explicitly querying deleted records
    if (params.args.where.deletedAt === undefined) {
      params.args.where.deletedAt = null;
    }
  }

  // Intercept delete — convert to soft delete
  if (params.action === "delete") {
    params.action = "update";
    params.args.data = { deletedAt: new Date() };
  }

  if (params.action === "deleteMany") {
    params.action = "updateMany";
    if (!params.args.data) params.args.data = {};
    params.args.data.deletedAt = new Date();
  }

  return next(params);
};
```

## Prisma Client Extension (Modern Approach)

```typescript
// src/lib/prisma-extensions.ts

import { Prisma, PrismaClient } from "@prisma/client";

/**
 * Prisma Client Extension for soft delete — preferred over $use middleware (v4.16+).
 *
 * Usage:
 *   const prisma = new PrismaClient().$extends(softDeleteExtension);
 */
export const softDeleteExtension = Prisma.defineExtension({
  name: "soft-delete",
  query: {
    widget: {
      async findMany({ args, query }) {
        args.where = { ...args.where, deletedAt: null };
        return query(args);
      },
      async findFirst({ args, query }) {
        args.where = { ...args.where, deletedAt: null };
        return query(args);
      },
      async delete({ args }) {
        // Convert delete to soft delete
        return (prisma as any).widget.update({
          ...args,
          data: { deletedAt: new Date(), updatedAt: new Date() },
        }) as any;
      },
    },
  },
});
```

---

# Drizzle Section

## Drizzle Schema Definition

```typescript
// src/db/schema.ts

import {
  pgTable,
  uuid,
  varchar,
  timestamp,
  integer,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

export const widgets = pgTable(
  "widgets",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: varchar("name", { length: 255 }).notNull(),
    description: varchar("description", { length: 2000 }).default("").notNull(),
    status: varchar("status", { length: 50 }).default("active").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
    createdBy: uuid("created_by").notNull(),
    updatedBy: uuid("updated_by").notNull(),
    version: integer("version").default(1).notNull(),
  },
  (table) => ({
    tenantCreatedIdx: index("widgets_tenant_created_idx").on(table.tenantId, table.createdAt),
    tenantStatusIdx: index("widgets_tenant_status_idx").on(table.tenantId, table.status),
    tenantNameUnique: uniqueIndex("widgets_tenant_name_unique").on(table.tenantId, table.name),
  }),
);

export const components = pgTable(
  "components",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    widgetId: uuid("widget_id")
      .notNull()
      .references(() => widgets.id),
    tenantId: uuid("tenant_id").notNull(),
    name: varchar("name", { length: 255 }).notNull(),
    type: varchar("type", { length: 100 }).notNull(),
    createdBy: uuid("created_by").notNull(),
    updatedBy: uuid("updated_by").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => ({
    widgetIdx: index("components_widget_idx").on(table.widgetId),
  }),
);

export const widgetRelations = relations(widgets, ({ many }) => ({
  components: many(components),
}));

export const componentRelations = relations(components, ({ one }) => ({
  widget: one(widgets, {
    fields: [components.widgetId],
    references: [widgets.id],
  }),
}));

/** Type inference helpers. */
export type WidgetInsert = typeof widgets.$inferInsert;
export type WidgetSelect = typeof widgets.$inferSelect;
export type ComponentInsert = typeof components.$inferInsert;
export type ComponentSelect = typeof components.$inferSelect;
```

## Drizzle Repository Implementation

```typescript
// src/repositories/drizzle-widget.repository.ts

import { eq, and, isNull, lt, gt, asc, desc, sql, type SQL } from "drizzle-orm";
import type { PostgresJsDatabase } from "drizzle-orm/postgres-js";
import { widgets } from "../db/schema";
import type { IWidgetRepository } from "./widget.repository.interface";
import type { Widget } from "../domain/entity";
import type { ListFilters, ListResult } from "../types/pagination";
import { AppError } from "../errors/app-error";
import {
  notFound,
  conflict,
  businessRule,
  internal,
  unavailable,
} from "../errors/domain-errors";

/** Allowed sort columns — maps external names to Drizzle column references. */
const SORT_COLUMN_MAP = {
  created_at: widgets.createdAt,
  updated_at: widgets.updatedAt,
  name: widgets.name,
} as const satisfies Record<string, typeof widgets[keyof typeof widgets]>;

type SortColumn = keyof typeof SORT_COLUMN_MAP;

export class DrizzleWidgetRepository implements IWidgetRepository {
  constructor(private readonly db: PostgresJsDatabase) {}

  // --- Create ---

  async create(widget: Widget): Promise<Widget> {
    try {
      const [result] = await this.db
        .insert(widgets)
        .values({
          id: widget.id,
          tenantId: widget.tenantId,
          name: widget.name,
          description: widget.description,
          status: widget.status,
          createdBy: widget.createdBy,
          updatedBy: widget.updatedBy,
          version: widget.version,
        })
        .returning();

      return this.toDomain(result);
    } catch (err) {
      throw this.mapError(err, "create");
    }
  }

  // --- Find by ID (tenant-scoped, soft-delete filtered) ---

  async findById(tenantId: string, id: string): Promise<Widget | null> {
    const [result] = await this.db
      .select()
      .from(widgets)
      .where(
        and(
          eq(widgets.id, id),
          eq(widgets.tenantId, tenantId),
          isNull(widgets.deletedAt),
        ),
      )
      .limit(1);

    return result ? this.toDomain(result) : null;
  }

  // --- Find by Name (for duplicate checking) ---

  async findByName(tenantId: string, name: string): Promise<Widget | null> {
    const [result] = await this.db
      .select()
      .from(widgets)
      .where(
        and(
          eq(widgets.tenantId, tenantId),
          eq(widgets.name, name),
          isNull(widgets.deletedAt),
        ),
      )
      .limit(1);

    return result ? this.toDomain(result) : null;
  }

  // --- Update with Optimistic Locking ---

  async update(widget: Widget): Promise<Widget> {
    try {
      const [result] = await this.db
        .update(widgets)
        .set({
          name: widget.name,
          description: widget.description,
          status: widget.status,
          updatedBy: widget.updatedBy,
          updatedAt: widget.updatedAt,
          version: widget.version,
        })
        .where(
          and(
            eq(widgets.id, widget.id),
            eq(widgets.tenantId, widget.tenantId),
            eq(widgets.version, widget.version - 1), // optimistic lock
            isNull(widgets.deletedAt),
          ),
        )
        .returning();

      if (!result) {
        throw conflict("This widget was changed by someone else. Reload and try again.");
      }

      return this.toDomain(result);
    } catch (err) {
      if (err instanceof AppError) throw err;
      throw this.mapError(err, "update");
    }
  }

  // --- Soft Delete ---

  async softDelete(tenantId: string, id: string): Promise<void> {
    const result = await this.db
      .update(widgets)
      .set({
        deletedAt: new Date(),
        updatedAt: new Date(),
      })
      .where(
        and(
          eq(widgets.id, id),
          eq(widgets.tenantId, tenantId),
          isNull(widgets.deletedAt),
        ),
      )
      .returning({ id: widgets.id });

    if (result.length === 0) {
      throw notFound("Widget"); // also when it belongs to another tenant
    }
  }

  // --- List with Cursor Pagination ---

  async list(tenantId: string, filters: ListFilters): Promise<ListResult<Widget>> {
    const sortCol = this.safeSortColumn(filters.sortBy);
    const sortFn = filters.sortDir === "asc" ? asc : desc;
    const compareFn = filters.sortDir === "asc" ? gt : lt;

    // Build base conditions
    const conditions: SQL[] = [
      eq(widgets.tenantId, tenantId),
      isNull(widgets.deletedAt),
    ];

    // Apply dynamic field filters
    this.applyFieldFilters(conditions, filters.fields);

    // Apply cursor
    if (filters.cursor) {
      const cursorData = decodeCursor(filters.cursor);
      if (cursorData) {
        conditions.push(
          sql`(${sortCol}, ${widgets.id}) ${filters.sortDir === "desc" ? sql`<` : sql`>`} (${cursorData.sortValue}, ${cursorData.id})`,
        );
      }
    }

    // Request limit+1 to detect has_more
    const items = await this.db
      .select()
      .from(widgets)
      .where(and(...conditions))
      .orderBy(sortFn(sortCol), sortFn(widgets.id))
      .limit(filters.pageSize + 1);

    const hasMore = items.length > filters.pageSize;
    const pageItems = hasMore ? items.slice(0, filters.pageSize) : items;

    // Build next cursor
    let cursor = "";
    if (hasMore && pageItems.length > 0) {
      const last = pageItems[pageItems.length - 1];
      const sortValue = last[this.sortFieldKey(filters.sortBy)];
      cursor = encodeCursor(sortValue, last.id);
    }

    // Count total
    const [{ count }] = await this.db
      .select({ count: sql<number>`count(*)::int` })
      .from(widgets)
      .where(
        and(
          eq(widgets.tenantId, tenantId),
          isNull(widgets.deletedAt),
          ...this.buildFieldFilterConditions(filters.fields),
        ),
      );

    return {
      items: pageItems.map((item) => this.toDomain(item)),
      cursor,
      hasMore,
      total: count,
    };
  }

  // --- Multi-Tenant Filtering Helper ---

  /**
   * Applies tenant scoping to any query.
   * Every query builder in this repository calls this — no query escapes tenant isolation.
   */
  private tenantScope(tenantId: string): SQL {
    return eq(widgets.tenantId, tenantId);
  }

  // --- Private Helpers ---

  private safeSortColumn(col: string): (typeof SORT_COLUMN_MAP)[SortColumn] {
    if (col in SORT_COLUMN_MAP) {
      return SORT_COLUMN_MAP[col as SortColumn];
    }
    return SORT_COLUMN_MAP.created_at;
  }

  private sortFieldKey(col: string): keyof typeof widgets.$inferSelect {
    const map: Record<string, keyof typeof widgets.$inferSelect> = {
      created_at: "createdAt",
      updated_at: "updatedAt",
      name: "name",
    };
    return map[col] ?? "createdAt";
  }

  private applyFieldFilters(conditions: SQL[], fields: Record<string, string>): void {
    const allowed = new Set(["status", "priority", "category"]);
    const columnMap: Record<string, typeof widgets[keyof typeof widgets]> = {
      status: widgets.status,
    };

    for (const [key, value] of Object.entries(fields)) {
      if (allowed.has(key) && columnMap[key]) {
        conditions.push(eq(columnMap[key] as any, value));
      }
    }
  }

  private buildFieldFilterConditions(fields: Record<string, string>): SQL[] {
    const conditions: SQL[] = [];
    this.applyFieldFilters(conditions, fields);
    return conditions;
  }

  /**
   * Maps Postgres errors to AppErrors by SQLSTATE — never by matching message text. Client messages
   * are generic; the driver error (with the constraint name) stays in `cause` for the log.
   */
  private mapError(err: unknown, operation: string): AppError {
    switch (sqlStateOf(err)) {
      case "23505": // unique_violation → 409
        return conflict("This widget already exists.").withCause(err);
      case "23503": // foreign_key_violation → 422
        return businessRule("A referenced item doesn't exist.").withCause(err);
      case "23514": // check_violation → 422
        return businessRule("This change isn't allowed.").withCause(err);
      case "57014": // query_canceled (statement_timeout) → 503, retryable
        return unavailable("postgres", err);
      default:
        return internal(err);
    }
  }

  /** Maps database row to domain entity. */
  private toDomain(record: typeof widgets.$inferSelect): Widget {
    return {
      id: record.id,
      tenantId: record.tenantId,
      name: record.name,
      description: record.description,
      status: record.status,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt,
      deletedAt: record.deletedAt,
      createdBy: record.createdBy,
      updatedBy: record.updatedBy,
      version: record.version,
    };
  }
}

/**
 * The SQLSTATE of a Postgres error. postgres.js and node-postgres both expose it as `code`; newer
 * drizzle-orm versions may wrap the driver error, so also look one level down in `cause`.
 */
function sqlStateOf(err: unknown): string | undefined {
  const e = err as { code?: unknown; cause?: { code?: unknown } } | null;
  const code = e?.code ?? e?.cause?.code;
  return typeof code === "string" ? code : undefined;
}
```

## Drizzle Pagination Helpers

```typescript
// src/db/pagination.ts

/**
 * Pagination helpers shared across all Drizzle repositories.
 */

import { sql, type SQL, gt, lt, asc, desc } from "drizzle-orm";

/**
 * Creates a tuple comparison for cursor pagination.
 * Generates: (sort_column, id) > (cursor_value, cursor_id)
 *
 * This is more efficient than separate WHERE clauses and handles
 * tied sort values correctly.
 */
export function cursorCondition(
  sortColumn: any,
  idColumn: any,
  cursorSortValue: unknown,
  cursorId: string,
  direction: "asc" | "desc",
): SQL {
  const op = direction === "asc" ? sql`>` : sql`<`;
  return sql`(${sortColumn}, ${idColumn}) ${op} (${cursorSortValue}, ${cursorId})`;
}

/**
 * Builds ORDER BY clause for cursor pagination.
 * Always includes id as tiebreaker to ensure stable ordering.
 */
export function cursorOrderBy(
  sortColumn: any,
  idColumn: any,
  direction: "asc" | "desc",
) {
  const sortFn = direction === "asc" ? asc : desc;
  return [sortFn(sortColumn), sortFn(idColumn)];
}
```

---

## Cursor Encoding / Decoding (Shared)

```typescript
// src/lib/cursor.ts

/**
 * Cursor = base64url(JSON{sortValue, id}) — opaque, stable across inserts.
 * Used by both Prisma and Drizzle repositories.
 */

interface CursorPayload {
  sv: unknown; // sort value (timestamp, string, etc.)
  id: string;  // entity ID
}

export function encodeCursor(sortValue: unknown, id: string): string {
  const payload: CursorPayload = { sv: sortValue, id };
  return Buffer.from(JSON.stringify(payload)).toString("base64url");
}

export function decodeCursor(cursor: string): { sortValue: unknown; id: string } | null {
  try {
    const json = Buffer.from(cursor, "base64url").toString("utf-8");
    const payload = JSON.parse(json) as CursorPayload;

    if (!payload.id) return null;

    // Restore Date objects if the sort value looks like an ISO timestamp
    let sortValue = payload.sv;
    if (typeof sortValue === "string" && /^\d{4}-\d{2}-\d{2}T/.test(sortValue)) {
      sortValue = new Date(sortValue);
    }

    return { sortValue, id: payload.id };
  } catch {
    return null; // Invalid cursor — treat as no cursor
  }
}
```

---

## Drizzle Database Connection Setup

```typescript
// src/db/connection.ts

import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import * as schema from "./schema";

export function createDatabase(connectionString: string) {
  const client = postgres(connectionString, {
    max: 50,                    // max pool connections
    idle_timeout: 30,           // close idle connections after 30s
    connect_timeout: 10,        // connection timeout
    max_lifetime: 60 * 60,      // max connection lifetime (1 hour)
  });

  const db = drizzle(client, { schema });

  return {
    db,
    client,
    close: async () => {
      await client.end();
    },
  };
}
```

---

## Critical Rules

- Every query MUST include `tenantId` equality check — no cross-tenant data leaks
- Every read query MUST include `deletedAt IS NULL` (soft delete filter)
- Update operations MUST use optimistic locking: `WHERE version = expected_version`
- Sort column names MUST be allow-listed via `SORT_COLUMN_MAP` — never accept arbitrary column names
- Filter field names MUST be allow-listed — never pass arbitrary query params to the DB
- Cursor values MUST be opaque (base64url-encoded JSON) — never expose raw DB values
- List queries MUST request `LIMIT + 1` to detect `hasMore` without extra count query
- Prisma errors MUST be mapped to `AppError`s (`notFound`, `conflict`, `businessRule`, `unavailable`, `internal`) — unique violation → 409 `CONFLICT`, FK/check violation → 422 `BUSINESS_RULE_VIOLATION`, timeout → 503 `UNAVAILABLE`
- Drizzle errors MUST be mapped the same way at the repository boundary, by SQLSTATE (never by matching message text)
- Client-visible messages MUST be generic — constraint names, SQL and driver messages stay in `cause` for the log
- There is no offset/page-number list method — list endpoints are cursor-only (`crud-handler-typescript.md` §Pagination)
- Cache MUST be invalidated on every write — handled by the service layer, not the repository
- The repository returns `null` for not-found reads — the service converts to `notFound(...)` (404 `NOT_FOUND`)
- Connection pools MUST have explicit limits — never use unbounded connection counts
- All SQL-like operations MUST use parameterized queries — Prisma and Drizzle handle this natively
- `toDomain()` mapping MUST exist — never return ORM-specific types to the service layer
