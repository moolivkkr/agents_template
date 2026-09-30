#!/usr/bin/env bash
# run.sh — compile-check every ```python block in .claude/skills/backend/archetypes/*.md.
#
# The blocks are extracted from the markdown at run time, assembled into small projects (units.py),
# then each project is: imported (every import must resolve against the real, pinned libraries),
# type-checked with pyright against the libraries' own type information, smoke-run where that needs
# no external service, and its test samples collected (or run, when they need no database).
# Fails on any error, on a block no unit checks and no skip entry explains, and on a block-count
# change the config doesn't know about.
#
# Needs: uv, node/npx (pyright), network for the first package download.
# Usage: ./run.sh [--unit NAME ...] [--live] [--keep] [--list]
#   --live   also run the database samples against a throwaway Postgres (Docker + testcontainers)
#   --keep   keep the assembled projects in .build/ for debugging
# Config: units.py (which blocks form which project). After changing the harness, run
# `.venv/bin/python selftest.py`: it breaks copies of the docs and checks each break fails the run.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ARCHETYPE_PY_VENV:-$HERE/.venv}"
PYRIGHT_VERSION="1.1.414"

command -v uv >/dev/null || { echo "run.sh: uv is required (https://docs.astral.sh/uv/)" >&2; exit 2; }
command -v npx >/dev/null || { echo "run.sh: node/npx is required for pyright" >&2; exit 2; }

if [ ! -x "$VENV/bin/python" ]; then
  uv venv -q --python 3.12 "$VENV"
fi
# Exact lock; a no-op when already satisfied.
uv pip install -q --python "$VENV/bin/python" -r "$HERE/requirements.txt"

export PYRIGHT_CMD="npx --yes pyright@$PYRIGHT_VERSION"
exec "$VENV/bin/python" "$HERE/harness.py" "$@"
