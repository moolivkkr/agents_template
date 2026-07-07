# Skill Index

> Machine- and human-readable index of every skill in `.claude/skills/` (207 files). Agents
> should consult this index and load only the skill files they need (by path) rather than
> pulling whole large files blindly. Columns: **File** (path relative to `.claude/skills/`),
> **Description** (one line), **Tags**. Redirect stubs are marked `↪` and point to their canonical target.

> Regenerate discipline: when you add or rename a skill, add its row here in the matching category.

## Core (31)

| File | Description | Tags |
|------|-------------|------|
| `core/adaptive-replan.md` | Failure classification and minimum re-test scope — how an agent re-plans after a failed step without redoing the whole phase | replanning, failure-handling, testing, intelligence, core |
| `core/agent-common.md` | Shared blocks every agent inherits — required reading, definition of done, no-intrinsic-self-correction, lessons write-back, severity model, output template | agent-protocol, dod, verification, memory, core |
| `core/api-design.md` | ↪ Redirect → api-excellence.md | — |
| `core/api-excellence.md` | Production API patterns — OpenAPI-first, cursor pagination, domain error codes, idempotency, response envelopes, HATEOAS, versioning strategy | api, rest, pagination, errors, idempotency, openapi |
| `core/auto-research.md` | Self-answering protocol — resolve open questions via research (web + code) instead of pausing for human input, with a confidence threshold | research, autonomy, decisions, web, core |
| `core/change-impact-analysis.md` | Git-diff-based test selection — map changed files to the minimal set of tests/phases to re-run for per-phase regression | regression, test-selection, git, impact-analysis, core |
| `core/code-quality.md` | Code quality enforcement — self-review, function size, naming, KISS, DRY, incremental development, early returns, nesting limits | quality, clean-code, naming, refactoring, best-practices |
| `core/context-budget-protocol.md` | Context budget discipline — selective loading, summarization, and INDEX/frontmatter-driven skill retrieval to stay within the window | context, tokens, selective-loading, efficiency, core |
| `core/debate-protocol.md` | Multi-specialist debate — research, debate, collaborate, decide; produces a durable verdict promoted to the decisions ledger | debate, decisions, multi-agent, consensus, core |
| `core/deep-research.md` | Ultra-deep product and market research protocol — vendor/capability/persona analysis feeding /init and /research | research, market, vendors, personas, core |
| `core/dual-ledger-replan.md` | Dual-ledger replanning — track intended vs actual work across two ledgers to re-plan safely and preserve durable decisions | replanning, ledger, decisions, state, core |
| `core/edit-validation.md` | Reject malformed edits before writing — validate structure/syntax of an edit against the target file to prevent corrupt writes | editing, validation, safety, tooling, core |
| `core/eval-harness.md` | Measure the framework's own output quality — score tasks on outcome and trajectory, compare against a baseline to detect improvement/regression | eval, quality, benchmark, trajectory, core |
| `core/gate-verification.md` | Evidence-based, graded, cross-checked phase gate — the checklist and proof requirements that let a phase pass | gate, verification, evidence, quality, core |
| `core/git-workflow.md` | Trunk-based branching strategy, conventional commits, PR process, branch naming, commit message format | git, workflow, ci, branching |
| `core/implementation-guidelines-template.md` | 24-section template for generating comprehensive IMPLEMENTATION_GUIDELINES.md — used by impl_guidelines_agent to produce the engineering contract for all dow... | template, implementation, guidelines, architecture, engineering-standards |
| `core/memory-as-tools.md` | Retrieval discipline for Tier 1/Tier 2 memory — query lessons/codebase KB on demand by category/tag rather than loading whole files | memory, retrieval, lessons, knowledge-base, core |
| `core/model-routing.md` | Complexity-based model routing — pick haiku/sonnet/opus per task complexity to balance cost and quality | model-routing, cost, complexity, intelligence, core |
| `core/observability-patterns.md` | Structured logging, OpenTelemetry metrics/traces, tenant-aware observability, error taxonomy, SLA metrics, correlation IDs | observability, logging, metrics, tracing, opentelemetry, monitoring |
| `core/product-workflow-research.md` | Skill pack — research a product's configuration workflows from docs/videos/community into screen-by-screen guides and config schemas | research, workflows, product, config, core |
| `core/repo-map.md` | Ranked repo map — Personalized-PageRank over a tree-sitter symbol graph to surface the most relevant files for a task | repo-map, ranking, tree-sitter, codebase, core |
| `core/resiliency-patterns.md` | Circuit breakers, retries, timeouts, graceful degradation, health checks, bulkhead, rate limiting, graceful shutdown — production resilience patterns | resiliency, circuit-breaker, retry, timeout, health-check, rate-limiting |
| `core/scale-adaptive-depth.md` | Scale-adaptive workflow depth — match pipeline rigor (waves, reviews) to project size and risk instead of one fixed depth | workflow, scaling, depth, adaptivity, core |
| `core/security-owasp.md` | OWASP Top 10, input validation, injection prevention, auth best practices, secrets management, dependency scanning | security, owasp, auth, jwt, secrets |
| `core/shared-backend-patterns.md` | Language-agnostic backend contracts — the shared patterns that per-language files (go/python/typescript/java/rust) extend | backend, contracts, language-agnostic, architecture, core |
| `core/shared-context-protocol.md` | Ground truth for every session and subagent — the memory-tier model (facts/decisions/lessons/KB) and how context propagates | memory, context, ground-truth, tiers, core |
| `core/software-architecture.md` | SOLID principles, design patterns, interface-based development, dependency injection, layer boundaries — with Go and TypeScript examples | architecture, solid, patterns, dependency-injection, clean-architecture |
| `core/structured-lessons.md` | Tagged, indexed lessons with confidence levels — the schema and write/read discipline for Tier 1 lessons | lessons, memory, tagging, confidence, core |
| `core/testing-principles.md` | Test pyramid, AAA pattern, naming conventions, test isolation, fixtures, coverage gates, what to test vs skip | testing, unit, integration, e2e, coverage |
| `core/vendor-comparison-framework.md` | Framework for comparing vendors/open-source options — research-first, criteria matrix, evidence-cited, no unverified claims | vendors, comparison, research, evaluation, core |
| `core/verification-protocol.md` | Systematic verification checklist — 4-level depth, assignment-delivery audit, anti-rationalization rules for ensuring implementations are complete and correct | verification, quality, checklist, review, completeness |

