#!/usr/bin/env bash
# verify-gate.sh — the REAL, deterministic phase gate. This is the linchpin that turns the
# framework's "prose an LLM is asked to obey" into an assertion the harness actually runs.
#
# It enforces the SHARED EXECUTION-GUARANTEE CONTRACT:
#   roster.json     : {"phase": N, "required": ["<real-agent-name>", ...]}
#   execution.jsonl : append-only, one JSON object per line:
#                     {"agent":"<name>","phase":N,"status":"started|completed|failed",
#                      "report":"<relative-path-or-null>","ts":"<iso8601>"}
#
# It BLOCKS (exit non-zero) unless ALL of these hold for the phase under test:
#   (a)  roster completeness — every name in roster.required has a status:"completed" line.
#   (a2) roster FLOOR        — deterministic, NOT model-authored: if the phase ran any implementation
#                             agent, roster.required MUST also carry the review floor (code_reviewer_I/II,
#                             security_reviewer, code_quality_verifier) AND the verification floor
#                             (test_runner, spec_test_reconciler, acceptance_test_agent unless the manifest
#                             records acceptance.not_applicable with a reason; deploy_dev + deploy_qa on
#                             projects with deploy/k8s/app.env).
#   (b)  report integrity    — every completed line with a non-null "report" points to a file that
#                             EXISTS. TEST agents (unit/integration/ui/mobile/e2e/acceptance/performance,
#                             test_runner, spec_test_reconciler, deploy_dev/qa) must have an
#                             sdlc.test-results/v1 sidecar: verdict PASS, total>0, failed=0, flaky=0, no
#                             HIGH/MEDIUM case FAIL/BLOCKED/UNTESTED, no expired quarantine, and — on an
#                             explicit gate — code_sha == the current code commit and not dirty
#                             (skills/testing/test-results-sidecar.md). Reviewers: their count line or a
#                             sidecar; prose fallback rejects an unresolved "BLOCKING".
#   (e)  execution-grounded  — OPT-IN: if a verify-commands config exists, the hook RUNS the project's
#                             test/lint/typecheck and blocks on non-zero (real execution, not self-
#                             report). Only on an explicit-phase gate; advisory-skip when unconfigured.
#   (c)  no dangling failure — no "failed" status without a LATER "completed" for the same agent.
#   (f)  no pending debate   — every blocking debate request for the phase has a valid verdict that
#                             reached docs/DECISIONS.md, or is auto-resolved/withdrawn (debate-status.py).
#   (d)  gate.passed honesty — if manifest.json has gate.passed==true, (a)-(c) must STILL hold
#                             (this catches the known "gate.passed written without reports" bug).
#
# FORCED OVERRIDE: a well-formed gate.forced ({blockers:[...non-empty], user_rationale:"..."}) turns
#   the FINDING failures (b/c/d) into a loud WARNING and exits 0 (the --force_gate escape hatch). It
#   does NOT override a structurally incomplete/thin roster (a/a2) — you cannot "force" past agents
#   that never ran — and it overrides security findings only with one security_acknowledged[] entry
#   per finding.
#
# Missing roster.json or execution.jsonl => BLOCK with an explanatory message (never silently pass).
#
# Invocation:
#   verify-gate.sh [PHASE]         # explicit phase number
#   verify-gate.sh                 # auto-detect latest agent_state/phases/<N> dir
# As a Stop hook, Claude Code passes no args, so auto-detection is the normal path.
#
# Exit codes: 0 = PASS (gate may proceed), 2 = BLOCK (gate violated), 3 = usage/precondition error.
#
# Dependencies: bash, jq. Robust to being run from any cwd via CLAUDE_PROJECT_DIR / git root.

set -uo pipefail
# All diagnostics go to stderr: when this blocks as a Stop/PostToolUse hook (exit 2) Claude Code
# shows the model stderr only, so stdout output left the model blocked without a reason.
exec 1>&2

# ---------------------------------------------------------------------------
# 0. Locate the project root so this works regardless of the caller's cwd.
#    Claude Code sets CLAUDE_PROJECT_DIR for hooks; fall back to git, then cwd.
# ---------------------------------------------------------------------------
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"   # sibling tools (debate-status.py)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
cd "$PROJECT_DIR" 2>/dev/null || { echo "verify-gate: cannot cd to project dir '$PROJECT_DIR'"; exit 3; }

PHASES_ROOT="agent_state/phases"

# jq is mandatory — without it we cannot parse the contract deterministically.
if ! command -v jq >/dev/null 2>&1; then
  echo "verify-gate: BLOCK — jq is not installed; cannot verify the gate deterministically."
  exit 3
fi

