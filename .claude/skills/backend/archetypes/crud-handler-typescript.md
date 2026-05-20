---
skill: crud-handler-typescript
description: TypeScript HTTP handler archetype — Express and NestJS patterns, Zod validation, typed request/response, cursor + offset pagination, async error handling, middleware chain
version: "1.0"
tags:
  - typescript
  - handler
  - http
  - express
  - nestjs
  - archetype
  - backend
---

# CRUD Handler Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-handler.md` (Go). Both produce identical response envelopes so frontend clients can use a single parsing strategy.

Complete HTTP handler set for Express and NestJS. Every generated TypeScript handler MUST follow this pattern.

---

## Shared Types — Response Envelopes

```typescript
// src/types/response.ts

/** Wraps a single resource response — matches Go archetype exactly. */
export interface Envelope<T> {
  data: T;
  meta: Meta;
}

/** Wraps a paginated list response (cursor-based). */
export interface ListEnvelope<T> {
  data: T[];
  meta: ListMeta;
}

/** Wraps an offset-paginated list response (admin/reporting UIs). */
export interface OffsetListEnvelope<T> {
  data: T[];
  meta: OffsetListMeta;
  links: PageLinks;
}

export interface Meta {
  request_id: string;
  timestamp: string;
}

export interface ListMeta {
  cursor: string;
  has_more: boolean;
  total: number;
  request_id: string;
  timestamp: string;
}

export interface OffsetListMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  request_id: string;
  timestamp: string;
}

export interface PageLinks {
  self: string;
  next?: string;
  prev?: string;
  first: string;
  last: string;
}

export function newMeta(requestId: string): Meta {
  return {
    request_id: requestId,
    timestamp: new Date().toISOString(),
  };
}
```

---

## Shared Types — Pagination and Filters

```typescript
// src/types/pagination.ts

export interface ListFilters {
  cursor: string;
  pageSize: number;
  sortBy: string;
  sortDir: "asc" | "desc";
  fields: Record<string, string>;
}

export interface OffsetListFilters {
  page: number;
  perPage: number;
  sortBy: string;
  sortDir: "asc" | "desc";
  fields: Record<string, string>;
}

export interface ListResult<T> {
  items: T[];
  cursor: string;
  hasMore: boolean;
  total: number;
}

export interface OffsetListResult<T> {
  items: T[];
  total: number;
}
```

---

## Zod Validation Schemas

```typescript
// src/schemas/widget.schema.ts

import { z } from "zod";

export const createWidgetSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "name is required")
    .max(255, "name must be 255 characters or fewer"),
  description: z
    .string()
    .trim()
    .max(2000, "description must be 2000 characters or fewer")
    .default(""),
});

export const updateWidgetSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "name is required")
    .max(255, "name must be 255 characters or fewer"),
  description: z
    .string()
    .trim()
    .max(2000, "description must be 2000 characters or fewer")
    .default(""),
  version: z.number().int().nonnegative("version must be a non-negative integer"),
});

export const idParamSchema = z.object({
  id: z.string().uuid("invalid UUID format"),
});

export const cursorPaginationSchema = z.object({
  cursor: z.string().optional().default(""),
  page_size: z.coerce.number().int().min(1).max(100).optional().default(20),
  sort_by: z.enum(["created_at", "updated_at", "name"]).optional().default("created_at"),
  sort_dir: z.enum(["asc", "desc"]).optional().default("desc"),
});

export const offsetPaginationSchema = z.object({
  page: z.coerce.number().int().min(1).optional().default(1),
  per_page: z.coerce.number().int().min(1).max(100).optional().default(20),
  sort_by: z.enum(["created_at", "updated_at", "name"]).optional().default("created_at"),
  sort_dir: z.enum(["asc", "desc"]).optional().default("desc"),
});

export type CreateWidgetInput = z.infer<typeof createWidgetSchema>;
export type UpdateWidgetInput = z.infer<typeof updateWidgetSchema>;
```

---

# Express Section

## Async Handler Wrapper

