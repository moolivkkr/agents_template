#!/usr/bin/env bash
# testing-agents.test.sh — deterministic guards for the testing agents and skills after the
# 2026-09-30 board review (docs/AGENT_BOARD_REVIEW_2026-09-30.md). Each check names the finding it
# guards, so a regression points straight at the reason the rule exists.
# Bash 3.2 compatible (macOS /bin/bash): no associative arrays, no mapfile, grep -E only (BSD grep).
# Run: bash tests/testing-agents.test.sh   (exit 0 = pass)

set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
A="$ROOT/.claude/agents"; S="$ROOT/.claude/skills/testing"; H="$ROOT/.claude/hooks"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

TEMPLATES="unit_test_agent integration_test_agent ui_test_agent mobile_test_agent"
CORE_TEST="test_runner e2e_orchestrator mobile_e2e_orchestrator acceptance_test_agent system_test_agent performance_agent spec_test_reconciler"
file_of() {  # agent name → its file
  if [ -f "$A/templates/${1}.tmpl" ]; then echo "$A/templates/${1}.tmpl"; else echo "$A/core/${1}.md"; fi
}
ALL_TEST_AGENTS="$TEMPLATES $CORE_TEST manual_test_agent accessibility_auditor"

echo "── base URL: the deployed build, never a hard-coded dev target (ARCH-09, TEST-09, OPS-02, OPS-11) ──"
for a in $ALL_TEST_AGENTS; do
  f="$(file_of "$a")"
  if grep -nE 'localhost:(8080|3000)|npm run dev' "$f" >/dev/null; then
    bad "$a hard-codes a dev target: $(grep -nE 'localhost:(8080|3000)|npm run dev' "$f" | head -2 | tr '\n' ' ')"
  else ok "$a: no localhost:8080/3000 or npm run dev target"; fi
done
for a in e2e_orchestrator mobile_e2e_orchestrator acceptance_test_agent performance_agent system_test_agent accessibility_auditor ui_test_agent mobile_test_agent; do
  grep -q 'APP_BASE_URL' "$(file_of "$a")" && ok "$a targets APP_BASE_URL" || bad "$a never mentions APP_BASE_URL"
done
if grep -nE 'localhost:3000|webServer:|npm run dev' "$S/playwright.md" >/dev/null; then
  bad "playwright.md still starts a dev server / hard-codes localhost:3000"
else ok "playwright.md: baseURL from APP_BASE_URL, no webServer"; fi
grep -q 'process.env.APP_BASE_URL' "$S/playwright.md" && ok "playwright.md reads APP_BASE_URL" || bad "playwright.md does not read APP_BASE_URL"
if grep -nE 'localhost:\$PORT/health|localhost:PORT' "$A/core/mobile_e2e_orchestrator.md" >/dev/null; then
  bad "mobile_e2e_orchestrator preflight still assumes a compose localhost backend (OPS-11)"
else ok "mobile_e2e_orchestrator preflight uses APP_BASE_URL, not a compose localhost"; fi
grep -q 'Host' "$A/core/mobile_e2e_orchestrator.md" && grep -q '10.0.2.2' "$A/core/mobile_e2e_orchestrator.md" \
  && ok "mobile_e2e_orchestrator: Android via 10.0.2.2 with the Host header (OPS-11)" || bad "mobile_e2e_orchestrator lacks the 10.0.2.2 + Host header rule"

echo "── evidence: runner JUnit → sidecar, never prose (TEST-01) ──"
for a in $TEMPLATES test_runner e2e_orchestrator mobile_e2e_orchestrator acceptance_test_agent system_test_agent performance_agent; do
  f="$(file_of "$a")"
  grep -q 'test-results-sidecar.md' "$f" && grep -q 'junit-to-sidecar.py' "$f" \
    && ok "$a references test-results-sidecar.md and junit-to-sidecar.py" \
    || bad "$a does not reference both test-results-sidecar.md and junit-to-sidecar.py"
