# Lima k8s lab cluster — non-prod dev/qa environments for every project

The framework's non-prod Kubernetes target: k3s in Lima VMs on one or two Macs, one namespace per
app per environment (`<app>-dev`, `<app>-qa`). Agents deploy to it unattended; humans own the cluster.
Templates live in `~/.claude/templates/k8s/` (repo: `.claude/templates/k8s/`).
Staging and prod run the same base on Amazon EKS, promoted from qa by digest. Humans or CI deploy
them, never agents: see `eks.md`.

## Topology (two Macs over a Thunderbolt bridge)

```text
server Mac (10.10.10.20)                                  dev Mac (10.10.10.30) — Claude runs here
Lima VM sdlc-server: k3s server, Traefik, registry        Lima VM sdlc-agent: k3s agent
  node IP 172.30.10.2 (dummy iface sdlc0)                   node IP 172.30.10.3
  forwards on 10.10.10.20: 6443 API, 51820/udp WG,          forwards: 51820/udp WG on 10.10.10.30,
    5001 registry, 18080 ingress                              127.0.0.1:5001 registry, 127.0.0.1:18080 ingress
        └──────────── flannel wireguard-native over forwarded UDP 51820 ────────────┘
```

- Lima can't bridge a VM onto a Thunderbolt Bridge, so k3s runs in its "distributed" mode:
  `--node-external-ip`, `--flannel-backend=wireguard-native`, `--flannel-external-ip`. Each host
  forwards only what the cluster needs. No host routes and no sudo.
- **On the dev Mac everything is loopback**, except kubectl → `https://10.10.10.20:6443`:
  - push images to `localhost:5001`;
  - reach apps at `http://<app>-<env>.localhost:18080`. curl and Chromium resolve `*.localhost`
    to 127.0.0.1 themselves.
- Single-Mac variant: run `cluster-up.sh` with `SERVER_SSH=""` and `AGENT_IP=""`. The registry and
  ingress are then on the server VM's forwards.
- **Why .20/.30 and not .2/.3.** 10.10.10.0/24 is a common Thunderbolt-bridge choice, and a remote
  client site reached over ssh uses .1–.3 on the same /24. The guard treats `--lab-host` IPs as local.
  With the lab on .2/.3, a command aimed at the other site's .2 would pass as a lab call. Keep lab
  host numbers out of the range other sites use. A routed site-to-site VPN would need a different
  subnet on one side. ssh tunnels, which resolve addresses on the far side, do not.

## Who does what

| Human (admin kubeconfig `~/.kube/sdlc-lab-admin.yaml`) | Agent (`~/.kube/sdlc-lab.json`, ServiceAccount `sdlc-system/sdlc-agent`) |
|---|---|
| `scripts/cluster-up.sh`: VMs, registry, RBAC, agent kubeconfig, guard policy | read anything except Secrets outside its namespaces |
| `scripts/app-namespaces.sh <app>`: namespaces, quota, RBAC, NetworkPolicy | `admin` inside `<app>-dev` / `<app>-qa` only |
| `scripts/cluster-check.sh`: end-to-end proof | `scripts/k8s/deploy.sh`, `env-reset.sh`, `seed.sh`, `smoke.sh` |

The agent can't create or delete namespaces, change quotas, write cluster-scoped objects, or touch
kube-system. The sdlc-guard hook and PATH shims repeat these limits at the command line, with clearer
errors.

## Per-project layer (`instantiate.sh <project> <app>` → deployment_agent adapts it)

- `deploy/k8s/app.env`: APP, REGISTRY, INGRESS_PORT, SMOKE_PATHS, VERSION_PATH.
- `deploy/k8s/images.txt`: `<image-name> <build-context> [dockerfile]` for each built service.
- `deploy/k8s/base/`: one `<service>.yaml` per stateless service, plus `postgres.yaml`, `jobs.yaml`
  (the `db-roles`, `db-migrate`, `db-seed` and `db-rls-check` Job templates), `ingress.yaml`,
  `db-roles.sh` (rule 10) and `db-rls-check.sh` (rule 7, decision D-001).
