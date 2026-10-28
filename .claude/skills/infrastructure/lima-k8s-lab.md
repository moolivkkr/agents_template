# Lima k8s lab cluster — dev, qa and prod namespaces for every project

The framework's Kubernetes target: k3s in Lima VMs on one or two Macs, one namespace per app per
environment: `<app>-dev`, `<app>-qa` and `<app>-prod`. Agents deploy dev and qa unattended. **prod is
human-only**: it receives qa's digests, never a build, and agents can read it but not write it. Humans
own the cluster. Templates live in `~/.claude/templates/k8s/` (repo: `.claude/templates/k8s/`).

```text
dev  (agent: build from working tree) ──digests──▶ qa  (agent: promote) ──digests──▶ prod  (human: promote + confirm)
```

**Know what lab prod is.** Namespaces separate names, RBAC, quotas and network traffic. They don't
isolate failures: prod shares nodes, the registry, Traefik and the control plane with dev and qa, and a
laptop that sleeps takes a node `NotReady`, so pods move about 5 minutes later. Fine for a pilot or an
internal tool. For anything with an availability promise, run prod on Amazon EKS: put
`deploy/k8s/overlays/prod/eks.env` in place (`instantiate.sh --eks`) and `prod` then routes to EKS,
promoted via staging. Humans or CI deploy it, never agents: see `eks.md`.

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

## Tailnet mode (any number of Macs over Tailscale)

`cluster-up.sh` with `TRANSPORT=tailnet` builds the same cluster (same namespaces, RBAC, registry,
ingress, guard model) across Macs that share a Tailscale tailnet instead of a Thunderbolt link.

```text
Mac SERVER_MAC ── VM sdlc-server (tailnet device sdlc-server, tag:k8s) ─┐
Mac A ── VM sdlc-agent (tailnet device sdlc-agent-A) ───────────────────┤  tailnet: WireGuard mesh,
Mac B ── VM sdlc-agent (sdlc-agent-B) ──────────────────────────────────┤  pod /24s as subnet routes
Mac C ── VM sdlc-agent (sdlc-agent-C) ──────────────────────────────────┘
```

