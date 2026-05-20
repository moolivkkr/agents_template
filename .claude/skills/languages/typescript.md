> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# TypeScript patterns and conventions for type-safe, maintainable applications.

## Compiler Config
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true
  }
}
```
Always use strict mode. Treat compiler errors as build failures.

## Types
- `interface` for object shapes (extendable); `type` for unions, intersections, mapped types
- Never use `any` — use `unknown` + type narrowing instead
- `satisfies` operator for type-checked literals
- Use `readonly` on function parameters and return types where appropriate

```typescript
// Good
function processUser(user: Readonly<User>): Readonly<ProcessedUser> { ... }

// Bad
function processUser(user: any): any { ... }
```

## Error Handling
```typescript
// Result pattern for expected failures
type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E }

function parseConfig(raw: unknown): Result<Config, ValidationError> {
  const parsed = ConfigSchema.safeParse(raw)
  if (!parsed.success) return { ok: false, error: new ValidationError(parsed.error) }
  return { ok: true, value: parsed.data }
}
```
- Use `zod` for runtime validation at system boundaries
- Never throw in library code — return Result types

## Async
- `async/await` over raw Promises
- `Promise.allSettled` when you need all results regardless of failures
- `Promise.all` only when all must succeed together

## Module Conventions
```
src/
  domain/         # types, entities
  services/       # business logic
  repositories/   # data access
  api/            # HTTP handlers
  index.ts        # barrel export (public API only)
```
- Barrel exports only at module boundaries — not inside modules
- Path aliases in `tsconfig.json`: `@/` → `src/`

## Runtime Validation
```typescript
import { z } from "zod"

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  createdAt: z.coerce.date(),
})
type User = z.infer<typeof UserSchema>
```
Use `zod` for all external data (API input, env vars, config files).

## Strict Mode Rules

```typescript
// tsconfig.json — non-negotiable settings
{
  "compilerOptions": {
    "strict": true,                        // enables all strict checks
    "noUncheckedIndexedAccess": true,       // array/object index returns T | undefined
    "exactOptionalPropertyTypes": true,     // undefined !== missing
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}

// Never use `any` — use `unknown` + type narrowing
function processInput(input: unknown): string {
  if (typeof input === "string") return input.toUpperCase();
  if (typeof input === "number") return String(input);
  throw new Error(`Unexpected input type: ${typeof input}`);
}

// Explicit return types on all exported functions
export function calculateTotal(items: readonly LineItem[]): number {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

// Discriminated unions over type assertions
type ApiResponse =
  | { status: "success"; data: User }
  | { status: "error"; error: { code: string; message: string } };

function handleResponse(res: ApiResponse) {
  switch (res.status) {
    case "success": return res.data;   // TypeScript narrows to success branch
    case "error": throw new AppError(res.error.code, res.error.message);
  }
}

// `satisfies` for type-safe object literals with inferred narrow types
const ROUTES = {
  home: "/",
  users: "/users",
  user: "/users/:id",
} satisfies Record<string, string>;
// typeof ROUTES.home is "/" (literal), not string
```

- `strict: true` is mandatory — never ship with it off
- No `any` anywhere — use `unknown` + narrowing, generics, or `satisfies`
- Explicit return types on exported functions prevent accidental API changes
- Discriminated unions replace `instanceof` checks and type assertions
- `satisfies` validates types while preserving narrow inferred types

## Performance

```typescript
// Bundle-aware imports — always use named imports for tree-shaking
import { debounce } from "lodash-es";        // tree-shakeable ESM
// NOT: import _ from "lodash";              // imports entire library

// Lazy loading with React.lazy + Suspense
const Dashboard = React.lazy(() => import("./pages/Dashboard"));

function App() {
  return (
    <Suspense fallback={<Skeleton />}>
      <Dashboard />
    </Suspense>
  );
}

// Memoization — only when you've measured a performance issue
const ExpensiveList = React.memo(function ExpensiveList({ items }: Props) {
  return <ul>{items.map((item) => <li key={item.id}>{item.name}</li>)}</ul>;
});

// useMemo / useCallback — for referential stability, not premature optimization
function ParentComponent({ data }: { data: RawData[] }) {
  const processed = useMemo(
    () => data.filter(isValid).map(transform),
    [data],
  );

  const handleClick = useCallback(
    (id: string) => { navigate(`/items/${id}`); },
    [navigate],
  );

  return <ChildComponent items={processed} onClick={handleClick} />;
}

// Virtual lists for large datasets — never render 10,000+ DOM nodes
import { useVirtualizer } from "@tanstack/react-virtual";

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
  });
  return (
    <div ref={parentRef} style={{ overflow: "auto", height: 600 }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((vItem) => (
          <div key={vItem.key} style={{ transform: `translateY(${vItem.start}px)` }}>
            {items[vItem.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}

// AbortController for cancellable requests
async function fetchWithCancel(url: string, signal: AbortSignal): Promise<Data> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new HttpError(res.status);
  return res.json();
}

// In React — cancel on unmount
useEffect(() => {
  const controller = new AbortController();
  fetchData(controller.signal).then(setData).catch((err) => {
    if (!controller.signal.aborted) setError(err);
  });
  return () => controller.abort();
}, []);
```

- Use named imports from tree-shakeable ESM packages
- `React.lazy()` + `Suspense` for route-level code splitting
- `useMemo` / `useCallback` only when profiling shows re-render overhead
- Virtual lists (`@tanstack/react-virtual`) for datasets > 100 items
- `AbortController` for every fetch — cancel on unmount, cancel on re-request

## Error Handling

```typescript
// Custom error classes with machine-readable codes
class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "AppError";
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super("NOT_FOUND", `${resource} ${id} not found`, 404);
    this.name = "NotFoundError";
  }
}

class ValidationError extends AppError {
  constructor(
    public readonly fields: Array<{ field: string; message: string }>,
  ) {
    super("VALIDATION_ERROR", "Validation failed", 422);
    this.name = "ValidationError";
  }
}

// Result<T, E> pattern for expected failures — no exceptions for control flow
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

function parseConfig(raw: unknown): Result<Config, ValidationError> {
  const parsed = ConfigSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      ok: false,
      error: new ValidationError(
        parsed.error.issues.map((i) => ({ field: i.path.join("."), message: i.message })),
      ),
    };
  }
  return { ok: true, value: parsed.data };
}

