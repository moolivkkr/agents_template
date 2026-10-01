#!/usr/bin/env bash
# verify-gate.test.sh — committed regression test for the framework's linchpin enforcement hook.
#
# This is the CODE form of eval task T-004 (agent_state/eval/suite/T-004-gate-blocks-missing-review):
# it proves the phase gate is real deterministic CODE, not prose a model is trusted to follow. If a
# change ever weakens .claude/hooks/verify-gate.sh (or someone un-wires it), one of these assertions
# flips and the regression is caught BY NAME — no manual /eval run required.
#
# Run: bash tests/verify-gate.test.sh   (exit 0 = all pass, non-zero = a guarantee regressed)
# Wire into CI / a pre-commit hook so weakening the gate fails the build.
#
# Dependencies: bash, jq (same as the hook). No bats, no network.

set -uo pipefail

# Locate the hook relative to this test file, so it runs from any cwd.
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TEST_DIR/.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/verify-gate.sh"

PASS=0; FAIL=0
FIXROOT="$(mktemp -d)"
trap 'rm -rf "$FIXROOT"' EXIT

# assert_exit <expected_code> <test-name> -- <hook args...>   (fixture cwd = $CWD env)
run_hook() { CLAUDE_PROJECT_DIR="$1" bash "$HOOK" "${@:2}" 2>&1; }

check() {  # check <name> <expected_exit> <actual_exit> [must-contain]
  local name="$1" want="$2" got="$3" needle="${4:-}"
  if [ "$got" != "$want" ]; then
    echo "  ✗ FAIL: $name — expected exit $want, got $got"; FAIL=$((FAIL+1)); return
  fi
  if [ -n "$needle" ] && ! printf '%s' "$LAST_OUT" | grep -qF "$needle"; then
    echo "  ✗ FAIL: $name — output missing expected text: '$needle'"; FAIL=$((FAIL+1)); return
  fi
  echo "  ✓ $name"; PASS=$((PASS+1))
}

# Build a phase fixture dir and return its project-root path. Args: name, then it's caller-populated.
new_phase() {
  local d="$FIXROOT/$1"; mkdir -p "$d/agent_state/phases/1/reports"; ( cd "$d" && git init -q 2>/dev/null ); echo "$d"
}


# Board review 2026-09-30: evidence helpers. sidecar <file> <verdict> <total> <failed> [extra-json-fields]
sidecar() { printf '{"schema":"sdlc.test-results/v1","tier":"t","verdict":"%s","total":%s,"passed":%s,"failed":%s,"flaky":0%s}\n' "$2" "$3" "$(( $3 - $4 ))" "$4" "${5:-}" > "$1"; }
code_sha() { git -C "$1" log -1 --format=%H -- . ':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays'; }
commit_code() {  # commit_code <fixture> <file> <content>
  mkdir -p "$(dirname "$1/$2")"; printf '%s\n' "$3" > "$1/$2"
  git -C "$1" add "$2" && git -C "$1" -c user.email=t@t -c user.name=t commit -qm "code $2"
}
# A complete implementation phase: implementer, review floor, verification floor, fresh sidecars.
full_phase() {  # full_phase <fixture> [extra roster agents...]
  local d="$1" p="$1/agent_state/phases/1" sha; shift
  commit_code "$d" src/app.go "package app"
  sha="$(code_sha "$d")"
  local agents=(backend_developer code_reviewer_I code_reviewer_II security_reviewer code_quality_verifier test_runner spec_test_reconciler acceptance_test_agent "$@")
  printf '{"phase":1,"required":[%s]}\n' "$(printf '"%s",' "${agents[@]}" | sed 's/,$//')" > "$p/roster.json"
  : > "$p/execution.jsonl"
  for a in "${agents[@]}"; do
    case "$a" in
      backend_developer) echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":null,\"ts\":\"t\"}" >> "$p/execution.jsonl" ;;
      test_runner|spec_test_reconciler|acceptance_test_agent|deploy_dev|deploy_qa|unit_test_agent|e2e_orchestrator)
        echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":\"reports/$a.md\",\"ts\":\"t\"}" >> "$p/execution.jsonl"
        echo "results for $a" > "$p/reports/$a.md"
        sidecar "$p/reports/$a.json" PASS 10 0 ",\"code_sha\":\"$sha\",\"dirty\":false" ;;
      *) echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":\"reports/$a.md\",\"ts\":\"t\"}" >> "$p/execution.jsonl"
         printf 'Review for %s\nBLOCKING:0 WARNING:0 INFO:0\n' "$a" > "$p/reports/$a.md" ;;
    esac
  done
  echo '{"gate":{"passed":true}}' > "$p/manifest.json"
}
# --- 1. Clean, complete gate (implementer + review floor + verification floor, fresh evidence) → PASS ---
D=$(new_phase clean); full_phase "$D"
LAST_OUT="$(run_hook "$D" 1)"; check "clean complete gate PASSes" 0 "$?"

