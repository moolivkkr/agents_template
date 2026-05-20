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

> **Purpose:** Master blueprint for `docs/IMPLEMENTATION_GUIDELINES.md`. Fill every `{{PLACEHOLDER}}` with concrete, actionable decisions — no vague phrases, no "TBD" without owner/date. Each section must have enough detail for implementation without follow-up questions.

---

## How to Use

1. Fill `{{PLACEHOLDER}}` markers with project-specific values
2. If section N/A, mark as `N/A — [reason]` and remove sub-sections
3. Every decision concrete: "PostgreSQL 16" not "SQL database"
4. In --auto mode, log decisions to `agent_state/autonomous/decisions.md`
5. Cross-reference BRD requirements (FR-*, NFR-*, OBJ-*) per section

---

## Template Output Structure

```markdown
# {{PROJECT_NAME}}: Implementation Guidelines

> **Version:** {{VERSION}}
> **Date:** {{DATE}}
> **Purpose:** Consolidated engineering reference for the {{PROJECT_NAME}} platform
> **Scope:** All technical architecture decisions
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

> Load `code-quality.md` and `software-architecture.md` skill packs. NON-NEGOTIABLE.

```markdown
## 0. Coding Standards & Engineering Principles

> **NON-NEGOTIABLE. Every developer, agent, and code review enforces these. No exceptions.**

### 0.1 Performance-First Design

- Time complexity: {{MAX_ACCEPTABLE_COMPLEXITY}} unacceptable for user-facing paths
- Memory: minimize heap allocations in hot paths
- DB: N+1 queries are blocking code review defects
- Network: batch external calls, never call in a loop
- Concurrency: {{CONCURRENCY_MODEL}} for parallel I/O

**Performance budgets (hard limits, CI-enforced):**

| Operation | P50 | P95 | P99 | Max |
|-----------|-----|-----|-----|-----|
| REST read | {{P50_READ}} | {{P95_READ}} | {{P99_READ}} | {{MAX_READ}} |
| REST write | {{P50_WRITE}} | {{P95_WRITE}} | {{P99_WRITE}} | {{MAX_WRITE}} |
| DB indexed | {{P50_DB_INDEXED}} | {{P95_DB_INDEXED}} | {{P99_DB_INDEXED}} | {{MAX_DB_INDEXED}} |
| DB aggregation | {{P50_DB_AGG}} | {{P95_DB_AGG}} | {{P99_DB_AGG}} | {{MAX_DB_AGG}} |
| Background job | {{P50_JOB}} | {{P95_JOB}} | {{P99_JOB}} | {{MAX_JOB}} |

**Caching:** L1: {{L1_CACHE}} ({{L1_TTL}}), L2: {{L2_CACHE}} ({{L2_TTL}}), L3: {{L3_CACHE}}. Invalidation: {{CACHE_INVALIDATION_STRATEGY}}

**Pagination (mandatory ALL list endpoints):** Default: {{DEFAULT_PAGE_SIZE}}, Max: {{MAX_PAGE_SIZE}}, Strategy: {{PAGINATION_STRATEGY}}. Response must include: items, total, limit, offset/cursor, has_more.

**Connection pooling:** {{DB_POOL_LIBRARY}}, max {{DB_MAX_CONNS}}, min idle {{DB_MIN_CONNS}}, lifetime {{DB_MAX_CONN_LIFETIME}}, health check {{DB_HEALTH_CHECK_INTERVAL}}

### 0.2 Interface-Based Development

- Program to interfaces, not implementations; accept interfaces, return structs
- Keep interfaces small ({{MAX_INTERFACE_METHODS}} methods max)
- Interface lives in CONSUMER package, not provider
- DI via constructors — no global state, no init() side effects, no service locators
- Constructor pattern: `New*(deps...) *Type`

### 0.3 Small Functions — Unit-Testable

- Max {{MAX_FUNCTION_LINES}} lines, {{MAX_PARAMS}} params, {{MAX_RETURN_VALUES}} return values, {{MAX_NESTING_DEPTH}} nesting levels
- Early return on error — no deep nesting

### 0.4 Object-Oriented Design — Mandatory Patterns

| Pattern | Where Applied | Purpose |
|---------|---------------|---------|
| **Repository** | ALL data access | Abstract DB behind interface |
| **Service Layer** | ALL business logic | Orchestrate repos, enforce rules |
| **Strategy** | {{STRATEGY_USAGE}} | Swap implementations at runtime |
| **Factory** | {{FACTORY_USAGE}} | Encapsulate complex object creation |
| **Observer** | {{OBSERVER_USAGE}} | Decouple side effects |
| **Circuit Breaker** | ALL external calls | Prevent cascade failure |
| **Decorator** | {{DECORATOR_USAGE}} | Cross-cutting concerns |
| **Builder** | {{BUILDER_USAGE}} | Complex object construction |

