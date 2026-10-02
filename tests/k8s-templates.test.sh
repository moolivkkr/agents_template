#!/usr/bin/env bash
# k8s-templates.test.sh — static checks for .claude/templates/k8s: scripts parse under macOS bash 3.2,
# Lima templates validate (when limactl is installed), cluster manifests pass kubeconform (when
# installed; CRDs like HelmChartConfig are skipped). Run: bash tests/k8s-templates.test.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S="$REPO/.claude/templates/k8s"
PASS=0; FAIL=0; SKIP=0
ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
skip() { echo "  - skip: $1"; SKIP=$((SKIP+1)); }

for f in "$K8S"/scripts/*.sh "$K8S"/app/instantiate.sh "$K8S"/app/scripts/k8s/*.sh; do
  /bin/bash -n "$f" 2>/dev/null && ok "bash 3.2 parses $(basename "$f")" || bad "$(basename "$f") does not parse under /bin/bash"
  [ -x "$f" ] && ok "$(basename "$f") is executable" || bad "$(basename "$f") is not executable"
done
# bash 3.2 + set -u: "${arr[@]}" on an empty array aborts; scripts must use ${arr[@]+"${arr[@]}"}
for f in "$K8S"/scripts/*.sh "$K8S"/app/scripts/k8s/*.sh; do
  if grep -q 'set -[a-z]*u' "$f" && grep -nE '"\$\{[A-Z_]+_ARGS\[@\]\}"' "$f" | grep -v '+"' >/dev/null; then
    bad "$(basename "$f"): *_ARGS[@] expanded without the empty-array guard"
  fi
done

if command -v limactl >/dev/null; then
  for f in "$K8S"/lima/*.yaml; do
    limactl validate "$f" >/dev/null 2>&1 && ok "limactl validate $(basename "$f")" || bad "limactl validate $(basename "$f")"
  done
else skip "limactl not installed"; fi

# Lima applies the FIRST matching portForwards rule: the same guestPort+proto twice is dead config
python3 - "$K8S"/lima/*.yaml <<'PY' && ok "no duplicate guestPort forwards in Lima templates" || bad "duplicate guestPort forward (Lima uses the first match only)"
import re, sys
bad = False
for p in sys.argv[1:]:
    seen = set()
    for block in re.split(r"\n- ", open(p).read().split("portForwards:", 1)[1].split("\ncopyToHost", 1)[0]):
        m = re.search(r"guestPort:\s*(\d+)", block)
        if not m: continue
        key = (m.group(1), (re.search(r"proto:\s*(\w+)", block) or [None, "tcp"])[1])
        if key in seen: print(f"{p}: guestPort {key}"); bad = True
        seen.add(key)
sys.exit(1 if bad else 0)
PY

KC="$(command -v kubeconform || ls "$HOME/go/bin/kubeconform" 2>/dev/null)"
if [ -n "$KC" ]; then
  "$KC" -strict -summary -skip HelmChartConfig -ignore-missing-schemas "$K8S"/cluster/*.yaml >/dev/null 2>&1 \
    && ok "kubeconform cluster/*.yaml" || bad "kubeconform cluster/*.yaml: $("$KC" -strict -skip HelmChartConfig "$K8S"/cluster/*.yaml 2>&1 | head -3)"
else skip "kubeconform not installed"; fi

# ── app layer: instantiate the fixture, render both overlays, validate, exercise deploylib ──────────
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
bash "$K8S/app/instantiate.sh" "$W" demo >/dev/null && ok "instantiate.sh demo" || bad "instantiate.sh failed"
grep -rq "__APP__" "$W" && bad "unreplaced __APP__ placeholders" || ok "all __APP__ placeholders replaced"
grep -qxF 'deploy/k8s/overlays/*/secrets.env' "$W/.gitignore" && ok "secrets.env gitignored" || bad "secrets.env not gitignored"
again="$(bash "$K8S/app/instantiate.sh" "$W" demo)"   # (not piped into grep -q: SIGPIPE + pipefail)
echo "$again" | grep -q "kept" && ! echo "$again" | grep -q "created" && ok "instantiate.sh never overwrites" || bad "instantiate.sh overwrote files"
KUBECTL="$(command -v kubectl || ls /Applications/Docker.app/Contents/Resources/bin/kubectl 2>/dev/null)"
for e in dev qa; do
  python3 "$W/scripts/k8s/deploylib.py" db-secrets "$W/deploy/k8s/overlays/$e/secrets.env" 2>/dev/null
  if [ -n "$KUBECTL" ] && "$KUBECTL" kustomize "$W/deploy/k8s/overlays/$e" > "$W/$e.yaml" 2>"$W/$e.err"; then
    grep -q "namespace: demo-$e" "$W/$e.yaml" && grep -q "host: demo-$e.localhost" "$W/$e.yaml" \
      && ok "overlay $e renders (namespace demo-$e, host demo-$e.localhost)" || bad "overlay $e: wrong namespace/host"
    [ -n "$KC" ] && { "$KC" -strict -summary "$W/$e.yaml" >/dev/null 2>&1 && ok "kubeconform overlay $e" || bad "kubeconform overlay $e"; }
  elif [ -n "$KUBECTL" ]; then bad "overlay $e does not render: $(head -2 "$W/$e.err")"
  else skip "kubectl not installed (overlay $e)"; fi
