---
skill: error-handling-typescript
description: TypeScript error handling archetype — AppError class with FieldError details, one constructor per error code, one Express error middleware (NestJS filter delegates to it), HTTP mapping to the canonical error envelope matching the Go archetype
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

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Express 5.2, NestJS 12.1, class-validator 0.15 (tests/archetype-compile/typescript/run.sh).

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/error-handling-go.md` (Go). Both produce the error envelope in `~/.claude/skills/api/response-envelope.md` (`{"error": {code, message, details[], request_id, retryable}}`), so frontend clients can use a single error parsing strategy. If this file and the envelope ever disagree, the envelope wins.

Complete error handling system for TypeScript backend services (Express, NestJS). Every generated TypeScript service MUST follow this pattern.

## AppError Base Class

```typescript
// src/errors/app-error.ts

/**
 * FieldError is one entry of error.details[] — field-level problems for VALIDATION_FAILED.
 * `code` is a stable lower_snake identifier; `message` comes from a fixed catalog, never from
 * an exception or a validator's raw text.
 */
export interface FieldError {
  field: string;
  code: string;
  message: string;
}

/** The error envelope (api/response-envelope.md). Every error response uses it; it has no `data` key. */
export interface ErrorResponseBody {
  error: {
    code: string;
    message: string;
    details?: FieldError[];
    request_id: string;
    retryable: boolean;
  };
}

/**
 * AppError is the one application error type. Domain code throws AppErrors built by the
 * constructors in domain-errors.ts so the error middleware can map them to the envelope.
 */
export class AppError extends Error {
  public readonly code: string;          // UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, ...
  public readonly status: number;        // HTTP status — not serialized
  public readonly details: FieldError[]; // serialized as error.details
  public readonly retryable: boolean;    // serialized as error.retryable
  public readonly retryAfter: number;    // seconds; sets the Retry-After header (429/503)
  public cause?: unknown;                // wrapped cause — logged server-side, never serialized

