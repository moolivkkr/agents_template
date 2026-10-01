#!/usr/bin/env bash
# run-tests.sh — the full run (run.sh) plus `cargo test` of every unit that has runnable tests
# (units.Unit.tests): the samples' own tests and the harness smoke tests. DB-backed tests
# (#[sqlx::test], the TestApp helpers) get a throwaway postgres:17-alpine (throwaway-pg.sh) and create
# their own databases on it; testcontainers tests start their own container through the Docker daemon.
#
#   bash tests/archetype-compile/rust/run-tests.sh
#   bash tests/archetype-compile/rust/run-tests.sh --only lang-rust -v
#
# Needs Docker and a Rust toolchain. A unit whose requirement is missing prints NOT RUN.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=throwaway-pg.sh
source "$HERE/throwaway-pg.sh"
python3 "$HERE/harness.py" --run-tests --database-url "$PG_URL" "$@"
