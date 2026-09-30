#!/usr/bin/env bash
# docs-and-acceptance-map.test.sh — docs-policy.py (optional documents are lean by default, every gated key
# exists) and acceptance-map.py (a changed requirement or a new phase shows up as blocking acceptance work).
set -uo pipefail
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/docs_acceptance_cases.py"
