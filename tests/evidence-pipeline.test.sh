#!/usr/bin/env bash
# evidence-pipeline.test.sh — the board-review evidence chain end to end on a simulated phase, with the
# REAL tools: runner JUnit → junit-to-sidecar.py → tc-inventory.py → execution.jsonl/roster → verify-gate.sh.
# Proves the file names and fields line up across tools (unit tests of each tool can't), and that the
# gate reacts to the situations Wave 5v exists for: a fix committed after testing makes evidence stale;
# re-running restores it; a failing or skipped HIGH test blocks. Run: bash tests/evidence-pipeline.test.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$REPO/.claude/hooks"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
W="$(mktemp -d)"; L="$(mktemp -d)"; trap 'rm -rf "$W" "$L"' EXIT   # logs OUTSIDE the project (an untracked file there is uncommitted code)
cd "$W" && git init -q && git config user.email t@t && git config user.name t
P=agent_state/phases/1; R=$P/reports; C=agent_state/reconciliation/phase-1
mkdir -p docs/design/phases/1/specs src "$P/junit" "$R" "$C"

# ── a phase: spec inventory, code, tests (IDs in test NAMES) ────────────────────────────────────────
printf '| TC ID | Category | Description | Priority | Tier |\n|---|---|---|---|---|\n| TC-API-001 | API | create order | HIGH | integration |\n| TC-API-002 | API | reject bad order | MEDIUM | unit |\n| TC-ACC-001 | Acceptance | buyer checks out | HIGH | acceptance |\n' > docs/design/phases/1/specs/orders.md
printf 'package src\nfunc Create() int { return 1 }\n' > src/orders.go
printf 'package src\nimport "testing"\nfunc TestOrders(t *testing.T) {\n  t.Run("TC-API-001 create order", func(t *testing.T) {})\n  t.Run("TC-API-002 reject bad order", func(t *testing.T) {})\n}\n' > src/orders_test.go
mkdir -p tests/acceptance && printf "test('TC-ACC-001 buyer checks out', async () => {})\n" > tests/acceptance/checkout.spec.ts
git add -A && git commit -qm "phase 1 code + tests"
git rev-parse HEAD > "$P/base_sha"

junit() {  # junit <file> <verdict-for-TC-API-002: pass|fail|skip>
  local extra=""
  case "$2" in fail) extra='<failure message="boom"/>' ;; skip) extra='<skipped/>' ;; esac
  printf '<testsuite><testcase classname="src" name="TestOrders/TC-API-001 create order"/><testcase classname="src" name="TestOrders/TC-API-002 reject bad order">%s</testcase></testsuite>\n' "$extra" > "$1"
}
evidence() {  # evidence <TC-API-002 outcome> — what Wave 3 + 3v + Track B/C produce
  python3 "$H/tc-inventory.py" --phase 1 --spec-only --out "$P/tc_priorities.json" >/dev/null
  junit "$P/junit/unit.xml" "$1"
  python3 "$H/junit-to-sidecar.py" --tier unit --command "gotestsum ./..." --exit-code 0 --priorities "$P/tc_priorities.json" --out "$R/unit_tests.json" "$P/junit/unit.xml" >/dev/null
  python3 "$H/junit-to-sidecar.py" --tier all --command "test_runner" --exit-code 0 --priorities "$P/tc_priorities.json" --out "$R/test_results.json" "$P/junit/unit.xml" >/dev/null
  printf '<testsuite><testcase name="TC-ACC-001 buyer checks out"/></testsuite>\n' > "$P/junit/acc.xml"
  python3 "$H/junit-to-sidecar.py" --tier acceptance --command "playwright tests/acceptance" --exit-code 0 --priorities "$P/tc_priorities.json" --out "$R/acceptance_report.json" "$P/junit/acc.xml" >/dev/null
  python3 - "$R/test_results.json" "$R/acceptance_report.json" <<'PY'   # test_runner's all-tier results include acceptance
import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
a["cases"] += b["cases"]; a["total"] += b["total"]; a["passed"] += b["passed"]; json.dump(a, open(sys.argv[1], "w"))
PY
  python3 "$H/tc-inventory.py" --phase 1 --results "$R/test_results.json" --diff-base "$(cat "$P/base_sha")" --out "$C/specs_vs_tests.json" >/dev/null
  for f in unit_tests test_results acceptance_report; do echo "see $f.json" > "$R/$f.md"; done
  printf 'TC inventory — see specs_vs_tests.json\nBLOCKING:0 WARNING:0 INFO:0\n' > "$C/specs_vs_tests.md"
}
AGENTS="backend_developer code_reviewer_I code_reviewer_II security_reviewer code_quality_verifier unit_test_agent test_runner spec_test_reconciler acceptance_test_agent"
printf '{"phase":1,"required":[%s]}\n' "$(for a in $AGENTS; do printf '"%s",' "$a"; done | sed 's/,$//')" > "$P/roster.json"
log_all() {
  : > "$P/execution.jsonl"
  for a in $AGENTS; do
    case "$a" in
      backend_developer) r=null ;;
      unit_test_agent) r="\"$R/unit_tests.md\"" ;;
      test_runner) r="\"$R/test_results.md\"" ;;
      acceptance_test_agent) r="\"$R/acceptance_report.md\"" ;;
      spec_test_reconciler) r="\"$C/specs_vs_tests.md\"" ;;
      *) printf 'review\nBLOCKING:0 WARNING:0 INFO:0\n' > "$R/$a.md"; r="\"$R/$a.md\"" ;;
    esac
    echo "{\"agent\":\"$a\",\"phase\":1,\"status\":\"completed\",\"report\":$r,\"ts\":\"t\"}" >> "$P/execution.jsonl"
  done
}
gate() { CLAUDE_PROJECT_DIR="$W" bash "$H/verify-gate.sh" 1 >"$L/gate.log" 2>&1; }

