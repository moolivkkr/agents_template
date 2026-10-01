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

SKIP = {
    "performance-typescript#31": "barrel-export illustration: `export * from './orders'` etc. name the reader's own "
    "modules; there is no library API in it to check.",
    "observability-typescript#24": "intentionally elided body: createOrder(): Promise<Order> ends in `// ...`, so it "
    "can't type-check (TS2355). The nestjs-pino API it shows (LoggerModule, Logger) is compiled by observability-nest.",
}