**SOLID enforced at code review:**
- S: Each struct/package owns ONE concern
- O: New variants via interface implementation, not modifying existing code
- L: Mock implementations behave identically to real in tests
- I: Separate reader/writer interfaces; no god interfaces
- D: Depend on interfaces, wire in main.go / DI container

### 0.5 Naming Conventions

- **Files:** {{FILE_NAMING_CONVENTION}} | **Types:** {{TYPE_NAMING_CONVENTION}} | **Functions:** {{FUNCTION_NAMING_CONVENTION}}
- **Variables:** {{VARIABLE_NAMING_CONVENTION}} | **Constants:** {{CONSTANT_NAMING_CONVENTION}}
- **DB tables:** {{DB_TABLE_NAMING}} | **DB columns:** {{DB_COLUMN_NAMING}}
- **API endpoints:** {{API_ENDPOINT_NAMING}} | **Env vars:** {{ENV_VAR_NAMING}}

### 0.6 Code Organization Rules

- One concept per file; group by domain not technical layer
- Keep package APIs small — export only what consumers need
```

---

## Section 1: Project Structure

> Define exact directory layout. Reference `software-architecture.md` for layer boundaries.

```markdown
## 1. Project Structure

### 1.1 Directory Layout

{{PROJECT_STRUCTURE_TREE}}

### 1.2 Package/Module Boundaries

| Package/Module | Responsibility | May Import | Must NOT Import |
|----------------|---------------|------------|-----------------|
| {{PACKAGE_1}} | {{RESPONSIBILITY_1}} | {{ALLOWED_IMPORTS_1}} | {{FORBIDDEN_IMPORTS_1}} |

### 1.3 Layer Architecture

{{LAYER_DIAGRAM}}

**Dependency direction:** {{DEPENDENCY_RULE}}

| Layer | Owns | Does NOT Own |
|-------|------|-------------|
| Handler/Controller | Request parsing, validation, response serialization | Business logic, direct DB access |
| Service | Business rules, orchestration, transactions | HTTP concerns, SQL queries |
| Repository | Data access, query construction | Business rules, HTTP concerns |
| Domain | Entities, value objects, domain errors | Infrastructure, frameworks |

### 1.4 Shared Code

- Utils: `{{SHARED_UTILS_PATH}}` | Types: `{{SHARED_TYPES_PATH}}`
- Shared code must be stateless with zero external dependencies
```

---

## Section 2: API Design

> Load `api-excellence.md` skill pack.

```markdown
## 2. API Design

### 2.1 API Style & Versioning

- **Style:** {{API_STYLE}} | **Versioning:** {{API_VERSIONING}} | **Breaking change policy:** {{BREAKING_CHANGE_POLICY}}

### 2.2 URL Structure

| Method | Pattern | Description |
|--------|---------|-------------|
| GET | `/api/v1/{{RESOURCE}}` | List with pagination |
| GET | `/api/v1/{{RESOURCE}}/{id}` | Get single |
| POST | `/api/v1/{{RESOURCE}}` | Create |
| PUT | `/api/v1/{{RESOURCE}}/{id}` | Full update |
| PATCH | `/api/v1/{{RESOURCE}}/{id}` | Partial update |
| DELETE | `/api/v1/{{RESOURCE}}/{id}` | Soft/hard delete |

### 2.3 Request/Response Conventions

**Success:** `{ "data": { ... }, "meta": { "request_id": "{{REQUEST_ID_FORMAT}}", "timestamp": "ISO-8601" } }`

**List:** `{ "data": [...], "pagination": { "total": 100, "limit": {{DEFAULT_PAGE_SIZE}}, "offset": 0, "has_more": true }, "meta": { ... } }`

**Error:** `{ "error": { "code": "{{ERROR_CODE_FORMAT}}", "message": "...", "detail": "...", "retryable": false, "request_id": "uuid" } }`

### 2.4 HTTP Status Codes

| Status | When | Status | When |
|--------|------|--------|------|
| 200 | Read/update success | 400 | Validation/malformed |
| 201 | Created | 401 | Unauthenticated |
| 204 | Delete (no body) | 403 | Unauthorized |
| 404 | Not found | 409 | Conflict |
| 422 | Semantically invalid | 429 | Rate limited |
| 500 | Internal error | 502/503 | Upstream failure |

### 2.5 Rate Limiting

- Strategy: {{RATE_LIMIT_STRATEGY}} | Defaults: {{RATE_LIMIT_DEFAULTS}}
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 2.6 Idempotency

- Header: `{{IDEMPOTENCY_HEADER}}` | Required on: {{IDEMPOTENT_OPERATIONS}} | TTL: {{IDEMPOTENCY_TTL}}

### 2.7 Content Negotiation

- Default: `application/json` | Supported: {{SUPPORTED_CONTENT_TYPES}} | Uploads: `multipart/form-data`
```

---

## Section 3: Database Design

```markdown
## 3. Database Design

### 3.1 Technology

