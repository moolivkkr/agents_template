---
command: rollback
description: "Roll back a deployment to the previous known-good state. Reverses migrations, redeploys previous build, and validates health."
arguments:
  - name: target
    required: true
    description: "Deployment target to roll back: local | staging | prod"
  - name: confirm
    required: false
    default: false
    description: "Required for production rollbacks. Prevents accidental prod rollbacks."
---

# /rollback — Deployment Rollback

Rolls back a deployment to the previous known-good state. Identifies the last successful deploy, reverses any migrations applied since then, redeploys the previous build, and validates health.

**Safety:** Production rollbacks ALWAYS require `--confirm`. This is non-negotiable.

---

## Step 0 — Read Last Deploy Manifest

```bash
TARGET=${ARG_TARGET}
```

### Production safety gate
```bash
if [ "$TARGET" = "prod" ] && [ "${ARG_CONFIRM}" != "true" ]; then
  echo "⛔ Production rollback requires --confirm flag"
  echo ""
  echo "  /rollback --target=prod --confirm"
  echo ""
  echo "  This will:"
  echo "    1. Reverse migrations applied in the last deploy"
  echo "    2. Redeploy the previous build"
  echo "    3. Run health checks"
  echo ""
  echo "  Make sure you understand the impact before confirming."
  exit 1
fi
```

Read the deploy state:
```bash
DEPLOY_STATE="agent_state/deploy/"
```

From the deploy state, identify:
- **Current deploy:** timestamp, git SHA, image tag, migrations applied
- **Previous deploy:** timestamp, git SHA, image tag (the rollback target)

If no previous deploy exists:
```
⛔ No previous deploy found in agent_state/deploy/
   Cannot roll back — there is no known-good state to roll back to.

   Options:
     1. Fix the issue manually
     2. /diagnose --symptom="<describe the problem>"
```

```
Rollback plan:
  Target:           ${TARGET}
  Current deploy:   ${CURRENT_SHA} (${CURRENT_TIMESTAMP})
  Rollback to:      ${PREVIOUS_SHA} (${PREVIOUS_TIMESTAMP})
  Migrations to reverse: [list or "none"]
```

---

## Step 1 — Identify Previous Good State

Find the git tag from the last successful deployment:

```bash
# Look for deploy tags
PREVIOUS_TAG=$(git tag -l "deploy-${TARGET}-*" | sort -r | sed -n '2p')

# If no deploy tags, use the SHA from deploy state
if [ -z "$PREVIOUS_TAG" ]; then
  PREVIOUS_SHA=$(cat agent_state/deploy/previous-sha.txt 2>/dev/null)
fi
```

Verify the previous state is valid:
```bash
# Check that the commit exists
git cat-file -t "${PREVIOUS_SHA}" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "⛔ Previous deploy SHA ${PREVIOUS_SHA} not found in git history"
  echo "  Deploy state may be corrupted. Manual intervention required."
  exit 1
fi
```

```
Rollback target:
  SHA:   ${PREVIOUS_SHA}
  Tag:   ${PREVIOUS_TAG:-none}
  Date:  ${PREVIOUS_TIMESTAMP}
```

---

## Step 2 — Reverse Migrations

Check if any database migrations were applied in the current deploy:

```bash
# Read migration state from deploy manifest
MIGRATIONS_APPLIED=$(cat agent_state/deploy/last-migrations.json 2>/dev/null)
```

### If migrations were applied:

**Agent:** Generated `migration_agent`

```bash
# Run DOWN migrations for each migration applied in the current deploy (reverse order)
# e.g. goose down, flyway undo, alembic downgrade, prisma migrate reset
```

**Dry run first:**
```
Migrations to reverse:
  1. 003_add_user_preferences.sql (DOWN)
  2. 002_add_analytics_table.sql (DOWN)

Confirm reversal? [auto-confirmed for local, requires --confirm for prod]
```

For local target: proceed automatically.
For staging: proceed with warning.
For prod: require `--confirm` (already checked in Step 0).

### Migration Reversal Failure

If DOWN migration fails:
```
⛔ Migration reversal failed

  Failed migration: ${MIGRATION_FILE}
  Error: ${ERROR_MESSAGE}

  The database is in a partially rolled-back state.
  DO NOT proceed with redeployment.

  Manual intervention required:
    1. Check database state: <connection command>
    2. Review failed migration: ${MIGRATION_FILE}
    3. Apply manual fix or restore from backup
```

