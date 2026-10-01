#!/usr/bin/env bash
# k8s-e2e.sh — end-to-end proof of the k8s deploy layer on the LIVE sdlc lab cluster, using the
# throwaway fixture in tests/fixtures/k8s-hello. Not part of run-all.sh (needs the cluster, ~3 min).
#
# Runs as the AGENT would: agent kubeconfig (~/.kube/sdlc-lab.json), sdlc-guard's PATH shims first on
# PATH so every kubectl inside the scripts is re-checked by the guard. Prereqs (human, once):
# cluster-up.sh, app-namespaces.sh hello.
#
#   1 deploy dev (build)          HEALTHY, seeded data served through the ingress, phase sidecar PASS;
#                                 two DB roles: the API reads only DB_APP_* and runs under FORCE RLS (a
#                                 tenant sees only its notes), app_migrator owns every table, app_runtime
#                                 is NOSUPERUSER NOBYPASSRLS, the db-roles Job found nothing to change
#   2 deploy qa (promote)         HEALTHY, same digest as dev, own database, env=qa, RLS-scoped notes
#   3 isolation                   a pod in hello-dev cannot reach hello-qa's Postgres; can reach its own
#   4 guard                       shim refuses `delete ns` and bulk deletes from a script (exit 126)
#   5 env-reset qa                volume replaced, data re-seeded, HEALTHY
#   6 v2 to dev, then rollback    new digest serves the new seed; rollback restores the v1 digest
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHIMS="${SDLC_GUARD_SHIMS:-$REPO/.claude/guard/shims}"; HOOK="${SDLC_GUARD_HOOK:-$REPO/.claude/guard/sdlc-guard.sh}"   # override to test the installed copy
export PATH="$SHIMS:$PATH:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin"
export SDLC_GUARD_HOOK="$HOOK" SDLC_GUARD_SHIMS="$SHIMS"
export KUBECONFIG="$HOME/.kube/sdlc-lab.json"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
last() { tail -1 "$W/agent_state/deploy/$1/history.jsonl" | python3 -c "import json,sys; e=json.load(sys.stdin); print($2)"; }
items() { curl -s -m 5 "http://hello-$1.localhost:18080/api/items" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)["items"]))' 2>/dev/null; }
notes() { curl -s -m 5 "http://hello-$1.localhost:18080/api/tenants/$2/notes" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)["notes"]))' 2>/dev/null; }
pgq()   { kubectl -n "hello-$1" exec postgres-0 -c postgres -- psql -U postgres -d app -tA -F ' ' -c "$2" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//'; }   # superuser over the pod's socket
rolesjob() { kubectl -n "hello-$1" logs "$(kubectl -n "hello-$1" get jobs -o name | grep '/roles-' | sort | tail -1)" 2>/dev/null | tail -1; }

W="$(mktemp -d "${TMPDIR:-/tmp}/k8s-e2e.XXXXXX")"; L="$(mktemp -d "${TMPDIR:-/tmp}/k8s-e2e-logs.XXXXXX")"   # logs OUTSIDE the project: an untracked file there would make every build "-dirty"
cp -R "$REPO/tests/fixtures/k8s-hello/services" "$W/"
bash "$REPO/.claude/templates/k8s/app/instantiate.sh" "$W" hello >/dev/null
cd "$W" && git init -q && git add -A && git -c user.name=e2e -c user.email=e2e@localhost commit -qm "fixture v1"
echo "fixture project: $W"
kubectl get serviceaccount default -n hello-dev >/dev/null 2>&1 || { echo "hello-dev missing: run app-namespaces.sh hello"; exit 1; }

echo "== 1 deploy dev"
# start from empty envs so the run is independent of earlier ones (reset = approved, namespaced)
for e in dev qa; do
  K="$(bash -c ". scripts/k8s/lib.sh; real_kubectl")"
  "$K" -n "hello-$e" delete deployments,statefulsets,cronjobs,jobs,services,ingresses,secrets,persistentvolumeclaims --all --wait=true --timeout=180s >/dev/null 2>&1
done
PHASE=1 bash scripts/k8s/deploy.sh dev >/dev/null 2>"$L/dev1.log" && ok "deploy.sh dev exit 0" || { bad "deploy.sh dev: $(tail -5 "$L/dev1.log")"; }
[ "$(last dev 'e["verdict"]')" = HEALTHY ] && ok "dev verdict HEALTHY" || bad "dev verdict $(last dev 'e["verdict"]')"
[ "$(items dev)" = "alpha,beta,gamma" ] && ok "dev serves seeded items via ingress" || bad "dev items: '$(items dev)'"
V=agent_state/phases/1/reports/deploy_dev.json
python3 -c "import json; d=json.load(open('$V')); assert d['schema']=='sdlc.test-results/v1' and d['verdict']=='PASS' and d['failed']==0 and d['total']>0 and len(d['code_sha'])==40 and not d['dirty']" 2>/dev/null \
  && ok "gate evidence deploy_dev.json: v1 schema, PASS, bound to the code commit" || bad "deploy_dev.json missing or not a clean PASS"
grep -q '"agent": "deploy_dev".*"status": "completed"' agent_state/phases/1/execution.jsonl \
  && ok "deploy logged itself to the phase's execution.jsonl (the gate reads it)" || bad "no deploy_dev line in execution.jsonl"
[ "$(last dev 'e["steps"].get("roles")')" = ok ] && ok "deploy ran the db-roles Job (step roles: ok)" || bad "no roles step in the dev deploy"
[ "$(notes dev acme)" = "acme roadmap" ] && [ "$(notes dev globex)" = "globex payroll" ] \
  && ok "dev API runs under FORCE row-level security: each tenant sees only its own note" || bad "dev tenant notes: acme='$(notes dev acme)' globex='$(notes dev globex)'"
r="$(pgq dev "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN ('app_migrator', 'app_runtime') ORDER BY 1")"
[ "$r" = "app_migrator f t app_runtime f f" ] && ok "roles: app_migrator NOSUPERUSER BYPASSRLS, app_runtime NOSUPERUSER NOBYPASSRLS" || bad "role attributes: '$r'"
r="$(pgq dev "SELECT string_agg(DISTINCT tableowner, ',') FROM pg_tables WHERE schemaname = 'public'")"
[ "$r" = app_migrator ] && ok "every table is owned by app_migrator" || bad "table owners: '$r'"
r="$(kubectl -n hello-dev get deploy api -o jsonpath='{.spec.template.spec.containers[*].env[*].valueFrom.secretKeyRef.key}')"
[ "$r" = "DB_APP_USER DB_APP_PASSWORD" ] && ok "the API Deployment reads only DB_APP_USER/DB_APP_PASSWORD" || bad "API secret keys: '$r'"
case "$(rolesjob dev)" in "db-roles: no changes"*) ok "db-roles Job after initdb: no changes" ;; *) bad "db-roles Job: '$(rolesjob dev)'" ;; esac
DEV1="$(last dev 'e["images"]["api"]')"