- **Engine:** {{DB_ENGINE}} | **ORM/Query:** {{ORM_OR_QUERY_LAYER}} | **Migrations:** {{MIGRATION_TOOL}} | **Connection:** {{DB_CONNECTION_LIB}}

### 3.2 Naming Conventions

- Tables: {{DB_TABLE_NAMING_DETAIL}} | Columns: {{DB_COLUMN_NAMING_DETAIL}}
- PKs: {{PK_CONVENTION}} | FKs: {{FK_CONVENTION}}
- Indexes: {{INDEX_NAMING}} | Constraints: {{CONSTRAINT_NAMING}}

### 3.3 Standard Columns (ALL tables)

| Column | Type | Purpose |
|--------|------|---------|
| `id` | {{PK_TYPE}} | Primary key |
| `tenant_id` | {{TENANT_ID_TYPE}} | Tenant isolation |
| `created_at` | `TIMESTAMPTZ` | Creation (DEFAULT NOW()) |
| `updated_at` | `TIMESTAMPTZ` | Last modified (trigger) |
| `created_by` / `updated_by` | {{USER_ID_TYPE}} | Audit |
| `deleted_at` | `TIMESTAMPTZ NULL` | Soft delete |

### 3.4 Migration Strategy

- **Direction:** Forward-only / Reversible | **Naming:** `{{MIGRATION_NAMING}}`
- **Review:** {{MIGRATION_REVIEW_PROCESS}} | **Zero-downtime:** {{ZERO_DOWNTIME_MIGRATION_STRATEGY}}
- Data migrations separate from schema; run as background jobs
- **Rollback:** {{MIGRATION_ROLLBACK_STRATEGY}}

### 3.5 Indexing Strategy

- Every FK gets an index; every WHERE column gets an index
- Composite indexes: most-selective column first
- Partial indexes for filtered queries; GIN indexes for JSONB/full-text
- Slow query threshold: {{SLOW_QUERY_THRESHOLD}}

### 3.6 Query Patterns

- No N+1: use JOINs or batch loading | Prepared statements: {{PREPARED_STATEMENT_POLICY}}
- Read replicas: {{READ_REPLICA_STRATEGY}} | Query timeout: {{QUERY_TIMEOUT}}
```

---

## Section 4: Authentication & Authorization

```markdown
## 4. Authentication & Authorization

### 4.1 Authentication

- **Method:** {{AUTH_METHOD}} | **Token format:** {{TOKEN_FORMAT}}
- **Lifetime:** Access: {{ACCESS_TOKEN_TTL}}, Refresh: {{REFRESH_TOKEN_TTL}}
- **Storage:** {{TOKEN_STORAGE}} | **Provider:** {{AUTH_PROVIDER}}

### 4.2 Authorization

- **Model:** {{AUTHZ_MODEL}} | **Roles:** {{DEFAULT_ROLES}} | **Permissions:** {{PERMISSION_FORMAT}}

| Role | {{RESOURCE_1}} | {{RESOURCE_2}} | {{RESOURCE_3}} |
|------|------|------|------|
| Admin | CRUD | CRUD | CRUD |
| Member | CR | CR | R |
| Viewer | R | R | R |

### 4.3 Middleware Chain

`Request → Rate Limiter → Auth → RBAC → Tenant Scoping → Handler`

### 4.4 API Keys

- **Format:** {{API_KEY_FORMAT}} | **Storage:** {{API_KEY_STORAGE}} (hashed, never plaintext)
- **Scoping:** {{API_KEY_SCOPING}} | **Rotation:** {{API_KEY_ROTATION_POLICY}}

### 4.5 Sessions

- **Store:** {{SESSION_STORE}} | **Invalidation:** {{SESSION_INVALIDATION}}
- **Concurrent:** {{CONCURRENT_SESSIONS_POLICY}}

### 4.6 Service-to-Service Auth

- **Method:** {{S2S_AUTH_METHOD}} | **Secrets:** {{S2S_SECRET_MANAGEMENT}}
```

---

## Section 5: Error Handling

> Load `code-quality.md`. Define domain error types mapping to HTTP status codes.

```markdown
## 5. Error Handling

### 5.1 Error Taxonomy

| Category | HTTP | Retryable | Example |
|----------|------|-----------|---------|
| Validation | 400 | No | Missing field |
| Authentication | 401 | No | Expired token |
| Authorization | 403 | No | Insufficient perms |
| Not Found | 404 | No | Resource missing |
| Conflict | 409 | No | Duplicate |
| Rate Limited | 429 | Yes | Too many requests |
| Internal | 500 | No | Unexpected error |
| Upstream | 502 | Yes | External failure |
| Unavailable | 503 | Yes | Temporarily down |

### 5.2 Domain Error Type

```{{LANG}}
{{DOMAIN_ERROR_STRUCT}}
```

**Error code constants:**
```{{LANG}}
{{ERROR_CODE_CONSTANTS}}
```

### 5.3 Error Handling Rules

