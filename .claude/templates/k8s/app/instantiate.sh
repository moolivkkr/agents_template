#!/bin/bash
# instantiate.sh <project-dir> <app> — copy the k8s deploy layer into a project (deployment_agent runs
# this, then adapts deploy/k8s/base/*.yaml and images.txt to the project's services).
#   deploy/k8s/{app.env,images.txt,base/,overlays/dev,overlays/qa}   (__APP__ -> <app>)
#   scripts/k8s/{deploy,smoke,seed,env-reset}.sh + lib.sh + deploylib.py
# Never overwrites an existing file (prints "kept"). Adds the overlays' secrets.env to .gitignore.
set -euo pipefail
PROJECT="${1:?usage: $0 <project-dir> <app>}"; APP="${2:?usage: $0 <project-dir> <app>}"
[[ "$APP" =~ ^[a-z][a-z0-9-]{0,40}[a-z0-9]$ ]] || { echo "app must be a DNS label" >&2; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SRC"
find deploy scripts -type f -not -path '*/__pycache__/*' | sort | while read -r f; do
  dest="$PROJECT/$f"
  if [ -e "$dest" ]; then echo "  kept    $f"; continue; fi
  mkdir -p "$(dirname "$dest")"
  LC_ALL=C sed "s/__APP__/$APP/g" "$f" > "$dest"   # byte-wise: templates contain UTF-8
  [ -x "$f" ] && chmod +x "$dest"
  echo "  created $f"
done
GI="$PROJECT/.gitignore"
grep -qxF 'deploy/k8s/overlays/*/secrets.env' "$GI" 2>/dev/null || echo 'deploy/k8s/overlays/*/secrets.env' >> "$GI"
