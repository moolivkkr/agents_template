#!/usr/bin/env python3
"""deploylib.py — structured state for scripts/k8s/*.sh (digest pinning, deploy history, evidence).

  set-images  <kustomization.yaml> name=repo@sha256:... ...   rewrite the managed images block
  get-images  <kustomization.yaml>                             print pinned name=repo@digest lines
  pick        <history.jsonl> [--differs name=ref ...]         print the newest HEALTHY entry (JSON);
                                                               with --differs, the newest HEALTHY one
                                                               whose images differ (= rollback target)
  keep        <history.jsonl> [--n N]                          print the image refs of the newest N HEALTHY
                                                               deploys (registry-prune.sh keeps these)
  stuck       [--digests sha256:...]  < kubectl get pods -o json
                                                               print "pod/container: reason: message" for
                                                               containers stuck in a state that never
                                                               resolves (only pods running the given digests)
  record      --root R --env E --ns NS --sha S --url U --verdict V --steps JSON --smoke JSON
              [--phase N] [--images name=ref ...]              append history, write the status marker
                                                               and (with --phase) the gate sidecar
  db-secrets  <secrets.env> [--recover FILE|-]                 create or converge the overlay's gitignored
                                                               secrets.env: the three Postgres role pairs
                                                               (see DB_ROLES). --recover reads `kubectl get
                                                               secrets -o json` when the file is missing.
                                                               Prints key names only, never a value
  db-access   < kubectl create --dry-run=client -o json -f rendered.yaml   (or any JSON List of objects)
                                                               refuse a render in which a workload can read
                                                               a database role it must not have (POLICY)
Evidence is written by code, never by an agent's prose:
  agent_state/deploy/<env>/history.jsonl         one line per deploy (promotion and rollback read it)
  agent_state/deploy/last-deploy-status.json     marker /accept and /status read (status HEALTHY|DEGRADED|FAILED)
  agent_state/phases/<N>/reports/deploy_<env>.{json,md} + an execution.jsonl line (agent deploy_<env>):
                                                 the sdlc.test-results/v1 evidence verify-gate.sh reads
"""
import argparse, base64, datetime, json, os, re, secrets, sys, tempfile

BLOCK = re.compile(r"(# BEGIN images[^\n]*\n)(.*?)(# END images)", re.S)

# ── database roles ────────────────────────────────────────────────────────────────────────────────────
# One secret (db-credentials, from the overlay's gitignored secrets.env) holds three user/password pairs;
# each workload references only the keys of its own role (POLICY, enforced on every render by db-access).
#   SUPERUSER  bootstrap superuser: Postgres itself and the db-roles Job (deploy/k8s/base/db-roles.sh)
#   MIGRATOR   owns the schema and every table, NOSUPERUSER BYPASSRLS: db-migrate, db-seed (the db-* Jobs)
#   APP        the services: NOSUPERUSER NOBYPASSRLS, owns nothing, so FORCE row-level security applies
DB_ROLES = (("SUPERUSER", "postgres"), ("MIGRATOR", "app_migrator"), ("APP", "app_runtime"))
DB_SECRET = re.compile(r"^db-credentials(-[a-z0-9]{10})?$")   # generator name, bare or hash-suffixed
ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
PASSWORD = re.compile(r"^[A-Za-z0-9._~-]{16,}$")   # interpolated unescaped into DATABASE_URL


def read_env(path):
    out = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def recover_secret(src):
    """The db-credentials secret to rebuild secrets.env from (a fresh checkout of an env that exists).
    Newest one with the three-role keys: every such secret carries the superuser pair the volume was
    initialised with, and the newest has the role passwords db-roles last set. Else the OLDEST one in the
    old one-superuser layout (DB_USER/DB_PASSWORD), which is the pair the volume was initialised with."""
    doc = json.load(sys.stdin if src == "-" else open(src))
    items = sorted((s for s in doc.get("items", []) if DB_SECRET.match(s.get("metadata", {}).get("name", ""))),
                   key=lambda s: s["metadata"].get("creationTimestamp", ""))
    current = [s for s in items if "DB_SUPERUSER_PASSWORD" in (s.get("data") or {})]
    legacy = [s for s in items if "DB_PASSWORD" in (s.get("data") or {})]
    pick = current[-1] if current else (legacy[0] if legacy else None)
    if not pick:
        return None, None
    return {k: base64.b64decode(v).decode() for k, v in pick["data"].items()}, pick["metadata"]["name"]


