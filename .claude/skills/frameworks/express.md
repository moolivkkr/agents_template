# Express.js patterns for Node.js HTTP APIs.

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Express 5.2, helmet 8.3, cors 2.8, Zod 4.6, against the error, request-id and logger modules of the backend archetypes (tests/archetype-compile/typescript/run.sh).

The full stack (errors, auth, validation, CRUD routes) is `backend/archetypes/*-typescript.md`; this page is
the short form. Every body is the envelope in `api/response-envelope.md`.

## App Setup
```typescript
// src/app.ts
import express from "express"
import helmet from "helmet"
import cors from "cors"
import { config } from "./config"
import { requestId } from "./middleware/request-id"
import { errorHandler } from "./middleware/error-handler"
import usersRouter from "./routes/users"

const app = express()
app.use(helmet())
app.use(cors({ origin: config.ALLOWED_ORIGINS })) // an explicit list from config: never "*", never a fallback
app.use(express.json({ limit: "1mb" }))
app.use(requestId)
// … authMiddleware (backend/archetypes/auth-middleware-typescript.md) before the routes

app.use("/api/v1/users", usersRouter)
app.use(errorHandler)  // must be last

export default app
```

## Router
```typescript
// src/routes/users.ts
import { Router } from "express"
import { z } from "zod"
import { notFound } from "../errors/domain-errors"
import { asyncHandler } from "../middleware/async-handler"
import { userService } from "../services/user.service"
import type { AuthenticatedRequest } from "../types/express"

const router = Router()
const IdParams = z.object({ id: z.uuid() })

router.get("/:id", asyncHandler(async (req, res) => {
    const { tenantId, requestId } = req as AuthenticatedRequest // set by the auth and request-id middleware
    const params = IdParams.safeParse(req.params)
    if (!params.success) throw notFound("User") // a malformed id names no row
    const user = await userService.getById(tenantId, params.data.id) // tenant from the token, never the request
    res.json({ data: user, meta: { request_id: requestId } })
}))

export default router
```

## Async Handler Wrapper
```typescript
// src/middleware/async-handler.ts — catches promise rejections and passes them to the error middleware
import type { RequestHandler } from "express"

export const asyncHandler = (fn: RequestHandler): RequestHandler =>
    (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next)
```
Express 4: always wrap async route handlers — a rejection never reaches the error middleware and, unhandled,
exits the process. Express 5 forwards rejected promises from handlers and middleware to the error middleware
itself, so the wrapper is optional there (and harmless).

## Error Middleware
```typescript
// src/middleware/error-handler.ts — 4 arguments = error middleware (must be the last app.use).
// AppError and the error constructors: backend/archetypes/error-handling-typescript.md
import type { NextFunction, Request, Response } from "express"
import { AppError } from "../errors/app-error"
import { internal } from "../errors/domain-errors"
import { logger } from "../lib/logger"

export function errorHandler(err: unknown, req: Request, res: Response, next: NextFunction): void {
    if (res.headersSent) return next(err)
    const e = err instanceof AppError ? err : internal(err) // unknown → 500 INTERNAL; its text is never sent
    const requestId = (req as Request & { requestId?: string }).requestId ?? ""
    if (e.status >= 500) logger.error({ err: e.cause ?? e, code: e.code, request_id: requestId }, "request failed")
    if (e.retryAfter > 0) res.set("Retry-After", String(e.retryAfter))
    res.status(e.status).json(e.toBody(requestId)) // { error: { code, message, details?, request_id, retryable } }
}
```

## Configuration
```typescript
// src/config.ts — validate at startup, fail fast; no defaults for secrets or origins
import { z } from "zod"

const EnvSchema = z.object({
    DATABASE_URL: z.url(),
    JWT_SECRET: z.string().min(32),
    ALLOWED_ORIGINS: z.string().min(1).transform((s) => s.split(",").map((o) => o.trim())),
    PORT: z.coerce.number().int().min(1).max(65535).default(3000),
})

export const config = EnvSchema.parse(process.env)
```

## Rules
- No business logic in route handlers — call service layer only
- `helmet()` and explicit CORS config always — never wildcard in production
- Validate request body with `zod` at route level before calling service
- Graceful shutdown: `server.close()` on SIGTERM, drain connections
- Never `console.log` — use structured logger (pino, winston)
