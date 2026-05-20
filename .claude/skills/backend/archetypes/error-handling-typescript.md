---
skill: error-handling-typescript
description: TypeScript error handling archetype — AppError class, domain error subclasses, Express/NestJS middleware, HTTP mapping, structured error responses matching Go archetype output
version: "1.0"
tags:
  - typescript
  - errors
  - middleware
  - archetype
  - backend
  - express
  - nestjs
---

# Error Handling Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/error-handling.md` (Go). Both produce identical error response envelopes so frontend clients can use a single error parsing strategy.

Complete error handling system for TypeScript backend services (Express, NestJS, Fastify). Every generated TypeScript service MUST follow this pattern.

## AppError Base Class

```typescript
// src/errors/app-error.ts

 * AppError is the base application error type.
 * All domain errors MUST extend this class so error middleware can map them to HTTP responses.
 * Produces the same JSON envelope as the Go archetype:
 * {"error": {"code": "...", "message": "...", "details": {...}}}
export class AppError extends Error {
  public readonly code: string;
  public readonly httpStatus: number;
  public readonly details: Record<string, unknown>;
  public readonly cause?: Error;

  constructor(opts: {
    code: string;
    message: string;
    httpStatus: number;
    details?: Record<string, unknown>;
    cause?: Error;
  }) {
    super(opts.message);
    this.name = "AppError";
    this.code = opts.code;
    this.httpStatus = opts.httpStatus;
    this.details = opts.details ?? {};
    this.cause = opts.cause;

    // Maintain proper stack trace in V8 engines
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /** Add structured context to the error. Returns this for chaining. */
  withDetails(key: string, value: unknown): this {
    (this.details as Record<string, unknown>)[key] = value;
    return this;
  }

  /** Wrap an underlying error for debugging while keeping the client message clean. */
  withCause(err: Error): this {
    (this as any).cause = err;
    return this;
  }

  /** Serialize to the standard error response format. */
  toJSON(): ErrorResponseBody {
    return {
      error: {
        code: this.code,
        message: this.message,
        ...(Object.keys(this.details).length > 0 ? { details: this.details } : {}),
      },
    };
  }
}

/** Standard JSON error response body — matches Go archetype exactly. */
export interface ErrorResponseBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
```

## Domain Error Subclasses

```typescript
// src/errors/domain-errors.ts

import { AppError } from "./app-error";

// --- 400 Bad Request: Malformed Request (JSON parse errors, wrong content type) ---

export class BadRequestError extends AppError {
  constructor(reason: string, cause?: Error) {
    super({
      code: "BAD_REQUEST",
      message: reason,
      httpStatus: 400,
      cause,
    });
    this.name = "BadRequestError";
  }
}

// --- 422 Unprocessable Entity: Business Validation Errors ---
// Use 422 for well-formed requests that fail domain/business validation rules.
// Use 400 (above) for malformed JSON, wrong content type, or request parsing errors.

export class ValidationError extends AppError {
  constructor(field: string, reason: string, cause?: Error) {
    super({
      code: "VALIDATION_ERROR",
      message: `invalid value for field '${field}'`,
      httpStatus: 422,
      details: { field, reason },
      cause,
    });
    this.name = "ValidationError";
  }
}

export class MultiValidationError extends AppError {
  constructor(fieldErrors: Record<string, string>) {
    super({
      code: "VALIDATION_ERROR",
      message: "one or more fields failed validation",
      httpStatus: 422,
      details: { fields: fieldErrors },
    });
    this.name = "MultiValidationError";
  }
}

// --- 401 Unauthorized: Authentication Errors ---

export class UnauthorizedError extends AppError {
  constructor(reason: string = "authentication required") {
    super({
      code: "UNAUTHORIZED",
      message: reason,
      httpStatus: 401,
    });
    this.name = "UnauthorizedError";
  }
}

// --- 403 Forbidden: Authorization Errors ---

export class ForbiddenError extends AppError {
  constructor(action: string, resource: string) {
    super({
      code: "FORBIDDEN",
      message: `insufficient permissions to ${action} ${resource}`,
      httpStatus: 403,
      details: { action, resource },
    });
    this.name = "ForbiddenError";
  }
}

// --- 404 Not Found ---

export class NotFoundError extends AppError {
  constructor(resource: string, identifier?: string) {
    const message = identifier
      ? `${resource} '${identifier}' not found`
      : `${resource} not found`;
    super({
      code: "NOT_FOUND",
      message,
      httpStatus: 404,
      details: { resource, ...(identifier ? { identifier } : {}) },
    });
    this.name = "NotFoundError";
  }
}

// --- 409 Conflict: Duplicate / Version Mismatch ---

export class ConflictError extends AppError {
  constructor(resource: string, reason: string) {
    super({
      code: "CONFLICT",
      message: `${resource} conflict: ${reason}`,
      httpStatus: 409,
      details: { resource, reason },
    });
    this.name = "ConflictError";
  }
}

// --- 429 Too Many Requests ---

export class RateLimitError extends AppError {
  public readonly retryAfterSeconds: number;

  constructor(retryAfterSeconds: number) {
    super({
      code: "RATE_LIMITED",
      message: "too many requests — please retry later",
      httpStatus: 429,
      details: { retry_after_seconds: retryAfterSeconds },
    });
    this.name = "RateLimitError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

// --- 500 Internal Server Error ---

export class InternalError extends AppError {
  constructor(cause?: Error) {
    super({
      code: "INTERNAL_ERROR",
      message: "an unexpected error occurred",
      httpStatus: 500,
      cause,
    });
    this.name = "InternalError";
  }
}

// --- 502 Bad Gateway: Upstream Failure ---

export class UpstreamError extends AppError {
  constructor(service: string, cause?: Error) {
    super({
      code: "UPSTREAM_ERROR",
      message: `upstream service '${service}' is unavailable`,
      httpStatus: 502,
      details: { service },
      cause,
    });
    this.name = "UpstreamError";
  }
}
```

