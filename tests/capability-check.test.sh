#!/usr/bin/env bash
# capability-check.test.sh — scripts/capability-check.sh, the informational "which tool does each feature need"
# table install.sh prints after the graph preflight. Every case runs the script with a fake PATH (a temp dir of
# stub executables, no system dirs) so the result never depends on what this machine has installed, and checks:
# it always exits 0; found / missing / "missing (shim)" (a sdlc-guard shim is not the real tool); required vs
# optional in the summary; terraform falls back to tofu; Playwright is checked only when STITCH_PLAYWRIGHT_DIR is
# set; install.sh prints it, installs it, and still exits 0 with nothing on PATH but bash's own dir. The real
# ~/.claude is never touched (sandbox HOME).
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
CC="$ROOT/scripts/capability-check.sh"
BASH_BIN="$(command -v bash)"
REAL_PY="$(command -v python3)"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
export HOME="$W/home"; mkdir -p "$HOME"
stub() {   # $1 dir, $2.. names → executable stubs that exit 0
  local d="$1"; shift; mkdir -p "$d"
  for n in "$@"; do printf '#!/bin/sh\nexit 0\n' > "$d/$n"; chmod +x "$d/$n"; done
}
run() { env -i HOME="$HOME" PATH="$1" ${2:+CAPABILITY_CHECK_PYTHON="$2"} ${3:+STITCH_PLAYWRIGHT_DIR="$3"} "$BASH_BIN" "$CC" 2>&1; }
line() { grep -E "^  [^ ].* $1 +" <<<"$out" | head -1; }   # the row for tool $1

echo "── this machine ──"
out="$(bash "$CC" 2>&1)"; rc=$?
check "exits 0 and prints the header + a summary" '[ $rc -eq 0 ] && grep -q "^capabilities (informational" <<<"$out" && grep -qE "^capabilities: [0-9]+/[0-9]+ found" <<<"$out"'
check "python3 row reports the version the hooks will use" 'line python3 | grep -qE "found 3\.[0-9]+\.[0-9]+"'

echo "── fake PATH: only jq + git (python3 via CAPABILITY_CHECK_PYTHON) ──"
stub "$W/b1" jq git
out="$(run "$W/b1" "$REAL_PY")"; rc=$?
check "exit 0" '[ $rc -eq 0 ]'
check "jq, git, python3, sqlite3 found" 'line jq | grep -q found && line git | grep -q found && line python3 | grep -q found && line sqlite3 | grep -q found'
check "docker, kubectl, crane, aws, helm, node reported missing" 'for t in docker kubectl crane aws helm node; do line $t | grep -q " missing " || exit 1; done'
check "summary: no required tool missing; optional ones listed" '! grep -q "MISSING (required)" <<<"$out" && grep -qE "missing \(optional\):.* docker.* kubectl" <<<"$out"'
check "Playwright: per project when STITCH_PLAYWRIGHT_DIR is unset" 'line playwright | grep -q "per project"'

echo "── fake PATH: nothing (no python3, no jq) ──"
mkdir -p "$W/empty"
out="$(run "$W/empty")"; rc=$?
check "still exits 0" '[ $rc -eq 0 ]'
check "required tools named in the summary" 'grep -qE "MISSING \(required\): python3 sqlite3 jq git" <<<"$out"'

echo "── guard shims are not the real tool ──"
stub "$W/hooks/sdlc-guard-shims" kubectl crane
stub "$W/b2" crane
out="$(run "$W/hooks/sdlc-guard-shims:$W/b2" "$REAL_PY")"
check "kubectl only as a shim → missing (shim)" 'line kubectl | grep -q "missing (shim)"'
check "crane behind its shim → found (the real one)" 'line crane | grep -q found'

echo "── terraform falls back to tofu ──"
stub "$W/b3" tofu
out="$(run "$W/b3" "$REAL_PY")"
check "tofu found when terraform is absent" 'line tofu | grep -q found'
stub "$W/b4" terraform tofu
out="$(run "$W/b4" "$REAL_PY")"
check "terraform preferred when both exist" 'line terraform | grep -q found'

echo "── Playwright with STITCH_PLAYWRIGHT_DIR ──"
mkdir -p "$W/pw" "$W/b5"
printf '#!/bin/sh\nexit 1\n' > "$W/b5/node"; chmod +x "$W/b5/node"   # require.resolve fails
out="$(run "$W/b5" "$REAL_PY" "$W/pw")"
check "not resolvable there → missing" 'line playwright | grep -q " missing "'
stub "$W/b6" node
out="$(run "$W/b6" "$REAL_PY" "$W/pw")"
check "resolvable (node's check succeeds) → found" 'line playwright | grep -q found'

echo "── a python3 older than 3.9 ──"
printf '#!/bin/sh\necho "3.8.18|old|3.31.1|yes"\n' > "$W/oldpy"; chmod +x "$W/oldpy"
out="$(run "$W/b1" "$W/oldpy")"
check "too old, counted as a required miss" 'line python3 | grep -q "too old (3.8.18)" && grep -q "MISSING (required): python3" <<<"$out"'

echo "── install.sh (sandbox HOME) ──"
out="$(bash "$ROOT/install.sh" 2>&1)"; rc=$?
check "install.sh exits 0 and prints the table after the graph preflight" \
  '[ $rc -eq 0 ] && awk "/^graph preflight:/{p=1} p&&/^capabilities: [0-9]+\/[0-9]+ found/{f=1} END{exit !f}" <<<"$out"'
check "capability-check.sh installed to ~/.claude/scripts/startup" '[ -x "$HOME/.claude/scripts/startup/capability-check.sh" ] && cmp -s "$CC" "$HOME/.claude/scripts/startup/capability-check.sh"'
check "install.sh --guard does not run it (unchanged mode)" '! HOME="$W/home3" bash "$ROOT/install.sh" --guard 2>&1 | grep -q "^capabilities"'

echo "── docs ──"
check "README documents the check and links the deployment guide" 'grep -q "capability-check.sh" "$ROOT/README.md" && grep -q "docs/DEPLOYMENT_GUIDE.md" "$ROOT/README.md" && [ -f "$ROOT/docs/DEPLOYMENT_GUIDE.md" ]'

echo "────────────────────────────────────────────"
echo "capability-check.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
