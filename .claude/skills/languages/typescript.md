> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# TypeScript Patterns

## Compiler Config
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}
```
`strict: true` is mandatory. Never use `any` — use `unknown` + type narrowing.

## Types
- `interface` for object shapes; `type` for unions, intersections, mapped types
- `satisfies` for type-checked literals preserving narrow types
- `readonly` on function parameters and return types where appropriate
- Explicit return types on all exported functions

```typescript
// Discriminated unions — primary polymorphism pattern
type ApiResponse =
  | { status: "success"; data: User }
  | { status: "error"; error: { code: string; message: string } };

// satisfies: validates type, preserves narrow inference
const ROUTES = {
  home: "/",
  users: "/users",
} satisfies Record<string, string>;
// typeof ROUTES.home is "/" (literal), not string

// as const for readonly literal types
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"] as const;
type HttpMethod = (typeof HTTP_METHODS)[number];

// Branded types for nominal safety
type UserId = string & { readonly __brand: "UserId" };
type TenantId = string & { readonly __brand: "TenantId" };
```

## Type System Deep Patterns

```typescript
// Generics with constraints
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] { return obj[key]; }
function merge<T extends object, U extends object>(a: T, b: U): T & U { return { ...a, ...b }; }

// Conditional types
type AsyncReturnType<T extends (...args: any[]) => Promise<any>> =
  T extends (...args: any[]) => Promise<infer R> ? R : never;

// Custom mapped types
type DeepReadonly<T> = { readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K] };
type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

// Template literal types
type EventName = `${string}.created` | `${string}.updated` | `${string}.deleted`;
type EndpointKey = `${HttpMethod} /${string}`;

// Type guards
function isWidget(value: unknown): value is Widget {
  return typeof value === "object" && value !== null && "id" in value && "name" in value;
}
function assertWidget(value: unknown): asserts value is Widget {
  if (!isWidget(value)) throw new Error("Expected Widget");
}

// Exhaustiveness check in switch
const _exhaustive: never = event; // compile error if case missed
```

## Error Handling

```typescript
// Custom error hierarchy
class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = this.constructor.name;
    Object.setPrototypeOf(this, new.target.prototype);
  }
  toJSON(): { code: string; message: string } {
    return { code: this.code, message: this.message };
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) { super("NOT_FOUND", `${resource} ${id} not found`, 404); }
}
class ValidationError extends AppError {
  constructor(public readonly fields: Array<{ field: string; message: string }>) {
    super("VALIDATION_ERROR", "Validation failed", 422);
  }
}
class MultiValidationError extends AppError {
  constructor(public readonly fieldErrors: Record<string, string>) { super("VALIDATION_ERROR", "Validation failed", 422); }
  override toJSON() { return { code: this.code, message: this.message, details: this.fieldErrors }; }
}
class ConflictError extends AppError {
  constructor(resource: string, detail: string) { super("CONFLICT", `${resource} conflict: ${detail}`, 409); }
}
class UnauthorizedError extends AppError { constructor(detail = "authentication required") { super("UNAUTHORIZED", detail, 401); } }
class ForbiddenError extends AppError { constructor(detail = "insufficient permissions") { super("FORBIDDEN", detail, 403); } }
class InternalError extends AppError { constructor(cause?: Error) { super("INTERNAL_ERROR", "An internal error occurred", 500, { cause }); } }

// Result<T, E> pattern for library/validator code
type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E };
function unwrap<T, E extends Error>(result: Result<T, E>): T {
  if (!result.ok) throw result.error;
  return result.value;
}

// Error cause chain (ES2022+)
function logErrorChain(err: Error): void {
  let current: Error | undefined = err;
  while (current) {
    logger.error(`${current.name}: ${current.message}`);
    current = current.cause instanceof Error ? current.cause : undefined;
  }
}

// Express error middleware (MUST be 4-arg — Express uses arity detection)
function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof AppError) { res.status(err.statusCode).json({ error: err.toJSON() }); return; }
  logger.error("Unhandled error", { error: err.message, stack: err.stack });
  res.status(500).json({ error: { code: "INTERNAL_ERROR", message: "An internal error occurred" } });
}
```

- `throw` in service/handler for exceptional errors; `Result<T,E>` in library code
- `try/catch` only at boundaries (API handlers, event handlers)
- `toJSON()` controls API serialization — never exposes stack traces
- ErrorBoundary wraps React component trees

## Runtime Validation (Zod)

```typescript
import { z } from "zod";