- `deploy/k8s/overlays/{dev,qa}/kustomization.yaml`: namespace, host, `APP_ENV`, replicas, and the
  **managed images block**. Only `deploylib.py set-images` writes that block, and only with digests.
- `scripts/k8s/*`: identical in every project. Don't fork them; fix the template instead.

## Rules (each learned on the live cluster)

1. **Digests, never tags.** qa is promoted from the newest HEALTHY dev deploy's digests. deploy.sh
   checks that the running pods' `imageID`s end with those digests.
2. **Numeric `USER` in every image** (e.g. `USER 65532:65532`). With `runAsNonRoot: true`, a named
   user fails with `CreateContainerConfigError: image has non-numeric user`.
3. **Migrations and seeds run as Jobs created from suspended CronJob templates**
   (`kubectl create job … --from=cronjob/db-migrate`). Jobs are immutable, and the template keeps
   the current digest.
4. **New pods can't connect for about 5 s.** k3s's network-policy controller refuses a new pod's
   first connections while it admits the pod's IP (measured: refused at t+0, fine at t+5 s).
   - Job templates carry a `wait-for-db` init container.
   - Migrate/seed commands must retry the connection for about 60 s.
   - They must fail fast on auth errors (SQLSTATE 28xxx).
   - Job retries don't help: each retry is a new pod with a new IP.
5. **Seeds are idempotent upserts**, because they run on every deploy and after every reset.
   Schema is forward-only: rollback redeploys code, not schema.
6. **Readiness must check what the release needs.** For example, the fixture's `/readyz` checks
   the schema version. New pods then stay unready until migrations land, and old pods keep serving.
