#!/usr/bin/env bash
# archetype-compile-typescript-inventory.test.sh — every TypeScript/TSX/JavaScript block in the archetypes
# (.claude/skills/{backend,ui}/archetypes) and in the backend packs agents copy from (languages/typescript.md,
# frameworks/{express,fastify,nestjs,trpc,graphql}.md, testing/{vitest,testcontainers,contract-testing,
# property-based,load-testing}.md, core/, security/, api/) is either compiled by
# tests/archetype-compile/typescript/run.sh or listed there as skipped with a reason, and each file's block
# count still matches units.py. Needs only python3 (no npm, no tsc); the compile itself needs Node:
# run `bash tests/archetype-compile/typescript/run.sh` after editing any TypeScript sample.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/archetype-compile/typescript/harness.py" --inventory-only
