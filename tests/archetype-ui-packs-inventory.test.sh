#!/usr/bin/env bash
# archetype-ui-packs-inventory.test.sh — offline guard for the React / Next.js / React Native / UI / UI-test packs
# (frameworks/{react,nextjs,tanstack-query,react-native,react-native-app-patterns}.md, ui/*.md,
# testing/{msw,playwright,react-native-testing-library,detox,appium-mobile,mobile-testing-strategy,
# test-case-generation,test-case-traceability}.md). Every ```tsx/ts/typescript/jsx/javascript/js block is
# compiled by a unit of tests/archetype-compile/ui-packs or skipped there with a reason, block counts match,
# each checked pack says what it was compile-checked against (dated), the projects are pinned, and the
# fixes those runs proved stay fixed (no token in web storage or a URL, the one envelope, MSW names).
# The compile/run itself needs npm: bash tests/archetype-compile/ui-packs/run.sh
# Run: bash tests/archetype-ui-packs-inventory.test.sh   (exit 0 = pass; bash 3.2 compatible; no network)
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$REPO/tests/archetype-compile/ui-packs"
S="$REPO/.claude/skills"
T="$REPO/.claude/agents/templates"
PASS=0
FAIL=0
check() { if [ "$1" -eq 0 ]; then PASS=$((PASS + 1)); echo "  ✓ $2"; else FAIL=$((FAIL + 1)); echo "  ✗ $2"; fi; }

echo "── block inventory (units.py ↔ the packs) ──"
out="$(python3 "$H/harness.py" --inventory 2>&1)"
rc=$?
echo "$out"
check $rc "harness.py --inventory"

echo "── the fixes the runs proved ──"
UI_PACKS="$S/ui/api-integration-patterns.md $S/ui/advanced-state-patterns.md"
hits="$(grep -nE '(localStorage|sessionStorage)\.(getItem|setItem)\([^)]*(token|jwt|auth)' $UI_PACKS)"
[ -z "$hits" ]; check $? "api-integration / advanced-state read or write no token in web storage${hits:+ — $hits}"
hits="$(grep -nE '[?&](token|access_token|jwt)=' $UI_PACKS | grep -vE 'never|Never|NEVER|\| Token in a URL')"
[ -z "$hits" ]; check $? "api-integration / advanced-state put no token in a URL${hits:+ — $hits}"
grep -q 'credentials: "same-origin"' "$S/ui/api-integration-patterns.md" && grep -q 'X-CSRF-Token' "$S/ui/api-integration-patterns.md"
check $? "api-integration-patterns.md: cookie session + CSRF header in the fetch client"
! grep -q 'those examples are wrong' "$T/ui_developer.tmpl"
check $? "ui_developer.tmpl no longer carries the 'those examples are wrong' caveat (the examples are fixed)"
grep -qE 'never written to `localStorage`, `sessionStorage`' "$T/ui_developer.tmpl" && grep -q 'never put in URLs' "$T/ui_developer.tmpl"
check $? "ui_developer.tmpl still states the rule: no token in web storage or URLs (Security rules 1)"
hits="$(grep -nE 'VALIDATION_ERROR|details\??\.fields|error\.status === 422' "$S/ui/form-patterns.md" "$S/ui/form-validation-protocol.md" "$S/ui/error-handling-patterns.md")"
[ -z "$hits" ]; check $? "form packs map 400 VALIDATION_FAILED details[], not a second error shape${hits:+ — $hits}"
hits="$(grep -nE 'ApiResponse<|meta\.total\b|old\.meta\.total' "$S/ui/advanced-state-patterns.md")"
[ -z "$hits" ]; check $? "advanced-state-patterns.md uses the one envelope (ApiSuccess, no meta.total)${hits:+ — $hits}"
hits="$(grep -nE 'required_error|z\.string\(\)\.(email|url)\(' "$S"/ui/*.md "$S/frameworks/react.md" | grep -v 'Zod 4')"   # lines naming the old API in a "Zod 4: …" note are prose
[ -z "$hits" ]; check $? "Zod 4 APIs: no required_error, no z.string().email()/url()${hits:+ — $hits}"
grep -q 'onUnhandledFrame: "error"' "$S/testing/msw.md"
check $? "msw.md (MSW 3) uses onUnhandledFrame"
grep -q "onUnhandledRequest: 'error'" "$S/testing/react-native-testing-library.md" \
  && grep -q "customExportConditions: \['node', 'require', 'react-native'\]" "$S/testing/react-native-testing-library.md" \
  && grep -q "import { server } from './test/msw-server'" "$S/testing/react-native-testing-library.md"
check $? "react-native-testing-library.md: msw@2 on the RN Jest tier, with the export condition and the server import"
grep -q 'wrapper: TestProviders' "$S/testing/react-native-testing-library.md" && grep -q 'renderWithProviders' "$S/testing/msw.md"
check $? "screen tests render inside a QueryClientProvider (RNTL TestProviders, msw.md renderWithProviders)"
grep -q 'proxy.ts' "$S/frameworks/nextjs.md" && grep -q 'requireSession' "$S/frameworks/nextjs.md"
check $? "nextjs.md: Next 16 proxy.ts, and the Server Action authorizes itself"

echo "── harness hygiene ──"
[ -z "$(find "$H" -name node_modules -prune -print -quit)" ] || git -C "$REPO" check-ignore -q "$H/web/node_modules"
check $? "node_modules is never committed (absent or git-ignored)"
[ -z "$(git -C "$REPO" ls-files "$H" | grep -E '(^|/)(node_modules|\.units|test-results|playwright-report)/')" ]
check $? "no node_modules/, .units/ or Playwright output is tracked"

echo "archetype-ui-packs-inventory.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