7. **Three database credentials in one secret; each workload reads only its own.** The overlay's
   gitignored `secrets.env` becomes the secret `db-credentials` with three user/password pairs:

   | Keys | Role | Who reads them |
   |---|---|---|
   | `DB_SUPERUSER_USER/_PASSWORD` | bootstrap superuser (`postgres`; `app` on a volume made before the two roles) | Postgres itself and the `db-roles` Job, nobody else |
   | `DB_MIGRATOR_USER/_PASSWORD` | `app_migrator`: NOSUPERUSER BYPASSRLS, owns the database and every object in it | `db-migrate`, `db-seed` (the `db-*` Job templates) |
   | `DB_APP_USER/_PASSWORD` | `app_runtime`: NOSUPERUSER NOBYPASSRLS, owns nothing; CONNECT, USAGE on `public`, DML via default privileges | every service (`api.yaml`) and the `db-rls-check` Job |

   - The app role is what makes `FORCE ROW LEVEL SECURITY` real: it isn't the owner and can't bypass
     RLS, so a tenant query without a WHERE clause still returns one tenant's rows. It can't CREATE,
     ALTER, DROP, TRUNCATE or `SET ROLE` the migrator. The migrator reaches every tenant in data
     migrations and seeds without lifting FORCE RLS, so they take no table-wide exclusive locks. On the
     lab it has BYPASSRLS. Decision D-001 also gives every FORCE-RLS table a migrator-only policy
     (`SELECT app_grant_migrator('<table>')`, `databases/postgres.md`). That policy is what works on
     RDS/Aurora, where BYPASSRLS can't be granted (`infrastructure/eks.md`), and here it is harmless.
     Write migrations with it on the lab too, so they run unchanged on staging and prod
     (`backend/archetypes/migration-pattern-*.md`, `infrastructure/saas-tenancy-models.md`).
   - **The `db-rls-check` Job proves it after every migrate + seed**, as the app role, before the
     rollout (`db-rls-check.sh`). The deploy fails if any of these hold:
     - a FORCE-RLS table lacks its migrator policy;
     - an unconditional (`USING (true)`) policy names any role but the table owner, e.g. `TO PUBLIC`
       or `TO app_runtime`;
     - the app role reads a row with no tenant set.
   - **deploy.sh enforces who reads what** on every render, before anything is applied
     (`deploylib.py db-access`): superuser keys only in Postgres and `db-roles`, migrator keys only in
     Postgres and `db-*` Job templates (never a Deployment), `db-rls-check` present and holding the app
     keys only, no `envFrom` or volume of the whole secret, no old `DB_USER`/`DB_PASSWORD`. The apply
     step fails and names the container otherwise.
   - `secrets.env` is gitignored, and deploy.sh refuses to write passwords into one git would track.
     When it's missing, deploy.sh rebuilds it from the namespace so a fresh checkout doesn't lock
     itself out of the volume: from the newest three-role secret, or, in a namespace from before the
     two roles, from the OLDEST `DB_USER`/`DB_PASSWORD` secret (the pair the volume was initialised
     with), which becomes the superuser pair. An old-layout `secrets.env` is upgraded in place the
     same way. Missing passwords are generated (48 random hex characters).
   - Only `env-reset.sh` rotates the superuser, because it deletes the volume too. The migrator and app
     passwords follow the secret: the `db-roles` Job sets whatever it holds (rule 10).
   - Debug as the service sees it: `kubectl -n <app>-dev exec postgres-0 -- psql -U postgres -d app`
     (`-U app` on an old-layout volume), then `SET ROLE app_runtime;` (the superuser may; the app role
     can't go the other way).
8. **No NodePort or LoadBalancer Services in app namespaces** (quota 0). Traffic enters through the
   Traefik ingress, host `<app>-<env>.localhost`.
9. **dev and qa are isolated** by the `env-isolation` NetworkPolicy, which allows ingress only from
   the same namespace and from kube-system. Don't delete it, even though `admin` technically can.
10. **The roles converge on every deploy; no reset needed.** (Proven on throwaway Postgres 17
    containers by `tests/k8s-db-roles.sh`; `tests/k8s-e2e.sh` checks it on the cluster.) One script,
    `deploy/k8s/base/db-roles.sh` (ConfigMap `db-roles`), has two callers:
    - Postgres runs it from `/docker-entrypoint-initdb.d` once, on an empty data directory.
    - The `db-roles` Job runs it as the superuser on every deploy, after Postgres is ready and before
      `db-migrate` (deploy step `roles`).
    It creates or resets both roles' attributes, revokes any membership that would let the app role
    become the migrator, makes the migrator own the database, revokes CONNECT/TEMP from PUBLIC, sets the
    default privileges, and hands every object someone else owns (tables, partitions, sequences, views,
    types, routines, statistics, schemas; extension members excepted) to the migrator, granting the app
    role what the default privileges would have. So a volume from the one-superuser era converges on its
    next deploy. It checks before it changes: on a converged database it prints
    `db-roles: no changes` and leaves the catalog byte-identical, passwords included (it tries a login
    first). Passwords come from the environment (`\getenv`), and the session that sets them turns
    statement logging off. It never prints one.
    - Migrations must run as the migrator. Tables a superuser creates are out of the app role's default
      privileges, and `/readyz` stays 503 until the next deploy's `db-roles` hands them over. The
      fixture's `migrate` refuses both the superuser and the app role (the archetypes' `env.py`
      refuses the app role).
    - Default privileges cover schema `public`. A migration that creates another schema grants the
      app role `USAGE` and sets that schema's default privileges itself.
    - The app role gets DML on every table the migrator creates, including the schema-version table
      (which `/readyz` must read). A migration may `REVOKE INSERT, UPDATE, DELETE` on a table from it;
      `db-roles` never re-grants on objects the migrator already owns.

## Keeping it clean (automatic — don't add ad-hoc cleanup)

