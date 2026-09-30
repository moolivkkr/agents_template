#!/bin/bash
# smoke.sh <dev|qa> [expected-git-sha] — post-rollout checks against http://<app>-<env>.localhost:<port>.
# Every SMOKE_PATHS entry must return 200 (retried briefly while the ingress picks up new endpoints);
# VERSION_PATH, when set, must report the expected git sha. Prints one JSON object on stdout:
#   {"url", "total", "passed", "failed", "failures": [{"path", "got"}]}     exit 0 only if failed == 0
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
env_setup "${1:-}"
WANT_SHA="${2:-}"
TOTAL=0; FAILED=0; FAILURES=""

check() {  # $1 path, $2 ok|fail, $3 detail
  TOTAL=$((TOTAL + 1))
  if [ "$2" != ok ]; then
    FAILED=$((FAILED + 1))
    FAILURES="$FAILURES${FAILURES:+,}{\"path\":\"$1\",\"got\":\"$3\"}"
    log "smoke FAIL $BASE_URL$1 -> $3"
  else log "smoke ok   $BASE_URL$1"; fi
}

for p in $SMOKE_PATHS; do
  code=000
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BASE_URL$p" || true)"
    [ "$code" = 200 ] && break; sleep 2
  done
  [ "$code" = 200 ] && check "$p" ok "" || check "$p" fail "HTTP $code"
done

if [ -n "${VERSION_PATH:-}" ] && [ -n "$WANT_SHA" ]; then
  got="$(curl -s -m 5 "$BASE_URL$VERSION_PATH" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("git_sha",""))' 2>/dev/null || true)"
  [ "$got" = "$WANT_SHA" ] && check "$VERSION_PATH" ok "" || check "$VERSION_PATH" fail "git_sha=${got:-none} want $WANT_SHA"
fi

printf '{"url":"%s","total":%d,"passed":%d,"failed":%d,"failures":[%s]}\n' "$BASE_URL" "$TOTAL" "$((TOTAL - FAILED))" "$FAILED" "$FAILURES"
[ "$FAILED" -eq 0 ]
