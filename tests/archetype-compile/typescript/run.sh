#!/usr/bin/env bash
# Type-check every TypeScript/TSX sample in .claude/skills/{backend,ui}/archetypes/*.md.
#
#   bash tests/archetype-compile/typescript/run.sh              # the gate: every unit, every block
#   bash tests/archetype-compile/typescript/run.sh --unit NAME  # one unit (repeatable); --list shows them
#   bash tests/archetype-compile/typescript/run.sh --keep       # keep the generated projects for debugging
#   bash tests/archetype-compile/typescript/run.sh --strictest  # report: + exactOptionalPropertyTypes etc.
#
# Blocks are extracted from the markdown at run time, grouped into units (units.py) and compiled with the
# pinned TypeScript under strict + noUncheckedIndexedAccess. Exit 0 = every unit passes AND every TS block
# is either compiled or listed in units.SKIP with a reason AND each file's block count matches units.FILES.
#
# Needs node + npm (first run: `npm ci` into ./node_modules, ~20s; repeated only when package-lock.json
# changes) and python3 >= 3.8. Not part of tests/run-all.sh: it needs the npm registry once.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

command -v node >/dev/null || { echo "run.sh: node is required" >&2; exit 2; }
command -v npm >/dev/null || { echo "run.sh: npm is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "run.sh: python3 is required" >&2; exit 2; }

want="$(shasum -a 256 package-lock.json 2>/dev/null || sha256sum package-lock.json)"
want="${want%% *}"
have="$(cat node_modules/.package-lock.sha256 2>/dev/null || true)"
if [ "$want" != "$have" ]; then
  echo "run.sh: installing pinned dependencies (npm ci)…"
  # --ignore-scripts: nothing here needs install scripts (TypeScript 7 and buf ship platform binaries as
  # optional dependencies; the harness runs `prisma generate` itself against shims/prisma/schema.prisma).
  npm ci --ignore-scripts --no-audit --no-fund --loglevel=error
  printf '%s' "$want" > node_modules/.package-lock.sha256
fi

exec python3 "$DIR/harness.py" "$@"