# --- 2. Missing required agent (security_reviewer never completed) → BLOCK naming it (T-004 core) ---
D=$(new_phase missing_review)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","security_reviewer","code_quality_verifier"]}
J
for a in backend_developer code_reviewer_I code_reviewer_II code_quality_verifier; do
  echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":null,\"ts\":\"t\"}" >> "$D/agent_state/phases/1/execution.jsonl"
done
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "missing security_reviewer BLOCKs (named)" 2 "$?" "security_reviewer"

# --- 3. Forged gate.passed with NO contract files → BLOCK (gate.passed-without-evidence bug) ---
D=$(new_phase forged)
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "forged gate.passed w/o contract BLOCKs" 2 "$?"

# --- 4. Unresolved BLOCKING finding in a report → BLOCK naming the report ---
D=$(new_phase blocking)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'Findings\nBLOCKING: IDOR in GET /users/:id\n' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "unresolved BLOCKING report BLOCKs (named)" 2 "$?" "security_review.md"

# --- 5. Roster FLOOR: impl agent present but reviewer dropped from roster → BLOCK ---
D=$(new_phase thin_roster)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","code_quality_verifier"]}
J
for a in backend_developer code_reviewer_I code_reviewer_II code_quality_verifier; do
  echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":null,\"ts\":\"t\"}" >> "$D/agent_state/phases/1/execution.jsonl"
done
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "thin roster (drops security_reviewer) BLOCKs on FLOOR" 2 "$?" "FLOOR"

# --- 6. Docs-only phase (no impl agent) → floor not required → PASS ---
D=$(new_phase docs_only)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["documentation_agent"]}
J
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "docs-only phase (no floor) PASSes" 0 "$?"

# --- 7. Valid gate.forced overrides a finding-blocker → FORCED PASS (exit 0) ---
D=$(new_phase forced_ok)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"code_reviewer_I","phase":1,"status":"completed","report":"reports/cr1.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
sed -i.bak 's/security_reviewer/code_reviewer_I/' "$D/agent_state/phases/1/roster.json"
printf 'Findings\nBLOCKING: accepted style risk\n' > "$D/agent_state/phases/1/reports/cr1.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"gate_item":"code_review","details":"x"}],"user_rationale":"accepted, tracked"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "valid gate.forced → FORCED PASS" 0 "$?" "FORCED PASS"

# --- 7b/7c. A security finding needs a per-finding acknowledgement to be forced (SEC-01) ---
D=$(new_phase forced_security)
echo '{"phase":1,"required":["security_reviewer"]}' > "$D/agent_state/phases/1/roster.json"
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'Findings\nBLOCKING: IDOR in GET /orders/:id\n' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"gate_item":"security_review"}],"user_rationale":"ship it"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "blanket gate.forced cannot override a security finding" 2 "$?" "security finding"
echo '{"phase":1,"blockers":[{"gate_item":"security_review"}],"user_rationale":"ship it","security_acknowledged":[{"finding":"IDOR in GET /orders/:id","approved_by":"owner","reason":"endpoint disabled by flag until fix"}]}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "security finding forced only with a per-finding acknowledgement" 0 "$?" "FORCED PASS"

