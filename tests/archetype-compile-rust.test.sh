#!/usr/bin/env bash
# archetype-compile-rust.test.sh — the cheap half of tests/archetype-compile/rust/run.sh, safe for
# run-all: every ```rust block in .claude/skills/backend/archetypes/*.md is compiled by a unit of the
# compile harness or skipped with a reason, each file's block count matches the harness config (an
# added or removed sample fails here until the harness is updated), and no doc-comment ``` fence would
# become a doctest `cargo test` compiles. Needs only python3 (no Rust toolchain, no network).
#
# The full check — cargo check of every unit, sqlx macros against .sqlx/, Cargo manifests — is
#   bash tests/archetype-compile/rust/run.sh
# Run: bash tests/archetype-compile-rust.test.sh   (exit 0 = pass)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$TEST_DIR/archetype-compile/rust/harness.py" --coverage-only
