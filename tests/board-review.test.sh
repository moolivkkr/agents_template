#!/usr/bin/env bash
# board-review.test.sh — /board-review's deterministic half (board-review.py: targets, citation checks, blind
# verification inputs, merge and scores, compare) and the command/checklist wiring.
set -uo pipefail
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/board_review_cases.py"