done
DL="$W/scripts/k8s/deploylib.py"; KZ="$W/deploy/k8s/overlays/dev/kustomization.yaml"; D1=sha256:$(printf a%.0s {1..64}); D2=sha256:$(printf b%.0s {1..64})
python3 "$DL" set-images "$KZ" "api=localhost:5001/demo/api@$D1" && [ "$(python3 "$DL" get-images "$KZ")" = "api=localhost:5001/demo/api@$D1" ] \
  && ok "deploylib set-images/get-images round-trip" || bad "deploylib set/get-images"
python3 "$DL" set-images "$KZ" "api=localhost:5001/demo/api:latest" 2>/dev/null && bad "deploylib accepted a tag (must be digest)" || ok "deploylib refuses non-digest refs"
H="$W/h.jsonl"
printf '%s\n' "{\"verdict\":\"HEALTHY\",\"git_sha\":\"v1\",\"images\":{\"api\":\"r@$D1\"}}" "{\"verdict\":\"HEALTHY\",\"git_sha\":\"v2\",\"images\":{\"api\":\"r@$D2\"}}" "{\"verdict\":\"DEGRADED\",\"git_sha\":\"v3\",\"images\":{}}" > "$H"
[ "$(python3 "$DL" pick "$H" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')" = v2 ] && ok "pick: newest HEALTHY (skips DEGRADED)" || bad "pick newest HEALTHY"
[ "$(python3 "$DL" pick "$H" --differs "api=r@$D2" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')" = v1 ] && ok "pick --differs: rollback target" || bad "pick --differs"

# ── two database roles: secrets, initdb/reconcile wiring, who may read which role ───────────────────
# (live proof on real Postgres containers: tests/k8s-db-roles.sh; on the cluster: tests/k8s-e2e.sh)
RS="$K8S/app/deploy/k8s/base/db-roles.sh"
/bin/bash -n "$RS" 2>/dev/null && [ -x "$RS" ] && [ -x "$W/deploy/k8s/base/db-roles.sh" ] \
  && ok "db-roles.sh parses under bash 3.2 and is executable (template and instantiated copy)" || bad "db-roles.sh does not parse or is not executable"
S="$W/s.env"
out="$(python3 "$DL" db-secrets "$S" 2>&1)"
python3 - "$S" "$out" <<'PY' && ok "db-secrets: new env gets postgres/app_migrator/app_runtime, 48-hex passwords, file 0600, values never printed" || bad "db-secrets fresh: $out"
import os, re, stat, sys
env = dict(l.strip().split("=", 1) for l in open(sys.argv[1]) if "=" in l)
assert [env[f"DB_{r}_USER"] for r in ("SUPERUSER", "MIGRATOR", "APP")] == ["postgres", "app_migrator", "app_runtime"], env.keys()
pws = [env[f"DB_{r}_PASSWORD"] for r in ("SUPERUSER", "MIGRATOR", "APP")]
assert all(re.fullmatch(r"[0-9a-f]{48}", p) for p in pws) and len(set(pws)) == 3
assert stat.S_IMODE(os.stat(sys.argv[1]).st_mode) == 0o600
assert not any(p in sys.argv[2] for p in pws)
PY
before="$(cat "$S")"; out="$(python3 "$DL" db-secrets "$S" 2>&1)"
[ "$(cat "$S")" = "$before" ] && [ -z "$out" ] && ok "db-secrets re-run: file unchanged, nothing printed" || bad "db-secrets re-run changed the file: $out"
printf 'DB_USER=app\nDB_PASSWORD=legacypassword0123456789\n' > "$W/old.env"
python3 "$DL" db-secrets "$W/old.env" 2>/dev/null
grep -qx 'DB_SUPERUSER_USER=app' "$W/old.env" && grep -qx 'DB_SUPERUSER_PASSWORD=legacypassword0123456789' "$W/old.env" \
  && ! grep -qE '^DB_(USER|PASSWORD)=' "$W/old.env" && grep -q '^DB_MIGRATOR_PASSWORD=' "$W/old.env" && grep -q '^DB_APP_PASSWORD=' "$W/old.env" \
  && ok "db-secrets upgrades the old DB_USER/DB_PASSWORD file: that pair stays the superuser, migrator + app added, old keys dropped" || bad "db-secrets legacy upgrade: $(cut -d= -f1 "$W/old.env" | tr '\n' ' ')"
