---
command: rollback
description: "Roll back a deployment to the previous known-good build and validate health. Code only: the schema stays, because migrations are forward-only and N-1 compatible. Reversing a migration is a separate, explicit, human-confirmed step that exists for local only."
arguments:
  - name: target
    required: true
    description: "Deployment target to roll back: local | dev | qa | staging | prod  (dev/qa = lab Kubernetes cluster; staging/prod = Amazon EKS, human or CI only)"
  - name: confirm
    required: false
    default: false
    description: "Required for production rollbacks. Prevents accidental prod rollbacks."
  - name: reverse_schema
    required: false
    default: false
    description: "local only: after the code rollback, offer to run the DOWN migrations newer than the rolled-back build — shown first, run only after the human confirms. Refused for every other target."
---

# /rollback — Deployment Rollback

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

Rolls back a deployment to the previous known-good state: identifies the last HEALTHY deploy from the
recorded deploy history, **redeploys that build first**, and validates health. The schema is not
reversed. Migrations are expand/contract and N-1 compatible (`migration_agent`), so the previous
build runs on the current schema; reversing the schema first would break the code that is still
serving and can drop data written since the deploy.

**Safety:** Production rollbacks ALWAYS require `--confirm`. This is non-negotiable.

---

## Targets `dev` and `qa` (lab Kubernetes cluster)

For projects with `deploy/k8s/app.env`, rollback is one script call and needs no confirmation (the
environments are disposable and the previous state is recorded):

```bash
case "${ARG_TARGET}" in dev|qa)
  scripts/k8s/deploy.sh "${ARG_TARGET}" --rollback; RC=$?
  tail -1 "agent_state/deploy/${ARG_TARGET}/history.jsonl"; exit $RC ;;
esac
```

It redeploys the newest earlier HEALTHY deploy of that env whose digests differ (from
`agent_state/deploy/<env>/history.jsonl`), then re-runs migrate/seed, rollout, smoke and digest
parity, and records the result with `mode: rollback`. **Schema is not reversed.** Migrations are
forward-only. If the old code can't run on the new schema, fix forward, or `env-reset.sh <env>`
for a clean database. Steps 0–5 below are for local/staging/prod.

---

## Step 0 — Safety gate and deploy history

```bash
TARGET=${ARG_TARGET}
if [ "$TARGET" = "prod" ] && [ "${ARG_CONFIRM}" != "true" ]; then
  echo "⛔ Production rollback requires --confirm flag"
  echo ""
  echo "  /rollback --target=prod --confirm"
  echo ""
  echo "  This will:"
  echo "    1. Redeploy the previous HEALTHY build recorded for prod"
  echo "    2. Run health checks"
  echo "  It will NOT change the database schema."
  exit 1
fi
if [ "${ARG_REVERSE_SCHEMA}" = "true" ] && [ "$TARGET" != "local" ]; then
  echo "⛔ --reverse_schema is local only. For $TARGET: fix forward, or restore from a verified backup (a human operation)."
  exit 1
fi
```

Read the recorded history — never a file nothing writes:
1. `agent_state/deploy/${TARGET}/history.jsonl` — one JSON line per deploy (`ts`, `git_sha`, image refs
   or digests, `status`). The current deploy is the newest line; the rollback target is the newest
   earlier line with `status: HEALTHY` whose images differ.
2. Otherwise, the deploy platform's own release history for staging/prod (the previous release or
   revision recorded by the platform named in IMPLEMENTATION_GUIDELINES §11).
3. Otherwise, git tags `deploy-${TARGET}-*` if the project creates them.

If none of these names a previous HEALTHY build:
```
⛔ No previous HEALTHY deploy recorded for ${TARGET}
   Cannot roll back — there is no known-good state to roll back to.

   Options:
     1. Fix forward: /diagnose --symptom="<describe the problem>" then /hotfix
     2. Redeploy a specific commit you know is good: /deploy --target=${TARGET} from that commit
```