done
grep -q 'tc-inventory.py' "$A/core/spec_test_reconciler.md" && grep -q 'test-results-sidecar.md' "$A/core/spec_test_reconciler.md" \
  && ok "spec_test_reconciler builds its sidecar with tc-inventory.py" || bad "spec_test_reconciler lacks tc-inventory.py / sidecar skill"
# Report names must be the ones the orchestrator and the gate look for.
for pair in unit_test_agent:unit_tests integration_test_agent:integration_tests ui_test_agent:ui_test_results \
            mobile_test_agent:mobile_test_results e2e_orchestrator:e2e_results mobile_e2e_orchestrator:mobile_e2e_results \
            acceptance_test_agent:acceptance_report performance_agent:performance_results test_runner:test_results \
            system_test_agent:system_test_results; do
  a="${pair%%:*}"; r="${pair##*:}"; f="$(file_of "$a")"
  if grep -q "reports/${r}.json" "$f" && grep -q "\"report\":\"agent_state/phases/{{PHASE}}/reports/${r}.md\"" "$f"; then
    ok "$a writes reports/${r}.json beside reports/${r}.md (its completion line)"
  else bad "$a: report name drift — expected reports/${r}.md + .json"; fi
done
grep -q 'agent_state/reconciliation/phase-{{PHASE}}/specs_vs_tests.json' "$A/core/spec_test_reconciler.md" \
  && ok "spec_test_reconciler writes specs_vs_tests.json beside specs_vs_tests.md (gate treats it as a test agent)" \
  || bad "spec_test_reconciler does not write specs_vs_tests.json"
for a in $TEMPLATES e2e_orchestrator mobile_e2e_orchestrator acceptance_test_agent; do
  grep -q 'agent_state/phases/{{PHASE}}/junit/' "$(file_of "$a")" && ok "$a writes JUnit under agent_state/phases/{{PHASE}}/junit/" \
    || bad "$a does not write JUnit under the phase junit dir (dirty-tree evidence)"
done

echo "── TC coverage by parser, never grep (TEST-02, DEV-13, TEST-17) ──"
for f in "$A/core/spec_test_reconciler.md" "$S/test-case-traceability.md" "$ROOT/.claude/commands/test.md"; do
  if grep -nE 'grep -r?h?oP|grep -rhoP' "$f" >/dev/null; then bad "$(basename "$f") still has a grep -P TC inventory"
  else ok "$(basename "$f"): no grep -rhoP inventory"; fi
done
grep -q 'tc-inventory.py' "$S/test-case-traceability.md" && ok "test-case-traceability.md points at tc-inventory.py" || bad "test-case-traceability.md does not use tc-inventory.py"

echo "── test_runner commands: only the command table, no broken fallbacks (OPS-05, TEST-15, OPS-06) ──"
TR="$A/core/test_runner.md"
if grep -nE -- '-- --run|pytest --integration' "$TR" >/dev/null; then bad "test_runner still has the Jest --run / pytest --integration fallback"
else ok "test_runner has no --run / --integration fallback flags"; fi
grep -q 'verify-commands.json' "$TR" && ok "test_runner reads verify-commands.json" || bad "test_runner does not read verify-commands.json"
grep -q -- '-count=1' "$TR" && ok "test_runner: Go -count=1 (no cached results)" || bad "test_runner lacks -count=1"
grep -q 'refreshed_by' "$TR" && grep -q 'reports/writer/' "$TR" && ok "test_runner refreshes writer sidecars and keeps the writer copy" || bad "test_runner does not refresh tier sidecars"
grep -q 'mutation-testing.md' "$TR" && grep -q 'mutation-testing.md' "$A/templates/unit_test_agent.tmpl" \
  && ok "mutation-testing.md is loaded by test_runner and unit_test_agent (TEST-06)" || bad "mutation-testing.md not referenced by test_runner and unit_test_agent"