# ---------------------------------------------------------------------------
# 1. Resolve the phase (arg wins; else latest numeric phase dir).
# ---------------------------------------------------------------------------
PHASE="${1:-}"
AUTODETECT="false"
if [ -z "$PHASE" ]; then
  AUTODETECT="true"
  if [ ! -d "$PHASES_ROOT" ]; then
    # No phases at all — nothing to gate. This is not a violation (e.g. pre-/develop repo).
    echo "verify-gate: no $PHASES_ROOT directory yet — nothing to verify (PASS by vacuity)."
    exit 0
  fi
  PHASE="$(ls -1 "$PHASES_ROOT" 2>/dev/null | grep -E '^[0-9]+$' | sort -n | tail -1)"
  if [ -z "$PHASE" ]; then
    echo "verify-gate: no numeric phase dirs under $PHASES_ROOT — nothing to verify (PASS by vacuity)."
    exit 0
  fi
fi

PHASE_DIR="$PHASES_ROOT/$PHASE"
ROSTER="$PHASE_DIR/roster.json"
EXEC="$PHASE_DIR/execution.jsonl"
MANIFEST="$PHASE_DIR/manifest.json"
FORCED="$PHASE_DIR/gate.forced"   # user-approved override (see /develop --force_gate)

# ---------------------------------------------------------------------------
# 1b. Passive Stop-hook sweep (no explicit phase arg): only SPEAK when a gate is
#     actually being CLAIMED. An absent / in-progress / stale phase has nothing to
#     certify yet, so stay completely silent and let the STRICT paths do the
#     blocking: the orchestrator's Wave 6 (verify-gate.sh <N>) and the PostToolUse
#     hook on a manifest.json write both pass an explicit phase. This keeps turn-end
#     quiet in any repo (including the framework repo itself, which never runs a real
#     phase) while STILL catching a forged gate.passed the moment it appears.
if [ "$AUTODETECT" = "true" ]; then
  _claimed="false"
  # A gate is "claimed" by the gate.passed FILE (what /develop-orchestrator Wave 6 writes) or by
  # manifest .gate.passed == true. Keying on the manifest field alone meant the sweep never ran.
  [ -f "$PHASE_DIR/gate.passed" ] && _claimed="true"
  if [ "$_claimed" != "true" ] && [ -f "$MANIFEST" ] && jq -e . "$MANIFEST" >/dev/null 2>&1; then
    _claimed="$(jq -r 'try (.gate.passed) catch false | if . == true then "true" else "false" end' "$MANIFEST" 2>/dev/null || echo false)"
  fi
  [ "$_claimed" != "true" ] && exit 0   # nothing claimed → nothing to verify → silent PASS
fi

echo "════════════════════════════════════════════════════════════════"
echo "verify-gate — Phase $PHASE  ($PHASE_DIR)"
echo "════════════════════════════════════════════════════════════════"

FAILURES=()             # human-readable block reasons
ROSTER_INCOMPLETE="false"   # set true iff a required agent never completed (check a)
fail() { FAILURES+=("$1"); echo "  ✗ $1"; }
ok()   { echo "  ✓ $1"; }

# ---------------------------------------------------------------------------
# 2. Preconditions: roster.json + execution.jsonl must exist and parse.
#    A gate with no evidence contract is a BLOCK, not a silent pass.
# ---------------------------------------------------------------------------
GATE_PASSED_CLAIMED="false"
if [ -f "$MANIFEST" ]; then
  # Tolerate manifests without the field; treat malformed manifest as a violation.
  if jq -e . "$MANIFEST" >/dev/null 2>&1; then
    GATE_PASSED_CLAIMED="$(jq -r 'try (.gate.passed) catch false | if . == true then "true" else "false" end' "$MANIFEST" 2>/dev/null || echo false)"
  else
    fail "manifest.json exists but is not valid JSON: $MANIFEST"
  fi
fi

if [ ! -f "$ROSTER" ]; then
  fail "roster.json missing ($ROSTER) — no execution-guarantee contract; cannot certify the gate."
fi
if [ ! -f "$EXEC" ]; then
  fail "execution.jsonl missing ($EXEC) — no execution evidence; cannot certify the gate."
fi

# If the core contract files are absent, we can't run the substantive checks. Emit the verdict now.
if [ ! -f "$ROSTER" ] || [ ! -f "$EXEC" ]; then
  echo "────────────────────────────────────────────────────────────────"
  if [ "$GATE_PASSED_CLAIMED" = "true" ]; then
    echo "  NOTE: manifest claims gate.passed==true but the contract files are missing."
    echo "        This is exactly the 'gate.passed without evidence' bug — BLOCKING."
  fi
  echo "RESULT: ❌ BLOCK — Phase $PHASE (${#FAILURES[@]} check(s) failed)"
  for f in "${FAILURES[@]}"; do echo "   - $f"; done
  exit 2
fi

# Validate that every execution line is well-formed JSON (a corrupt log can't certify a gate).
BAD_LINES=0
LINE_NO=0
while IFS= read -r line || [ -n "$line" ]; do
  LINE_NO=$((LINE_NO + 1))
  [ -z "$line" ] && continue
  if ! printf '%s' "$line" | jq -e . >/dev/null 2>&1; then
    BAD_LINES=$((BAD_LINES + 1))
    echo "  ! execution.jsonl line $LINE_NO is not valid JSON"
  fi
