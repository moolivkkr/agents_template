#!/bin/bash
# deploy-eks.sh <staging|prod> [--rollback] — deploy this project to Amazon EKS (called by deploy.sh).
# HUMAN OR CI ONLY: sdlc-guard refuses agents (staging/prod are never unattended), and the agent's lab
# kubeconfig can't reach EKS anyway. Prod asks for a typed confirmation EVERY time (see confirm_prod).
#
#   (default)   deploy the digests pinned in deploy/k8s/overlays/<env>/kustomization.yaml — written by
#               promote-eks.sh and committed — never a build: staging runs what qa verified, prod what
#               staging verified, byte for byte (same digest in ECR)
#   --rollback  redeploy the newest earlier HEALTHY deploy of this env whose digests differ (from
#               agent_state/deploy/<env>/history.jsonl). Code only: migrations are forward-only. In CI,
#               roll back by reverting the promotion commit instead (same effect, reviewable).
#
# Steps: preflight (eks.env filled, EKS_KUBECONFIG is this env's cluster, digests exist in ECR; prod: each
# digest carries the staging-healthy tag) → confirm (prod) → render + db-access + eks-policy → apply →
# ExternalSecret synced → db-roles (as the RDS master user) → db-migrate → db-seed (as the migrator) →
# rollout → smoke over HTTPS + digest parity → record (history.jsonl, last-deploy-status.json) → on
# HEALTHY tag the images <env>-healthy-<sha> in ECR (what promote-eks.sh prod requires).
# Needs: kubectl, crane (ECR auth via the docker credential store: amazon-ecr-login in CI, or
# `aws ecr get-login-password | crane auth login <registry> -u AWS --password-stdin` for a human).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
case "$ENV_NAME" in staging|prod) ;; *) die "deploy-eks.sh deploys staging|prod; dev/qa use deploy.sh" ;; esac
MODE=deploy
case "${2:-}" in --rollback) MODE=rollback ;; "") ;; *) die "unknown option $2" ;; esac
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STEPS=""
step() { STEPS="$STEPS${STEPS:+,}\"$1\":\"$2\""; }
IMAGES=()
command -v crane >/dev/null || die "crane not installed (brew install crane / go install github.com/google/go-containerregistry/cmd/crane)"

# ── preflight ────────────────────────────────────────────────────────────────────────────────────
log "preflight ($NS on $EKS_CLUSTER_NAME, $AWS_REGION)"
eks_kube_check
kc get serviceaccount default >/dev/null 2>&1 || die "namespace $NS missing — a cluster admin runs: scripts/k8s/eks-bootstrap.sh $ENV_NAME"
PROV="$OVERLAY/promoted-from.json"
field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")' "$1" "$2"; }
case "$MODE" in
  deploy)
    while IFS= read -r l; do IMAGES+=("$l"); done < <(python3 "$DL" get-images "$OVERLAY/kustomization.yaml")
    [ "${#IMAGES[@]}" -gt 0 ] || die "nothing promoted to $ENV_NAME yet: scripts/k8s/promote-eks.sh $ENV_NAME, commit, then deploy"
    [ -f "$PROV" ] || die "$PROV missing: images are pinned only by promote-eks.sh"
    SHA="$(field "$PROV" git_sha)"; CODE_SHA="$(field "$PROV" code_sha)"
    ;;
  rollback)
    CUR=(); while IFS= read -r l; do CUR+=("$l"); done < <(python3 "$DL" get-images "$OVERLAY/kustomization.yaml")
    SRC="$(python3 "$DL" pick "$HIST" --differs ${CUR[@]+"${CUR[@]}"})" || die "no earlier HEALTHY $ENV_NAME deploy with different images in $HIST (in CI: revert the promotion commit)"
    SHA="$(printf '%s' "$SRC" | python3 -c 'import json,sys; print(json.load(sys.stdin)["git_sha"])')"
    CODE_SHA="$(printf '%s' "$SRC" | python3 -c 'import json,sys; e=json.load(sys.stdin); print(e.get("code_sha") or "")')"
    while IFS= read -r l; do IMAGES+=("$l"); done < <(printf '%s' "$SRC" | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin)["images"].items()]')
    log "rolling back $NS to $SHA"
    ;;
esac
[ -n "$SHA" ] || die "no git sha recorded for the pinned images"
DIGESTS=()
for pair in "${IMAGES[@]}"; do
  ref="${pair#*=}"; repo="${ref%@*}"; digest="${ref##*@}"; DIGESTS+=("$digest")
  case "$repo" in "$ECR_REGISTRY/$APP/"*) ;; *) die "$pair is not in $ECR_REGISTRY/$APP/ (promote-eks.sh copies images there)" ;; esac
  got="$(crane digest "$ref" 2>"$TMP/crane.err")" || die "$ref not readable in ECR: $(head -2 "$TMP/crane.err") (ECR login? promoted?)"
  [ "$got" = "$digest" ] || die "$ref resolves to $got"
  if [ "$ENV_NAME" = prod ] && [ "$MODE" = deploy ]; then   # prod runs only what staging ran HEALTHY
    st="$(crane digest "$repo:staging-healthy-$SHA" 2>/dev/null || true)"
    [ "$st" = "$digest" ] || die "$repo@$digest has no staging-healthy-$SHA tag: deploy it to staging (HEALTHY) first"
  fi