[ -f "$S/mutation-testing.md" ] && grep -q 'gremlins' "$S/mutation-testing.md" && grep -q -i 'stryker' "$S/mutation-testing.md" && grep -q 'mutmut' "$S/mutation-testing.md" \
  && ok "mutation-testing.md covers gremlins, Stryker and mutmut" || bad "mutation-testing.md missing or incomplete"

echo "── unit tier: spec oracle, red first, colocated Go tests (TEST-06, TEST-07, DEV-12) ──"
U="$A/templates/unit_test_agent.tmpl"
if grep -qE 'primary: *"?tests/unit/' "$U"; then bad "unit_test_agent output is still tests/unit/ (0% per-package Go coverage)"; else ok "unit_test_agent no longer writes Go tests to tests/unit/"; fi
grep -q 'reproduction-first.md' "$U" && ok "unit_test_agent loads reproduction-first.md (red first)" || bad "unit_test_agent lacks reproduction-first.md"
grep -qi 'from the spec' "$U" && ok "unit_test_agent derives expected values from the spec" || bad "unit_test_agent lacks the spec-oracle rule"

echo "── UI tier: correct axe API, no jsdom contrast, typed mocks, the UI manifest (TEST-19, DEV-03, ARCH-01, ARCH-08) ──"
UI="$A/templates/ui_test_agent.tmpl"
if grep -nE 'import[^;]*(injectAxe|checkA11y)[^;]*@axe-core/playwright' "$UI" "$S/playwright.md" >/dev/null; then
  bad "an injectAxe/checkA11y import from @axe-core/playwright remains"
else ok "no injectAxe/checkA11y import from @axe-core/playwright"; fi
grep -q 'AxeBuilder' "$UI" && ok "ui_test_agent uses AxeBuilder" || bad "ui_test_agent lacks AxeBuilder"
grep -qi 'color-contrast' "$UI" && ok "ui_test_agent states jsdom/jest-axe can't check contrast" || bad "ui_test_agent does not warn about jsdom contrast"
if grep -nE 'error: null' "$UI" "$A/templates/mobile_test_agent.tmpl" "$S/msw.md" "$S/react-native-testing-library.md" >/dev/null; then
  bad "a mock still hand-shapes { data, error: null, meta } (contradicts api/response-envelope.md)"
else ok "no hand-shaped '{ data, error: null, meta }' mocks in UI/mobile agents or mock skills"; fi
if grep -nE '"data", "error", "meta" keys' "$A/templates/integration_test_agent.tmpl" >/dev/null; then
  bad "integration_test_agent still has the wrong 'data, error, meta — no extra' envelope rule"
else ok "integration_test_agent envelope rule follows response-envelope.md"; fi
grep -q 'HttpResponse.json<ApiSuccess' "$S/msw.md" && ok "msw.md builds mocks from the envelope types" || bad "msw.md mocks are not typed from the envelope"
grep -q 'ui_developer/manifest.json' "$UI" && ok "ui_test_agent reads ui_developer/manifest.json" || bad "ui_test_agent does not read ui_developer/manifest.json"
grep -q 'XSS-RENDER' "$UI" && grep -q 'SESSION-STORAGE' "$UI" && ok "ui_test_agent has XSS-RENDER and SESSION-STORAGE rows (SEC-08/09/12)" || bad "ui_test_agent lacks XSS-RENDER/SESSION-STORAGE"

echo "── flake policy: no retries to green (TEST-10, SRE-11) ──"
grep -q 'retries: 0' "$S/playwright.md" && grep -q 'failOnFlakyTests: true' "$S/playwright.md" && grep -q 'forbidOnly: true' "$S/playwright.md" \
  && ok "playwright.md: retries 0, failOnFlakyTests, forbidOnly" || bad "playwright.md flake policy incomplete"
