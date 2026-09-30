#!/usr/bin/env bash
# ui-framework-packs.test.sh — offline guard for the non-React UI framework packs (board review
# 2026-09-30, root cause #14 / ARCH-13). Every code block in frameworks/{vue,svelte,angular}.md is
# either compiled by tests/archetype-compile/ui-frameworks/run.sh (a `file: src/…` marker) or listed
# in its skips.tsv with a reason; each pack states the versions it was verified against; the
# harness scaffolds are pinned by a lockfile. The compile + test run itself needs npm and lives in
# run.sh (not here, so this suite stays offline).
# Run: bash tests/ui-framework-packs.test.sh   (exit 0 = pass; bash 3.2 compatible; no network)
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$REPO/tests/archetype-compile/ui-frameworks"
PASS=0
FAIL=0
check() { if [ "$1" -eq 0 ]; then PASS=$((PASS + 1)); echo "  ✓ $2"; else FAIL=$((FAIL + 1)); echo "  ✗ $2"; fi; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for fw in vue svelte angular; do
  pack="$REPO/.claude/skills/frameworks/$fw.md"
  [ -f "$pack" ]; check $? "frameworks/$fw.md exists"
  out="$(python3 "$H/extract.py" pack --pack "$pack" --dest "$TMP/$fw" --skips "$H/skips.tsv" --manifest "$TMP/$fw.tsv" 2>&1)"
  check $? "$fw.md: every code block is compiled by run.sh or skipped with a reason${out:+ — $out}"
  n="$(grep -c '^CHECKED' "$TMP/$fw.tsv" 2>/dev/null || echo 0)"
  [ "$n" -ge 10 ]; check $? "$fw.md: at least 10 compile-checked blocks ($n)"
  grep -qE '^> Verified against .*\(.*20[0-9]{2}-[0-9]{2}-[0-9]{2}\)' "$pack"
  check $? "$fw.md: states the versions it was verified against, with the date"
  [ -f "$H/$fw/package.json" ] && [ -f "$H/$fw/package-lock.json" ]
  check $? "$fw harness scaffold is pinned (package.json + package-lock.json)"
done
[ -z "$(find "$H" -name node_modules -print -quit)" ]; check $? "no node_modules committed under the harness"

echo "ui-framework-packs.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