// try/catch only at boundaries (API handlers, event handlers)
app.post("/users", async (req, res) => {
  try {
    const user = await userService.create(req.body);
    res.status(201).json({ data: user });
  } catch (err) {
    if (err instanceof AppError) {
      res.status(err.statusCode).json({
        error: { code: err.code, message: err.message },
      });
    } else {
      logger.error("Unhandled error", { err });
      res.status(500).json({
        error: { code: "INTERNAL_ERROR", message: "Something went wrong" },
      });
    }
  }
});

// ErrorBoundary for React components
class ErrorBoundary extends React.Component<
  { fallback: React.ReactNode; children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, info);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
```

- Custom error classes extending `Error` with machine-readable `code` and `statusCode`
- `Result<T, E>` for expected failures — reserves exceptions for truly unexpected errors
- `try/catch` only at system boundaries — API handlers, event handlers, top-level
- Typed error responses from APIs: `{ error: { code, message, details? } }`
- `ErrorBoundary` wraps React component trees — prevents full-page crashes
- Never swallow errors silently — always log, report, or propagate

## Rules
- Never disable TypeScript with `// @ts-ignore` — fix the type
- No barrel `index.ts` that re-exports everything from subdirectories
- ESLint with `@typescript-eslint/recommended-type-checked`
- Format with Prettier (no config debates)
- `tsx` for scripts, `ts-node` only as last resort

## Async/Await Patterns