done < "$EXEC"
if [ "$BAD_LINES" -gt 0 ]; then
  fail "execution.jsonl has $BAD_LINES malformed line(s) — cannot trust the execution record."
fi

# Validate roster.json shape.
if ! jq -e 'has("required") and (.required | type == "array")' "$ROSTER" >/dev/null 2>&1; then
  fail "roster.json malformed — expected {\"phase\":N,\"required\":[...]} with an array 'required'."
fi

# ---------------------------------------------------------------------------
# 3. Check (a): roster completeness.
#    Every required agent must have at least one status:"completed" line.
# ---------------------------------------------------------------------------
echo "── (a) roster completeness ──"
REQUIRED_AGENTS=()
COMPLETED_SET=""
if jq -e 'has("required")' "$ROSTER" >/dev/null 2>&1; then
  while IFS= read -r a; do
    [ -n "$a" ] && REQUIRED_AGENTS+=("$a")
  done < <(jq -r '.required[]?' "$ROSTER" 2>/dev/null)
fi

if [ "${#REQUIRED_AGENTS[@]}" -eq 0 ]; then
  fail "roster.required is empty — a phase with no required agents cannot be certified."
else
  # Set of agents that have a completed line.
  COMPLETED_SET="$(jq -r 'select(.status=="completed") | .agent' "$EXEC" 2>/dev/null | sort -u)"
  MISSING=0
  for agent in "${REQUIRED_AGENTS[@]}"; do
    if printf '%s\n' "$COMPLETED_SET" | grep -qxF "$agent"; then
      ok "required agent completed: $agent"
    else
      fail "required agent NEVER completed: $agent (in roster.required, no status:\"completed\" line)"
      ROSTER_INCOMPLETE="true"
      MISSING=$((MISSING + 1))
    fi
  done
  [ "$MISSING" -eq 0 ] && ok "all ${#REQUIRED_AGENTS[@]} required agents completed"
fi

# ---------------------------------------------------------------------------
# 3b. Check (a2): mandatory roster FLOOR (deterministic, not model-authored).
#     The roster's *contents* are written by the model, so the completeness check above only proves
#     "the model ran what the model listed." This closes the biggest hole: a thin roster that drops
#     reviewers. Rule — if this phase ran ANY implementation agent, it MUST also carry the review
#     floor. Derived purely from roster composition, so no external state is needed and a docs-only
#     / trivial phase (no implementation agent) is unaffected.
# ---------------------------------------------------------------------------
echo "── (a2) mandatory roster floor ──"
in_roster() { printf '%s\n' ${REQUIRED_AGENTS[@]+"${REQUIRED_AGENTS[@]}"} | grep -qxF "$1"; }
IMPL_AGENTS=(backend_developer api_developer ui_developer mobile_developer database_agent migration_agent backend_audit_agent)
REVIEW_FLOOR=(code_reviewer_I code_reviewer_II security_reviewer code_quality_verifier)
# Independent verification (board review 2026-09-30, TEST-04): the only independent test re-run and the
# TC reconciler are no longer optional, and acceptance runs for every implementation phase unless the
# manifest records why it can't apply.
VERIFY_FLOOR=(test_runner spec_test_reconciler)
if [ -f "$MANIFEST" ] && jq -e '.acceptance.not_applicable == true and ((.acceptance.reason // "") | length >= 20)' "$MANIFEST" >/dev/null 2>&1; then
  echo "  ! acceptance not applicable for this phase: $(jq -r '.acceptance.reason' "$MANIFEST")"
else
  VERIFY_FLOOR+=(acceptance_test_agent)
fi
# Projects on the k8s lab cluster: the phase's code must actually have been deployed to dev and promoted
# to qa (scripts/k8s/deploy.sh logs deploy_dev / deploy_qa into execution.jsonl with --phase).
[ -f "deploy/k8s/app.env" ] && VERIFY_FLOOR+=(deploy_dev deploy_qa)
PHASE_HAS_IMPL="false"
for a in "${IMPL_AGENTS[@]}"; do in_roster "$a" && PHASE_HAS_IMPL="true" && break; done
if [ "$PHASE_HAS_IMPL" = "true" ]; then
  FLOOR_MISSING=0
  for a in "${REVIEW_FLOOR[@]}" "${VERIFY_FLOOR[@]}"; do
    if in_roster "$a"; then
      ok "floor agent present in roster: $a"
    else
      fail "roster FLOOR violation — implementation phase omits required agent '$a' from roster.required (a thin roster cannot silently drop review or verification)."
      ROSTER_INCOMPLETE="true"   # a missing floor agent is structural, NOT a forceable finding
      FLOOR_MISSING=$((FLOOR_MISSING + 1))
    fi
  done
  [ "$FLOOR_MISSING" -eq 0 ] && ok "review + verification floor satisfied (implementation phase)"
else
  ok "no implementation agent in roster — review floor not required for this phase"
fi

