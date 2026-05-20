---
command: deploy
description: Deploy the application. Reads IMPLEMENTATION_GUIDELINES for infra config. Supports local, staging, and production targets.
arguments:
  - name: target
    required: false
    default: local
    description: "Deployment target: local | staging | prod"
  - name: phase
    required: false
    description: "Deploy artifacts from a specific phase. Omit to deploy current state."
  - name: dry_run
    required: false
    default: false
    description: "Show what would be deployed without actually deploying"
---

# /deploy — Application Deployment

Deploys the application to the specified target using the infrastructure configuration from `docs/IMPLEMENTATION_GUIDELINES.md`.

**⚠ Production deployments always require explicit confirmation.**

---

## Step 0 — Pre-flight Checks

```bash
TARGET=${ARG_TARGET:-local}
echo "▶ Deploying to: $TARGET"
```

Read `docs/IMPLEMENTATION_GUIDELINES.md` Section 5 (Local Dev Environment) and Section 1 (Infrastructure) for:
- Container/orchestration technology
- Environment configuration
- Required secrets/env vars

Gate check (non-local only):
- Latest phase gate must be passed: `agent_state/phases/*/gate.passed`
- All tests must be green: check latest test results
- No HIGH security findings outstanding

---

## Step 1 — Build

**Agent:** `deployment_agent`

Reads IMPLEMENTATION_GUIDELINES for build commands. Builds production artifacts:

```bash
# Docker build (if containerized — adjust per IMPLEMENTATION_GUIDELINES)
docker build --no-cache -t <project>:<version> .

# Or language-specific build:
# go build -o bin/app ./cmd/api
# npm run build
# python -m build
```

Verifies build succeeds.

### Build Failure Recovery (CLOSED LOOP)
On failure:
1. Surface error with context (compiler output, missing dependencies)
2. Attempt auto-fix: if error is a missing dependency, run `go mod tidy` / `npm install` / `pip install -r requirements.txt`
3. Re-run build (max 1 retry after auto-fix)
4. If still failing: STOP with clear error and suggest manual fix

---

## Step 2 — Database Migrations

**Agent:** Generated `migration_agent`

Runs pending migrations against the target database:

```bash
# Migration command from IMPLEMENTATION_GUIDELINES
# e.g. goose up, flyway migrate, alembic upgrade head, prisma migrate deploy
```

**Dry run:** shows pending migrations without applying.

### Migration Failure Recovery (CLOSED LOOP)
On failure:
1. STOP — do NOT proceed with deployment
2. Surface error with specific migration file and error message
3. If error is a connection/transient issue (timeout, connection refused):
   - Wait 5 seconds, retry migration (max 2 retries)
   - If still failing: surface connection issue and suggest checking DB status
4. If error is a schema conflict (duplicate column, constraint violation):
   - Surface the conflict with rollback command: `<migration_tool> down 1`
   - Do NOT auto-rollback — require user confirmation
5. Write migration status to `agent_state/reports/migration_status.md`

---

## Step 3 — Deploy

### Local
```bash
docker compose up -d  # (or equivalent from IMPLEMENTATION_GUIDELINES)
```

### Staging / Production
**⚠ Confirm with user before proceeding for staging and prod targets.**

Reads infrastructure config from IMPLEMENTATION_GUIDELINES. Applies deployment using configured orchestration (Docker Compose / Kubernetes / cloud CLI).

---

## Step 4 — Health Check

After deployment, verify services are healthy:

```bash
# Health check endpoint (from IMPLEMENTATION_GUIDELINES)
curl -f http://localhost:<PORT>/health || curl -f http://localhost:<PORT>/api/v1/health
```

### Health Check Recovery (CLOSED LOOP)

1. Wait up to 60s for healthy status (poll every 5s)
2. If unhealthy after 60s:
   - Print container logs: `docker logs --tail 50 <container>`
   - Diagnose: check for common issues (port conflict, missing env var, crash loop)
   - If crash loop detected: `docker restart <container>`, wait 30s more (1 retry)
   - If port conflict: surface specific port and conflicting process
