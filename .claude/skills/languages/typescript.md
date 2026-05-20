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
