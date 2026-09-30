#!/usr/bin/env bash
# sdlc-guard.test.sh — table test for the user-level permission guard (.claude/guard/): allow/ask/deny
# per command, kube identity pinning, namespace patterns, the policy generator, the PATH shim and the
# SessionStart env hook. Run: bash tests/sdlc-guard.test.sh   (exit 0 = pass)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$TEST_DIR/lib/sdlc_guard_cases.py"
