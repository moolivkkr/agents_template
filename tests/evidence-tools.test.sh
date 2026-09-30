#!/usr/bin/env bash
# evidence-tools.test.sh — junit-to-sidecar.py and tc-inventory.py against the loopholes the 2026-09-30
# board review found (skipped/comment-only/recycled TC IDs, retried flakes, crashed runners, weakened tests).
set -uo pipefail
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/evidence_tools_cases.py"