3. If still unhealthy after retry:
   - Surface rollback steps:
     ```
     ⛔ Health check failed after retry
     Rollback: docker compose down && git checkout phase-${PHASE}-complete -- docker-compose.yml && docker compose up -d
     Logs: docker logs <container>
     ```
4. Write deployment status to `agent_state/reports/deploy_status.md`

---

## Step 4b — Observability Setup (first deploy to staging/prod only)

**Agent:** `observability_agent`
**When:** Deploying to staging or prod for the first time (`TARGET != local`)

Reads observability config from `docs/IMPLEMENTATION_GUIDELINES.md` §Observability. Verifies:
- Log aggregation is configured and receiving logs
- Metrics endpoints are reachable
- Traces (if configured) are being emitted

Output: `agent_state/reports/observability_setup.md` with pass/fail per check.

---

## Step 4c — CI/CD Pipeline Setup (first deploy only)

**Agent:** `ci_cd_agent`
**When:** `agent_state/reports/cicd_setup.md` does not yet exist (first time only)

Reads CI/CD config from `docs/IMPLEMENTATION_GUIDELINES.md` §CI/CD. Generates or validates:
- Pipeline configuration file (`.github/workflows/`, `.gitlab-ci.yml`, etc.)
- Required environment variables and secrets
- Deploy triggers and environment protection rules

Output: `agent_state/reports/cicd_setup.md`

---

## Step 5 — Post-Deploy Health Validation

After successful deployment, verify the application actually works beyond the basic health endpoint:

1. **Endpoint health check** — curl every route in the phase manifest's `api_routes[]`
   - GET endpoints: verify 200 status + response has expected shape
   - Authenticated endpoints: use test credentials from seed data
   - Timeout: 10s per endpoint
   - Record: status code, response time, response body shape

2. **Contract shape validation** — for each endpoint response:
   - Compare against `data-contracts.md` TypeScript interfaces
   - Verify list endpoints return arrays, single endpoints return objects
   - Verify required fields are present and non-null
   - Flag any CONTRACT_VIOLATION

3. **Performance baseline** — record p95 response times per endpoint
   - Write to `agent_state/deploy/health-check-<timestamp>.json`
   - If a previous health check exists: compare response times
   - If >2x slower than previous deploy: WARNING — investigate before declaring success

4. **On failure:**
   - Surface specific endpoint + failure reason
   - Recommend: `/rollback` or targeted fix + redeploy
   - Do NOT auto-rollback (user decides)
   - Write failure details to health report for debugging

Output: `agent_state/deploy/health-report.md`

```markdown
# Post-Deploy Health Report — <timestamp>

## Endpoint Validation
| Endpoint | Status | Response Time | Contract | Result |
|----------|--------|---------------|----------|--------|
| GET /api/v1/health | 200 | 12ms | — | ✅ |
| GET /api/v1/users | 200 | 45ms | ✅ valid | ✅ |
| POST /api/v1/auth | 200 | 80ms | ✅ valid | ✅ |

## Performance Comparison (vs previous deploy)
| Endpoint | Previous p95 | Current p95 | Delta | Status |
|----------|-------------|-------------|-------|--------|

## Failures
[None | list with reproduction details]

## Verdict
HEALTHY — all endpoints responding, contracts valid, performance within bounds
DEGRADED — N endpoints failing or N contract violations (see above)
```

---

## Step 6 — Report

```
✅ Deployment complete — target: <TARGET>

  Build:      ✅ <image>:<version>
  Migrations: ✅ N migrations applied (or: N already up to date)
  Services:   ✅ all healthy

  Endpoints:
    API:  http://localhost:<PORT>/api/v1/
    UI:   http://localhost:<UI_PORT>/        (if frontend)
    Docs: http://localhost:<PORT>/api/docs   (if OpenAPI enabled)

  (or for non-local targets: deployed URLs)
```
