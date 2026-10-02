#!/usr/bin/env bash
# graph-preflight.sh — can this machine run the framework's python hooks and the sdlc-graph store?
#
# Checks the `python3` on PATH (the hooks are run as `python3 .claude/hooks/X.py` and by `#!/usr/bin/env python3`):
#   FAIL  python3 missing, older than 3.9 (the hooks' floor; macOS /usr/bin/python3 is 3.9 and works),
#         `import sqlite3` fails, `import fcntl` fails (POSIX only: the graph's build lock), or the sqlite
#         library can't create a table in :memory:.
#   WARN  sqlite has no FTS5. sdlc-graph still builds and every pipeline command (context, diff-context, tc,
#         gate, unlocked, ...) works; only the interactive `find` ranks with LIKE instead of bm25.
# Used by install.sh (warns, keeps installing), new-project.sh and startup-project-update.sh (stop on FAIL).
#
# Usage: graph-preflight.sh [--quiet]     exit 0 = usable (OK or WARN), 1 = FAIL. One summary line on stdout
#                                         ("graph preflight: OK|WARN|FAIL — ..."); the fix goes to stderr.
# Env: GRAPH_PREFLIGHT_PYTHON  interpreter to check instead of `python3` (tests).
set -uo pipefail
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1
PY="${GRAPH_PREFLIGHT_PYTHON:-python3}"

fix() {   # $1 = what is wrong
  {
    echo "  How to fix ($1):"
    case "$(uname -s 2>/dev/null)" in
      Darwin)
        echo "    macOS: xcode-select --install          (Apple's /usr/bin/python3 3.9: sqlite3 + FTS5 included)"
        echo "       or: brew install python              (then make sure \`command -v python3\` finds it)" ;;
      *)
        echo "    Debian/Ubuntu: sudo apt-get install python3        (sqlite3 module is in libpython3.x-stdlib)"
        echo "    Fedora/RHEL:   sudo dnf install python3"
        echo "    pyenv/source builds: install the sqlite dev headers (libsqlite3-dev / sqlite-devel) and rebuild python" ;;
    esac
    echo "    Until then: graph commands print GRAPH UNAVAILABLE and agents use the pre-graph procedure, but the phase"
    echo "    gate's TC check (verify-gate.sh check h) cannot run, so /develop gates BLOCK on any phase with specs."
  } >&2
}

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "graph preflight: FAIL — $PY not found on PATH"
  fix "no python3"
  exit 1
fi

IFS= read -r -d '' CHECK <<'PYEOF'
import sys
v = sys.version_info
if v < (3, 9):
    print("FAIL|python %d.%d.%d is older than 3.9|%s" % (v[0], v[1], v[2], sys.executable)); sys.exit(0)
try:
    import fcntl  # noqa: F401  (sdlc-graph's build lock)
except ImportError as e:
    print("FAIL|import fcntl failed (%s): the hooks need a POSIX python|%s" % (e, sys.executable)); sys.exit(0)
try:
    import sqlite3
except ImportError as e:
    print("FAIL|python %d.%d.%d has no sqlite3 module (%s)|%s" % (v[0], v[1], v[2], e, sys.executable)); sys.exit(0)
pyv = "%d.%d.%d" % (v[0], v[1], v[2])
try:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE t(k TEXT PRIMARY KEY, v TEXT)")
    db.execute("INSERT OR REPLACE INTO t VALUES('a','b')")
except sqlite3.Error as e:
    print("FAIL|sqlite %s cannot create a table: %s|%s" % (sqlite3.sqlite_version, e, sys.executable)); sys.exit(0)
fts5 = "yes"
try:
    db.execute("CREATE VIRTUAL TABLE f USING fts5(title, body, tokenize='porter unicode61')")
    db.execute("INSERT INTO f VALUES('graph store', 'sqlite full text')")
    db.execute("SELECT bm25(f) FROM f WHERE f MATCH 'graph'").fetchall()
except sqlite3.Error:
    fts5 = "no"
print("%s|python %s (%s), sqlite %s, FTS5 %s|%s" % ("OK" if fts5 == "yes" else "WARN", pyv, sys.executable,
                                                    sqlite3.sqlite_version, fts5, sys.executable))
PYEOF
OUT="$("$PY" -c "$CHECK" 2>&1)"
STATUS="${OUT%%|*}"; REST="${OUT#*|}"; DETAIL="${REST%|*}"
case "$STATUS" in
  OK)   [ "$QUIET" = 1 ] || echo "graph preflight: OK — $DETAIL"; exit 0 ;;
  WARN) echo "graph preflight: WARN — $DETAIL: sdlc-graph builds and the pipeline commands work; interactive find ranks without bm25"
        fix "no FTS5 in this sqlite"; exit 0 ;;
  FAIL) echo "graph preflight: FAIL — $DETAIL"; fix "unusable python3"; exit 1 ;;
  *)    echo "graph preflight: FAIL — $PY did not run the check: $(printf '%s' "$OUT" | head -3 | tr '\n' ' ')"
        fix "python3 does not run"; exit 1 ;;
esac