```typescript
// --- Promise creation ---
function fetchUser(id: string): Promise<User> {
  return new Promise((resolve, reject) => {
    db.query("SELECT * FROM users WHERE id = $1", [id])
      .then((rows) => {
        if (rows.length === 0) reject(new NotFoundError("user", id));
        else resolve(rows[0] as User);
      })
      .catch(reject);
  });
}

// --- async/await with structured error handling ---
async function createOrder(input: CreateOrderInput): Promise<Order> {
  // Validate first — throw before any side effects
  const parsed = CreateOrderSchema.parse(input);

  try {
    const order = await orderRepo.create(parsed);
    await notificationService.send(order.userId, "order.created");
    return order;
  } catch (err) {
    if (err instanceof UniqueConstraintError) {
      throw new ConflictError("order", "duplicate order reference");
    }
    throw err; // re-throw unexpected errors
  }
}

// --- Promise.all — all must succeed ---
// Use when all operations are required and independent
async function loadDashboard(userId: string): Promise<Dashboard> {
  const [profile, orders, notifications] = await Promise.all([
    userService.getProfile(userId),
    orderService.listRecent(userId, 10),
    notificationService.getUnread(userId),
  ]);
  return { profile, orders, notifications };
}

// --- Promise.allSettled — collect all results regardless of failures ---
// Use when partial results are acceptable
async function sendBulkEmails(
  recipients: string[],
): Promise<{ sent: number; failed: number }> {
  const results = await Promise.allSettled(
    recipients.map((email) => emailService.send(email)),
  );

  const sent = results.filter((r) => r.status === "fulfilled").length;
  const failed = results.filter((r) => r.status === "rejected").length;

  for (const result of results) {
    if (result.status === "rejected") {
      logger.warn("Email send failed", { error: result.reason });
    }
  }

  return { sent, failed };
}

// --- Promise.race — first to resolve wins ---
// Use for timeouts or fastest-response patterns
async function fetchWithTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
): Promise<T> {
  const timeout = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs),
  );
  return Promise.race([promise, timeout]);
}

// --- AbortController for cancellation ---
async function fetchData(
  url: string,
  signal: AbortSignal,
): Promise<unknown> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new HttpError(response.status, await response.text());
  }
  return response.json();
}

// Cancel on timeout
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 5000);
try {
  const data = await fetchData("/api/widgets", controller.signal);
} finally {
  clearTimeout(timeoutId);
}

// --- Async iterators ---
async function* paginateAll<T>(
  fetcher: (cursor: string) => Promise<{ items: T[]; cursor: string; hasMore: boolean }>,
): AsyncGenerator<T[], void, unknown> {
  let cursor = "";
  let hasMore = true;

  while (hasMore) {
    const page = await fetcher(cursor);
    yield page.items;
    cursor = page.cursor;
    hasMore = page.hasMore;
  }
}

// Usage
for await (const batch of paginateAll((cursor) => widgetService.list(tenantId, { cursor, pageSize: 100 }))) {
  await processBatch(batch);
}

// --- Sequential async processing with reduce ---
async function processSequentially(items: string[]): Promise<void> {
  await items.reduce(
    async (prevPromise, item) => {
      await prevPromise;
      await processItem(item);
    },
    Promise.resolve(),
  );
}

// --- Retry with exponential backoff ---
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelayMs: number = 100,
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}
```

- `async/await` is the default — use raw Promises only when constructing custom async operations
- `Promise.all` when all must succeed (fail-fast on first rejection)
- `Promise.allSettled` when you need all results regardless of individual failures
- `Promise.race` for timeouts, fastest-response, or cancellation patterns
- `AbortController` for cancellable fetch, streams, and long-running operations
- Async generators (`async function*`) for paginated data iteration
- Never use `async void` except in top-level event handlers — it swallows errors
- Always `await` the return value of async functions — dangling promises are bugs

## Type System Deep Patterns

