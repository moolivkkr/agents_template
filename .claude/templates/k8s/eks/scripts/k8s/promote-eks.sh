#!/bin/bash
# promote-eks.sh <staging|prod> — pin the next environment to digests that already passed the previous
# one, copying them into this environment's ECR registry WITHOUT rebuilding (crane copy keeps the
# manifest bytes, so the digest is identical — and checked). Writes the overlay's managed images block
# and promoted-from.json; commit both (that commit is the release record; CI deploys it on merge).
#   staging  source: the newest HEALTHY qa deploy (agent_state/deploy/qa/history.jsonl), pulled from the
#            lab registry — so run it on the dev Mac, where localhost:5001 is reachable
#   prod     source: staging's pinned digests, only if ECR carries their staging-healthy-<sha> tag (set by
#            deploy-eks.sh after a HEALTHY staging deploy). Copied to prod's registry if it differs.
# HUMAN OR CI ONLY (writes to ECR): sdlc-guard refuses agents. Never builds, never deploys.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
case "$ENV_NAME" in staging|prod) ;; *) die "usage: promote-eks.sh <staging|prod>" ;; esac
[ "$EKS_PLACEHOLDERS" = 0 ] || die "$OVERLAY/eks.env still has placeholder values (scripts/k8s/eks-outputs.sh $ENV_NAME)"
command -v crane >/dev/null || die "crane not installed"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
SRC_IMAGES=()
if [ "$ENV_NAME" = staging ]; then
  SRC="$(python3 "$DL" pick "$ROOT/agent_state/deploy/qa/history.jsonl")" || die "no HEALTHY qa deploy to promote (scripts/k8s/deploy.sh qa first)"
  get() { printf '%s' "$SRC" | python3 -c 'import json,sys; v=json.load(sys.stdin).get(sys.argv[1]); print("" if v is None else str(v).lower() if isinstance(v, bool) else v)' "$1"; }
  SHA="$(get git_sha)"; CODE_SHA="$(get code_sha)"
  [ "$(get dirty)" != true ] && [ "${SHA%-dirty}" = "$SHA" ] || die "the newest HEALTHY qa deploy ($SHA) was built from uncommitted changes: never promoted past qa"
  while IFS= read -r l; do SRC_IMAGES+=("$l"); done < <(printf '%s' "$SRC" | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin)["images"].items()]')
  FROM=qa
else
  SOV="$K8S_DIR/overlays/staging"
  [ -f "$SOV/promoted-from.json" ] || die "staging has never been promoted"
  SHA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["git_sha"])' "$SOV/promoted-from.json")"
  CODE_SHA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("code_sha") or "")' "$SOV/promoted-from.json")"
  while IFS= read -r l; do SRC_IMAGES+=("$l"); done < <(python3 "$DL" get-images "$SOV/kustomization.yaml")
  for pair in "${SRC_IMAGES[@]}"; do
    ref="${pair#*=}"
    [ "$(crane digest "${ref%@*}:staging-healthy-$SHA" 2>/dev/null || true)" = "${ref##*@}" ] \
      || die "$ref has no staging-healthy-$SHA tag: it has not been deployed HEALTHY to staging"
  done
  FROM=staging
fi
[ "${#SRC_IMAGES[@]}" -gt 0 ] || die "no images in the $FROM source"
OUT=()
for pair in "${SRC_IMAGES[@]}"; do
  name="${pair%%=*}"; src="${pair#*=}"; digest="${src##*@}"; dest="$ECR_REGISTRY/$APP/$name"
  if [ "${src%@*}" != "$dest" ]; then
    have="$(crane digest "$dest:$SHA" 2>/dev/null || true)"
    if [ -z "$have" ]; then
      log "copy $src -> $dest:$SHA"
      crane copy "$src" "$dest:$SHA" 2>"$TMP/err" || die "crane copy failed: $(head -3 "$TMP/err")"
      have="$(crane digest "$dest:$SHA")"
    fi
    [ "$have" = "$digest" ] || die "$dest:$SHA is $have, not $digest (tags are immutable: a different image already has this tag)"
  fi
  OUT+=("$name=$dest@$digest")
done
python3 "$DL" set-images "$OVERLAY/kustomization.yaml" "${OUT[@]}"
python3 - "$OVERLAY/promoted-from.json" "$FROM" "$SHA" "$CODE_SHA" "${OUT[@]}" <<'PY'
import datetime, json, sys
path, frm, sha, code_sha, imgs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
json.dump({"from_env": frm, "git_sha": sha, "code_sha": code_sha,
           "images": dict(i.split("=", 1) for i in imgs),
           "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, open(path, "w"), indent=1)
open(path, "a").write("\n")
PY
log "$ENV_NAME pinned to $SHA from $FROM. Commit deploy/k8s/overlays/$ENV_NAME/{kustomization.yaml,promoted-from.json}, then deploy: scripts/k8s/deploy.sh $ENV_NAME (CI on merge)"