```
Rollback plan:
  Target:         ${TARGET}
  Current deploy: ${CURRENT_SHA} (${CURRENT_TS})  images: ${CURRENT_IMAGES}
  Rollback to:    ${PREVIOUS_SHA} (${PREVIOUS_TS}) images: ${PREVIOUS_IMAGES}
  Schema:         unchanged (forward-only migrations)
```

---

## Step 1 — Check the previous build can run on the current schema

```bash
git cat-file -e "${PREVIOUS_SHA}^{commit}" 2>/dev/null || { echo "⛔ ${PREVIOUS_SHA} not in git history — deploy state is corrupted; manual intervention"; exit 1; }
# Migrations added since the previous build:
git diff --name-only --diff-filter=A "${PREVIOUS_SHA}" "${CURRENT_SHA}" -- migrations/
```
For each migration listed, read its header and `migrations/registry.yaml`: every one should say
`n_minus_1_compatible: true`. If any says `false` (a contract step, or an accepted exception), the
previous build may not run on this schema — say so in the plan, and for staging/prod stop and
escalate to a human (fix forward or restore from backup); don't proceed on a guess.

---

## Step 2 — Redeploy the previous build (code first)

### Local
Never check out an older commit over the working tree (it may hold uncommitted work).
```bash
if [ -n "${PREVIOUS_IMAGE}" ] && docker image inspect "${PREVIOUS_IMAGE}" >/dev/null 2>&1; then
  : # the recorded image still exists — run it via a compose override that pins image: ${PREVIOUS_IMAGE}
else
  WT="$(mktemp -d)/rollback-${PREVIOUS_SHA}"
  git worktree add --detach "$WT" "${PREVIOUS_SHA}"          # separate checkout; the working tree is untouched
  docker compose -f "$WT/docker-compose.yml" build
fi
docker compose up -d --no-deps <app services>                 # the datastore keeps running; no volume is touched
```
Remove the temporary worktree afterwards (`git worktree remove "$WT"`).

### Staging / Production
**Amazon EKS projects** (`deploy/k8s/overlays/<env>/eks.env`, skill `infrastructure/eks.md`) are
human or CI only, like `/deploy`. The guard refuses agents. Print the steps and stop:
- **CI:** revert the promotion commit (the one that changed `deploy/k8s/overlays/<env>/`). The
  deploy-eks workflow redeploys the previous digests. For prod, a reviewer approves the run in the
  protected `prod` environment.
- **By hand:** `EKS_KUBECONFIG=<kubeconfig> scripts/k8s/deploy.sh <env> --rollback`. It picks the newest
  earlier HEALTHY deploy in `agent_state/deploy/<env>/history.jsonl` and pins the overlay to it, so
  commit that change afterwards. Prod asks for the typed `<app>-prod@<sha>` again.

Other platforms: redeploy the previous release's recorded image digests (or the platform's previous
revision) with the platform named in IMPLEMENTATION_GUIDELINES §11. Either way no `migrate` step runs:
the schema stays.

Wait for the runtime contract's probes:
```bash
for i in $(seq 1 12); do
  curl -sf "${BASE_URL}/healthz" >/dev/null 2>&1 && curl -sf "${BASE_URL}/readyz" >/dev/null 2>&1 && break
  sleep 5
done
```

---

## Step 3 — Health Check

Reuse the post-deploy health validation from `/deploy` Step 5:

1. **Probes** — `/healthz` and `/readyz` return 200; the version route reports `${PREVIOUS_SHA}`.
2. **Endpoint health check** — curl every route in the phase manifest's `api_routes[]`
   - GET endpoints: verify 200 status + response has expected shape
   - Authenticated endpoints: use test credentials from seed data (never production credentials)
   - Timeout: 10s per endpoint
3. **Contract shape validation** — every response matches the envelope (`~/.claude/skills/api/response-envelope.md`) and `data-contracts.md`; flag any CONTRACT_VIOLATION.
4. **Performance baseline** — record p95 response times per endpoint; compare with the pre-rollback baseline if available.

```
Health check results:
  Probes:     /healthz 200 · /readyz 200 · git_sha ${PREVIOUS_SHA}
  Endpoints:  N/N healthy
  Contracts:  N/N valid
  Performance: within baseline | degraded (expected for older version)
```

