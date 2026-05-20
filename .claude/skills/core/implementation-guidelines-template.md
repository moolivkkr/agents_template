---
skill: implementation-guidelines-template
description: 24-section template for generating comprehensive IMPLEMENTATION_GUIDELINES.md — used by impl_guidelines_agent to produce the engineering contract for all downstream agents
version: "1.0"
tags:
  - template
  - implementation
  - guidelines
  - architecture
  - engineering-standards
---

# Implementation Guidelines Template

> **Purpose:** This template is the master blueprint for generating project-specific `docs/IMPLEMENTATION_GUIDELINES.md` files. The `impl_guidelines_agent` fills in every `{{PLACEHOLDER}}` with concrete, actionable decisions — no vague phrases, no "TBD" without an owner and due date.
>
> **Depth expectation:** Each section must contain enough detail that a new engineer can implement the pattern without asking follow-up questions. Include code snippets, configuration examples, and anti-patterns where applicable.
>
> **Reference:** See the cert-manager IMPLEMENTATION_GUIDELINES for the depth and specificity expected in a production-quality output.

---

## How to Use This Template

1. Read the entire template before starting
2. For each section, fill `{{PLACEHOLDER}}` markers with project-specific values
3. If a section is not applicable to the project (e.g., no multi-tenancy), mark it as `N/A — [reason]` and remove the sub-sections
4. Every decision must be concrete: "PostgreSQL 16" not "SQL database", "Gin v1.10" not "Go web framework"
5. When auto-deciding (--auto mode), log every decision to `agent_state/autonomous/decisions.md` with rationale
6. Cross-reference BRD requirements (FR-*, NFR-*, OBJ-*) in each section where relevant

---

## Template Output Structure

```markdown
# {{PROJECT_NAME}}: Implementation Guidelines

> **Version:** {{VERSION}}
> **Date:** {{DATE}}
> **Purpose:** Consolidated engineering reference for the {{PROJECT_NAME}} platform
> **Scope:** All technical architecture decisions from design documents
>
> **Deployment Target:** {{DEPLOYMENT_TARGET}}
> **Build Target:** {{BUILD_TARGET}}

---

## Table of Contents

0. [Coding Standards & Engineering Principles](#0-coding-standards--engineering-principles)
1. [Project Structure](#1-project-structure)
2. [API Design](#2-api-design)
3. [Database Design](#3-database-design)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Error Handling](#5-error-handling)
6. [Logging & Observability](#6-logging--observability)
7. [Testing Strategy](#7-testing-strategy)
8. [Security](#8-security)
9. [Performance](#9-performance)
10. [Configuration Management](#10-configuration-management)
11. [Deployment & CI/CD](#11-deployment--cicd)
12. [Documentation](#12-documentation)
13. [Git Workflow](#13-git-workflow)
14. [Dependency Management](#14-dependency-management)
15. [Multi-Tenancy](#15-multi-tenancy)
16. [Background Jobs & Async Processing](#16-background-jobs--async-processing)
17. [File Storage](#17-file-storage)
18. [Email & Notifications](#18-email--notifications)
19. [Search](#19-search)
20. [Data Import/Export](#20-data-importexport)
21. [Internationalization](#21-internationalization)
22. [Accessibility](#22-accessibility)
23. [Monitoring & Alerting](#23-monitoring--alerting)

---
```

---

## Section 0: Coding Standards & Engineering Principles

> **Agent guidance:** This section is NON-NEGOTIABLE. Load `code-quality.md` and `software-architecture.md` skill packs. Every sub-section must have concrete rules with code examples showing correct and incorrect patterns.

```markdown
## 0. Coding Standards & Engineering Principles

> **This section is NON-NEGOTIABLE. Every developer, every agent, every code review MUST enforce these standards. No exceptions. No shortcuts.**

### 0.1 Performance-First Design

Performance is not an afterthought — it is a design constraint applied to every decision.

**Mandatory performance practices:**

- Time complexity: {{MAX_ACCEPTABLE_COMPLEXITY}} is unacceptable for any user-facing path
- Memory allocation: minimize heap allocations in hot paths
- Database queries: N+1 queries are a blocking code review defect
- Network round-trips: batch external calls, never call in a loop
- Concurrency: use {{CONCURRENCY_MODEL}} for parallel I/O operations

**Performance budgets (hard limits, enforced by CI):**

| Operation | P50 | P95 | P99 | Absolute Max |
|-----------|-----|-----|-----|--------------|
| REST API read | {{P50_READ}} | {{P95_READ}} | {{P99_READ}} | {{MAX_READ}} |
| REST API write | {{P50_WRITE}} | {{P95_WRITE}} | {{P99_WRITE}} | {{MAX_WRITE}} |
| Database query (indexed) | {{P50_DB_INDEXED}} | {{P95_DB_INDEXED}} | {{P99_DB_INDEXED}} | {{MAX_DB_INDEXED}} |
| Database query (aggregation) | {{P50_DB_AGG}} | {{P95_DB_AGG}} | {{P99_DB_AGG}} | {{MAX_DB_AGG}} |
| Background job | {{P50_JOB}} | {{P95_JOB}} | {{P99_JOB}} | {{MAX_JOB}} |

**Caching strategy:**

- L1: {{L1_CACHE}} (in-process, {{L1_TTL}})
- L2: {{L2_CACHE}} (distributed, {{L2_TTL}})
- L3: {{L3_CACHE}} (database)
- Invalidation: {{CACHE_INVALIDATION_STRATEGY}}

**Pagination (mandatory on ALL list endpoints):**

- Default page size: {{DEFAULT_PAGE_SIZE}}
- Max page size: {{MAX_PAGE_SIZE}}
- Strategy: {{PAGINATION_STRATEGY}} (offset-based for small sets, cursor-based for 10K+ result sets)
- Response envelope MUST include: items, total, limit, offset/cursor, has_more

**Connection pooling:**

- {{DB_POOL_LIBRARY}} with max {{DB_MAX_CONNS}} connections per instance
- Min idle connections: {{DB_MIN_CONNS}}
- Max connection lifetime: {{DB_MAX_CONN_LIFETIME}}
- Health check interval: {{DB_HEALTH_CHECK_INTERVAL}}

### 0.2 Interface-Based Development

**Every external dependency, every service layer, every data access layer MUST be defined by an interface.**

- Program to interfaces, not implementations
- Accept interfaces, return structs
- Keep interfaces small ({{MAX_INTERFACE_METHODS}} methods max). Split if larger.
- Interface lives in the CONSUMER package, not the provider

**Dependency injection via constructors — no global state:**

- Every dependency explicit in constructor
- No init() side effects or package-level mutable vars (except constants)
- No service locator pattern or global registries
- Constructor pattern: `New*(deps...) *Type`

### 0.3 Small Functions — Unit-Testable

- Maximum function length: {{MAX_FUNCTION_LINES}} lines of logic (excluding comments, blank lines, struct definitions)
- Max {{MAX_PARAMS}} parameters per function. Use option struct if more needed.
- Max {{MAX_RETURN_VALUES}} return values (result, error). Use named struct for more.
- Max {{MAX_NESTING_DEPTH}} levels of nesting. Extract to helper if deeper.
- Early return on error — no deep nesting

### 0.4 Object-Oriented Design — Mandatory Patterns

| Pattern | Where Applied | Purpose |
|---------|---------------|---------|
| **Repository** | ALL data access | Abstract DB behind interface; swap for testing |
| **Service Layer** | ALL business logic | Orchestrate repos, enforce rules, coordinate transactions |
| **Strategy** | {{STRATEGY_USAGE}} | Swap implementations at runtime |
| **Factory** | {{FACTORY_USAGE}} | Encapsulate complex object creation |
| **Observer** | {{OBSERVER_USAGE}} | Decouple side effects from core operations |
| **Circuit Breaker** | ALL external calls | Prevent cascade failure |
| **Decorator** | {{DECORATOR_USAGE}} | Add cross-cutting concerns without modifying core |
| **Builder** | {{BUILDER_USAGE}} | Construct complex objects step-by-step |

**SOLID principles — enforced at code review:**

- S — Single Responsibility: Each struct/package owns ONE concern
- O — Open/Closed: New variants added by implementing interface, not modifying existing code
- L — Liskov Substitution: Mock implementations behave identically to real ones in tests
- I — Interface Segregation: Separate reader/writer interfaces; no god interfaces
- D — Dependency Inversion: Depend on interfaces, wire in main.go / DI container

### 0.5 Naming Conventions

- **Files:** {{FILE_NAMING_CONVENTION}} (e.g., snake_case.go, kebab-case.ts)
- **Types/Structs/Classes:** {{TYPE_NAMING_CONVENTION}} (e.g., PascalCase)
- **Functions/Methods:** {{FUNCTION_NAMING_CONVENTION}} (e.g., PascalCase for exported, camelCase for private)
- **Variables:** {{VARIABLE_NAMING_CONVENTION}}
- **Constants:** {{CONSTANT_NAMING_CONVENTION}}
- **Database tables:** {{DB_TABLE_NAMING}} (e.g., snake_case, plural)
- **Database columns:** {{DB_COLUMN_NAMING}} (e.g., snake_case)
- **API endpoints:** {{API_ENDPOINT_NAMING}} (e.g., kebab-case, plural nouns)
- **Environment variables:** {{ENV_VAR_NAMING}} (e.g., SCREAMING_SNAKE_CASE)

### 0.6 Code Organization Rules

- One concept per file — do not combine unrelated structs/classes
- Group by domain, not by technical layer (prefer `users/service.go` over `services/user_service.go`)
- Keep package/module APIs small — export only what consumers need
- Internal implementation details should be unexported/private
```