```typescript
// --- Generics with constraints ---
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

// Generic with multiple constraints
function merge<T extends object, U extends object>(a: T, b: U): T & U {
  return { ...a, ...b };
}

// Generic factory with constructor constraint
function createInstance<T>(ctor: new () => T): T {
  return new ctor();
}

// Generic with default type parameter
interface ApiResponse<T = unknown> {
  data: T;
  meta: { requestId: string; timestamp: string };
}

// --- Conditional types ---
type IsString<T> = T extends string ? true : false;
type A = IsString<string>;   // true
type B = IsString<number>;   // false

// Extract return type of async functions
type AsyncReturnType<T extends (...args: any[]) => Promise<any>> =
  T extends (...args: any[]) => Promise<infer R> ? R : never;

// Conditional type for nullable handling
type NonNullableFields<T> = {
  [K in keyof T]: NonNullable<T[K]>;
};

// --- Mapped types ---
// Built-in utilities
type PartialWidget = Partial<Widget>;           // all fields optional
type RequiredWidget = Required<Widget>;         // all fields required
type WidgetName = Pick<Widget, "id" | "name">; // subset of fields
type WidgetNoId = Omit<Widget, "id">;           // exclude fields
type StatusMap = Record<string, boolean>;        // index signature

// Custom mapped type: make all fields readonly recursively
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

// Custom mapped type: make specific fields optional
type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
type CreateWidgetInput = PartialBy<Widget, "id" | "createdAt" | "updatedAt">;

// Custom mapped type: transform field types
type Stringify<T> = {
  [K in keyof T]: string;
};

// --- Template literal types ---
type EventName = `${string}.created` | `${string}.updated` | `${string}.deleted`;
type WidgetEvent = `widget.${EventName}`;

// HTTP method routing
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
type Route = `/${string}`;
type EndpointKey = `${HttpMethod} ${Route}`;

// CSS-like property types
type CSSUnit = "px" | "rem" | "em" | "%";
type CSSValue = `${number}${CSSUnit}`;

// --- Type guards and narrowing ---
// User-defined type guard
function isWidget(value: unknown): value is Widget {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "name" in value &&
    "tenantId" in value
  );
}

// Asserting type guard (throws if false)
function assertWidget(value: unknown): asserts value is Widget {
  if (!isWidget(value)) {
    throw new Error("Expected Widget object");
  }
}

// Narrowing with `in` operator
function processEntity(entity: Widget | Component) {
  if ("status" in entity) {
    // TypeScript narrows to Widget
    console.log(entity.status);
  }
}

// --- Discriminated unions ---
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

function handleResult<T>(result: Result<T>): T {
  if (result.ok) {
    return result.value; // narrowed to { ok: true; value: T }
  }
  throw result.error; // narrowed to { ok: false; error: Error }
}

// Tagged union for domain events
type DomainEvent =
  | { type: "widget.created"; payload: { widget: Widget } }
  | { type: "widget.updated"; payload: { widget: Widget; changes: Partial<Widget> } }
  | { type: "widget.deleted"; payload: { widgetId: string } };

function handleEvent(event: DomainEvent): void {
  switch (event.type) {
    case "widget.created":
      console.log("Created:", event.payload.widget.name); // narrows correctly
      break;
    case "widget.updated":
      console.log("Changes:", event.payload.changes);
      break;
    case "widget.deleted":
      console.log("Deleted:", event.payload.widgetId);
      break;
    default:
      // Exhaustiveness check — compile error if a case is missed
      const _exhaustive: never = event;
      throw new Error(`Unhandled event type: ${(_exhaustive as any).type}`);
  }
}

// --- satisfies operator ---
// Validates type without widening — preserves narrow inferred types
const STATUS_CODES = {
  ok: 200,
  created: 201,
  notFound: 404,
  conflict: 409,
  internalError: 500,
} satisfies Record<string, number>;
// typeof STATUS_CODES.ok is 200 (literal), not number

const ROUTES = {
  home: "/",
  widgets: "/api/v1/widgets",
  widgetById: "/api/v1/widgets/:id",
} satisfies Record<string, string>;
// typeof ROUTES.home is "/" (literal), not string

// --- const assertions ---
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"] as const;
type HttpMethodTuple = typeof HTTP_METHODS; // readonly ["GET", "POST", "PUT", "DELETE"]
type HttpMethodUnion = (typeof HTTP_METHODS)[number]; // "GET" | "POST" | "PUT" | "DELETE"

// Const assertion on objects
const config = {
  port: 3000,
  host: "localhost",
  features: {
    caching: true,
    rateLimit: false,
  },
} as const;
// config.port is 3000 (literal), config.features.caching is true (literal)

// --- Branded types (nominal typing) ---
type UserId = string & { readonly __brand: "UserId" };
type TenantId = string & { readonly __brand: "TenantId" };

function createUserId(id: string): UserId {
  return id as UserId;
}

function createTenantId(id: string): TenantId {
  return id as TenantId;
}

// Prevents accidental mixing:
// const userId: UserId = createUserId("abc");
// const tenantId: TenantId = createTenantId("xyz");
// findWidget(tenantId, userId); // compile error if params are (UserId, TenantId)
```

- `interface` for extensible object shapes; `type` for unions, intersections, mapped types
- Generics over `any` — always constrain with `extends`
- `satisfies` validates a type while preserving the narrow inferred type
- `as const` creates readonly literal types from objects and arrays
- Discriminated unions + `switch` + exhaustiveness check is the primary pattern for polymorphism
- Type guards (`is` / `asserts`) for runtime narrowing of `unknown` values
- Branded types for nominal type safety (UserId vs TenantId cannot be swapped)
- Never use `any` — use `unknown` + narrowing, generics, or mapped types

## Module System

