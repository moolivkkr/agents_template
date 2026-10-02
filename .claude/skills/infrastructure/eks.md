---
skill: eks
description: Amazon EKS staging/prod targets — Auto Mode cluster, RDS PostgreSQL with the two-role model, Pod Identity + External Secrets Operator, ECR digest promotion from the lab, GitHub OIDC CI, Terraform with S3-native locking, and why agents never deploy there
version: "1.0"
tags:
  - kubernetes
  - eks
  - aws
  - ecr
  - rds
  - terraform
  - deployment
---

# Amazon EKS — the staging and prod targets

The lab cluster (`lima-k8s-lab.md`) runs `<app>-dev` and `<app>-qa`, and agents deploy there unattended.
`--target=staging|prod` runs the **same kustomize base** on Amazon EKS, one cluster, VPC and database
per environment. Agents write and validate this layer offline. **Humans or CI deploy it.** The guard
refuses agents, and prod asks for a confirmation every time.

Templates: `~/.claude/templates/k8s/eks/` (repo `.claude/templates/k8s/eks/`). Copy them into a project
with `instantiate.sh <project> <app> --eks`.

## Release flow (build once, promote the digest)

```text
dev (lab)  --build-->  localhost:5001/<app>/api@sha256:D     deploy.sh dev     (agent)
qa  (lab)  --promote-> same digest D                          deploy.sh qa      (agent)
staging    --promote-eks.sh staging: crane copy to ECR, still D (human, dev Mac) -> commit -> CI deploys
           deploy-eks.sh: HEALTHY -> ECR tag staging-healthy-<sha> on D
prod       --promote-eks.sh prod: only digests with staging-healthy-<sha>       -> commit -> CI deploys
           (GitHub Environment "prod": a required reviewer approves the run = the confirmation)
```

- Nothing is ever rebuilt after dev. `crane copy` keeps the manifest bytes, so the ECR digest equals the
  lab digest, and the scripts check that.
- The commit that changes `deploy/k8s/overlays/<env>/{kustomization.yaml,promoted-from.json}` is the
  release record. Reverting it is the CI rollback.
- ECR tags are **immutable**. `<git-sha>` and `<env>-healthy-<git-sha>` can't be moved to another image.
  That makes the staging-healthy tag trustworthy evidence for promoting to prod.

## Who does what

| Step | Who | Command |
|---|---|---|
| Write / adapt the layer, validate offline | agent (deployment_agent, ci_cd_agent) | `instantiate.sh . <app> --eks`; `kubectl kustomize` each overlay into `deploylib.py db-access` and `eks-policy --allow-placeholders`, kubeconform, `terraform fmt -check`, `init -backend=false` + `validate`, tflint, actionlint |
| State bucket (once per account) | human | `terraform -chdir=infra/terraform/envs/state apply` |
| Infrastructure | human (or a CI job with an admin role) | `terraform -chdir=infra/terraform/envs/<env> plan -out=tf.plan` then `apply tf.plan` |
| Coordinates into git | human / CI | `scripts/k8s/eks-outputs.sh <env>`, which writes `overlays/<env>/eks.env` (commit it) |
| Cluster bootstrap (once per cluster) | human, cluster-admin | `EKS_KUBECONFIG=… scripts/k8s/eks-bootstrap.sh <env>` |
| Promote | human on the dev Mac (staging needs the lab registry), CI or human for prod | `scripts/k8s/promote-eks.sh <env>`, then commit |
| Deploy | CI (`.github/workflows/deploy-eks.yml`) or human | `EKS_KUBECONFIG=… scripts/k8s/deploy.sh <env>` |
| Roll back | CI: revert the promotion commit. Human: `deploy.sh <env> --rollback` | prod asks again |

