#!/bin/bash
# registry-prune.sh [--keep N] [--dry-run] — delete this app's images from the lab registry that nothing
# needs any more. deploy.sh runs it after every HEALTHY deploy; safe to run by hand at any time.
#
# Kept (by digest):
#   - everything referenced right now by Deployments, StatefulSets and CronJob templates in
#     <app>-dev and <app>-qa (what is running, and what the next migrate/seed Job will use)
#   - the newest N HEALTHY deploys of each env in agent_state/deploy/<env>/history.jsonl — the
#     rollback targets and qa's promotion source (default N=5)
# Everything else under <registry>/<app>/ is deleted: failed, dirty and superseded builds.
# Deleting frees the tag and manifest at once; the layers are freed by the registry's nightly
# garbage-collect CronJob (cluster/registry.yaml, sdlc-system/registry-gc).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
KEEP=5; DRY=""
while [ $# -gt 0 ]; do
  case "$1" in --keep) KEEP="${2:?}"; shift ;; --dry-run) DRY=1 ;; *) die "usage: $(basename "$0") [--keep N] [--dry-run]" ;; esac
  shift
done

keep="$(
  for e in dev qa; do
    kubectl -n "$APP-$e" get deployments,statefulsets,cronjobs -o jsonpath='{..image}' 2>/dev/null | tr ' ' '\n'
    python3 "$DL" keep "$ROOT/agent_state/deploy/$e/history.jsonl" --n "$KEEP"
  done | grep -oE 'sha256:[0-9a-f]{64}' | sort -u
)"
# Refuse to prune blind: with nothing to keep, a cluster-read failure would delete everything.
[ -n "$keep" ] || die "found no in-use or recent HEALTHY digests for $APP — refusing to prune"

deleted=0; kept=0
for repo in $(crane catalog "$REGISTRY" 2>/dev/null | grep "^$APP/"); do
  seen=""
  for tag in $(crane ls "$REGISTRY/$repo" 2>/dev/null); do
    d="$(crane digest "$REGISTRY/$repo:$tag" 2>/dev/null)" || continue
    case " $seen " in *" $d "*) continue ;; esac
    seen="$seen $d"
    if printf '%s\n' "$keep" | grep -qxF "$d"; then kept=$((kept + 1)); continue; fi
    if [ -n "$DRY" ]; then log "would delete $repo:$tag ($d)"; deleted=$((deleted + 1)); continue; fi
    crane delete "$REGISTRY/$repo@$d" 2>/dev/null && { deleted=$((deleted + 1)); log "deleted $repo:$tag"; } \
      || log "could not delete $repo@$d"
  done
done
verb=deleted; [ -n "$DRY" ] && verb="would delete"
log "registry-prune $APP: kept $kept, $verb $deleted (keep newest $KEEP HEALTHY per env + in use)"