```typescript
// src/middleware/async-handler.ts

import type { Request, Response, NextFunction } from "express";

/**
 * Wraps async Express route handlers to catch rejected promises
 * and forward them to error middleware.
 *
 * Usage:
 *   router.get("/widgets/:id", asyncHandler(async (req, res) => {
 *     const widget = await widgetService.get(req.params.id);
 *     res.json({ data: widget });
 *   }));
 */
export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<void>,
) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}
```

## Express Typed Request Helpers

```typescript
// src/types/express.d.ts

import type { Request } from "express";

/** Authenticated request — populated by auth middleware. */
export interface AuthenticatedRequest extends Request {
  userId: string;
  tenantId: string;
  roles: string[];
  requestId: string;
}
```

## Express Validation Middleware

```typescript
// src/middleware/validate.ts

import type { Request, Response, NextFunction } from "express";
import type { ZodSchema, ZodError } from "zod";
import { MultiValidationError } from "../errors/domain-errors";

type ValidationTarget = "body" | "params" | "query";

/**
 * Express middleware that validates the specified request target against a Zod schema.
 * On success, replaces the target with the parsed (and sanitized) value.
 * On failure, throws a MultiValidationError caught by error middleware.
 *
 * Usage:
 *   router.post("/widgets", validate("body", createWidgetSchema), createHandler);
 *   router.get("/widgets/:id", validate("params", idParamSchema), getHandler);
 */
export function validate(target: ValidationTarget, schema: ZodSchema) {
  return (req: Request, _res: Response, next: NextFunction) => {
    const result = schema.safeParse(req[target]);

    if (!result.success) {
      const fieldErrors = formatZodErrors(result.error);
      throw new MultiValidationError(fieldErrors);
    }

    // Replace target with parsed value (trimmed, defaulted, coerced)
    (req as any)[target] = result.data;
    next();
  };
}

function formatZodErrors(error: ZodError): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  for (const issue of error.issues) {
    const path = issue.path.join(".");
    fieldErrors[path] = issue.message;
  }
  return fieldErrors;
}
```

## Express Router Setup

