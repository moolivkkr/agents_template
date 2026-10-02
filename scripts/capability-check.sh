#!/usr/bin/env bash
# capability-check.sh — which framework capabilities can this machine run? Informational only: it always exits 0
# and never changes anything. install.sh prints it after the graph preflight; run it any time with
#   ~/.claude/scripts/startup/capability-check.sh        (or bash scripts/capability-check.sh in the repo)
#
# One row per tool: capability, tool, found/missing, what needs it. "required" rows are what the phase gate and
# the hooks need on every project; the others matter only for the feature named. Where each tool is used:
#   python3 >= 3.9 + sqlite3  .claude/hooks/*.py, sdlc-graph.py, verify-gate.sh check (h)   (scripts/graph-preflight.sh)
#   FTS5                      sdlc-graph.py find/ask ranking (interactive, off by default; LIKE fallback)
#   jq                        verify-gate.sh (blocks without it), autonomous-* hooks + manifest-write-check.sh (skip
#                             silently without it), remember.sh, scripts/startup-autonomous-run.sh
#   git                       startup-project-update.py (hook versions from git history), deploy build identity
#   perl                      startup-autonomous-run.sh: restores default INT/TERM/HUP for the child (python3 fallback)
#   claude                    startup-autonomous-run.sh (claude -p), scripts/eval-question-tokens.py
#   node / Playwright         .claude/hooks/stitch-capture.mjs (/stitch import); Playwright is resolved from
#                             $STITCH_PLAYWRIGHT_DIR, else from the project, so it is checked only when that is set
#   docker                    deploy.sh image builds (dev), docker compose (local target)
#   kubectl                   deploy.sh dev|qa (kubectl kustomize + apply); kustomize is built in
#   crane                     deploy.sh pushes to the lab registry; promote-eks.sh / deploy-eks.sh (ECR)
#   limactl                   cluster-up.sh (lab cluster, human)
#   terraform | tofu          infra/terraform for EKS (human); tests/eks-templates.test.sh validation
#   aws, helm                 EKS: credentials/kubeconfig and eks-bootstrap.sh (External Secrets Operator), human/CI
#
# A PATH entry inside an `sdlc-guard-shims` directory is skipped: the guard's kubectl/helm/limactl/aws/crane shims
# answer `command -v` even when the real tool is absent, so the real binary is looked up behind them.
# Env: CAPABILITY_CHECK_PYTHON  interpreter to probe instead of python3 (tests).
set -u

# real_tool NAME → path of the first executable NAME on PATH that is not a guard shim; empty when none
real_tool() {
  local d IFS=:
  for d in $PATH; do
    [ -n "$d" ] || continue
    case "$d" in *sdlc-guard-shims*) continue ;; esac
    if [ -f "$d/$1" ] && [ -x "$d/$1" ]; then printf '%s\n' "$d/$1"; return 0; fi
  done
  return 1
}
shim_only() {   # NAME → 0 when only a guard shim provides it
  local d IFS=:
  for d in $PATH; do
    case "$d" in *sdlc-guard-shims*) [ -x "$d/$1" ] && return 0 ;; esac
  done
  return 1
}

FOUND=0; TOTAL=0; MISSING_REQ=""; MISSING_OPT=""
row() {   # capability tool status need required(1|0)
  TOTAL=$((TOTAL + 1))
  printf '  %-22s %-12s %-16s %s\n' "$1" "$2" "$3" "$4"
  case "$3" in
    found*) FOUND=$((FOUND + 1)) ;;
    *) if [ "$5" = 1 ]; then MISSING_REQ="$MISSING_REQ $2"; else MISSING_OPT="$MISSING_OPT $2"; fi ;;
  esac
}
status_of() {   # NAME → "found" | "missing" | "missing (shim)"
  if real_tool "$1" >/dev/null; then echo found
  elif shim_only "$1"; then echo "missing (shim)"
  else echo missing; fi
}

echo "capabilities (informational: a missing tool disables only the feature named; nothing here stops the install)"
printf '  %-22s %-12s %-16s %s\n' "capability" "tool" "status" "needed for"

# python3 + sqlite3 + FTS5: one probe (graph-preflight.sh is the authoritative check and runs before this)
PY="${CAPABILITY_CHECK_PYTHON:-}"; [ -n "$PY" ] || PY="$(real_tool python3 || true)"
PYV=""; SQL=""; FTS=""
IFS= read -r -d '' PROBE <<'PYEOF'
import sys
v = "%d.%d.%d" % sys.version_info[:3]
ok = "ok" if sys.version_info >= (3, 9) else "old"
try:
    import sqlite3
    sv = sqlite3.sqlite_version
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE VIRTUAL TABLE f USING fts5(t)"); fts = "yes"
    except sqlite3.Error:
        fts = "no"
