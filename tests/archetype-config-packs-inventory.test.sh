#!/usr/bin/env bash
# archetype-config-packs-inventory.test.sh — every non-application code block (sql, sh, yaml, json,
# dockerfile, hcl, ngql) in .claude/skills outside backend/archetypes and ui/archetypes is either
# checked by tests/archetype-compile/config-packs/run.sh or skipped there with a reason, and no block
# count or first line changed since units.py was written. Needs only python3; the checks themselves
# need the tools listed in run.sh: run `bash tests/archetype-compile/config-packs/run.sh` (and --live)
# after editing any of those blocks.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/archetype-compile/config-packs/harness.py" --inventory-only
