# Lima k8s lab cluster — non-prod dev/qa environments for every project

The framework's non-prod Kubernetes target: k3s in Lima VMs on one or two Macs, one namespace per
app per environment (`<app>-dev`, `<app>-qa`). Agents deploy to it unattended; humans own the cluster.
Templates live in `~/.claude/templates/k8s/` (repo: `.claude/templates/k8s/`).

## Topology (two Macs over a Thunderbolt bridge)

```
server Mac (10.10.10.2)                                   dev Mac (10.10.10.3) — Claude runs here
Lima VM sdlc-server: k3s server, Traefik, registry        Lima VM sdlc-agent: k3s agent
  node IP 172.30.10.2 (dummy iface sdlc0)                   node IP 172.30.10.3
  forwards on 10.10.10.2: 6443 API, 51820/udp WG,           forwards: 51820/udp WG on 10.10.10.3,
    5001 registry, 18080 ingress                              127.0.0.1:5001 registry, 127.0.0.1:18080 ingress
        └──────────── flannel wireguard-native over forwarded UDP 51820 ────────────┘
```

- Lima can't bridge a VM onto a Thunderbolt Bridge, so k3s runs in its "distributed" mode:
  `--node-external-ip`, `--flannel-backend=wireguard-native`, `--flannel-external-ip`. Each host
  forwards only what the cluster needs. No host routes and no sudo.
- **On the dev Mac everything is loopback**, except kubectl → `https://10.10.10.2:6443`:
  - push images to `localhost:5001`;
  - reach apps at `http://<app>-<env>.localhost:18080`. curl and Chromium resolve `*.localhost`
    to 127.0.0.1 themselves.
- Single-Mac variant: run `cluster-up.sh` with `SERVER_SSH=""` and `AGENT_IP=""`. The registry and
  ingress are then on the server VM's forwards.

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
  and `ingress.yaml`.
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
7. **DB credentials live in the namespace.**
   - `secrets.env` is gitignored.
   - deploy.sh recovers the oldest `db-credentials-*` secret when `secrets.env` is missing, so a
     fresh checkout doesn't lock itself out of the existing volume.
   - Only `env-reset.sh` rotates credentials, because it deletes the volume too.
8. **No NodePort or LoadBalancer Services in app namespaces** (quota 0). Traffic enters through the
   Traefik ingress, host `<app>-<env>.localhost`.
9. **dev and qa are isolated** by the `env-isolation` NetworkPolicy, which allows ingress only from
   the same namespace and from kube-system. Don't delete it, even though `admin` technically can.

## Keeping it clean (automatic — don't add ad-hoc cleanup)

| What accumulates | Who cleans it | When |
|---|---|---|
| Local Docker copies of pushed images | `deploy.sh` removes each tag right after `crane push` (build cache stays, so rebuilds stay fast) | every build |
| Registry images for the app | `scripts/k8s/registry-prune.sh`. Keeps digests in use in `<app>-dev`/`<app>-qa` plus the newest 5 HEALTHY deploys per env (rollback targets), and deletes failed, dirty and superseded builds | after every HEALTHY deploy; by hand with `--dry-run` / `--keep N` |
| Registry disk (layers of deleted images) | CronJob `sdlc-system/registry-gc` (`registry garbage-collect --delete-untagged`) | nightly 04:30 |
| Old generated ConfigMaps/Secrets (`<name>-<hash>`) | `deploy.sh` deletes those of its own generators that the current render doesn't reference | after every HEALTHY deploy |
| Finished migrate/seed Jobs and their pods | `ttlSecondsAfterFinished: 3600` (results are in `history.jsonl`) | 1 h after finishing |
| Old ReplicaSets | `revisionHistoryLimit: 3` (rollback is by digest, not ReplicaSet) | on rollout |
| `-dirty` image tags | only produced when a *build context* has uncommitted changes. Keep logs and outputs out of `services/*` | — |

Cleanup never runs after a failed or DEGRADED deploy, so everything is left in place for debugging.
Nothing ever deletes a namespace or a database volume except `env-reset.sh`.

## Endpoints

| | dev | qa |
|---|---|---|
| Web/API from the dev Mac (curl, Playwright/Chromium, iOS simulator via Safari*) | `http://<app>-dev.localhost:18080` | `http://<app>-qa.localhost:18080` |
| From the server Mac | `curl -H 'Host: <app>-dev.localhost' http://10.10.10.2:18080` | same with `-qa` |
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
| migrate: `password authentication failed` | Rule 7: `secrets.env` doesn't match the volume. Delete `secrets.env` and redeploy (recovers the oldest), or `env-reset.sh` |
| A node `NotReady` | The laptop slept or the link dropped. Pods reschedule after ~5 min; Traefik, CoreDNS and the registry are pinned to the server node |
| Anything else in the VM | `limactl shell sdlc-agent sudo journalctl -u k3s-agent`; on the server Mac `limactl shell sdlc-server sudo journalctl -u k3s` |

Verify the whole path at any time with `scripts/cluster-check.sh` (admin). For the framework itself,
run `tests/k8s-e2e.sh`.
