#!/bin/bash
# instantiate.sh <project-dir> <app> [--eks] — copy the k8s deploy layer into a project (deployment_agent
# runs this, then adapts deploy/k8s/base/*.yaml and images.txt to the project's services).
#   deploy/k8s/{app.env,images.txt,base/,overlays/dev,overlays/qa,overlays/prod}   (__APP__ -> <app>)
#   (overlays/prod is the lab prod namespace <app>-prod; with --eks it comes from the EKS layer instead)
#   scripts/k8s/{deploy,smoke,seed,env-reset}.sh + lib.sh + deploylib.py
# --eks also copies the Amazon EKS layer (../eks/, skill infrastructure/eks.md):
#   deploy/k8s/{components/eks,overlays/staging,overlays/prod,eks-cluster.yaml}
#   scripts/k8s/{deploy-eks,promote-eks,eks-bootstrap,eks-outputs}.sh
#   infra/terraform/{modules,envs/{state,shared,staging,prod}}   .github/workflows/deploy-eks.yml
# Never overwrites an existing file (prints "kept"). Adds the overlays' secrets.env to .gitignore.
set -euo pipefail
PROJECT="${1:?usage: $0 <project-dir> <app> [--eks]}"; APP="${2:?usage: $0 <project-dir> <app> [--eks]}"
EKS=false; case "${3:-}" in --eks) EKS=true ;; "") ;; *) echo "unknown option ${3}" >&2; exit 1 ;; esac
[[ "$APP" =~ ^[a-z][a-z0-9-]{0,40}[a-z0-9]$ ]] || { echo "app must be a DNS label" >&2; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$PROJECT"; PROJECT="$(cd "$PROJECT" && pwd)"   # absolute: `instantiate.sh . app` means the caller's cwd
copy_tree() {  # $1 template root, then the top-level paths to copy from it (SKIP_PREFIX: a path prefix to leave out)
  local root="$1"; shift
  (cd "$root" && find "$@" -type f -not -path '*/__pycache__/*' -not -path '*/.terraform/*' -not -name '.terraform.lock.hcl' | sort) | while read -r f; do
    case "$f" in "${SKIP_PREFIX:-//none}"*) continue ;; esac
    dest="$PROJECT/$f"
    if [ -e "$dest" ]; then echo "  kept    $f"; continue; fi
    mkdir -p "$(dirname "$dest")"
    LC_ALL=C sed "s/__APP__/$APP/g" "$root/$f" > "$dest"   # byte-wise: templates contain UTF-8
    [ -x "$root/$f" ] && chmod +x "$dest"
    echo "  created $f"
  done
}
if [ "$EKS" = true ]; then
  SKIP_PREFIX=deploy/k8s/overlays/prod/ copy_tree "$SRC" deploy scripts   # prod is EKS's, not the lab's
  if [ -f "$PROJECT/deploy/k8s/overlays/prod/kustomization.yaml" ] && [ ! -f "$PROJECT/deploy/k8s/overlays/prod/eks.env" ] \
     && ! grep -q 'components/eks' "$PROJECT/deploy/k8s/overlays/prod/kustomization.yaml"; then
    echo "  WARNING deploy/k8s/overlays/prod is the LAB prod overlay; move it aside so the EKS prod overlay can be copied" >&2
  fi
  copy_tree "$SRC/../eks" deploy scripts infra .github
  GI="$PROJECT/.gitignore"
  for p in '.terraform/' '*.tfstate' '*.tfstate.*' '*.tfplan' 'tf.plan'; do grep -qxF "$p" "$GI" 2>/dev/null || echo "$p" >> "$GI"; done
else
  copy_tree "$SRC" deploy scripts
fi
GI="$PROJECT/.gitignore"
grep -qxF 'deploy/k8s/overlays/*/secrets.env' "$GI" 2>/dev/null || echo 'deploy/k8s/overlays/*/secrets.env' >> "$GI"
# Keep pipeline state and agent config out of any build context rooted at the repo (they change every
# wave, which would otherwise make every root-context image "-dirty" and bake agent notes into images).
DI="$PROJECT/.dockerignore"
for p in agent_state/ .claude/ docs/ '**/secrets.env'; do grep -qxF "$p" "$DI" 2>/dev/null || echo "$p" >> "$DI"; done