```typescript
// src/routes/widget.routes.ts

import { Router } from "express";
import { asyncHandler } from "../middleware/async-handler";
import { validate } from "../middleware/validate";
import {
  createWidgetSchema,
  updateWidgetSchema,
  idParamSchema,
  cursorPaginationSchema,
  offsetPaginationSchema,
} from "../schemas/widget.schema";
import type { WidgetService } from "../services/widget.service";
import type { AuthenticatedRequest } from "../types/express";
import { newMeta } from "../types/response";
import type {
  Envelope,
  ListEnvelope,
  OffsetListEnvelope,
  PageLinks,
} from "../types/response";
import type { Widget } from "../domain/widget";

/**
 * Creates the widget router with all CRUD endpoints mounted.
 * Mount into the main app: app.use("/api/v1/widgets", createWidgetRouter(widgetService));
 */
export function createWidgetRouter(svc: WidgetService): Router {
  const router = Router();

  // --- Create ---
  router.post(
    "/",
    validate("body", createWidgetSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const result = await svc.create(authReq.tenantId, authReq.userId, req.body);

      const response: Envelope<Widget> = {
        data: result,
        meta: newMeta(authReq.requestId),
      };
      res.status(201).json(response);
    }),
  );

  // --- List (cursor pagination — default for public APIs) ---
  router.get(
    "/",
    validate("query", cursorPaginationSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const query = req.query as unknown as {
        cursor: string;
        page_size: number;
        sort_by: string;
        sort_dir: "asc" | "desc";
      };

      // Parse dynamic field filters: ?filter[status]=active&filter[priority]=high
      const fields = parseFieldFilters(req);

      const result = await svc.list(authReq.tenantId, {
        cursor: query.cursor,
        pageSize: query.page_size,
        sortBy: query.sort_by,
        sortDir: query.sort_dir,
        fields,
      });

      const response: ListEnvelope<Widget> = {
        data: result.items,
        meta: {
          cursor: result.cursor,
          has_more: result.hasMore,
          total: result.total,
          request_id: authReq.requestId,
          timestamp: new Date().toISOString(),
        },
      };
      res.json(response);
    }),
  );

  // --- List Admin (offset pagination — for admin/reporting UIs) ---
  router.get(
    "/admin",
    validate("query", offsetPaginationSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const query = req.query as unknown as {
        page: number;
        per_page: number;
        sort_by: string;
        sort_dir: "asc" | "desc";
      };

      const fields = parseFieldFilters(req);

      const result = await svc.listOffset(authReq.tenantId, {
        page: query.page,
        perPage: query.per_page,
        sortBy: query.sort_by,
        sortDir: query.sort_dir,
        fields,
      });

      const totalPages = query.per_page > 0
        ? Math.ceil(result.total / query.per_page)
        : 0;

      const basePath = req.baseUrl + req.path;
      const links: PageLinks = {
        self: `${basePath}?page=${query.page}&per_page=${query.per_page}`,
        first: `${basePath}?page=1&per_page=${query.per_page}`,
        last: `${basePath}?page=${totalPages}&per_page=${query.per_page}`,
        ...(query.page < totalPages
          ? { next: `${basePath}?page=${query.page + 1}&per_page=${query.per_page}` }
          : {}),
        ...(query.page > 1
          ? { prev: `${basePath}?page=${query.page - 1}&per_page=${query.per_page}` }
          : {}),
      };

      const response: OffsetListEnvelope<Widget> = {
        data: result.items,
        meta: {
          page: query.page,
          per_page: query.per_page,
          total: result.total,
          total_pages: totalPages,
          request_id: authReq.requestId,
          timestamp: new Date().toISOString(),
        },
        links,
      };
      res.json(response);
    }),
  );

  // --- Get by ID ---
  router.get(
    "/:id",
    validate("params", idParamSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const result = await svc.get(authReq.tenantId, req.params.id);

      const response: Envelope<Widget> = {
        data: result,
        meta: newMeta(authReq.requestId),
      };
      res.json(response);
    }),
  );

  // --- Update ---
  router.put(
    "/:id",
    validate("params", idParamSchema),
    validate("body", updateWidgetSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const result = await svc.update(authReq.tenantId, req.params.id, req.body);

      const response: Envelope<Widget> = {
        data: result,
        meta: newMeta(authReq.requestId),
      };
      res.json(response);
    }),
  );

  // --- Delete (soft) ---
  router.delete(
    "/:id",
    validate("params", idParamSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      await svc.delete(authReq.tenantId, req.params.id);
      res.status(204).send();
    }),
  );

  return router;
}

// --- Helpers ---

const ALLOWED_FILTER_FIELDS = new Set(["status", "priority", "category"]);

/**
 * Parses dynamic field filters from query string.
 * Accepts: ?filter[status]=active&filter[priority]=high
 * Only allow-listed fields are accepted — arbitrary params are dropped.
 */
function parseFieldFilters(req: { query: Record<string, unknown> }): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const [key, value] of Object.entries(req.query)) {
    const match = /^filter\[(\w+)]$/.exec(key);
    if (match && ALLOWED_FILTER_FIELDS.has(match[1]) && typeof value === "string") {
      fields[match[1]] = value;
    }
  }
  return fields;
}
```

## Express App Assembly

```typescript
// src/app.ts — Express app setup showing middleware chain order

import express from "express";
import { createWidgetRouter } from "./routes/widget.routes";
import { errorHandler } from "./middleware/error-handler";
import { requestId } from "./middleware/request-id";
import { authMiddleware } from "./middleware/auth";
import { corsMiddleware } from "./middleware/cors";

export function createApp(deps: AppDependencies): express.Application {
  const app = express();

  // --- Middleware chain (order matters) ---
  // 1. CORS — outermost, handles preflight before auth
  app.use(corsMiddleware(deps.config.cors));

  // 2. Request ID — generate/extract before anything else
  app.use(requestId);

  // 3. Body parser with size limit — prevent abuse
  app.use(express.json({ limit: "1mb" }));

  // 4. Auth — sets req.userId, req.tenantId, req.roles
  app.use(authMiddleware(deps.config.jwt));

  // 5. Routes
  app.use("/api/v1/widgets", createWidgetRouter(deps.widgetService));

  // 6. Error handler — MUST be last
  app.use(errorHandler);

  return app;
}
```

---

# NestJS Section