const CreateWidgetSchema = z.object({
  name: z.string().trim().min(1).max(255),
  priority: z.number().int().min(0).max(10).default(0),
  tags: z.array(z.string().min(1)).max(20).default([]),
});
type CreateWidgetInput = z.infer<typeof CreateWidgetSchema>;

// Env validation — fail fast at startup
const EnvSchema = z.object({
  DATABASE_URL: z.string().url(),
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  JWT_SECRET: z.string().min(32),
});
export const env = EnvSchema.parse(process.env);
```

## Async/Await Patterns

```typescript
// Promise.all — all must succeed (fail-fast)
const [profile, orders, notifications] = await Promise.all([
  userService.getProfile(userId),
  orderService.listRecent(userId, 10),
  notificationService.getUnread(userId),
]);

// Promise.allSettled — partial results acceptable
const results = await Promise.allSettled(recipients.map(email => emailService.send(email)));

// Promise.race for timeouts
async function fetchWithTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  const timeout = new Promise<never>((_, reject) => setTimeout(() => reject(new Error(`Timeout`)), timeoutMs));
  return Promise.race([promise, timeout]);
}

// AbortController — cancel on unmount/re-request
useEffect(() => {
  const controller = new AbortController();
  fetchData(controller.signal).then(setData).catch(err => { if (!controller.signal.aborted) setError(err); });
  return () => controller.abort();
}, []);

// Async generators for pagination
async function* paginateAll<T>(
  fetcher: (cursor: string) => Promise<{ items: T[]; cursor: string; hasMore: boolean }>,
): AsyncGenerator<T[]> {
  let cursor = ""; let hasMore = true;
  while (hasMore) { const page = await fetcher(cursor); yield page.items; cursor = page.cursor; hasMore = page.hasMore; }
}

// Retry with exponential backoff
async function withRetry<T>(fn: () => Promise<T>, maxRetries = 3, baseDelayMs = 100): Promise<T> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try { return await fn(); }
    catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < maxRetries) await new Promise(r => setTimeout(r, baseDelayMs * Math.pow(2, attempt)));
    }
  }
  throw lastError;
}
```

- Never use `async void` except in top-level event handlers
- Always `await` async returns — dangling promises are bugs

## Module System

```typescript
// ESM default: "type": "module" in package.json, "module": "NodeNext" in tsconfig
// Named exports preferred (tree-shakeable)
export function createWidget(input: CreateInput): Widget { /* ... */ }
export type { Widget, CreateInput };

// Dynamic imports for code splitting
const Dashboard = React.lazy(() => import("./pages/Dashboard.js"));
async function getCache(): Promise<ICache> {
  if (process.env.REDIS_URL) { const { RedisCache } = await import("./redis-cache.js"); return new RedisCache(process.env.REDIS_URL); }
  const { InMemoryCache } = await import("./memory-cache.js"); return new InMemoryCache();
}

// Path aliases: "@/*" -> "src/*" in tsconfig paths
// Barrel index.ts ONLY at module boundaries — never for internal re-exports
// .js extensions in import paths for ESM compatibility
// export type for type-only exports — no runtime cost
```

## Performance

- Named imports from tree-shakeable ESM packages (`import { x } from "lodash-es"`)
- `React.lazy()` + `Suspense` for route-level code splitting
- `useMemo`/`useCallback` only when profiling shows re-render overhead
- Virtual lists (`@tanstack/react-virtual`) for datasets > 100 items
- `AbortController` for every fetch

## Decorators

```typescript
// TS 5.x Stage 3 decorators (no experimentalDecorators needed)
// NestJS uses legacy decorators — set experimentalDecorators: true

// Method decorator: retry
function retry(maxAttempts = 3) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const original = descriptor.value;
    descriptor.value = async function (...args: any[]) {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try { return await original.apply(this, args); }
        catch (err) { if (attempt === maxAttempts) throw err; await new Promise(r => setTimeout(r, 100 * attempt)); }
      }
    };
    return descriptor;
  };
}

// NestJS patterns
@Controller("widgets")
class WidgetController {
  @Get(":id")
  async findOne(@Param("id") id: string): Promise<Widget> { return this.widgetService.get(id); }
}

const CurrentUser = createParamDecorator((data: unknown, ctx: ExecutionContext) => ctx.switchToHttp().getRequest().user);
const Roles = (...roles: string[]) => SetMetadata("roles", roles);
```

## Rules
- Never `// @ts-ignore` — fix the type
- No barrel `index.ts` that re-exports everything from subdirectories
- ESLint with `@typescript-eslint/recommended-type-checked`
- Format with Prettier
- `tsx` for scripts, `ts-node` only as last resort