done

# ── prod: explicit human confirmation, every time ────────────────────────────────────────────────
confirm_prod() {
  [ "$ENV_NAME" = prod ] || return 0
  local want="$NS@$SHA" ans
  if [ "${GITHUB_ACTIONS:-}" = true ] && [ -n "${SDLC_PROD_CONFIRM:-}" ]; then
    # CI: the job runs in the protected GitHub Environment "prod" (required reviewers): a human approved
    # this run in the GitHub UI, and the workflow passes the exact namespace@sha that was approved.
    [ "$SDLC_PROD_CONFIRM" = "$want" ] || die "SDLC_PROD_CONFIRM='$SDLC_PROD_CONFIRM' does not match $want"
    log "prod confirmed by the approved GitHub Environment run ($want)"; return 0
  fi
  [ -t 0 ] && [ -t 2 ] || die "prod needs a typed confirmation on a terminal (or, in GitHub Actions, SDLC_PROD_CONFIRM=$want from a job in the protected 'prod' environment)"
  printf '\n  PRODUCTION %s on %s (%s)\n  %s %s\n  images:\n' "$MODE" "$NS" "$EKS_CLUSTER_ARN" "git sha" "$SHA" >&2
  printf '    %s\n' "${IMAGES[@]}" >&2
  printf '  Type %s to continue: ' "$want" >&2
  read -r ans
  [ "$ans" = "$want" ] || die "not confirmed — nothing was changed"
}
confirm_prod
[ "$MODE" = rollback ] && python3 "$DL" set-images "$OVERLAY/kustomization.yaml" "${IMAGES[@]}" \
  && log "overlay now pins the rollback digests: commit deploy/k8s/overlays/$ENV_NAME/kustomization.yaml"

# ── render → policy → apply → secrets → roles → migrate → seed → rollout ────────────────────────
VERDICT=HEALTHY
if kubectl kustomize "$OVERLAY" > "$TMP/rendered.yaml" \
  && kc create --dry-run=client -o json -f "$TMP/rendered.yaml" > "$TMP/rendered.json" \
  && python3 "$DL" db-access < "$TMP/rendered.json" \
  && python3 "$DL" eks-policy --registry "$ECR_REGISTRY" < "$TMP/rendered.json" \
  && kubectl apply -n "$NS" -k "$OVERLAY" >/dev/null; then
  step apply ok
else step apply fail; VERDICT=FAILED; fi
if [ "$VERDICT" = HEALTHY ]; then   # ESO wrote db-credentials from Secrets Manager (Pod Identity, no keys)
  if kc wait --for=condition=Ready externalsecret/db-credentials --timeout=180s >/dev/null 2>&1; then step secrets ok
  else step secrets fail; VERDICT=FAILED; kc describe externalsecret/db-credentials 2>/dev/null | tail -15 >&2; fi
fi
[ "$VERDICT" = HEALTHY ] && { run_job db-roles roles || VERDICT=FAILED; }
[ "$VERDICT" = HEALTHY ] && { run_job db-migrate migrate || VERDICT=FAILED; }
[ "$VERDICT" = HEALTHY ] && { run_job db-seed seed || VERDICT=FAILED; }
if [ "$VERDICT" = HEALTHY ]; then
  ok=ok; for d in $(kc get deploy -o name); do wait_rollout "$d" || ok=fail; done
  step rollout "$ok"; [ "$ok" = ok ] || VERDICT=FAILED
fi

# ── verify: smoke (HTTPS through the ALB) + digest parity ────────────────────────────────────────
SMOKE='{"total":0,"passed":0,"failed":0,"failures":[]}'
if [ "$VERDICT" = HEALTHY ]; then
  SMOKE="$("$HERE/smoke.sh" "$ENV_NAME" "$SHA")" || VERDICT=DEGRADED
  digest_parity || VERDICT=DEGRADED
fi

# ── registry evidence + record ───────────────────────────────────────────────────────────────────
if [ "$VERDICT" = HEALTHY ]; then
  tagged=ok
  for pair in "${IMAGES[@]}"; do
    ref="${pair#*=}"; repo="${ref%@*}"; tag="$ENV_NAME-healthy-$SHA"
    [ "$(crane digest "$repo:$tag" 2>/dev/null || true)" = "${ref##*@}" ] && continue   # (tags are immutable)
    crane tag "$ref" "$tag" 2>"$TMP/crane.err" || { tagged=fail; log "could not tag $ref as $tag: $(head -1 "$TMP/crane.err")"; }
  done
  step healthy_tag "$tagged"; [ "$tagged" = ok ] || VERDICT=DEGRADED
fi
python3 "$DL" record --root "$ROOT" --env "$ENV_NAME" --ns "$NS" --sha "$SHA" --code-sha "$CODE_SHA" --dirty false --url "$BASE_URL" \
  --verdict "$VERDICT" --mode "$MODE" --steps "{$STEPS}" --smoke "$SMOKE" ${PHASE:+--phase "$PHASE"} --images "${IMAGES[@]}"
log "$NS: $VERDICT ($MODE, $SHA) — $BASE_URL"
[ "$VERDICT" = HEALTHY ] && prune_generated "$TMP/rendered.yaml"
[ "$VERDICT" = HEALTHY ]
