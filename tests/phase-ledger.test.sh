#!/usr/bin/env bash
# phase-ledger.test.sh — the observe-only phase ledger (.claude/hooks/ledger.py, docs/PHASE_LEDGER.md):
# recorded claude -p payloads replayed through the hook, every event type, spawn→start matching (parallel same-type
# spawns with and without TASK tags, background spawns, exact links from .meta.json), phase derivation, 20 parallel
# writers under the lock, never-fail on garbage/unwritable dirs, task card on/off/env and size, report filtering
# by phase / --since / budget / roster compare, rotation, settings wiring, and startup-project-update --ledger-only
# on a temp git project with uncommitted work. Run: bash tests/phase-ledger.test.sh   (exit 0 = pass)
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -B "$DIR/lib/ledger_cases.py"
