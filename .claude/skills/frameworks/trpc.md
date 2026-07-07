---
skill: trpc
description: tRPC patterns — end-to-end type-safe procedures, Zod input validation, routers/context/middleware, and TanStack Query client integration
version: "1.0"
tags:
  - trpc
  - typescript
  - type-safety
  - api
  - zod
---

# tRPC patterns for end-to-end type-safe TypeScript APIs.

Use tRPC when client and server are both TypeScript in one repo/monorepo — you get inferred types with no codegen and no OpenAPI. For public/partner APIs or non-TS clients, use REST (see `core/api-excellence.md`) instead.

## Router & Procedures
```ts
// server/trpc.ts — init once
import { initTRPC, TRPCError } from '@trpc/server';
const t = initTRPC.context<Context>().create();
export const router = t.router;
export const publicProcedure = t.procedure;

// auth middleware → protected procedure
const isAuthed = t.middleware(({ ctx, next }) => {
  if (!ctx.user) throw new TRPCError({ code: 'UNAUTHORIZED' });
  return next({ ctx: { user: ctx.user } }); // narrows ctx.user to non-null
});
export const protectedProcedure = t.procedure.use(isAuthed);
```

```ts
// server/routers/user.ts
import { z } from 'zod';
export const userRouter = router({
  list: publicProcedure
    .input(z.object({ cursor: z.string().optional(), limit: z.number().max(100).default(20) }))
    .query(({ input, ctx }) => ctx.db.users.list(input)),
  create: protectedProcedure
    .input(z.object({ email: z.string().email(), name: z.string().min(1) }))
    .mutation(({ input, ctx }) => ctx.db.users.create(input)),
});

export const appRouter = router({ user: userRouter });
export type AppRouter = typeof appRouter; // export the TYPE only
```

- Every procedure declares its input with a Zod schema — validation and types come from one source
- `.query` for reads, `.mutation` for writes — the client uses the matching hook
- Compose routers by domain; merge into one `appRouter`
- Export `type AppRouter`, never the runtime router, to the client bundle

## Context & Errors
```ts
export async function createContext({ req }: CreateContextOptions): Promise<Context> {
  return { db, user: await getUserFromToken(req.headers.authorization) };
}
// Map domain errors to tRPC codes: NOT_FOUND, BAD_REQUEST, FORBIDDEN, CONFLICT, INTERNAL_SERVER_ERROR
throw new TRPCError({ code: 'NOT_FOUND', message: 'user not found' });
```

## Client (React + TanStack Query)
```ts
export const trpc = createTRPCReact<AppRouter>();

function UserList() {
  const { data, isLoading } = trpc.user.list.useQuery({ limit: 20 }); // fully typed input + output
  const create = trpc.user.create.useMutation({
    onSuccess: () => utils.user.list.invalidate(),
  });
}
```

- Types flow from server to client automatically — rename a field server-side and the client fails to compile
- Use `utils.<path>.invalidate()` after mutations to refetch affected queries
- Wrap the app in `trpc.Provider` + a `QueryClientProvider` (tRPC sits on TanStack Query)

## Rules
- Validate every input with Zod at the procedure boundary — never trust the client
- Keep procedures thin: validate → call a service/repository → return; no business logic in the router
- Do auth in middleware (`protectedProcedure`), not per-procedure `if` checks
- Batch requests are on by default via the httpBatchLink — keep procedures side-effect-scoped so batching is safe