## NestJS Controller

```typescript
// src/modules/widget/widget.controller.ts

import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Param,
  Body,
  Query,
  HttpCode,
  HttpStatus,
  UseGuards,
  UsePipes,
  ValidationPipe,
  ParseUUIDPipe,
} from "@nestjs/common";
import { WidgetService } from "./widget.service";
import { CreateWidgetDto, UpdateWidgetDto } from "./dto/widget.dto";
import { CursorPaginationDto, OffsetPaginationDto } from "./dto/pagination.dto";
import { JwtAuthGuard } from "../../guards/jwt-auth.guard";
import { CurrentUser } from "../../decorators/current-user.decorator";
import { RequestId } from "../../decorators/request-id.decorator";
import type { AuthUser } from "../../types/auth";
import type { Envelope, ListEnvelope } from "../../types/response";
import type { Widget } from "../../domain/widget";

@Controller("api/v1/widgets")
@UseGuards(JwtAuthGuard)
@UsePipes(new ValidationPipe({ whitelist: true, transform: true }))
export class WidgetController {
  constructor(private readonly widgetService: WidgetService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async create(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Body() dto: CreateWidgetDto,
  ): Promise<Envelope<Widget>> {
    const result = await this.widgetService.create(user.tenantId, user.id, dto);
    return {
      data: result,
      meta: { request_id: requestId, timestamp: new Date().toISOString() },
    };
  }

  @Get()
  async list(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Query() query: CursorPaginationDto,
  ): Promise<ListEnvelope<Widget>> {
    const result = await this.widgetService.list(user.tenantId, {
      cursor: query.cursor ?? "",
      pageSize: query.page_size ?? 20,
      sortBy: query.sort_by ?? "created_at",
      sortDir: query.sort_dir ?? "desc",
      fields: {},
    });
    return {
      data: result.items,
      meta: {
        cursor: result.cursor,
        has_more: result.hasMore,
        total: result.total,
        request_id: requestId,
        timestamp: new Date().toISOString(),
      },
    };
  }

  @Get(":id")
  async get(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Param("id", new ParseUUIDPipe({ version: "4" })) id: string,
  ): Promise<Envelope<Widget>> {
    const result = await this.widgetService.get(user.tenantId, id);
    return {
      data: result,
      meta: { request_id: requestId, timestamp: new Date().toISOString() },
    };
  }

  @Put(":id")
  async update(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Param("id", new ParseUUIDPipe({ version: "4" })) id: string,
    @Body() dto: UpdateWidgetDto,
  ): Promise<Envelope<Widget>> {
    const result = await this.widgetService.update(user.tenantId, id, dto);
    return {
      data: result,
      meta: { request_id: requestId, timestamp: new Date().toISOString() },
    };
  }

  @Delete(":id")
  @HttpCode(HttpStatus.NO_CONTENT)
  async delete(
    @CurrentUser() user: AuthUser,
    @Param("id", new ParseUUIDPipe({ version: "4" })) id: string,
  ): Promise<void> {
    await this.widgetService.delete(user.tenantId, id);
  }
}
```

## NestJS DTOs with class-validator

```typescript
// src/modules/widget/dto/widget.dto.ts

import {
  IsString,
  IsNotEmpty,
  MaxLength,
  IsOptional,
  IsInt,
  Min,
} from "class-validator";
import { Transform } from "class-transformer";

export class CreateWidgetDto {
  @IsString()
  @IsNotEmpty({ message: "name is required" })
  @MaxLength(255, { message: "name must be 255 characters or fewer" })
  @Transform(({ value }: { value: string }) => value?.trim())
  name!: string;

  @IsString()
  @IsOptional()
  @MaxLength(2000, { message: "description must be 2000 characters or fewer" })
  @Transform(({ value }: { value: string }) => value?.trim())
  description?: string;
}

export class UpdateWidgetDto {
  @IsString()
  @IsNotEmpty({ message: "name is required" })
  @MaxLength(255, { message: "name must be 255 characters or fewer" })
  @Transform(({ value }: { value: string }) => value?.trim())
  name!: string;

  @IsString()
  @IsOptional()
  @MaxLength(2000, { message: "description must be 2000 characters or fewer" })
  @Transform(({ value }: { value: string }) => value?.trim())
  description?: string;

  @IsInt()
  @Min(0, { message: "version must be a non-negative integer" })
  version!: number;
}
```