---

## Step 4 — Reverse schema (local only, explicit, human-confirmed)

Runs only when `--reverse_schema` was passed, `TARGET` is `local`, and the code rollback in Step 2 is
healthy. It never runs automatically and never runs for dev, qa, staging or prod.

1. List the migrations added after `${PREVIOUS_SHA}` (Step 1), newest first, and the DOWN file for
   each. A migration marked `forward-only` has no DOWN: stop — the only local options are to keep
   the schema or reset the local database with the project's documented reset for local dev.
2. Show the list and the command that would run (the tool's one-step-down command, e.g.
   `goose down`, `migrate down 1`, `alembic downgrade -1`), and ask the human to confirm each step.
   Never use a command that drops and recreates the database.
3. Run the confirmed steps one at a time with the local database URL; stop at the first failure and
   report the partial state.

---

## Step 5 — Update State and Report

### If health passes:

Append the rollback to the deploy history and write the marker `/accept` and `/status` read:
```bash
mkdir -p "agent_state/deploy/${TARGET}"
printf '%s\n' "{\"ts\":\"${TS}\",\"target\":\"${TARGET}\",\"mode\":\"rollback\",\"git_sha\":\"${PREVIOUS_SHA}\",\"from_sha\":\"${CURRENT_SHA}\",\"images\":${PREVIOUS_IMAGES_JSON},\"status\":\"HEALTHY\",\"schema_reversed\":${SCHEMA_REVERSED:-false}}" \
  >> "agent_state/deploy/${TARGET}/history.jsonl"
printf '%s\n' "{\"target\":\"${TARGET}\",\"status\":\"HEALTHY\",\"mode\":\"rollback\",\"git_sha\":\"${PREVIOUS_SHA}\",\"ts\":\"${TS}\"}" \
  > agent_state/deploy/last-deploy-status.json
```

```
✅ Rollback complete — ${TARGET}

  From:   ${CURRENT_SHA} (${CURRENT_TS})
  To:     ${PREVIOUS_SHA} (${PREVIOUS_TS})
  Schema: unchanged${SCHEMA_REVERSED:+ (local: N DOWN steps confirmed and run)}
  Health: ✅ probes and endpoints healthy

  History: agent_state/deploy/${TARGET}/history.jsonl

  ⚠ The rolled-back code is now deployed. To fix forward:
    /diagnose --symptom="<what caused the rollback>"
    /hotfix --phase=N --component=<component> --description="<fix>"
    /deploy --target=${TARGET}
```

### If health fails:

```
⛔ Rollback health check FAILED

  Rolled back to: ${PREVIOUS_SHA}
  Failing checks: [list]
  Errors: [details]

  The system is in a degraded state. Manual intervention required:

  Options:
    1. Check logs: docker compose logs <service> (local) or the platform's logs
    2. Roll back further: the next older HEALTHY entry in agent_state/deploy/${TARGET}/history.jsonl
    3. Restore from a verified backup (human operation) if data was affected
    4. Investigate: /diagnose --symptom="<health check failures>"

  ⚠ DO NOT run additional automated rollbacks without understanding the failure.
```
Write the DEGRADED marker (`last-deploy-status.json` with `status: DEGRADED`) so `/accept` and
`/status` surface it.

---

## Rules

- **NEVER auto-rollback production** — always require `--confirm`
- **Code first, schema never (automatically):** redeploy the previous build; DOWN migrations run only
  in Step 4, for `local`, after an explicit human confirmation of each step
- **Never a destroy-and-recreate command** (a reset that drops the database) in any rollback path
- **Read the recorded deploy history,** not files nothing writes; refuse when no previous HEALTHY deploy is recorded
- **Never check out an old commit over the working tree** — build it in a separate worktree or reuse its recorded image
- Health checks after rollback use the same validation as `/deploy`, on `/healthz` + `/readyz`
- Every rollback is appended to `agent_state/deploy/<target>/history.jsonl` — full audit trail
- Rollback is not a fix — it buys time. Always follow up with `/diagnose` + `/hotfix` or `/develop`