# --- 8. gate.forced must NOT override a structurally incomplete roster → still BLOCK ---
D=$(new_phase forced_incomplete)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["backend_developer","code_reviewer_I","code_reviewer_II","security_reviewer","code_quality_verifier"]}
J
echo '{"agent":"backend_developer","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"x":1}],"user_rationale":"skip everything"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "gate.forced does NOT bypass incomplete roster" 2 "$?"

# --- 9. Empty gate.forced must not disarm the gate → BLOCK ---
D=$(new_phase forced_empty)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/s.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'BLOCKING: x\n' > "$D/agent_state/phases/1/reports/s.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "empty gate.forced does NOT disarm gate" 2 "$?"

# --- 10. JSON sidecar with unresolved BLOCKING finding → BLOCK (jq path, not grep) ---
D=$(new_phase sidecar_blocking)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["security_reviewer"]}
J
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo 'clean-looking prose report with no BLOCKING word at all' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"agent":"security_reviewer","blocking":1,"findings":[{"id":"S1","severity":"BLOCKING","resolved":false,"ref":"h.go:12"}]}' > "$D/agent_state/phases/1/reports/security_review.json"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "JSON sidecar unresolved BLOCKING BLOCKs (jq)" 2 "$?" "sidecar"

# --- 11. JSON sidecar all resolved + tests pass → PASS ---
D=$(new_phase sidecar_ok)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["unit_test_agent"]}
J
echo '{"agent":"unit_test_agent","phase":1,"status":"completed","report":"reports/unit_tests.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo 'unit test report' > "$D/agent_state/phases/1/reports/unit_tests.md"
sidecar "$D/agent_state/phases/1/reports/unit_tests.json" PASS 42 0
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "JSON sidecar clean+tests-pass PASSes" 0 "$?"

# --- 12. JSON sidecar reports failed>0 → BLOCK ---
D=$(new_phase sidecar_failed)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["unit_test_agent"]}
J
echo '{"agent":"unit_test_agent","phase":1,"status":"completed","report":"reports/unit_tests.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo 'unit test report' > "$D/agent_state/phases/1/reports/unit_tests.md"
sidecar "$D/agent_state/phases/1/reports/unit_tests.json" FAIL 42 2
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "JSON sidecar failed>0 BLOCKs" 2 "$?" "failed=2"

# --- 13. Execution-grounded (e): failing test command → BLOCK (explicit phase, config present) ---
D=$(new_phase exec_fail)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["documentation_agent"]}
J
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"test":"exit 1"}' > "$D/sdlc-verify.json"
LAST_OUT="$(run_hook "$D" 1)"; check "exec-grounded failing test BLOCKs" 2 "$?" "test FAILED"

# --- 14. Execution-grounded (e): passing test command → PASS ---
D=$(new_phase exec_pass)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["documentation_agent"]}
J
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"test":"true","lint":"true"}' > "$D/sdlc-verify.json"
LAST_OUT="$(run_hook "$D" 1)"; check "exec-grounded passing test PASSes" 0 "$?"

# --- 15. Execution-grounded honors VERIFY_GATE_SKIP_EXEC=1 (failing cmd skipped) → PASS ---
D=$(new_phase exec_skip)
cat > "$D/agent_state/phases/1/roster.json" <<'J'
{"phase":1,"required":["documentation_agent"]}
J
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"test":"exit 1"}' > "$D/sdlc-verify.json"
LAST_OUT="$(VERIFY_GATE_SKIP_EXEC=1 run_hook "$D" 1)"; check "exec-grounded skip env honored" 0 "$?"

