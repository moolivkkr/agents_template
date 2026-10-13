#!/usr/bin/env bash
# archetype-compile-rust.test.sh — the cheap half of tests/archetype-compile/rust/run.sh, safe for
# run-all: every ```rust block in .claude/skills/backend/archetypes/*.md is compiled by a unit of the
# compile harness or skipped with a reason, each file's block count matches the harness config (an
# added or removed sample fails here until the harness is updated), no doc-comment ``` fence would
# become a doctest `cargo test` compiles, no axum route has a `:param` segment (a startup panic since
# axum 0.8), and every Rust Dockerfile builder / rust-toolchain.toml equals the harness's pinned
# toolchain, and the Dockerfile variants docker-check.sh builds still compose and set a numeric USER.
# Also covers languages/rust.md, the axum / actix-web / graphql framework packs, testing/rust-test.md
# and the Rust blocks of the shared testing packs — and fails if any other .claude/skills file gains a
# ```rust block the harness does not list. Needs only python3 (no Rust, no network).
#
# The full check — cargo check of every unit, sqlx macros against .sqlx/, Cargo manifests — is
#   bash tests/archetype-compile/rust/run.sh
# Run: bash tests/archetype-compile-rust.test.sh   (exit 0 = pass)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# harness.py reads Cargo.toml with tomllib (Python 3.11+); macOS's python3 is 3.9, so take the first newer one
PY=python3
for c in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import tomllib' 2>/dev/null; then PY="$c"; break; fi
done
"$PY" "$TEST_DIR/archetype-compile/rust/harness.py" --coverage-only