if grep -nE 'retries: process\.env\.CI \? [1-9]' "$S/playwright.md" >/dev/null; then bad "playwright.md still retries in CI"; else ok "playwright.md has no CI retries"; fi
grep -q 'allowOnly: false' "$S/vitest.md" && ok "vitest.md: allowOnly false" || bad "vitest.md lacks allowOnly: false"

echo "── acceptance: committed specs, portable binary check, no seed endpoint (TEST-11, SEC-11, OPS-05) ──"
AC="$A/core/acceptance_test_agent.md"
if grep -q -- '-perm +111' "$AC"; then bad "acceptance_test_agent uses the BSD-only find -perm +111"; else ok "acceptance_test_agent has no -perm +111"; fi
grep -q 'tests/acceptance/' "$AC" && grep -q 'TC-ACC-' "$AC" && ok "acceptance_test_agent writes committed TC-ACC specs under tests/acceptance/" || bad "acceptance specs are not committed/named"
if grep -nE 'curl[^|]*-X POST[^|]*/seed' "$AC" >/dev/null; then bad "acceptance_test_agent still seeds through an HTTP seed endpoint"; else ok "acceptance_test_agent does not seed through an HTTP endpoint"; fi
grep -q 'use_cases' "$AC" && grep -q 'UNTESTED' "$AC" && ok "acceptance sidecar is per use case with UNTESTED cases" || bad "acceptance sidecar lacks use_cases/UNTESTED"

echo "── e2e_orchestrator scope comes from the spec inventory (ARCH-07, TEST-08, TEST-23) ──"
E2E="$A/core/e2e_orchestrator.md"
FM="$(awk 'NR==1 && /^---$/ {f=1; next} f && /^---$/ {exit} f' "$E2E")"
if printf '%s' "$FM" | grep -q 'e2e_workflows_unlocked'; then bad "e2e_orchestrator frontmatter still depends on e2e_workflows_unlocked"
else ok "e2e_orchestrator frontmatter has no e2e_workflows_unlocked input"; fi
if grep -n 'e2e_workflows_unlocked' "$E2E" | grep -v 'no producer' >/dev/null; then bad "e2e_orchestrator body still reads e2e_workflows_unlocked"
else ok "e2e_orchestrator body no longer reads e2e_workflows_unlocked"; fi
if grep -q 'e2e_workflows_unlocked' "$ROOT/.claude/commands/test.md"; then bad "/test still scopes e2e by e2e_workflows_unlocked"; else ok "/test no longer scopes e2e by e2e_workflows_unlocked"; fi
grep -q 'healthz' "$E2E" && grep -q 'bugs_found' "$E2E" && ok "e2e_orchestrator: /healthz preflight; app failures go to the owning role" || bad "e2e_orchestrator lacks preflight/owner routing"
grep -q 'playwright.md' "$E2E" && ok "e2e_orchestrator loads playwright.md (TEST-23)" || bad "e2e_orchestrator does not load playwright.md"