- Every VM is its own tailnet device. Its tailnet IPv4 is its node IP, and k3s's `--vpn-auth`
  integration switches flannel to the Tailscale backend, which advertises each node's pod /24
  (https://docs.k3s.io/networking/distributed-multicloud). One template, `lima/sdlc-node-tailnet.yaml`,
  serves all nodes; `scripts/tailnet-join.sh` joins the VM and installs k3s. Secrets go in on stdin.
- The VM joins with `--snat-subnet-routes=false`. Routed packets keep their real source IP, so the
  `env-isolation` NetworkPolicy still recognises same-namespace pods on other nodes.
- **Every lab Mac reaches every pod IP directly.** `cluster-up.sh` stores the lab Macs' tailnet IPs
  in ConfigMap `sdlc-system/lab-network`. `app-namespaces.sh` then adds one `ipBlock /32` per lab Mac
  to `env-isolation`. Other tailnet devices and other namespaces are still refused.
- **Every lab Mac reaches every Service too, by name.** `sdlc-server` also advertises the Service
  CIDR (10.43.0.0/16). With split DNS for `cluster.local` (console step 2 below), any Mac reaches,
  for example, `postgres.<app>-dev.svc.cluster.local:5432`, or any `http(s)://<svc>.<ns>.svc.cluster.local`.
  kube-proxy masquerades that traffic to the node that routed it, so `env-isolation` also admits the
  node VMs' tailnet IPs (`lab-network` key `node-ips`). Pod-to-pod and pod-to-Service traffic keeps
  the pod's own IP, so other namespaces are still refused.
- Each Mac keeps the loopback conventions: `localhost:5001` (registry),
  `http://<app>-<env>.localhost:18080` and `https://<app>-<env>.localhost:18443` (ingress; Traefik's
  default certificate is self-signed). The API is `https://<sdlc-server tailnet IP>:6443`.
- **Mac to Mac**, outside the cluster: Tailscale's default policy passes every port. On the LandOS
  hosts, pf (`io.landos`) only restricts ssh and VNC. For ssh, run landos
  `infra/scripts/host-ssh-tailnet-onboard.sh` once per Mac; it admits the lab Macs' tailnet IPs.
  The macOS application firewall lets signed software listen. An unsigned host service needs
  allowing in System Settings › Network › Firewall. Prove every pair, both ways, with
  `MACS="[user@]mac ..." scripts/lab-mesh-check.sh` (path direct or relayed, ssh, HTTP on a test port).
- The guard's lab hosts are the lab Macs and node VMs only, by tailnet name and IP. Other devices on
  the same tailnet (for example another site's Mac) stay non-local.

**One-time, in the Tailscale admin console:**

1. Merge this into the policy file:
   ```hujson
   "tagOwners":     {"tag:k8s": ["autogroup:admin"]},
   "autoApprovers": {"routes": {"10.42.0.0/16": ["tag:k8s"], "10.43.0.0/16": ["tag:k8s"]}},
   "ssh": [{"action": "accept", "src": ["autogroup:member"], "dst": ["tag:k8s"],
            "users": ["autogroup:nonroot", "root"]}],
   ```
   With a restricted policy (not the default allow-all), also grant the lab Macs and `tag:k8s`
   access to `tag:k8s:*`, `10.42.0.0/16:*` and `10.43.0.0/16:*`. Grant nothing else to those ranges.
2. DNS › Nameservers › Add nameserver › Custom: `10.43.0.10` (CoreDNS), with "Restrict to domain"
   set to `cluster.local`. This is split DNS: only `*.cluster.local` goes there.
3. Settings › Keys: create an auth key that is reusable, pre-approved and tagged `tag:k8s`
   (not ephemeral).

**Each lab Mac:** Tailscale running, `brew install lima`, Remote Login on, and
`ssh <mac> true` working from the Mac that runs `cluster-up.sh`. Tailscale's macOS app can't be a
Tailscale SSH server, so Mac-to-Mac is plain ssh over MagicDNS. The VMs run Tailscale SSH
(`ssh sdlc-agent-<mac>`).

```bash
TRANSPORT=tailnet SERVER_MAC=macstudio51 AGENT_MACS="macm4 studio52 studio256" \
  TS_AUTHKEY=tskey-auth-... .claude/templates/k8s/scripts/cluster-up.sh
```

**Sites and latency.** Node IPs are tailnet IPs. A Mac can move to another network or country and
its node rejoins with the same IP, with no change to the cluster. The server is the exception:
moving `sdlc-server` means rebuilding the cluster, so put it on the Mac that will be its permanent
home. The registry, Traefik and CoreDNS are pinned to the server node. Agents on a distant site pay
that round trip on image pulls, ingress and DNS lookups until they move close to it. Check each path
with `tailscale ping sdlc-agent-<mac>`: "via <ip>:<port>" means a direct connection, "via DERP"
means relayed.

Switching an existing Thunderbolt cluster to tailnet rebuilds it. `limactl delete` the old
`sdlc-server` and `sdlc-agent` VMs (this wipes every `<app>-<env>` namespace and its data), run the
command above, then `app-namespaces.sh <app>` and each project's deploy.

## Who does what

| Human (admin kubeconfig `~/.kube/sdlc-lab-admin.yaml`) | Agent (`~/.kube/sdlc-lab.json`, ServiceAccount `sdlc-system/sdlc-agent`) |
|---|---|
| `scripts/cluster-up.sh`: VMs, registry, RBAC, agent kubeconfig, guard policy | read anything except Secrets outside its namespaces |
| `scripts/app-namespaces.sh <app>`: namespaces dev, qa and prod, quota, RBAC, NetworkPolicy | `admin` inside `<app>-dev` / `<app>-qa` only; `<app>-prod` read-only (no Secrets) |
| `scripts/cluster-check.sh`: end-to-end proof | `scripts/k8s/deploy.sh`, `env-reset.sh`, `seed.sh`, `smoke.sh` for dev/qa |
| `scripts/k8s/deploy.sh prod [--rollback]`: promote qa's digests, typed `<app>-prod` confirmation (CI: `PROD_KUBECONFIG` + `CONFIRM_PROD=<app>-prod`) | — (RBAC and the guard refuse) |

The agent can't create or delete namespaces, change quotas, write cluster-scoped objects, or touch
kube-system. The sdlc-guard hook and PATH shims repeat these limits at the command line, with clearer
errors.

## Per-project layer (`instantiate.sh <project> <app>` → deployment_agent adapts it)

- `deploy/k8s/app.env`: APP, REGISTRY, INGRESS_PORT, SMOKE_PATHS, VERSION_PATH.
- `deploy/k8s/images.txt`: `<image-name> <build-context> [dockerfile]` for each built service.
- `deploy/k8s/base/`: one `<service>.yaml` per stateless service, plus `postgres.yaml`, `jobs.yaml`
  (the `db-roles`, `db-migrate`, `db-seed` and `db-rls-check` Job templates), `ingress.yaml`,
  `db-roles.sh` (rule 10) and `db-rls-check.sh` (rule 7, decision D-001).
- `deploy/k8s/overlays/{dev,qa,prod}/kustomization.yaml`: namespace, host, `APP_ENV`, replicas, and the
  **managed images block**. Only `deploylib.py set-images` writes that block, and only with digests.
- `scripts/k8s/*`: identical in every project. Don't fork them; fix the template instead.

## Rules (each learned on the live cluster)

1. **Digests, never tags.** qa is promoted from the newest HEALTHY dev deploy's digests, and prod from
   the newest HEALTHY qa deploy's. deploy.sh
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
9. **dev, qa and prod are isolated** by the `env-isolation` NetworkPolicy, which allows ingress only from
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
| Registry images for the app | `scripts/k8s/registry-prune.sh`. Keeps digests in use in `<app>-dev`/`<app>-qa`/`<app>-prod` plus the newest 5 HEALTHY deploys per env (rollback targets), and deletes failed, dirty and superseded builds | after every HEALTHY deploy; by hand with `--dry-run` / `--keep N` |
| Registry disk (layers of deleted images) | CronJob `sdlc-system/registry-gc` (`registry garbage-collect --delete-untagged`) | nightly 04:30 |
| Old generated ConfigMaps/Secrets (`<name>-<hash>`) | `deploy.sh` deletes those of its own generators that the current render doesn't reference | after every HEALTHY deploy |
| Finished roles/migrate/seed Jobs and their pods | `ttlSecondsAfterFinished: 3600` (results are in `history.jsonl`) | 1 h after finishing |
| Old ReplicaSets | `revisionHistoryLimit: 3` (rollback is by digest, not ReplicaSet) | on rollout |
| `-dirty` image tags | only produced when a *build context* has uncommitted changes. Keep logs and outputs out of `services/*` | — |

Cleanup never runs after a failed or DEGRADED deploy, so everything is left in place for debugging.
Nothing ever deletes a namespace or a database volume except `env-reset.sh`.

## Endpoints

| | dev | qa | prod |
|---|---|---|---|
| Web/API from the dev Mac (curl, Playwright/Chromium, iOS simulator via Safari*) | `http://<app>-dev.localhost:18080` | `http://<app>-qa.localhost:18080` | `http://<app>-prod.localhost:18080` |
| From the server Mac | `curl -H 'Host: <app>-dev.localhost' http://10.10.10.20:18080` | same with `-qa` | same with `-prod` |
| Postgres (debugging) | `kubectl -n <app>-dev port-forward svc/postgres 15432:5432` | `… -n <app>-qa … 25432:5432` | human only (admin kubeconfig), `35432` |

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
