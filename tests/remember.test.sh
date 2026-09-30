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

# A missing --fact must fail (exit 3) and must NOT record a blank fact that supersedes the real one.
# Run under /bin/bash explicitly: macOS ships bash 3.2, where the old ${k,,} silently skipped the exit.
before="$(grep -c '^### F-' docs/PROJECT_FACTS.md)"
CLAUDE_PROJECT_DIR="$W" /bin/bash "$R" add --subject svc-b --relation environment --title "oops" --date 2026-07-09 >/dev/null 2>&1; rc=$?
after="$(grep -c '^### F-' docs/PROJECT_FACTS.md)"
[ "$rc" = "3" ] && [ "$before" = "$after" ] && ok "missing --fact → exit 3, nothing recorded (bash 3.2)" || bad "missing --fact: rc=$rc, facts $before→$after"
lst="$(CLAUDE_PROJECT_DIR="$W" bash "$R" list)"
echo "$lst" | grep -q 'svc-b env' && ! echo "$lst" | grep -q 'oops' && ok "real svc-b fact still active, no blank 'oops' fact" || bad "svc-b fact was superseded by a blank one"

# --- decide: the only writer of docs/DECISIONS.md (the guard denies direct edits — SEC-04) ---
D="docs/DECISIONS.md"
CLAUDE_PROJECT_DIR="$W" bash "$R" decide --title "Use Postgres" --scope global --date 2026-09-30 --source adr \
  --confidence reported --link docs/adr/ADR-001.md --decision "PostgreSQL 17" --rationale "JSONB + RLS; MySQL rejected for RLS" >/dev/null
CLAUDE_PROJECT_DIR="$W" bash "$R" decide --title "Use cursor pagination" --scope global --date 2026-09-30 --source debate \
  --decision "cursor in meta.pagination" --rationale "stable under concurrent writes" >/dev/null
grep -q '^### D-001 — Use Postgres' "$D" && grep -q '^### D-002 — Use cursor pagination' "$D" && ok "decide assigns D-001, D-002 in order" || bad "decide ids wrong"
awk '/^### D-001/{p=1} p&&/^- source: adr/{s=1} p&&/^- confidence: reported/{c=1} /^### D-002/{p=0} END{exit !(s&&c)}' "$D" \
  && ok "decide records source + confidence (provenance)" || bad "provenance missing"
CLAUDE_PROJECT_DIR="$W" bash "$R" decide --title "Use CockroachDB" --scope global --date 2026-10-01 --source human:/remember \
  --decision "CockroachDB" --rationale "multi-region" --reverses D-001 >/dev/null
awk '/^### D-001/{p=1} p&&/^- status: reversed/{s=1} p&&/^- reversed_by: D-003/{r=1} /^### D-002/{p=0} END{exit !(s&&r)}' "$D" \
  && ok "--reverses flips D-001 to reversed, reversed_by D-003" || bad "reversal not stamped"
inj="$(CLAUDE_PROJECT_DIR="$W" bash "$I" 2>/dev/null | grep '### D-')"
echo "$inj" | grep -q 'D-001' && bad "inject hook surfaced reversed D-001" || { echo "$inj" | grep -q 'D-003' && ok "inject hook: active decisions only (D-002, D-003)" || bad "inject hook missing D-003"; }
before="$(grep -c '^### D-' "$D")"
CLAUDE_PROJECT_DIR="$W" bash "$R" decide --title "x" --scope global --date 2026-10-01 >/dev/null 2>&1; rc=$?
[ "$rc" = 3 ] && [ "$(grep -c '^### D-' "$D")" = "$before" ] && ok "decide without --decision/--rationale → exit 3, nothing written" || bad "incomplete decide wrote an entry (rc=$rc)"

echo "────────────────────────────────────────────"
echo "remember.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