```typescript
// --- ESM (ECMAScript Modules) — the default for TypeScript 5.x+ ---
// tsconfig.json: "module": "NodeNext" or "ESNext"
// package.json: "type": "module"

// Named exports (preferred — tree-shakeable)
export function createWidget(input: CreateInput): Widget { /* ... */ }
export class WidgetService { /* ... */ }
export type { Widget, CreateInput };
export const MAX_PAGE_SIZE = 100;

// Default export (use sparingly — harder to refactor and tree-shake)
export default class WidgetService { /* ... */ }

// Re-export from other modules
export { WidgetService } from "./widget.service.js";
export type { Widget } from "./widget.types.js";

// Named import
import { WidgetService, type Widget } from "./widget.service.js";

// Namespace import
import * as widgetModule from "./widget.service.js";

// --- CommonJS (legacy — avoid for new projects) ---
// module.exports = { createWidget };
// const { createWidget } = require("./widget.service");

// --- Dynamic imports (code splitting) ---
// Lazy-load expensive modules
async function processReport(): Promise<void> {
  // Only loaded when this function is called
  const { PDFGenerator } = await import("./pdf-generator.js");
  const generator = new PDFGenerator();
  await generator.generate();
}

// Conditional dynamic import (load different implementations)
async function getCache(): Promise<ICache> {
  if (process.env.REDIS_URL) {
    const { RedisCache } = await import("./redis-cache.js");
    return new RedisCache(process.env.REDIS_URL);
  }
  const { InMemoryCache } = await import("./memory-cache.js");
  return new InMemoryCache();
}

// React lazy loading
const Dashboard = React.lazy(() => import("./pages/Dashboard.js"));

// --- Barrel exports (index.ts) ---
// src/services/index.ts — public API barrel
export { WidgetService } from "./widget.service.js";
export { OrderService } from "./order.service.js";
export type { CreateWidgetInput, UpdateWidgetInput } from "./widget.service.interface.js";

// RULE: Barrel exports ONLY at module boundaries (src/services/index.ts)
// NOT inside modules (src/services/widget/index.ts re-exporting internals)
// Deep re-exports defeat tree-shaking and create circular dependency risks

// --- Path aliases (tsconfig paths) ---
// tsconfig.json:
// {
//   "compilerOptions": {
//     "baseUrl": ".",
//     "paths": {
//       "@/*": ["src/*"],
//       "@/domain/*": ["src/domain/*"],
//       "@/services/*": ["src/services/*"]
//     }
//   }
// }

// Usage:
import { WidgetService } from "@/services/widget.service.js";
import type { Widget } from "@/domain/entity.js";

// For Node.js: register path aliases at runtime with tsx, tsconfig-paths, or tsc-alias
// For bundlers (Vite, esbuild): configured automatically from tsconfig paths
```

- ESM (`import`/`export`) is the default — use `"type": "module"` in package.json
- Named exports over default exports — better refactoring, autocompletion, and tree-shaking
- Dynamic `import()` for code splitting and conditional module loading
- Barrel `index.ts` ONLY at module boundaries — never for internal re-exports
- Path aliases (`@/`) for cleaner imports — configure in tsconfig.json `paths`
- `.js` extensions in import paths for ESM compatibility (TypeScript resolves `.js` to `.ts`)
- `export type` for type-only exports — stripped at compile time, no runtime cost

## Decorators (Stage 3 / TypeScript 5.x)

