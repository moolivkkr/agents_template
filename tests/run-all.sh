#!/usr/bin/env bash
# run-all.sh — run every framework enforcement test. Wire into CI / pre-commit so a change that
# weakens the deterministic guarantees (verify-gate.sh, remember.sh, inject-project-facts.sh) fails
# the build instead of silently passing a bad gate. Exit 0 = all green.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RC=0
for t in "$DIR"/*.test.sh; do
  echo "▶ $(basename "$t")"
  bash "$t" || RC=1
  echo ""
done
[ "$RC" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit "$RC"
