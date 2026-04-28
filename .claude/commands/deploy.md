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

Verifies build succeeds. On failure: surface error with context.

---

## Step 2 — Database Migrations

**Agent:** Generated `migration_agent`

Runs pending migrations against the target database:

```bash
# Migration command from IMPLEMENTATION_GUIDELINES
# e.g. goose up, flyway migrate, alembic upgrade head, prisma migrate deploy
```

**Dry run:** shows pending migrations without applying.
**On failure:** STOP — do not proceed with deployment. Surface error with rollback instructions.

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

Waits up to 60s for healthy status. On failure: print logs and surface rollback steps.

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

## Step 5 — Report

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
