#!/usr/bin/env bash
# field-codes.test.sh — every lower_snake details[].code a skill sample or template puts on the wire is in the
# closed set in .claude/skills/api/response-envelope.md, so one client mapping works for every service.
# Also proves the checker still catches a stray code (a scratch copy with one planted).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

if out="$(python3 "$DIR/lib/field_codes.py" --root "$ROOT" 2>&1)"; then ok "no skill sample sends a details[].code outside the closed set"
else bad "details[].code outside the closed set:"; echo "$out" | sed 's/^/      /'; fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/.claude/skills/api" "$T/.claude/skills/x" "$T/.claude/agents/templates"
cp "$ROOT/.claude/skills/api/response-envelope.md" "$T/.claude/skills/api/"
printf '```go\nreturn apperr.NewValidationError("limit", "too_big", "x")\n```\n' > "$T/.claude/skills/x/planted.md"
if python3 "$DIR/lib/field_codes.py" --root "$T" >/dev/null 2>&1; then bad "the checker missed a planted 'too_big'"; else ok "the checker catches a planted stray code"; fi
printf '```ts\nconst e = { field: "name", code: "required", message: "This field is required." }\n```\n' > "$T/.claude/skills/x/planted.md"
if python3 "$DIR/lib/field_codes.py" --root "$T" >/dev/null 2>&1; then ok "a code from the set passes"; else bad "a code from the set was flagged"; fi

echo "field-codes.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
