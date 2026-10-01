<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 6 — Phase Gate

**Single source of truth.** The canonical gate is `/develop-orchestrator` Wave 6, which itself
defers to the shared hook `.claude/hooks/verify-gate.sh` for the execution-guarantee check (roster
completeness + every completed agent's report exists and is non-stub + no unresolved `failed`). This
Step 6 is the equivalent check for anyone running `/develop` directly; **if the required-report set
here ever diverges from the orchestrator's, the orchestrator wins — reconcile back to it.** The two
now share ONE required set (below), with the same report paths (`reports/…`, not a separate
`agent_state/reconciliation/…` path).

**Always-required reports** (a missing/stub one BLOCKS the gate — this is the human-readable view of
what `verify-gate.sh` check (b) enforces from `roster.required`; the hook, not a duplicated array
here, is the source of truth — see the "Gate File Precondition Check" block above):

```text
Gate Item                    Source File                                          Pass Condition
─────────────────────────────────────────────────────────────────────────────────────────────────
Unit tests                   agent_state/phases/${PHASE}/reports/unit_tests.md   No FAILED tests AND total > 0
Integration tests            agent_state/phases/${PHASE}/reports/integration_tests.md   No FAILED tests AND total > 0
E2E tests (MANDATORY)        agent_state/phases/${PHASE}/reports/e2e_results.md    No FAILED tests AND total > 0 (browser OR CLI/pipeline)
Independent re-run            agent_state/phases/${PHASE}/reports/test_results.json   blocking == 0 (writer counts match test_runner's re-run)
Mobile tests (if in roster)  agent_state/phases/${PHASE}/reports/mobile_test_results.md   No FAILED tests AND total > 0
Mobile device E2E (if roster) agent_state/phases/${PHASE}/reports/mobile_e2e_results.json  iOS AND Android each run (not blocked), 0 failed
Mobile platform (if roster)  agent_state/phases/${PHASE}/reports/mobile_platform_audit.json  blocking == 0
Reconciliation (spec↔impl)   agent_state/reconciliation/phase-${PHASE}/specs_vs_impl.md   No BLOCKING findings (MISSING resolved, unspecced acknowledged)
Reconciliation (spec↔tests)  agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.md  No BLOCKING findings; no HIGH-priority untested behaviors
TC-* ID inventory (if specs) agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md  100% coverage for HIGH+MEDIUM TC-* IDs (skip if no TC-* IDs in specs)
Code review I                agent_state/phases/${PHASE}/reports/code_review_I.md   No BLOCKING issues
Code review II               agent_state/phases/${PHASE}/reports/code_review_II.md  No architecture violations
Security review              agent_state/phases/${PHASE}/reports/security_review.md  No HIGH severity findings
Dependency scan              agent_state/phases/${PHASE}/reports/dependency_scan.md  No CRITICAL/HIGH CVE without an applied fix
Code quality                 agent_state/phases/${PHASE}/reports/quality_gate.md    No BLOCKING (TODOs/stubs/secrets/dead code)
Acceptance tests             agent_state/phases/${PHASE}/reports/acceptance_report.md   All in-scope use cases: PASS
Cross-phase regression       manifest.json → cross_phase_regression                    All affected phases PASSED (skip if PHASE == 1)
```

**Conditional reports** — required ONLY when the phase has the relevant surface; otherwise the item is
recorded as `not_applicable` (an explicit, auditable skip — never a silent pass). The condition is
determined from the phase's own code/specs, not guessed:

```text
Gate Item (CONDITIONAL)      Source File                                          Required WHEN … / else
─────────────────────────────────────────────────────────────────────────────────────────────────
SAST + secret scanning       agent_state/phases/${PHASE}/reports/quality_gate.md     ALWAYS (code_quality_verifier Checks 3 + 9, fixed semgrep/gitleaks commands) → BLOCKING:0; a scan that did not run is itself BLOCKING (Stage 4c).
Migration safety             agent_state/phases/${PHASE}/reports/migration_safety.md   WHEN phase adds/changes DB migrations → Zero CRITICAL findings, DOWN coverage ≥ 90%. Else: not_applicable.
Visual validation            agent_state/phases/${PHASE}/reports/visual_validation.md  WHEN *.wireframe.html files exist for this phase → Mismatch < 10%. Else: not_applicable.
Tenant isolation             agent_state/phases/${PHASE}/reports/tenant_isolation.md   WHEN project is multi-tenant (roster marks tenant_isolation_verifier required) → No cross-tenant leak. Else: not_applicable.
UI code optimization         agent_state/phases/${PHASE}/reports/ui_code_optimization.md  ONLY if /optimize ran (not part of /develop)
Code optimization            agent_state/phases/${PHASE}/reports/code_optimization.md     ONLY if /optimize ran (not part of /develop)
```

> **Spec compliance** is covered by the spec↔impl reconciliation report (`specs_vs_impl.md`) above —
> there is no separate `spec_compliance_review.md` gate item (that was a divergent report name that
> the orchestrator never required). If a phase produces a distinct spec-compliance report, fold its
> findings into `specs_vs_impl.md` so there is one reconciliation source.

**E2E gate is ALWAYS active.** Every phase must have E2E tests — generated during Step 3c.1 if they don't exist. The conditional gates above activate only when their surface is present; each inactive one must be logged `not_applicable`, never omitted silently.

### Gate Item Enforcement (EXECUTABLE — do not eyeball the table)

**The table above states the pass conditions; this block enforces them.** The per-phase gate was
historically honor-system — the parent read a report and judged "looks like it passed." A subagent
report claiming "42 passing, 0 failed" was accepted without re-derivation. Parse the numbers and
block on them (mirrors the counting used in `/accept` and `gate-verification.md` Layer 1):

```bash
GATE_BLOCKED=false
REPORTS_DIR="agent_state/phases/${PHASE:?}/reports"

# 1. Test tiers — parse totals; block on FAILED>0, total==0, or no total at all.
python3 - "$REPORTS_DIR" << 'PY' || GATE_BLOCKED=true
import re, sys, os, glob
d = sys.argv[1]
tiers = {"unit_tests.md":"unit","integration_tests.md":"integration",
         "e2e_results.md":"e2e","acceptance_report.md":"acceptance"}
bad = False
for fn, name in tiers.items():
    p = os.path.join(d, fn)
    if not os.path.exists(p):
        print(f"⛔ {name}: report missing"); bad = True; continue
    txt = open(p, encoding="utf-8", errors="ignore").read().lower()
    failed = sum(int(m) for m in re.findall(r'failed[:\s]+(\d+)', txt))
    totals = [int(m) for m in re.findall(r'total[:\s]+(\d+)', txt)]
    total = max(totals) if totals else None
    if failed > 0:
        print(f"⛔ {name}: {failed} FAILED test(s) — gate blocked"); bad = True
    if total is None:
        print(f"⛔ {name}: no 'total: N' in the report — nothing shows that tests ran"); bad = True
    elif total == 0:
        print(f"⛔ {name}: total=0 — tier was skipped"); bad = True
if not bad:
    print("✓ All test tiers: 0 failed, non-zero totals")
sys.exit(1 if bad else 0)
PY

# 2. TC-* coverage — HIGH+MEDIUM must be 100%. Read the tc-inventory sidecar Step 3d wrote (verdict
#    PASS = every HIGH/MEDIUM ID has a test that ran and passed), not prose. No sidecar blocks too,
#    unless the specs define no TC-* IDs at all (the table's "skip if no TC-* IDs in specs").
#    (This used grep -P, which macOS grep rejects: the check silently never ran there.)
TC_JSON="agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.json"
if [ -f "$TC_JSON" ]; then
  if ! jq -e '.verdict == "PASS"' "$TC_JSON" >/dev/null 2>&1; then
    echo "⛔ GATE BLOCKED: TC-* inventory verdict is $(jq -r '.verdict // "missing"' "$TC_JSON" 2>/dev/null || echo unreadable) ($TC_JSON)"
    GATE_BLOCKED=true
  fi
elif grep -rqE 'TC-[A-Z0-9]+-[0-9]+' "docs/design/phases/${PHASE}/specs" 2>/dev/null; then
  echo "⛔ GATE BLOCKED: the specs define TC-* IDs but $TC_JSON is missing (run Step 3d)"; GATE_BLOCKED=true
fi

# 3. Review dimensions — every report must exist. Its count line "BLOCKING:N WARNING:N INFO:N" (what
#    each Wave 4 reviewer ends with) decides, as in verify-gate.sh; without one, the same prose rule:
#    BLOCKING lines that aren't "none" summaries or "non-blocking", minus lines marked resolved.
for R in code_review_I code_review_II security_review; do
  F="$REPORTS_DIR/${R}.md"
  if [ ! -s "$F" ]; then
    echo "⛔ GATE BLOCKED: ${R}.md is missing or empty"; GATE_BLOCKED=true; continue
  fi
  NB=$(grep -Eo 'BLOCKING:[[:space:]]*[0-9]+[[:space:]]+WARNING:' "$F" | tail -1 | grep -Eo '[0-9]+' || true)
  if [ -z "$NB" ]; then
    NB=$(awk '{ l = tolower($(0)); if (l !~ /blocking/) next
                if (l ~ /no[ \t]+blocking|blocking[ \t]*[:=]?[ \t]*0([^0-9]|$)|0[ \t]+blocking|non[- ]?blocking|\|[ \t]*0[ \t]*\|[ \t]*$/) next
                if (l ~ /resolved/) { r++; next }; f++ }
              END { u = f - r; print (u > 0 ? u : 0) }' "$F")
  fi
  if [ "$NB" -gt 0 ]; then
    echo "⛔ GATE BLOCKED: ${R} has ${NB} unresolved BLOCKING finding(s)"; GATE_BLOCKED=true
  fi
done

if [ "$GATE_BLOCKED" = true ]; then
  echo "⛔ Phase gate NOT passed — route the blockers above to the Wave 5 feedback loop."
  exit 1
fi
echo "✅ Gate item enforcement passed — proceeding to write gate.passed"
```

> **Canonical enforcement lives in `/develop-orchestrator`** (Wave 0b roster + Wave 6 Layers 0–3 +
> `gate-verification.md`). This block is the equivalent executable check for anyone running
> `/develop` directly. If the two ever diverge, the orchestrator wins — reconcile back to it.

### Bug Severity Classification

All items in `known_issues[]` and `carried_forward[]` MUST have a severity level:

| Severity | Definition | Gate Impact | Carry-Forward Limit |
|----------|-----------|-------------|-------------------|
| `critical` | Data loss, security breach, complete feature broken | BLOCKS gate — must fix | 0 phases (fix immediately) |
| `high` | Major feature broken, significant UX degradation | BLOCKS gate — must fix | 1 phase max |
| `medium` | Minor feature broken, workaround exists | Does not block gate | 3 phases max |
| `low` | Cosmetic, minor inconvenience | Does not block gate | No limit (tracked) |

When severity is not explicitly set, default to `medium`.

Carry-forward enforcement:
- `critical` items that appear in `carried_forward[]` → ⛔ IMMEDIATE BLOCK, cannot proceed
- `high` items carried for >1 phase → becomes `critical` (auto-escalation)
- `medium` items carried for >3 phases → becomes `high` (auto-escalation)

If any gate item fails:
1. Write `gate.failed` with structured failure data (enables next-phase detection of "ran but failed" vs "never ran"):
   ```bash
   cat > "agent_state/phases/${PHASE}/gate.failed" <<EOF
   {
     "phase": ${PHASE},
     "failed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
     "blockers": [
       {"gate_item": "<failing gate item, e.g. unit_tests>", "details": "<what failed, with file:line>"}
     ],
     "attempt": ${ATTEMPT:-1}
   }
   EOF
   ```
2. Surface to user with specific blocker text, file location, and the exact failing entry.
3. Do not proceed to Step 7.

**Gate state machine (ternary):**
- `gate.passed` exists → phase completed successfully
- `gate.failed` exists (no `gate.passed`) → phase ran but has unresolved blockers
- Neither exists → phase has not been attempted yet
- Both exist → `gate.passed` wins (gate.failed is from a previous attempt)

When the Gate Failure Recovery Procedure resolves all blockers:
1. Write `gate.passed`
2. Rename `gate.failed` → `gate.failed.resolved` (preserve history, don't delete)

### Gate Failure Recovery Procedure

When the gate fails, DO NOT delete any phase files. Follow this sequence:
1. **Identify the blocker** — read the specific report file and find the failing entry
2. **Fix the root cause** — re-run the failing agent (e.g., fix test → re-run unit_test_agent)
3. **Re-run only the failed check** — no need to re-run the entire pipeline
4. **Re-evaluate the gate** — re-read all report files and check conditions again
5. If gate now passes → write `gate.passed` and manifest

**DO NOT:**
- Delete `agent_state/phases/${PHASE}/` — it contains all the work done so far
- Re-run the entire `/develop` pipeline — only re-run the failing step
- Modify tests to force them to pass — fix the implementation instead

### --force-gate Override

**Hard precondition: a breaking change can never be force-gated.** The prose in "Breaking Change
Detection" asserts "Hard blocks CANNOT be force-gated"; this is where that claim is ENFORCED, not just
stated. Before writing any forced-gate files, re-read `schema_evolution.md` and REFUSE the override if
any unresolved `⛔ BREAKING` remains:

```bash
SCHEMA_EVO="agent_state/phases/${PHASE}/reports/schema_evolution.md"
if [ -f "$SCHEMA_EVO" ]; then
  # An unresolved breaking change is a ⛔ BREAKING line NOT marked resolved/restored/versioned on the
  # same line. Count them; any >0 hard-blocks the force-gate.
  UNRESOLVED_BREAKING=$(grep '⛔ BREAKING' "$SCHEMA_EVO" 2>/dev/null \
    | grep -viE '(resolved|restored|versioned|deprecated alias|migration path)' | wc -l | tr -d ' ')
  if [ "${UNRESOLVED_BREAKING:-0}" -gt 0 ]; then
    echo "⛔ FORCE-GATE REFUSED: ${UNRESOLVED_BREAKING} unresolved BREAKING change(s) in $SCHEMA_EVO."
    echo "   Breaking changes cannot be force-gated (they silently break earlier phases' consumers)."
    echo "   Resolve each: restore the field, version the endpoint, or provide a deprecated-alias"
    echo "   migration path — then re-run. --force_gate does NOT override this."
    exit 1
  fi
fi
```

If `--force_gate` flag is set AND the gate has failures (and the breaking-change precondition above
passed):
1. Write `gate.passed` with a warning header:
   ```text
   ⚠ FORCED GATE — ${N} blockers overridden by user at ${TIMESTAMP}
   Overridden items: [list of failed gate items]
   ```
2. Write `gate.forced` with structured failure data:
   ```json
   {
     "phase": N,
     "forced_at": "<ISO 8601>",
     "blockers": [
       { "gate_item": "unit_tests", "details": "TestAuthFlow FAILED — flaky", "severity": "gate_override" },
       { "gate_item": "security_review", "details": "SR-3-2 HIGH: IDOR in GET /users/:id", "severity": "gate_override" }
     ],
     "security_acknowledged": [
       { "finding": "SR-3-2 HIGH: IDOR in GET /users/:id", "approved_by": "<the human's name>",
         "reason": "<why shipping it is acceptable, and the fix date>" }
     ],
     "user_rationale": "<user's reason for forcing>"
   }
   ```
   **Security findings are never forced by a blanket approval** (board review 2026-09-30, SEC-01). Every
   failure from `security_reviewer`, `tenant_isolation_verifier` or `dependency_scanner` needs its own
   `security_acknowledged` entry. The entry is written from the answer of **the human who was shown that
   finding** (its ID, file:line and exploit description), never by an agent or a fix loop.
   `verify-gate.sh` refuses the override when acknowledgements are missing. Under `/autonomous` this
   means PAUSE and ask; see its "Gate failures" rules.
3. Add overridden failures to manifest `known_issues[]` with `"severity": "gate_override"`
4. Print warning: `⚠ Gate forced with N unresolved blockers — review before release`

### Forced Gate Carry-Forward Enforcement

When the NEXT phase starts (Phase N+1 Step 0):
1. Check: `test -f agent_state/phases/$((PHASE-1))/gate.forced`
2. If exists: read `gate.forced` and surface ALL blockers prominently:
   ```text
   ⛔ FORCED GATE DETECTED — Phase $((PHASE-1)) passed with N unresolved blockers:
     - [blocker 1 details]
     - [blocker 2 details]
   These MUST be resolved in Phase ${PHASE} or explicitly re-deferred with --force_gate.
   ```
3. Phase N+1 audit (Step 1) MUST list each forced blocker as a **CRITICAL carried-forward item**
4. Phase N+1 gate (Step 6) adds an extra gate check:
   ```text
   Forced gate resolution    agent_state/phases/$((PHASE-1))/gate.forced    All blockers resolved OR explicitly re-deferred
   ```
5. If a blocker survives **2 consecutive forced gates**: it becomes **PERMANENTLY BLOCKING** — cannot be force-gated again. Must fix or remove from scope via BRD change request. (Today this rule is prose: `verify-gate.sh` does not yet compare consecutive `gate.forced` files, so the orchestrator must check it before writing a new override.)

**Anti-pattern:** Forcing gates across 3+ phases creates a project where nothing actually works. The 2-force limit prevents this.

### Manifest Write Protocol (Atomic)

All manifest writes MUST use atomic write protocol to prevent corrupt JSON from crashing downstream phases:

1. Write to `agent_state/phases/${PHASE}/manifest.json.tmp`
2. Validate the `.tmp`: JSON syntax, then the required fields (Schema Validation below)
3. If valid: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not proceed. Log error and retry write.

```bash
# Atomic manifest write: both checks run on the .tmp BEFORE the mv (a schema check after the mv
# would read a .tmp that no longer exists); a failure leaves manifest.json untouched
M="agent_state/phases/${PHASE:?}/manifest.json"
python3 - "$M.tmp" <<'PY' && mv "$M.tmp" "$M" || { echo "⛔ CORRUPT or incomplete manifest — aborting"; exit 1; }
import json, os, sys
manifest = json.load(open(sys.argv[1]))
schema = 'agent_state/manifest_schema.json'   # its "required" list wins when the project has it
required = json.load(open(schema))['required'] if os.path.exists(schema) else [
    'phase', 'goal', 'started_at', 'completed_at', 'attempt', 'brd_requirements_met',
    'test_results', 'artifacts', 'known_issues', 'carried_forward']
missing = [f for f in required if f not in manifest]
if missing:
    print(f'⛔ MANIFEST MISSING FIELDS: {missing}')
    sys.exit(1)
print('✅ Manifest JSON + required fields valid')
PY
```

This protocol also applies to any agent-level manifest writes in `agent_state/phases/${PHASE}/<agent>/manifest.json` — always write to `.tmp`, validate, then `mv`.

### Schema Validation

The atomic write above checks the `.tmp` against the manifest schema's `required` list
(`agent_state/manifest_schema.json`: `phase`, `goal`, `started_at`, `completed_at`, `attempt`,
`brd_requirements_met`, `test_results`, `artifacts`, `known_issues`, `carried_forward`) before the `mv`.

### Phase Completion Tagging

After gate passes and manifest is written:
1. `git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"`
2. This tag serves as the rollback point for future phase resets

```bash
git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"
```

### Write gate files

```bash
mkdir -p "agent_state/phases/${PHASE:?}"
touch "agent_state/phases/${PHASE}/gate.passed"
```

Write `agent_state/phases/${PHASE}/manifest.json` — the handshake for the next phase:

```json
{
  "phase": N,
  "goal": "<from PHASE_PLAN.md>",
  "started_at": "<ISO 8601 timestamp>",
  "completed_at": "<ISO 8601 timestamp>",
  "attempt": 1,
  "brd_requirements_met": ["FR-001", "FR-002", "NFR-PERF-01"],
  "acceptance_tests": {
    "use_cases_total": 5,
    "use_cases_passed": 5,
    "personas_exercised": ["Admin User", "End User"],
    "seed_data": "agent_state/phases/N/test-data/generated-seed.yaml"
  },
  "artifacts": {
    "specs":      ["docs/design/phases/N/specs/auth-flow.md"],
    "code":       ["src/services/auth.go", "src/handlers/auth.go"],
    "migrations": ["migrations/001_add_users.sql"],
    "tests":      ["src/services/auth_test.go", "tests/integration/auth_test.go"],
    "api_routes": ["POST /api/v1/auth/login", "POST /api/v1/auth/logout"]
  },
  "test_results": {
    "unit": {
      "status": "passed",
      "total": 24,
      "passed": 24,
      "failed": 0,
      "report": "agent_state/phases/N/reports/unit_tests.md"
    },
    "integration": {
      "status": "passed",
      "total": 8,
      "passed": 8,
      "failed": 0,
      "report": "agent_state/phases/N/reports/integration_tests.md"
    },
    "e2e": {
      "status": "passed",
      "total": 3,
      "passed": 3,
      "failed": 0,
      "report": "agent_state/phases/N/reports/e2e_results.md"
    }
  },
  "optimization": {
    "backend": {
      "status": "CLEAN | PARTIAL | REVERTED",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "lines_reduced": 0,
      "report": "agent_state/phases/N/reports/code_optimization.md"
    },
    "ui": {
      "status": "CLEAN | PARTIAL | REVERTED | not_run",
      "dead_code_removed": 0,
      "optimizations_applied": 0,
      "report": "agent_state/phases/N/reports/ui_code_optimization.md"
    },
    "post_optimization_tests": "not_applicable unless /optimize ran | PASS | PASS_WITH_REVERTS"
  },
  "test_case_inventory": {
    "spec_count": 0,
    "implemented_count": 0,
    "missing_count": 0,
    "orphaned_count": 0,
    "coverage_pct": 100,
    "by_category": {},
    "missing_ids": [],
    "deferred_ids": [],
    "report": "agent_state/reconciliation/phase-N/test_case_inventory.md"
  },
  "known_issues":    [],
  "carried_forward": [],
  "carried_forward_policy": "Items in carried_forward[] MUST be addressed within 1 phase. If an item survives 2 consecutive phases: it becomes a BLOCKING gate item in the 2nd phase — fix or explicitly remove from scope via BRD change request. Forced gate overrides count toward this limit — an item force-gated in Phase N and still unresolved in Phase N+1 is BLOCKING in Phase N+1."
}
```

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 6 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 4 run in fixture scenarios on macOS bash 3.2.57 (1 also on Linux bash 5.2.37 with GNU tools); 2 JSON blocks parsed + agent_state/manifest_schema.json, verify-gate.sh's gate.forced jq checks.