python3 - "$DL" "$W" <<'PY' && ok "db-secrets --recover: newest three-role secret wins; with only old-layout secrets the OLDEST pair becomes the superuser" || bad "db-secrets --recover picked the wrong secret"
import base64, json, subprocess, sys
dl, w = sys.argv[1], sys.argv[2]
b = lambda s: base64.b64encode(s.encode()).decode()
def sec(name, ts, **kv): return {"metadata": {"name": name, "creationTimestamp": ts}, "data": {k: b(v) for k, v in kv.items()}}
old1 = sec("db-credentials-aaaaaaaaaa", "2026-01-01T00:00:00Z", DB_USER="app", DB_PASSWORD="oldestpassword00000000")
old2 = sec("db-credentials-bbbbbbbbbb", "2026-02-01T00:00:00Z", DB_USER="app", DB_PASSWORD="newerpassword000000000")
new = lambda n, ts, m: sec(n, ts, DB_SUPERUSER_USER="app", DB_SUPERUSER_PASSWORD="oldestpassword00000000", DB_MIGRATOR_USER="app_migrator",
                           DB_MIGRATOR_PASSWORD=m, DB_APP_USER="app_runtime", DB_APP_PASSWORD="apppassword0000000000")
other = sec("api-keys-cccccccccc", "2026-05-01T00:00:00Z", DB_SUPERUSER_PASSWORD="notthisone000000000000")
def run(items, path):
    subprocess.run([sys.executable, dl, "db-secrets", path, "--recover", "-"], input=json.dumps({"items": items}), text=True, check=True, capture_output=True)
    return dict(l.strip().split("=", 1) for l in open(path) if "=" in l)
e = run([old2, new("db-credentials-dddddddddd", "2026-03-01T00:00:00Z", "migrator1111111111111"), old1,
         new("db-credentials-eeeeeeeeee", "2026-04-01T00:00:00Z", "migrator2222222222222"), other], f"{w}/r1.env")
assert e["DB_MIGRATOR_PASSWORD"] == "migrator2222222222222" and e["DB_SUPERUSER_PASSWORD"] == "oldestpassword00000000", e
e = run([old2, old1], f"{w}/r2.env")
assert (e["DB_SUPERUSER_USER"], e["DB_SUPERUSER_PASSWORD"]) == ("app", "oldestpassword00000000") and "DB_PASSWORD" not in e, e
PY
printf 'DB_SUPERUSER_USER=postgres\nDB_SUPERUSER_PASSWORD=aaaaaaaaaaaaaaaaaaaa\nDB_APP_USER=postgres\n' > "$W/dup.env"
python3 "$DL" db-secrets "$W/dup.env" >/dev/null 2>&1 && bad "db-secrets accepted the app role named like the superuser" || ok "db-secrets refuses two roles with one name"
printf 'DB_APP_PASSWORD=has@and/inside0000000\n' > "$W/url.env"
python3 "$DL" db-secrets "$W/url.env" >/dev/null 2>&1 && bad "db-secrets accepted a password that breaks DATABASE_URL" || ok "db-secrets refuses a password with URL-special characters"
to_json() {  # rendered multi-document YAML -> {"items": [...]}: PyYAML, else yq; else the checks below skip
  if python3 -c 'import yaml' 2>/dev/null; then
    python3 -c 'import json,sys,yaml; print(json.dumps({"items":[d for d in yaml.safe_load_all(open(sys.argv[1])) if d]}))' "$1"
  else yq ea -o=json -I=0 '[.] | {"items": .}' "$1"; fi
}
if python3 -c 'import yaml' 2>/dev/null || command -v yq >/dev/null; then
  for e in dev qa; do
    [ -s "$W/$e.yaml" ] || continue
    to_json "$W/$e.yaml" > "$W/$e.json"
    python3 "$DL" db-access < "$W/$e.json" 2>"$W/$e.access" && ok "db-access: overlay $e passes the role policy" || bad "db-access $e: $(cat "$W/$e.access")"
    python3 - "$W/$e.json" "$RS" "$K8S/app/deploy/k8s/base/db-rls-check.sh" > "$W/$e.checks" 2>&1 <<'PY' || echo "FAIL|role checks crashed: $(tail -1 "$W/$e.checks")" >> "$W/$e.checks"
