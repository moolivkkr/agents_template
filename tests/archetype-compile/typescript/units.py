"""Which archetype TS blocks compile together, and which are skipped (with why).

Block refs are "<archetype file stem>#<n>", n = 1-based index of the TS block in that file
(```typescript / ts / tsx / javascript …, in document order). Run `./run.sh --list` to see units.

A block lands at the path in its `// src/...` header comment; `place` overrides that (or places a
header-less continuation block, which is appended to that path). Blocks from several archetype
files share a unit when they import each other (the CRUD stack: handler → service → repository →
errors), so cross-file drift (a renamed export, a moved file) fails the compile.

Harness stubs live in shims/<dir> (copied into the unit) or in `prelude` strings below. They stand in
for PROJECT code a fragment assumes (a shadcn component, an app module) — never for the library API
a sample demonstrates.
"""

# Expected number of TS blocks per archetype file. A mismatch fails the run: a block was added or
# removed, so the units below must be updated to cover it.
FILES = {
    "backend/archetypes/auth-middleware-typescript.md": 14,
    "backend/archetypes/crud-handler-test-typescript.md": 11,
    "backend/archetypes/crud-handler-typescript.md": 14,
    "backend/archetypes/crud-repository-test-typescript.md": 17,
    "backend/archetypes/crud-repository-typescript.md": 7,
    "backend/archetypes/crud-service-test-typescript.md": 8,
    "backend/archetypes/crud-service-typescript.md": 11,
    "backend/archetypes/dockerfile-typescript.md": 1,
    "backend/archetypes/error-handling-typescript.md": 7,
    "backend/archetypes/grpc-pattern-typescript.md": 5,
    "backend/archetypes/migration-pattern-typescript.md": 7,
    "backend/archetypes/observability-typescript.md": 33,
    "backend/archetypes/performance-typescript.md": 32,
    "backend/archetypes/websocket-pattern-typescript.md": 6,
    "backend/archetypes/worker-pattern-typescript.md": 7,
    "ui/archetypes/component-test.md": 10,
    "ui/archetypes/dashboard-page.md": 1,
    "ui/archetypes/detail-page.md": 2,
    "ui/archetypes/form-page.md": 3,
    "ui/archetypes/list-page.md": 2,
    "ui/archetypes/settings-page.md": 3,
    # the backend packs agents copy from
    "languages/typescript.md": 12,
    "frameworks/express.md": 5,
    "frameworks/fastify.md": 10,
    "frameworks/nestjs.md": 5,
    "frameworks/trpc.md": 4,
    "frameworks/graphql.md": 2,
    "testing/vitest.md": 7,
    "testing/contract-testing.md": 1,
    "testing/property-based.md": 1,
    "testing/load-testing.md": 5,
    "core/api-excellence.md": 2,
    "core/code-quality.md": 5,
    "core/observability-patterns.md": 6,
    "core/resiliency-patterns.md": 7,
    "core/software-architecture.md": 5,
    "core/testing-principles.md": 1,
    "api/response-envelope.md": 1,
}


def refs(stem, *nums):
    return [f"{stem}#{n}" for n in nums]