| What accumulates | Who cleans it | When |
|---|---|---|
| Local Docker copies of pushed images | `deploy.sh` removes each tag right after `crane push` (build cache stays, so rebuilds stay fast) | every build |
| Registry images for the app | `scripts/k8s/registry-prune.sh`. Keeps digests in use in `<app>-dev`/`<app>-qa` plus the newest 5 HEALTHY deploys per env (rollback targets), and deletes failed, dirty and superseded builds | after every HEALTHY deploy; by hand with `--dry-run` / `--keep N` |
| Registry disk (layers of deleted images) | CronJob `sdlc-system/registry-gc` (`registry garbage-collect --delete-untagged`) | nightly 04:30 |
| Old generated ConfigMaps/Secrets (`<name>-<hash>`) | `deploy.sh` deletes those of its own generators that the current render doesn't reference | after every HEALTHY deploy |
| Finished roles/migrate/seed Jobs and their pods | `ttlSecondsAfterFinished: 3600` (results are in `history.jsonl`) | 1 h after finishing |
| Old ReplicaSets | `revisionHistoryLimit: 3` (rollback is by digest, not ReplicaSet) | on rollout |
| `-dirty` image tags | only produced when a *build context* has uncommitted changes. Keep logs and outputs out of `services/*` | — |

Cleanup never runs after a failed or DEGRADED deploy, so everything is left in place for debugging.
Nothing ever deletes a namespace or a database volume except `env-reset.sh`.

## Endpoints

| | dev | qa |
|---|---|---|
| Web/API from the dev Mac (curl, Playwright/Chromium, iOS simulator via Safari*) | `http://<app>-dev.localhost:18080` | `http://<app>-qa.localhost:18080` |
| From the server Mac | `curl -H 'Host: <app>-dev.localhost' http://10.10.10.20:18080` | same with `-qa` |
| Postgres (debugging) | `kubectl -n <app>-dev port-forward svc/postgres 15432:5432` | `… -n <app>-qa … 25432:5432` |

\*Safari and native apps may not resolve `*.localhost`. Use `http://127.0.0.1:18080` with a Host
header, or `port-forward` to a fixed local port.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| `deploy.sh: cluster API not reachable` | Thunderbolt link up? (`ifconfig bridge0`) Both VMs running? (`limactl list`; `ssh <server> limactl list`) |
| `registry localhost:5001 not reachable` | The agent VM's static forward: `lsof -iTCP:5001`. Restart with `limactl stop/start sdlc-agent` |
| Docker can't push to `localhost:5001` | Expected. Docker Desktop's daemon can't reach host loopback; deploy.sh pushes with `crane` |
| Pod `CreateContainerConfigError` | Numeric USER (rule 2), or a missing secret/configmap key |
| migrate: `connection refused` right after start | Rule 4: the `wait-for-db` init container is missing from the Job template |
| roles: `superuser login refused` | Rule 7: the superuser pair in `secrets.env` doesn't match the volume. Delete `secrets.env` and redeploy (it is rebuilt from the namespace), or `env-reset.sh` |
| migrate/seed/API: `password authentication failed` for `app_migrator`/`app_runtime` | The `roles` step didn't run or failed (it sets those passwords from the secret). Read `kubectl logs job/roles-…` |
| apply fails with `db-access: … reads DB_MIGRATOR_…` (or `DB_SUPERUSER_`, `envFrom`, `DB_PASSWORD`) | Rule 7: a workload is wired to a role it must not have. Services use `DB_APP_*`; only `db-*` Job templates get the migrator |
| migrate: `must run as the migration role` | The migrate Job got the app or superuser keys. Use `DB_MIGRATOR_*` (`jobs.yaml`) |
| `/readyz` 503, `permission denied for table …` in the API log | Tables made by someone other than the migrator (a migration run by hand as `postgres`). The next deploy's `roles` step hands them over (rule 10) |
| A node `NotReady` | The laptop slept or the link dropped. Pods reschedule after ~5 min; Traefik, CoreDNS and the registry are pinned to the server node |
| Anything else in the VM | `limactl shell sdlc-agent sudo journalctl -u k3s-agent`; on the server Mac `limactl shell sdlc-server sudo journalctl -u k3s` |

Verify the whole path at any time with `scripts/cluster-check.sh` (admin). For the framework itself,
run `tests/k8s-e2e.sh` (live cluster), `tests/k8s-db-roles.sh` (the two roles on throwaway local
Postgres containers, no cluster: fresh and old-layout volumes, RLS, idempotence, no password in any
log) and `tests/k8s-templates.test.sh` (offline, in `run-all.sh`).
