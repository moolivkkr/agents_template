---
skill: crud-handler-typescript
description: TypeScript HTTP handler archetype — Express and NestJS patterns, Zod validation, typed request/response, cursor pagination, async error handling, middleware chain
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

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/crud-handler.md` (Go). Both produce the envelope in `~/.claude/skills/api/response-envelope.md` — success `{data, meta}`, error `{error}`, never both; list metadata in `meta.pagination` — so frontend clients can use a single parsing strategy. Error bodies are written only by the error middleware in `error-handling-typescript.md`.

Complete HTTP handler set for Express and NestJS. Every generated TypeScript handler MUST follow this pattern.

---

## Shared Types — Response Envelopes

```typescript
// src/types/response.ts

/** Wraps a single resource response — matches the Go archetype exactly. */
export interface Envelope<T> {
  data: T;
  meta: Meta;
}

/** Wraps a list response (cursor pagination). `data` is always an array — [] when empty, never null. */
export interface ListEnvelope<T> {
  data: T[];
  meta: ListMeta;
}

export interface Meta {
  request_id: string;
}

export interface ListMeta extends Meta {
  pagination: Pagination;
}

export interface Pagination {
  next_cursor: string | null; // null when has_more is false
  has_more: boolean;
  limit: number;
  total_count?: number;       // only if cheap AND the UI shows it
}

export function newMeta(requestId: string): Meta {
  return { request_id: requestId };
}