# --- the Express CRUD stack: errors + auth + handler + service + repositories (Prisma and Drizzle)
ERRORS = refs("error-handling-typescript", 1, 2, 3, 7)
AUTH_EXPRESS = refs("auth-middleware-typescript", 1, 2, 3, 4, 7, 9, 10, 11, 12, 14)
HANDLER_EXPRESS = refs("crud-handler-typescript", 1, 2, 3, 4, 5, 6, 7, 8, 9)
SERVICE = refs("crud-service-typescript", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
REPOSITORY = refs("crud-repository-typescript", 1, 2, 3, 4, 5, 6, 7)
EXPRESS_STACK = ERRORS + AUTH_EXPRESS + HANDLER_EXPRESS + SERVICE + REPOSITORY

HANDLER_TEST = "src/routes/widget.routes.test.ts"
SERVICE_TEST = "src/services/widget.service.test.ts"
PRISMA_REPO_TEST = "src/repositories/prisma-widget.repository.test.ts"
DRIZZLE_REPO_TEST = "src/repositories/drizzle-widget.repository.test.ts"

# --- the NestJS CRUD stack: filter + guards + controller/DTOs/decorators on the same errors/service
NEST_STACK = (
    ERRORS + ["error-handling-typescript#4"]
    + refs("auth-middleware-typescript", 1, 5, 6, 8, 13)
    + refs("crud-handler-typescript", 1, 2, 3, 10, 11, 12, 13, 14)
    + SERVICE + REPOSITORY
)

# The TypeScript envelope types, extracted from api/response-envelope.md at run time (UI units import it
# as src/types/api.ts), so UI mocks and fragments are checked against the one envelope.
ENVELOPE = {"doc": "api/response-envelope.md", "langs": ["ts", "typescript"], "index": 1, "path": "src/types/api.ts"}

UNITS = [
    {
        "name": "crud-express-stack",
        "blocks": EXPRESS_STACK,
        "prisma": True,
        "shims": ["crud-stack"],
    },
    {
        "name": "crud-express-handler-tests",
        "blocks": EXPRESS_STACK + refs("crud-handler-test-typescript", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        "place": {f"crud-handler-test-typescript#{n}": HANDLER_TEST for n in range(3, 11)},
        "prisma": True,
        "shims": ["crud-stack"],
        "vitest": [HANDLER_TEST],  # also RUN them (supertest, in-process): the samples' own assertions
    },
    {
        "name": "crud-service-tests",
        "blocks": EXPRESS_STACK + refs("crud-service-test-typescript", 1, 2, 3, 4, 5, 6, 7, 8),
        "place": {
            "crud-service-test-typescript#5": "src/services/prisma-mock.test.ts",
            "crud-service-test-typescript#6": "src/services/drizzle-mock.test.ts",
            "crud-service-test-typescript#7": SERVICE_TEST,
            "crud-service-test-typescript#8": SERVICE_TEST,
        },
        "prisma": True,
        "shims": ["crud-stack"],
        "vitest": ["src/services"],  # all four service test files — mocks only, no database
    },
    {
        "name": "crud-repository-tests",
        "blocks": EXPRESS_STACK + refs("crud-repository-test-typescript", *range(1, 18)),
        "place": {
            **{f"crud-repository-test-typescript#{n}": PRISMA_REPO_TEST for n in range(3, 11)},
            **{f"crud-repository-test-typescript#{n}": DRIZZLE_REPO_TEST for n in range(12, 18)},
        },
        "prisma": True,
        "shims": ["crud-stack"],
    },
    {
        # nice-grpc server on the CRUD service/errors; ts-proto output of grpc-pattern.md's protos is
        # committed in shims/grpc/src/gen (grpc-codegen/regen.sh regenerates it)
        "name": "grpc-nice-grpc",
        "blocks": ERRORS + SERVICE + REPOSITORY + refs("crud-handler-typescript", 2)
        + refs("grpc-pattern-typescript", 1, 2, 3, 4, 5),
        "prisma": True,
        "shims": ["crud-stack", "grpc", "project-auth"],
    },
    {
        "name": "websocket",
        "blocks": refs("websocket-pattern-typescript", 1, 2, 3, 4, 5, 6),
        "shims": ["project-auth", "ws-test"],
        # both servers over real sockets: Origin allowlist, single-use tickets, tenant rooms (shims/ws-test)
        "vitest": ["src/ws/ws-authz.test.ts"],
    },
    {
        "name": "worker-bullmq",
        "blocks": refs("worker-pattern-typescript", 1, 2, 3, 4, 5, 6, 7),
        "shims": ["worker"],
    },
    {
        "name": "dockerfile-health-route",
        "blocks": ["dockerfile-typescript#1"],
        "prisma": True,
    },
    {
        # illustrative fragments: the service sketch and the isAppError try/catch
        "name": "error-handling-fragments",
        "blocks": ERRORS + refs("error-handling-typescript", 5, 6) + ["crud-service-typescript#9"],
        "place": {
            "error-handling-typescript#5": {
                "path": "src/services/widget.service.ts",
                # the types the sketch leaves to the project (crud-service-typescript.md defines real ones)
                "postlude": "\n".join([
                    "interface Widget { id: string; tenantId: string; name: string; version: number }",
                    "interface CreateWidgetInput { tenantId: string; name: string }",
                    "interface UpdateWidgetInput { name: string; version: number }",
                    "interface WidgetRepository {",
                    "  findByName(tenantId: string, name: string): Promise<Widget | null>;",
                    "  findById(tenantId: string, id: string): Promise<Widget | null>;",
                    "  create(input: CreateWidgetInput): Promise<Widget>;",
                    "  update(id: string, patch: UpdateWidgetInput): Promise<Widget>;",
                    "}",
                ]),
            },
            "error-handling-typescript#6": {
                "path": "src/services/widget.usage.ts",
                "wrap": "async",
                "prelude": "\n".join([
                    'import { isAppError } from "../errors";',
                    "declare const widgetService: { create(input: unknown): Promise<unknown> };",
                    "declare const input: unknown;",
                ]),
            },
        },
    },
    {
        # migrate runner, prisma.config.ts, seed — and `prisma validate` of the doc's own ```prisma blocks
        # (the schema and the multi-schema variant) with the doc's own prisma.config.ts
        "name": "migration-prisma",
        "blocks": refs("migration-pattern-typescript", 1, 2, 3),
        "prisma": True,
        "prisma_validate": [
            {"doc": "backend/archetypes/migration-pattern-typescript.md", "langs": ["prisma"], "index": 1},
            {"doc": "backend/archetypes/migration-pattern-typescript.md", "langs": ["prisma"], "index": 2},
        ],
    },
    {
        "name": "migration-drizzle",
        "blocks": refs("migration-pattern-typescript", 4, 5, 6, 7),
    },
    {
        # Express side: SDK setup, manual spans, middleware, Prisma/Drizzle/Redis spans, metrics, pino,
        # request context and the full Express main.ts (src/routes/health.ts = dockerfile-typescript.md)
        "name": "observability-express",
        "blocks": refs("observability-typescript", 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20,
                       21, 26, 27, 28, 30, 33)
        + refs("error-handling-typescript", 1, 2, 3, 7) + refs("auth-middleware-typescript", 1, 3)
        + ["dockerfile-typescript#1"],
        "place": {
            "observability-typescript#2": {
                "path": "src/instrumentation.prisma.ts",
                "wrap": "object",
                "prelude": "import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';",
            },
            "observability-typescript#4": {
                "path": "src/services/order.service.ts",
                # the members the usage sketch assumes (declaration-merged onto the class)
                "postlude": "\n".join([
                    "interface CreateOrderDto { items: unknown[] }",
                    "interface Order { id: string; total: number }",
                    "export interface OrderService {",
                    "  validate(req: CreateOrderDto): CreateOrderDto;",
                    "  orderRepo: { create(tenantId: string, dto: CreateOrderDto): Promise<Order> };",
                    "  eventBus: { publish(topic: string, payload: unknown): Promise<void> };",
                    "}",
                ]),
            },
            "observability-typescript#11": "src/lib/span-errors.ts",
            "observability-typescript#21": {
                "path": "src/app.logging.ts",
                "prelude": "\n".join([
                    "import express from 'express';",
                    "import { httpLogger } from './middleware/logging.middleware';",
                    "const app = express();",
                ]),
            },
            "observability-typescript#27": {"path": "src/lib/redaction.example.ts", "prelude": "import pino from 'pino';"},
            "observability-typescript#28": {"path": "src/lib/redaction.usage.ts", "prelude": "import { logger } from './logger';"},
            "observability-typescript#33": {
                "path": "src/shutdown.ts",
                "prelude": "declare const server: import('node:http').Server; // the app.listen() result",
            },
        },
        "prisma": True,
        "shims": ["obs-express"],
        # run the auth ↔ request-context interop test (shims/obs-express); NODE_ENV=production keeps the
        # sample logger on plain JSON (its dev branch wants the pino-pretty transport)
        "vitest": ["src/auth-context.interop.test.ts"],
        "vitest_env": {"NODE_ENV": "production", "LOG_LEVEL": "silent"},
    },
    {
        "name": "observability-nest",
        "blocks": refs("observability-typescript", 6, 7, 14, 22, 23, 29, 31, 32),
        "place": {
            "observability-typescript#7": {"path": "src/app.module.tracing.ts", "prelude": "import { Module } from '@nestjs/common';"},
            "observability-typescript#23": {
                "path": "src/main.logger.ts",
                "prelude": "import { NestFactory } from '@nestjs/core';\nimport { AppModule } from './app.module';",
            },
        },
        "decorators": "legacy",
        "shims": ["obs-nest"],
    },
    {
        # the small main.ts + the trace-correlated logger variant
        "name": "observability-correlated-logger",
        "blocks": refs("observability-typescript", 1, 14, 15, 25),
    },
    {
        # event loop, worker threads, streams, pools, caches, headers, Prisma query patterns (src/lib/prisma.ts
        # here is the slow-query-logging client, #20; the pool-sizing variant #8 compiles in its own unit)
        "name": "performance",
        "blocks": refs("performance-typescript", 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                       21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32),
        "place": {
            "performance-typescript#1": "src/usage/streaming.ts",
            "performance-typescript#5": {
                "path": "src/usage/hash-pool.ts",
                "prelude": "import { WorkerPool } from '../lib/worker-pool';\ndeclare const largePayload: string;",
            },
            "performance-typescript#6": {
                "path": "src/usage/batches.ts",
                "prelude": "declare const hugeArray: number[];",
                "postlude": "export {}; // a module, so the top-level await is legal",
            },
            "performance-typescript#13": {
                "path": "src/usage/leaks.ts",
                "prelude": "\n".join([
                    "declare const someExternalEmitter: import('node:events').EventEmitter;",
                    "declare const logger: import('pino').Logger;",
                    "declare function someAsyncOp(): Promise<void>;",
                ]),
            },
            "performance-typescript#16": {"path": "src/usage/gc.ts", "prelude": "declare const logger: import('pino').Logger;"},
            "performance-typescript#17": {
                "path": "src/usage/prisma-queries.ts",
                "prelude": "import { prisma } from '../lib/prisma';\ndeclare const tenantId: string;\ndeclare const orderId: string;\ndeclare const lastOrderId: string;",
            },
            "performance-typescript#18": {
                "path": "src/usage/batch-ops.ts",
                "prelude": "\n".join([
                    "import { prisma } from '../lib/prisma';",
                    "import type { Prisma } from '@prisma/client';",
                    "declare const tenantId: string;",
                    "declare const items: Array<{ productId: string; name: string; quantity: number; price: number }>;",
                    "declare const order: { id: string };",
                    "declare const orderData: Prisma.OrderUncheckedCreateInput;",
                ]),
            },
            "performance-typescript#19": {
                "path": "src/usage/read-replicas.ts",
                "prelude": "\n".join([
                    "import type { Prisma } from '@prisma/client';",
                    "declare const tenantId: string;",
                    "declare const orderId: string;",
                    "declare const orderData: Prisma.OrderUncheckedCreateInput;",
                ]),
            },
            "performance-typescript#22": {
                "path": "src/usage/n-plus-one.ts",
                "prelude": "import { prisma } from '../lib/prisma';\nimport type { OrderItem } from '@prisma/client';\ndeclare const tenantId: string;",
            },
            "performance-typescript#23": {
                "path": "src/lib/profile.ts",
                "prelude": "import { Router } from 'express';\nconst router = Router();",
            },
            "performance-typescript#24": "src/usage/loadtest.ts",
            "performance-typescript#28": {
                "path": "src/middleware/cache-headers.middleware.ts",
                "prelude": "\n".join([
                    "import type { Express, RequestHandler } from 'express';",
                    "declare const app: Express;",
                    "declare const productsHandler: RequestHandler;",
                    "declare const meHandler: RequestHandler;",
                    "declare const tokenHandler: RequestHandler;",
                ]),
            },
            "performance-typescript#29": {
                "path": "src/middleware/etag.middleware.ts",
                "prelude": "\n".join([
                    "import { Router } from 'express';",
                    "const router = Router();",
                    "declare const orderService: { getById(tenantId: string, id: string): Promise<{ id: string; updatedAt: Date }> };",
                ]),
            },
            "performance-typescript#30": "src/usage/validation.ts",
            "performance-typescript#32": "src/usage/bundle-notes.ts",
        },
        "prisma": True,
        "shims": ["express-tenant"],
    },
    {
        "name": "performance-prisma-pool",
        "blocks": ["performance-typescript#8"],
        "prisma": True,
    },
    {
        # one test file across the 10 blocks; WidgetList/WidgetForm are the project's components (shims/ui)
        "name": "ui-component-test",
        "kind": "ui",
        "blocks": refs("component-test", *range(1, 11)),
        "place": {f"component-test#{n}": "src/features/widgets/WidgetList.test.tsx" for n in range(1, 11)},
        "external": [ENVELOPE],
        "shims": ["ui"],
        "compilerOptions": {"paths": {"@/*": ["./src/*"]}},
    },
    {
        # page-archetype fragments (hooks / JSX excerpts), each wrapped in a component, over shims/ui's
        # query factories (real TanStack helpers) and the envelope types from api/response-envelope.md
        "name": "ui-page-fragments",
        "kind": "ui",
        "blocks": ["list-page#1", "list-page#2", "detail-page#1", "detail-page#2", "form-page#1", "form-page#2",
                   "form-page#3", "settings-page#1", "settings-page#2", "settings-page#3", "dashboard-page#1"],
        "place": {
            "list-page#1": {"path": "src/pages/list-data.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useInfiniteQuery } from '@tanstack/react-query';",
                "import { parseAsString, useQueryState } from 'nuqs';",
                "import { resourceQueries } from '../lib/queries';",
            ])},
            "list-page#2": {"path": "src/pages/list-loading.tsx", "wrap": "jsx",
                            "prelude": "import { Skeleton } from '../components/ui';"},
            "detail-page#1": {"path": "src/pages/detail-data.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useQuery } from '@tanstack/react-query';",
                "import { useParams } from 'react-router-dom';",
                "import { resourceQueries, useDeleteResource } from '../lib/queries';",
            ])},
            "detail-page#2": {"path": "src/pages/detail-loading.tsx", "wrap": "jsx",
                              "prelude": "import { Skeleton } from '../components/ui';"},
            "form-page#1": {"path": "src/pages/form-data.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useQuery } from '@tanstack/react-query';",
                "import { useForm } from 'react-hook-form';",
                "import { zodResolver } from '@hookform/resolvers/zod';",
                "import { toast } from 'sonner';",
                "import { ApiError } from '../lib/api-client';",
                "import { mapServerErrors } from '../lib/form-errors';",
                "import { createUserSchema, updateUserSchema, userQueries, useCreateUser, type CreateUserInput, type UpdateUserInput } from '../lib/queries';",
                "declare const id: string; // the route param",
                "declare const router: { push(href: string): void }; // the app's router",
                "const createUser = useCreateUser();",
            ])},
            "form-page#2": {"path": "src/pages/form-loading.tsx", "wrap": "jsx",
                            "prelude": "import { Card, CardContent, Skeleton } from '../components/ui';"},
            "form-page#3": {"path": "src/pages/form-dirty.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useEffect } from 'react';",
                "import type { UseFormReturn } from 'react-hook-form';",
                "declare const form: UseFormReturn<{ name: string }>;",
            ])},
            "settings-page#1": {"path": "src/pages/settings-data.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useQuery } from '@tanstack/react-query';",
                "import { useForm } from 'react-hook-form';",
                "import { zodResolver } from '@hookform/resolvers/zod';",
                "import { toast } from 'sonner';",
                "import { z } from 'zod';",
                "import { notifSchema, profileSchema, settingsQueries, useUpdateProfile } from '../lib/queries';",
                "const updateProfile = useUpdateProfile();",
            ])},
            "settings-page#2": {"path": "src/pages/settings-tab.tsx", "wrap": "jsx", "prelude": "\n".join([
                "import { useQuery } from '@tanstack/react-query';",
                "import { FormSkeleton, TabsContent } from '../components/ui';",
                "import { settingsQueries } from '../lib/queries';",
                "const profile = useQuery(settingsQueries.profile());",
                "declare function ProfileForm(props: { data: unknown }): React.JSX.Element; // the tab's form component",
            ])},
            "settings-page#3": {"path": "src/pages/settings-tabs.tsx", "wrap": "function", "prelude": "\n".join([
                "import { parseAsString, useQueryState } from 'nuqs';",
                "import { Tabs } from '../components/ui';",
            ])},
            "dashboard-page#1": {"path": "src/pages/dashboard-data.tsx", "wrap": "function", "prelude": "\n".join([
                "import { useQuery } from '@tanstack/react-query';",
                "import { dashboardQueries } from '../lib/queries';",
            ])},
        },
        "external": [ENVELOPE],
        "shims": ["ui"],
    },
    {
        "name": "crud-nest-stack",
        "blocks": NEST_STACK,
        "decorators": "legacy",
        "prisma": True,
        "shims": ["crud-stack", "nest-stack"],
        # Nest resolves constructor deps from emitted metadata at runtime — tsc can't see a missing token
        "node_probe": "src/di-probe.ts",
    },
    {
        "name": "crud-nest-controller-spec",
        "blocks": NEST_STACK + ["crud-handler-test-typescript#11"],
        "decorators": "legacy",
        "prisma": True,
        "shims": ["crud-stack", "nest-stack"],
        "compilerOptions": {"types": ["node", "jest"]},
    },
]

