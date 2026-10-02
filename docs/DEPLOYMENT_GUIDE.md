# Deployment Guide: local, lab dev/qa, EKS staging/prod

This guide covers where a project built with the framework runs, how a build moves from one environment to the
next, who is allowed to run each step, how the database roles work, and how to roll back. It summarises; the
sources of truth are:

| Topic | Source |
|---|---|
| `/deploy` and `/rollback` | `.claude/commands/deploy.md`, `.claude/commands/rollback.md` |
| Lab cluster (dev/qa) | `.claude/skills/infrastructure/lima-k8s-lab.md`, templates in `.claude/templates/k8s/` |
| EKS (staging/prod) | `.claude/skills/infrastructure/eks.md`, templates in `.claude/templates/k8s/eks/` |
| Migrator policy (D-001) | `docs/DECISIONS.md` D-001, `.claude/skills/databases/postgres.md` "The migrator policy" |
| EKS compute (D-003) | `docs/DECISIONS.md` D-003 (EKS Auto Mode) |
| Agent permissions | `docs/PERMISSIONS_GUIDE.md`, `.claude/guard/sdlc-guard.sh` |

## 1. Targets at a glance

| Target | Runs on | Who deploys | Images | Database | URL |
|---|---|---|---|---|---|
| `local` (`ha-local`) | Docker Compose on your machine | agent or you | built locally | the compose Postgres | `http://localhost:<port>` |
| `dev` | lab k3s cluster, namespace `<app>-dev` | agent (unattended) | built from the working tree, pushed to `localhost:5001` by digest | own Postgres StatefulSet | `http://<app>-dev.localhost:18080` |
| `qa` | lab cluster, namespace `<app>-qa` | agent (unattended) | **promoted**: the newest HEALTHY dev digests, never rebuilt | own Postgres, separate from dev | `http://<app>-qa.localhost:18080` |
| `staging` | Amazon EKS (Auto Mode), one cluster per env | **human or CI only** | qa's digests copied into ECR (same digest) | RDS for PostgreSQL, single-AZ | `https://<APP_HOST>` (ALB + ACM) |
| `prod` | Amazon EKS, its own cluster/VPC/database | **human or CI only**, confirmed every time | only digests ECR tagged `staging-healthy-<sha>` | RDS Multi-AZ, deletion protection | `https://<APP_HOST>` |

