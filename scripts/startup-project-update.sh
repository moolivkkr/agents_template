#!/usr/bin/env bash
# startup-project-update.sh — install or refresh the framework's files in a project (new or existing), enable the
# sdlc-graph store (SQLite + FTS5) and build it. Installed to ~/.claude/scripts/startup/ by install.sh.
#
# Usage: startup-project-update.sh [--project DIR] [--dry-run] [--force] [--hooks-only | --ledger-only] [--no-build]
#                                  [--graph-interactive on|off] [--source DIR] [--settings FILE] [--quiet]
#   --project DIR     project root (default: current directory)
#   --dry-run         print what would change; write nothing (the preflight still runs)
#   --force           overwrite framework hooks that were edited in the project (their diff is printed first)
#   --hooks-only      refresh .claude/hooks + its manifest only (what /develop Wave 0c runs)
#   --ledger-only     install ONLY the phase ledger (docs/PHASE_LEDGER.md): .claude/hooks/ledger.py, its hook entries
#                     in .claude/settings.json (created with just those when absent), agent_state/ledger/ in .gitignore.
#                     No other hook, no env keys, no graph build. Combine with --dry-run to preview.
#   --no-build        skip the initial graph build
#   --graph-interactive on|off   write agent_state/config/graph-policy.json (default: leave it absent = OFF)
#
# Touches only: .claude/hooks/<framework files> + .claude/hooks/.framework-manifest.json, .claude/settings.json
# (merge, never removes), .gitignore (agent_state/graph/, agent_state/ledger/), agent_state/graph/ (the build) and, with
# --graph-interactive, agent_state/config/graph-policy.json. Runs no git command that changes the worktree.
#
# Exit: 0 ok · 1 a locally modified hook was kept (use --force) · 2 usage / unreadable input / nothing staged
#       3 preflight FAIL (python3 >= 3.9 with sqlite3 needed; nothing was changed) · 4 graph build failed
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in -h|--help) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;; esac
QUIET=""; for x in "$@"; do [ "$x" = "--quiet" ] && QUIET="--quiet"; done
if ! bash "$DIR/graph-preflight.sh" $QUIET; then
  echo "startup-project-update: preflight failed — nothing was changed (fix python3 above, then re-run)" >&2
  exit 3
fi
exec python3 "$DIR/startup-project-update.py" update "$@"