import json, sys
objs = json.load(open(sys.argv[1]))["items"]
by = {f"{o['kind']}/{o['metadata']['name']}": o for o in objs}
def spec(o): return o["spec"]["jobTemplate"]["spec"]["template"]["spec"] if o["kind"] == "CronJob" else o["spec"]["template"]["spec"]
def keys(o):
    s = spec(o)
    return sorted(e["valueFrom"]["secretKeyRef"]["key"] for c in s.get("initContainers", []) + s["containers"] for e in c.get("env", [])
                  if (e.get("valueFrom") or {}).get("secretKeyRef", {}).get("name", "").startswith("db-credentials"))
def check(cond, msg): print(("PASS" if cond else "FAIL") + "|" + msg)
su = sorted(w for w, o in by.items() if o["kind"] in ("Deployment", "StatefulSet", "CronJob", "Job", "DaemonSet") and any(k.startswith("DB_SUPERUSER_") for k in keys(o)))
check(su == ["CronJob/db-roles", "StatefulSet/postgres"], f"only Postgres and the db-roles Job read the superuser ({', '.join(su)})")
check(keys(by["Deployment/api"]) == ["DB_APP_PASSWORD", "DB_APP_USER"], f"the API reads only DB_APP_* ({', '.join(keys(by['Deployment/api']))}), never the migrator")
mig = {w: keys(by[w]) for w in ("CronJob/db-migrate", "CronJob/db-seed")}
check(all(k == ["DB_MIGRATOR_PASSWORD", "DB_MIGRATOR_USER"] for k in mig.values()), "db-migrate and db-seed read only DB_MIGRATOR_*")
pg, rj = spec(by["StatefulSet/postgres"]), spec(by["CronJob/db-roles"])
init = [m for m in pg["containers"][0]["volumeMounts"] if m["mountPath"] == "/docker-entrypoint-initdb.d"]
vol = {v["name"]: v for v in pg["volumes"]}
check(len(init) == 1 and vol[init[0]["name"]]["configMap"] == {"name": "db-roles", "defaultMode": 0o555},
      "Postgres mounts ConfigMap db-roles (0555) at /docker-entrypoint-initdb.d: initdb runs db-roles.sh")
rv = {v["name"]: v for v in rj["volumes"]}
check(rj["containers"][0]["command"] == ["bash", "/db-roles/db-roles.sh"] and rv["db-roles"]["configMap"]["name"] == "db-roles"
      and rj["containers"][0]["securityContext"].get("readOnlyRootFilesystem") is True,
      "the db-roles Job runs the same script from the same ConfigMap (read-only root, own /tmp)")
cm = by.get("ConfigMap/db-roles")
check(cm is not None and cm["data"]["db-roles.sh"] == open(sys.argv[2]).read(), "ConfigMap db-roles (no hash suffix) carries db-roles.sh byte for byte")
check(cm is not None and set(cm["data"]) == {"db-roles.sh"}, "ConfigMap db-roles holds db-roles.sh only (initdb runs every *.sh in it)")
rc = by.get("CronJob/db-rls-check")
check(rc is not None and keys(rc) == ["DB_APP_PASSWORD", "DB_APP_USER"], f"db-rls-check reads only DB_APP_* ({', '.join(keys(rc)) if rc else 'missing'}): it proves what the runtime role sees (D-001)")
rcs = spec(rc) if rc else {"containers": [{}], "volumes": []}
rcv = {v["name"]: v for v in rcs.get("volumes", [])}
check(rcs["containers"][0].get("command") == ["bash", "/db-rls-check/db-rls-check.sh"] and rcv.get("db-rls-check", {}).get("configMap", {}).get("name") == "db-rls-check"
      and rcs["containers"][0].get("securityContext", {}).get("readOnlyRootFilesystem") is True,
      "the db-rls-check Job runs db-rls-check.sh from its own ConfigMap (read-only root)")
cr = by.get("ConfigMap/db-rls-check")
check(cr is not None and cr["data"]["db-rls-check.sh"] == open(sys.argv[3]).read(), "ConfigMap db-rls-check (no hash suffix) carries db-rls-check.sh byte for byte")
PY
    while IFS='|' read -r v m; do [ "$v" = PASS ] && ok "$e: $m" || bad "$e: ${m:-$v}"; done < "$W/$e.checks"   # (no heredoc inside <(...): bash 3.2 mangles it)
  done
  python3 - "$DL" "$W/dev.json" <<'PY' && ok "db-access refuses: API with the migrator, a worker with the superuser, envFrom/volume of the whole secret, old DB_PASSWORD, a non-db-* CronJob with the migrator, no db-rls-check, db-rls-check as the migrator; reads kubectl's back-to-back JSON" || bad "db-access let a forbidden render through"