# Code state the evidence must describe: the last commit touching code, ignoring paths that change with
# every wave. Explicit-phase gates only (the passive Stop sweep doesn't judge freshness).
CODE_EXCL=(':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays')
CUR_CODE_SHA=""; CODE_DIRTY="false"; DIRTY_PATHS=""
if [ "$AUTODETECT" = "false" ] && git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  CUR_CODE_SHA="$(git log -1 --format=%H -- . "${CODE_EXCL[@]}" 2>/dev/null)"
  DIRTY_PATHS="$(git status --porcelain -- . "${CODE_EXCL[@]}" 2>/dev/null | cut -c4- | head -5 | tr '\n' ' ')"
  [ -n "$DIRTY_PATHS" ] && CODE_DIRTY="true"
fi
TEST_AGENTS=(unit_test_agent integration_test_agent ui_test_agent mobile_test_agent e2e_orchestrator mobile_e2e_orchestrator acceptance_test_agent test_runner performance_agent system_test_agent spec_test_reconciler deploy_dev deploy_qa)
SECURITY_AGENTS=(security_reviewer tenant_isolation_verifier dependency_scanner)
is_test_agent() { printf '%s\n' "${TEST_AGENTS[@]}" | grep -qxF "$1"; }
is_security_agent() { printf '%s\n' "${SECURITY_AGENTS[@]}" | grep -qxF "$1"; }
SECURITY_FAILS=0

# ---------------------------------------------------------------------------
# 4. Check (c): no dangling failure.
#    A "failed" for an agent must be followed by a LATER "completed" for the same agent.
#    (Order is line order in the append-only log.)
# ---------------------------------------------------------------------------
echo "── (c) no unresolved failures ──"
# For each agent, take its LAST status in append order (jsonl is chronological). If that final
# status is "failed", the agent never recovered → dangling. A failed line followed by a later
# completed line for the same agent is fine (the retry succeeded).
DANGLING="$(
  jq -r 'select(type=="object") | "\(.agent)\t\(.status)"' "$EXEC" 2>/dev/null \
  | awk -F '\t' '{last[$1]=$2} END{for (a in last) if (last[a]=="failed") print a}' \
  | sort -u
)"
if [ -n "$DANGLING" ]; then
  while IFS= read -r a; do
    [ -n "$a" ] && fail "agent last status is \"failed\" with no later \"completed\": $a"
  done <<< "$DANGLING"
else
  ok "no agent left in a failed state"
fi

# ---------------------------------------------------------------------------
# 5. Check (b): report integrity for every completed line with a non-null report.
#    - file must EXIST
#    - test reports: reject "total: 0" or "SKIPPED"
#    - any report: reject an unresolved "BLOCKING" (a BLOCKING line with no later matching
#      "BLOCKING ... resolved")
# ---------------------------------------------------------------------------
echo "── (b) report integrity ──"
# Emit "agent<TAB>report" for completed lines whose report is a non-null, non-empty string.
# The legacy string "null"/"none" (older completion-line templates quoted ${REPORT_PATH:-null}) is null too.
REPORTS="$(jq -r 'select(.status=="completed") | select(.report != null and .report != "" and ((.report|ascii_downcase) as $r | ($r != "null" and $r != "none"))) | "\(.agent)\t\(.report)"' "$EXEC" 2>/dev/null | sort -u)"

if [ -z "$REPORTS" ]; then
  echo "  (no completed lines carry a report path)"
fi

REPORT_ISSUES=0
check_results_sidecar() {  # $1 agent, $2 sidecar — the sdlc.test-results/v1 rules
  local a="$1" s="$2" bad=0 v t f fl n names q sha d sel
  v="$(jq -r '.verdict // "MISSING"' "$s")"; t="$(jq -r '.total // 0' "$s")"
  f="$(jq -r '.failed // 0' "$s")"; fl="$(jq -r '.flaky // 0' "$s")"
  [ "$v" = "PASS" ] || { fail "'$a' results verdict is $v ($s)"; bad=1; }
  [ "$t" -gt 0 ] 2>/dev/null || { fail "'$a' results report total=$t — nothing ran ($s)"; bad=1; }
  if [ "$f" -gt 0 ] 2>/dev/null; then fail "'$a' results report failed=$f ($s)"; bad=1; fi
  if [ "$fl" -gt 0 ] 2>/dev/null; then fail "'$a' results report flaky=$fl — a pass on retry is a failure: fix it, or quarantine with an issue and an expiry ($s)"; bad=1; fi
  sel='[.cases[]? | select(((.priority // "") | ascii_upcase) as $p | $p == "HIGH" or $p == "MEDIUM") | select(((.verdict // "") | ascii_upcase) as $x | $x == "FAIL" or $x == "BLOCKED" or $x == "UNTESTED" or $x == "FLAKY")]'
  n="$(jq -r "$sel | length" "$s")"
  if [ "${n:-0}" -gt 0 ] 2>/dev/null; then
    names="$(jq -r "$sel | map(\"\\(.name)=\\(.verdict)\") | .[:5] | join(\"; \")" "$s")"
    fail "'$a' has $n HIGH/MEDIUM case(s) not passing: $names ($s)"; bad=1
  fi
  q="$(jq -r --arg today "$(date -u +%Y-%m-%d)" '[.quarantined[]? | select((.issue // "") == "" or (.expires // "") < $today)] | length' "$s")"
  if [ "${q:-0}" -gt 0 ] 2>/dev/null; then fail "'$a' has $q quarantined test(s) past expiry or without an issue link ($s)"; bad=1; fi
  if [ -n "$CUR_CODE_SHA" ]; then
    sha="$(jq -r '.code_sha // ""' "$s")"; d="$(jq -r '.dirty // false' "$s")"
    if [ -z "$sha" ]; then
      fail "'$a' results carry no code_sha — can't tell which code they describe ($s)"; bad=1
    elif [ "${CUR_CODE_SHA#"$sha"}" = "$CUR_CODE_SHA" ] && [ "${sha#"$CUR_CODE_SHA"}" = "$sha" ]; then
      fail "'$a' results are STALE: produced at code ${sha:0:12}, code is now ${CUR_CODE_SHA:0:12} — re-run after the last code change ($s)"; bad=1
    fi
    if [ "$d" = "true" ]; then fail "'$a' results were produced from uncommitted code ($s)"; bad=1; fi
  fi
  [ "$bad" -eq 0 ] && ok "results OK: $s ('$a': $v, $t tests)"
  return "$bad"
}