---

## Section 1: Project Structure

> **Agent guidance:** Define the exact directory layout. Every directory must have a purpose. Ask the user what build system and monorepo/polyrepo strategy they prefer. Reference `software-architecture.md` for layer boundary rules.

```markdown
## 1. Project Structure

### 1.1 Directory Layout

{{PROJECT_STRUCTURE_TREE}}

### 1.2 Package/Module Boundaries

| Package/Module | Responsibility | May Import | Must NOT Import |
|----------------|---------------|------------|-----------------|
| {{PACKAGE_1}} | {{RESPONSIBILITY_1}} | {{ALLOWED_IMPORTS_1}} | {{FORBIDDEN_IMPORTS_1}} |
| {{PACKAGE_2}} | {{RESPONSIBILITY_2}} | {{ALLOWED_IMPORTS_2}} | {{FORBIDDEN_IMPORTS_2}} |

### 1.3 Layer Architecture

{{LAYER_DIAGRAM}}

**Dependency direction:** {{DEPENDENCY_RULE}} (e.g., domain <- service <- handler; never reversed)

**Layer responsibilities:**

| Layer | Owns | Does NOT Own |
|-------|------|-------------|
| Handler/Controller | Request parsing, validation, response serialization | Business logic, direct DB access |
| Service | Business rules, orchestration, transactions | HTTP concerns, SQL queries |
| Repository | Data access, query construction | Business rules, HTTP concerns |
| Domain | Entities, value objects, domain errors | Infrastructure, frameworks |

### 1.4 Shared Code

- Shared utilities: `{{SHARED_UTILS_PATH}}`
- Shared types/DTOs: `{{SHARED_TYPES_PATH}}`
- Rule: shared code must be stateless and have zero external dependencies
```

---

## Section 2: API Design

> **Agent guidance:** Load `api-excellence.md` skill pack. Define REST conventions, versioning, error responses, and authentication. Ask about GraphQL/gRPC if the BRD mentions real-time or inter-service communication.

```markdown
## 2. API Design

### 2.1 API Style & Versioning

- **Style:** {{API_STYLE}} (REST / GraphQL / gRPC / hybrid)
- **Versioning:** {{API_VERSIONING}} (e.g., URL path: /api/v1/)
- **Breaking change policy:** {{BREAKING_CHANGE_POLICY}}

### 2.2 URL Structure

| Method | Pattern | Description |
|--------|---------|-------------|
| GET | `/api/v1/{{RESOURCE}}` | List with pagination |
| GET | `/api/v1/{{RESOURCE}}/{id}` | Get single resource |
| POST | `/api/v1/{{RESOURCE}}` | Create resource |
| PUT | `/api/v1/{{RESOURCE}}/{id}` | Full update |
| PATCH | `/api/v1/{{RESOURCE}}/{id}` | Partial update |
| DELETE | `/api/v1/{{RESOURCE}}/{id}` | Soft/hard delete |

### 2.3 Request/Response Conventions

**Success response envelope:**

```json
{
  "data": { ... },
  "meta": {
    "request_id": "{{REQUEST_ID_FORMAT}}",
    "timestamp": "ISO-8601"
  }
}
```

**List response envelope:**

```json
{
  "data": [ ... ],
  "pagination": {
    "total": 100,
    "limit": {{DEFAULT_PAGE_SIZE}},
    "offset": 0,
    "has_more": true
  },
  "meta": { ... }
}
```

**Error response envelope:**

```json
{
  "error": {
    "code": "{{ERROR_CODE_FORMAT}}",
    "message": "Human-readable message",
    "detail": "Technical detail for debugging",
    "retryable": false,
    "request_id": "uuid"
  }
}
```

### 2.4 HTTP Status Codes

| Status | When Used |
|--------|-----------|
| 200 | Successful read or update |
| 201 | Resource created |
| 204 | Successful delete (no body) |
| 400 | Validation error, malformed request |
| 401 | Missing or invalid authentication |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 409 | Conflict (duplicate, state violation) |
| 422 | Semantically invalid (well-formed but logically wrong) |
| 429 | Rate limited |
| 500 | Internal server error |
| 502 | Upstream dependency failure |
| 503 | Service temporarily unavailable |

### 2.5 Rate Limiting

- Strategy: {{RATE_LIMIT_STRATEGY}}
- Default limits: {{RATE_LIMIT_DEFAULTS}}
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 2.6 Idempotency

- Idempotency key header: `{{IDEMPOTENCY_HEADER}}` (e.g., `Idempotency-Key`)
- Required on: {{IDEMPOTENT_OPERATIONS}} (e.g., POST, PATCH)
- TTL: {{IDEMPOTENCY_TTL}}

### 2.7 Content Negotiation

- Default: `application/json`
- Supported: {{SUPPORTED_CONTENT_TYPES}}
- File uploads: `multipart/form-data`
```

---

## Section 3: Database Design

> **Agent guidance:** Ask about data model complexity, expected data volumes, multi-tenancy needs. Reference the BRD for data entities. Determine migration strategy based on the chosen ORM/query layer.