# =========================================================================== the backend packs
# languages/typescript.md, frameworks/*, testing/*, core/*, api/* — the code agents copy from. Fragments get
# their project names from a `prelude` (declarations only: the PROJECT's types and services, never the
# library API the sample shows); "modules": every file is a module, as it is in a project.

def lines(*ls):
    return "\n".join(ls)


PINO_LOGGER = 'declare const logger: import("pino").Logger;'
EXPRESS_TYPES = 'import type { NextFunction, Request, Response } from "express";'

PACK_UNITS = [
    {
        # languages/typescript.md under the doc's OWN "non-negotiable" tsconfig set (strict,
        # noUncheckedIndexedAccess, exactOptionalPropertyTypes, noImplicitReturns, noFallthroughCasesInSwitch);
        # Stage 3 decorators, i.e. no experimentalDecorators
        "name": "lang-typescript",
        "blocks": refs("typescript", 2, 3, 4, 5, 6, 7, 8, 10, 12),
        "place": {
            "typescript#2": {"path": "src/result.ts", "prelude": lines(
                'import type { z } from "zod";',
                "interface Config { port: number }",
                "declare const ConfigSchema: z.ZodType<Config>;",
                "type FieldError = { field: string; code: string; message: string };",
                "declare class ValidationError extends Error { constructor(details: FieldError[]); }",
                "declare function toFieldErrors(issues: z.core.$ZodIssue[]): FieldError[];",
            )},
            "typescript#3": "src/user-schema.ts",
            "typescript#4": {"path": "src/strict.ts", "prelude": lines(
                "interface LineItem { price: number; quantity: number }",
                "interface User { id: string; name: string }",
                "type FieldError = { field: string; code: string; message: string };",
                "declare class AppError extends Error { constructor(code: string, message: string); }",
            )},
            "typescript#5": {"path": "src/performance.tsx", "prelude": lines(
                "declare function Skeleton(): React.JSX.Element;",
                "interface Item { id: string; name: string }",
                "interface RawData { id: string; value: number }",
                "declare function isValid(row: RawData): boolean;",
                "declare function transform(row: RawData): Item;",
                "declare function ChildComponent(props: { items: Item[]; onClick: (id: string) => void }): React.JSX.Element;",
                "type Data = { widgets: Item[] };",
                'declare const DataSchema: import("zod").ZodType<Data>;',
                "declare class HttpError extends Error { constructor(status: number); }",
            )},
            "typescript#6": {"path": "src/error-boundary.ts", "prelude": lines(
                'import type { Express } from "express";',
                'import type { z } from "zod";',
                "declare const app: Express;",
                PINO_LOGGER,
                "declare const userService: { create(tenantId: string, body: unknown): Promise<{ id: string }> };",
                "interface Config { port: number }",
                "declare const ConfigSchema: z.ZodType<Config>;",
                "declare function toFieldErrors(issues: z.core.$ZodIssue[]): FieldError[];",
                "declare function reportToErrorTracker(error: Error, componentStack: string | null | undefined): void;",
            )},
            "typescript#7": {"path": "src/async.ts", "prelude": lines(
                "interface Order { id: string; userId: string }",
                "interface CreateOrderInput { userId: string; reference: string }",
                'declare const CreateOrderSchema: import("zod").ZodType<CreateOrderInput>;',
                "declare const orderRepo: { create(input: CreateOrderInput): Promise<Order> };",
                "declare const notificationService: {",
                "  send(userId: string, event: string): Promise<void>;",
                "  getUnread(userId: string): Promise<string[]>;",
                "};",
                "declare class UniqueConstraintError extends Error {}",
                "declare class ConflictError extends Error { constructor(message: string); }",
                "interface Dashboard { profile: { name: string }; orders: Order[]; notifications: string[] }",
                "declare const userService: { getProfile(userId: string): Promise<{ name: string }> };",
                "declare const orderService: { listRecent(userId: string, n: number): Promise<Order[]> };",
                "declare const emailService: { send(email: string): Promise<void> };",
                PINO_LOGGER,
                "declare class HttpError extends Error { constructor(status: number, body?: string); }",
                "declare const WIDGETS_API_URL: string;",
                "interface Widget { id: string }",
                "declare const widgetService: {",
                "  list(tenantId: string, page: { cursor: string; limit: number }): Promise<{ items: Widget[]; cursor: string; hasMore: boolean }>;",
                "};",
                "declare const tenantId: string;",
                "declare function processBatch(batch: Widget[]): Promise<void>;",
                "declare function processItem(item: string): Promise<void>;",
            )},
            "typescript#8": {"path": "src/types-deep.ts", "prelude": lines(
                "interface Widget { id: string; tenantId: string; name: string; status: string; createdAt: Date; updatedAt: Date }",
                "interface Component { id: string; tenantId: string; name: string }",
            )},
            "typescript#10": {"path": "src/decorators.ts", "prelude": lines(
                PINO_LOGGER,
                "declare class AppError extends Error { readonly retryable: boolean; }",
                "interface Widget { id: string; tenantId: string; name: string }",
                "interface WidgetRepository { findById(tenantId: string, id: string): Promise<Widget> }",
            )},
            "typescript#12": {"path": "src/error-hierarchy.ts", "prelude": lines(
                "interface Widget { id: string; tenantId: string; name: string }",
                "interface CreateInput { name: string }",
                "interface Config { port: number }",
                'declare const ConfigSchema: import("zod").ZodType<Config>;',
                "declare const repo: {",
                "  findById(tenantId: string, id: string): Promise<Widget | null>;",
                "  create(input: CreateInput): Promise<Widget>;",
                "};",
                PINO_LOGGER,
            )},
        },
        "modules": True,
        "shims": ["lang-ts", "packs-express"],
        "compilerOptions": {
            "exactOptionalPropertyTypes": True,
            "noImplicitReturns": True,
            "noFallthroughCasesInSwitch": True,
            "lib": ["es2023", "dom", "dom.iterable"],
            "types": ["node"],
        },
    },
    {
        # the NestJS half of the decorators section: legacy decorators, as a NestJS project compiles them
        "name": "lang-typescript-nest",
        "blocks": ["typescript#11"],
        "place": {"typescript#11": {"path": "src/nest-decorators.ts", "prelude": lines(
            "interface AuthUser { id: string; tenantId: string; roles: string[] }",
            "interface Widget { id: string; name: string }",
            "interface WidgetPage { items: Widget[]; nextCursor: string | null }",
            "declare class WidgetService {",
            "  get(tenantId: string, id: string): Promise<Widget>;",
            "  list(tenantId: string, page: { cursor?: string | undefined; limit: number }): Promise<WidgetPage>;",
            "}",
        )}},
        "decorators": "legacy",
        "compilerOptions": {"exactOptionalPropertyTypes": True, "noImplicitReturns": True,
                            "noFallthroughCasesInSwitch": True},
    },
    {
        # frameworks/express.md against the archetype modules it names: AppError + constructors, the request-id
        # middleware, the pino logger and AuthenticatedRequest
        "name": "pack-express",
        "blocks": refs("express", 1, 2, 3, 4, 5) + refs("error-handling-typescript", 1, 2)
        + ["crud-service-typescript#9", "auth-middleware-typescript#2", "crud-handler-typescript#6"],
        "shims": ["pack-express"],
    },
    {
        # frameworks/nestjs.md on the archetype NestJS stack (JwtAuthGuard, CurrentUser, AppErrorFilter,
        # validationExceptionFactory, conflict()); the spec is type-checked (Jest types)
        "name": "pack-nestjs",
        "blocks": NEST_STACK + refs("nestjs", 1, 2, 3, 4, 5),
        "place": {"nestjs#3": {"path": "src/main.pipes.ts", "wrap": "function", "prelude": lines(
            'import { ValidationPipe, type INestApplication } from "@nestjs/common";',
            'import { AppErrorFilter, validationExceptionFactory } from "./filters/app-error.filter";',
            "declare const app: INestApplication;",
        )}},
        "decorators": "legacy",
        "prisma": True,
        "shims": ["crud-stack", "nest-stack", "pack-nestjs"],
        "compilerOptions": {"types": ["node", "jest"]},
    },
    {
        # frameworks/fastify.md as one app: build(), plugins, schemas, routes, error handler — and its inject()
        # tests RUN with node:test (WidgetService and verifyJwt are in-memory project stubs, shims/pack-fastify)
        "name": "pack-fastify",
        "blocks": refs("fastify", *range(1, 11)),
        "place": {
            "fastify#6": {"path": "src/plugins/hooks.ts", "prelude": lines(
                'import type { FastifyPluginAsync } from "fastify";',
                "declare function setTenantContext(db: import(\"@prisma/client\").PrismaClient, tenantId: string): Promise<void>;",
                "export const hooksPlugin: FastifyPluginAsync = async (fastify) => {",
            ), "postlude": "};"},
            "fastify#10": {"path": "src/plugins/shared-schemas.ts", "prelude": lines(
                'import type { FastifyPluginAsync } from "fastify";',
                "export const sharedSchemasPlugin: FastifyPluginAsync = async (fastify) => {",
            ), "postlude": "};"},
        },
        "prisma": True,
        "shims": ["pack-fastify"],
        "node_test": {"entry": "src/widgets.test.ts", "files": ["src/types/fastify.d.ts"],
                      "env": {"DATABASE_URL": "postgresql://harness:harness@127.0.0.1:1/harness"}},
    },
    {
        # frameworks/trpc.md: server (init, router, context) + the @trpc/tanstack-react-query client
        "name": "pack-trpc",
        "blocks": refs("trpc", 1, 2, 3, 4),
        "place": {
            "trpc#1": "src/server/trpc.ts",
            "trpc#2": "src/server/routers/user.ts",
            "trpc#3": "src/server/context.ts",
            "trpc#4": "src/client/trpc.tsx",
        },
        "shims": ["pack-trpc"],
        "compilerOptions": {"lib": ["es2023", "dom", "dom.iterable"], "types": ["node"]},
    },
    {
        # frameworks/graphql.md's TypeScript blocks: Apollo-style resolvers + per-request DataLoaders
        "name": "pack-graphql",
        "blocks": refs("graphql", 1, 2),
        "shims": ["pack-graphql"],
    },
    {
        # testing/vitest.md: config, setup, unit/component/mock/hook/snapshot samples (type-checked; the
        # components they render are the project's)
        "name": "pack-vitest",
        "kind": "ui",
        "blocks": refs("vitest", *range(1, 8)),
        "place": {
            "vitest#3": "src/utils/format.test.ts",
            "vitest#4": "src/components/UserCard.test.tsx",
            "vitest#5": "src/components/UserProfile.test.tsx",
            "vitest#6": "src/hooks/useCounter.test.ts",
            "vitest#7": "src/components/Badge.test.tsx",
        },
        "shims": ["pack-vitest"],
        "compilerOptions": {"types": ["vitest/globals"]},
    },
    {
        # testing/contract-testing.md's pact-js consumer test, RUN: Pact's mock server answers the consumer's
        # client (shims/pack-pact) and the pact file is written
        "name": "pack-pact",
        "blocks": ["contract-testing#1"],
        "place": {"contract-testing#1": "tests/widget.pact.test.ts"},
        "shims": ["pack-pact"],
        "vitest": ["tests/widget.pact.test.ts"],
    },
    {
        # testing/property-based.md's fast-check properties, RUN (paginate is a project stub)
        "name": "pack-fastcheck",
        "blocks": ["property-based#1"],
        "place": {"property-based#1": "src/properties.test.ts"},
        "shims": ["pack-fastcheck"],
        "vitest": ["src/properties.test.ts"],
    },
    {
        # testing/load-testing.md's k6 scripts: JavaScript, type-checked (checkJs) against @types/k6
        "name": "pack-k6",
        "blocks": refs("load-testing", 1, 2, 3, 4, 5),
        "place": {
            "load-testing#2": "tests/perf/load.js",
            "load-testing#3": "tests/perf/stress.js",
            "load-testing#4": "tests/perf/spike.js",
            "load-testing#5": "tests/perf/ci-thresholds.js",
        },
        "compilerOptions": {"types": ["k6"], "lib": ["es2023"]},
    },
    {
        # core/observability-patterns.md: request logger, pino setup, OTel metrics + tracing, redaction,
        # request ids (src/lib/logger.ts = crud-service-typescript.md's pino logger)
        "name": "core-observability",
        "blocks": refs("observability-patterns", 1, 2, 3, 4, 5, 6) + ["crud-service-typescript#9"],
        "place": {
            "observability-patterns#1": {"path": "src/obs/context-logger.ts", "prelude": lines(
                EXPRESS_TYPES,
                'import { logger } from "../lib/logger";',
                "declare function getTraceId(req: Request): string;",
                "declare const req: Request; // the usage line below runs inside a handler",
                "declare const order: { id: string; totalCents: number };",
            )},
            "observability-patterns#2": {"path": "src/obs/pino-setup.ts", "prelude": lines(
                "declare const req: { tenantId: string; id: string };",
                "declare function getTraceId(req: unknown): string;",
                "declare const order: { id: string; items: unknown[]; total: number };",
            )},
            "observability-patterns#3": {"path": "src/obs/metrics.ts", "prelude": EXPRESS_TYPES},
            "observability-patterns#4": {"path": "src/obs/tracing.ts", "prelude": lines(
                "interface Context { tenantId: string }",
                "interface CreateOrderReq { items: { sku: string; qty: number }[] }",
                "interface Order { id: string }",
                "declare const repo: { save(ctx: Context, order: Order): Promise<Order> };",
                "declare function buildOrder(req: CreateOrderReq): Order;",
            )},
            "observability-patterns#5": {"path": "src/obs/redaction.ts", "prelude": 'import pino from "pino";'},
            "observability-patterns#6": {"path": "src/obs/request-id.ts", "prelude": lines(
                "interface RequestContext { requestId: string; serviceToken: string; signal: AbortSignal }",
            )},
        },
        "modules": True,
        "shims": ["packs-express"],
    },
    {
        # core/resiliency-patterns.md: circuit breaker, idempotent-only retry, degradation, health + graceful
        # shutdown (one server file), bulkhead, per-tenant rate limit
        "name": "core-resiliency",
        "blocks": refs("resiliency-patterns", 1, 2, 3, 4, 5, 6, 7) + ["crud-service-typescript#9"],
        "place": {
            "resiliency-patterns#1": {"path": "src/res/circuit-breaker.ts", "prelude": lines(
                'import type { Logger } from "pino";',
                "declare class CircuitOpenError extends Error { constructor(name: string); }",
            )},
            "resiliency-patterns#2": {"path": "src/res/retry.ts", "prelude": lines(
                "declare class HttpError extends Error { status: number; retryAfterMs?: number }",
                "declare function sleep(ms: number, signal?: AbortSignal): Promise<void>;",
            )},
            "resiliency-patterns#3": {"path": "src/res/degrade.ts", "prelude": lines(
                "interface Product { id: string }",
                "interface ProductPage { product: Product; recommendations: Product[]; reviews: string[]; degraded: boolean }",
                "declare const productRepo: { findById(id: string): Promise<Product> };",
                "declare const recommendationService: { getFor(id: string): Promise<Product[]> };",
                "declare const reviewService: { getFor(id: string): Promise<string[]> };",
            )},
            "resiliency-patterns#4": {"path": "src/res/server.ts", "prelude": lines(
                'import express from "express";',
                'import type { Pool } from "pg";',
                'import { logger } from "../lib/logger";',
                "const app = express();",
                "declare const pool: Pool;",
                "declare function withTimeout<T>(p: Promise<T>, ms: number): Promise<T>;",
            )},
            "resiliency-patterns#5": {"path": "src/res/bulkhead.ts", "prelude": lines(
                "declare class BulkheadFullError extends Error { constructor(name: string, max: number); }",
            )},
            "resiliency-patterns#6": {"path": "src/res/rate-limit.ts", "prelude": EXPRESS_TYPES},
            "resiliency-patterns#7": {"path": "src/res/server.ts", "prelude": lines(
                "declare function sleep(ms: number): Promise<void>;",
                "declare const consumer: { stop(): Promise<void> };",
                "declare const redis: { quit(): Promise<unknown> };",
                "declare const meterProvider: { shutdown(): Promise<void> };",
                "declare const tracerProvider: { shutdown(): Promise<void> };",
            )},
        },
        "modules": True,
        "shims": ["packs-express"],
    },
    {
        # core/ design samples that are real code: interface segregation, a factory, a test-data builder
        "name": "core-design",
        "blocks": ["software-architecture#3", "software-architecture#5", "testing-principles#1"],
        "place": {
            "software-architecture#3": {"path": "src/isp.ts", "prelude": lines(
                "interface Entity { id: string }",
                "interface Filter { tenantId: string }",
            )},
            "software-architecture#5": {"path": "src/notification-factory.ts", "prelude": lines(
                "type NotificationChannel = 'email' | 'sms' | 'push';",
                "interface NotificationPayload { to: string; body: string }",
                "interface Notification { send(): Promise<void> }",
                "declare class EmailNotification implements Notification { constructor(p: NotificationPayload); send(): Promise<void>; }",
                "declare class SMSNotification implements Notification { constructor(p: NotificationPayload); send(): Promise<void>; }",
                "declare class PushNotification implements Notification { constructor(p: NotificationPayload); send(): Promise<void>; }",
            )},
            "testing-principles#1": {"path": "src/factories.ts", "prelude": lines(
                "interface User { id: string; tenantId: string; email: string; name: string; role: 'member' | 'admin' }",
            )},
        },
        "modules": True,
    },
    {
        # api/response-envelope.md's TS types, core/api-excellence.md's restatement of them (must be IDENTICAL:
        # shims/api-envelope/src/types/envelope-parity.ts) and its openapi-typescript usage
        "name": "api-envelope",
        "blocks": ["response-envelope#1", "api-excellence#1", "api-excellence#2"],
        "place": {
            "response-envelope#1": "src/types/api.ts",
            "api-excellence#1": "src/list-users.ts",
            "api-excellence#2": {"path": "src/types/api-excellence.ts",
                                 "postlude": "export type { ApiSuccess, Pagination, ApiErrorBody };"},
        },
        "shims": ["api-envelope"],
    },
]
UNITS += PACK_UNITS