  constructor(opts: {
    code: string;
    message: string; // user-safe; the UI shows it as-is
    status: number;
    details?: FieldError[];
    retryable?: boolean;
    retryAfter?: number;
    cause?: unknown;
  }) {
    super(opts.message);
    this.name = "AppError";
    this.code = opts.code;
    this.status = opts.status;
    this.details = opts.details ?? [];
    this.retryable = opts.retryable ?? false;
    this.retryAfter = opts.retryAfter ?? 0;
    this.cause = opts.cause;

    // Maintain proper stack trace in V8 engines
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /** Append a field-level problem (VALIDATION_FAILED). Returns this for chaining. */
  withField(field: string, code: string, message: string): this {
    this.details.push({ field, code, message });
    return this;
  }

  /** Wrap an underlying error for the log while keeping the client message clean. */
  withCause(err: unknown): this {
    this.cause = err;
    return this;
  }

  /** The client-visible body: only code, message, details, request_id and retryable leave the server. */
  toBody(requestId: string): ErrorResponseBody {
    return {
      error: {
        code: this.code,
        message: this.message,
        ...(this.details.length > 0 ? { details: this.details } : {}),
        request_id: requestId,
        retryable: this.retryable,
      },
    };
  }
}

/** Type guard — the TypeScript form of Go's errors.Is(err, apperr.ErrNotFound). */
export function isAppError(err: unknown, code?: string): err is AppError {
  return err instanceof AppError && (code === undefined || err.code === code);
}
```

## Error Taxonomy — Constructor Functions

The codes and statuses are the table in `api/response-envelope.md`. Messages are user-safe and fixed;
nothing from a parser, driver or upstream error reaches the client.

```typescript
// src/errors/domain-errors.ts

import { AppError, type FieldError } from "./app-error";

/** details[].message per lower_snake field code. Validator text (Zod, class-validator) is never sent. */
export const FIELD_MESSAGES = {
  required: "This field is required.",
  invalid_type: "This value has the wrong type.",
  invalid_format: "This value isn't in the right format.",
  invalid_value: "This value isn't allowed.",
  too_short: "This value is too short.",
  too_long: "This value is too long.",
  too_small: "This value is too small.",
  too_big: "This value is too large.",
  unknown_field: "This field isn't allowed.",
} as const;

/** A details[].code that has a catalog message — so FIELD_MESSAGES[code] is always a string. */
export type FieldCode = keyof typeof FIELD_MESSAGES;

// --- 400 MALFORMED_REQUEST: JSON parse errors, wrong content type, body too large ---

export function malformedRequest(cause?: unknown): AppError {
  return new AppError({ code: "MALFORMED_REQUEST", message: "The request could not be read.", status: 400, cause });
}

// --- 400 VALIDATION_FAILED: the input fails schema/validation; details[] lists the fields ---

export function validationError(field: string, code: string, message: string): AppError {
  return multiValidationError([{ field, code, message }]);
}

export function multiValidationError(fields: FieldError[]): AppError {
  return new AppError({ code: "VALIDATION_FAILED", message: "Some fields are invalid.", status: 400, details: fields });
}

// --- 422 BUSINESS_RULE_VIOLATION: a valid request rejected by a domain rule ---

export function businessRule(message: string): AppError {
  return new AppError({ code: "BUSINESS_RULE_VIOLATION", message, status: 422 });
}

// --- 401 UNAUTHENTICATED ---

export function unauthenticated(): AppError {
  return new AppError({ code: "UNAUTHENTICATED", message: "Sign in to continue.", status: 401 });
}

// --- 403 FORBIDDEN: authenticated, not allowed (function-level) ---

export function forbidden(): AppError {
  return new AppError({ code: "FORBIDDEN", message: "You don't have permission to do this.", status: 403 });
}

// --- 404 NOT_FOUND: missing OR another tenant's/owner's object (never 403 for those) ---

export function notFound(resource: string): AppError {
  return new AppError({ code: "NOT_FOUND", message: `${resource} not found.`, status: 404 });
}

// --- 409 CONFLICT: duplicate / version mismatch / state conflict ---

export function conflict(message: string): AppError {
  return new AppError({ code: "CONFLICT", message, status: 409 });
}

// --- 409 IDEMPOTENCY_KEY_REUSED: an Idempotency-Key replayed with a different body ---

export function idempotencyKeyReused(): AppError {
  return new AppError({
    code: "IDEMPOTENCY_KEY_REUSED",
    message: "This Idempotency-Key was already used with a different request.",
    status: 409,
  });
}

// --- 429 RATE_LIMITED ---

export function rateLimited(retryAfterSeconds: number): AppError {
  return new AppError({
    code: "RATE_LIMITED",
    message: "Too many requests. Try again shortly.",
    status: 429,
    retryable: true,
    retryAfter: retryAfterSeconds,
  });
}

// --- 500 INTERNAL ---

export function internal(cause?: unknown): AppError {
  return new AppError({ code: "INTERNAL", message: "Something went wrong.", status: 500, cause });
}

// --- 503 UNAVAILABLE: a dependency (DB, upstream API) failed or timed out ---
// The service name goes to the log (inside `cause`), not the client.

export function unavailable(service: string, cause?: unknown): AppError {
  return new AppError({
    code: "UNAVAILABLE",
    message: "The service is temporarily unavailable.",
    status: 503,
    retryable: true,
    retryAfter: 5,
    cause: new Error(`upstream ${service}`, { cause }),
  });
}
```

## Express Error Middleware

```typescript
// src/middleware/error-handler.ts

import { randomUUID } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import { AppError } from "../errors/app-error";
import { internal, malformedRequest } from "../errors/domain-errors";
import { logger } from "../lib/logger"; // structured logger (pino, winston, etc.)

/** The request's ID, set by the request-id middleware; created here if that middleware didn't run. */
export function requestIdOf(req: Request): string {
  const r = req as Request & { requestId?: string };
  r.requestId ||= randomUUID();
  return r.requestId;
}

/** express.json() (body-parser) failures that mean "the body could not be read". */
const BODY_PARSER_ERRORS = new Set([
  "entity.parse.failed", // malformed JSON
  "entity.too.large",    // over the express.json({ limit }) cap
  "charset.unsupported",
  "encoding.unsupported",
]);

/** Maps anything thrown to an AppError. Unknown errors become 500 INTERNAL; their text is never sent. */
export function toAppError(err: unknown): AppError {
  if (err instanceof AppError) return err;
  const type = (err as { type?: unknown } | null)?.type;
  if (typeof type === "string" && BODY_PARSER_ERRORS.has(type)) return malformedRequest(err);
  return internal(err);
}

/** writeErrorBody is the only function that writes an error response. */
export function writeErrorBody(res: Response, requestId: string, e: AppError): void {
  res.set("X-Request-Id", requestId);
  if (e.retryAfter > 0) res.set("Retry-After", String(e.retryAfter));
  if (e.status === 401) res.set("WWW-Authenticate", "Bearer");
  res.status(e.status).json(e.toBody(requestId));
}

/**
 * Express error middleware — the ONE place thrown errors become HTTP responses. Mount LAST.
 *
 * Usage:
 *   app.use(errorHandler);
 */
export function errorHandler(
  err: unknown,
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  if (res.headersSent) return next(err); // too late for an envelope; Express closes the connection

  const requestId = requestIdOf(req);
  const e = toAppError(err);

  if (e.status >= 500) {
    // The cause (driver/upstream message, stack) goes to the log under request_id — never to the client.
    logger.error("request failed", {
      code: e.code,
      request_id: requestId,
      method: req.method,
      path: req.path,
      err: e.cause ?? e,
    });
  }

  writeErrorBody(res, requestId, e);
}

/**
 * Async route handler wrapper — catches rejected promises and forwards to error middleware.
 *
 * Usage:
 *   router.get("/users/:id", asyncHandler(async (req, res) => {
 *     const user = await userService.get(req.params.id);
 *     res.json({ data: user, meta: newMeta(requestIdOf(req)) });
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

## NestJS Exception Filter

The filter is an adapter: it turns the exception into an `AppError` and hands it to the same
`writeErrorBody`, so Express and NestJS write the envelope in one place.

```typescript
// src/filters/app-error.filter.ts

import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  Logger,
} from "@nestjs/common";
import type { ValidationError } from "class-validator";
import type { Request, Response } from "express";
import { AppError } from "../errors/app-error";
import {
  FIELD_MESSAGES,
  type FieldCode,
  businessRule,
  conflict,
  forbidden,
  internal,
  malformedRequest,
  multiValidationError,
  notFound,
  rateLimited,
  unauthenticated,
  unavailable,
} from "../errors/domain-errors";
import { requestIdOf, toAppError, writeErrorBody } from "../middleware/error-handler";

@Catch()
export class AppErrorFilter implements ExceptionFilter {
  private readonly logger = new Logger(AppErrorFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const res = ctx.getResponse<Response>();
    const req = ctx.getRequest<Request>();
    const requestId = requestIdOf(req);
    const e = exception instanceof HttpException ? fromHttpException(exception) : toAppError(exception);

    if (e.status >= 500) {
      this.logger.error("request failed", { code: e.code, request_id: requestId, err: e.cause ?? e });
    }

    writeErrorBody(res, requestId, e);
  }
}

/**
 * Nest's own HttpExceptions (guards, pipes, unknown routes) get a code from their status and a
 * fixed message. The exception's own message is never sent — it can echo input or internals.
 */
const FROM_HTTP_STATUS: Record<number, () => AppError> = {
  400: () => malformedRequest(),
  401: () => unauthenticated(),
  403: () => forbidden(),
  404: () => notFound("Resource"),
  409: () => conflict("This request conflicts with the current state."),
  413: () => malformedRequest(),
  415: () => malformedRequest(),
  422: () => businessRule("This request can't be completed."),
  429: () => rateLimited(5),
  503: () => unavailable("upstream"),
};

function fromHttpException(ex: HttpException): AppError {
  const make = FROM_HTTP_STATUS[ex.getStatus()];
  return (make ? make() : internal()).withCause(ex);
}

/** class-validator constraint name → lower_snake details[].code. */
const CONSTRAINT_CODES: Record<string, FieldCode> = {
  isNotEmpty: "required",
  isDefined: "required",
  isString: "invalid_type",
  isInt: "invalid_type",
  isUuid: "invalid_format",
  isEnum: "invalid_value",
  minLength: "too_short",
  maxLength: "too_long",
  min: "too_small",
  max: "too_big",
  whitelistValidation: "unknown_field", // forbidNonWhitelisted
};

/**
 * ValidationPipe exceptionFactory: class-validator errors → 400 VALIDATION_FAILED with details[].
 * Constraint messages are never sent; each becomes a stable code + a catalog message.
 * Use it wherever a ValidationPipe is built:
 *   new ValidationPipe({ whitelist: true, transform: true, exceptionFactory: validationExceptionFactory })
 */
export function validationExceptionFactory(errors: ValidationError[]): AppError {
  const fields = errors.flatMap((e) =>
    Object.keys(e.constraints ?? {}).map((constraint) => {
      const code = CONSTRAINT_CODES[constraint] ?? "invalid_value";
      return { field: e.property, code, message: FIELD_MESSAGES[code] };
    }),
  ); // nested DTOs: recurse into e.children
  return multiValidationError(fields);
}

// Register globally in main.ts:
//   app.useGlobalFilters(new AppErrorFilter());
```

## HTTP Status Mapping Summary

| Constructor | HTTP Status | Code | When to Use |
|---|---|---|---|
| `malformedRequest(cause?)` | 400 | `MALFORMED_REQUEST` | Malformed JSON, wrong content type, body too large |
| `validationError(field, code, message)` / `multiValidationError(fields)` | 400 | `VALIDATION_FAILED` | Input fails schema/validation — `details[]` lists `{field, code, message}` |
| `unauthenticated()` | 401 | `UNAUTHENTICATED` | Missing, invalid or expired credentials (JWT, API key) |
| `forbidden()` | 403 | `FORBIDDEN` | Authenticated but not allowed (function-level) |
| `notFound(resource)` | 404 | `NOT_FOUND` | Doesn't exist, soft-deleted, **or belongs to another tenant/owner** |
| `conflict(message)` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `idempotencyKeyReused()` | 409 | `IDEMPOTENCY_KEY_REUSED` | Idempotency-Key replayed with a different body |
| `businessRule(message)` | 422 | `BUSINESS_RULE_VIOLATION` | Valid shape, rejected by a domain rule |
| `rateLimited(seconds)` | 429 | `RATE_LIMITED` | Too many requests (`Retry-After`, `retryable: true`) |
| `internal(cause?)` | 500 | `INTERNAL` | Unexpected server error — never expose details |
| `unavailable(service, cause?)` | 503 | `UNAVAILABLE` | A dependency failed or timed out (`Retry-After`, `retryable: true`) |

## Error Response Format

All error responses use the envelope from `api/response-envelope.md`. The HTTP status carries the
class, the `X-Request-Id` header equals `request_id`, and there is no `data` key:

```json
// 400 VALIDATION_FAILED:
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Some fields are invalid.",
    "details": [{ "field": "email", "code": "invalid_format", "message": "This value isn't in the right format." }],
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 404 NOT_FOUND (also for another tenant's or owner's widget — don't confirm it exists):
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Widget not found.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 409 CONFLICT:
{
  "error": {
    "code": "CONFLICT",
    "message": "This widget was changed by someone else. Reload and try again.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 503 UNAVAILABLE (with Retry-After: 5):
{
  "error": {
    "code": "UNAVAILABLE",
    "message": "The service is temporarily unavailable.",
    "request_id": "b7e1c2…",
    "retryable": true
  }
}

// 500 INTERNAL (the cause is in the log line with the same request_id):
{
  "error": {
    "code": "INTERNAL",
    "message": "Something went wrong.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}
```

## Usage in Service Layer

```typescript
// src/services/widget.service.ts

import { validationError, notFound, conflict } from "../errors/domain-errors";

export class WidgetService {
  constructor(private readonly repo: WidgetRepository) {}

  async create(input: CreateWidgetInput): Promise<Widget> {
    // Validate — throws 400 VALIDATION_FAILED
    if (!input.name?.trim()) {
      throw validationError("name", "required", "Name is required.");
    }

    // Check for duplicates — throws 409 CONFLICT
    const existing = await this.repo.findByName(input.tenantId, input.name);
    if (existing) {
      throw conflict("A widget with this name already exists.");
    }

    return this.repo.create(input);
  }

  async get(tenantId: string, id: string): Promise<Widget> {
    const widget = await this.repo.findById(tenantId, id);
    if (!widget) {
      throw notFound("Widget"); // also for another tenant's widget — never 403
    }
    return widget;
  }

  async update(tenantId: string, id: string, input: UpdateWidgetInput): Promise<Widget> {
    const existing = await this.get(tenantId, id);

    // Optimistic lock check — throws 409 CONFLICT on version mismatch
    if (input.version !== existing.version) {
      throw conflict("This widget was changed by someone else. Reload and try again.");
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
// Use isAppError (instanceof AppError, optionally by code) for error type checking
try {
  await widgetService.create(input);
} catch (err) {
  if (isAppError(err, "VALIDATION_FAILED")) {
    // err.details: FieldError[] — [{ field, code, message }]
  }
  if (isAppError(err, "NOT_FOUND")) {
    // err.status === 404
  }
  if (isAppError(err)) {
    // Any domain error — err.code, err.status, err.retryable
  }
  // Unknown error — rethrow; the error middleware maps it to 500 INTERNAL
  throw err;
}
```

## Barrel Export

```typescript
// src/errors/index.ts

export { AppError, isAppError, type FieldError, type ErrorResponseBody } from "./app-error";
export {
  FIELD_MESSAGES,
  type FieldCode,
  malformedRequest,
  validationError,
  multiValidationError,
  businessRule,
  unauthenticated,
  forbidden,
  notFound,
  conflict,
  idempotencyKeyReused,
  rateLimited,
  internal,
  unavailable,
} from "./domain-errors";
```

## Critical Rules

- Every error thrown from service/repo layers MUST be an `AppError` built by a constructor above; anything else becomes 500 `INTERNAL`
- Internal error messages (500, 503) MUST NOT leak to clients — always return the generic message
- No client-visible field ever contains an exception message (`err.message`, `String(err)`), SQL, a constraint name, a driver/upstream message, a path or a stack trace — the cause is logged with `request_id`
- Validation errors (400 `VALIDATION_FAILED`) carry `details[]` of `{field, code, message}` — lower_snake codes, catalog messages
- Business-rule rejections are 422 `BUSINESS_RULE_VIOLATION`; malformed bodies are 400 `MALFORMED_REQUEST`
- Every error body carries `request_id` (= the `X-Request-Id` header) and `retryable`, and has no `data` key
- `writeErrorBody` is the only code that writes an error response — `errorHandler` (Express) and `AppErrorFilter` (NestJS) both call it
- `instanceof AppError` / `isAppError` checks MUST work — never throw plain `Error` objects from domain code
- Log errors ONCE at the top of the call stack (middleware) — never log at every layer
- Create domain errors at the BOUNDARY where you know the error type (repo maps DB errors, service maps business rules)
- Panic recovery (uncaughtException / unhandledRejection) MUST be in the process — crashes MUST be caught
- 429 and 503 responses MUST include a `Retry-After` header
- 401 responses MUST include `WWW-Authenticate: Bearer` header