## Testing (17)

| File | Description | Tags |
|------|-------------|------|
| `testing/contract-testing.md` | Contract testing patterns for microservice API evolution. | — |
| `testing/external-service-mocks.md` | Mock patterns for common SaaS services in tests — Stripe, Auth0/Clerk, SendGrid/Postmark, AWS S3, Twilio, OpenAI/Claude API with examples for MSW (TS), WireM... | testing, mocking, stripe, auth0, sendgrid, s3 |
| `testing/gomock.md` | gomock patterns for Go mock generation and verification. | — |
| `testing/junit-mockito.md` | JUnit 5 + Mockito skill pack — unit tests, controller tests with MockMvc, repository tests with @DataJpaTest, integration tests with Testcontainers, AssertJ,... | java, junit, mockito, testing, spring-boot |
| `testing/load-testing.md` | Load testing patterns for performance validation and capacity planning. | — |
| `testing/msw.md` | MSW (Mock Service Worker) patterns for API mocking in tests and development. | — |
| `testing/playwright.md` | Playwright patterns for browser E2E testing. | — |
| `testing/property-based.md` | Property-based testing patterns for robust input validation. | — |
| `testing/pytest.md` | Pytest skill pack — fixtures, parametrize, async tests, mocking, database fixtures with testcontainers, coverage, assertion patterns for Python 3.11+ | python, pytest, testing, asyncio, testcontainers |
| `testing/reproduction-first.md` | Reproduction-Test-First Self-Repair Loop | — |
| `testing/rust-test.md` | Rust testing patterns for backend services. | — |
| `testing/targeted-testing.md` | Targeted Component Testing | — |
| `testing/test-case-generation.md` | Test Case Generation — Exhaustive Enumeration for All Tiers | — |
| `testing/test-case-traceability.md` | Test Case ID Traceability — Spec-to-Test Inventory Enforcement | — |
| `testing/testcontainers.md` | testcontainers-go patterns for container-based integration testing. | — |
| `testing/testify.md` | testify patterns for Go testing. | — |
| `testing/vitest.md` | Vitest patterns for Vite-native unit and component testing. | — |

## UI (16)