- Wrap errors at layer boundaries with context
- Never swallow errors; use domain errors from service layer
- Log full error at handler level only; user-facing messages separate from internal details
- Panic recovery: {{PANIC_RECOVERY_STRATEGY}}

### 5.4 Error Wrapping Pattern

```{{LANG}}
{{ERROR_WRAPPING_EXAMPLE}}
```
```

---

## Section 6: Logging & Observability

> Load `observability-patterns.md`. tenant_id on every log/metric in multi-tenant systems.

```markdown
## 6. Logging & Observability

### 6.1 Structured Logging

- **Library:** {{LOG_LIBRARY}} | **Format:** {{LOG_FORMAT}} | **Output:** {{LOG_OUTPUT}} → {{LOG_COLLECTOR}}

**Mandatory fields:** `timestamp`, `level`, `message`, `tenant_id`, `trace_id`, `request_id`, `service`, `component`

### 6.2 Log Levels

| Level | When | Example |
|-------|------|---------|
| DEBUG | Dev-only detail | SQL queries |
| INFO | Business events | "User created" |
| WARN | Recoverable issues | "Cache miss fallback" |
| ERROR | Failures needing attention | "DB connection lost" |
| FATAL | Unrecoverable | "Cannot bind port" |

Rules: Never log PII/tokens; 404 is INFO not ERROR; ERROR must have diagnostic context.

### 6.3 Metrics

- **Library:** {{METRICS_LIBRARY}} | **Export:** {{METRICS_EXPORT}} | **Dashboard:** {{METRICS_DASHBOARD}}

| Metric | Type | Labels |
|--------|------|--------|
| `http_request_duration_seconds` | Histogram | method, path, status, tenant_id |
| `http_request_total` | Counter | method, path, status, tenant_id |
| `db_query_duration_seconds` | Histogram | operation, table, tenant_id |
| `external_call_duration_seconds` | Histogram | service, operation, result |
| `active_connections` | Gauge | pool_name |
| `error_total` | Counter | type, component, tenant_id |

### 6.4 Distributed Tracing

- **Library:** {{TRACING_LIBRARY}} | **Exporter:** {{TRACING_EXPORTER}} | **Sampling:** {{TRACING_SAMPLING}}
- Mandatory spans: HTTP requests, DB queries, external calls, queue pub/sub, cache ops

### 6.5 Request-Scoped Logger

```{{LANG}}
{{REQUEST_LOGGER_MIDDLEWARE}}
```
```

---

## Section 7: Testing Strategy

> Load `testing-principles.md`.

```markdown
## 7. Testing Strategy

### 7.1 Test Pyramid

| Level | Framework | Coverage | Run When |
|-------|-----------|----------|----------|
| Unit | {{UNIT_FRAMEWORK}} | {{UNIT_COVERAGE}}% | Every commit |
| Integration | {{INTEGRATION_FRAMEWORK}} | {{INTEGRATION_COVERAGE}}% | Every PR |
| E2E | {{E2E_FRAMEWORK}} | {{E2E_COVERAGE}} critical paths | Pre-release |
| Performance | {{PERF_FRAMEWORK}} | {{PERF_TARGETS}} | Weekly |

### 7.2 Test Naming: `{{TEST_NAMING_PATTERN}}`

### 7.3 Test Data

- Fixtures: {{TEST_FIXTURE_STRATEGY}} | DB: {{TEST_DB_STRATEGY}}
- Cleanup: {{TEST_CLEANUP_STRATEGY}} | Mocking: {{MOCK_STRATEGY}} via {{MOCK_LIBRARY}}

### 7.4 Test Structure

```{{LANG}}
{{TEST_STRUCTURE_EXAMPLE}}
```

### 7.5 Do NOT Test

Framework internals, third-party libs, trivial getters, generated code.

### 7.6 CI Integration

- Environment: {{TEST_CI_ENVIRONMENT}} | Parallelism: {{TEST_PARALLELISM}}
- Timeout: {{TEST_TIMEOUT}} | Flaky policy: {{FLAKY_TEST_POLICY}}
```

---

## Section 8: Security

> Load `security-owasp.md`.

```markdown
## 8. Security

### 8.1 OWASP Top 10 Mitigations

| Vulnerability | Mitigation |
|--------------|------------|
| Injection | {{INJECTION_MITIGATION}} — parameterized queries |
| Broken Auth | {{BROKEN_AUTH_MITIGATION}} — JWT validation, secure sessions |
| Sensitive Data | {{SENSITIVE_DATA_MITIGATION}} — encrypt at rest/transit |
| XXE | {{XXE_MITIGATION}} |
| Broken Access | {{BROKEN_ACCESS_MITIGATION}} — RBAC on every route |
| Misconfiguration | {{MISCONFIG_MITIGATION}} — security headers, no debug in prod |
| XSS | {{XSS_MITIGATION}} — output encoding, CSP |
| Deserialization | {{DESER_MITIGATION}} — schema validation |
| Components | {{COMPONENTS_MITIGATION}} — dependency scanning |
| Logging | {{LOGGING_MITIGATION}} — structured audit trail |