export function newListMeta(
  requestId: string,
  page: { cursor: string; hasMore: boolean },
  limit: number,
): ListMeta {
  return {
    request_id: requestId,
    pagination: {
      next_cursor: page.hasMore && page.cursor ? page.cursor : null,
      has_more: page.hasMore,
      limit,
    },
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

export interface ListResult<T> {
  items: T[];
  cursor: string;  // opaque next-page cursor; "" when hasMore is false
  hasMore: boolean;
  total: number;   // internal — becomes meta.pagination.total_count only if cheap AND the UI shows it
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

// ?cursor=<next_cursor>&limit=<n> — cursor pagination only (see "Pagination — cursor only" below)
export const cursorPaginationSchema = z.object({
  cursor: z.string().optional().default(""),
  limit: z.coerce.number().int().min(1).max(100).optional().default(20),
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
 *     res.json({ data: widget, meta: newMeta(requestId) });
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
import type { ZodSchema, ZodError, ZodIssue } from "zod";
import type { FieldError } from "../errors/app-error";
import { FIELD_MESSAGES, multiValidationError } from "../errors/domain-errors";

type ValidationTarget = "body" | "params" | "query";

/**
 * Express middleware that validates the specified request target against a Zod schema.
 * On success, replaces the target with the parsed (and sanitized) value.
 * On failure, throws 400 VALIDATION_FAILED (details[] per field), caught by the error middleware.
 *
 * Usage:
 *   router.post("/widgets", validate("body", createWidgetSchema), createHandler);
 *   router.get("/widgets/:id", validate("params", idParamSchema), getHandler);
 */
export function validate(target: ValidationTarget, schema: ZodSchema) {
  return (req: Request, _res: Response, next: NextFunction) => {
    const result = schema.safeParse(req[target]);

    if (!result.success) {
      throw multiValidationError(toFieldErrors(result.error));
    }

    // Replace target with parsed value (trimmed, defaulted, coerced)
    (req as any)[target] = result.data;
    next();
  };
}

/**
 * Zod issues → details[]: a stable lower_snake code plus the catalog message for that code.
 * issue.message is never sent — default Zod text isn't written for users.
 */
function toFieldErrors(error: ZodError): FieldError[] {
  return error.issues.map((issue) => {
    const code = fieldCode(issue);
    return { field: issue.path.join("."), code, message: FIELD_MESSAGES[code] };
  });
}

function fieldCode(issue: ZodIssue): string {
  switch (issue.code) {
    case "invalid_type":
      return issue.received === "undefined" ? "required" : "invalid_type";
    case "too_small":
      return issue.type === "string" && issue.minimum === 1 ? "required" : "too_small";
    case "too_big":
      return issue.type === "string" ? "too_long" : "too_big";
    case "invalid_string": // uuid, email, url, regex …
      return "invalid_format";
    default: // invalid_enum_value, custom, …
      return "invalid_value";
  }
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
} from "../schemas/widget.schema";
import type { WidgetService } from "../services/widget.service";
import type { AuthenticatedRequest } from "../types/express";
import { newMeta, newListMeta } from "../types/response";
import type { Envelope, ListEnvelope } from "../types/response";
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

  // --- List (cursor pagination: ?cursor=<next_cursor>&limit=<n>) ---
  router.get(
    "/",
    validate("query", cursorPaginationSchema),
    asyncHandler(async (req, res) => {
      const authReq = req as AuthenticatedRequest;
      const query = req.query as unknown as {
        cursor: string;
        limit: number;
        sort_by: string;
        sort_dir: "asc" | "desc";
      };

      // Parse dynamic field filters: ?filter[status]=active&filter[priority]=high
      const fields = parseFieldFilters(req);

      const result = await svc.list(authReq.tenantId, {
        cursor: query.cursor,
        pageSize: query.limit,
        sortBy: query.sort_by,
        sortDir: query.sort_dir,
        fields,
      });

      // data is [] (never null) when empty; next_cursor is null when has_more is false
      const response: ListEnvelope<Widget> = {
        data: result.items ?? [],
        meta: newListMeta(authReq.requestId, result, query.limit),
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

  // 2. Request ID — generate/extract before anything else; sets req.requestId and the
  //    X-Request-Id response header (= meta.request_id / error.request_id)
  app.use(requestId);

  // 3. Body parser with size limit — prevent abuse (bad JSON / too large → 400 MALFORMED_REQUEST)
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
import { CursorPaginationDto } from "./dto/pagination.dto";
import { JwtAuthGuard } from "../../guards/jwt-auth.guard";
import { CurrentUser } from "../../decorators/current-user.decorator";
import { RequestId } from "../../decorators/request-id.decorator";
import { validationExceptionFactory } from "../../filters/app-error.filter";
import { validationError } from "../../errors/domain-errors";
import type { AuthUser } from "../../types/auth";
import { newMeta, newListMeta } from "../../types/response";
import type { Envelope, ListEnvelope } from "../../types/response";
import type { Widget } from "../../domain/widget";

/** Invalid :id → 400 VALIDATION_FAILED (details[0].field = "id"), not Nest's default body. */
const uuidPipe = new ParseUUIDPipe({
  version: "4",
  exceptionFactory: () => validationError("id", "invalid_format", "Must be a valid ID."),
});

@Controller("api/v1/widgets")
@UseGuards(JwtAuthGuard)
@UsePipes(new ValidationPipe({ whitelist: true, transform: true, exceptionFactory: validationExceptionFactory }))
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
      meta: newMeta(requestId),
    };
  }

  @Get()
  async list(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Query() query: CursorPaginationDto,
  ): Promise<ListEnvelope<Widget>> {
    const limit = query.limit ?? 20;
    const result = await this.widgetService.list(user.tenantId, {
      cursor: query.cursor ?? "",
      pageSize: limit,
      sortBy: query.sort_by ?? "created_at",
      sortDir: query.sort_dir ?? "desc",
      fields: {},
    });
    return {
      data: result.items ?? [],
      meta: newListMeta(requestId, result, limit),
    };
  }

  @Get(":id")
  async get(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Param("id", uuidPipe) id: string,
  ): Promise<Envelope<Widget>> {
    const result = await this.widgetService.get(user.tenantId, id);
    return {
      data: result,
      meta: newMeta(requestId),
    };
  }

  @Put(":id")
  async update(
    @CurrentUser() user: AuthUser,
    @RequestId() requestId: string,
    @Param("id", uuidPipe) id: string,
    @Body() dto: UpdateWidgetDto,
  ): Promise<Envelope<Widget>> {
    const result = await this.widgetService.update(user.tenantId, id, dto);
    return {
      data: result,
      meta: newMeta(requestId),
    };
  }

  @Delete(":id")
  @HttpCode(HttpStatus.NO_CONTENT)
  async delete(
    @CurrentUser() user: AuthUser,
    @Param("id", uuidPipe) id: string,
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

/** ?cursor=<next_cursor>&limit=<n> — cursor pagination only. */
export class CursorPaginationDto {
  @IsOptional()
  @IsString()
  cursor?: string;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;

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
import { requestIdOf } from "../middleware/error-handler";

/**
 * The request ID set by the request-id middleware (or generated once per request) — the same value
 * the error filter puts in error.request_id and X-Request-Id.
 *
 * Usage: @RequestId() requestId: string
 */
export const RequestId = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): string => {
    return requestIdOf(ctx.switchToHttp().getRequest());
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

## Pagination — cursor only

List endpoints take `?cursor=<next_cursor>&limit=<n>` and return `meta.pagination`. There is no offset
or page-number variant: offset pages skip or repeat rows under concurrent writes, and `OFFSET 10000`
still scans 10,000 rows. For "jump to page N" admin tables, filter instead (date range, search, status).
A spec that truly needs numbered pages records it in `docs/DECISIONS.md` and still uses the envelope.

---

## Critical Rules

- Every handler MUST validate input via Zod (Express) or class-validator (NestJS) before calling the service
- Every handler MUST extract `requestId` from the request and include it in response metadata
- Tenant ID comes from auth context (set by auth middleware) — NEVER from path params or body
- Request body size MUST be limited (`express.json({ limit: "1mb" })`) to prevent abuse
- Error responses MUST map domain errors to correct HTTP status codes via error middleware/filter — handlers never write error bodies themselves
- Internal error messages MUST NOT leak to clients — return generic message for 500s
- Validation failures (Zod / class-validator / invalid `:id`) are 400 `VALIDATION_FAILED` with `details[]` of `{field, code, message}` — never the validator's raw text
- Pagination is cursor-only (`cursor` + `limit`); `limit` MUST be capped at 100 — never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST use the envelope in `api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}`; lists add `meta.pagination` `{next_cursor, has_more, limit}` and `data` is `[]` when empty
- DELETE returns 204 No Content — no body
- POST create returns 201 Created with the created resource in the body
- Zod schemas MUST use `.trim()` on string fields to sanitize whitespace
- The `asyncHandler` wrapper is MANDATORY for all Express route handlers — without it, rejected promises crash the process