`/startup:deploy --target=<target>` (default `local`). For `dev`/`qa` it runs `scripts/k8s/deploy.sh <env>`. For
`staging`/`prod` it does not deploy: it prints the human steps and stops (`deploy.md`, "Targets `staging` and
`prod`").

## 2. What each target needs

Run `~/.claude/scripts/startup/capability-check.sh` (also printed by `install.sh`) to see which of these tools
this machine has.

| Target | Tools | One-time setup |
|---|---|---|
| `local` | Docker (Compose) | none |
| `dev` / `qa` | `kubectl` (kustomize is built in), `crane` (pushes to the lab registry: Docker Desktop can't reach host loopback), `docker` (builds), `python3`, `git`; the agent kubeconfig `~/.kube/sdlc-lab.json` | **Human:** `cluster-up.sh` (VMs, registry, RBAC, agent kubeconfig, guard policy; needs `limactl`), then `app-namespaces.sh <app>` per app. **Agent:** `instantiate.sh . <app>` copies the deploy layer into the project, then `deployment_agent` adapts it |
| `staging` / `prod` | `terraform` ≥ 1.11 (or `tofu`), `aws`, `kubectl`, `crane`, `helm` (bootstrap only); GitHub Environments for CI | **Human:** state bucket, `terraform apply` per env, `eks-outputs.sh <env>` → commit `eks.env`, `eks-bootstrap.sh <env>`, GitHub Environments `staging` and `prod` (prod: required reviewers, restricted to `main`), variable `AWS_DEPLOY_ROLE_ARN`. **Agent:** `instantiate.sh . <app> --eks` and offline validation only |

The full first-time EKS sequence is in `deploy.md` ("First time (human, once)") and `eks.md` ("Who does what").
The cluster scripts live in `~/.claude/templates/k8s/scripts/` after `install.sh`.

## 3. The promotion flow (build once, promote the digest)

```text
dev      deploy.sh dev       build from the working tree → localhost:5001/<app>/<svc>@sha256:D   (agent)
qa       deploy.sh qa        same digest D, never rebuilt; pods' imageIDs must equal D           (agent)
staging  promote-eks.sh staging   crane copy D into ECR (digest unchanged, checked)              (human, on the dev Mac:
                                  → commit overlays/staging/ → CI deploys                         it needs the lab registry)
         deploy-eks.sh: HEALTHY → ECR tag staging-healthy-<sha> on D
prod     promote-eks.sh prod      only digests carrying staging-healthy-<sha>                    (human or CI)
                                  → commit overlays/prod/ → CI deploy in the protected "prod" Environment
```

- The commit that changes `deploy/k8s/overlays/<env>/{kustomization.yaml,promoted-from.json}` is the release
  record. Only `deploylib.py set-images` writes the overlay's images block, and only with digests.
- ECR tags are immutable, so a `staging-healthy-<sha>` tag is trustworthy evidence for promoting to prod.
- Each deploy ends HEALTHY, DEGRADED or FAILED, and exits 0 only on HEALTHY. A DEGRADED dev deploy blocks
  promotion to qa; a staging deploy that isn't HEALTHY never tags its images.
- Evidence, written by the scripts: `agent_state/deploy/<env>/history.jsonl` and
  `agent_state/deploy/last-deploy-status.json` (read by `/accept` and `/status`). With `--phase=N`, also
  `agent_state/phases/N/reports/deploy_<env>.{json,md}` and a `deploy_<env>` line in `execution.jsonl`. On a
  project with `deploy/k8s/app.env`, the phase gate requires HEALTHY `deploy_dev` and `deploy_qa` evidence bound
  to the current commit (`verify-gate.sh` check a2).

## 4. Who may run what

| Action | Agent | Human / CI |
|---|---|---|
| `/deploy --target=local\|dev\|qa`, `deploy.sh dev\|qa`, `env-reset.sh dev\|qa`, `seed.sh`, `smoke.sh` | yes | yes |
| `/rollback --target=dev\|qa` (`deploy.sh <env> --rollback`) | yes | yes |
| Create the cluster (`cluster-up.sh`), app namespaces (`app-namespaces.sh`), anything with the admin kubeconfig | no | yes |
| Write and validate the EKS layer offline: `kubectl kustomize`, `deploylib.py db-access` / `eks-policy --allow-placeholders`, kubeconform, `terraform fmt -check`, `init -backend=false`, `validate`, tflint, actionlint | yes | yes |
| `terraform plan/output/state/test`, `init` with a backend | asks first | yes |
| `terraform apply/destroy/import` | asks first | yes |
| `crane` against a remote registry (ECR) | asks first | yes |
| `deploy-eks.sh`, `promote-eks.sh`, `eks-bootstrap.sh`, `eks-outputs.sh`; `deploy.sh`/`seed.sh`/`env-reset.sh`/`smoke.sh` with `staging` or `prod` | **denied** | yes |
| `/deploy` or `/rollback` with `--target=staging\|prod` | **denied** | yes |
| `aws` without a LocalStack endpoint, `eksctl`, `aws-vault`, `saml2aws`; any kubeconfig other than the pinned lab one | **denied** | yes |

These rules are enforced by `sdlc-guard.sh` (a PreToolUse hook plus PATH shims for `kubectl`, `helm`,
`limactl`, `aws` and `crane`) once you install it with `./install.sh --guard` and apply the settings in
`docs/PERMISSIONS_GUIDE.md`. Without the guard, these rules are only instructions to the agents.
Inside the lab cluster, RBAC limits the agent's ServiceAccount to `admin` in `<app>-dev` and `<app>-qa`.
`tests/sdlc-guard.test.sh` is the guard's table test.

**Prod confirmation.** `deploy-eks.sh prod` accepts a typed `<app>-prod@<sha>` on a terminal, or, in GitHub
Actions, `SDLC_PROD_CONFIRM` equal to that string inside a job in the protected `prod` Environment. GitHub
withholds that job and its OIDC token until a required reviewer approves. Without required reviewers on that
Environment, CI has no human gate.

## 5. Database roles

Every deploy (lab and EKS) runs, in order: `db-roles` Job → `db-migrate` → `db-seed` → `db-rls-check` → rollout
(`scripts/k8s/deploy.sh`, `deploy-eks.sh`). The roles:

| Role | Lab (self-hosted Postgres) | RDS / Aurora (staging, prod) | Used by |
|---|---|---|---|
| Bootstrap | `postgres` superuser | the RDS master user (not a superuser; password managed by RDS in Secrets Manager) | Postgres itself and the `db-roles` Job only |
| `app_migrator` | NOSUPERUSER **BYPASSRLS**, owns the database and every object | NOSUPERUSER **NOBYPASSRLS** (RDS can't grant BYPASSRLS; the Job prints a WARNING), owns everything | `db-migrate`, `db-seed` |
| `app_runtime` | NOSUPERUSER NOBYPASSRLS, owns nothing, DML via default privileges | same | every service, the `db-rls-check` Job |

- `db-roles.sh` converges both roles on every deploy and prints `db-roles: no changes` on a converged database.
  It also converts a volume from the older one-superuser layout.
- On every render, before anything is applied, `deploylib.py db-access` checks who reads which credential. Only
  Postgres and `db-roles` may hold the superuser/master keys. Only the `db-*` Jobs may hold the migrator keys,
  never a Deployment. `db-rls-check` must be present and hold only the app keys. The deploy fails and names the
  container otherwise.
- Lab credentials come from the overlay's gitignored `secrets.env` (rebuilt from the namespace when missing). On
  EKS, the `db-credentials` Secret comes only from the ExternalSecret (External Secrets Operator with Pod
  Identity). No database password is in Terraform state, a plan, git or a manifest (write-only arguments,
  Terraform 1.11+).

### The migrator policy (D-001)

On RDS the migrator is NOBYPASSRLS. Under `FORCE ROW LEVEL SECURITY` it would see no tenant's rows, so
migrations, backfills and seeds would silently touch 0 rows. Decision D-001 fixes that the same way on both paths:

- The project's first migration creates the helper `app_grant_migrator(tbl regclass)`.
- Every migration that creates a FORCE-RLS tenant table ends with `SELECT app_grant_migrator('<table>');`. This
  creates a permissive policy `<table>_migrator_all ... TO <table owner> USING (true) WITH CHECK (true)`.
- The runtime role is neither the owner nor a member of it, so it still gets only the tenant policy. On the lab
  the policy is redundant with BYPASSRLS and harmless, so a migration written for dev runs unchanged on staging
  and prod.
- Never write `TO PUBLIC`, `TO app_runtime` or a typed role name in an unconditional policy. Never lift `FORCE`
  in a data migration: it takes an `ACCESS EXCLUSIVE` lock.

The SQL is in `databases/postgres.md`, the migration archetypes, and the TypeScript (Prisma, Drizzle), Java
(Flyway), Python and Go archetypes. `migration_safety_reviewer` (Check 7) and `tenant_isolation_verifier`
(Step 7) review for it.

**The `db-rls-check` Job** runs as the app role after migrate and seed, before the rollout. The deploy fails if:
- a FORCE-RLS table has no migrator policy;
- an unconditional policy names any role other than the table owner;
- the app role can read any row with no tenant set.

### Adopting D-001 in an existing project

1. **Schema.** Add one new migration that creates the helper and calls `app_grant_migrator()` for every FORCE-RLS
   table that lacks the policy. Never edit an applied migration (`postgres.md`, "Existing schema").
2. **Deploy layer.** `instantiate.sh` never overwrites existing files ("kept"), and the project updater
   (`startup-project-update.sh`) only touches `.claude/hooks/`, `.claude/settings.json`, `.gitignore` and the
   graph, not `deploy/` or `scripts/`. A project instantiated before 2026-10-01 therefore keeps its old
   `scripts/k8s/` and has no `db-rls-check` Job. Bring it up to date by hand from
   `~/.claude/templates/k8s/app/`:
   - copy `scripts/k8s/*` (they are shared and meant to stay unedited);
   - add `deploy/k8s/base/db-rls-check.sh`, the `db-rls-check` entry in `base/kustomization.yaml` and the
     `db-rls-check` template in `base/jobs.yaml`.

   Then run `deploy.sh dev`. The current `deploylib.py db-access` refuses a render without the Job.
3. Deploy dev, then promote to qa. A missing policy now fails the `rls` step instead of a silent 0-row backfill.

## 6. Rollback

Rollback redeploys the previous HEALTHY build's digests. **It never reverses the schema.** Migrations are
forward-only and N-1 compatible (expand/contract), so the previous build runs on the current schema.

| Target | How | Confirmation |
|---|---|---|
| `local` | `/rollback --target=local`, from `agent_state/deploy/local/history.jsonl`; `--reverse_schema` offers the DOWN migrations afterwards, shown first and run only after you confirm | none (schema reversal: yes) |
| `dev`, `qa` | `/rollback --target=dev\|qa` → `deploy.sh <env> --rollback` (the newest earlier HEALTHY deploy whose digests differ), then migrate/seed, rollout, smoke, digest parity | none |
| `staging`, `prod` | CI: revert the promotion commit, and the workflow redeploys the previous digests (prod: a reviewer approves the run). By hand: `EKS_KUBECONFIG=… scripts/k8s/deploy.sh <env> --rollback` | prod asks again |

If the old code can't run on the new schema, fix forward. On dev/qa you can also run `env-reset.sh <env>` for a
clean database (wipes workloads and volumes, keeps the namespace, redeploys, re-seeds). Restoring staging/prod
data from a backup is a human operation.

## 7. What is verified, and what isn't

| Area | Verified | How |
|---|---|---|
| Lab templates, scripts, overlays | yes, offline | `tests/k8s-templates.test.sh` (in `run-all.sh`) |
| Lab deploy on the live cluster: build, digest promotion, isolation, guard, reset, rollback | yes, live, on 2026-09-30 (23/23, then 31/31 checks), **before** the two database roles were added | `tests/k8s-e2e.sh` (needs the lab cluster, ~3 min; not in `run-all.sh`) |
| Two roles on the live cluster | **not recorded**: the 40-check `k8s-e2e.sh` that asserts them was waiting for the lab (board review 2026-09-30) | `tests/k8s-e2e.sh` |
| Two roles + D-001 migrator policy, lab mode | yes, on throwaway local Postgres 17 | `tests/k8s-db-roles.sh` (Docker or a local Postgres; not in `run-all.sh`) |
| Two roles + D-001 policy, RDS mode | on **stock PostgreSQL 17 set up like RDS** (master NOSUPERUSER, migrator NOBYPASSRLS), not on RDS | `tests/eks-db-roles.sh` (Docker; not in `run-all.sh`) |
| EKS layer: renders, schemas, policies (digests only, no Secret, PDB + zone spread, no placeholders), prod gates in `deploy-eks.sh` with fake kubectl/crane, Terraform fmt/validate, workflow lint | yes, offline | `tests/eks-templates.test.sh` (in `run-all.sh`; downloads Terraform providers and kubeconform schemas on first run) |
| `db-rls-check` Job on the live lab cluster | **not recorded**: `k8s-e2e.sh` does not assert it, and no live run after the D-001 change (2026-10-01) is recorded in the repo | — |
| Anything against real AWS | **never run**: no `terraform apply`, no EKS cluster, no RDS instance, no ECR push, no CI run of `deploy-eks.yml` | — |

`eks.md` ("Not verifiable offline") lists what the first real EKS deploy must confirm. That list includes: the
Auto Mode ALB honouring the Ingress annotations together with IngressClassParams certificates; NetworkPolicy
enforcement on Auto Mode; ESO picking up Pod Identity credentials with no `auth` block; RDS's actual refusal of
BYPASSRLS and the D-001 policy on a real RDS/Aurora instance; and the `metrics-server` add-on name.

## 8. Troubleshooting

Use the symptom tables in `lima-k8s-lab.md` (lab) and `eks.md` (EKS). The common cases:

| Symptom | Fix |
|---|---|
| `deploy.sh: cluster API not reachable` | Check the Thunderbolt link and both Lima VMs (`limactl list`) |
| namespace `<app>-dev` missing | Ask a human to run `app-namespaces.sh <app>`; agents can't create namespaces |
| `db-access: … reads DB_MIGRATOR_…` | A service is wired to the migrator; services use `DB_APP_*` |
| `db-rls-check: FAIL …` | Read the Job log. Either a table has no migrator policy (add a migration calling `app_grant_migrator`), or an unconditional policy reaches the app role (drop it in a new migration) |
| migrate/seed see no rows of other tenants (RDS) | D-001: the table lacks the migrator policy |
| `has no staging-healthy-<sha> tag` | Deploy that exact promotion to staging first |