### 8.2 Input Validation

- Strategy: {{INPUT_VALIDATION_STRATEGY}} | Library: {{VALIDATION_LIBRARY}}
- Allowlist chars, enforce max lengths, validate enums, sanitize HTML if accepted

### 8.3 Output Encoding

- HTML: {{HTML_ENCODING}} | JSON: {{JSON_ENCODING}} | SQL: parameterized only

### 8.4 Secrets Management

- Dev: {{DEV_SECRETS}} | Prod: {{PROD_SECRETS}} | Rotation: {{SECRET_ROTATION_POLICY}}
- Never hardcode, commit .env, or log secrets

### 8.5 CORS

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
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
```

---

## Section 9: Performance

> Load `resiliency-patterns.md`.

```markdown
## 9. Performance

### 9.1 Caching

| Data Type | L1 (In-Process) | L2 (Distributed) | TTL | Invalidation |
|-----------|-----------------|-------------------|-----|--------------|
| {{CACHE_DATA_1}} | {{L1_1}} | {{L2_1}} | {{TTL_1}} | {{INVALIDATION_1}} |
| Session data | No | {{SESSION_CACHE}} | {{SESSION_TTL}} | On logout/change |

### 9.2 Connection Pooling

DB: {{DB_POOL_CONFIG}} | Redis: {{REDIS_POOL_CONFIG}} | HTTP: {{HTTP_POOL_CONFIG}}

### 9.3 Query Optimization

- EXPLAIN ANALYZE on every new query; no seq scans on tables >10K rows
- N+1 detection: {{N_PLUS_ONE_DETECTION}} | Slow query log: >{{SLOW_QUERY_MS}}ms = WARN

### 9.4 Lazy Loading (Frontend)

- Route splitting: {{CODE_SPLITTING_STRATEGY}} | Virtual scroll: >{{VIRTUAL_SCROLL_THRESHOLD}} items
- Image lazy loading; API caching: {{CLIENT_CACHE_STRATEGY}}

### 9.5 Circuit Breakers

- Library: {{CIRCUIT_BREAKER_LIB}} | Max {{CB_MAX_FAILURES}} failures → open, {{CB_RESET_TIMEOUT}} reset
- Applied to ALL external calls; state changes logged + gauged

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

```markdown
## 10. Configuration Management

### 10.1 Sources (precedence)

1. {{CONFIG_SOURCE_1}} (highest) → 2. {{CONFIG_SOURCE_2}} → 3. {{CONFIG_SOURCE_3}} (defaults)

### 10.2 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `{{APP_PREFIX}}_PORT` | No | {{DEFAULT_PORT}} | HTTP port |
| `{{APP_PREFIX}}_DB_URL` | Yes | — | DB connection |
| `{{APP_PREFIX}}_LOG_LEVEL` | No | `info` | Log level |
| `{{APP_PREFIX}}_ENV` | Yes | — | Environment |

### 10.3 Validation

- All required config validated at startup — fail fast
- Type-safe config struct — no raw string lookups at runtime

### 10.4 Feature Flags

- System: {{FEATURE_FLAG_SYSTEM}} | Naming: {{FEATURE_FLAG_NAMING}}
- Cleanup within {{FEATURE_FLAG_CLEANUP_WINDOW}} of full rollout

### 10.5 Per-Environment

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Log level | debug | info | info |
| Debug endpoints | enabled | enabled | disabled |
| CORS | localhost | staging domain | prod domain |
| Rate limits | disabled | relaxed | enforced |
| Seed data | auto | test data | empty |
```

---

## Section 11: Deployment & CI/CD

```markdown
## 11. Deployment & CI/CD

### 11.1 Docker

- Base: {{DOCKER_BASE_IMAGE}} | Multi-stage: Yes | Image: `{{PROJECT}}-api:{{VERSION}}`
- Health: `HEALTHCHECK CMD {{HEALTH_CHECK_CMD}}`

### 11.2 Docker Compose

```yaml
{{DOCKER_COMPOSE_EXAMPLE}}
```

### 11.3 CI/CD

- Platform: {{CI_PLATFORM}} | Trigger: {{CI_TRIGGER}}
- Stages: `{{CI_PIPELINE_STAGES}}`

### 11.4 Promotion: `{{PROMOTION_FLOW}}`

### 11.5 Rollback

- Method: {{ROLLBACK_METHOD}} | Time: <{{ROLLBACK_TIME}} | Data: {{DATA_ROLLBACK_STRATEGY}}

### 11.6 Health Checks

| Endpoint | Check | Expected |
|----------|-------|----------|
| `{{HEALTH_ENDPOINT}}` | Liveness | 200 |
| `{{READY_ENDPOINT}}` | DB + cache | 200 + deps |
```