# --- Review 2026-09-30 regressions (B1-B4): clean reports must pass, real findings must block ---
one_agent() {  # one_agent <fixture> <agent> <report-json-value>  → roster + completed line
  local d="$1"; echo "{\"phase\":1,\"required\":[\"$2\"]}" > "$d/agent_state/phases/1/roster.json"
  echo "{\"agent\":\"$2\",\"phase\":1,\"status\":\"completed\",\"report\":$3,\"ts\":\"t\"}" > "$d/agent_state/phases/1/execution.jsonl"
}
# B1: realistic clean reports that the old heuristics blocked
D=$(new_phase clean_prose); one_agent "$D" dependency_scanner '"reports/dependency_scan.md"'
cat > "$D/agent_state/phases/1/reports/dependency_scan.md" <<'R'
# Dependency scan
Severity legend: BLOCKING = must fix before gate; WARNING = should fix.
| Check | Count |
|---|---|
| Copyleft License Issues (BLOCKING) | 0 |
All remaining advisories are non-blocking.
Total: 120 | Passed: 120 | Failed: 0
The API returns meta.total=0 for an empty list.
BLOCKING:0 WARNING:2 INFO:1
R
LAST_OUT="$(run_hook "$D" 1)"; check "clean report with legend/table/prose + count line PASSes" 0 "$?"
D=$(new_phase count_blocks); one_agent "$D" code_reviewer_I '"reports/cr1.md"'
printf 'Review\nnon-blocking notes only in prose\nBLOCKING:2 WARNING:0 INFO:0\n' > "$D/agent_state/phases/1/reports/cr1.md"
LAST_OUT="$(run_hook "$D" 1)"; check "count line BLOCKING:2 BLOCKs even with benign prose" 2 "$?" "BLOCKING:2"
D=$(new_phase table_no_count); one_agent "$D" dependency_scanner '"reports/ds.md"'
printf '| Copyleft (BLOCKING) | 0 |\nAll findings are non-blocking.\n' > "$D/agent_state/phases/1/reports/ds.md"
LAST_OUT="$(run_hook "$D" 1)"; check "zero-count BLOCKING table row + non-blocking prose PASSes (no count line)" 0 "$?"
D=$(new_phase total_zero); one_agent "$D" unit_test_agent '"reports/unit_tests.md"'
printf '# Unit tests\nTotal: 0 | Passed: 0 | Failed: 0\n' > "$D/agent_state/phases/1/reports/unit_tests.md"
LAST_OUT="$(run_hook "$D" 1)"; check "a markdown-only test report ('Total: 0') BLOCKs — no sidecar" 2 "$?" "sidecar"
# B2: legacy "null" string and directory reports
D=$(new_phase null_string); one_agent "$D" documentation_agent '"null"'
LAST_OUT="$(run_hook "$D" 1)"; check "report \"null\" string treated as no report → PASS" 0 "$?"
D=$(new_phase dir_report); one_agent "$D" e2e_orchestrator '"reports/e2e/"'; mkdir -p "$D/agent_state/phases/1/reports/e2e"
LAST_OUT="$(run_hook "$D" 1)"; check "directory as report BLOCKs with a clear message" 2 "$?" "is a directory"
# B3: diagnostics on stderr (exit-2 hooks show the model stderr only)
D=$(new_phase stderr); one_agent "$D" code_reviewer_I '"reports/missing.md"'
out_stdout="$(CLAUDE_PROJECT_DIR="$D" bash "$HOOK" 1 2>/dev/null)"; rc=$?
if [ "$rc" = "2" ] && [ -z "$out_stdout" ]; then echo "  ✓ blocking diagnostics go to stderr, not stdout"; PASS=$((PASS+1)); else echo "  ✗ FAIL: expected exit 2 with empty stdout (got $rc, stdout=${#out_stdout} bytes)"; FAIL=$((FAIL+1)); fi
# B4: passive Stop sweep (no phase arg) triggers on the gate.passed FILE, not only manifest .gate.passed
D=$(new_phase sweep_file); touch "$D/agent_state/phases/1/gate.passed"
LAST_OUT="$(run_hook "$D")"; check "Stop sweep verifies a claimed gate.passed file (no contract → BLOCK)" 2 "$?"
D=$(new_phase sweep_quiet)
LAST_OUT="$(run_hook "$D")"; check "Stop sweep stays silent when nothing is claimed" 0 "$?"


