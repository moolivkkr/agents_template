#!/bin/bash
# deploy.sh <dev|qa> [--reuse | --rollback]  — deploy this project to the sdlc lab cluster.
#
#   dev             build every image in deploy/k8s/images.txt from the working tree, push to the
#                   in-cluster registry, pin the overlay to the pushed DIGESTS, apply, migrate, seed,
#                   roll out, smoke-test, and record evidence
#   qa              PROMOTE: take the newest HEALTHY dev deploy's digests (never rebuild), then the same
#                   apply/migrate/seed/rollout/smoke, plus a check that the running pods' image IDs
#                   are exactly those digests
#   --reuse         redeploy the digests already pinned in the overlay (no build; used by env-reset.sh)
#   --rollback      redeploy the newest earlier HEALTHY deploy of this env whose digests differ.
#                   Migrations are forward-only: rollback redeploys code, it does not undo schema.
#
# Verdict: HEALTHY (all steps + smoke + digest parity pass) | DEGRADED (deployed, checks failed) |
# FAILED (apply/migrate/rollout failed). Exit 0 only when HEALTHY. Evidence (deploylib.py record):
# agent_state/deploy/<env>/history.jsonl, agent_state/deploy/last-deploy-status.json, and with
# PHASE=<n> set, agent_state/phases/<n>/reports/deploy_verification.json for the phase gate.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
MODE=build; [ "$ENV_NAME" = qa ] && MODE=promote
case "${2:-}" in --reuse) MODE=reuse ;; --rollback) MODE=rollback ;; "") ;; *) die "unknown option $2" ;; esac
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STEPS=""   # JSON fragments: "step":"ok|fail"
step() { STEPS="$STEPS${STEPS:+,}\"$1\":\"$2\""; }
IMAGES=()

# ── preflight ────────────────────────────────────────────────────────────────────────────────────
log "preflight ($NS via $KUBECONFIG)"
kubectl get --raw /readyz >/dev/null 2>&1 || die "cluster API not reachable — is the lab cluster up? (limactl list)"
kc get serviceaccount default >/dev/null 2>&1 || die "namespace $NS missing — a human runs: app-namespaces.sh $APP"
if [ ! -f "$OVERLAY/secrets.env" ]; then
  # The database volume outlives any one checkout: reuse the credentials already in the namespace so a
  # fresh clone does not lock itself out of its own Postgres. New ones only for an empty env.
  umask 077
  cur="$(kc get secrets --sort-by=.metadata.creationTimestamp -o name 2>/dev/null | grep '^secret/db-credentials-' | head -1 || true)"   # oldest = the one the volume was initialised with
  if [ -n "$cur" ]; then
    { printf 'DB_USER=%s\n' "$(kc get "$cur" -o jsonpath='{.data.DB_USER}' | base64 -d)"
      printf 'DB_PASSWORD=%s\n' "$(kc get "$cur" -o jsonpath='{.data.DB_PASSWORD}' | base64 -d)"; } > "$OVERLAY/secrets.env"
    log "recovered $OVERLAY/secrets.env from ${cur#secret/} (gitignored)"
  else
    printf 'DB_USER=app\nDB_PASSWORD=%s\n' "$(openssl rand -hex 24)" > "$OVERLAY/secrets.env"
    log "created $OVERLAY/secrets.env (gitignored)"
  fi
fi

# ── images ───────────────────────────────────────────────────────────────────────────────────────
SHA="$(git_sha)"
case "$MODE" in
  build)
    curl -sf -m 5 "http://$REGISTRY/v2/" >/dev/null || die "registry $REGISTRY not reachable (lab cluster forward down?)"
    # the overlay digest blocks and agent_state/ evidence change on every deploy; they are not "source"
    [ -z "$(git -C "$ROOT" status --porcelain -- . ':!deploy/k8s/overlays' ':!agent_state' 2>/dev/null)" ] \
      || { SHA="$SHA-dirty"; log "working tree has uncommitted source changes: tagging $SHA"; }
    while read -r name ctx dockerfile; do
      case "$name" in ''|'#'*) continue ;; esac
      ref="$REGISTRY/$APP/$name:$SHA"
      log "build $name ($ctx) -> $ref"
      docker build -q --build-arg "GIT_SHA=$SHA" -t "$ref" -f "$ROOT/$ctx/${dockerfile:-Dockerfile}" "$ROOT/$ctx" >/dev/null
      docker save "$ref" -o "$TMP/$name.tar"
      pushed="$(crane push "$TMP/$name.tar" "$ref" 2>"$TMP/crane.err")" || die "push $ref failed: $(cat "$TMP/crane.err")"
      IMAGES+=("$name=$pushed"); log "pushed $pushed"
    done < "$K8S_DIR/images.txt"
    ;;
  promote)
    DEV_HIST="$ROOT/agent_state/deploy/dev/history.jsonl"
    SRC="$(python3 "$DL" pick "$DEV_HIST")" || die "no HEALTHY dev deploy to promote (run deploy.sh dev first)"
    SHA="$(printf '%s' "$SRC" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')"
    while IFS= read -r l; do IMAGES+=("$l"); done < <(printf '%s' "$SRC" | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin)["images"].items()]')
    [ "$SHA" = "$(git_sha)" ] || log "note: promoting dev-verified $SHA (HEAD is $(git_sha))"
    ;;
  reuse)
    while IFS= read -r l; do IMAGES+=("$l"); done < <(python3 "$DL" get-images "$OVERLAY/kustomization.yaml")
    [ "${#IMAGES[@]}" -gt 0 ] || die "no pinned digests in $OVERLAY to reuse"
    SRC="$(python3 "$DL" pick "$HIST" 2>/dev/null || true)"
    [ -n "$SRC" ] && SHA="$(printf '%s' "$SRC" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')"
    ;;
  rollback)
    CUR=(); while IFS= read -r l; do CUR+=("$l"); done < <(python3 "$DL" get-images "$OVERLAY/kustomization.yaml")
    SRC="$(python3 "$DL" pick "$HIST" --differs ${CUR[@]+"${CUR[@]}"})" || die "no earlier HEALTHY $ENV_NAME deploy with different images"
    SHA="$(printf '%s' "$SRC" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')"
    while IFS= read -r l; do IMAGES+=("$l"); done < <(printf '%s' "$SRC" | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin)["images"].items()]')
    log "rolling back $NS to $SHA"
    ;;
