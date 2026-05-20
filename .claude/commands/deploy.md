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

Deploys to specified target using `docs/IMPLEMENTATION_GUIDELINES.md` infra config.

**Production deployments always require explicit confirmation.**

---

## Step 0 — Pre-flight Checks

```bash
TARGET=${ARG_TARGET:-local}
```

Read IMPLEMENTATION_GUIDELINES Section 5 (Local Dev) and Section 1 (Infrastructure): container tech, env config, required secrets.

Gate check (non-local): latest phase gate passed, all tests green, no HIGH security findings.

---

## Step 1 — Build

**Agent:** `deployment_agent`

```bash
docker build --no-cache -t <project>:<version> .
# Or: go build, npm run build, python -m build
```

**Build failure recovery:** surface error, attempt auto-fix (missing dependency → install), retry once, then STOP.

---

## Step 2 — Database Migrations

**Agent:** Generated `migration_agent`

Run pending migrations. **Dry run:** show pending without applying.

**Migration failure:** STOP immediately. Transient errors → wait 5s, retry (max 2). Schema conflicts → surface with rollback command, do NOT auto-rollback. Write status to `agent_state/reports/migration_status.md`.

---

## Step 3 — Deploy

### Local
```bash
docker compose up -d
```

### Staging / Production
Confirm with user before proceeding. Apply deployment using configured orchestration.

---

## Step 4 — Health Check

```bash
curl -f http://localhost:<PORT>/health || curl -f http://localhost:<PORT>/api/v1/health
```

**Recovery:** Poll every 5s up to 60s. Unhealthy → check logs, diagnose (port conflict, missing env, crash loop). Crash loop → restart + 30s wait (1 retry). Still unhealthy → surface rollback steps + STOP.

Write: `agent_state/reports/deploy_status.md`

---

## Step 4b — Observability Setup (first staging/prod deploy)

**Agent:** `observability_agent` | **When:** `TARGET != local`, first time

Verify: log aggregation receiving, metrics endpoints reachable, traces emitting.

Output: `agent_state/reports/observability_setup.md`

---

## Step 4c — CI/CD Pipeline Setup (first deploy)

**Agent:** `ci_cd_agent` | **When:** `agent_state/reports/cicd_setup.md` doesn't exist

Generate/validate pipeline config, required env vars/secrets, deploy triggers.

Output: `agent_state/reports/cicd_setup.md`

---

## Step 5 — Post-Deploy Health Validation

1. **Endpoint health** — curl every route in manifest's `api_routes[]`, verify status + shape + auth
2. **Contract validation** — compare responses against `data-contracts.md`, verify ARRAY/OBJECT correctness, required fields non-null
3. **Performance baseline** — record p95 per endpoint, compare against previous deploy (>2x slower → WARNING)
4. **On failure** — surface endpoint + reason, recommend `/rollback` or fix, do NOT auto-rollback

Output: `agent_state/deploy/health-report.md` (endpoint table, performance comparison, failures, verdict: HEALTHY/DEGRADED)

---

## Step 6 — Report

```
✅ Deployment complete — target: <TARGET>
  Build:      ✅ <image>:<version>
  Migrations: ✅ N applied
  Services:   ✅ all healthy
  Endpoints:  API, UI, Docs URLs
```
