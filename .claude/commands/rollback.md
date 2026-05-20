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

Rolls back to previous known-good state: identify last deploy → reverse migrations → redeploy previous build → validate health.

**Production rollbacks ALWAYS require `--confirm`.**

---

## Step 0 — Read Last Deploy Manifest

```bash
TARGET=${ARG_TARGET}
if [ "$TARGET" = "prod" ] && [ "${ARG_CONFIRM}" != "true" ]; then
  echo "⛔ Production rollback requires --confirm flag"
  echo "  /rollback --target=prod --confirm"
  exit 1
fi
```

From `agent_state/deploy/`, identify current deploy (SHA, image tag, migrations) and previous deploy (rollback target). No previous deploy → STOP with manual fix options.

---

## Step 1 — Identify Previous Good State

```bash
PREVIOUS_TAG=$(git tag -l "deploy-${TARGET}-*" | sort -r | sed -n '2p')
[ -z "$PREVIOUS_TAG" ] && PREVIOUS_SHA=$(cat agent_state/deploy/previous-sha.txt 2>/dev/null)
git cat-file -t "${PREVIOUS_SHA}" > /dev/null 2>&1 || { echo "⛔ SHA not found"; exit 1; }
```

---

## Step 2 — Reverse Migrations

Check `agent_state/deploy/last-migrations.json` for migrations applied in current deploy.

**If migrations exist:** `migration_agent` runs DOWN migrations in reverse order. Dry run shown first. Local → auto-proceed. Staging → warning. Prod → requires `--confirm`.

**Migration failure → STOP immediately.** Partially rolled-back DB is worse than broken deploy. Surface error + manual fix instructions.

**No migrations → proceed to redeploy.**

---

## Step 3 — Redeploy Previous Build

### Local
```bash
git checkout "${PREVIOUS_SHA}"
docker compose build
docker compose down && docker compose up -d
git checkout main
```

### Staging / Production
```bash
docker compose -f docker-compose.${TARGET}.yml up -d --force-recreate
```

Wait for health (poll every 5s, max 60s).

---

## Step 4 — Health Check

Reuse `/deploy` Step 5 validation:
1. **Endpoint health** — curl every route in manifest's `api_routes[]`, verify status + shape
2. **Contract validation** — compare against `data-contracts.md` interfaces
3. **Performance baseline** — record p95, compare against pre-rollback if available

---

## Step 5 — Update State and Report

### Health passes:
Write rollback record to `agent_state/deploy/rollback-${TIMESTAMP}.json`. Tag: `rollback-${TARGET}-${TIMESTAMP}`.

```
✅ Rollback complete — ${TARGET}
  From: ${CURRENT_SHA} → To: ${PREVIOUS_SHA}
  Migrations: ${N} reversed | Health: all endpoints healthy

  ⚠ To fix forward:
    /diagnose → /hotfix → /deploy --target=${TARGET}
```

### Health fails:
```
⛔ Rollback health check FAILED
  Failing endpoints: [list]
  Manual intervention required. DO NOT run additional automated rollbacks.
```

---

## Rules

- **NEVER auto-rollback production** — always require `--confirm`
- **NEVER skip migration reversal** — schema must match code
- **STOP on migration failure** — half-rolled-back DB is dangerous
- Health checks use same validation as `/deploy`
- Every rollback recorded in `agent_state/deploy/` and tagged in git
- Rollback buys time — always follow up with `/diagnose` + `/hotfix` or `/develop`
- Unknown/corrupted deploy state → refuse to rollback, manual intervention safer