echo "== happy path"
evidence pass; log_all
gate && ok "green phase with runner-written evidence PASSes the gate" || { bad "green phase blocked"; tail -15 "$L/gate.log"; }
jq -e '.verdict == "PASS" and .passed == 3 and .total == 3' "$C/specs_vs_tests.json" >/dev/null \
  && ok "tc-inventory (results mode): 3/3 HIGH+MEDIUM covered by tests that ran and passed" || bad "inventory not 3/3: $(jq -c '{verdict,passed,total,missing,failing}' "$C/specs_vs_tests.json")"

echo "== a fix committed after testing (why Wave 5v exists)"
printf 'package src\nfunc Create() int { return 2 }\n' > src/orders.go && git commit -qam "fix after review"
gate; rc=$?
[ "$rc" = 2 ] && grep -q "STALE" "$L/gate.log" && ok "evidence from before the fix BLOCKs as STALE" || bad "stale evidence not blocked (rc=$rc)"
evidence pass
gate && ok "re-running the tiers at the new commit (Wave 5v) PASSes again" || { bad "fresh evidence still blocked"; tail -8 "$L/gate.log"; }

echo "== failures the old gate let through"
evidence fail
gate; rc=$?
[ "$rc" = 2 ] && grep -q "failed=1" "$L/gate.log" && ok "one failing unit test BLOCKs (unit and runner sidecars)" || bad "failing test not blocked (rc=$rc)"
grep -q "TC-API-002=FAIL" "$L/gate.log" && ok "the failing MEDIUM TC case is named in the gate output" || bad "failing TC case not named"
evidence skip
gate; rc=$?
[ "$rc" = 2 ] && jq -e '.missing | index("TC-API-002")' "$C/specs_vs_tests.json" >/dev/null && ok "a skipped MEDIUM test leaves its TC ID missing and BLOCKs" || bad "skipped test counted as coverage (rc=$rc)"
evidence pass
printf 'package src\nimport "testing"\nfunc TestOrders(t *testing.T) {\n  t.Skip("later")\n  t.Run("TC-API-001 create order", func(t *testing.T) {})\n  t.Run("TC-API-002 reject bad order", func(t *testing.T) {})\n}\n' > src/orders_test.go
git commit -qam "skip the suite"
evidence pass
gate; rc=$?
[ "$rc" = 2 ] && jq -e '.weakening_unacknowledged | length > 0' "$C/specs_vs_tests.json" >/dev/null && ok "a new t.Skip since the phase base is test weakening and BLOCKs" || bad "test weakening not caught (rc=$rc)"

echo "────────────────────────────────────────────"
echo "evidence-pipeline.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