**STOP — do not continue if migration reversal fails.**

### If no migrations to reverse:
```
No migrations to reverse — proceeding to redeploy.
```

---

## Step 3 — Redeploy Previous Build

### Local
```bash
# Checkout previous version
git checkout "${PREVIOUS_SHA}"

# Rebuild
docker compose build

# Restart services
docker compose down
docker compose up -d

# Return to main branch (keep deployment on previous version)
git checkout main
```

### Staging / Production
```bash
# Use the previous image tag
docker compose -f docker-compose.${TARGET}.yml up -d --force-recreate
# Or equivalent orchestration command from IMPLEMENTATION_GUIDELINES
```

Wait for services to start:
```bash
for i in $(seq 1 12); do
  curl -sf http://localhost:<PORT>/health > /dev/null 2>&1 && break
  sleep 5
done
```

---

## Step 4 — Health Check

Reuse the post-deploy health validation from `/deploy` Step 5:

1. **Endpoint health check** — curl every route in the phase manifest's `api_routes[]`
   - GET endpoints: verify 200 status + response has expected shape
   - Authenticated endpoints: use test credentials from seed data
   - Timeout: 10s per endpoint

2. **Contract shape validation** — for each endpoint response:
   - Compare against `data-contracts.md` TypeScript interfaces
   - Verify list endpoints return arrays, single endpoints return objects
   - Flag any CONTRACT_VIOLATION

3. **Performance baseline** — record p95 response times per endpoint
   - Compare against pre-rollback baseline if available
   - Verify rolled-back version performs within acceptable range

```
Health check results:
  Endpoints:  N/N healthy
  Contracts:  N/N valid
  Performance: within baseline | degraded (expected for older version)
```

---

## Step 5 — Update State and Report

### If health passes:

Update deploy state:
```bash
# Record rollback in deploy state
cat > agent_state/deploy/rollback-${TIMESTAMP}.json << EOF
{
  "timestamp": "${TIMESTAMP}",
  "target": "${TARGET}",
  "rolled_back_from": "${CURRENT_SHA}",
  "rolled_back_to": "${PREVIOUS_SHA}",
  "migrations_reversed": [${MIGRATION_LIST}],
  "health_check": "PASS",
  "reason": "manual rollback via /rollback"
}
EOF
```

Tag the rollback:
```bash
git tag "rollback-${TARGET}-${TIMESTAMP}" -m "Rollback on ${TARGET}: ${CURRENT_SHA} → ${PREVIOUS_SHA}"
```

```
✅ Rollback complete — ${TARGET}

  From:       ${CURRENT_SHA} (${CURRENT_TIMESTAMP})
  To:         ${PREVIOUS_SHA} (${PREVIOUS_TIMESTAMP})
  Migrations: ${N} reversed
  Health:     ✅ all endpoints healthy

  State: agent_state/deploy/rollback-${TIMESTAMP}.json
  Tag:   rollback-${TARGET}-${TIMESTAMP}

  ⚠ The rolled-back code is now deployed. To fix forward:
    /diagnose --symptom="<what caused the rollback>"
    /hotfix --phase=N --component=<component> --description="<fix>"
    /deploy --target=${TARGET}
```

### If health fails:

```
⛔ Rollback health check FAILED

  Rolled back to: ${PREVIOUS_SHA}
  Failing endpoints: [list]
  Errors: [details]

  The system is in a degraded state. Manual intervention required:

  Options:
    1. Check logs: docker logs <container>
    2. Try an older version: /rollback with a different target SHA
    3. Restore from backup (if database was affected)
    4. Investigate: /diagnose --symptom="<health check failures>"

  ⚠ DO NOT run additional automated rollbacks without understanding the failure.
```

---

## Rules

- **NEVER auto-rollback production** — always require `--confirm` flag
- **NEVER skip migration reversal** — data integrity depends on schema matching code
- **STOP on migration failure** — a half-rolled-back database is worse than a broken deploy
- Health checks after rollback use the same validation as `/deploy` — consistency matters
- Every rollback is recorded in `agent_state/deploy/` and tagged in git — full audit trail
- Rollback is not a fix — it buys time. Always follow up with `/diagnose` + `/hotfix` or `/develop`
- If the previous deploy state is unknown or corrupted, refuse to rollback — manual intervention is safer than guessing