---

## Section 12: Documentation

```markdown
## 12. Documentation

### 12.1 API Docs

- Format: {{API_DOC_FORMAT}} | Generation: {{API_DOC_GENERATION}} | Host: {{API_DOC_HOSTING}}

### 12.2 Code Comments

- Public APIs: doc comment explaining what; complex logic: inline why
- No noise comments; TODO format: `// TODO({{AUTHOR}}): {{DESCRIPTION}} — {{TICKET_ID}}`

### 12.3 ADRs

Location: `docs/adr/`, Format: `NNNN-title.md`
```markdown
# ADR-NNNN: {{TITLE}}
## Status: {{Proposed | Accepted | Deprecated | Superseded}}
## Context — ## Decision — ## Consequences
```

### 12.4 Runbooks

Location: `docs/runbooks/` — required for every production alert and deployment procedure.
```

---

## Section 13: Git Workflow

> Load `git-workflow.md`.

```markdown
## 13. Git Workflow

### 13.1 Branching

- Strategy: {{GIT_STRATEGY}} | Main: `{{MAIN_BRANCH}}` (always deployable)
- Features: `{{FEATURE_BRANCH_FORMAT}}` | Releases: {{RELEASE_BRANCH_POLICY}} | Hotfix: `hotfix/{{TICKET_ID}}-description`

### 13.2 Commits

- Format: {{COMMIT_FORMAT}} | `{{COMMIT_TEMPLATE}}`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

### 13.3 PR Process

1. {{PR_STEP_1}} → 2. {{PR_STEP_2}} → 3. {{PR_STEP_3}} (min {{MIN_REVIEWERS}} approvals) → 4. {{PR_STEP_4}}

### 13.4 Code Review

- SLA: {{REVIEW_SLA}} | Focus: architecture, security, correctness | Max PR: {{MAX_PR_SIZE}} lines

### 13.5 Protected Branches

- `{{MAIN_BRANCH}}`: {{MAIN_BRANCH_RULES}} | Force push: {{FORCE_PUSH_POLICY}}
```

---

## Section 14: Dependency Management

```markdown
## 14. Dependency Management

### 14.1 Versioning

- Lock: {{LOCK_FILE}} | Pinning: {{VERSION_PINNING}} | Updates: {{UPDATE_CADENCE}}

### 14.2 Security Scanning

- Tool: {{SECURITY_SCAN_TOOL}} | Frequency: {{SCAN_FREQUENCY}} | Policy: {{VULN_POLICY}}

### 14.3 Licenses

- Allowed: {{ALLOWED_LICENSES}} | Forbidden: {{FORBIDDEN_LICENSES}} | Review: {{LICENSE_REVIEW_PROCESS}}

### 14.4 Internal Dependencies

- Shared packages: {{SHARED_PACKAGE_STRATEGY}} | Versioning: {{INTERNAL_VERSION_STRATEGY}}
```

---

## Section 15: Multi-Tenancy

> Required if BRD mentions multiple orgs/workspaces/teams. If single-tenant, mark N/A.

```markdown
## 15. Multi-Tenancy

### 15.1 Isolation

- **Level:** {{ISOLATION_LEVEL}} | **Tenant ID source:** {{TENANT_ID_SOURCE}} | **Resolution:** {{TENANT_RESOLUTION}}

### 15.2 Data Partitioning

- Strategy: {{PARTITION_STRATEGY}} | Enforcement: {{PARTITION_ENFORCEMENT}}
- Indexes: `(tenant_id, id)`, `(tenant_id, created_at)`

### 15.3 RLS

```sql
{{RLS_POLICY_EXAMPLE}}
```

### 15.4 Tenant-Scoped Operations

- Every service method and repo query MUST include tenant_id
- Cross-tenant access is a VIOLATION; return 404 (not 403) for other tenants' resources

### 15.5 Noisy Neighbor

- Rate limit: {{PER_TENANT_RATE_LIMIT}} | Quotas: {{TENANT_QUOTAS}} | Pool: {{TENANT_POOL_STRATEGY}}

### 15.6 Tenancy Model

- Architecture: {{TENANCY_MODEL}} | Pooled: {{POOLED_TIERS}} | Dedicated: {{DEDICATED_TIERS}}
- DB isolation: {{DB_ISOLATION}} | Compute: {{COMPUTE_ISOLATION}} | Tenant extraction: {{TENANT_EXTRACTION}}
- Encryption: {{ENCRYPTION_MODEL}} | Skill pack: `.claude/skills/infrastructure/saas-tenancy-models.md`

### 15.7 Local AWS Simulation

- Tool: {{LOCAL_AWS_TOOL}} | Services: {{LOCAL_AWS_SERVICES}} | Regions: {{LOCAL_AWS_REGIONS}}
- Init: `localstack/init/ready.d/` | Multi-region: {{MULTI_REGION}}
- Skill pack: `.claude/skills/infrastructure/localstack-aws-local.md`
```

---

## Section 16: Background Jobs & Async Processing

```markdown
## 16. Background Jobs

