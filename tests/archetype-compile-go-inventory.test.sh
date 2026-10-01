#!/usr/bin/env bash
# archetype-compile-go-inventory.test.sh — every ```go block in .claude/skills/** (the backend
# archetypes and every other pack: languages/go.md, frameworks/*, testing/*, core/*, ...) is either
# compiled by tests/archetype-compile/go/run.sh or listed there as skipped with a reason; a pack file
# with Go blocks that units.json doesn't list fails; and the blocks haven't moved since units.json
# was written. Needs only python3; the compile itself needs Go: run
# `bash tests/archetype-compile/go/run.sh` after editing any Go sample.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/archetype-compile/go/harness.py" --inventory-only