## Express Error Middleware

```typescript
// src/middleware/error-handler.ts

import { Request, Response, NextFunction } from "express";
import { AppError } from "../errors/app-error";
import { RateLimitError } from "../errors/domain-errors";
import { logger } from "../lib/logger"; // structured logger (pino, winston, etc.)

 * Express error middleware. Mount LAST in the middleware stack.
 * Maps AppError instances to structured HTTP responses.
 * Usage:
 *   app.use(errorHandler);
export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction,
): void {
  const requestId = (req as any).requestId ?? req.headers["x-request-id"] ?? "";

  if (err instanceof AppError) {
    // Log internal errors with full detail; client gets sanitized message
    if (err.httpStatus >= 500) {
      logger.error("internal error", {
        code: err.code,
        message: err.message,
        cause: err.cause?.message,
        stack: err.cause?.stack,
        request_id: requestId,
        method: req.method,
        path: req.path,
      });
    }

    // Add Retry-After header for rate limit errors
    if (err instanceof RateLimitError) {
      res.set("Retry-After", String(err.retryAfterSeconds));
    }

    // Add WWW-Authenticate header for 401 errors
    if (err.httpStatus === 401) {
      res.set("WWW-Authenticate", "Bearer");
    }

    res.status(err.httpStatus).json(err.toJSON());
    return;
  }

  // Unknown error type — treat as 500, never expose message
  logger.error("unmapped error", {
    error: err.message,
    stack: err.stack,
    request_id: requestId,
    method: req.method,
    path: req.path,
  });

  res.status(500).json({
    error: {
      code: "INTERNAL_ERROR",
      message: "an unexpected error occurred",
    },
  });
}

 * Async route handler wrapper — catches rejected promises and forwards to error middleware.
 * Usage:
 *   router.get("/users/:id", asyncHandler(async (req, res) => {
 *     const user = await userService.get(req.params.id);
 *     res.json({ data: user });
 *   }));
export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<void>,
) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}
```

## NestJS Exception Filter

```typescript
// src/filters/app-error.filter.ts

import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  Logger,
} from "@nestjs/common";
import { Request, Response } from "express";
import { AppError } from "../errors/app-error";
import { RateLimitError } from "../errors/domain-errors";

@Catch()
export class AppErrorFilter implements ExceptionFilter {
  private readonly logger = new Logger(AppErrorFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const res = ctx.getResponse<Response>();
    const req = ctx.getRequest<Request>();
    const requestId = (req as any).requestId ?? req.headers["x-request-id"] ?? "";

    // Handle AppError (domain errors)
    if (exception instanceof AppError) {
      if (exception.httpStatus >= 500) {
        this.logger.error("Internal error", {
          code: exception.code,
          message: exception.message,
          cause: exception.cause?.message,
          request_id: requestId,
        });
      }

      if (exception instanceof RateLimitError) {
        res.set("Retry-After", String(exception.retryAfterSeconds));
      }
      if (exception.httpStatus === 401) {
        res.set("WWW-Authenticate", "Bearer");
      }

      res.status(exception.httpStatus).json(exception.toJSON());
      return;
    }

    // Handle NestJS HttpException
    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      res.status(status).json({
        error: {
          code: status >= 500 ? "INTERNAL_ERROR" : "BAD_REQUEST",
          message: exception.message,
        },
      });
      return;
    }

    // Unknown error — 500
    this.logger.error("Unmapped error", {
      error: exception instanceof Error ? exception.message : String(exception),
      stack: exception instanceof Error ? exception.stack : undefined,
      request_id: requestId,
    });

    res.status(500).json({
      error: {
        code: "INTERNAL_ERROR",
        message: "an unexpected error occurred",
      },
    });
  }
}

// Register globally in main.ts:
//   app.useGlobalFilters(new AppErrorFilter());
```

