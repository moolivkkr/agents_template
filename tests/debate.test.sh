#!/usr/bin/env bash
# debate.test.sh — the decision debate system: debate-status.py (the one reader of agent_state/debates/)
# and a lint of the debate prompts and wiring, so the 2026-09-30 fixes (D1-D11) cannot silently regress.
set -uo pipefail
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/debate_cases.py"