What the guard (`sdlc-guard.sh`) refuses an agent:
- the EKS scripts, and `deploy.sh`/`seed.sh`/`env-reset.sh`/`smoke.sh` with `staging` or `prod`;
- `/deploy` and `/rollback` with `--target=staging|prod`;
- `aws` without a LocalStack endpoint, `eksctl`, `aws-vault` and `saml2aws`;
- `kubectl` with any kubeconfig except the pinned lab one.

It **asks** first for:
- `terraform plan/output/state/test` and `init` with a backend;
- `crane` against a remote registry.

The `aws` and `crane` PATH shims repeat these checks inside scripts.

## Choices (checked 2026-10-01; re-verify before relying on a version)

| Choice | Why | Source |
|---|---|---|
| **EKS Auto Mode** (not managed node groups + Karpenter + a self-installed LB controller) | AWS runs compute (Karpenter-based, Bottlerocket, nodes replaced within 21 days), the ALB/NLB controller, EBS CSI, the Pod Identity agent and network policy. Nothing to install or patch for a small team. Cost: a per-instance management fee on top of EC2. | docs.aws.amazon.com/eks/latest/userguide/automode.html, aws.amazon.com/eks/pricing/ |
| Ingress = Auto Mode's managed ALB (`IngressClass` controller `eks.amazonaws.com/alb` + `IngressClassParams`) | The certificate (ACM), scheme, group and the allowed namespaces go in `IngressClassParams`. Annotations on an IngressClass are ignored, and `alb.ingress.kubernetes.io/group.name` on an Ingress is unsupported. `ssl-redirect`, `listen-ports` and `healthcheck-path` stay Ingress annotations. | docs.aws.amazon.com/eks/latest/userguide/auto-configure-alb.html |
| **EKS Pod Identity** (not IRSA) for pod AWS access | AWS: "recommends using EKS Pod Identities … whenever possible". No OIDC provider per cluster. Session tags (namespace, service account) for ABAC. Built into Auto Mode. IRSA remains for Fargate/Windows, which this layer doesn't use. | docs.aws.amazon.com/eks/latest/userguide/service-accounts.html, …/pod-id-abac.html |
| **External Secrets Operator** (not the Secrets Store CSI driver/ASCP) | It produces the **same** `db-credentials` Kubernetes Secret with the same keys the lab's secretGenerator makes. The base manifests, `secretKeyRef` env and `deploylib.py db-access` are unchanged. ASCP mounts files per pod and would fork the base. Trade-off: the controller's role reads every secret it is granted, so Terraform grants it exactly this environment's three. With one cluster per environment and one app per cluster, that is exact. Several apps in one cluster would need per-namespace stores (`auth.jwt` = IRSA) or one ESO role per app. | external-secrets.io/latest/provider/aws-access/ (no `auth` block = the controller's SDK credential chain = Pod Identity); docs.aws.amazon.com/eks/latest/userguide/manage-secrets.html (AWS documents ASCP) |
| **RDS for PostgreSQL** (Aurora optional) | One Multi-AZ instance in prod and single-AZ in staging is the cheapest managed Postgres with failover. Aurora PostgreSQL is a drop-in swap of `aws_db_instance` for an `aws_rds_cluster` (the same managed master secret is supported) when read scaling or faster failover is worth the price. | docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html |
| Master password managed by RDS in Secrets Manager; migrator/app passwords **write-only** | No database password is ever in Terraform state, a plan, git or a Kubernetes manifest: `manage_master_user_password`, `ephemeral "random_password"` and `secret_string_wo` (Terraform 1.11+, hashicorp/aws 6.x). | developer.hashicorp.com/terraform/language/resources/ephemeral (write-only arguments) |
| GitHub Actions → AWS with **OIDC** | No stored keys. The trust is pinned to one repo **and** one GitHub Environment (`…:environment:prod`), audience `sts.amazonaws.com`, exact match. No thumbprint, because IAM validates GitHub's CA. Set `github_ids` for repos created or renamed after 2026-07-15, which send the immutable subject `repo:OWNER@ID/REPO@ID:…`. | docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws, github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/ |
| Terraform state in S3 with `use_lockfile` | S3-native locking (Terraform 1.11+). The DynamoDB lock table is deprecated. | developer.hashicorp.com/terraform/language/backend/s3 |
| Versions pinned in the templates | Kubernetes **1.36** (EKS standard support until 2027-08-02); hashicorp/aws `>= 6.0, < 7.0` (6.67.0 resolved); terraform-aws-modules/eks `~> 21.26`, vpc `~> 6.7`; RDS PostgreSQL major **17** (= the `postgres:17-alpine` the db Jobs run, pinned by digest from ECR Public); ESO chart **2.11.0**; kubectl **v1.36.5** and crane **v0.22.1** in CI | docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html; GitHub releases; charts.external-secrets.io |