def db_secrets(path, recover):
    notes, env = [], None
    if os.path.exists(path):
        env = read_env(path)
    elif recover:
        env, name = recover_secret(recover)
        if env is not None:
            notes.append(f"recovered from secret/{name}")
    env = dict(env or {})
    before = dict(env)
    if "DB_PASSWORD" in env and not env.get("DB_SUPERUSER_PASSWORD"):
        # the one-superuser layout: that pair initialised the volume, so it stays the superuser
        env["DB_SUPERUSER_USER"] = env.get("DB_USER") or "app"
        env["DB_SUPERUSER_PASSWORD"] = env["DB_PASSWORD"]
        notes.append("kept the old DB_USER/DB_PASSWORD as the superuser pair")
    for k in ("DB_USER", "DB_PASSWORD"):   # gone on purpose: a manifest still reading them fails closed
        if env.pop(k, None) is not None:
            notes.append(f"dropped {k}")
    for role, default in DB_ROLES:
        u, p = f"DB_{role}_USER", f"DB_{role}_PASSWORD"
        if not env.get(u):
            env[u] = default
        if not env.get(p):
            env[p] = secrets.token_hex(24)
            notes.append(f"generated the {role.lower()} password")
    users = [env[f"DB_{r}_USER"] for r, _ in DB_ROLES]
    bad = [u for u in users if not ROLE_NAME.match(u)]
    if bad or len(set(users)) != len(users):
        sys.exit(f"deploylib: {path}: the superuser, migrator and app users must be three different lowercase role names (got {', '.join(users)})")
    if any(not PASSWORD.match(env[f"DB_{r}_PASSWORD"]) for r, _ in DB_ROLES):
        sys.exit(f"deploylib: {path}: every DB_*_PASSWORD must be 16+ characters of [A-Za-z0-9._~-] (it goes into DATABASE_URL)")
    if env == before and os.path.exists(path):
        return
    order = [f"DB_{r}_{x}" for r, _ in DB_ROLES for x in ("USER", "PASSWORD")]
    body = "".join(f"{k}={env[k]}\n" for k in order) + "".join(f"{k}={v}\n" for k, v in env.items() if k not in order)
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".secrets.")   # 0600, then atomically into place
    with os.fdopen(fd, "w") as f:
        f.write(body)
    os.replace(tmp, path)
    print(f"deploylib: {path}: {'; '.join(notes) or 'rewritten'} (gitignored; values not shown)", file=sys.stderr)