```typescript
// --- TypeScript 5.x Stage 3 Decorators ---
// tsconfig.json: no experimentalDecorators needed (Stage 3 is built-in)

// Class decorator — adds metadata or modifies class behavior
function sealed(constructor: Function) {
  Object.seal(constructor);
  Object.seal(constructor.prototype);
}

@sealed
class Widget {
  name: string;
  constructor(name: string) {
    this.name = name;
  }
}

// Class decorator factory — parameterized decorator
function entity(tableName: string) {
  return function <T extends { new (...args: any[]): {} }>(constructor: T) {
    return class extends constructor {
      static tableName = tableName;
    };
  };
}

@entity("widgets")
class WidgetEntity {
  name!: string;
}

// --- Method decorators ---
// Logging decorator
function log(target: any, propertyKey: string, descriptor: PropertyDescriptor) {
  const originalMethod = descriptor.value;

  descriptor.value = function (...args: any[]) {
    console.log(`Calling ${propertyKey} with:`, args);
    const result = originalMethod.apply(this, args);
    console.log(`${propertyKey} returned:`, result);
    return result;
  };

  return descriptor;
}

// Retry decorator
function retry(maxAttempts: number = 3) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
          return await originalMethod.apply(this, args);
        } catch (err) {
          if (attempt === maxAttempts) throw err;
          await new Promise((r) => setTimeout(r, 100 * attempt));
        }
      }
    };

    return descriptor;
  };
}

class WidgetService {
  @log
  @retry(3)
  async fetchWidget(id: string): Promise<Widget> {
    return this.repo.findById(id);
  }
}

// --- Parameter decorators (NestJS style) ---
// These require experimentalDecorators: true in tsconfig.json
// NestJS uses legacy/experimental decorators (not Stage 3)

import { Controller, Get, Param, Query } from "@nestjs/common";

@Controller("widgets")
class WidgetController {
  @Get(":id")
  async findOne(
    @Param("id") id: string,
    @Query("include") include?: string,
  ): Promise<Widget> {
    return this.widgetService.get(id);
  }
}

// --- NestJS decorator patterns ---

// Custom parameter decorator
import { createParamDecorator, ExecutionContext } from "@nestjs/common";

const CurrentUser = createParamDecorator(
  (data: unknown, ctx: ExecutionContext) => {
    const request = ctx.switchToHttp().getRequest();
    return request.user;
  },
);

// Custom method decorator
import { SetMetadata } from "@nestjs/common";

const Roles = (...roles: string[]) => SetMetadata("roles", roles);

@Controller("admin/widgets")
class AdminWidgetController {
  @Get()
  @Roles("admin", "manager")
  async listAll(@CurrentUser() user: AuthUser): Promise<Widget[]> {
    return this.widgetService.listAll(user.tenantId);
  }
}

// Custom class decorator (Guard)
import { Injectable, CanActivate, ExecutionContext } from "@nestjs/common";
import { Reflector } from "@nestjs/core";

@Injectable()
class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.get<string[]>("roles", context.getHandler());
    if (!requiredRoles) return true;

    const request = context.switchToHttp().getRequest();
    const user = request.user as AuthUser;
    return requiredRoles.some((role) => user.roles.includes(role));
  }
}
```

- TypeScript 5.x supports Stage 3 decorators natively (no `experimentalDecorators` flag needed)
- NestJS still uses legacy/experimental decorators — set `experimentalDecorators: true` for NestJS projects
- Class decorators modify or replace the class constructor
- Method decorators wrap method behavior (logging, retry, caching)
- Parameter decorators extract and transform request data (NestJS `@Param`, `@Query`, `@Body`)
- Custom decorators combine `createParamDecorator` (params) and `SetMetadata` (metadata)
- Guards read decorator metadata via `Reflector` for authorization decisions
- Decorator execution order: parameter decorators first, then method, then class (bottom to top)

## Error Handling