check_report() {  # $1 agent, $2 report path from execution.jsonl
  local agent="$1" report="$2" candidate sidecar sc_bad ub total failed COUNT_LINE nb UNRESOLVED
  [ -z "$report" ] && return 0
  # Resolve report path: allow it to be relative to project root or to the phase dir.
  candidate="$report"
  if [ ! -f "$candidate" ] && [ -f "$PHASE_DIR/$report" ]; then
    candidate="$PHASE_DIR/$report"
  fi
  if [ -d "$candidate" ] || [ -d "$PHASE_DIR/$report" ]; then
    fail "report referenced by '$agent' is a directory, not a report file: $report (log the results file, e.g. ${report%/}/results.md)"
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi
  if [ ! -f "$candidate" ]; then
    fail "report referenced by '$agent' does not exist: $report"
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi

  # Test agents: only the machine-readable sidecar counts (board review 2026-09-30, TEST-01).
  sidecar="${candidate%.*}.json"
  if is_test_agent "$agent"; then
    if [ ! -f "$sidecar" ] || ! jq -e '.schema == "sdlc.test-results/v1"' "$sidecar" >/dev/null 2>&1; then
      fail "test evidence for '$agent' has no sdlc.test-results/v1 sidecar ($sidecar) — prose results are not evidence (skills/testing/test-results-sidecar.md)."
      REPORT_ISSUES=$((REPORT_ISSUES + 1)); return
    fi
    check_results_sidecar "$agent" "$sidecar" || REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi

  # A2 — machine-checkable JSON sidecar preferred. If a `<report>.json` sits beside the markdown
  # report and parses, use jq NUMERIC assertions (robust) instead of the grep/awk heuristics below.
  # Schema (progressive; any subset): {blocking:N, findings:[{severity,resolved}], total,passed,failed}.
  if [ -f "$sidecar" ] && jq -e . "$sidecar" >/dev/null 2>&1; then
    sc_bad=0
    if [ "$(jq -r 'has("findings")' "$sidecar" 2>/dev/null)" = "true" ]; then
      ub=$(jq -r '[.findings[]? | select((.severity|ascii_upcase)=="BLOCKING") | select((.resolved // false) != true)] | length' "$sidecar" 2>/dev/null || echo 0)
    else
      ub=$(jq -r '(.blocking // 0)' "$sidecar" 2>/dev/null || echo 0)
    fi
    [ -z "$ub" ] && ub=0
    if [ "$ub" -gt 0 ] 2>/dev/null; then
      fail "report sidecar '$sidecar' (agent '$agent') has $ub unresolved BLOCKING finding(s)."; sc_bad=1
    fi
    if [ "$(jq -r 'has("total")' "$sidecar" 2>/dev/null)" = "true" ]; then
      total=$(jq -r '(.total // 0)' "$sidecar" 2>/dev/null || echo 0)
      failed=$(jq -r '(.failed // 0)' "$sidecar" 2>/dev/null || echo 0)
      if [ "$total" -le 0 ] 2>/dev/null; then fail "report sidecar '$sidecar' (agent '$agent') reports total=$total — no tests ran."; sc_bad=1; fi
      if [ "$failed" -gt 0 ] 2>/dev/null; then fail "report sidecar '$sidecar' (agent '$agent') reports failed=$failed."; sc_bad=1; fi
    fi
    if [ "$sc_bad" -eq 0 ]; then ok "report OK (json sidecar): $sidecar (agent '$agent')"; else REPORT_ISSUES=$((REPORT_ISSUES + 1)); fi
    return
  fi

  # The report's own machine-readable count line is authoritative when present: every Track-A/C
  # agent must end with "BLOCKING:N WARNING:N INFO:N" (develop-orchestrator Wave 4). Prose heuristics
  # below are only a fallback for reports without it — they false-blocked clean reports that mention
  # "non-blocking", severity legends or zero-count table rows (review 2026-09-30, B1).
  COUNT_LINE="$(grep -Eo 'BLOCKING:[[:space:]]*[0-9]+[[:space:]]+WARNING:[[:space:]]*[0-9]+[[:space:]]+INFO:[[:space:]]*[0-9]+' "$candidate" | tail -1)"
  if [ -n "$COUNT_LINE" ]; then
    nb="$(printf '%s' "$COUNT_LINE" | sed -E 's/^BLOCKING:[[:space:]]*([0-9]+).*/\1/')"
    if [ "${nb:-0}" -gt 0 ] 2>/dev/null; then
      fail "report '$report' (agent '$agent') count line reports BLOCKING:$nb."
      # a security report's BLOCKING:N is N findings — each needs its own acknowledgement to be forced
      is_security_agent "$agent" && [ "$nb" -gt 1 ] 2>/dev/null && SECURITY_FAILS=$((SECURITY_FAILS + nb - 1))
      REPORT_ISSUES=$((REPORT_ISSUES + 1))
    else
      ok "report OK (count line ${COUNT_LINE}): $report (agent '$agent')"
    fi
    return
  fi

  # Stub detection for test reports: a "Total: 0" results line or a bare "SKIPPED". Only lines that
  # START with total (optionally bold/bulleted/table-celled) count, so prose like "meta.total=0" or
  # "Total: 120 | Failed: 0" no longer trips it.
  if grep -Eiq '^[[:space:]|*_-]*total[[:space:]*_]*[:=|][[:space:]*_|]*0([^0-9]|$)' "$candidate"; then
    fail "report '$report' (agent '$agent') is a stub — contains 'total: 0' (no tests ran)."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi
  if grep -Eq '(^|[^A-Za-z])SKIPPED([^A-Za-z]|$)' "$candidate"; then
    fail "report '$report' (agent '$agent') contains 'SKIPPED' — evidence not produced."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi

  # Unresolved BLOCKING detection (one-pass, line-oriented — awk so no fragile multi-count math).
  # Classification per line containing "BLOCKING" (case-insensitive):
  #   benign   — a summary line asserting NONE: "no BLOCKING", "0 BLOCKING", "BLOCKING: 0",
  #              "BLOCKING count: 0". These are not findings; ignore.
  #   resolved — the line ALSO says "resolved" (same-line resolution marker). Counts +1 resolved.
  #   finding  — any other BLOCKING line. Counts +1 finding.
  # A report is clean iff findings <= resolved (every raised BLOCKING has a resolution marker,
  # whether same-line or on a LATER line — order-insensitive counting is sufficient and robust).
  UNRESOLVED=$(awk '
    BEGIN{ f=0; r=0 }
    {
      line=$0
      if (line !~ /BLOCKING/ && line !~ /blocking/) next
      low=tolower(line)
      # benign "none" summary lines
      if (low ~ /no[ \t]+blocking/ || low ~ /blocking[ \t]*[:=]?[ \t]*0([^0-9]|$)/ \
          || low ~ /0[ \t]+blocking/ || low ~ /blocking[ \t]*count[ \t]*[:=][ \t]*0/) next
      # "non-blocking" is not a finding; neither is a table row whose last cell is 0
      # (e.g. "| Copyleft License Issues (BLOCKING) | 0 |"). Legend lines are left to the count line.
      if (low ~ /non[- ]?blocking/) next
      if (low ~ /\|[ \t]*0[ \t]*\|[ \t]*$/) next
      if (low ~ /resolved/) { r++ ; next }
      f++
    }
    END{ u = f - r; if (u < 0) u = 0; print u }
  ' "$candidate")
  UNRESOLVED=${UNRESOLVED:-0}
  if [ "$UNRESOLVED" -gt 0 ]; then
    fail "report '$report' (agent '$agent') has $UNRESOLVED unresolved BLOCKING finding(s)."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    return
  fi

  ok "report OK: $report (agent '$agent')"
}

while IFS=$'\t' read -r agent report; do
  before=${#FAILURES[@]}
  check_report "$agent" "$report"
  if is_security_agent "$agent" && [ "${#FAILURES[@]}" -gt "$before" ]; then SECURITY_FAILS=$((SECURITY_FAILS + ${#FAILURES[@]} - before)); fi
done <<< "$REPORTS"

# A required test agent that "completed" without logging its results can't be checked at all.
for agent in ${REQUIRED_AGENTS[@]+"${REQUIRED_AGENTS[@]}"}; do
  is_test_agent "$agent" || continue
  has_report="$(jq -r --arg a "$agent" 'select(.agent==$a and .status=="completed") | .report // "" | select(. != "" and (ascii_downcase) != "null" and (ascii_downcase) != "none")' "$EXEC" 2>/dev/null | head -1)"
  if printf '%s\n' "$COMPLETED_SET" | grep -qxF "$agent" && [ -z "$has_report" ]; then
    fail "test agent '$agent' completed without logging a report/sidecar — its results can't be verified."
  fi
done

# Evidence can only be bound to committed code (explicit-phase gate).
if [ "$CODE_DIRTY" = "true" ]; then
  fail "uncommitted code changes (${DIRTY_PATHS}) — commit them (untracked build/test output belongs in .gitignore or agent_state/), re-run the final verification (Wave 5v), then gate; evidence can't describe uncommitted code."
fi

# ---------------------------------------------------------------------------
# 5a. Check (f): no pending debate. A blocking decision escalated to the debate team must have a valid
#     verdict (or be auto-resolved in agent_state/debates/unresolved.json, or withdrawn with a reason)
#     before the phase gates, and a verdict must reach docs/DECISIONS.md. debate-status.py is the only
#     reader of agent_state/debates/ (the gate used to glob a name the protocol never wrote — review
#     2026-09-30, D1/D2). A pending debate is a finding: gate.forced can override it.
# ---------------------------------------------------------------------------
echo "── (f) no pending debate ──"
DEBATE_STATUS="${HOOK_DIR:-.claude/hooks}/debate-status.py"
[ -f "$DEBATE_STATUS" ] || DEBATE_STATUS=".claude/hooks/debate-status.py"
if ! ls agent_state/debates/*.json >/dev/null 2>&1; then
  ok "no debates recorded"
elif [ ! -f "$DEBATE_STATUS" ] || ! command -v python3 >/dev/null 2>&1; then
  fail "agent_state/debates/ has debates but debate-status.py (or python3) is unavailable — can't tell whether one is pending (copy it from ~/.claude/hooks/startup/)."
else
  DEBATE_OUT="$(python3 "$DEBATE_STATUS" --root "$PWD" --phase "$PHASE" --check 2>&1)"; DEBATE_RC=$?
  printf '%s\n' "$DEBATE_OUT" | grep -v '^BLOCKING: ' | sed 's/^/    /'
  if [ "$DEBATE_RC" -eq 0 ]; then
    ok "every blocking debate for phase $PHASE has a verdict (or is auto-resolved/withdrawn)"
  else
    while IFS= read -r b; do [ -n "$b" ] && fail "${b#BLOCKING: }"; done < <(printf '%s\n' "$DEBATE_OUT" | grep '^BLOCKING: ')
    [ "$DEBATE_RC" -ne 2 ] && fail "debate-status.py failed (exit $DEBATE_RC)"
  fi
fi

# ---------------------------------------------------------------------------
# 5b. Check (e): EXECUTION-GROUNDED verification. Rather than trust a report that CLAIMS tests passed,
#     RUN the project's own test/lint/typecheck commands and block on a non-zero exit. Highest-value
#     enforcement — grounds the gate in real execution, not self-report (SWE-bench-style).
#     Safe + opt-in: runs ONLY when (1) an explicit phase arg was given (Wave 6 / the PostToolUse
#     manifest hook — NOT the passive Stop sweep), (2) a verify-commands config exists, and (3) it is
#     not disabled via VERIFY_GATE_SKIP_EXEC=1. Absent config => advisory skip (framework repo safe).
#     Config (first found): <phase>/verify-commands.json | agent_state/config/verify-commands.json |
#     sdlc-verify.json — shape: {"typecheck":"<cmd>","lint":"<cmd>","test":"<cmd>","timeout_seconds":600}
# ---------------------------------------------------------------------------
echo "── (e) execution-grounded verification ──"
VERIFY_CFG=""
for c in "$PHASE_DIR/verify-commands.json" "agent_state/config/verify-commands.json" "sdlc-verify.json"; do
  [ -f "$c" ] && { VERIFY_CFG="$c"; break; }
done
if [ "${VERIFY_GATE_SKIP_EXEC:-0}" = "1" ]; then
  ok "execution-grounded verification skipped (VERIFY_GATE_SKIP_EXEC=1)"
elif [ "$AUTODETECT" = "true" ]; then
  ok "passive sweep — execution-grounded verification deferred to the explicit-phase gate"
elif [ -z "$VERIFY_CFG" ]; then
  ok "no verify-commands config — execution-grounded verification not configured (advisory)"
elif ! jq -e . "$VERIFY_CFG" >/dev/null 2>&1; then
  fail "verify-commands config is not valid JSON: $VERIFY_CFG"
else
  TOSECS="$(jq -r '.timeout_seconds // 600' "$VERIFY_CFG" 2>/dev/null)"
  TO=""
  if command -v timeout >/dev/null 2>&1; then TO="timeout ${TOSECS}"
  elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout ${TOSECS}"; fi
  ran_any=0
  for key in typecheck lint test; do
    cmd="$(jq -r --arg k "$key" '.[$k] // empty' "$VERIFY_CFG" 2>/dev/null)"
    [ -z "$cmd" ] && continue
    ran_any=1
    echo "  → running $key: $cmd"
    mkdir -p "$PHASE_DIR/junit"   # commands write JUnit under agent_state/phases/$PHASE/junit/
    if PHASE="$PHASE" $TO bash -o pipefail -c "$cmd" >"/tmp/verify-gate-$key.log" 2>&1; then
      ok "$key passed: $cmd"
    else
      rc=$?
      fail "$key FAILED (exit $rc): $cmd — see /tmp/verify-gate-$key.log"
      tail -5 "/tmp/verify-gate-$key.log" 2>/dev/null | sed 's/^/      | /'
    fi
  done
  [ "$ran_any" -eq 0 ] && ok "verify-commands config present but declares no test/lint/typecheck commands"
fi

# ---------------------------------------------------------------------------
# 6. Check (d): gate.passed honesty.
#    If manifest claims gate.passed==true, all of the above must have held. Since we accumulate
#    FAILURES, the presence of ANY failure while gate.passed==true is the smoking gun.
# ---------------------------------------------------------------------------
echo "── (d) gate.passed honesty ──"
if [ "$GATE_PASSED_CLAIMED" = "true" ]; then
  if [ "${#FAILURES[@]}" -gt 0 ]; then
    fail "manifest.gate.passed==true but ${#FAILURES[@]} check(s) failed above — gate passed WITHOUT evidence."
  else
    ok "manifest.gate.passed==true and all evidence checks hold"
  fi
else
  ok "manifest does not (yet) claim gate.passed — evidence checks are advisory for this run"
fi

# ---------------------------------------------------------------------------
# 6b. Forced-gate override (user-approved). A well-formed gate.forced downgrades FINDING failures
#     (unresolved BLOCKINGs, dangling failures, gate.passed honesty) to a loud WARNING and lets the
#     turn proceed — this is the deliberate "--force_gate" escape hatch. It does NOT override a
#     STRUCTURALLY INCOMPLETE roster: you cannot "force" past a required agent that never ran (that
#     is missing evidence, not an accepted blocker). Validity = valid JSON with a non-empty
#     blockers[] and a non-empty user_rationale (so an empty file can't silently disarm the gate).
# ---------------------------------------------------------------------------
FORCED_VALID="false"
if [ -f "$FORCED" ] && jq -e '(.blockers | type=="array" and length>0) and (.user_rationale // "" | length>0)' "$FORCED" >/dev/null 2>&1; then
  FORCED_VALID="true"
fi
# Security findings can't ride a blanket override (board review 2026-09-30, SEC-01): each one needs its
# own entry in gate.forced.security_acknowledged ([{finding, approved_by, reason}]) — written by the
# human who read it, never by a fix loop.
if [ "$FORCED_VALID" = "true" ] && [ "$SECURITY_FAILS" -gt 0 ]; then
  ACKS="$(jq -r '[.security_acknowledged[]? | select((.finding // "") != "" and (.approved_by // "") != "" and (.reason // "") != "")] | length' "$FORCED" 2>/dev/null || echo 0)"
  if [ "${ACKS:-0}" -lt "$SECURITY_FAILS" ]; then
    echo "  ✗ gate.forced cannot override $SECURITY_FAILS security finding(s) with ${ACKS:-0} per-finding acknowledgement(s) (security_acknowledged[])."
    FORCED_VALID="false"
  fi
fi

# ---------------------------------------------------------------------------
# 7. Verdict.
# ---------------------------------------------------------------------------
echo "────────────────────────────────────────────────────────────────"
if [ "${#FAILURES[@]}" -eq 0 ]; then
  echo "RESULT: ✅ PASS — Phase $PHASE gate evidence is complete and honest."
  exit 0
elif [ "$FORCED_VALID" = "true" ] && [ "$ROSTER_INCOMPLETE" = "false" ]; then
  echo "RESULT: ⚠️  FORCED PASS — Phase $PHASE has ${#FAILURES[@]} unresolved blocker(s), OVERRIDDEN"
  echo "        by an explicit user-approved gate.forced ($FORCED)."
  i=1
  for f in "${FAILURES[@]}"; do echo "   $i. (overridden) $f"; i=$((i + 1)); done
  echo ""
  echo "   Rationale: $(jq -r '.user_rationale' "$FORCED" 2>/dev/null)"
  echo "   These blockers MUST be carried forward and resolved (see Forced Gate Carry-Forward)."
  exit 0
else
  echo "RESULT: ❌ BLOCK — Phase $PHASE (${#FAILURES[@]} check(s) failed):"
  i=1
  for f in "${FAILURES[@]}"; do
    echo "   $i. $f"
    i=$((i + 1))
  done
  echo ""
  if [ "$FORCED_VALID" = "true" ] && [ "$ROSTER_INCOMPLETE" = "true" ]; then
    echo "A gate.forced is present but the roster is INCOMPLETE — a required agent never ran."
    echo "--force_gate overrides findings, not missing agents. Run the missing agent(s), then force."
  else
    echo "The phase gate is NOT satisfied. Do not mark gate.passed until every item above is fixed."
    echo "(To override known blockers with explicit approval, write a valid gate.forced — see /develop --force_gate.)"
  fi
  exit 2
fi
