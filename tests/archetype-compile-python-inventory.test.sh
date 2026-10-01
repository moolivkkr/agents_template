#!/usr/bin/env bash
# archetype-compile-python-inventory.test.sh — every ```python block in .claude/skills (the backend
# archetypes and every other pack) is either checked by a unit of tests/archetype-compile/python
# (units.py, units_packs.py) or listed there as comment-only / skipped with a reason, block counts and
# anchors match the config, and no Python fence is in a form the extractor would miss. Needs only
# python3; compiling and running the samples needs the venv: run
# `bash tests/archetype-compile/python/run.sh` (and `--live`) after editing any Python sample.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ... and every lower_snake details[].code a Python sample puts on the wire is in the closed set in
# api/response-envelope.md.
rc=0
python3 "$DIR/archetype-compile/python/harness.py" --inventory-only || rc=1
python3 "$DIR/lib/field_codes.py" --lang python || rc=1
exit $rc