import copy, json, subprocess, sys
dl, objs = sys.argv[1], json.load(open(sys.argv[2]))["items"]
api = next(o for o in objs if o["kind"] == "Deployment" and o["metadata"]["name"] == "api")
secret = next(o["metadata"]["name"] for o in objs if o["kind"] == "Secret")
def ref(key): return {"name": "X", "valueFrom": {"secretKeyRef": {"name": secret, "key": key}}}
def access(items, stream=False):
    data = "\n".join(json.dumps(o, indent=1) for o in items) if stream else json.dumps({"kind": "List", "items": items})
    return subprocess.run([sys.executable, dl, "db-access"], input=data, text=True, capture_output=True).returncode
def mutate(f):
    a = copy.deepcopy(api); f(a); return [o for o in objs if o is not api] + [a]
c = lambda a: a["spec"]["template"]["spec"]["containers"][0]
bad = {
  "api+migrator": mutate(lambda a: c(a)["env"].append(ref("DB_MIGRATOR_PASSWORD"))),
  "worker+superuser": mutate(lambda a: (a["metadata"].update(name="worker"), c(a)["env"].append(ref("DB_SUPERUSER_PASSWORD")))),
  "envFrom": mutate(lambda a: c(a).setdefault("envFrom", []).append({"secretRef": {"name": secret}})),
  "secret volume": mutate(lambda a: a["spec"]["template"]["spec"].setdefault("volumes", []).append({"name": "s", "secret": {"secretName": secret}})),
  "old key": mutate(lambda a: c(a)["env"].append(ref("DB_PASSWORD"))),
}
cron = copy.deepcopy(next(o for o in objs if o["kind"] == "CronJob" and o["metadata"]["name"] == "db-migrate"))
cron["metadata"]["name"] = "nightly-report"
bad["non-db cronjob+migrator"] = objs + [cron]
rls = next(o for o in objs if o["kind"] == "CronJob" and o["metadata"]["name"] == "db-rls-check")
bad["no db-rls-check"] = [o for o in objs if o is not rls]
rls_mig = copy.deepcopy(rls)
for e in rls_mig["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["env"]:
    if (e.get("valueFrom") or {}).get("secretKeyRef", {}).get("key", "").startswith("DB_APP_"):
        e["valueFrom"]["secretKeyRef"]["key"] = e["valueFrom"]["secretKeyRef"]["key"].replace("DB_APP_", "DB_MIGRATOR_")
bad["db-rls-check as the migrator"] = [o for o in objs if o is not rls] + [rls_mig]
assert access(objs) == 0 and access(objs, stream=True) == 0, "clean render refused"
failed = [k for k, items in bad.items() if access(items) == 0]
assert not failed, failed
PY
else skip "neither PyYAML nor yq installed (rendered-manifest role checks)"; fi
DS="$K8S/app/scripts/k8s/deploy.sh"
r="$(grep -n 'run_job db-roles' "$DS" | head -1 | cut -d: -f1)"; m="$(grep -n 'run_job db-migrate' "$DS" | head -1 | cut -d: -f1)"
[ -n "$r" ] && [ -n "$m" ] && [ "$r" -lt "$m" ] && ok "deploy.sh runs the db-roles Job before db-migrate" || bad "deploy.sh: db-roles not run before migrate"
sd="$(grep -n 'run_job db-seed' "$DS" | head -1 | cut -d: -f1)"; rl="$(grep -n 'run_job db-rls-check' "$DS" | head -1 | cut -d: -f1)"; ro="$(grep -n 'wait_rollout "$d"' "$DS" | head -1 | cut -d: -f1)"
[ -n "$sd" ] && [ -n "$rl" ] && [ -n "$ro" ] && [ "$sd" -lt "$rl" ] && [ "$rl" -lt "$ro" ] && ok "deploy.sh runs db-rls-check after seed and before the rollout (D-001)" || bad "deploy.sh: db-rls-check missing or out of order"
grep -q 'python3 "$DL" db-access' "$DS" && grep -q 'check-ignore -q "$SECRETS"' "$DS" \
  && ok "deploy.sh checks every render with db-access and refuses a secrets.env git would track" || bad "deploy.sh lacks the db-access or gitignore guard"

echo "────────────────────────────────────────────"
echo "k8s-templates.test.sh: $PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" -eq 0 ]