## NestJS Pagination DTOs

```typescript
// src/modules/widget/dto/pagination.dto.ts

import { IsOptional, IsString, IsEnum, IsInt, Min, Max } from "class-validator";
import { Transform, Type } from "class-transformer";

export class CursorPaginationDto {
  @IsOptional()
  @IsString()
  cursor?: string;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  page_size?: number = 20;

  @IsOptional()
  @IsEnum(["created_at", "updated_at", "name"] as const)
  sort_by?: "created_at" | "updated_at" | "name" = "created_at";

  @IsOptional()
  @IsEnum(["asc", "desc"] as const)
  sort_dir?: "asc" | "desc" = "desc";
}

export class OffsetPaginationDto {
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  per_page?: number = 20;

  @IsOptional()
  @IsEnum(["created_at", "updated_at", "name"] as const)
  sort_by?: "created_at" | "updated_at" | "name" = "created_at";

  @IsOptional()
  @IsEnum(["asc", "desc"] as const)
  sort_dir?: "asc" | "desc" = "desc";
}
```

## NestJS Custom Decorators

```typescript
// src/decorators/current-user.decorator.ts

import { createParamDecorator, ExecutionContext } from "@nestjs/common";
import type { AuthUser } from "../types/auth";

/**
 * Extracts the authenticated user from the request.
 * Populated by JwtAuthGuard.
 *
 * Usage: @CurrentUser() user: AuthUser
 */
export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): AuthUser => {
    const request = ctx.switchToHttp().getRequest();
    return request.user as AuthUser;
  },
);

// src/decorators/request-id.decorator.ts

import { createParamDecorator, ExecutionContext } from "@nestjs/common";

/**
 * Extracts the request ID from headers or generates one.
 *
 * Usage: @RequestId() requestId: string
 */
export const RequestId = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): string => {
    const request = ctx.switchToHttp().getRequest();
    return request.headers["x-request-id"] ?? request.requestId ?? "";
  },
);
```

## NestJS Module Wiring

```typescript
// src/modules/widget/widget.module.ts

import { Module } from "@nestjs/common";
import { WidgetController } from "./widget.controller";
import { WidgetService } from "./widget.service";
import { WidgetRepository } from "./widget.repository";

@Module({
  controllers: [WidgetController],
  providers: [WidgetService, WidgetRepository],
  exports: [WidgetService],
})
export class WidgetModule {}
```

---

## Pagination Strategy — When to Use Which

| Strategy | Use When | Query Params | Example |
|----------|----------|--------------|---------|
| **Cursor** (default) | Public APIs, real-time feeds, large datasets, infinite scroll | `?cursor=abc&page_size=20` | User-facing list endpoints |
| **Offset** | Admin/reporting UIs, dashboards, "jump to page N", data export previews | `?page=3&per_page=20` | Back-office tables, audit logs |

**Default to cursor pagination.** Use offset only for admin/reporting UIs where users need to jump to arbitrary pages. Offset pagination degrades at high page numbers (OFFSET 10000 still scans 10000 rows).

---

## Critical Rules

- Every handler MUST validate input via Zod (Express) or class-validator (NestJS) before calling the service
- Every handler MUST extract `requestId` from the request and include it in response metadata
- Tenant ID comes from auth context (set by auth middleware) — NEVER from path params or body
- Request body size MUST be limited (`express.json({ limit: "1mb" })`) to prevent abuse
- Error responses MUST map domain errors to correct HTTP status codes via error middleware/filter
- Internal error messages MUST NOT leak to clients — return generic message for 500s
- Pagination MUST enforce max page size (100) — never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST use the envelope format: `{"data": T, "meta": {...}}`
- DELETE returns 204 No Content — no body
- POST create returns 201 Created with the created resource in the body
- Zod schemas MUST use `.trim()` on string fields to sanitize whitespace
- The `asyncHandler` wrapper is MANDATORY for all Express route handlers — without it, rejected promises crash the process