SKIP = {
    "performance-typescript#31": "barrel-export illustration: `export * from './orders'` etc. name the reader's own "
    "modules; there is no library API in it to check.",
    "observability-typescript#24": "intentionally elided body: createOrder(): Promise<Order> ends in `// ...`, so it "
    "can't type-check (TS2355). The nestjs-pino API it shows (LoggerModule, Logger) is compiled by observability-nest.",
    # --- backend packs: illustrations, not code to copy (none has a library API in it)
    "typescript#1": "Good/Bad signature pair for the no-`any` rule: both are named processUser and both bodies "
    "are elided (`{ ... }`).",
    "typescript#9": "a catalogue of alternative module forms side by side (one name exported as named, default and "
    "re-export, then imported) — deliberately not one module, so tsc reports the duplicates. Its tsconfig advice "
    "(`paths` without `baseUrl`, removed in TS 7: TS5102) was checked with this harness's tsc.",
    "code-quality#1": "BAD/GOOD refactoring sketch: both are named processPayment and the BAD body is elided.",
    "code-quality#2": "BAD/GOOD parameter-design sketch: two body-less createUser signatures.",
    "code-quality#3": "BAD/GOOD guard-clause sketch: both are named handleRequest, over hypothetical helpers.",
    "code-quality#4": "BAD/GOOD sketch with an elided factory body (`/* switch on 5 types, only 1 used */`).",
    "code-quality#5": "naming-convention listing: body-less signatures and sample declarations.",
    "software-architecture#1": "SRP BAD/GOOD sketch: classes whose method bodies are elided (`/* ... */`).",
    "software-architecture#2": "LSP BAD example, broken on purpose (undeclared width/height; Rectangle and Square "
    "are each declared twice, BAD and GOOD).",
    "software-architecture#4": "DIP BAD/GOOD sketch: UserService declared twice and an elided `query(...)` call.",
}