```markdown
## 3. Database Design

### 3.1 Technology

- **Engine:** {{DB_ENGINE}} (e.g., PostgreSQL 16)
- **ORM / Query Layer:** {{ORM_OR_QUERY_LAYER}} (e.g., GORM, SQLAlchemy, Drizzle, raw SQL with pgx)
- **Migration Tool:** {{MIGRATION_TOOL}} (e.g., golang-migrate, Alembic, Flyway, Drizzle Kit)
- **Connection Library:** {{DB_CONNECTION_LIB}} (e.g., pgxpool, asyncpg, Prisma)

### 3.2 Naming Conventions

- Tables: {{DB_TABLE_NAMING_DETAIL}} (e.g., plural snake_case: `users`, `order_items`)
- Columns: {{DB_COLUMN_NAMING_DETAIL}} (e.g., snake_case: `created_at`, `tenant_id`)
- Primary keys: {{PK_CONVENTION}} (e.g., `id UUID DEFAULT gen_random_uuid()`)
- Foreign keys: {{FK_CONVENTION}} (e.g., `{referenced_table_singular}_id`)
- Indexes: {{INDEX_NAMING}} (e.g., `idx_{table}_{columns}`)
- Constraints: {{CONSTRAINT_NAMING}} (e.g., `uq_{table}_{columns}`, `ck_{table}_{rule}`)

### 3.3 Standard Columns (ALL tables)

| Column | Type | Purpose |
|--------|------|---------|
| `id` | {{PK_TYPE}} | Primary key |
| `tenant_id` | {{TENANT_ID_TYPE}} | Tenant isolation (if multi-tenant) |
| `created_at` | `TIMESTAMPTZ` | Row creation time (DEFAULT NOW()) |
| `updated_at` | `TIMESTAMPTZ` | Last modification (trigger-updated) |
| `created_by` | {{USER_ID_TYPE}} | Audit: who created |
| `updated_by` | {{USER_ID_TYPE}} | Audit: who last modified |
| `deleted_at` | `TIMESTAMPTZ NULL` | Soft delete (if applicable) |

### 3.4 Migration Strategy

- **Direction:** Forward-only (no down migrations in production) / Reversible
- **Naming:** `{{MIGRATION_NAMING}}` (e.g., `YYYYMMDDHHMMSS_description.sql`)
- **Review process:** {{MIGRATION_REVIEW_PROCESS}}
- **Zero-downtime:** {{ZERO_DOWNTIME_MIGRATION_STRATEGY}}
- **Data migrations:** Separate from schema migrations; run as background jobs
- **Rollback strategy:** {{MIGRATION_ROLLBACK_STRATEGY}}

### 3.5 Indexing Strategy

- **Every foreign key** gets an index
- **Every column used in WHERE** clauses gets an index
- **Composite indexes** for multi-column queries (most-selective column first)
- **Partial indexes** for filtered queries (e.g., `WHERE deleted_at IS NULL`)
- **GIN indexes** for JSONB columns and full-text search
- **Monitor:** {{SLOW_QUERY_THRESHOLD}} threshold for slow query logging

### 3.6 Query Patterns

- **No N+1 queries:** Use JOINs or batch loading (DataLoader pattern)
- **Prepared statements:** {{PREPARED_STATEMENT_POLICY}}
- **Read replicas:** {{READ_REPLICA_STRATEGY}}
- **Query timeout:** {{QUERY_TIMEOUT}} per query
```

---

## Section 4: Authentication & Authorization

> **Agent guidance:** Determine auth strategy from BRD (JWT, session-based, OAuth). Ask about RBAC vs ABAC, API key support, and service-to-service auth. Reference `resiliency-patterns.md` for token refresh patterns.

```markdown
## 4. Authentication & Authorization

### 4.1 Authentication Strategy

- **Primary method:** {{AUTH_METHOD}} (e.g., JWT Bearer tokens)
- **Token format:** {{TOKEN_FORMAT}} (e.g., JWT with RS256 signing)
- **Token lifetime:** Access: {{ACCESS_TOKEN_TTL}}, Refresh: {{REFRESH_TOKEN_TTL}}
- **Token storage (client):** {{TOKEN_STORAGE}} (e.g., httpOnly cookie, secure localStorage)
- **Provider:** {{AUTH_PROVIDER}} (e.g., self-hosted, Auth0, Clerk, Firebase Auth)

### 4.2 Authorization Model

- **Model:** {{AUTHZ_MODEL}} (e.g., RBAC, ABAC, ReBAC)
- **Default roles:** {{DEFAULT_ROLES}} (e.g., admin, member, viewer)
- **Permission format:** {{PERMISSION_FORMAT}} (e.g., `resource:action` — `certificates:create`)

**Permission matrix:**

| Role | {{RESOURCE_1}} | {{RESOURCE_2}} | {{RESOURCE_3}} |
|------|------|------|------|
| Admin | CRUD | CRUD | CRUD |
| Member | CR | CR | R |
| Viewer | R | R | R |

### 4.3 Middleware Chain

```
Request → Rate Limiter → Auth (JWT/session) → RBAC → Tenant Scoping → Handler
```

### 4.4 API Key Authentication

- **Format:** {{API_KEY_FORMAT}} (e.g., `sk_live_xxxx`, prefixed for identification)
- **Storage:** {{API_KEY_STORAGE}} (e.g., bcrypt hash in DB, never stored plaintext)
- **Scoping:** {{API_KEY_SCOPING}} (per-tenant, per-user, per-application)
- **Rotation:** {{API_KEY_ROTATION_POLICY}}

### 4.5 Session Management

- **Session store:** {{SESSION_STORE}} (e.g., Redis with TTL, DB-backed)
- **Session invalidation:** {{SESSION_INVALIDATION}} (e.g., on password change, on role change)
- **Concurrent sessions:** {{CONCURRENT_SESSIONS_POLICY}} (e.g., max 5 per user)

### 4.6 Service-to-Service Authentication

- **Method:** {{S2S_AUTH_METHOD}} (e.g., mTLS, shared JWT, API keys)
- **Secret management:** {{S2S_SECRET_MANAGEMENT}}
```

---

## Section 5: Error Handling

> **Agent guidance:** Load `code-quality.md` for error handling patterns. Define domain error types that map to HTTP status codes. Every error must be structured, logged, and user-friendly.

```markdown
## 5. Error Handling

### 5.1 Error Taxonomy

| Error Category | HTTP Status | Retryable | Example |
|---------------|-------------|-----------|---------|
| Validation | 400 | No | Missing required field |
| Authentication | 401 | No | Expired token |
| Authorization | 403 | No | Insufficient permissions |
| Not Found | 404 | No | Resource does not exist |
| Conflict | 409 | No | Duplicate entry |
| Rate Limited | 429 | Yes | Too many requests |
| Internal | 500 | No | Unexpected server error |
| Upstream | 502 | Yes | External service failure |
| Unavailable | 503 | Yes | Service temporarily down |

### 5.2 Domain Error Type

```{{LANG}}
{{DOMAIN_ERROR_STRUCT}}
```

**Error code constants:**

```{{LANG}}
{{ERROR_CODE_CONSTANTS}}
```

### 5.3 Error Handling Rules

- **Wrap errors at boundaries:** Add context when crossing layer boundaries (handler->service->repo)
- **Never swallow errors:** Every error must be handled or propagated with wrapping
- **Use domain errors:** Never return raw/generic errors from the service layer
- **Log at the boundary:** Log the full error with stack trace at the handler level; do not log at every layer
- **User-facing messages:** Domain errors carry user-safe messages; internal details go to logs only
- **Panic recovery:** {{PANIC_RECOVERY_STRATEGY}} (e.g., global middleware that recovers, logs, returns 500)

### 5.4 Error Wrapping Pattern

```{{LANG}}
{{ERROR_WRAPPING_EXAMPLE}}
```
```

---

## Section 6: Logging & Observability

> **Agent guidance:** Load `observability-patterns.md` skill pack. Define structured logging format, log levels, metrics, and tracing. tenant_id must appear on every log line and metric in multi-tenant systems.