### 16.1 Queue: {{QUEUE_SYSTEM}} via {{QUEUE_LIBRARY}}

### 16.2 Job Types

| Job | Priority | Timeout | Retries | Dead Letter |
|-----|----------|---------|---------|-------------|
| {{JOB_1}} | {{PRIORITY_1}} | {{TIMEOUT_1}} | {{RETRIES_1}} | {{DL_1}} |

### 16.3 Retry: {{RETRY_BACKOFF}}, max {{MAX_RETRIES}}, DLQ: {{DLQ_STRATEGY}}. Jobs MUST be idempotent.

### 16.4 Scheduling: {{CRON_STRATEGY}} | Uniqueness: {{JOB_UNIQUENESS}}

### 16.5 Monitoring: Queue depth alert >{{QUEUE_DEPTH_THRESHOLD}}, duration histogram per type, failure counter, DLQ alert >0
```

---

## Section 17: File Storage

```markdown
## 17. File Storage

### 17.1 Backend: {{STORAGE_BACKEND}} | CDN: {{CDN_PROVIDER}} | Local: {{LOCAL_STORAGE}}

### 17.2 Uploads

- Max: {{MAX_FILE_SIZE}} | Allowed: {{ALLOWED_FILE_TYPES}} (whitelist)
- Validation: {{FILE_VALIDATION}} | Naming: {{FILE_NAMING}} | Method: {{UPLOAD_METHOD}}

### 17.3 Access: {{FILE_URL_STRATEGY}} | Tenant path: `{{TENANT_PATH_FORMAT}}`

### 17.4 Images: Resize: {{IMAGE_RESIZE_STRATEGY}} | Formats: {{IMAGE_FORMATS}}
```

---

## Section 18: Email & Notifications

```markdown
## 18. Email & Notifications

### 18.1 Provider: {{EMAIL_PROVIDER}} | From: {{FROM_ADDRESS}} | Templates: {{EMAIL_TEMPLATE_SYSTEM}}

### 18.2 Email Types

| Email | Trigger | Template | Priority |
|-------|---------|----------|----------|
| {{EMAIL_1}} | {{TRIGGER_1}} | {{TEMPLATE_1}} | {{PRIORITY_1}} |

### 18.3 Channels

| Channel | Technology | Use Cases |
|---------|-----------|-----------|
| Email | {{EMAIL_TECH}} | {{EMAIL_USES}} |
| In-app | {{INAPP_TECH}} | {{INAPP_USES}} |
| Push | {{PUSH_TECH}} | {{PUSH_USES}} |
| SMS | {{SMS_TECH}} | {{SMS_USES}} |

### 18.4 Delivery: Webhooks: {{DELIVERY_WEBHOOKS}} | Tracking: {{DELIVERY_TRACKING}} | Retry: {{EMAIL_RETRY_COUNT}}x with {{EMAIL_RETRY_BACKOFF}}
```

---

## Section 19: Search

```markdown
## 19. Search

### 19.1 Engine: {{SEARCH_ENGINE}} | Indexing: {{INDEX_STRATEGY}} | Refresh: {{INDEX_REFRESH}}

### 19.2 Features

| Feature | Supported | Implementation |
|---------|-----------|----------------|
| Full-text | {{FTS_SUPPORT}} | {{FTS_IMPL}} |
| Fuzzy | {{FUZZY_SUPPORT}} | {{FUZZY_IMPL}} |
| Faceted | {{FACET_SUPPORT}} | {{FACET_IMPL}} |
| Autocomplete | {{AUTOCOMPLETE_SUPPORT}} | {{AUTOCOMPLETE_IMPL}} |

### 19.3 Searchable Entities

| Entity | Fields | Boost | Filters |
|--------|--------|-------|---------|
| {{ENTITY_1}} | {{FIELDS_1}} | {{BOOST_1}} | {{FILTERS_1}} |

### 19.4 API: `GET /api/v1/search?q={{QUERY}}&type={{TYPE}}&filters={{FILTERS}}` — cursor pagination, tenant-scoped
```

---

## Section 20: Data Import/Export

```markdown
## 20. Data Import/Export

### 20.1 Import

- Formats: {{IMPORT_FORMATS}} | Max: {{IMPORT_MAX_SIZE}} | Processing: {{IMPORT_PROCESSING}}
- Row-by-row validation with error report | Partial: {{PARTIAL_SUCCESS_POLICY}} | Duplicates: {{DUPLICATE_HANDLING}}

### 20.2 Export

- Formats: {{EXPORT_FORMATS}} | Max: {{EXPORT_MAX_RECORDS}} | Processing: {{EXPORT_PROCESSING}}
- Tenant-scoped only

### 20.3 Progress: `GET /api/v1/jobs/{job_id}` | Real-time: {{REALTIME_PROGRESS}} | Email on complete/fail