except Exception:
    sv, fts = "", "no"
print("%s|%s|%s|%s" % (v, ok, sv, fts))
PYEOF
if [ -n "$PY" ] && [ -x "$PY" ]; then
  OUT="$("$PY" -c "$PROBE" 2>/dev/null)"
  PYV="${OUT%%|*}"; REST="${OUT#*|}"; PYOK="${REST%%|*}"; REST="${REST#*|}"; SQL="${REST%%|*}"; FTS="${REST#*|}"
fi
NEED_PY="hooks, sdlc-graph, phase gate (required)"
if [ -z "$PYV" ]; then row "hooks + graph" python3 missing "$NEED_PY" 1
elif [ "$PYOK" != ok ]; then row "hooks + graph" python3 "too old ($PYV)" "$NEED_PY; needs 3.9+" 1
else row "hooks + graph" python3 "found $PYV" "$NEED_PY" 1; fi
if [ -n "$SQL" ]; then row "graph store" sqlite3 "found $SQL" "sdlc-graph (required)" 1
else row "graph store" sqlite3 missing "sdlc-graph (required): python3 has no sqlite3 module" 1; fi
if [ "$FTS" = yes ]; then row "graph find ranking" FTS5 found "sdlc-graph find (off by default; LIKE fallback)" 0
else row "graph find ranking" FTS5 missing "sdlc-graph find (off by default; LIKE fallback)" 0; fi

row "phase gate + hooks"  jq      "$(status_of jq)"      "verify-gate.sh blocks without it; autonomous hooks skip (required)" 1
row "updater + deploys"   git     "$(status_of git)"     "hook versions, build identity (required)" 1
row "supervisor signals"  perl    "$(status_of perl)"    "startup-autonomous-run.sh (python3 fallback)" 0
row "unattended runs"     claude  "$(status_of claude)"  "startup-autonomous-run.sh, eval-question-tokens.py" 0
row "Stitch import"       node    "$(status_of node)"    "stitch-capture.mjs (/stitch import)" 0
if [ -n "${STITCH_PLAYWRIGHT_DIR:-}" ]; then
  NODE="$(real_tool node || true)"; PW=missing
  if [ -n "$NODE" ] && (cd "$STITCH_PLAYWRIGHT_DIR" 2>/dev/null && "$NODE" -e 'const r=require("module").createRequire(process.cwd()+"/");for(const n of["@playwright/test","playwright"]){try{r.resolve(n);process.exit(0)}catch{}}process.exit(1)' >/dev/null 2>&1); then PW=found; fi
  row "Stitch import" playwright "$PW" "stitch-capture.mjs (from \$STITCH_PLAYWRIGHT_DIR)" 0
else
  # not counted in the summary: Playwright can only be resolved inside a project
  printf '  %-22s %-12s %-16s %s\n' "Stitch import" playwright "per project" "resolved from the project at run time (or set STITCH_PLAYWRIGHT_DIR)"
fi
row "image builds"        docker  "$(status_of docker)"  "/deploy local + dev (docker build, compose)" 0
row "lab dev/qa deploys"  kubectl "$(status_of kubectl)" "deploy.sh dev|qa (kubectl kustomize + apply)" 0
row "lab + ECR images"    crane   "$(status_of crane)"   "deploy.sh registry push; promote-eks.sh (human/CI)" 0
row "lab cluster"         limactl "$(status_of limactl)" "cluster-up.sh (human)" 0
TF="$(status_of terraform)"; TFN=terraform
case "$TF" in found*) ;; *) T2="$(status_of tofu)"; case "$T2" in found*) TF="$T2"; TFN=tofu ;; esac ;; esac
row "EKS infrastructure"  "$TFN"  "$TF"                  "infra/terraform (human); eks-templates test" 0
row "EKS staging/prod"    aws     "$(status_of aws)"     "EKS kubeconfig + ECR login (human/CI only)" 0
row "EKS bootstrap"       helm    "$(status_of helm)"    "eks-bootstrap.sh: External Secrets Operator (human)" 0

SUMMARY="capabilities: $FOUND/$TOTAL found"
[ -n "$MISSING_REQ" ] && SUMMARY="$SUMMARY; MISSING (required):$MISSING_REQ"
[ -n "$MISSING_OPT" ] && SUMMARY="$SUMMARY; missing (optional):$MISSING_OPT"
echo "$SUMMARY"
exit 0