```markdown
## 6. Logging & Observability

### 6.1 Structured Logging

- **Library:** {{LOG_LIBRARY}} (e.g., slog, zerolog, winston, structlog)
- **Format:** {{LOG_FORMAT}} (e.g., JSON in production, human-readable in dev)
- **Output:** {{LOG_OUTPUT}} (e.g., stdout → collected by {{LOG_COLLECTOR}})

**Mandatory log fields on EVERY log line:**

| Field | Source | Purpose |
|-------|--------|---------|
| `timestamp` | Auto | ISO-8601 timestamp |
| `level` | Logger | Log level (debug/info/warn/error) |
| `message` | Developer | What happened |
| `tenant_id` | Context | Tenant isolation (if multi-tenant) |
| `trace_id` | Context | Distributed tracing correlation |
| `request_id` | Context | Request correlation |
| `service` | Config | Service name |
| `component` | Developer | Which component (e.g., "certificate.service") |

### 6.2 Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Development-only detail | "SQL query: SELECT ..." |
| `INFO` | Business events, state changes | "User created", "Order placed" |
| `WARN` | Recoverable issues, degraded state | "Cache miss, falling back to DB" |
| `ERROR` | Failures requiring attention | "Failed to connect to DB" |
| `FATAL` | Unrecoverable, process must exit | "Cannot bind to port" |

**Rules:**
- Never log sensitive data (passwords, tokens, PII, credit cards)
- Never log at ERROR for expected business conditions (e.g., 404 is INFO, not ERROR)
- Every ERROR log should have enough context to diagnose without access to the machine

### 6.3 Metrics

- **Library:** {{METRICS_LIBRARY}} (e.g., OpenTelemetry, Prometheus client, StatsD)
- **Export:** {{METRICS_EXPORT}} (e.g., Prometheus scrape endpoint at /metrics)
- **Dashboard:** {{METRICS_DASHBOARD}} (e.g., Grafana)

**Mandatory metrics:**

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http_request_duration_seconds` | Histogram | method, path, status, tenant_id | API latency |
| `http_request_total` | Counter | method, path, status, tenant_id | Request volume |
| `db_query_duration_seconds` | Histogram | operation, table, tenant_id | Query latency |
| `external_call_duration_seconds` | Histogram | service, operation, result | Dependency latency |
| `active_connections` | Gauge | pool_name | Connection pool health |
| `error_total` | Counter | type, component, tenant_id | Error rate |

### 6.4 Distributed Tracing

- **Library:** {{TRACING_LIBRARY}} (e.g., OpenTelemetry SDK)
- **Exporter:** {{TRACING_EXPORTER}} (e.g., OTLP → Jaeger, Tempo)
- **Sampling:** {{TRACING_SAMPLING}} (e.g., 100% in dev, 10% in prod, always-on for errors)

**Mandatory spans:**
- Every HTTP request (auto-instrumented via middleware)
- Every database query
- Every external service call
- Every message queue publish/consume
- Every cache operation (hit/miss)

### 6.5 Request-Scoped Logger

```{{LANG}}
{{REQUEST_LOGGER_MIDDLEWARE}}
```
```

---

## Section 7: Testing Strategy

> **Agent guidance:** Load `testing-principles.md` skill pack. Define framework choices, coverage targets, test data management. Ask about CI integration and test parallelism.

```markdown
## 7. Testing Strategy

### 7.1 Test Pyramid

| Level | Framework | Scope | Coverage Target | Run When |
|-------|-----------|-------|----------------|----------|
| Unit | {{UNIT_FRAMEWORK}} | Single function/method | {{UNIT_COVERAGE}}% | Every commit |
| Integration | {{INTEGRATION_FRAMEWORK}} | Service + DB/cache | {{INTEGRATION_COVERAGE}}% | Every PR |
| E2E | {{E2E_FRAMEWORK}} | Full API flow | {{E2E_COVERAGE}} critical paths | Pre-release |
| Performance | {{PERF_FRAMEWORK}} | Load testing | {{PERF_TARGETS}} | Weekly / pre-release |

### 7.2 Test Naming Convention

```
{{TEST_NAMING_PATTERN}}
```

Example: `Test{{Function}}_{{Scenario}}_{{ExpectedResult}}`

### 7.3 Test Data Management

