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
#   (a) roster completeness — every name in roster.required has a status:"completed" line.
#   (b) report integrity    — every completed line with a non-null "report" points to a file that
#                             EXISTS and is non-stub: test reports rejected on "total: 0"/"SKIPPED";
#                             ANY report rejected on an unresolved "BLOCKING" (a BLOCKING line with
#                             no later matching "BLOCKING ... resolved").
#   (c) no dangling failure — no "failed" status without a LATER "completed" for the same agent.
#   (d) gate.passed honesty — if manifest.json has gate.passed==true, (a)-(c) must STILL hold
#                             (this catches the known "gate.passed written without reports" bug).
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

# ---------------------------------------------------------------------------
# 0. Locate the project root so this works regardless of the caller's cwd.
#    Claude Code sets CLAUDE_PROJECT_DIR for hooks; fall back to git, then cwd.
# ---------------------------------------------------------------------------
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
  if [ -f "$MANIFEST" ] && jq -e . "$MANIFEST" >/dev/null 2>&1; then
    _claimed="$(jq -r 'try (.gate.passed) catch false | if . == true then "true" else "false" end' "$MANIFEST" 2>/dev/null || echo false)"
  fi
  [ "$_claimed" != "true" ] && exit 0   # nothing claimed → nothing to verify → silent PASS
fi

echo "════════════════════════════════════════════════════════════════"
echo "verify-gate — Phase $PHASE  ($PHASE_DIR)"
echo "════════════════════════════════════════════════════════════════"

FAILURES=()          # human-readable block reasons
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
      MISSING=$((MISSING + 1))
    fi
  done
  [ "$MISSING" -eq 0 ] && ok "all ${#REQUIRED_AGENTS[@]} required agents completed"
fi

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
REPORTS="$(jq -r 'select(.status=="completed") | select(.report != null and .report != "") | "\(.agent)\t\(.report)"' "$EXEC" 2>/dev/null | sort -u)"

if [ -z "$REPORTS" ]; then
  echo "  (no completed lines carry a report path)"
fi

REPORT_ISSUES=0
while IFS=$'\t' read -r agent report; do
  [ -z "$report" ] && continue
  # Resolve report path: allow it to be relative to project root or to the phase dir.
  candidate="$report"
  if [ ! -f "$candidate" ] && [ -f "$PHASE_DIR/$report" ]; then
    candidate="$PHASE_DIR/$report"
  fi
  if [ ! -f "$candidate" ]; then
    fail "report referenced by '$agent' does not exist: $report"
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    continue
  fi

  # Stub detection for test reports: "total: 0" (any spacing/case) or a bare "SKIPPED".
  # We treat a report as a "test report" heuristically if agent name or filename implies tests,
  # BUT the "total: 0" / "SKIPPED" check is cheap and safe to apply to all reports.
  if grep -Eiq 'total[[:space:]]*[:=][[:space:]]*0([^0-9]|$)' "$candidate"; then
    fail "report '$report' (agent '$agent') is a stub — contains 'total: 0' (no tests ran)."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    continue
  fi
  if grep -Eq '(^|[^A-Za-z])SKIPPED([^A-Za-z]|$)' "$candidate"; then
    fail "report '$report' (agent '$agent') contains 'SKIPPED' — evidence not produced."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    continue
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
      if (low ~ /resolved/) { r++ ; next }
      f++
    }
    END{ u = f - r; if (u < 0) u = 0; print u }
  ' "$candidate")
  UNRESOLVED=${UNRESOLVED:-0}
  if [ "$UNRESOLVED" -gt 0 ]; then
    fail "report '$report' (agent '$agent') has $UNRESOLVED unresolved BLOCKING finding(s)."
    REPORT_ISSUES=$((REPORT_ISSUES + 1))
    continue
  fi

  ok "report OK: $report (agent '$agent')"
done <<< "$REPORTS"

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
# 7. Verdict.
# ---------------------------------------------------------------------------
echo "────────────────────────────────────────────────────────────────"
if [ "${#FAILURES[@]}" -eq 0 ]; then
  echo "RESULT: ✅ PASS — Phase $PHASE gate evidence is complete and honest."
  exit 0
else
  echo "RESULT: ❌ BLOCK — Phase $PHASE (${#FAILURES[@]} check(s) failed):"
  i=1
  for f in "${FAILURES[@]}"; do
    echo "   $i. $f"
    i=$((i + 1))
  done
  echo ""
  echo "The phase gate is NOT satisfied. Do not mark gate.passed until every item above is fixed."
  exit 2
fi