# --- Board review 2026-09-30: the gate must see test failures and stale evidence ---
# TEST-01 reproduction: markdown-only e2e/acceptance reports saying FAIL / BLOCKED used to PASS.
D=$(new_phase md_fail); one_agent "$D" e2e_orchestrator '"reports/e2e_results.md"'
printf '# E2E\n| Workflow | Result |\n|---|---|\n| checkout | FAIL |\n' > "$D/agent_state/phases/1/reports/e2e_results.md"
LAST_OUT="$(run_hook "$D" 1)"; check "markdown-only e2e report with FAIL BLOCKs (no sidecar)" 2 "$?" "sidecar"
D=$(new_phase md_blocked); one_agent "$D" acceptance_test_agent '"reports/acceptance_report.md"'
printf '# Acceptance\nVerdict: BLOCKED / UNTESTED\n' > "$D/agent_state/phases/1/reports/acceptance_report.md"
LAST_OUT="$(run_hook "$D" 1)"; check "markdown-only acceptance BLOCKED/UNTESTED BLOCKs" 2 "$?" "sidecar"
# per-case verdicts: a HIGH case UNTESTED blocks even when failed=0
D=$(new_phase case_untested); one_agent "$D" acceptance_test_agent '"reports/acceptance.md"'; echo x > "$D/agent_state/phases/1/reports/acceptance.md"
sidecar "$D/agent_state/phases/1/reports/acceptance.json" PASS 8 0 ',"cases":[{"name":"UC-3 admin exports","priority":"HIGH","verdict":"UNTESTED"}]'
LAST_OUT="$(run_hook "$D" 1)"; check "HIGH acceptance case UNTESTED BLOCKs" 2 "$?" "UC-3 admin exports=UNTESTED"
D=$(new_phase flaky); one_agent "$D" e2e_orchestrator '"reports/e2e.md"'; echo x > "$D/agent_state/phases/1/reports/e2e.md"
printf '{"schema":"sdlc.test-results/v1","verdict":"PASS","total":5,"passed":5,"failed":0,"flaky":1}\n' > "$D/agent_state/phases/1/reports/e2e.json"
LAST_OUT="$(run_hook "$D" 1)"; check "flaky>0 BLOCKs (pass on retry is a failure)" 2 "$?" "flaky=1"
D=$(new_phase quarantine); one_agent "$D" unit_test_agent '"reports/unit.md"'; echo x > "$D/agent_state/phases/1/reports/unit.md"
sidecar "$D/agent_state/phases/1/reports/unit.json" PASS 5 0 ',"quarantined":[{"name":"TestX","issue":"#9","expires":"2000-01-01"}]'
LAST_OUT="$(run_hook "$D" 1)"; check "expired quarantine BLOCKs" 2 "$?" "quarantined"
D=$(new_phase verdict_error); one_agent "$D" unit_test_agent '"reports/unit.md"'; echo x > "$D/agent_state/phases/1/reports/unit.md"
sidecar "$D/agent_state/phases/1/reports/unit.json" ERROR 5 0
LAST_OUT="$(run_hook "$D" 1)"; check "verdict ERROR (runner crashed) BLOCKs" 2 "$?" "verdict is ERROR"
D=$(new_phase null_report_test); one_agent "$D" unit_test_agent 'null'
LAST_OUT="$(run_hook "$D" 1)"; check "test agent completed with no report BLOCKs" 2 "$?" "without logging a report"
# floor: verification agents are mandatory for implementation phases, and can't be forced past
D=$(new_phase floor_verify); full_phase "$D"
sed -i.bak 's/"test_runner",//' "$D/agent_state/phases/1/roster.json"
echo '{"phase":1,"blockers":[{"x":1}],"user_rationale":"skip tests"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "implementation phase without test_runner BLOCKs on FLOOR (not forceable)" 2 "$?" "'test_runner'"
D=$(new_phase floor_acc_na); full_phase "$D"
sed -i.bak 's/,"acceptance_test_agent"//' "$D/agent_state/phases/1/roster.json"
echo '{"gate":{"passed":true},"acceptance":{"not_applicable":true,"reason":"internal refactor phase with no FR in scope"}}' > "$D/agent_state/phases/1/manifest.json"
LAST_OUT="$(run_hook "$D" 1)"; check "acceptance may be dropped only with a recorded reason" 0 "$?" "acceptance not applicable"
D=$(new_phase floor_k8s); full_phase "$D"; mkdir -p "$D/deploy/k8s"; echo "APP=x" > "$D/deploy/k8s/app.env"
git -C "$D" add deploy && git -C "$D" -c user.email=t@t -c user.name=t commit -qm k8s
LAST_OUT="$(run_hook "$D" 1)"; check "k8s project without deploy_dev/deploy_qa BLOCKs on FLOOR" 2 "$?" "'deploy_qa'"
D=$(new_phase k8s_ok); mkdir -p "$D/deploy/k8s"; echo "APP=x" > "$D/deploy/k8s/app.env"
git -C "$D" add deploy && git -C "$D" -c user.email=t@t -c user.name=t commit -qm k8s; full_phase "$D" deploy_dev deploy_qa
LAST_OUT="$(run_hook "$D" 1)"; check "k8s project with fresh deploy_dev/deploy_qa evidence PASSes" 0 "$?"
# freshness: evidence must describe the committed code being gated
D=$(new_phase stale); full_phase "$D"; commit_code "$D" src/fix.go "package app // fix after tests"
LAST_OUT="$(run_hook "$D" 1)"; check "evidence from before the last code commit BLOCKs as STALE" 2 "$?" "STALE"
D=$(new_phase dirty); full_phase "$D"; echo "// wip" >> "$D/src/app.go"
LAST_OUT="$(run_hook "$D" 1)"; check "uncommitted code at gate time BLOCKs" 2 "$?" "uncommitted code"
D=$(new_phase docs_after); full_phase "$D"; mkdir -p "$D/docs"; echo notes > "$D/docs/n.md"
git -C "$D" add docs && git -C "$D" -c user.email=t@t -c user.name=t commit -qm docs
LAST_OUT="$(run_hook "$D" 1)"; check "a docs-only commit after testing does not make evidence stale" 0 "$?"