### 20.4 Bulk: Batch {{BATCH_SIZE}} per txn | Rate: {{BULK_RATE_LIMIT}} | Temp files cleaned after
```

---

## Section 21: Internationalization

```markdown
## 21. i18n

### 21.1 Required: {{I18N_REQUIRED}} | Default: {{DEFAULT_LOCALE}} | Supported: {{SUPPORTED_LOCALES}}

### 21.2 Framework: Frontend: {{FRONTEND_I18N}} | Backend: {{BACKEND_I18N}} | Format: {{TRANSLATION_FORMAT}}

### 21.3 Translation: Storage: {{TRANSLATION_STORAGE}} | Workflow: {{TRANSLATION_WORKFLOW}} | Fallback: {{TRANSLATION_FALLBACK}}

### 21.4 Rules

- Never hardcode user-facing strings; use locale-aware date/number/currency formatters
- Use ICU plural rules; RTL: {{RTL_SUPPORT}}
```

---

## Section 22: Accessibility

```markdown
## 22. Accessibility

### 22.1 Standard: {{A11Y_STANDARD}} | Testing: {{A11Y_TESTING_TOOL}} | CI: {{A11Y_CI}}

### 22.2 Requirements

| Area | Requirement |
|------|-------------|
| Keyboard nav | All interactive elements reachable |
| Screen readers | Semantic HTML, ARIA labels |
| Contrast | {{CONTRAST_RATIO}} minimum |
| Focus indicators | Visible :focus-visible ring |
| Forms | Every input labeled |
| Errors | aria-live announcements |
| Skip nav | Skip-to-content link |
| Alt text | All informational images |
| Motion | Respect prefers-reduced-motion |

### 22.3 Components: {{COMPONENT_LIBRARY}} | Custom must pass axe-core | Testing: {{A11Y_TESTING_STRATEGY}}
```

---

## Section 23: Monitoring & Alerting

> Load `observability-patterns.md`.

```markdown
## 23. Monitoring & Alerting

### 23.1 SLOs

| SLO | Target | Alert Threshold |
|-----|--------|-----------------|
| Availability | {{AVAILABILITY_SLO}} | <{{AVAILABILITY_ALERT}} over {{AVAILABILITY_WINDOW}} |
| Latency P95 | {{LATENCY_SLO}} | >{{LATENCY_ALERT}} for {{LATENCY_WINDOW}} |
| Error rate | {{ERROR_RATE_SLO}} | >{{ERROR_RATE_ALERT}} for {{ERROR_WINDOW}} |

### 23.2 Alerts

| Alert | Condition | Severity | Response |
|-------|-----------|----------|----------|
| High errors | 5xx >{{ERROR_THRESHOLD}}% for {{ERROR_DURATION}} | Critical | {{ERROR_RESPONSE}} |
| High latency | P95 >{{LATENCY_THRESHOLD}} for {{LATENCY_DURATION}} | Warning | {{LATENCY_RESPONSE}} |
| DB exhaustion | >{{DB_CONN_THRESHOLD}}% | Critical | Scale/investigate |
| Queue depth | >{{QUEUE_THRESHOLD}} | Warning | Scale workers |
| Disk | >{{DISK_THRESHOLD}}% | Warning | Cleanup/expand |
| Cert expiry | <{{CERT_EXPIRY_THRESHOLD}} days | Warning | Renew |

### 23.3 Dashboards

| Dashboard | Audience |
|-----------|----------|
| Service overview (rate, errors, latency, uptime) | Engineering |
| Infrastructure (CPU, mem, disk, pods) | SRE |
| Business metrics ({{BUSINESS_METRICS}}) | Product |
| Per-tenant usage | Support |

### 23.4 Incidents

- SEV1 (down): {{SEV1_RESPONSE}} | SEV2 (degraded): {{SEV2_RESPONSE}} | SEV3 (minor): {{SEV3_RESPONSE}}
- Post-mortem within {{POSTMORTEM_SLA}}, action items tracked, runbooks updated

### 23.5 On-Call

- Rotation: {{ONCALL_ROTATION}} | Escalation: {{ESCALATION_POLICY}} | Tools: {{ONCALL_TOOLS}}
```

---

## Agent Decision Guide

### Auto-Decision Ladder (--auto Mode)

For each `{{PLACEHOLDER}}`:
1. **Check draft:** Look in `requirements/IMPLEMENTATION_GUIDELINES.md`
2. **Infer from BRD:** NFR-PERF → caching; NFR-SEC → security headers; NFR-MULTI → multi-tenancy
3. **Match tech stack:** Go → slog, pgxpool, testify; etc.
4. **Apply defaults:** Most common industry choice for project size/type
5. **Flag for review:** If ambiguous, use best guess + log as "AUTO-DECIDED — review recommended"

### Cross-Referencing

Every section should reference: `> **BRD References:** FR-001, FR-002, NFR-PERF-001`
