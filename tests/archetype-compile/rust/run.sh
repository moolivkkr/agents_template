#!/usr/bin/env bash
# run.sh — compile-check every ```rust block in .claude/skills/backend/archetypes/*.md.
#
#   bash tests/archetype-compile/rust/run.sh              # full run: structure + cargo check + manifests
#   bash tests/archetype-compile/rust/run.sh --coverage-only   # block counts, coverage, doc-fence lint (no cargo)
#   bash tests/archetype-compile/rust/run.sh --only widget-app -v
#   bash tests/archetype-compile/rust/run.sh --update-lock     # after changing a version in Cargo.toml
#   bash tests/archetype-compile/rust/prepare-sqlx.sh          # after changing a sqlx::query! or the schema
#   bash tests/archetype-compile/rust/run-tests.sh             # the full run + cargo test (throwaway Postgres; Docker)
#
# Needs a Rust toolchain (brew install rustup && rustup-init -y --no-modify-path). The first run
# downloads and builds ~500 crates into ./target (gitignored); later runs take seconds per unit.
# sqlx::query! macros are checked offline against the committed .sqlx/ metadata, which
# prepare-sqlx.sh generates from a throwaway Postgres built from the archetype migrations.
# Exit 0 = every unit compiles and every manifest line resolves. See harness.py for the steps.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.cargo/bin:/opt/homebrew/opt/rustup/bin:$PATH"
if [ "${1:-}" != "--coverage-only" ] && ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not found: install Rust (brew install rustup && rustup-init -y --no-modify-path)" >&2
  exit 2
fi
exec python3 "$HERE/harness.py" "$@"