## The database roles on RDS/Aurora (read this before writing migrations)

The lab's model holds unchanged in one respect. `db-roles.sh` runs as a Job on every deploy, before
migrate. It creates and converges:
- `app_migrator`, which owns the database and every object;
- `app_runtime`, which is `NOSUPERUSER NOBYPASSRLS` and owns nothing, so `FORCE ROW LEVEL SECURITY`
  binds it.

`deploylib.py db-access` still proves on every render that only the db-* Jobs hold the migrator and
only db-roles holds the master user.

**The difference.** RDS has no superuser. The script runs as the master user (`NOSUPERUSER CREATEROLE
CREATEDB`, member of `rds_superuser`). PostgreSQL lets only a superuser or a BYPASSRLS role create a
BYPASSRLS role, and AWS's documented master role has no BYPASSRLS. So on RDS/Aurora:
- **The migrator is `NOBYPASSRLS`.** The Job prints a WARNING saying so. Owning the tables does not
  exempt it from `FORCE ROW LEVEL SECURITY`.
- **Settled by decision D-001 (docs/DECISIONS.md, 2026-10-01): the per-table migrator policy.** Every
  migration that creates a FORCE-RLS tenant table also gives it a permissive policy for the migrator
  alone, `USING (true) WITH CHECK (true)`. The pattern is the same on the lab and on RDS (on the lab it
  sits next to the migrator's BYPASSRLS, harmlessly), so a migration written for dev works unchanged on
  staging and prod.
  - **How.** The project's first migration creates the helper `app_grant_migrator(tbl regclass)`;
    every tenant-table migration ends with `SELECT app_grant_migrator('<table>');`, which creates
    `<table>_migrator_all ... TO <table owner>`. The SQL and the rules are in `databases/postgres.md`
    ("The migrator policy").
  - **Why the owner, not a configured name.** The migrator owns every object, because db-roles.sh
    converges ownership to `DB_MIGRATOR_USER`. So the helper reads the target from the catalog. No role
    name sits in the SQL, and nothing needs templating in golang-migrate, sqlx, Prisma or Drizzle, which
    have no placeholders. `DB_MIGRATOR_USER` stays the single source of the name, and db-roles.sh
    re-points any `*_migrator_all` policy to it after an ownership takeover.
  - **The runtime role stays confined.** It is not the owner and not a member of it, so the policy never
    applies to it; permissive policies are OR'ed, so it gets only the tenant policy. Data migrations never
    lift `FORCE` (that takes an `ACCESS EXCLUSIVE` lock).
  - **Proven on every deploy.** The `db-rls-check` Job runs as the app role after migrate and seed, before
    the rollout. It fails the deploy on any of these:
    - a FORCE-RLS table without the migrator policy;
    - any `USING (true)`/`WITH CHECK (true)` policy that names a role other than the table owner
      (`TO PUBLIC`, `TO app_runtime`, ...);
    - a runtime role that reads any row with no tenant set.

    `deploylib.py db-access` refuses a render without that Job, or one in which it holds anything but
    `DB_APP_*`.
  - **Proven offline.** `tests/eks-db-roles.sh` uses a stock PostgreSQL 17 set up like RDS. It runs the
    skill's own SQL block, and the NOBYPASSRLS migrator seeds and backfills two tenants. The runtime role
    reads and writes only its own tenant. Without the policy, the migrator's backfill reaches 0 rows.
  - **Rejected.** ENABLE without FORCE on RDS: the owner would bypass RLS silently, which is weaker.
- **Statement logging can't be switched off for the password session**, because that is a superuser
  setting. The Terraform parameter group pins `log_statement = none`. Keep it that way, or
  `ALTER ROLE … PASSWORD` lands in CloudWatch logs.
- **The master user becomes a member of the migrator.** It needs that to hand over the database and
  set default privileges. Requires PostgreSQL 16+ for `pg_has_role(…, 'SET')`.
- **Passwords:** to rotate the migrator and app passwords, bump `db_password_version` and apply.
  - The next deploy's db-roles Job sets the new passwords on the database.
  - Pods read their credentials at start, so restart them with
    `kubectl -n <app>-<env> rollout restart deploy`.
  - RDS rotates the master password itself, and ESO re-reads it every 15 minutes.

## Files (per project, after `instantiate.sh --eks`)

| Path | What |
|---|---|
| `deploy/k8s/components/eks/` | The kustomize Component that turns the lab base into EKS: deletes the Postgres StatefulSet/Service, points clients at `DB_HOST` with `sslmode=require`, adds the ExternalSecret/SecretStore, ServiceAccount, PDB, HPA, zone spread, NetworkPolicy and ALB ingress, and pins the postgres tool image by digest |
| `deploy/k8s/overlays/{staging,prod}/` | `kustomization.yaml` (namespace, replacements from `eks.env`, the managed images block), `eks.env` (non-secret coordinates), `promoted-from.json` (provenance, written by promote) |
| `deploy/k8s/eks-cluster.yaml` | Cluster-scoped objects applied by `eks-bootstrap.sh`: the namespace with Pod Security `restricted`, `IngressClass` + `IngressClassParams` limited to the namespace, and a Role so the deployers can manage ExternalSecrets |
| `scripts/k8s/{deploy-eks,promote-eks,eks-bootstrap,eks-outputs}.sh` | `deploy.sh staging\|prod` hands over to `deploy-eks.sh`. `lib.sh` holds the shared Job/rollout/parity helpers |
| `infra/terraform/modules/platform` | VPC (3 AZs; prod has one NAT per AZ), EKS Auto Mode (access entries only), ECR, RDS + parameter group, role secrets, ESO Pod Identity, optional per-service Pod Identity roles |
| `infra/terraform/modules/github-oidc` | The OIDC provider (one per account) and the environment-pinned deploy role. ECR read/tag/copy and `eks:DescribeCluster` only; Kubernetes rights come from its access entry (admin in `<app>-<env>` only) |
| `infra/terraform/envs/{state,staging,prod}` | Roots. `state` holds the state bucket (local state, apply once). The others have `backend.tf` (S3, `use_lockfile`) and `terraform.tfvars.example` |
| `.github/workflows/deploy-eks.yml` | Staging on push to main touching its overlay. Prod by `workflow_dispatch` only, in the protected Environment. OIDC, checksum-verified kubectl/crane |

## Rules

1. **Digests, never tags.** Same rule as the lab. `deploylib.py eks-policy` refuses a render with any
   image that isn't `<ECR registry>/…@sha256:…` (or the allowlisted digest-pinned public postgres tool).
2. **No Secret in git or in the render.** `db-credentials` comes only from the ExternalSecret.
   `eks-policy` fails a render containing a `Secret`.
3. **eks.env holds coordinates, not credentials.** `deploy-eks.sh` and `eks-policy` refuse placeholder
   values: `000000000000`, `example.com`, `placeholder`.
4. **Prod asks every time.** `deploy-eks.sh` accepts only two things:
   - a typed `<app>-prod@<sha>` on a terminal;
   - or, in GitHub Actions, `SDLC_PROD_CONFIRM` equal to that string, inside a job running in the
     protected `prod` Environment. GitHub withholds the job and its OIDC token until a required
     reviewer approves.

   Configure the `prod` Environment with required reviewers and restrict it to `main`. Without that,
   CI has no human gate.
5. **Prod runs only what staging ran HEALTHY**, checked by the `staging-healthy-<sha>` tag at promote
   and again at deploy.
6. **Never the lab kubeconfig.** For staging/prod, `EKS_KUBECONFIG` must be explicit. Its current
   context must be the `EKS_CLUSTER_ARN` in `eks.env` (the name `aws eks update-kubeconfig` gives it).
7. **Every Deployment gets a PDB and a zone spread. An HPA-scaled Deployment sets no `replicas`.**
   `eks-policy` enforces both. Add a `production-pods.yaml`-style patch for every new service.
8. **One cluster, VPC, database and ESO role per environment**, ideally one AWS account per
   environment. Staging can never read prod's secrets, and a bad Terraform apply has one blast radius.
9. **Migrations stay forward-only and N-1 compatible.** Rollback redeploys code, never schema. A
   failed migration stops the deploy before rollout, and the old pods keep serving.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| `secrets` step fails | `kubectl -n <app>-<env> describe externalsecret db-credentials`. Is ESO installed (`eks-bootstrap.sh`)? Does the Pod Identity association `external-secrets/external-secrets` exist (Terraform)? Do the secret ids in `eks.env` match `terraform output eks_env`? |
| roles: `superuser login refused` | The RDS master secret rotated and ESO hasn't refreshed yet (15 min). Force it with `kubectl annotate externalsecret db-credentials force-sync=$(date +%s) --overwrite`, then redeploy |
| roles: `permission denied to create role` | The connecting user isn't the RDS master user (`DB_MASTER_SECRET_ARN`), or the instance runs PostgreSQL < 16 |
| migrate/seed see no rows of other tenants | D-001: the table has no migrator policy. Add a migration with `SELECT app_grant_migrator('<table>');` (helper: `databases/postgres.md`) |
| `rls` step fails (`db-rls-check: FAIL ...`) | Read the Job log (`kubectl -n <app>-<env> logs job/<rls-…>`): a FORCE-RLS table without its migrator policy, an unconditional policy reaching the app role (BLOCKING: drop it in a new migration), or the app role reading rows with no tenant set |
| ALB never appears / Ingress has no address | Is the IngressClass `<app>-alb` present? Does the namespace label match `IngressClassParams.namespaceSelector`? Are the subnets tagged `kubernetes.io/role/elb`? Is the ACM certificate in the same region? |
| smoke fails with a TLS or DNS error | Point `APP_HOST` (Route 53 alias/CNAME) at the ALB hostname (`kubectl get ingress web`) after the first deploy |
| `has no staging-healthy-<sha> tag` | Deploy that exact promotion to staging first. Prod never takes an untested digest |
| HPA shows `<unknown>` | Is the metrics-server add-on active? (`aws eks describe-addon --addon-name metrics-server`, human) |

## Not verifiable offline (check on the first real deploy)

These are documented but not yet exercised against AWS: the Auto Mode ALB honouring the
`listen-ports`/`ssl-redirect`/`healthcheck-path` Ingress annotations together with `certificateARNs`
from IngressClassParams; NetworkPolicy enforcement on Auto Mode (it must be enabled for the cluster);
ESO picking up Pod Identity credentials with no `auth` block; RDS's actual refusal of BYPASSRLS and the
D-001 migrator policy on a real RDS/Aurora instance (both proven on stock PostgreSQL 17 set up like RDS,
not on RDS); `metrics-server` as an add-on name on the chosen Kubernetes version.
`tests/eks-templates.test.sh` proves the rest offline: renders, schemas, policies, the prod gates in
the script, and Terraform validity.