| File | Description | Tags |
|------|-------------|------|
| `ui/README.md` | Index and strict precedence order for all UI skills — resolves conflicts by giving each UI skill one non-overlapping scope; UI agents read this first | ui-standards, precedence, index, navigation, ui |
| `ui/accessibility-patterns.md` | WCAG 2.2 AA implementation reference — semantic elements, ARIA, keyboard nav, focus management, contrast, screen-reader patterns | accessibility, a11y, wcag, aria, ui |
| `ui/advanced-state-patterns.md` | Complex UI state — optimistic updates, WebSocket integration, offline-first, URL state, cross-tab sync with TanStack Query + React | state, tanstack-query, websocket, optimistic, ui |
| `ui/api-integration-patterns.md` | UI data-fetching layer — TanStack Query hooks, HTTP client setup, request/response typing; bans direct fetch in components | api, tanstack-query, http, data-fetching, ui |
| `ui/component-composition.md` | Component composition patterns — building from shadcn/ui primitives, compound components, slots, and React composition over configuration | components, shadcn, composition, react, ui |
| `ui/error-handling-patterns.md` | UI error handling — HTTP-status-to-UI mapping, error boundaries, toast/inline patterns, retry, and user-facing messages | errors, error-boundary, ux, resilience, ui |
| `ui/form-patterns.md` | Form patterns — React Hook Form + Zod + shadcn/ui, validation, field arrays, submission states, and accessible error display | forms, react-hook-form, zod, validation, ui |
| `ui/form-validation-protocol.md` | Protocol — derive Zod validation schemas from data-contracts.md request types so client validation matches the API contract | forms, zod, validation, data-contracts, ui |
| `ui/loading-states.md` | Loading patterns — skeleton screens, Suspense, progressive loading, and layout-shift prevention | loading, skeleton, suspense, ux, ui |
| `ui/professional-ui-standards.md` | Generic house UI defaults — 4px spacing grid, typography scale, z-index, state discipline, density, motion, anti-patterns (overridden by a project design sys... | ui-standards, spacing, typography, design-system, ui |
| `ui/responsive-patterns.md` | Mobile-first responsive design — breakpoints, fluid layouts, container queries, and progressive enhancement at larger sizes | responsive, mobile-first, breakpoints, layout, ui |
| `ui/shadcn.md` | shadcn/ui patterns for composable, accessible React components — install, theming, and component usage conventions | shadcn, components, react, tailwind, ui |
| `ui/structured-wireframe-format.md` | Optional YAML-based wireframe format — typed data-source references, explicit UI states, validated against data-contracts.md | wireframe, yaml, specs, data-contracts, ui |
| `ui/tailwind.md` | Tailwind CSS utility patterns for layout, spacing, flex/grid, and responsive design | tailwind, css, layout, responsive, ui |
| `ui/type-generation-protocol.md` | Protocol — generate types/api.ts from data-contracts.md so UI code shares one type source with the API response schemas | types, codegen, data-contracts, type-safety, ui |
| `ui/vertix-portal-design-system.md` | Vertix portal house style — tokens, component library, theme, severity scale, card radius/shadow; tier-2 override of generic UI standards | design-system, vertix, tokens, theme, ui |

## UI — Archetypes (6)

| File | Description | Tags |
|------|-------------|------|
| `ui/archetypes/component-test.md` | React/TypeScript component test archetype — Vitest + React Testing Library, render/interaction/form/list tests, MSW for API mocking, accessibility assertions | react, typescript, testing, vitest, rtl, archetype |
| `ui/archetypes/dashboard-page.md` | Page Archetype: Dashboard Page | — |
| `ui/archetypes/detail-page.md` | Page Archetype: Detail Page | — |
| `ui/archetypes/form-page.md` | Page Archetype: Form Page (Create / Edit) | — |
| `ui/archetypes/list-page.md` | Page Archetype: List Page | — |
| `ui/archetypes/settings-page.md` | Page Archetype: Settings Page | — |

## Backend — Archetypes (88)

| File | Description | Tags |
|------|-------------|------|
| `backend/archetypes/auth-middleware-go.md` | Go auth middleware archetype — JWT validation, RBAC, tenant context, rate limiting, CORS, API key auth, request ID, structured logging | go, middleware, auth, jwt, rbac, archetype |
| `backend/archetypes/auth-middleware-java.md` | Spring Security auth archetype — SecurityFilterChain, JwtAuthenticationFilter, @PreAuthorize, RBAC, rate limiting, CORS, request ID filter, API key authentic... | java, spring-boot, spring-security, jwt, rbac, middleware |
| `backend/archetypes/auth-middleware-python.md` | Python FastAPI auth middleware archetype — JWT dependency, CurrentUser, role-based access, rate limiting, CORS, request ID (contextvars), API key authentication | python, fastapi, middleware, auth, jwt, rbac |
| `backend/archetypes/auth-middleware-rust.md` | Axum auth middleware archetype — JWT validation (jsonwebtoken), AuthUser extractor (FromRequestParts), role-based access (RequireRole layer), rate limiting,... | rust, axum, auth, middleware, jwt, rbac |
| `backend/archetypes/auth-middleware-typescript.md` | TypeScript auth middleware archetype — JWT verification (jsonwebtoken + jose), Express middleware, NestJS Guard, RBAC, rate limiting, CORS, request ID, struc... | typescript, middleware, auth, jwt, rbac, express |
| `backend/archetypes/auth-middleware.md` | ↪ Redirect → auth-middleware-go.md | — |
| `backend/archetypes/crud-handler-go.md` | Go HTTP handler archetype — chi router, JSON request/response, cursor pagination, error mapping, OpenTelemetry, structured logging | go, handler, http, chi, archetype, backend |
| `backend/archetypes/crud-handler-java.md` | Spring Boot REST controller archetype — @RestController, request/response DTOs, pagination, error mapping, auth, OpenAPI annotations, structured logging | java, spring-boot, controller, rest, archetype, backend |
| `backend/archetypes/crud-handler-python.md` | Python FastAPI handler archetype — route decorators, Pydantic v2 request/response models, dependency injection, cursor + offset pagination, error mapping, au... | python, fastapi, handler, http, archetype, backend |
| `backend/archetypes/crud-handler-rust.md` | Axum handler archetype — extractors, JSON request/response, cursor + offset pagination, error mapping, tracing, structured validation | rust, axum, handler, http, archetype, backend |
| `backend/archetypes/crud-handler-test-go.md` | Go HTTP handler test archetype — httptest, chi router, JSON request/response validation, auth tests, error mapping, pagination, response envelope assertions | go, handler, http, unit-test, archetype, backend |
| `backend/archetypes/crud-handler-test-java.md` | Spring Boot controller test archetype — @WebMvcTest, MockMvc, @MockBean, JSON path assertions, pagination, validation, auth, error responses, parameterized t... | java, spring-boot, controller, unit-test, archetype, backend |
| `backend/archetypes/crud-handler-test-python.md` | Python FastAPI handler test archetype — pytest + httpx AsyncClient, dependency overrides, CRUD endpoint validation, pagination, auth, error mapping, parametr... | python, fastapi, handler, http, unit-test, archetype |
| `backend/archetypes/crud-handler-test-rust.md` | Axum handler test archetype — TestApp helper, reqwest integration tests, CRUD endpoint coverage, pagination (cursor + offset), validation errors, auth tests,... | rust, axum, handler, http, integration-test, archetype |
| `backend/archetypes/crud-handler-test-typescript.md` | TypeScript HTTP handler test archetype — Express (vitest + supertest) and NestJS (jest + supertest) patterns, Zod validation tests, auth tests, error mapping... | typescript, handler, http, unit-test, express, nestjs |
| `backend/archetypes/crud-handler-test.md` | ↪ Redirect → crud-handler-test-go.md | — |
| `backend/archetypes/crud-handler-typescript.md` | TypeScript HTTP handler archetype — Express and NestJS patterns, Zod validation, typed request/response, cursor + offset pagination, async error handling, mi... | typescript, handler, http, express, nestjs, archetype |
| `backend/archetypes/crud-handler.md` | ↪ Redirect → crud-handler-go.md | — |
| `backend/archetypes/crud-repository-go.md` | Go pgx repository archetype — parameterized queries, cursor pagination, soft delete, multi-level caching, tenant isolation, batch operations, optimistic locking | go, repository, pgx, postgres, archetype, backend |
| `backend/archetypes/crud-repository-java.md` | Spring Data JPA repository archetype — JpaRepository, custom queries, Specification API, pagination, soft delete, optimistic locking, multi-tenant filtering | java, spring-boot, jpa, repository, archetype, backend |
| `backend/archetypes/crud-repository-python.md` | Python repository archetype — SQLAlchemy async + asyncpg, parameterized queries, cursor pagination, soft delete, optimistic locking, multi-tenant isolation,... | python, repository, sqlalchemy, asyncpg, postgres, archetype |
| `backend/archetypes/crud-repository-rust.md` | Rust sqlx repository archetype — compile-time checked queries, cursor pagination, soft delete, optimistic locking, multi-tenant isolation, batch operations,... | rust, sqlx, repository, postgres, archetype, backend |
| `backend/archetypes/crud-repository-test-go.md` | Go integration test archetype for repository layer — testcontainers PostgreSQL, transaction-per-test isolation, real DB queries, pagination, tenant isolation... | go, repository, integration-test, postgres, testcontainers, archetype |
| `backend/archetypes/crud-repository-test-java.md` | Spring Data JPA repository integration test archetype — @DataJpaTest, Testcontainers PostgreSQL, real DB queries, Specification filtering, soft delete, optim... | java, spring-boot, jpa, repository, integration-test, testcontainers |
| `backend/archetypes/crud-repository-test-python.md` | Python repository integration test archetype — testcontainers PostgreSQL, per-test transaction rollback, real DB queries, pagination, soft delete, optimistic... | python, repository, integration-test, postgres, testcontainers, archetype |
| `backend/archetypes/crud-repository-test-rust.md` | Rust repository integration test archetype — sqlx::test with automatic migration + rollback, real PostgreSQL CRUD, cursor + offset pagination, soft delete, o... | rust, sqlx, repository, postgres, integration-test, archetype |
| `backend/archetypes/crud-repository-test-typescript.md` | TypeScript repository integration test archetype — Prisma test DB, Drizzle test DB, testcontainers, transaction isolation, CRUD operations, pagination, soft... | typescript, repository, integration-test, prisma, drizzle, postgres |
| `backend/archetypes/crud-repository-test.md` | ↪ Redirect → crud-repository-test-go.md | — |
| `backend/archetypes/crud-repository-typescript.md` | TypeScript repository archetype — Prisma and Drizzle patterns, cursor + offset pagination, soft delete, optimistic locking, multi-tenant filtering, error map... | typescript, repository, prisma, drizzle, postgres, archetype |
| `backend/archetypes/crud-repository.md` | ↪ Redirect → crud-repository-go.md | — |
| `backend/archetypes/crud-service-go.md` | Go service layer archetype — CRUD operations with cache-aside, audit logging, metrics, tenant isolation, transaction support, and input validation | go, service, crud, archetype, backend |
| `backend/archetypes/crud-service-java.md` | Spring Boot service layer archetype — @Service, @Transactional, cache-aside, audit logging, custom exceptions, business logic, tenant isolation | java, spring-boot, service, crud, archetype, backend |
| `backend/archetypes/crud-service-python.md` | Python service layer archetype — async CRUD operations with cache-aside, audit logging, transaction management, tenant isolation, structured logging, and inp... | python, service, crud, archetype, backend, asyncio |
| `backend/archetypes/crud-service-rust.md` | Rust service layer archetype — async CRUD with trait-object repositories, cache-aside, audit logging, tracing, tenant isolation, transaction support, input v... | rust, service, crud, archetype, backend |
| `backend/archetypes/crud-service-test-go.md` | Go unit test archetype for the service layer — mocked dependencies, table-driven tests, testify suite, cache/audit/metrics verification, tenant isolation, ed... | go, service, unit-test, archetype, backend, testing |
| `backend/archetypes/crud-service-test-java.md` | Spring Boot service unit test archetype — @ExtendWith(MockitoExtension), @Mock, @InjectMocks, cache verification, audit logging, optimistic locking, tenant i... | java, spring-boot, service, unit-test, archetype, backend |
| `backend/archetypes/crud-service-test-python.md` | Python service layer test archetype — pytest + AsyncMock, mocked repository/cache/audit, table-driven tests, cache-aside verification, optimistic locking, te... | python, service, unit-test, archetype, backend, testing |
| `backend/archetypes/crud-service-test-rust.md` | Rust service unit test archetype — mockall trait mocking, CRUD coverage, cache-aside verification, audit log assertions, optimistic locking, tenant isolation... | rust, service, unit-test, mockall, archetype, backend |
| `backend/archetypes/crud-service-test-typescript.md` | TypeScript service layer unit test archetype — vitest, mocked repository/cache/audit, table-driven tests, cache-aside verification, optimistic locking, tenan... | typescript, service, unit-test, vitest, archetype, backend |
| `backend/archetypes/crud-service-test.md` | ↪ Redirect → crud-service-test-go.md | — |
| `backend/archetypes/crud-service-typescript.md` | TypeScript service layer archetype — CRUD operations with cache-aside, audit logging, tenant isolation, transaction support (Prisma + Drizzle), typed errors,... | typescript, service, crud, prisma, drizzle, archetype |
| `backend/archetypes/crud-service.md` | ↪ Redirect → crud-service-go.md | — |
| `backend/archetypes/dockerfile-go.md` | Go Dockerfile Archetype | — |
| `backend/archetypes/dockerfile-java.md` | Java/Spring Boot optimized Docker archetype — multi-stage build, layered JAR, JVM tuning, non-root user, actuator health check, GraalVM native-image variant | java, spring-boot, docker, dockerfile, archetype, backend |
| `backend/archetypes/dockerfile-python.md` | Python-optimized Docker build archetype — multi-stage builder, non-root user, virtualenv, UV/pip-compile deterministic deps, health check, .dockerignore, Doc... | python, docker, dockerfile, archetype, backend, deployment |
| `backend/archetypes/dockerfile-rust.md` | Rust optimized Docker archetype — multi-stage with cargo-chef dependency caching, minimal runtime (debian-slim or alpine+musl), static linking, non-root user... | rust, docker, dockerfile, devops, archetype, backend |
| `backend/archetypes/dockerfile-typescript.md` | TypeScript/Node.js optimized Dockerfile archetype — multi-stage builds, npm/pnpm/bun variants, non-root user, health checks, .dockerignore, Docker Compose sn... | typescript, docker, nodejs, dockerfile, archetype, backend |
| `backend/archetypes/error-handling-go.md` | Go error handling archetype — domain error taxonomy, error types, HTTP mapping, error middleware, sentinel errors, wrapping guidelines | go, errors, middleware, archetype, backend |
| `backend/archetypes/error-handling-java.md` | Java/Spring Boot error handling archetype — exception hierarchy, @ControllerAdvice, ProblemDetail (RFC 7807), validation error mapping, structured error resp... | java, spring-boot, errors, exception-handling, archetype, backend |
| `backend/archetypes/error-handling-python.md` | Python error handling archetype — AppError base class hierarchy, FastAPI exception handlers, error response envelope, structured logging, error code registry | python, errors, fastapi, archetype, backend |
| `backend/archetypes/error-handling-rust.md` | Rust error handling archetype — AppError enum with thiserror, IntoResponse for Axum, JSON error envelope, From implementations, tracing integration | rust, errors, axum, archetype, backend |
| `backend/archetypes/error-handling-typescript.md` | TypeScript error handling archetype — AppError class, domain error subclasses, Express/NestJS middleware, HTTP mapping, structured error responses matching G... | typescript, errors, middleware, archetype, backend, express |
| `backend/archetypes/error-handling.md` | ↪ Redirect → error-handling-go.md | — |
| `backend/archetypes/grpc-pattern-go.md` | Go gRPC archetype — google.golang.org/grpc, protoc-gen-go, interceptors, server/client streaming, health check, reflection | go, grpc, protobuf, streaming, archetype, backend |
| `backend/archetypes/grpc-pattern-java.md` | Java gRPC archetype — grpc-java, protobuf-gradle-plugin, interceptors, streaming, health check, Spring integration | java, grpc, protobuf, grpc-java, archetype, backend |
| `backend/archetypes/grpc-pattern-python.md` | Python gRPC archetype — grpcio, grpc-tools, interceptors, streaming, health check, asyncio support | python, grpc, protobuf, grpcio, archetype, backend |
| `backend/archetypes/grpc-pattern-rust.md` | Rust gRPC archetype — tonic, prost, interceptors/layers, streaming, health check, reflection | rust, grpc, tonic, prost, streaming, archetype |
| `backend/archetypes/grpc-pattern-typescript.md` | TypeScript gRPC archetype — nice-grpc or @grpc/grpc-js, ts-proto, interceptors, streaming, health check | typescript, grpc, protobuf, nice-grpc, archetype, backend |
| `backend/archetypes/grpc-pattern.md` | Language-neutral gRPC archetype — proto design, unary/streaming RPCs, error handling, interceptors, health checks, reflection, versioning | grpc, protobuf, rpc, streaming, archetype, backend |
| `backend/archetypes/message-queue-pattern.md` | Language-neutral message queue archetype — producer/consumer, exactly-once, fan-out, saga, DLQ, schema evolution, observability across Kafka, RabbitMQ, SQS,... | message-queue, kafka, rabbitmq, sqs, nats, redis-streams |
| `backend/archetypes/migration-pattern-go.md` | PostgreSQL migration archetype — table creation, indexes, soft delete, RLS, seed data, data migrations, naming conventions, rollback safety | go, postgres, migration, sql, archetype, backend |
| `backend/archetypes/migration-pattern-java.md` | Flyway migration archetype — SQL naming conventions, repeatable migrations, Java-based migrations, rollback patterns, seed data, multi-tenant schema, @Flyway... | java, spring-boot, flyway, migration, sql, postgres |
| `backend/archetypes/migration-pattern-python.md` | Python Alembic migration archetype — async env.py setup, auto-generate from SQLAlchemy models, manual migrations, UP/DOWN functions, data migrations, RLS, se... | python, alembic, postgres, migration, sql, archetype |
| `backend/archetypes/migration-pattern-rust.md` | Rust sqlx migration archetype — CLI usage, embedded migrations (sqlx::migrate!), UP/DOWN files, reversible migrations, data migrations, testing, CI integrati... | rust, sqlx, migration, postgres, database, archetype |
| `backend/archetypes/migration-pattern-typescript.md` | TypeScript migration archetype — Prisma migrate (dev/deploy), schema definition, seed scripts, custom SQL, multi-tenant; Drizzle kit (generate/push/migrate),... | typescript, prisma, drizzle, migration, postgres, archetype |
| `backend/archetypes/migration-pattern.md` | ↪ Redirect → migration-pattern-go.md | — |
| `backend/archetypes/observability-go.md` | Go OpenTelemetry integration — traces, metrics, structured logging (slog), correlation IDs, tenant-aware instrumentation, Prometheus endpoint, DB/Redis/HTTP... | go, opentelemetry, observability, tracing, metrics, logging |
| `backend/archetypes/observability-java.md` | Java/Spring Boot observability archetype — OpenTelemetry traces, Micrometer metrics, structured logging with Logback, MDC correlation, tenant-aware instrumen... | java, spring-boot, observability, opentelemetry, micrometer, tracing |
| `backend/archetypes/observability-python.md` | Python observability archetype — OpenTelemetry traces/metrics/logs for FastAPI, structlog JSON pipeline, auto-instrumentation (SQLAlchemy, Redis, httpx), Pro... | python, observability, opentelemetry, tracing, metrics, logging |
| `backend/archetypes/observability-rust.md` | Rust observability archetype — OpenTelemetry traces/metrics via tracing + tracing-opentelemetry, structured logging, Axum middleware, sqlx spans, Prometheus... | rust, observability, tracing, opentelemetry, metrics, logging |
| `backend/archetypes/observability-typescript.md` | TypeScript observability archetype — OpenTelemetry traces/metrics, pino structured logging, Express/NestJS instrumentation, Prisma/Redis spans, log-trace cor... | typescript, observability, opentelemetry, tracing, metrics, logging |
| `backend/archetypes/performance-go.md` | Go performance patterns — connection pooling, memory management, concurrency tuning, profiling (pprof), hot path optimization, database performance, benchmar... | go, performance, profiling, pprof, connection-pooling, concurrency |
| `backend/archetypes/performance-java.md` | Java/Spring Boot performance archetype — HikariCP tuning, JVM container settings, GC selection, JPA batch optimization, virtual threads, Caffeine caching, pr... | java, spring-boot, performance, hikaricp, jvm, caching |
| `backend/archetypes/performance-python.md` | Python performance archetype — asyncio patterns, connection pooling, memory management, SQLAlchemy optimization, caching strategies, profiling tools, GIL con... | python, performance, asyncio, caching, profiling, fastapi |
| `backend/archetypes/performance-rust.md` | Rust performance archetype — connection pooling (sqlx, deadpool-redis, reqwest), memory optimization, async tuning, database performance, profiling, compilat... | rust, performance, pooling, async, profiling, optimization |
| `backend/archetypes/performance-typescript.md` | TypeScript/Node.js performance archetype — event loop management, connection pooling, memory management, database optimization, profiling, caching, TypeScrip... | typescript, performance, nodejs, caching, profiling, connection-pooling |
| `backend/archetypes/websocket-pattern-go.md` | Go WebSocket archetype — gorilla/websocket or nhooyr/websocket, goroutine per connection, hub pattern, graceful shutdown | go, websocket, gorilla, real-time, archetype, backend |
| `backend/archetypes/websocket-pattern-java.md` | Java/Spring Boot WebSocket archetype — Spring WebSocket, STOMP, SimpMessagingTemplate, session management, auth | java, spring-boot, websocket, stomp, real-time, archetype |
| `backend/archetypes/websocket-pattern-python.md` | Python WebSocket archetype — FastAPI WebSocket, Django Channels, connection manager, rooms, broadcasting, auth | python, websocket, fastapi, django-channels, real-time, archetype |
| `backend/archetypes/websocket-pattern-rust.md` | Rust WebSocket archetype — axum WebSocket, tokio-tungstenite, connection manager, rooms, broadcasting, graceful shutdown | rust, websocket, axum, tokio-tungstenite, real-time, archetype |
| `backend/archetypes/websocket-pattern-typescript.md` | TypeScript WebSocket archetype — ws library, Socket.IO, connection manager, rooms, broadcasting, auth, reconnection | typescript, websocket, ws, socket-io, real-time, archetype |
| `backend/archetypes/websocket-pattern.md` | Language-neutral WebSocket archetype — connection lifecycle, rooms/channels, broadcasting, reconnection, auth, rate limiting, graceful degradation | websocket, real-time, rooms, broadcasting, archetype, backend |
| `backend/archetypes/worker-pattern-go.md` | Go worker/background job archetype — goroutines, channels, signal handling, graceful shutdown, context cancellation, errgroup coordination | go, worker, background-job, goroutines, channels, archetype |
| `backend/archetypes/worker-pattern-java.md` | Java/Spring Boot worker archetype — @Scheduled, CompletableFuture, Spring Cloud Stream, ShedLock, graceful shutdown, structured logging | java, spring-boot, worker, scheduled, background-job, archetype |
| `backend/archetypes/worker-pattern-python.md` | Python worker/background job archetype — Celery, dramatiq, asyncio.Queue, APScheduler, graceful shutdown, structured logging | python, worker, celery, dramatiq, background-job, archetype |
| `backend/archetypes/worker-pattern-rust.md` | Rust worker/background job archetype — tokio::spawn, async channels, CancellationToken, graceful shutdown, tracing instrumentation | rust, worker, tokio, background-job, archetype, backend |
| `backend/archetypes/worker-pattern-typescript.md` | TypeScript worker/background job archetype — BullMQ, node-cron, graceful shutdown, structured logging, health checks | typescript, worker, bullmq, background-job, node-cron, archetype |
| `backend/archetypes/worker-pattern.md` | Language-neutral worker/background job archetype — job queue consumer, cron/scheduled jobs, event handlers, retry with backoff, graceful shutdown, health che... | worker, background-job, queue, cron, archetype, backend |

## Databases (11)

| File | Description | Tags |
|------|-------------|------|
| `databases/dynamodb.md` | DynamoDB patterns for serverless, high-scale key-value and document storage. | — |
| `databases/elasticsearch.md` | Elasticsearch patterns for full-text search, analytics, and log aggregation. | — |
| `databases/firestore.md` | Firestore patterns for document-oriented cloud-native data storage. | — |
| `databases/mongodb.md` | MongoDB patterns for document-oriented data storage. | — |
| `databases/mysql.md` | MySQL (InnoDB) patterns for relational data storage. | — |
| `databases/nebula.md` | NebulaGraph patterns for distributed graph data (nGQL, NebulaGraph 3.x). | — |
| `databases/postgres.md` | PostgreSQL patterns for reliable, performant relational data storage. | — |
| `databases/postgresql.md` | ↪ Redirect → postgres.md | — |
| `databases/query-optimization.md` | Database query optimization — N+1 detection, index strategy, connection pooling, batch operations, query patterns, monitoring | database, performance, postgresql, indexing, connection-pool, monitoring |
| `databases/redis.md` | Redis patterns for caching, sessions, and ephemeral data. | — |
| `databases/sqlite.md` | SQLite patterns for embedded, testing, and single-writer use cases. | — |

## Requirements (10)

| File | Description | Tags |
|------|-------------|------|
| `requirements/acceptance-criteria.md` | Acceptance Criteria Patterns — Testable, Complete, Automatable | — |
| `requirements/business-objectives.md` | Business Objectives Patterns — Measurable OBJ-* That Drive Prioritization | — |
| `requirements/conflict-detection.md` | Conflict Detection Patterns — Finding Contradictions Before They Reach Code | — |
| `requirements/ears-notation.md` | EARS Notation — Requirements That Parse Into Test Cases | — |
| `requirements/edge-case-taxonomy.md` | Edge Case Taxonomy — Systematic Framework for spec_writer | — |
| `requirements/gap-analysis-checklist.md` | Gap Analysis Checklist — 17 Dimensions for Requirement Completeness | — |
| `requirements/nfr-patterns.md` | Non-Functional Requirement Patterns — Scoping, Measuring, Testing | — |
| `requirements/persona-definition.md` | Persona Definition Patterns — Sharp Personas That Drive Feature Scope | — |
| `requirements/requirement-clarity.md` | Requirement Clarity Patterns — Writing Testable, Unambiguous Requirements | — |
| `requirements/traceability-matrix.md` | Traceability Matrix Patterns — Source → BRD → Spec → Test → Deploy | — |

## Languages (5)

| File | Description | Tags |
|------|-------------|------|
| `languages/go.md` | Go patterns — error handling, interfaces, context, goroutines, table-driven tests, module conventions, DI without frameworks | go, golang, patterns, concurrency, testing |
| `languages/java.md` | Java patterns for Spring Boot — layered architecture, dependency injection, JPA/Hibernate, records, streams, JUnit 5 testing | java, spring-boot, jpa, patterns, testing |
| `languages/python.md` | Python patterns — type hints, dataclasses/pydantic, async, dependency injection, pytest, project layout and packaging | python, async, pydantic, patterns, testing |
| `languages/rust.md` | Rust patterns — ownership, Result/Option error handling, traits, async with tokio, cargo layout, testing conventions | rust, ownership, async, traits, testing |
| `languages/typescript.md` | TypeScript patterns — strict compiler config, discriminated unions, generics, type-safe API contracts, error handling, testing | typescript, types, generics, patterns, testing |

## Frameworks (20)

| File | Description | Tags |
|------|-------------|------|
| `frameworks/actix-web.md` | Actix-web framework patterns for Rust HTTP APIs. | — |
| `frameworks/axum.md` | Axum framework patterns for Rust HTTP APIs. | — |
| `frameworks/chi.md` | chi v5 patterns for Go HTTP APIs. | — |
| `frameworks/django.md` | Django patterns for production-ready Python web applications. | — |
| `frameworks/drf.md` | Django REST Framework patterns for Python REST APIs. | — |
| `frameworks/echo.md` | Echo framework patterns for Go HTTP APIs. | — |
| `frameworks/express.md` | Express.js patterns for Node.js HTTP APIs. | — |
| `frameworks/fastapi.md` | FastAPI patterns for Python async HTTP APIs. | — |
| `frameworks/fastify.md` | Fastify framework patterns for TypeScript high-performance HTTP APIs. | — |
| `frameworks/gin.md` | Gin framework patterns for Go HTTP APIs. | — |
| `frameworks/graphql.md` | GraphQL skill pack — schema design, resolvers, DataLoader, auth, pagination, subscriptions, error handling, testing, performance across gqlgen (Go), Strawber... | graphql, api, schema, dataloader, apollo, gqlgen |
| `frameworks/nestjs.md` | NestJS patterns for structured, testable Node.js APIs. | — |
| `frameworks/nextjs.md` | Next.js (App Router) patterns for full-stack React applications. | — |
| `frameworks/quarkus.md` | Quarkus framework patterns for Java cloud-native APIs. | — |
| `frameworks/react.md` | React patterns for functional, accessible, maintainable UIs. | — |
| `frameworks/spring-boot.md` | Spring Boot framework patterns — project structure, dependency injection, configuration, exception handling, validation, security, testing conventions | java, spring-boot, framework, backend |
| `frameworks/svelte.md` | SvelteKit patterns — file-based routing, load functions, runes ($state/$derived/$effect), form actions, and server/client data boundaries | svelte, sveltekit, frontend, runes, ssr |
| `frameworks/tanstack-query.md` | TanStack Query v5 patterns for React data fetching. | — |
| `frameworks/trpc.md` | tRPC patterns — end-to-end type-safe procedures, Zod input validation, routers/context/middleware, and TanStack Query client integration | trpc, typescript, type-safety, api, zod |
| `frameworks/vue.md` | Vue 3 Composition API patterns for reactive, maintainable UIs. | — |

## Infrastructure (6)

| File | Description | Tags |
|------|-------------|------|
| `infrastructure/docker.md` | Docker patterns for containerized application builds and local development. | — |
| `infrastructure/github-actions.md` | GitHub Actions patterns for reliable CI/CD pipelines. | — |
| `infrastructure/kubernetes.md` | Kubernetes patterns for container orchestration and production deployments. | — |
| `infrastructure/localstack-aws-local.md` | LocalStack — Local AWS Service Simulation | — |
| `infrastructure/saas-tenancy-models.md` | SaaS Tenancy Models — Pooled, Dedicated, and Hybrid Architecture | — |
| `infrastructure/terraform.md` | Terraform patterns — remote state with locking, modules, workspaces vs directories, variable/output discipline, and safe plan/apply workflow | terraform, iac, infrastructure, state, modules |