echo "── TC-ACC = acceptance, TC-A11Y = accessibility, everywhere (TEST-11) ──"
TRC="$S/test-case-traceability.md"; GEN="$S/test-case-generation.md"
grep -E '^\| `ACC` \|' "$TRC" | grep -q 'cceptance' && ok "traceability: ACC row means acceptance" || bad "traceability: ACC row does not mean acceptance"
grep -E '^\| `A11Y` \|' "$TRC" | grep -q 'ccessib' && ok "traceability: A11Y row means accessibility" || bad "traceability: A11Y row does not mean accessibility"
if grep -nE 'TC-ACC-[0-9{].*[Aa]ccessib' "$S"/*.md "$A"/templates/*.tmpl "$A"/core/*.md >/dev/null; then
  bad "a TC-ACC ID is used for an accessibility case: $(grep -nE 'TC-ACC-[0-9{].*[Aa]ccessib' "$S"/*.md "$A"/templates/*.tmpl "$A"/core/*.md | head -1)"
else ok "no TC-ACC ID is used for accessibility"; fi
OUTSIDE="$(awk '/^## Tier 5: Acceptance/ {in5=1} /^## Tier 6/ {in5=0} /TC-ACC-\{/ && !in5 {print NR": "$0}' "$GEN")"
[ -z "$OUTSIDE" ] && ok "test-case-generation.md uses TC-ACC only in the acceptance tier" || bad "TC-ACC outside the acceptance tier: $OUTSIDE"
grep -q 'TC-A11Y-{' "$GEN" && ok "test-case-generation.md generates TC-A11Y rows for accessibility" || bad "test-case-generation.md has no TC-A11Y rows"

echo "── abuse-case matrix and failure modes (root cause 5: SEC-12, SEC-06; root cause 7: SRE-10) ──"
for row in AUTHZ-OBJ AUTHZ-TENANT AUTHZ-FN MASS-ASSIGN INJ SSRF UPLOAD TOKEN-TAMPER TOKEN-EXPIRED RATE-LIMIT SESSION-STORAGE XSS-RENDER CORS ERR-LEAK SECRET-FAILCLOSED; do
  grep -qE "^\| \`${row}\` \|" "$GEN" && ok "abuse row $row is in test-case-generation.md §Abuse cases" || bad "abuse row $row missing from test-case-generation.md"
done
# Every row secure-coding.md's "Proof:" lines cite must exist in the matrix (the two files can't drift apart).
for row in $(grep 'Proof:' "$ROOT/.claude/skills/security/secure-coding.md" | grep -oE '`[A-Z][A-Z0-9-]+`' | tr -d '`' | sort -u); do
  grep -qE "^\| \`${row}\` \|" "$GEN" || bad "secure-coding.md cites Proof row $row, which test-case-generation.md lacks"
done
ok "every secure-coding.md Proof row checked against the matrix"
for row in DEP-DOWN DEP-SLOW TIMEOUT SIGTERM-DRAIN; do
  grep -qE "^\| \`${row}\` \|" "$GEN" && ok "failure-mode row $row present" || bad "failure-mode row $row missing"
done
grep -q 'Toxiproxy' "$A/templates/integration_test_agent.tmpl" && ok "integration_test_agent injects failures (Toxiproxy / container pause)" || bad "integration_test_agent has no failure-mode injection"
grep -q 'threat_model' "$A/core/spec_writer.md" && grep -q 'security-tests.md' "$A/core/spec_writer.md" \
  && ok "spec_writer merges threat-model TC-SEC rows into the inventory (SEC-06, TEST-13)" || bad "spec_writer does not merge TC-SEC rows"
grep -q 'threat_model.md' "$A/core/spec_test_reconciler.md" && grep -q 'NFR-PERF' "$A/core/spec_test_reconciler.md" \
  && ok "spec_test_reconciler checks TC-SEC and NFR-PERF rows exist" || bad "spec_test_reconciler ignores TC-SEC / NFR-PERF"

echo "── performance: an executed open-model test, not a recommendation (SRE-09, TEST-12) ──"
PF="$A/core/performance_agent.md"
grep -q 'constant-arrival-rate' "$PF" && ok "performance_agent uses constant-arrival-rate" || bad "performance_agent lacks the open model"
if grep -qi 'Recommend load test configuration' "$PF"; then bad "performance_agent still only recommends a load test"; else ok "performance_agent no longer only recommends a load test"; fi
grep -q 'dropped_iterations' "$PF" && grep -q 'handleSummary' "$PF" && ok "performance_agent gates dropped_iterations and reads handleSummary" || bad "performance_agent lacks dropped_iterations/handleSummary"
grep -qi 'coordinated omission' "$S/load-testing.md" && grep -q 'constant-arrival-rate' "$S/load-testing.md" \
  && ok "load-testing.md explains open vs closed and coordinated omission" || bad "load-testing.md lacks the open-model section"

echo "── WCAG version is stated once: 2.2 AA (ARCH-09 / auditor row) ──"
for f in "$A/core/accessibility_auditor.md" "$UI" "$S/playwright.md"; do
  if grep -nE 'WCAG 2\.1 AA' "$f" >/dev/null; then bad "$(basename "$f") still targets WCAG 2.1 AA"; else ok "$(basename "$f"): no WCAG 2.1 AA target"; fi
done
grep -q 'wcag22aa' "$A/core/accessibility_auditor.md" && ok "accessibility_auditor scans with the wcag22aa tag" || bad "accessibility_auditor lacks wcag22aa"
grep -q 'A11Y-BLOCKED' "$A/core/accessibility_auditor.md" && ok "accessibility_auditor blocks (not skips) when the UI is unreachable (TEST-19)" || bad "accessibility_auditor can still skip silently"

echo "── system and manual testers (system_test_agent row, manual_test_agent row) ──"
ST="$A/core/system_test_agent.md"
grep -q 'system_test_results.json' "$ST" && grep -q 'SYS-ROLLOUT' "$ST" && grep -q 'Why this agent exists' "$ST" \
  && ok "system_test_agent: rebuilt with a procedure, a sidecar and the decision recorded" || bad "system_test_agent lacks procedure/sidecar/decision"
grep -q 'subagent_type: system_test_agent' "$ROOT/.claude/commands/test.md" && ok "/test --system spawns system_test_agent" || bad "/test --system does not spawn system_test_agent"
MT="$A/core/manual_test_agent.md"
grep -q 'Code sha' "$MT" && grep -qi 'game day' "$MT" && grep -qi 'DR restore' "$MT" && grep -qi 'failover' "$MT" \
  && ok "manual_test_agent records env/URL/sha and has game-day, DR-restore and failover templates" || bad "manual_test_agent lacks env/sha or drill templates"
grep -q 'NEVER the value' "$MT" && ok "manual_test_agent never writes credentials into scripts" || bad "manual_test_agent lacks the no-credentials rule"

echo "── spec inventory: the documented table parses with tc-inventory.py (TEST-02) ──"
TREE="$TMP/proj"; mkdir -p "$TREE/docs/design/phases/2/specs" "$TREE/internal/order" "$TREE/web/src" "$TREE/tests"
awk '/BEGIN example-inventory/{f=1;next}/END example-inventory/{f=0}f' "$TRC" > "$TREE/docs/design/phases/2/specs/orders.md"
awk '/BEGIN example-tests-go/{f=1;next}/END example-tests-go/{f=0}f' "$TRC" | grep -v '^```' > "$TREE/internal/order/total_test.go"
awk '/BEGIN example-tests-ts/{f=1;next}/END example-tests-ts/{f=0}f' "$TRC" | grep -v '^```' > "$TREE/web/src/OrderList.test.tsx"
awk '/BEGIN example-tests-py/{f=1;next}/END example-tests-py/{f=0}f' "$TRC" | grep -v '^```' > "$TREE/tests/test_orders.py"
if python3 "$H/tc-inventory.py" --phase 2 --root "$TREE" --spec-only --out "$TMP/prio.json" >/dev/null 2>&1; then
  n="$(jq 'length' "$TMP/prio.json")"; rows="$(grep -cE '^\| TC-' "$TREE/docs/design/phases/2/specs/orders.md")"
  [ "$n" = "$rows" ] && [ "$n" -gt 0 ] && ok "example inventory: all $n rows parse" || bad "example inventory: parsed $n of $rows rows"
  [ "$(jq -r '.["TC-UI-20107"]' "$TMP/prio.json")" = LOW ] && [ "$(jq -r '.["TC-REL-20101"]' "$TMP/prio.json")" = MEDIUM ] \
    && [ "$(jq -r '.["TC-SEC-20101"]' "$TMP/prio.json")" = HIGH ] && ok "example inventory: priorities read from the Priority column" \
    || bad "example inventory: priorities not parsed as written"
else bad "tc-inventory.py --spec-only failed on the example inventory"; fi
python3 "$H/tc-inventory.py" --phase 2 --root "$TREE" --out "$TMP/src.json" >/dev/null 2>&1
for id in TC-UNIT-20101 TC-UNIT-20102 TC-UI-20107 TC-SEC-20102 TC-API-20102 TC-SEC-20101; do
  v="$(jq -r --arg i "$id" '.cases[] | select(.name == $i) | .verdict' "$TMP/src.json" 2>/dev/null)"
  [ "$v" = PASS ] && ok "example test names cover $id (Go/TS/pytest naming guidance works)" || bad "example test for $id not found by name (got '$v')"
done
jq -e '.tier == "tc-inventory" and .schema == "sdlc.test-results/v1"' "$TMP/src.json" >/dev/null 2>&1 \
  && ok "tc-inventory output is an sdlc.test-results/v1 sidecar" || bad "tc-inventory output is not a sidecar"
# The EARS table in spec_writer must not create a second, priority-less row (first occurrence wins).
mkdir -p "$TMP/p3/docs/design/phases/3/specs"
{ printf '| Req ID | EARS clause | Inventory row |\n|---|---|---|\n| FR-1 | WHEN x THE SYSTEM SHALL y | → TC-API-30101 |\n\n'
  printf '| TC ID | Category | Description | Priority | Tier |\n|---|---|---|---|---|\n| TC-API-30101 | API | y | LOW | integration |\n'; } > "$TMP/p3/docs/design/phases/3/specs/x.md"
python3 "$H/tc-inventory.py" --phase 3 --root "$TMP/p3" --spec-only --out "$TMP/p3.json" >/dev/null 2>&1
[ "$(jq -r '.["TC-API-30101"]' "$TMP/p3.json")" = LOW ] && ok "spec_writer's arrow-prefixed EARS references don't shadow the inventory row" \
  || bad "an EARS-table reference shadowed the inventory row's priority"
grep -q '| TC ID | Category | Description | Priority | Tier |' "$A/core/spec_writer.md" && ok "spec_writer's inventory header matches the parsed columns" || bad "spec_writer inventory header drifted"
grep -q 'P·10000 + k·100 + i' "$A/core/spec_writer.md" && ok "spec_writer allocates project-unique IDs (TEST-02 cross-phase reuse)" || bad "spec_writer lacks project-unique ID allocation"

echo "── changing an existing test: a TEST-CHANGE comment says why and when (decision 2026-09-30) ──"
for a in unit_test_agent integration_test_agent ui_test_agent mobile_test_agent e2e_orchestrator acceptance_test_agent \
         backend_developer api_developer ui_developer mobile_developer; do
  f="$(file_of "$a")"
  if grep -q 'TEST-CHANGE <YYYY-MM-DD> phase <N>:' "$f" && grep -q 'spec:' "$f"; then ok "$a documents the TEST-CHANGE comment"
  else bad "$a does not tell the agent to write a TEST-CHANGE comment (why and when)"; fi
  if grep -nE 'genuine (test )?refactor.*test-changes\.json|in `test-changes\.json` if an assertion line changed' "$f" >/dev/null; then
    bad "$a still acknowledges in-file test changes in test-changes.json (the comment belongs in the test)"
  else ok "$a: in-file changes are not acknowledged in test-changes.json"; fi
done
grep -q '§Changing an existing test\|### Changing an existing test' "$S/test-case-traceability.md" && ok "test-case-traceability.md defines the rule" \
  || bad "test-case-traceability.md lacks the Changing an existing test section"
grep -q 'test_changes' "$A/core/spec_test_reconciler.md" && ok "spec_test_reconciler reports the why-and-when ledger" || bad "spec_test_reconciler ignores test_changes[]"

echo "────────────────────────────────────────────"
echo "testing-agents.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