- **Fixtures:** {{TEST_FIXTURE_STRATEGY}} (e.g., factory functions, not JSON files)
- **Database:** {{TEST_DB_STRATEGY}} (e.g., testcontainers per suite, transaction rollback per test)
- **Cleanup:** {{TEST_CLEANUP_STRATEGY}} (e.g., defer cleanup in setup, truncate between tests)
- **Mocking:** {{MOCK_STRATEGY}} (e.g., interface mocks via {{MOCK_LIBRARY}}, never mock what you don't own)

### 7.4 Test Structure

```{{LANG}}
{{TEST_STRUCTURE_EXAMPLE}}
```

### 7.5 What NOT to Test

- Framework internals (trust the framework)
- Third-party library behavior
- Trivial getters/setters with no logic
- Generated code (protobuf, OpenAPI clients)

### 7.6 CI Integration

- Tests run in: {{TEST_CI_ENVIRONMENT}} (e.g., GitHub Actions, Docker Compose)
- Parallelism: {{TEST_PARALLELISM}} (e.g., Go: -parallel=4, Jest: --maxWorkers=50%)
- Timeout: {{TEST_TIMEOUT}} per test suite
- Flaky test policy: {{FLAKY_TEST_POLICY}} (e.g., quarantine after 2 failures, fix within 48h)
```

---

## Section 8: Security

> **Agent guidance:** Load `security-owasp.md` skill pack. Cover OWASP Top 10 mitigations, input validation, output encoding, secrets management, and CORS. Reference NFR-SEC-* from BRD.

```markdown
## 8. Security

### 8.1 OWASP Top 10 Mitigations

| Vulnerability | Mitigation | Implementation |
|--------------|------------|----------------|
| Injection | {{INJECTION_MITIGATION}} | Parameterized queries, input validation |
| Broken Auth | {{BROKEN_AUTH_MITIGATION}} | JWT validation, secure session handling |
| Sensitive Data | {{SENSITIVE_DATA_MITIGATION}} | Encryption at rest/transit, no PII in logs |
| XXE | {{XXE_MITIGATION}} | Disable XML external entities |
| Broken Access | {{BROKEN_ACCESS_MITIGATION}} | RBAC middleware on every route |
| Misconfiguration | {{MISCONFIG_MITIGATION}} | Security headers, disable debug in prod |
| XSS | {{XSS_MITIGATION}} | Output encoding, CSP headers |
| Deserialization | {{DESER_MITIGATION}} | Schema validation, no arbitrary deserialization |
| Components | {{COMPONENTS_MITIGATION}} | Dependency scanning, automated updates |
| Logging | {{LOGGING_MITIGATION}} | Structured audit trail, tamper-proof |

### 8.2 Input Validation

- **Strategy:** {{INPUT_VALIDATION_STRATEGY}} (e.g., validate at handler boundary, reject early)
- **Library:** {{VALIDATION_LIBRARY}} (e.g., go-validator, zod, joi, pydantic)
- **Rules:**
  - Validate all user input before processing
  - Whitelist allowed characters, don't blacklist
  - Enforce max lengths on all string fields
  - Validate enum values against allowed set
  - Sanitize HTML if rich text is accepted

### 8.3 Output Encoding

- HTML: {{HTML_ENCODING}} (e.g., auto-escaped in templates)
- JSON: {{JSON_ENCODING}} (e.g., standard JSON encoder — no HTML in JSON)
- SQL: Parameterized queries only — NEVER string concatenation

### 8.4 Secrets Management

- **Development:** {{DEV_SECRETS}} (e.g., .env files, git-ignored)
- **Production:** {{PROD_SECRETS}} (e.g., AWS Secrets Manager, Vault, K8s secrets)
- **Rotation:** {{SECRET_ROTATION_POLICY}}
- **Never:** hardcode secrets, commit .env files, log secrets

### 8.5 CORS Configuration

```{{LANG}}
{{CORS_CONFIG}}
```

### 8.6 Security Headers

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Content-Security-Policy` | `{{CSP_POLICY}}` |
| `X-XSS-Protection` | `0` (rely on CSP instead) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
```

---

## Section 9: Performance

> **Agent guidance:** Load `resiliency-patterns.md` for circuit breakers, retries, timeouts. Define caching layers, connection pooling, query optimization rules, and lazy loading strategies.

```markdown
## 9. Performance

### 9.1 Caching Strategy

| Data Type | L1 (In-Process) | L2 (Distributed) | TTL | Invalidation |
|-----------|-----------------|-------------------|-----|--------------|
| {{CACHE_DATA_1}} | {{L1_1}} | {{L2_1}} | {{TTL_1}} | {{INVALIDATION_1}} |
| {{CACHE_DATA_2}} | {{L1_2}} | {{L2_2}} | {{TTL_2}} | {{INVALIDATION_2}} |
| Session data | No | {{SESSION_CACHE}} | {{SESSION_TTL}} | On logout/change |

### 9.2 Connection Pooling

- Database: {{DB_POOL_CONFIG}}
- Redis: {{REDIS_POOL_CONFIG}}
- HTTP clients: {{HTTP_POOL_CONFIG}}

### 9.3 Query Optimization

- **EXPLAIN ANALYZE** on every new query before merge
- **Index usage** verified — no sequential scans on tables > 10K rows
- **N+1 detection:** {{N_PLUS_ONE_DETECTION}} (e.g., middleware logging query count per request)
- **Slow query log:** queries > {{SLOW_QUERY_MS}}ms are logged at WARN level

### 9.4 Lazy Loading (Frontend)

- Route-level code splitting: {{CODE_SPLITTING_STRATEGY}}
- Virtual scrolling for lists > {{VIRTUAL_SCROLL_THRESHOLD}} items
- Image lazy loading with intersection observer
- API data caching: {{CLIENT_CACHE_STRATEGY}}

### 9.5 Circuit Breakers

- **Library:** {{CIRCUIT_BREAKER_LIB}}
- **Configuration:** Max {{CB_MAX_FAILURES}} consecutive failures → open, {{CB_RESET_TIMEOUT}} reset timeout
- **Applied to:** ALL external service calls
- **Metrics:** Circuit state changes logged + gauged

### 9.6 Timeouts & Retries

| Operation | Timeout | Max Retries | Backoff |
|-----------|---------|-------------|---------|
| DB query | {{DB_TIMEOUT}} | 0 | N/A |
| External API | {{EXTERNAL_TIMEOUT}} | {{EXTERNAL_RETRIES}} | {{EXTERNAL_BACKOFF}} |
| Cache read | {{CACHE_TIMEOUT}} | 0 | N/A |
| File upload | {{UPLOAD_TIMEOUT}} | 1 | Fixed |
```

---

## Section 10: Configuration Management

> **Agent guidance:** Define how configuration is loaded, validated, and overridden across environments. Ask about feature flags and secrets separation.

```markdown
## 10. Configuration Management

### 10.1 Configuration Sources (precedence order)

1. {{CONFIG_SOURCE_1}} (highest priority — e.g., environment variables)
2. {{CONFIG_SOURCE_2}} (e.g., config file — config.yaml)
3. {{CONFIG_SOURCE_3}} (e.g., defaults in code)

### 10.2 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `{{APP_PREFIX}}_PORT` | No | {{DEFAULT_PORT}} | HTTP server port |
| `{{APP_PREFIX}}_DB_URL` | Yes | — | Database connection string |
| `{{APP_PREFIX}}_LOG_LEVEL` | No | `info` | Log level |
| `{{APP_PREFIX}}_ENV` | Yes | — | Environment (dev/staging/prod) |

### 10.3 Configuration Validation

- All required config validated at startup — fail fast if missing
- Type-safe config struct — no raw string lookups at runtime
- Config changes require restart (no hot reload unless explicitly designed)

### 10.4 Feature Flags

- **System:** {{FEATURE_FLAG_SYSTEM}} (e.g., environment variables, LaunchDarkly, database-backed)
- **Naming:** {{FEATURE_FLAG_NAMING}} (e.g., `FF_ENABLE_NEW_BILLING`)
- **Cleanup:** Remove flags within {{FEATURE_FLAG_CLEANUP_WINDOW}} of full rollout

### 10.5 Environment-Specific Configuration

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| Log level | debug | info | info |
| Debug endpoints | enabled | enabled | disabled |
| CORS origins | localhost | staging domain | production domain |
| Rate limits | disabled | relaxed | enforced |
| Seed data | auto-seeded | test data | empty |
```

---

## Section 11: Deployment & CI/CD

> **Agent guidance:** Define Docker configuration, CI/CD pipeline stages, environment promotion, rollback strategy, and health checks. Reference the BRD deployment requirements.

```markdown
## 11. Deployment & CI/CD

### 11.1 Docker

- **Base image:** {{DOCKER_BASE_IMAGE}} (e.g., golang:1.22-alpine, node:20-slim)
- **Multi-stage builds:** Yes — build stage + minimal runtime stage
- **Image naming:** {{DOCKER_IMAGE_NAMING}} (e.g., `{{PROJECT}}-api:{{VERSION}}`)
- **Health check:** `HEALTHCHECK CMD {{HEALTH_CHECK_CMD}}`

### 11.2 Docker Compose (Local Development)

```yaml
{{DOCKER_COMPOSE_EXAMPLE}}
```

### 11.3 CI/CD Pipeline

- **Platform:** {{CI_PLATFORM}} (e.g., GitHub Actions)
- **Trigger:** {{CI_TRIGGER}} (e.g., push to main, PR opened)

**Pipeline stages:**

```
{{CI_PIPELINE_STAGES}}
```

### 11.4 Environment Promotion

```
{{PROMOTION_FLOW}}
```

### 11.5 Rollback Strategy

- **Method:** {{ROLLBACK_METHOD}} (e.g., deploy previous image tag, blue-green switch)
- **Time to rollback:** < {{ROLLBACK_TIME}}
- **Data rollback:** {{DATA_ROLLBACK_STRATEGY}} (e.g., forward-fix preferred, backward-compatible migrations only)

### 11.6 Health Checks

| Endpoint | Check | Expected |
|----------|-------|----------|
| `{{HEALTH_ENDPOINT}}` | Liveness | 200 OK |
| `{{READY_ENDPOINT}}` | DB + cache connectivity | 200 OK with dependency status |
```

---

## Section 12: Documentation

> **Agent guidance:** Define API documentation strategy (OpenAPI), code comment standards, ADR format, and runbook requirements.

```markdown
## 12. Documentation

### 12.1 API Documentation

- **Format:** {{API_DOC_FORMAT}} (e.g., OpenAPI 3.1 / Swagger)
- **Generation:** {{API_DOC_GENERATION}} (e.g., auto-generated from code annotations, manual spec-first)
- **Hosting:** {{API_DOC_HOSTING}} (e.g., Swagger UI at /docs, Redoc)
- **Versioning:** API docs versioned alongside code

### 12.2 Code Comments

- **Public APIs:** Every exported function/method has a doc comment explaining what, not how
- **Complex logic:** Inline comments for non-obvious algorithms
- **No noise:** No comments that repeat the code (`// increment counter` on `counter++`)
- **TODO format:** `// TODO({{AUTHOR}}): {{DESCRIPTION}} — {{TICKET_ID}}`

### 12.3 Architecture Decision Records (ADRs)

- **Location:** `docs/adr/`
- **Format:** `NNNN-title.md`
- **Template:**

```markdown
# ADR-NNNN: {{TITLE}}

## Status: {{Proposed | Accepted | Deprecated | Superseded}}

## Context
{{Why this decision is needed}}

## Decision
{{What we decided}}

## Consequences
{{What happens as a result — positive and negative}}
```

### 12.4 Runbooks

- Location: `docs/runbooks/`
- Required for: every production alert, deployment procedure, incident type
- Format: step-by-step with commands, expected outputs, escalation paths
```

---

## Section 13: Git Workflow

> **Agent guidance:** Load `git-workflow.md` skill pack. Define branching strategy, commit conventions, PR process, and code review rules.

```markdown
## 13. Git Workflow

### 13.1 Branching Strategy

- **Strategy:** {{GIT_STRATEGY}} (e.g., trunk-based, gitflow, GitHub Flow)
- **Main branch:** `{{MAIN_BRANCH}}` — always deployable
- **Feature branches:** `{{FEATURE_BRANCH_FORMAT}}` (e.g., `feat/{{TICKET_ID}}-short-description`)
- **Release branches:** {{RELEASE_BRANCH_POLICY}}
- **Hotfix branches:** `hotfix/{{TICKET_ID}}-description`

### 13.2 Commit Convention

- **Format:** {{COMMIT_FORMAT}} (e.g., Conventional Commits)

```
{{COMMIT_TEMPLATE}}
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

### 13.3 Pull Request Process

1. {{PR_STEP_1}} (e.g., Create PR with description template)
2. {{PR_STEP_2}} (e.g., CI passes — lint + test + build)
3. {{PR_STEP_3}} (e.g., Code review — minimum {{MIN_REVIEWERS}} approvals)
4. {{PR_STEP_4}} (e.g., Squash merge to main)

### 13.4 Code Review Standards

- Review within {{REVIEW_SLA}}
- Focus on: architecture, security, correctness, readability
- Not: style (automated by formatter/linter)
- Every PR < {{MAX_PR_SIZE}} lines changed (split large changes)

### 13.5 Protected Branch Rules

- `{{MAIN_BRANCH}}`: {{MAIN_BRANCH_RULES}} (e.g., require PR, require CI pass, require review)
- Force push: {{FORCE_PUSH_POLICY}} (e.g., never on main, allowed on feature branches)
```

---

## Section 14: Dependency Management

> **Agent guidance:** Define versioning strategy, security scanning, update cadence, and license compliance for third-party dependencies.

```markdown
## 14. Dependency Management

### 14.1 Versioning

- **Lock file:** {{LOCK_FILE}} (e.g., go.sum, package-lock.json, poetry.lock)
- **Version pinning:** {{VERSION_PINNING}} (e.g., exact versions in production, ranges in libraries)
- **Update cadence:** {{UPDATE_CADENCE}} (e.g., weekly automated PRs via Dependabot/Renovate)

### 14.2 Security Scanning

- **Tool:** {{SECURITY_SCAN_TOOL}} (e.g., Dependabot, Snyk, govulncheck, npm audit)
- **Frequency:** {{SCAN_FREQUENCY}} (e.g., daily, on every PR)
- **Policy:** {{VULN_POLICY}} (e.g., critical/high vulns block merge, medium reviewed within 7 days)

### 14.3 License Compliance

- **Allowed licenses:** {{ALLOWED_LICENSES}} (e.g., MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC)
- **Forbidden licenses:** {{FORBIDDEN_LICENSES}} (e.g., GPL, AGPL, SSPL)
- **Review process:** {{LICENSE_REVIEW_PROCESS}}

### 14.4 Internal Dependencies

- **Shared packages:** {{SHARED_PACKAGE_STRATEGY}} (e.g., monorepo internal packages, private registry)
- **Versioning:** {{INTERNAL_VERSION_STRATEGY}} (e.g., always use latest from main)
```

---

## Section 15: Multi-Tenancy

> **Agent guidance:** If the BRD mentions multiple organizations, workspaces, or teams, this section is required. Ask about isolation level, data partitioning strategy, and tenant-scoped operations. If single-tenant, mark as N/A.

```markdown
## 15. Multi-Tenancy

### 15.1 Isolation Model

- **Level:** {{ISOLATION_LEVEL}} (e.g., shared DB with RLS, schema-per-tenant, DB-per-tenant)
- **Tenant identifier:** {{TENANT_ID_SOURCE}} (e.g., JWT claim `org_id`, subdomain, header)
- **Tenant resolution:** {{TENANT_RESOLUTION}} (e.g., middleware extracts from JWT → context)

### 15.2 Data Partitioning

- **Strategy:** {{PARTITION_STRATEGY}} (e.g., tenant_id column on every table + RLS policy)
- **Enforcement:** {{PARTITION_ENFORCEMENT}} (e.g., PostgreSQL RLS, application-level WHERE clause, both)
- **Indexes:** All queries include tenant_id — composite indexes: `(tenant_id, id)`, `(tenant_id, created_at)`

### 15.3 Row-Level Security (if applicable)

```sql
{{RLS_POLICY_EXAMPLE}}
```

### 15.4 Tenant-Scoped Operations

- **Rule:** Every service method that accesses data MUST accept tenant_id
- **Rule:** Every repository query MUST include tenant_id in WHERE clause
- **Rule:** Cross-tenant data access is a VIOLATION — never return data from another tenant
- **Rule:** 404 (not 403) for resources belonging to other tenants — don't leak existence

### 15.5 Noisy Neighbor Protection

- Rate limiting: {{PER_TENANT_RATE_LIMIT}}
- Resource quotas: {{TENANT_QUOTAS}}
- Connection pool: {{TENANT_POOL_STRATEGY}}

### 15.6 Tenancy Model

- **Architecture:** {{TENANCY_MODEL}} (pooled | dedicated | hybrid)
- **Pooled tier:** {{POOLED_TIERS}} (e.g., Free, Starter, Pro)
- **Dedicated tier:** {{DEDICATED_TIERS}} (e.g., Enterprise, Premium)
- **Database isolation:** {{DB_ISOLATION}} (shared DB + RLS | schema-per-tenant | DB-per-tenant | hybrid routing)
- **Compute isolation:** {{COMPUTE_ISOLATION}} (shared pods | dedicated namespace | dedicated cluster)
- **Tenant ID extraction:** {{TENANT_EXTRACTION}} (JWT claims | API key | mTLS SAN | subdomain)
- **Encryption:** {{ENCRYPTION_MODEL}} (shared KEK | per-tenant KEK via Vault Transit | per-tenant AWS KMS)
- **Rate limiting:** Per-tenant with tier-based limits
- **Skill pack:** `.claude/skills/infrastructure/saas-tenancy-models.md`

### 15.7 Local AWS Simulation

- **Tool:** {{LOCAL_AWS_TOOL}} (LocalStack | moto | localstack-pro)
- **Services:** {{LOCAL_AWS_SERVICES}} (e.g., S3, KMS, SQS, Route53, IAM, SecretsManager)
- **Regions:** {{LOCAL_AWS_REGIONS}} (e.g., us-east-1, us-west-1, eu-west-1)
- **Init scripts:** `localstack/init/ready.d/` (auto-run on container start)
- **Multi-region simulation:** {{MULTI_REGION}} (geo-router nginx | single region)
- **Skill pack:** `.claude/skills/infrastructure/localstack-aws-local.md`
```

---

## Section 16: Background Jobs & Async Processing

> **Agent guidance:** Ask about job types (email sending, report generation, data processing). Determine queue technology and retry strategy. If no background processing needed, mark as N/A.

```markdown
## 16. Background Jobs & Async Processing

### 16.1 Queue Technology

- **System:** {{QUEUE_SYSTEM}} (e.g., Redis + worker, RabbitMQ, SQS, database-backed queue)
- **Library:** {{QUEUE_LIBRARY}} (e.g., Asynq, Celery, Bull, Sidekiq)

### 16.2 Job Types

| Job | Priority | Timeout | Max Retries | Dead Letter |
|-----|----------|---------|-------------|-------------|
| {{JOB_1}} | {{PRIORITY_1}} | {{TIMEOUT_1}} | {{RETRIES_1}} | {{DL_1}} |
| {{JOB_2}} | {{PRIORITY_2}} | {{TIMEOUT_2}} | {{RETRIES_2}} | {{DL_2}} |

### 16.3 Retry Strategy

- **Backoff:** {{RETRY_BACKOFF}} (e.g., exponential with jitter)
- **Max retries:** {{MAX_RETRIES}} (job-specific)
- **Dead letter queue:** {{DLQ_STRATEGY}} (e.g., after max retries → DLQ for manual review)
- **Idempotency:** Jobs MUST be idempotent — safe to retry without side effects

### 16.4 Scheduling

- **Cron jobs:** {{CRON_STRATEGY}} (e.g., in-app scheduler, Kubernetes CronJob, database-backed)
- **Job uniqueness:** {{JOB_UNIQUENESS}} (e.g., deduplicate by job type + payload hash)

### 16.5 Monitoring

- Queue depth metric: track and alert when queue exceeds {{QUEUE_DEPTH_THRESHOLD}}
- Job duration: histogram per job type
- Failure rate: counter per job type
- DLQ size: alert when > 0
```

---

## Section 17: File Storage

> **Agent guidance:** Ask about file types (user uploads, documents, images), storage backend, and CDN needs. If no file handling, mark as N/A.

```markdown
## 17. File Storage

### 17.1 Storage Backend

- **Primary:** {{STORAGE_BACKEND}} (e.g., S3, GCS, local filesystem, MinIO)
- **CDN:** {{CDN_PROVIDER}} (e.g., CloudFront, Cloudflare R2, none)
- **Local dev:** {{LOCAL_STORAGE}} (e.g., MinIO container, local ./uploads/)

### 17.2 Upload Handling

- **Max file size:** {{MAX_FILE_SIZE}}
- **Allowed types:** {{ALLOWED_FILE_TYPES}} (whitelist, not blacklist)
- **Validation:** {{FILE_VALIDATION}} (e.g., MIME type check, magic bytes, antivirus scan)
- **Naming:** {{FILE_NAMING}} (e.g., UUID-based to prevent collisions)
- **Upload method:** {{UPLOAD_METHOD}} (e.g., presigned URLs for direct-to-S3, server-side proxy)

### 17.3 Access Control

- **URL strategy:** {{FILE_URL_STRATEGY}} (e.g., signed URLs with TTL, public with CDN, API-proxied)
- **Tenant isolation:** Files stored under `{{TENANT_PATH_FORMAT}}` (e.g., `/{tenant_id}/{type}/{uuid}`)

### 17.4 Image Processing

- **Resize:** {{IMAGE_RESIZE_STRATEGY}} (e.g., on-upload thumbnails, on-demand via CDN transform)
- **Formats:** {{IMAGE_FORMATS}} (e.g., WebP preferred, JPEG/PNG fallback)
```

---

## Section 18: Email & Notifications

> **Agent guidance:** Ask about notification channels (email, in-app, push, SMS). Determine email provider and template strategy. If no notifications, mark as N/A.

```markdown
## 18. Email & Notifications

### 18.1 Email Provider

- **Provider:** {{EMAIL_PROVIDER}} (e.g., SendGrid, SES, Postmark, SMTP)
- **From address:** {{FROM_ADDRESS}} (e.g., noreply@{{DOMAIN}})
- **Template system:** {{EMAIL_TEMPLATE_SYSTEM}} (e.g., MJML, Handlebars, React Email)

### 18.2 Email Types

| Email | Trigger | Template | Priority |
|-------|---------|----------|----------|
| {{EMAIL_1}} | {{TRIGGER_1}} | {{TEMPLATE_1}} | {{PRIORITY_1}} |
| {{EMAIL_2}} | {{TRIGGER_2}} | {{TEMPLATE_2}} | {{PRIORITY_2}} |

### 18.3 Notification Channels

| Channel | Technology | Use Cases |
|---------|-----------|-----------|
| Email | {{EMAIL_TECH}} | {{EMAIL_USES}} |
| In-app | {{INAPP_TECH}} | {{INAPP_USES}} |
| Push | {{PUSH_TECH}} | {{PUSH_USES}} |
| SMS | {{SMS_TECH}} | {{SMS_USES}} |

### 18.4 Delivery Tracking

- **Webhooks:** {{DELIVERY_WEBHOOKS}} (e.g., SendGrid event webhooks)
- **Status tracking:** {{DELIVERY_TRACKING}} (e.g., sent → delivered → opened → clicked)
- **Retry:** Failed deliveries retried {{EMAIL_RETRY_COUNT}} times with {{EMAIL_RETRY_BACKOFF}} backoff
```

---

## Section 19: Search

> **Agent guidance:** Ask about search requirements (full-text, faceted, autocomplete). Determine if a dedicated search engine is needed or if database search is sufficient. If no search, mark as N/A.

```markdown
## 19. Search

### 19.1 Search Technology

- **Engine:** {{SEARCH_ENGINE}} (e.g., PostgreSQL full-text, Elasticsearch, Meilisearch, Typesense, Algolia)
- **Indexing strategy:** {{INDEX_STRATEGY}} (e.g., async indexing via worker, sync on write)
- **Index refresh:** {{INDEX_REFRESH}} (e.g., near-real-time, batch every N minutes)

### 19.2 Search Features

| Feature | Supported | Implementation |
|---------|-----------|----------------|
| Full-text search | {{FTS_SUPPORT}} | {{FTS_IMPL}} |
| Fuzzy matching | {{FUZZY_SUPPORT}} | {{FUZZY_IMPL}} |
| Faceted search | {{FACET_SUPPORT}} | {{FACET_IMPL}} |
| Autocomplete | {{AUTOCOMPLETE_SUPPORT}} | {{AUTOCOMPLETE_IMPL}} |
| Highlighting | {{HIGHLIGHT_SUPPORT}} | {{HIGHLIGHT_IMPL}} |
| Relevance tuning | {{RELEVANCE_SUPPORT}} | {{RELEVANCE_IMPL}} |

### 19.3 Searchable Entities

| Entity | Indexed Fields | Boost | Filters |
|--------|---------------|-------|---------|
| {{ENTITY_1}} | {{FIELDS_1}} | {{BOOST_1}} | {{FILTERS_1}} |
| {{ENTITY_2}} | {{FIELDS_2}} | {{BOOST_2}} | {{FILTERS_2}} |

### 19.4 Search API

- **Endpoint:** `GET /api/v1/search?q={{QUERY}}&type={{TYPE}}&filters={{FILTERS}}`
- **Pagination:** Cursor-based for large result sets
- **Tenant scoping:** All search results filtered by tenant_id
```

---

## Section 20: Data Import/Export

> **Agent guidance:** Ask about bulk data operations — CSV import, Excel export, data migration from legacy systems. Determine progress tracking and error handling for large operations. If no import/export, mark as N/A.

```markdown
## 20. Data Import/Export

### 20.1 Import

- **Supported formats:** {{IMPORT_FORMATS}} (e.g., CSV, Excel/XLSX, JSON)
- **Max file size:** {{IMPORT_MAX_SIZE}}
- **Processing:** {{IMPORT_PROCESSING}} (e.g., async via background job with progress tracking)
- **Validation:** Row-by-row validation with error report
- **Partial success:** {{PARTIAL_SUCCESS_POLICY}} (e.g., skip invalid rows, fail entire batch)
- **Duplicate handling:** {{DUPLICATE_HANDLING}} (e.g., skip, update, fail)

### 20.2 Export

- **Supported formats:** {{EXPORT_FORMATS}} (e.g., CSV, Excel/XLSX, PDF)
- **Max records:** {{EXPORT_MAX_RECORDS}} (e.g., 100K rows, paginated for larger)
- **Processing:** {{EXPORT_PROCESSING}} (e.g., async generation, download link via email)
- **Tenant scoping:** Exports ONLY include data for the requesting tenant

### 20.3 Progress Tracking

- **API:** `GET /api/v1/jobs/{job_id}` returns status, progress %, error details
- **WebSocket/SSE:** {{REALTIME_PROGRESS}} (e.g., SSE for progress updates)
- **Notifications:** Email on completion or failure

### 20.4 Bulk Operations

- **Batch size:** {{BATCH_SIZE}} records per transaction
- **Rate limiting:** {{BULK_RATE_LIMIT}} (e.g., 1 import per tenant at a time)
- **Cleanup:** Temporary files deleted after processing
```

---

## Section 21: Internationalization

> **Agent guidance:** Ask if the product needs multi-language support. If English-only, mark as N/A with a note about future-proofing. If i18n needed, define the framework and translation workflow.

```markdown
## 21. Internationalization (i18n)

### 21.1 Strategy

- **Required:** {{I18N_REQUIRED}} (Yes/No/Future)
- **Default locale:** {{DEFAULT_LOCALE}} (e.g., en-US)
- **Supported locales:** {{SUPPORTED_LOCALES}} (e.g., en-US, es-ES, fr-FR, de-DE, ja-JP)

### 21.2 Framework

- **Frontend:** {{FRONTEND_I18N}} (e.g., react-intl, next-intl, i18next)
- **Backend:** {{BACKEND_I18N}} (e.g., go-i18n, gettext, database-backed)
- **Translation format:** {{TRANSLATION_FORMAT}} (e.g., JSON key-value, ICU MessageFormat)

### 21.3 Translation Management

- **Storage:** {{TRANSLATION_STORAGE}} (e.g., JSON files in `/locales/`, translation management platform)
- **Workflow:** {{TRANSLATION_WORKFLOW}} (e.g., developer adds key → translator fills → PR review)
- **Fallback:** {{TRANSLATION_FALLBACK}} (e.g., fall back to en-US if key missing)

### 21.4 Implementation Rules

- Never hardcode user-facing strings — always use translation keys
- Date/time formatting: use locale-aware formatters (not manual formatting)
- Number formatting: respect locale decimal/thousand separators
- Currency: format with locale + currency code
- Pluralization: use ICU plural rules, not if/else
- RTL support: {{RTL_SUPPORT}} (Yes/No)
```

---

## Section 22: Accessibility

> **Agent guidance:** Determine WCAG compliance level from BRD/NFRs. If a web UI exists, this section is required. Define testing strategy and enforcement.

```markdown
## 22. Accessibility (a11y)

### 22.1 Compliance Target

- **Standard:** {{A11Y_STANDARD}} (e.g., WCAG 2.1 AA)
- **Testing tool:** {{A11Y_TESTING_TOOL}} (e.g., axe-core, Pa11y, Lighthouse)
- **CI enforcement:** {{A11Y_CI}} (e.g., axe-core in integration tests, Lighthouse CI threshold)

### 22.2 Requirements

| Area | Requirement | Implementation |
|------|-------------|----------------|
| Keyboard navigation | All interactive elements reachable via keyboard | tabindex, focus management |
| Screen readers | Semantic HTML, ARIA labels on custom components | aria-label, aria-describedby, role |
| Color contrast | {{CONTRAST_RATIO}} minimum (e.g., 4.5:1 for text, 3:1 for large text) | Design system tokens |
| Focus indicators | Visible focus ring on all interactive elements | CSS :focus-visible |
| Form labels | Every input has an associated label | `<label htmlFor>` or aria-label |
| Error messages | Errors announced to screen readers | aria-live="polite", role="alert" |
| Skip navigation | Skip-to-content link on every page | Hidden link, visible on focus |
| Alt text | All informational images have alt text | alt attribute, empty alt for decorative |
| Motion | Respect prefers-reduced-motion | @media (prefers-reduced-motion: reduce) |

### 22.3 Component Library

- **Base:** {{COMPONENT_LIBRARY}} (e.g., Radix UI primitives, Headless UI — accessibility built-in)
- **Custom components:** Must pass axe-core checks before merge
- **Testing:** {{A11Y_TESTING_STRATEGY}} (e.g., automated axe checks + manual screen reader testing per release)
```

---

## Section 23: Monitoring & Alerting

> **Agent guidance:** Load `observability-patterns.md`. Define SLOs, alert rules, incident response, and on-call setup. Reference NFR-AVAIL-* and NFR-PERF-* from BRD.

```markdown
## 23. Monitoring & Alerting

### 23.1 SLOs (Service Level Objectives)

| SLO | Target | Measurement | Alert Threshold |
|-----|--------|-------------|-----------------|
| Availability | {{AVAILABILITY_SLO}} (e.g., 99.9%) | Successful requests / total requests | < {{AVAILABILITY_ALERT}} over {{AVAILABILITY_WINDOW}} |
| Latency (P95) | {{LATENCY_SLO}} | P95 response time | > {{LATENCY_ALERT}} for {{LATENCY_WINDOW}} |
| Error rate | {{ERROR_RATE_SLO}} | 5xx responses / total responses | > {{ERROR_RATE_ALERT}} for {{ERROR_WINDOW}} |

### 23.2 Alert Rules

| Alert | Condition | Severity | Channel | Response |
|-------|-----------|----------|---------|----------|
| High error rate | 5xx > {{ERROR_THRESHOLD}}% for {{ERROR_DURATION}} | Critical | {{CRITICAL_CHANNEL}} | {{ERROR_RESPONSE}} |
| High latency | P95 > {{LATENCY_THRESHOLD}} for {{LATENCY_DURATION}} | Warning | {{WARNING_CHANNEL}} | {{LATENCY_RESPONSE}} |
| DB connection exhaustion | Active connections > {{DB_CONN_THRESHOLD}}% | Critical | {{CRITICAL_CHANNEL}} | Scale or investigate |
| Queue depth | Pending jobs > {{QUEUE_THRESHOLD}} | Warning | {{WARNING_CHANNEL}} | Scale workers |
| Disk usage | > {{DISK_THRESHOLD}}% | Warning | {{WARNING_CHANNEL}} | Cleanup or expand |
| Certificate expiry | < {{CERT_EXPIRY_THRESHOLD}} days | Warning | {{WARNING_CHANNEL}} | Renew |

### 23.3 Dashboards

| Dashboard | Content | Audience |
|-----------|---------|----------|
| Service overview | Request rate, error rate, latency, uptime | Engineering |
| Infrastructure | CPU, memory, disk, network, pod count | SRE/DevOps |
| Business metrics | {{BUSINESS_METRICS}} | Product/Leadership |
| Per-tenant | Tenant-specific usage, errors, quotas | Support |

### 23.4 Incident Response

- **Severity levels:**
  - SEV1: Service down, all users affected → {{SEV1_RESPONSE}}
  - SEV2: Degraded, significant impact → {{SEV2_RESPONSE}}
  - SEV3: Minor issue, workaround available → {{SEV3_RESPONSE}}

- **Post-incident:**
  - Blameless post-mortem within {{POSTMORTEM_SLA}}
  - Action items tracked to completion
  - Runbook updated if procedure was missing

### 23.5 On-Call Setup

- **Rotation:** {{ONCALL_ROTATION}} (e.g., weekly rotation, 2-person team)
- **Escalation:** {{ESCALATION_POLICY}} (e.g., 5 min → secondary, 15 min → engineering lead)
- **Tools:** {{ONCALL_TOOLS}} (e.g., PagerDuty, OpsGenie, Grafana OnCall)
```

---

## Agent Decision Guide

When filling this template, the `impl_guidelines_agent` should follow this decision process for each section:

### Questions to Ask the User (Normal Mode)

For each section, if the information is not available in `requirements/IMPLEMENTATION_GUIDELINES.md` or the BRD:

1. **Is this section applicable?** (e.g., multi-tenancy may not be needed for a personal project)
2. **What technology/approach do you prefer?** (provide 2-3 options with pros/cons)
3. **What are the scale requirements?** (affects caching, pooling, search engine choices)
4. **Are there compliance requirements?** (affects security, accessibility, i18n sections)

### Auto-Decision Ladder (--auto Mode)

For each `{{PLACEHOLDER}}`:

1. **Check draft:** Look in `requirements/IMPLEMENTATION_GUIDELINES.md` for explicit choice
2. **Infer from BRD:** NFR-PERF → caching needed; NFR-SEC → security headers; NFR-MULTI → multi-tenancy
3. **Match tech stack:** If Go backend → slog for logging, pgxpool for DB, testify for tests
4. **Apply defaults:** Use the most common industry choice for the project size/type
5. **Flag for review:** If genuinely ambiguous, use best guess + log as "AUTO-DECIDED — review recommended"

### Cross-Referencing

Every section should reference applicable BRD requirements:

```markdown
> **BRD References:** FR-001, FR-002, NFR-PERF-001
```

This ensures traceability between requirements and implementation decisions.