echo "== 2 promote to qa"
bash scripts/k8s/deploy.sh qa >/dev/null 2>"$L/qa1.log" && ok "deploy.sh qa exit 0" || bad "deploy.sh qa: $(tail -5 "$L/qa1.log")"
[ "$(last qa 'e["images"]["api"]')" = "$DEV1" ] && ok "qa runs dev's exact digest" || bad "qa digest $(last qa 'e["images"]["api"]') != $DEV1"
[ "$(last qa 'e["steps"].get("digest_parity")')" = ok ] && ok "qa pods' imageIDs match the digest" || bad "qa digest parity"
[ "$(curl -s -m 5 http://hello-qa.localhost:18080/api/version | python3 -c 'import json,sys; print(json.load(sys.stdin)["env"])')" = qa ] \
  && ok "qa reports env=qa" || bad "qa /api/version env"
[ "$(items qa)" = "alpha,beta,gamma" ] && ok "qa has its own seeded database" || bad "qa items: '$(items qa)'"
[ "$(notes qa globex)" = "globex payroll" ] && ok "qa API runs under row-level security too" || bad "qa globex notes: '$(notes qa globex)'"

echo "== 3 env isolation (NetworkPolicy)"
probe() {  # $1 name, $2 target host — tries for 12s (past the policy-sync window), prints ok|blocked
  kubectl -n hello-dev run "$1" --image=postgres:17-alpine --restart=Never --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":70}}}' \
    --command -- sh -c "sleep 6; for i in 1 2 3; do pg_isready -h $2 -t 2 -q && { echo ok; exit 0; }; sleep 2; done; echo blocked" >/dev/null
  kubectl -n hello-dev wait --for=jsonpath='{.status.phase}'=Succeeded "pod/$1" --timeout=90s >/dev/null 2>&1
  kubectl -n hello-dev logs "$1" 2>/dev/null | tail -1; kubectl -n hello-dev delete pod "$1" --wait=false >/dev/null 2>&1
}
[ "$(probe iso-own postgres)" = ok ] && ok "hello-dev pod reaches its own Postgres" || bad "own-namespace Postgres unreachable"
[ "$(probe iso-qa postgres.hello-qa.svc.cluster.local)" = blocked ] && ok "hello-dev pod cannot reach hello-qa Postgres" || bad "dev -> qa Postgres NOT blocked"

echo "== 4 guard (exec-time shim)"
kubectl delete namespace hello-qa >/dev/null 2>&1; [ $? = 126 ] && ok "shim refuses kubectl delete namespace (126)" || bad "delete namespace not refused"
kubectl -n hello-qa delete pods --all >/dev/null 2>&1; [ $? = 126 ] && ok "shim refuses bulk delete from a script (126)" || bad "bulk delete not refused"
kubectl -n kube-system delete pod x >/dev/null 2>&1; [ $? = 126 ] && ok "shim refuses writes to kube-system (126)" || bad "kube-system write not refused"