esac
[ "${#IMAGES[@]}" -gt 0 ] || die "no images to deploy (deploy/k8s/images.txt empty?)"
python3 "$DL" set-images "$OVERLAY/kustomization.yaml" "${IMAGES[@]}"

# ── apply → migrate → seed → rollout ─────────────────────────────────────────────────────────────
VERDICT=HEALTHY
DIGESTS=(); for pair in "${IMAGES[@]}"; do DIGESTS+=("${pair##*@}"); done
stuck() { kc get pods ${1:+-l "$1"} -o json 2>/dev/null | python3 "$DL" stuck --digests "${DIGESTS[@]}"; }
run_job() {  # $1 cronjob template, $2 step name — fails fast on a pod that can never start
  local job="$2-$(date +%s)" i s f r
  kc create job "$job" --from="cronjob/$1" >/dev/null || { step "$2" fail; return 1; }
  for i in $(seq 1 120); do
    s="$(kc get job "$job" -o jsonpath='{.status.succeeded}')"; [ "${s:-0}" -ge 1 ] && { step "$2" ok; return 0; }
    f="$(kc get job "$job" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')"; [ "$f" = True ] && break
    r="$(stuck "job-name=$job")"; [ -n "$r" ] && { log "$r"; break; }
    sleep 2
  done
  step "$2" fail; log "$2 job failed:"; kc logs "job/$job" --tail=40 >&2 || true
  kc delete job "$job" --wait=false >/dev/null 2>&1 || true   # a never-started Job never TTLs out
  return 1
}
wait_rollout() {  # $1 deployment.apps/<name> — fails fast when a new-digest pod can never start
  local i sel r
  sel="$(kc get "$1" -o jsonpath='{.spec.selector.matchLabels.app}')"
  for i in $(seq 1 120); do
    kc rollout status "$1" --timeout=2s >/dev/null 2>&1 && return 0
    r="$(stuck "${sel:+app=$sel}")"; [ -n "$r" ] && { log "$1: $r"; return 1; }
    sleep 1
  done
  return 1
}
if kubectl kustomize "$OVERLAY" > "$TMP/rendered.yaml" && kubectl apply -n "$NS" -k "$OVERLAY" >/dev/null; then
  step apply ok
else step apply fail; VERDICT=FAILED; fi
if [ "$VERDICT" = HEALTHY ]; then
  kc rollout status statefulset/postgres --timeout=240s >/dev/null && step database ok || { step database fail; VERDICT=FAILED; }
fi
[ "$VERDICT" = HEALTHY ] && { run_job db-migrate migrate || VERDICT=FAILED; }
[ "$VERDICT" = HEALTHY ] && { run_job db-seed seed || VERDICT=FAILED; }
if [ "$VERDICT" = HEALTHY ]; then
  ok=ok; for d in $(kc get deploy -o name); do wait_rollout "$d" || ok=fail; done
  step rollout "$ok"; [ "$ok" = ok ] || VERDICT=FAILED
fi

# ── verify: smoke + digest parity ────────────────────────────────────────────────────────────────
SMOKE='{"total":0,"passed":0,"failed":0,"failures":[]}'
if [ "$VERDICT" = HEALTHY ]; then
  SMOKE="$("$HERE/smoke.sh" "$ENV_NAME" "$SHA")" || VERDICT=DEGRADED
  parity=ok
  for pair in "${IMAGES[@]}"; do
    name="${pair%%=*}"; digest="${pair##*@}"
    ids="$(kc get pods -l "app=$name" --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.status.containerStatuses[*].imageID}{"\n"}{end}')"
    [ -n "$ids" ] || { parity=fail; log "no running pods for $name"; continue; }
    while IFS= read -r id; do case "$id" in *"@$digest") ;; *) parity=fail; log "pod runs $id, expected @$digest" ;; esac; done <<< "$ids"
  done
  step digest_parity "$parity"; [ "$parity" = ok ] || VERDICT=DEGRADED
fi

# ── evidence ─────────────────────────────────────────────────────────────────────────────────────
python3 "$DL" record --root "$ROOT" --env "$ENV_NAME" --ns "$NS" --sha "$SHA" --url "$BASE_URL" \
  --verdict "$VERDICT" --mode "$MODE" --steps "{$STEPS}" --smoke "$SMOKE" \
  ${PHASE:+--phase "$PHASE"} --images "${IMAGES[@]}"
log "$NS: $VERDICT ($MODE, $SHA) — $BASE_URL"
[ "$VERDICT" = HEALTHY ]
