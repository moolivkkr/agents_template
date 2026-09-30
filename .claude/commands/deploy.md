---
command: deploy
description: Deploy the application. Reads IMPLEMENTATION_GUIDELINES for infra config. Supports local (compose), dev/qa (lab Kubernetes cluster), staging, and production targets.
arguments:
  - name: target
    required: false
    default: local
    description: "Deployment target: local | ha-local | dev | qa | staging | prod  (dev/qa = the Lima k3s lab cluster)"
  - name: failover_test
    required: false
    default: false
    description: "Run failover test suite after HA deployment (requires --target=ha-local)"
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

## Targets `dev` and `qa` — the Kubernetes lab cluster

For projects with `deploy/k8s/app.env`, `--target=dev|qa` deploys to the namespaces `<app>-dev` and
`<app>-qa` on the lab cluster (skill: `infrastructure/lima-k8s-lab.md`). One script does build,
push, migrate, seed, rollout, smoke and evidence, so **Steps 1–5 below do not apply** to these
targets. Agents run it unattended; the permission guard and RBAC confine it to the app's namespaces.

```bash
TARGET=${ARG_TARGET:-local}
case "$TARGET" in dev|qa)
  [ -f deploy/k8s/app.env ] || { echo "no deploy/k8s/ — deployment_agent instantiates it first (Step 3g)"; exit 1; }
  PHASE="${ARG_PHASE:-}" scripts/k8s/deploy.sh "$TARGET"; RC=$?     # PHASE set → gate sidecar
  cat agent_state/deploy/last-deploy-status.json
  exit $RC ;;
esac
```

| | `dev` | `qa` |
|---|---|---|
| Images | built from the working tree, pushed to `localhost:5001`, pinned **by digest** | **promoted**: the newest HEALTHY dev deploy's digests, never rebuilt |
| Data | own Postgres (PVC) per env; migrate Job then seed Job (static reference data, idempotent) on every deploy | same, separate database |
| URL | `http://<app>-dev.localhost:18080` | `http://<app>-qa.localhost:18080` |
| Verdict | HEALTHY / DEGRADED / FAILED; exit 0 only when HEALTHY | + running pods' image IDs must equal the promoted digests |

- **Evidence (written by the script, not by prose):** `agent_state/deploy/<env>/history.jsonl`,
  `agent_state/deploy/last-deploy-status.json` (read by `/accept` and `/status`), and with `--phase=N`
  `agent_state/phases/N/reports/deploy_verification.json` for the phase gate.
- **Reset** (approved, no prompt): `scripts/k8s/env-reset.sh <env>` wipes workloads and volumes, keeps
  the namespace, redeploys (dev: same digests; qa: re-promote) and re-seeds.
- **Rollback:** `scripts/k8s/deploy.sh <env> --rollback` (newest earlier HEALTHY digests; schema is
  forward-only). `/rollback --target=dev|qa` calls it.
- **Human-only (the guard denies agents):** creating the cluster (`cluster-up.sh`), creating an app's
  namespaces (`app-namespaces.sh <app>`), anything with the admin kubeconfig. If the namespace is
  missing, stop and ask for `app-namespaces.sh <app>`; do not try to create it.
- **Failure handling:** read the log lines the script prints (it fails fast with the pod's exact
  reason, e.g. `CreateContainerConfigError`, `ImagePullBackOff`, a migrate error); fix the cause;
  re-run. A DEGRADED dev deploy blocks promotion to qa.

---

## Step 0 — Pre-flight Checks

```bash
TARGET=${ARG_TARGET:-local}
echo "▶ Deploying to: $TARGET"
```

Read `docs/IMPLEMENTATION_GUIDELINES.md` §1 (Tech Stack), §3 (Component Inventory), §5 (Local Dev Environment).

### 0a: Service Discovery (DYNAMIC)

Read §3 Component Inventory and classify each service:
- **Stateless** (replicate per region): frontends, APIs, workers
- **Stateful** (per-region or replicated): databases, caches
- **Shared** (single instance): observability, infrastructure

Output: service topology table in deployment report.

### 0b: Port Allocation

Assign ports from `DEPLOY_PORT_BASE` (default 30000) with +5 increments:
- Region 1: base+0, base+5, base+10, ...
- Region 2 (HA only): base+15, base+20, base+25, ...
- Shared: base+30, base+35, ...

### 0c: Gate Check (non-local targets only)

- Latest phase gate must be passed: `agent_state/phases/*/gate.passed`
- All tests must be green: check latest test results
- No HIGH security findings outstanding
- For HA: verify both regions' health endpoints are configured

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
docker compose up -d
```

### Local Dev (with hot reload)
```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

### HA Local (multi-region with Route 53)
```bash
docker compose -f docker-compose.yml -f docker-compose.ha.yml up -d
# Wait for ALL regions healthy
# Verify Route 53 records + health checks
# If --failover-test: run scripts/failover-test.sh
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

## Step 4d — Reliability / SLO Validation (staging or prod)

**Agent:** `reliability_agent`
**When:** Deploying to staging or prod (`TARGET != local`) AND the project has SLOs defined (a prior
`/plan` Step 3b produced `reliability_review.md`, or NFR-PERF-*/availability targets exist).

Validates the DEPLOYED system against the SLIs/SLOs and error budgets it defined at design time:
health/readiness/liveness endpoints respond correctly, timeout/retry/circuit-breaker behavior is
active, and the SLO measurement (metrics/probes) is wired. Confirms runbook stubs exist for the
top failure modes.

Output: `agent_state/reports/reliability_validation.md` (+ `.json`). BLOCKING findings cap release
readiness at NOT READY (same treatment as an unhealthy deploy).

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
   - **Write a durable status marker so the DEGRADED verdict propagates:**
     ```bash
     mkdir -p agent_state/deploy
     echo "{\"target\":\"${TARGET}\",\"status\":\"DEGRADED\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"failing\":\"<endpoints>\"}" \
       > agent_state/deploy/last-deploy-status.json
     ```

### Health is a gate, not just a signal

An unhealthy deploy must not silently be treated as "done." Enforce by target:

- **`--target=staging` or `--target=production`:** an unhealthy deploy is a HARD STOP.
  `exit 1` after writing the DEGRADED marker and rollback recommendation. Do NOT report the deploy
  as successful. A degraded prod deploy is an incident, not a warning.
- **`--target=local`:** surface DEGRADED and write the marker, but you may proceed (local iteration).
  The marker is what makes it non-silent: `/accept` reads `last-deploy-status.json` and caps release
  readiness at NOT READY when status is DEGRADED (accept.md Step 0a), and `/status` surfaces it under
  OPEN ISSUES. So "proceed locally" never becomes "shipped unnoticed."

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