# SEC-01 follow-up: a security report with BLOCKING:3 needs 3 acknowledgements, not 1
D=$(new_phase forced_security_count)
echo '{"phase":1,"required":["security_reviewer"]}' > "$D/agent_state/phases/1/roster.json"
echo '{"agent":"security_reviewer","phase":1,"status":"completed","report":"reports/security_review.md","ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
printf 'Findings\nBLOCKING:3 WARNING:0 INFO:0\n' > "$D/agent_state/phases/1/reports/security_review.md"
echo '{"gate":{"passed":true}}' > "$D/agent_state/phases/1/manifest.json"
echo '{"phase":1,"blockers":[{"x":1}],"user_rationale":"r","security_acknowledged":[{"finding":"IDOR","approved_by":"owner","reason":"flagged off"}]}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "one acknowledgement cannot force a BLOCKING:3 security report" 2 "$?" "3 security finding"

# (f) no pending debate (review 2026-09-30, D1/D2): the gate reads debates through debate-status.py
debate_req() {  # debate_req <fixture> <topic> <phase|null> [extra-json-fields]
  mkdir -p "$1/agent_state/debates"
  printf '{"schema":"sdlc.debate-request/v1","type":"debate_request","topic":"%s","phase":%s,"from_agent":"backend_developer","decision":"pick one","options":[{"id":"A","label":"a"},{"id":"B","label":"b"}],"impact":"HIGH","domain":"architecture","blocking":true%s}\n' "$2" "$3" "${4:-}" > "$1/agent_state/debates/$2.request.json"
}
debate_verdict() {  # debate_verdict <fixture> <topic> <option> [promote:yes|no]
  printf '{"schema":"sdlc.debate-verdict/v1","topic":"%s","phase":1,"status":"RESOLVED","verdict":"%s","verdict_label":"x","confidence":"HIGH","scores":{"A":{"total":7},"B":{"total":5}},"rationale":"r","decisive_factor":"brd","decision_id":"D-001"}\n' "$2" "$3" > "$1/agent_state/debates/$2.verdict.json"
  if [ "${4:-yes}" = yes ]; then mkdir -p "$1/docs"; printf '# Decisions\n\n### D-001 — %s\n- link: agent_state/debates/%s.verdict.json\n' "$2" "$2" > "$1/docs/DECISIONS.md"; fi
}
D=$(new_phase debate_pending); full_phase "$D"; debate_req "$D" cache_strategy 1
LAST_OUT="$(run_hook "$D" 1)"; check "pending blocking debate BLOCKs the gate (named)" 2 "$?" "debate 'cache_strategy' is pending"
D=$(new_phase debate_resolved); full_phase "$D"; debate_req "$D" cache_strategy 1; debate_verdict "$D" cache_strategy A
LAST_OUT="$(run_hook "$D" 1)"; check "debate with a promoted verdict PASSes" 0 "$?"
D=$(new_phase debate_unpromoted); full_phase "$D"; debate_req "$D" cache_strategy 1; debate_verdict "$D" cache_strategy A no
LAST_OUT="$(run_hook "$D" 1)"; check "verdict never promoted to DECISIONS.md BLOCKs" 2 "$?" "never promoted"
D=$(new_phase debate_bad_option); full_phase "$D"; debate_req "$D" cache_strategy 1; debate_verdict "$D" cache_strategy C
LAST_OUT="$(run_hook "$D" 1)"; check "verdict for an option the request never offered BLOCKs" 2 "$?" "not one of the requested options"
D=$(new_phase debate_other_phase); full_phase "$D"; debate_req "$D" later_choice 2
LAST_OUT="$(run_hook "$D" 1)"; check "another phase's pending debate does not block this gate" 0 "$?"
D=$(new_phase debate_no_phase); full_phase "$D"; debate_req "$D" orphan_choice null
LAST_OUT="$(run_hook "$D" 1)"; check "pending debate with no phase field still BLOCKs" 2 "$?" "orphan_choice"
D=$(new_phase debate_auto); full_phase "$D"; debate_req "$D" log_format 1
echo '{"phase":1,"decisions":[{"topic":"log_format","auto_resolved_with":"A","confidence":"LOW","reason":"escalation_limit_exceeded","needs_review":true}]}' > "$D/agent_state/debates/unresolved.json"
LAST_OUT="$(run_hook "$D" 1)"; check "debate auto-resolved in unresolved.json PASSes (flagged for review)" 0 "$?" "auto-resolved with a default"
D=$(new_phase debate_nonblocking); full_phase "$D"; debate_req "$D" nice_to_have 1 ',"blocking":false'
LAST_OUT="$(run_hook "$D" 1)"; check "non-blocking pending debate does not block" 0 "$?"
D=$(new_phase debate_legacy); full_phase "$D"; mkdir -p "$D/agent_state/debates"
echo '{"type":"debate_request","from_step":"step2","decision":"db","options":[{"id":"A"},{"id":"B"}],"impact":"HIGH","blocking":true}' > "$D/agent_state/debates/step2-database_choice.json"
LAST_OUT="$(run_hook "$D" 1)"; check "legacy <step>-<topic>.json request with no verdict BLOCKs (was invisible)" 2 "$?" "step2-database_choice"
echo '{"topic":"database_choice","verdict":"A","confidence":"HIGH"}' > "$D/agent_state/debates/database_choice-verdict.json"
LAST_OUT="$(run_hook "$D" 1)"; check "legacy request matched to its legacy <topic>-verdict.json PASSes" 0 "$?"
D=$(new_phase debate_forced); full_phase "$D"; debate_req "$D" cache_strategy 1
echo '{"phase":1,"blockers":[{"debate":"cache_strategy"}],"user_rationale":"owner decides next sprint"}' > "$D/agent_state/phases/1/gate.forced"
LAST_OUT="$(run_hook "$D" 1)"; check "a pending debate is a finding gate.forced can override" 0 "$?" "FORCED PASS"

echo "────────────────────────────────────────────"
echo "verify-gate.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