def pod_spec(o):
    s = o.get("spec") or {}
    kind = o.get("kind")
    if kind == "CronJob":
        return ((((s.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec")) or {}
    if kind in ("Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "ReplicationController", "Job"):
        return ((s.get("template") or {}).get("spec")) or {}
    return s if kind == "Pod" else None


def db_access_problems(objs):
    """POLICY: who may read which role's credentials from db-credentials.
      superuser keys  StatefulSet/postgres and CronJob/db-roles only
      migrator keys   StatefulSet/postgres and the db-* Job templates (CronJob/Job named db-*) only:
                      never a service (Deployment, other StatefulSets, DaemonSet)
      app keys        anyone
      never           envFrom or a volume of the whole secret (that is all three roles), or the old
                      one-superuser keys DB_USER/DB_PASSWORD"""
    out = []
    for o in objs:
        ps = pod_spec(o)
        if ps is None:
            continue
        kind, name = o.get("kind"), (o.get("metadata") or {}).get("name", "")
        who = f"{kind}/{name}"
        for c in (ps.get("initContainers") or []) + (ps.get("containers") or []):
            where = f"{who} container {c.get('name')}"
            for ef in c.get("envFrom") or []:
                if DB_SECRET.match((ef.get("secretRef") or {}).get("name", "")):
                    out.append(f"{where}: envFrom the whole db-credentials secret (all three roles); reference your own keys with secretKeyRef")
            for e in c.get("env") or []:
                ref = (e.get("valueFrom") or {}).get("secretKeyRef") or {}
                if not DB_SECRET.match(ref.get("name", "")):
                    continue
                key = ref.get("key", "")
                if key.startswith("DB_SUPERUSER_") and who not in ("StatefulSet/postgres", "CronJob/db-roles"):
                    out.append(f"{where}: reads {key}; only Postgres and the db-roles Job may hold the superuser")
                elif key.startswith("DB_MIGRATOR_") and who != "StatefulSet/postgres" and not (kind in ("CronJob", "Job") and name.startswith("db-")):
                    out.append(f"{where}: reads {key}; only the db-* Job templates (migrate, seed) may hold the migrator, a service uses DB_APP_*")
                elif key in ("DB_USER", "DB_PASSWORD"):
                    out.append(f"{where}: reads {key}, the old one-superuser key; services use DB_APP_USER/DB_APP_PASSWORD, migrate and seed DB_MIGRATOR_*")
        for v in ps.get("volumes") or []:
            if DB_SECRET.match((v.get("secret") or {}).get("secretName", "")):
                out.append(f"{who}: mounts the whole db-credentials secret as volume {v.get('name')}")
    return out


def json_stream(text):
    """Objects from one JSON value or several back to back (`kubectl create -o json` prints one per object);
    a List contributes its items."""
    dec, i, out = json.JSONDecoder(), 0, []
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i == len(text):
            return out
        v, i = dec.raw_decode(text, i)
        for o in (v if isinstance(v, list) else [v]):
            out.extend(o.get("items", []) if o.get("kind", "").endswith("List") or "items" in o and "kind" not in o else [o])


def db_access():
    objs = json_stream(sys.stdin.read())
    if not objs:
        sys.exit("db-access: no objects on stdin (expected the rendered manifests as JSON)")
    problems = db_access_problems(objs)
    for p in problems:
        print(f"db-access: {p}", file=sys.stderr)
    if problems:
        sys.exit(1)


def pairs(items):
    out = {}
    for it in items or []:
        name, ref = it.split("=", 1)
        if "@sha256:" not in ref:
            sys.exit(f"deploylib: {it} is not digest-pinned (repo@sha256:...)")
        out[name] = ref
    return out


def set_images(path, items):
    imgs = pairs(items)
    s = open(path).read()
    lines = "".join(f"- {{name: {n}, newName: {r.split('@')[0]}, digest: {r.split('@')[1]}}}\n"
                    for n, r in sorted(imgs.items()))
    new, n = BLOCK.subn(lambda m: m.group(1) + "images:\n" + lines + m.group(3), s)
    if n != 1:
        sys.exit(f"deploylib: {path}: '# BEGIN images' / '# END images' markers not found")
    open(path, "w").write(new)


def get_images(path):
    m = BLOCK.search(open(path).read())
    if not m:
        sys.exit(f"deploylib: {path}: images markers not found")
    for name, repo, digest in re.findall(r"name:\s*([\w.-]+),\s*newName:\s*([^,}\s]+),\s*digest:\s*(sha256:[0-9a-f]+)", m.group(2)):
        print(f"{name}={repo}@{digest}")


def pick(path, differs):
    try:
        entries = [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        entries = []
    current = pairs(differs) if differs else None
    for e in reversed(entries):
        if e.get("verdict") != "HEALTHY":
            continue
        if current is not None and e.get("images") == current:
            continue
        print(json.dumps(e))
        return
    sys.exit(1)


def keep(path, n):
    try:
        entries = [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return
    for e in [e for e in entries if e.get("verdict") == "HEALTHY"][-n:]:
        for ref in e.get("images", {}).values():
            print(ref)


STUCK = {"CreateContainerConfigError", "CreateContainerError", "ErrImagePull", "ImagePullBackOff",
         "InvalidImageName", "CrashLoopBackOff", "ErrImageNeverPull"}


def stuck(digests):
    pods = json.load(sys.stdin).get("items", [])
    for pod in pods:
        images = {c["name"]: c.get("image", "") for c in pod["spec"].get("containers", [])}
        for cs in pod.get("status", {}).get("containerStatuses", []) or []:
            w = (cs.get("state") or {}).get("waiting") or {}
            if w.get("reason") in STUCK and (not digests or any(d in images.get(cs["name"], "") for d in digests)):
                print(f"{pod['metadata']['name']}/{cs['name']}: {w['reason']}: {w.get('message', '')[:300]}")
                return


def record(a):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    steps, smoke = json.loads(a.steps), json.loads(a.smoke)
    dirty = str(a.dirty).lower() == "true"
    entry = {"ts": now, "env": a.env, "namespace": a.ns, "git_sha": a.sha, "code_sha": a.code_sha, "dirty": dirty,
             "url": a.url, "images": pairs(a.images), "mode": a.mode, "steps": steps, "smoke": smoke,
             "verdict": a.verdict}
    state = os.path.join(a.root, "agent_state", "deploy")
    os.makedirs(os.path.join(state, a.env), exist_ok=True)
    with open(os.path.join(state, a.env, "history.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    failing = [k for k, v in steps.items() if v != "ok"] + [x["path"] for x in smoke.get("failures", [])]
    with open(os.path.join(state, "last-deploy-status.json"), "w") as f:
        json.dump({"target": a.env, "status": a.verdict, "ts": now, "namespace": a.ns, "git_sha": a.sha,
                   "code_sha": a.code_sha, "url": a.url, "digests": entry["images"], "failing": ", ".join(failing)},
                  f, indent=1)
    if a.phase:
        # Gate evidence (sdlc.test-results/v1) + an execution.jsonl line, so verify-gate.sh actually reads it:
        # agent "deploy_<env>", report reports/deploy_<env>.md, sidecar reports/deploy_<env>.json.
        pdir = os.path.join(a.root, "agent_state", "phases", str(a.phase))
        rep = os.path.join(pdir, "reports")
        os.makedirs(rep, exist_ok=True)
        cases = [{"name": f"step:{k}", "verdict": "PASS" if v == "ok" else "FAIL", "priority": "HIGH"} for k, v in steps.items()]
        cases += [{"name": f"smoke:{x['path']}", "verdict": "FAIL", "priority": "HIGH", "detail": x.get("got", "")}
                  for x in smoke.get("failures", [])]
        total = len(steps) + smoke.get("total", 0)
        failed = sum(1 for v in steps.values() if v != "ok") + smoke.get("failed", 0)
        with open(os.path.join(rep, f"deploy_{a.env}.json"), "w") as f:
            json.dump({"schema": "sdlc.test-results/v1", "tier": "deploy", "verdict": "PASS" if a.verdict == "HEALTHY" else "FAIL",
                       "deploy_status": a.verdict, "total": total, "passed": total - failed, "failed": failed,
                       "skipped": 0, "flaky": 0, "code_sha": a.code_sha, "dirty": dirty, "env": a.env,
                       "base_url": a.url, "namespace": a.ns, "digests": entry["images"], "mode": a.mode,
                       "cases": cases, "ts": now}, f, indent=1)
        with open(os.path.join(rep, f"deploy_{a.env}.md"), "w") as f:
            f.write(f"# deploy_{a.env} — {a.verdict}\n\n- namespace: {a.ns}\n- url: {a.url}\n- mode: {a.mode}\n"
                    f"- code_sha: {a.code_sha}\n- images: {json.dumps(entry['images'])}\n- failing: {', '.join(failing) or 'none'}\n")
        with open(os.path.join(pdir, "execution.jsonl"), "a") as f:
            f.write(json.dumps({"agent": f"deploy_{a.env}", "phase": int(a.phase) if str(a.phase).isdigit() else a.phase,
                                "status": "completed" if a.verdict == "HEALTHY" else "failed",
                                "report": f"agent_state/phases/{a.phase}/reports/deploy_{a.env}.md", "ts": now}) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("set-images"); p.add_argument("path"); p.add_argument("images", nargs="*")
    p = sub.add_parser("get-images"); p.add_argument("path")
    p = sub.add_parser("pick"); p.add_argument("history"); p.add_argument("--differs", nargs="*")
    p = sub.add_parser("keep"); p.add_argument("history"); p.add_argument("--n", type=int, default=5)
    p = sub.add_parser("stuck"); p.add_argument("--digests", nargs="*")
    p = sub.add_parser("record")
    for k in ("root", "env", "ns", "sha", "url", "verdict", "steps", "smoke"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--mode", default="deploy"); p.add_argument("--phase"); p.add_argument("--images", nargs="*")
    p.add_argument("--code-sha", default=""); p.add_argument("--dirty", default="false")
    p = sub.add_parser("db-secrets"); p.add_argument("path"); p.add_argument("--recover")
    sub.add_parser("db-access")
    a = ap.parse_args()
    if a.cmd == "set-images": set_images(a.path, a.images)
    elif a.cmd == "get-images": get_images(a.path)
    elif a.cmd == "pick": pick(a.history, a.differs)
    elif a.cmd == "keep": keep(a.history, a.n)
    elif a.cmd == "stuck": stuck(a.digests)
    elif a.cmd == "db-secrets": db_secrets(a.path, a.recover)
    elif a.cmd == "db-access": db_access()
    else: record(a)


if __name__ == "__main__":
    main()
