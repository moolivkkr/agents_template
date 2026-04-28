# Express.js patterns for Node.js HTTP APIs.

## App Setup
```typescript
import express from "express"
import helmet from "helmet"
import cors from "cors"

const app = express()
app.use(helmet())
app.use(cors({ origin: process.env.ALLOWED_ORIGINS?.split(",") }))
app.use(express.json({ limit: "1mb" }))
app.use(requestIdMiddleware)

app.use("/api/v1/users", usersRouter)
app.use("/api/v1/auth", authRouter)
app.use(errorMiddleware)  // must be last
```

## Router
```typescript
// routes/users.ts
const router = Router()

router.get("/:id", asyncHandler(async (req, res) => {
    const user = await userService.getById(req.params.id)
    res.json({ data: user })
}))

export default router
```

## Async Handler Wrapper
```typescript
// Catches promise rejections and passes to error middleware
const asyncHandler = (fn: RequestHandler): RequestHandler =>
    (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next)
```
Always wrap async route handlers — unhandled rejections crash the process.

## Error Middleware
```typescript
// 4 arguments = error middleware (must be last app.use)
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
    if (err instanceof ValidationError) {
        return res.status(400).json({ error: err.message })
    }
    if (err instanceof NotFoundError) {
        return res.status(404).json({ error: err.message })
    }
    logger.error("unhandled error", { err })
    res.status(500).json({ error: "Internal server error" })
})
```

## Configuration
```typescript
// config.ts — validate at startup, fail fast
import { z } from "zod"

const EnvSchema = z.object({
    DATABASE_URL: z.string().url(),
    JWT_SECRET: z.string().min(32),
    PORT: z.coerce.number().default(3000),
})

export const config = EnvSchema.parse(process.env)
```

## Rules
- No business logic in route handlers — call service layer only
- `helmet()` and explicit CORS config always — never wildcard in production
- Validate request body with `zod` at route level before calling service
- Graceful shutdown: `server.close()` on SIGTERM, drain connections
- Never `console.log` — use structured logger (pino, winston)
