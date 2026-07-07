#!/usr/bin/env bash
# remember.test.sh — regression test for deterministic bi-temporal fact supersession.
# Proves .claude/hooks/remember.sh assigns ids correctly, supersedes on the exact (subject,relation)
# key, and that the SessionStart inject hook surfaces ONLY active facts (no phantom from the template
# example). Run: bash tests/remember.test.sh   (exit 0 = pass)

set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TEST_DIR/.." && pwd)"
R="$REPO_ROOT/.claude/hooks/remember.sh"
I="$REPO_ROOT/.claude/hooks/inject-project-facts.sh"

PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
mkdir -p "$W/.claude/templates" "$W/docs"
cp "$REPO_ROOT/.claude/templates/PROJECT_FACTS.md.template" "$W/.claude/templates/"
cd "$W" && git init -q

CLAUDE_PROJECT_DIR="$W" bash "$R" add --subject svc-a --relation lifecycle --title "svc-a retired" --date 2026-07-07 --fact "retired" >/dev/null
CLAUDE_PROJECT_DIR="$W" bash "$R" add --subject svc-b --relation environment --title "svc-b env" --date 2026-07-07 --fact "port 5433" >/dev/null
CLAUDE_PROJECT_DIR="$W" bash "$R" add --subject svc-a --relation lifecycle --title "svc-a revived" --date 2026-07-08 --fact "back" >/dev/null

active="$(CLAUDE_PROJECT_DIR="$W" bash "$R" list)"
echo "$active" | grep -q 'F-002' && echo "$active" | grep -q 'F-003' || bad "expected F-002 + F-003 active"
echo "$active" | grep -q 'F-001' && bad "F-001 should be superseded, not in active list" || ok "supersession: F-001 dropped from active"
[ "$(echo "$active" | grep -c '### F-')" = "2" ] && ok "exactly 2 active facts" || bad "expected exactly 2 active"

# F-001 block must be status: superseded, superseded_by F-003
if awk '/### F-001/{p=1} p&&/superseded_by: F-003/{f=1} /### F-002/{p=0} END{exit !f}' docs/PROJECT_FACTS.md; then
  ok "F-001 superseded_by F-003 stamped"
else bad "F-001 not stamped superseded_by F-003"; fi

# inject hook surfaces only active facts, no phantom F-001
inj="$(CLAUDE_PROJECT_DIR="$W" bash "$I" 2>/dev/null | grep '### F-')"
echo "$inj" | grep -q 'F-001' && bad "inject hook surfaced phantom/ superseded F-001" || ok "inject hook: no phantom F-001"

# no leftover pedagogical example comment in the live file
grep -q 'Example (delete' docs/PROJECT_FACTS.md && bad "template example comment leaked into live file" || ok "example comment stripped"

echo "────────────────────────────────────────────"
echo "remember.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
