#!/usr/bin/env bash
# sdlc-graph.test.sh — the artifact graph + deterministic TC gate (.claude/hooks/sdlc-graph.py): ranges,
# cross-phase/in-phase duplicates, comment-only and skipped IDs, priority handling, malformed IDs, results mode,
# test weakening, incremental == full rebuild, output budgets, agent queries, verify-gate check (h), and
# agreement with tc-inventory.py on every ID it sees.
set -uo pipefail
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/sdlc_graph_cases.py"
