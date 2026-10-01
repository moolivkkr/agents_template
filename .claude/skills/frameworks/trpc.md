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

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, tRPC 11.19 (@trpc/server, @trpc/client, @trpc/tanstack-react-query), TanStack Query 5.104, Zod 4.6, React 19 (tests/archetype-compile/typescript/run.sh).

Use tRPC when client and server are both TypeScript in one repo/monorepo — you get inferred types with no codegen and no OpenAPI. For public/partner APIs or non-TS clients, use REST (see `core/api-excellence.md`) instead.

## Router & Procedures
```ts
// server/trpc.ts — init once
import { initTRPC, TRPCError } from '@trpc/server';
import type { Context } from './context';

const t = initTRPC.context<Context>().create({
  // An unexpected error becomes INTERNAL_SERVER_ERROR carrying the thrown error's message (and, outside
  // production, its stack). Send catalog text instead; the cause goes to the log (the adapter's onError).
  errorFormatter: ({ shape, error }) =>
    error.code === 'INTERNAL_SERVER_ERROR'
      ? { ...shape, message: 'Something went wrong.', data: { ...shape.data, stack: undefined } }
      : shape,
});
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
import { protectedProcedure, router } from '../trpc';

// Tenant data: protected procedures, and the tenant comes from the verified token (ctx.user) — never the input
export const userRouter = router({
  list: protectedProcedure
    .input(z.object({ cursor: z.string().optional(), limit: z.number().int().min(1).max(100).default(20) }))
    .query(({ input, ctx }) => ctx.db.users.list(ctx.user.tenantId, input)),
  create: protectedProcedure
    .input(z.object({ email: z.email(), name: z.string().min(1).max(255) }))
    .mutation(({ input, ctx }) => ctx.db.users.create(ctx.user.tenantId, input)),
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
// server/context.ts
import { TRPCError } from '@trpc/server';
import type { CreateExpressContextOptions } from '@trpc/server/adapters/express';
import { getUserFromToken } from './auth'; // verifies the JWT (signature, exp, iss, aud); null if absent/invalid
import { db } from './db';

export async function createContext({ req }: CreateExpressContextOptions) {
  return { db, user: await getUserFromToken(req.headers.authorization) };
}
export type Context = Awaited<ReturnType<typeof createContext>>;

// Map domain errors to tRPC codes: NOT_FOUND, BAD_REQUEST, FORBIDDEN, CONFLICT, INTERNAL_SERVER_ERROR.
// The message is user-safe catalog text — never a caught error's message.
export function notFound(what: string): never {
  throw new TRPCError({ code: 'NOT_FOUND', message: `${what} not found.` }); // also another tenant's row
}
```

## Client (React + TanStack Query)
`@trpc/tanstack-react-query` is the integration tRPC recommends for new code: plain TanStack Query hooks fed
by `queryOptions()` / `mutationOptions()`. (`createTRPCReact` from `@trpc/react-query` is the classic one,
still supported.)
```tsx
// client/trpc.tsx
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createTRPCClient, httpBatchLink } from '@trpc/client';
import { createTRPCContext } from '@trpc/tanstack-react-query';
import { useState, type ReactNode } from 'react';
import type { AppRouter } from '../server/routers/user'; // the TYPE only — no server code in the bundle
import { getAccessToken } from './auth/session'; // in memory — never localStorage, never the URL

export const { TRPCProvider, useTRPC } = createTRPCContext<AppRouter>();

export function TrpcProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const [trpcClient] = useState(() =>
    createTRPCClient<AppRouter>({
      links: [httpBatchLink({ url: '/trpc', headers: () => ({ authorization: `Bearer ${getAccessToken()}` }) })],
    }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <TRPCProvider trpcClient={trpcClient} queryClient={queryClient}>{children}</TRPCProvider>
    </QueryClientProvider>
  );
}

export function UserList() {
  const trpc = useTRPC();
  const queryClient = useQueryClient();
  const users = useQuery(trpc.user.list.queryOptions({ limit: 20 })); // fully typed input + output
  const create = useMutation(trpc.user.create.mutationOptions({
    onSuccess: () => queryClient.invalidateQueries(trpc.user.list.pathFilter()), // every page of the list
  }));

  if (users.isPending) return <p>Loading…</p>;
  if (users.isError) return <p role="alert">Couldn't load the users.</p>;
  return (
    <>
      <ul>{users.data.items.map((u) => <li key={u.id}>{u.name}</li>)}</ul>
      <button disabled={create.isPending} onClick={() => create.mutate({ email: 'new@example.com', name: 'New user' })}>
        Add user
      </button>
    </>
  );
}
```

- Types flow from server to client automatically — rename a field server-side and the client fails to compile
- After a mutation, invalidate the affected queries: `queryClient.invalidateQueries(trpc.<path>.pathFilter())`
- Wrap the app in `TRPCProvider` inside a `QueryClientProvider` (tRPC sits on TanStack Query)

## Rules
- Validate every input with Zod at the procedure boundary — never trust the client
- Keep procedures thin: validate → call a service/repository → return; no business logic in the router
- Do auth in middleware (`protectedProcedure`), not per-procedure `if` checks
- Batch requests are on by default via the httpBatchLink — keep procedures side-effect-scoped so batching is safe