```typescript
// --- Custom error class hierarchy ---
class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    options?: ErrorOptions, // supports `cause` for error chaining
  ) {
    super(message, options);
    this.name = this.constructor.name;

    // Fix prototype chain for instanceof checks (TypeScript target < ES6)
    Object.setPrototypeOf(this, new.target.prototype);
  }

  /** Serializes for API responses — never leaks stack traces. */
  toJSON(): { code: string; message: string } {
    return { code: this.code, message: this.message };
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super("NOT_FOUND", `${resource} ${id} not found`, 404);
  }
}

class ValidationError extends AppError {
  constructor(
    public readonly field: string,
    detail: string,
  ) {
    super("VALIDATION_ERROR", `Validation failed: ${field} — ${detail}`, 422);
  }
}

class MultiValidationError extends AppError {
  constructor(public readonly fieldErrors: Record<string, string>) {
    super("VALIDATION_ERROR", "Validation failed", 422);
  }

  override toJSON() {
    return {
      code: this.code,
      message: this.message,
      details: this.fieldErrors,
    };
  }
}

class ConflictError extends AppError {
  constructor(resource: string, detail: string) {
    super("CONFLICT", `${resource} conflict: ${detail}`, 409);
  }
}

class UnauthorizedError extends AppError {
  constructor(detail: string = "authentication required") {
    super("UNAUTHORIZED", detail, 401);
  }
}

class ForbiddenError extends AppError {
  constructor(detail: string = "insufficient permissions") {
    super("FORBIDDEN", detail, 403);
  }
}

class InternalError extends AppError {
  constructor(cause?: Error) {
    super("INTERNAL_ERROR", "An internal error occurred", 500, { cause });
  }
}

// --- throw vs return Result pattern ---

// THROW pattern: Use in service/handler layers where errors are exceptional
async function getWidget(tenantId: string, id: string): Promise<Widget> {
  const widget = await repo.findById(tenantId, id);
  if (!widget) throw new NotFoundError("widget", id);
  return widget;
}

// RESULT pattern: Use in library code, parsers, validators
type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E };

function parseConfig(raw: unknown): Result<Config, ValidationError> {
  const parsed = ConfigSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      ok: false,
      error: new ValidationError("config", parsed.error.message),
    };
  }
  return { ok: true, value: parsed.data };
}

// Utility: unwrap Result or throw
function unwrap<T, E extends Error>(result: Result<T, E>): T {
  if (!result.ok) throw result.error;
  return result.value;
}

// --- Error cause chain (ES2022+) ---
async function createWidget(input: CreateInput): Promise<Widget> {
  try {
    return await repo.create(input);
  } catch (err) {
    // Chain the original error as the cause
    throw new InternalError(err instanceof Error ? err : undefined);
  }
}

// Access the full error chain
function logErrorChain(err: Error): void {
  let current: Error | undefined = err;
  let depth = 0;

  while (current) {
    logger.error(`[${"  ".repeat(depth)}] ${current.name}: ${current.message}`);
    current = current.cause instanceof Error ? current.cause : undefined;
    depth++;
  }
}
// Output:
// [] InternalError: An internal error occurred
// [  ] PrismaClientKnownRequestError: Unique constraint violated

// --- Zod for runtime validation at system boundaries ---
import { z } from "zod";

// Schema definition
const CreateWidgetSchema = z.object({
  name: z.string().trim().min(1, "name is required").max(255),
  description: z.string().trim().max(2000).default(""),
  priority: z.number().int().min(0).max(10).default(0),
  tags: z.array(z.string().min(1)).max(20).default([]),
  config: z.record(z.unknown()).default({}),
});

type CreateWidgetInput = z.infer<typeof CreateWidgetSchema>;

// Validation — safeParse returns Result-like structure
function validateInput(raw: unknown): CreateWidgetInput {
  const result = CreateWidgetSchema.safeParse(raw);
  if (!result.success) {
    const fieldErrors: Record<string, string> = {};
    for (const issue of result.error.issues) {
      fieldErrors[issue.path.join(".")] = issue.message;
    }
    throw new MultiValidationError(fieldErrors);
  }
  return result.data;
}

// Zod for environment variable validation
const EnvSchema = z.object({
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  JWT_SECRET: z.string().min(32),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

// Validate at startup — fail fast if config is invalid
export const env = EnvSchema.parse(process.env);

// Zod transform — parse and transform in one step
const DateStringSchema = z.string().transform((s) => new Date(s));
const PaginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  per_page: z.coerce.number().int().min(1).max(100).default(20),
});

// --- Express error middleware ---
import type { Request, Response, NextFunction } from "express";

function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof AppError) {
    res.status(err.statusCode).json({ error: err.toJSON() });
    return;
  }

  // Unknown error — log full details, return generic message
  logger.error("Unhandled error", { error: err.message, stack: err.stack });
  res.status(500).json({
    error: { code: "INTERNAL_ERROR", message: "An internal error occurred" },
  });
}
```

- Custom error classes extend `Error` with `code` (machine-readable) and `statusCode`
- `throw` in service/handler code for exceptional errors (NotFound, Conflict, Validation)
- `Result<T, E>` pattern in library/utility code — no exceptions for expected failures
- Error `cause` (ES2022) for chaining: `new Error("msg", { cause: originalError })`
- `Object.setPrototypeOf(this, new.target.prototype)` fixes `instanceof` for transpiled classes
- `toJSON()` on error classes controls API response serialization — never exposes stack traces
- Zod `safeParse` at system boundaries (API input, env vars, config) — returns structured errors
- Express error middleware MUST be a 4-argument function `(err, req, res, next)` — Express uses arity detection
- Internal errors MUST return generic messages to clients — log full details server-side
- Never `catch` and swallow errors silently — always log, rethrow, or return a meaningful Result
