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

## Rules
- Never disable TypeScript with `// @ts-ignore` — fix the type
- No barrel `index.ts` that re-exports everything from subdirectories
- ESLint with `@typescript-eslint/recommended-type-checked`
- Format with Prettier (no config debates)
- `tsx` for scripts, `ts-node` only as last resort