## HTTP Status Mapping Summary

| Error Class | HTTP Status | Code | When to Use |
|---|---|---|---|
| `BadRequestError` | 400 | `BAD_REQUEST` | Malformed JSON, wrong content type, request parsing failure |
| `ValidationError` | 422 | `VALIDATION_ERROR` | Well-formed request that fails business/domain validation |
| `MultiValidationError` | 422 | `VALIDATION_ERROR` | Multiple field validation failures |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` | Missing or invalid credentials (JWT, API key) |
| `ForbiddenError` | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `NotFoundError` | 404 | `NOT_FOUND` | Resource does not exist or was soft-deleted |
| `ConflictError` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `RateLimitError` | 429 | `RATE_LIMITED` | Too many requests from tenant/user |
| `InternalError` | 500 | `INTERNAL_ERROR` | Unexpected server error — never expose details |
| `UpstreamError` | 502 | `UPSTREAM_ERROR` | External service failure |

## Error Response Format

All error responses use the same envelope format as the Go archetype:

```json
// 422 Validation Error:
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "invalid value for field 'email'",
    "details": { "field": "email", "reason": "invalid format" }
  }
}

// 404 Not Found:
{
  "error": {
    "code": "NOT_FOUND",
    "message": "widget 'abc-123' not found",
    "details": { "resource": "widget", "identifier": "abc-123" }
  }
}

// 409 Conflict:
{
  "error": {
    "code": "CONFLICT",
    "message": "widget conflict: version mismatch — reload and retry",
    "details": { "resource": "widget", "reason": "version mismatch" }
  }
}

// 500 Internal Error:
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "an unexpected error occurred"
  }
}
```

## Usage in Service Layer

```typescript
// src/services/widget.service.ts

import {
  ValidationError,
  NotFoundError,
  ConflictError,
} from "../errors/domain-errors";

export class WidgetService {
  constructor(private readonly repo: WidgetRepository) {}

  async create(input: CreateWidgetInput): Promise<Widget> {
    // Validate — throws 422 on failure
    if (!input.name?.trim()) {
      throw new ValidationError("name", "name is required");
    }

    // Check for duplicates — throws 409 on conflict
    const existing = await this.repo.findByName(input.tenantId, input.name);
    if (existing) {
      throw new ConflictError("widget", `name '${input.name}' already exists`);
    }

    return this.repo.create(input);
  }

  async get(tenantId: string, id: string): Promise<Widget> {
    const widget = await this.repo.findById(tenantId, id);
    if (!widget) {
      throw new NotFoundError("widget", id);
    }
    return widget;
  }

  async update(tenantId: string, id: string, input: UpdateWidgetInput): Promise<Widget> {
    const existing = await this.get(tenantId, id);

    // Optimistic lock check — throws 409 on version mismatch
    if (input.version !== existing.version) {
      throw new ConflictError("widget", "version mismatch — reload and retry");
    }

    return this.repo.update(id, {
      ...input,
      version: existing.version + 1,
    });
  }
}
```

## Type Checking Errors

```typescript
// Use instanceof for error type checking
try {
  await widgetService.create(input);
} catch (err) {
  if (err instanceof ValidationError) {
    // Access err.details.field, err.details.reason
  }
  if (err instanceof NotFoundError) {
    // Access err.details.resource, err.details.identifier
  }
  if (err instanceof AppError) {
    // Any domain error — access err.code, err.httpStatus, err.details
  }
  // Unknown error — rethrow or wrap
  throw err;
}
```

## Barrel Export

```typescript
// src/errors/index.ts

export { AppError, type ErrorResponseBody } from "./app-error";
export {
  BadRequestError,
  ValidationError,
  MultiValidationError,
  UnauthorizedError,
  ForbiddenError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  InternalError,
  UpstreamError,
} from "./domain-errors";
```

## Critical Rules

- Every error thrown from service/repo layers MUST be an `AppError` subclass
- Internal error messages (500, 502) MUST NOT leak to clients — always return generic message
- Validation errors (422) SHOULD include the field name and reason in `details`
- Bad request errors (400) are for malformed JSON/request parsing — NOT business validation
- `instanceof` checks MUST work — never throw plain `Error` objects from domain code
- Log errors ONCE at the top of the call stack (middleware) — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type
- Panic recovery (uncaughtException / unhandledRejection) MUST be in the process — crashes MUST be caught
- Rate limit responses MUST include `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
- Error response format MUST match the Go archetype: `{"error": {"code": "...", "message": "...", "details": {...}}}`