echo "== 5 env-reset qa"
PVC1="$(kubectl -n hello-qa get pvc -o jsonpath='{.items[0].metadata.uid}')"
bash scripts/k8s/env-reset.sh qa >/dev/null 2>"$L/reset.log" && ok "env-reset.sh qa exit 0" || bad "env-reset qa: $(tail -5 "$L/reset.log")"
PVC2="$(kubectl -n hello-qa get pvc -o jsonpath='{.items[0].metadata.uid}')"
[ -n "$PVC2" ] && [ "$PVC1" != "$PVC2" ] && ok "qa database volume replaced" || bad "qa PVC not replaced ($PVC1 -> $PVC2)"
[ "$(items qa)" = "alpha,beta,gamma" ] && ok "qa re-seeded after reset" || bad "qa items after reset: '$(items qa)'"

echo "== 6 v2 to dev, then rollback"
# plant a stale generated ConfigMap (what a changed configMapGenerator leaves behind) and an unrelated one
kubectl -n hello-dev create configmap app-config-zzzzzzzzzz --from-literal=APP_ENV=stale >/dev/null
kubectl -n hello-dev create configmap notes-abcde12345 --from-literal=k=v >/dev/null
sed -i '' "s/('gamma')/('gamma'), ('delta')/" services/api/main.go && git -c user.name=e2e -c user.email=e2e@localhost commit -qam "v2: seed delta"
bash scripts/k8s/deploy.sh dev >/dev/null 2>"$L/dev2.log" && ok "deploy.sh dev (v2) exit 0" || bad "deploy v2: $(tail -5 "$L/dev2.log")"
DEV2="$(last dev 'e["images"]["api"]')"
[ "$DEV2" != "$DEV1" ] && ok "v2 has a new digest" || bad "v2 digest unchanged"
[ "$(items dev)" = "alpha,beta,gamma,delta" ] && ok "v2 seed applied" || bad "dev items v2: '$(items dev)'"
case "$(rolesjob dev)" in "db-roles: no changes"*) ok "db-roles Job on the second deploy: no changes (idempotent)" ;; *) bad "db-roles Job v2: '$(rolesjob dev)'" ;; esac
bash scripts/k8s/deploy.sh dev --rollback >/dev/null 2>"$L/rb.log" && ok "deploy.sh dev --rollback exit 0" || bad "rollback: $(tail -5 "$L/rb.log")"
[ "$(last dev 'e["images"]["api"]')" = "$DEV1" ] && [ "$(last dev 'e["mode"]')" = rollback ] && ok "dev rolled back to the v1 digest" || bad "rollback digest $(last dev 'e["images"]["api"]')"
[ "$(python3 -c "import json; print(json.load(open('agent_state/deploy/last-deploy-status.json'))['status'])")" = HEALTHY ] \
  && ok "last-deploy-status.json HEALTHY" || bad "last-deploy-status.json not HEALTHY"

echo "== 7 nothing left behind"
n=0; for s in $(python3 -c "import json; [print(json.loads(l)['git_sha']) for l in open('agent_state/deploy/dev/history.jsonl')]" | sort -u); do
  docker images -q "localhost:5001/hello/api:$s" | grep -q . && n=$((n + 1))
done
[ "$n" = 0 ] && ok "no local docker copies of this run's pushed images" || bad "$n of this run's images still in local docker"
kubectl -n hello-dev get configmap app-config-zzzzzzzzzz >/dev/null 2>&1 && bad "stale generated ConfigMap not removed" || ok "stale generated ConfigMap removed after HEALTHY deploy"
kubectl -n hello-dev get configmap notes-abcde12345 >/dev/null 2>&1 && ok "unrelated ConfigMap left alone" || bad "unrelated ConfigMap deleted"
kubectl -n hello-dev delete configmap notes-abcde12345 --wait=false >/dev/null 2>&1
for e in dev qa; do
  c="$(kubectl -n "hello-$e" get configmaps,secrets -o name | grep -cE '/(app-config|db-credentials)-')"
  [ "$c" = 2 ] && ok "hello-$e: exactly one app-config + one db-credentials" || bad "hello-$e: $c generated objects (want 2)"
done
tags="$(crane ls localhost:5001/hello/api 2>/dev/null | wc -l | tr -d ' ')"
[ "$tags" -ge 1 ] && [ "$tags" -le 2 ] && ok "registry holds only v1+v2 ($tags tags) — earlier runs pruned" || bad "registry has $tags hello/api tags"
[ -z "$(git status --porcelain -- services)" ] && ok "build contexts clean (no -dirty tags)" || bad "build context dirty"
case "$(last dev 'e["git_sha"]')" in *-dirty) bad "dev deployed a -dirty build" ;; *) ok "deployed builds are not -dirty" ;; esac

echo "────────────────────────────────────────────"
if [ "$FAIL" -eq 0 ]; then rm -rf "$W" "$L"; WHERE="temp project removed"; else WHERE="project kept for debugging: $W, logs: $L"; fi
echo "k8s-e2e.sh: $PASS passed, $FAIL failed   ($WHERE; envs stay up: http://hello-dev.localhost:18080 http://hello-qa.localhost:18080)"
[ "$FAIL" -eq 0 ]
